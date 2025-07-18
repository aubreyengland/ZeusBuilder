import re
import json
import shutil
import logging
import pickle
from redis import Redis
from pathlib import Path
from functools import partial
from datetime import timedelta
from zeus.models import JobData
from zipfile import ZipFile, ZipInfo
from flask_sqlalchemy import SQLAlchemy
from typing import List, Dict, IO, Optional, Type
from werkzeug.utils import secure_filename
from zeus.shared.data_type_models import DataTypeBase
from zeus.services.upload_service import WorksheetLoadResp, RowLoadResp

log = logging.getLogger(__name__)

DEFAULT_REDIS_STORE_TTL_SECS = 14400  # 4 hours


class PicklSerializer:
    dumps = partial(pickle.dumps, protocol=pickle.HIGHEST_PROTOCOL)
    loads = pickle.loads


class JSONSerializer:
    @staticmethod
    def dumps(*args, **kwargs):
        return json.dumps(*args, **kwargs).encode("utf-8")

    @staticmethod
    def loads(s, *args, **kwargs):
        return json.loads(s.decode("utf-8"), *args, **kwargs)


class RedisWorkSheetStore:
    """
    Store class for bulk worksheet storage to Redis.

    Attributes:
        conn (Redis): Redis connection instance
        serializer: provides methods to load and dump models to/from Redis
        ttl: Number of seconds to retain saved records
    """

    def __init__(self, conn):
        self.conn: Redis = conn
        self.serializer = PicklSerializer()
        self.ttl = timedelta(seconds=DEFAULT_REDIS_STORE_TTL_SECS)

    @staticmethod
    def hash_key(job_id, data_type):
        return f"{job_id}:{data_type}"

    def save(self, job_id: str, ws_resp: WorksheetLoadResp) -> None:
        """
        Save the loaded rows in the WorksheetLoadResp to Redis
        as a hash with key derived from tool:job_id:data_type.
        The hash consists of row ids as keys and serialized models
        as values.
        Set an expiration TTL for the hash based on the ttl attribute.
        """
        hash_key = self.hash_key(job_id, ws_resp.data_type)
        serialized_models_by_row_id = self.serialize_rows(ws_resp.loaded_rows)

        if serialized_models_by_row_id:
            self.conn.hset(hash_key, mapping=serialized_models_by_row_id)
            self.conn.expire(hash_key, self.ttl)

    def get(self, job_id, data_type) -> Dict[str, DataTypeBase]:
        """
        Get the models stored for the provided data_type.
        Return them as a dictionary with the row ids as keys
        """
        hash_dict = self.conn.hgetall(self.hash_key(job_id, data_type))
        return {
            row_id.decode(): self.serializer.loads(hash_dict[row_id])
            for row_id in sorted(hash_dict)
        }

    def get_row(self, job_id, data_type, row_id) -> Optional[DataTypeBase]:
        """
        Return the model stored for the provided data_type and row_id.
        Return None if a matching record is not found.
        """
        model_bytes = self.conn.hget(self.hash_key(job_id, data_type), row_id)
        if model_bytes:
            return self.serializer.loads(model_bytes)  # noqa

    def serialize_rows(self, row_resps: List[RowLoadResp]) -> Dict[str, bytes]:
        """
        Prepare the row responses for storage.
        Serialize the models and return then in a dictionary
        keyed by the RowLoadResp.index value (the row id).
        """
        prepped = {}

        for row_resp in row_resps:
            row_id = str(row_resp.index)
            prepped[row_id] = self.serializer.dumps(row_resp.data)

        return prepped


