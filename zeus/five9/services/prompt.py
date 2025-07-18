import logging
from zeus import registry as reg
from .. import five9_models as fm
from werkzeug.utils import secure_filename
from .shared import Five9BulkSvc, Five9BulkTask
from zeus.exceptions import ZeusFileNotFoundError
from zeus.services import BrowseSvc, ExportSvc, UploadTask, RowLoadResp

log = logging.getLogger(__name__)


@reg.bulk_service("five9", "prompts", "CREATE")
class Five9PromptCreateSvc(Five9BulkSvc):

    def __init__(self, client, model, wav_bytes=None, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current = None
        self.wav_bytes = wav_bytes

    def run(self):
        self.create_prompt()
        self.current = self.client.getPrompt(self.model.name)

        self.add_languages()

    def create_prompt(self):
        task = Five9PromptCreateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def add_languages(self):
        task = Five9PromptUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("five9", "prompts", "UPDATE")
class Five9PromptUpdateSvc(Five9BulkSvc):

    def __init__(self, client, model, wav_bytes=None, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current = None
        self.wav_bytes = wav_bytes

    def run(self):
        self.current = self.client.getPrompt(self.model.name)
        task = Five9PromptUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("five9", "prompts", "DELETE")
class Five9PromptDeleteSvc(Five9BulkSvc):

    def run(self):
        self.client.deletePrompt(self.model.name)


class Five9PromptCreateTask(Five9BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: Five9PromptCreateSvc = svc
        self.created = False

    def run(self):
        if self.model.type == "PreRecorded":
            payload = build_wav_payload(self.model, self.svc.wav_bytes)
            self.client.addPromptWavInline(**payload)
        else:
            payload = build_tts_payload(self.model)
            self.client.addPromptTTS(**payload)

        self.created = True

    def rollback(self):
        if self.created:
            self.client.deletePrompt(self.model.name)


class Five9PromptUpdateTask(Five9BulkTask):
    """
    Prompt update task for Five9 Wav and Tts prompts.
    Languages can only be added to prompts (not removed) and
    must be added one at a time so a modifyPrompt API
    call is made for each new language in the model.
    """
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: Five9PromptUpdateSvc = svc
        self.complete: bool = False
        self.current = svc.current

    def run(self):
        # Ensure modify request is made at least once if no new languages are found
        languages_to_add = self.get_languages_to_add() or [""]
        for language in languages_to_add:
            if self.model.type == "PreRecorded":
                self.update_wav_prompt(language)
            else:
                self.update_tts_prompt(language)

        self.complete = True

    def update_wav_prompt(self, language=""):
        payload = build_wav_payload(self.model, self.svc.wav_bytes, language)
        self.client.modifyPromptWavInline(**payload)

    def update_tts_prompt(self, language=""):
        payload = build_tts_payload(self.model, language)
        self.client.modifyPromptTTS(**payload)

    def get_languages_to_add(self):
        to_add = []
        for language in self.model.languages_list:
            if language not in self.current.languages:
                to_add.append(language)
        return to_add

    def rollback(self):
        # only value that can be rolled back is description
        pass


def build_tts_payload(model, language="") -> dict:
    tts_info = {
        "text": model.prompt_text,
        "sayAs": "Default",
        "sayAsFormat": "NoFormat",
    }

    # Only include language if it matches one of the supported
    # TTS languages
    if language in fm.tts_prompt_languages:
        tts_info["language"] = language

    prompt_info = build_prompt_info(model, language)

    payload = {"prompt": prompt_info, "ttsInfo": tts_info}

    return payload


def build_wav_payload(model, wav_bytes, language="") -> dict:
    prompt_info = build_prompt_info(model, language)
    payload = {"prompt": prompt_info, "wavFile": wav_bytes}

    return payload


def build_prompt_info(model, language="") -> dict:
    """
    Return a dictionary formatted for the promptInfo object
    in the add or modify prompt payload

    The languages payload property is an array but only supports a single
    entry for modify requests.  It is ignored for add requests.

    Args:
        model (Five9Prompt): data submitted by the user
        language (str): Optional language code for modify requests only

    Returns:
       prompt_info (dict): dictionary for promptInfo attribute of payload
    """
    languages = [language] if language else []
    prompt_info = {
        "name": model.name,
        "description": model.description,
        "type": model.type,
        "languages": languages,
    }
    return prompt_info


@reg.upload_task("five9", "prompts")
class Five9PromptUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            self.validate_wav_file(row)
        except ZeusFileNotFoundError as exc:
            return RowLoadResp(index=idx, error=exc.message)

        return super().validate_row(idx, row)

    def validate_wav_file(self, row):
        action = row.get("Action")
        wav_file = row.get("Wav File")

        if wav_file and action in ["CREATE", "UPDATE"]:
            if secure_filename(wav_file).lower() not in self.svc.wav_files:
                raise ZeusFileNotFoundError(f"Wav file '{wav_file}' not found")


@reg.export_service("five9", "prompts")
class Five9PromptExportSvc(ExportSvc):

    def run(self) -> dict:
        rows = []
        errors = []
        data_type = fm.Five9Prompt.schema()["data_type"]

        for resp in self.client.getPrompts():

            try:
                model = build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                log.warning(f"Prompt export failed: {exc}")
                errors.append({"name": resp.name, "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


@reg.browse_service("five9", "prompts")
class Five9PromptBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        for item in self.client.getPrompts():

            model = build_model(item)
            rows.append(model.dict())

        return rows


def build_model(resp):
    languages = ";".join(resp.languages)
    wav_file, prompt_text = "", ""

    if resp.type == "PreRecorded":
        wav_file = "< Not Available for Export >"
    else:
        prompt_text = "< Not Available for Export >"

    return fm.Five9Prompt(
        action="IGNORE",
        name=resp.name,
        type=resp.type,
        wav_file=wav_file,
        languages=languages,
        prompt_text=prompt_text,
        description=resp.description or "",
    )