class SqlWorkSheetStore:
    """
    Store class for saving worksheets to the Postgres JobData table.

    Attributes:
        user_id (int): id of the logged-in user's record
        db (SQLAlchemy): Flask-SQLAlchemy instance
    """
    def __init__(self, user_id, db):
        self.user_id: int = user_id
        self.db: SQLAlchemy = db

    def save(self, job_id, ws_resp: WorksheetLoadResp) -> None:
        """
        Clear any records for a previous workbook upload from this user,
        then save the loaded rows in the WorksheetLoadResp to the
        JobData table with the row id and model data as a json data field.
        """
        self._clear_existing_records_for_user()

        for row_resp in ws_resp.loaded_rows:
            data = {"row_id": str(row_resp.index), "data": row_resp.data.dict()}

            self.db.session.add(
                JobData(
                    job_id=job_id,
                    user_id=self.user_id,
                    data_type=ws_resp.data_type,
                    data=data,
                )
            )

        self.db.session.commit()

    def get(self, job_id, data_type, model_cls: Type[DataTypeBase]) -> Dict[str, DataTypeBase]:
        """
        Get records for the job_id and the provided data_type from the JobData
        table. Create models from the retrieved data and return them in
        a dictionary with the row ids as keys.

        # TODO: If this store will be used long-term, change table schema to
           store serialized model as bytes so model_cls is not required as an arg
        """
        return {
            record.data["row_id"]: model_cls(**record.data["data"])
            for record in self._records_for_data_type(job_id, data_type)
        }

    def get_row(self, job_id, data_type, row_id, model_cls: Type[DataTypeBase]) -> Optional[DataTypeBase]:
        """
        Get the record for the job_id, data_type and row_id provided from
        the JobData table. Return a model instance using the retrieved data

        # TODO: If this store will be used long-term, change table schema to
           store serialized model as bytes so model_cls is not required as an arg
        """
        for record in self._records_for_data_type(job_id, data_type):
            row_data = record.data
            if str(row_data["row_id"]) == str(row_id):
                return model_cls(**row_data["data"])

        return None

    @staticmethod
    def _records_for_data_type(job_id, data_type):
        """Query for existing job_data records for current user"""
        return JobData.query.filter_by(job_id=job_id, data_type=data_type)

    def _clear_existing_records_for_user(self):
        """Clear any existing cached data for the user"""
        existing_user_records = self.db.session.query(JobData).filter(
            JobData.user_id == self.user_id
        )
        count = existing_user_records.delete()
        log.debug(f"Cleared {count} old worksheet upload records for {self.user_id}")


class InMemoryWorkSheetStore:
    """
    Store class for worksheet storage in memory.
    Used for test purposes.
    """

    def __init__(self, **kwargs):
        self._store = {}

    @staticmethod
    def hash_key(job_id, data_type):
        return f"{job_id}:{data_type}"

    def save(self, job_id, ws_resp: WorksheetLoadResp) -> None:
        """
        Save the loaded rows in the WorksheetLoadResp to the _store dict.
        The key is derived from tool:job_id:data_type.
        The value is a dictionary with row ids as keys and
        model instances as values.
        """
        key = self.hash_key(job_id, ws_resp.data_type)
        serialized_models_by_row_id = self.serialize_rows(ws_resp.loaded_rows)

        if serialized_models_by_row_id:
            self._store[key] = serialized_models_by_row_id

    def get(self, job_id, data_type) -> Dict[str, DataTypeBase]:
        """
        Get the models stored for the provided data_type.
        Return them as a dictionary with the row ids as keys.
        """
        stored = self._store.get(self.hash_key(job_id, data_type), {})
        return {row_id: stored[row_id] for row_id in sorted(stored)}

    def get_row(self, job_id, data_type, row_id) -> Optional[DataTypeBase]:
        """
        Return the model stored for the provided data_type and row_id.
        Return None if a matching record is not found.
        """
        stored = self._store.get(self.hash_key(job_id, data_type), {})
        return stored.get(str(row_id))

    @staticmethod
    def serialize_rows(row_resps: List[RowLoadResp]) -> Dict[str, DataTypeBase]:
        prepped = {}

        for row_resp in row_resps:
            row_id = str(row_resp.index)
            prepped[row_id] = row_resp.data

        return prepped


class RedisWavFileStore:
    """
    Store class for wav file storage in Redis.
    Wav files are saved using a key composed of the tool:job_id:filename
    and set with an expiration TTL
    """

    def __init__(self, conn):
        self.conn: Redis = conn
        self.ttl = timedelta(seconds=DEFAULT_REDIS_STORE_TTL_SECS)

    @staticmethod
    def hash_key(job_id):
        return f"{job_id}:wav_files"

    def save(self, job_id, zip_file: IO[bytes]) -> None:
        """
        Extract wav files from the provided Zip file object and
        save them to Redis with a key composed of the tool:job_id:filename
        and with an expiration TTL.
        """
        wavs_by_name = extract_wav_files_from_zip(zip_file)
        bytes_by_file_name = {name: wav.read() for name, wav in wavs_by_name.items()}

        key = self.hash_key(job_id)

        if bytes_by_file_name:
            self.conn.hset(key, mapping=bytes_by_file_name)
            self.conn.expire(key, self.ttl)

    def get(self, job_id) -> Dict[str, bytes]:
        """
        Get all wav files saved to for the job_id.
        Return them as a dictionary with file names as keys
        and the wav file bytestream as values
        """
        redis_resp = self.conn.hgetall(self.hash_key(job_id))
        return {key.decode(): value for key, value in redis_resp.items()}

    def get_file(self, job_id, file_name) -> Optional[bytes]:
        """
        Get the wav file using the provided name from the
        store path and return the bytestream.
        Return None if the file is not found
        """
        return self.conn.hget(self.hash_key(job_id), file_name)

    def get_file_names(self, job_id) -> List[str]:
        """Return file names of stored files as a list of strings."""
        return [file_name.decode() for file_name in self.conn.hkeys(self.hash_key(job_id))]


class FileSystemWavFileStore:
    """
    Store class for wav file storage on the local file system.
    Requires a Path object for a writable file system location for store_root.
    This is defined as the "ZEUS_APP_UPLOAD_FOLDER" flask config var
    """

    def __init__(self, store_root, **kwargs):
        self.store_root: Path = store_root

    def store_path(self, job_id) -> Path:
        return Path(self.store_root / job_id)

    def save(self, job_id, zip_file) -> None:
        """
        Extract wav files from the provided Zip file object and
        save them to a subdirectory within the store_root.
        """
        wavs_by_file_name = extract_wav_files_from_zip(zip_file)
        store_path = self.store_path(job_id)
        store_path.unlink(missing_ok=True)
        store_path.mkdir()

        if wavs_by_file_name:
            for file_name, wav_fh in wavs_by_file_name.items():
                save_path = self._build_wav_file_path(job_id, file_name)
                target = open(save_path, "wb")

                with wav_fh, target:
                    shutil.copyfileobj(wav_fh, target)

    def get(self, job_id) -> Dict[str, bytes]:
        """
        Get all wav files saved to the store path.
        Return them as a dictionary with file names as keys
        and the wav file bytestream as values.
        """
        wav_files = {}
        store_path = self.store_path(job_id)

        for wav_path in store_path.glob("*.wav"):
            wav_files[wav_path.name] = wav_path.read_bytes()

        return wav_files

    def get_file(self, job_id, file_name) -> Optional[bytes]:
        """
        Get the wav file using the provided name from the
        store path and return the bytestream.
        Return None if file is not found.
        """
        wav_path = self._build_wav_file_path(job_id, file_name)

        if wav_path.exists():
            return wav_path.read_bytes()

        return None

    def get_file_names(self, job_id) -> List[str]:
        """Return a list of wav file names from the store path """
        store_path = self.store_path(job_id)
        return [wav_path.name for wav_path in store_path.glob("*.wav")]

    def _build_wav_file_path(self, job_id, file_name) -> Path:
        """
        Normalize file names to lower-case and pass through
        the werkzeug secure_filename function.
        Return as a path within the store_path.
        """
        store_path = self.store_path(job_id)
        basename = Path(file_name).name.lower()
        checked_file_name = secure_filename(basename)

        if not checked_file_name:
            raise ValueError(f"Filename {file_name} is invalid")

        return store_path / checked_file_name


class InMemoryWavFileStore:
    """
    Store class for wav file storage in memory.
    Used for test purposes.
    """

    def __init__(self, **kwargs):
        self._store = {}

    @staticmethod
    def hash_key(job_id):
        return f"{job_id}:wav_files"

    def save(self, job_id, zip_file) -> None:
        """
        Extract wav files from the provided Zip file object and
        save them to the _store dictionary
        """
        wavs_by_file_name = extract_wav_files_from_zip(zip_file)
        bytes_by_file_name = {name: fh.read() for name, fh in wavs_by_file_name.items()}

        if bytes_by_file_name:
            self._store[self.hash_key(job_id)] = bytes_by_file_name

    def get(self, job_id) -> Dict[str, bytes]:
        """
        Get all wav files saved to the store path.
        Return them as a dictionary with file names as keys
        and the wav file bytestream as values.
        """
        data = self._store.get(self.hash_key(job_id), {})
        return {key: value for key, value in data.items()}

    def get_file(self, job_id, file_name) -> Optional[bytes]:
        """
        Get the wav file using the provided name from the
        store path and return the bytestream.
        Return None if file is not found.
        """
        return self.get(job_id).get(file_name)

    def get_file_names(self, job_id) -> List[str]:
        """
        Return a list of wav file names from the store path
        """
        return list(self.get(job_id).keys())


def extract_wav_files_from_zip(fh: IO[bytes]) -> Dict[str, IO[bytes]]:
    """
    Extract wav files in the provided zip file object.
    Return them in a dictionary with wav file names as keys
    and wav file objects as value.
    """
    processed = {}
    zipfile = ZipFile(fh)

    for zipinfo in zipfile.infolist():

        if not is_wavfile(zipinfo):
            continue

        name = Path(zipinfo.filename).name
        processed[name] = zipfile.open(zipinfo)

    return processed


def is_wavfile(zipinfo: ZipInfo) -> bool:
    """
    Return True if the file represented by the ZipInfo object is
    a valid prompt wav file.

    A valid prompt wav file...
    - Has a '.wav' extension
    - Is not a directory
    - Is not within a macOS resource fork directory
    """
    return all(
        [
            re.match(r".+\.wav$", zipinfo.filename, re.I),
            not zipinfo.is_dir(),
            not re.search(r"__MACOSX", zipinfo.filename, re.I),
        ]
    )
