import os
import logging
from zeus.app import db as FlaskDb
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable, Any
from zeus.models import ProvisioningOrg as Org
from zeus.exceptions import TokenMgrError
log = logging.getLogger(__name__)


@dataclass
class EnvAuth:
    id: str  # prefix
    name: str  # defaults to prefix
    client_id: str
    client_secret: str
    redirect_uri: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]
    access_expires: Optional[float]
    refresh_expires: Optional[float]
    scopes: List[Optional[str]]


@dataclass
class TokenResponse:
    """
    Data object defining the contents of the response
    to an access token request or refresh request
    """
    access_token: str
    refresh_token: Optional[str] = None
    access_expires: Optional[float] = None
    refresh_expires: Optional[float] = None


class EnvStore:
    """
    Implementation of the Store interface for storing token info as environment variables.

    Useful for testing. Assumes a single set of credentials for each app type so prefix
    is used as the unique identifier
    """

    def __init__(self, prefix):
        self.prefix = prefix
        self.default_refresh_expires = (datetime.now() + timedelta(days=1)).timestamp()

    def _getenv(self, attr, default: Any = "", coerce: Callable = str):
        key = f"{self.prefix.upper()}_{attr.upper()}"
        val = os.getenv(key)
        if val is None:
            return default
        return coerce(val)

    def get(self, **kwargs):
        """ Get the stored variables for self.prefix """
        client_id = self._getenv("client_id")
        client_secret = self._getenv("client_secret")
        if not all([client_id, client_secret]):
            return None

        default_refresh_expires = (datetime.now() + timedelta(days=1)).timestamp()
        return EnvAuth(
            id=self.prefix,
            client_id=client_id,
            client_secret=client_secret,
            access_token=self._getenv("access_token"),
            redirect_uri=self._getenv("redirect_uri"),
            refresh_token=self._getenv("refresh_token"),
            name=self._getenv("name", default=self.prefix),
            access_expires=self._getenv("access_expires", default=0, coerce=float),
            scopes=self._getenv("scopes", default=[], coerce=lambda x: x.split(" ")),
            refresh_expires=self._getenv("refresh_expires", default=self.default_refresh_expires, coerce=float),
        )

    @staticmethod
    def save(org: EnvAuth):
        for field, value in asdict(org).items():
            if field == "id":
                continue

            key = f"{org.id.upper()}_{field.upper()}"

            if field == "scopes":
                value = " ".join(org.scopes) if value else ""
            else:
                os.environ[key] = str(value)

    @staticmethod
    def delete(org: EnvAuth):
        for field, value in asdict(org).items():
            if field == "id":
                continue

            key = f"{org.id.upper()}_{field.upper()}"
            os.environ.pop(key, None)


class SqlaStore:
    """
    Implementation of the Store interface for databases using Flask-SQLAlchemy orm.
    A Store instance should be created and passed to the TokenMgr instance.
    """

    def __init__(self, db=None, Model=Org, **kwargs):
        """
        Args:
            db(SQLAlchemy): The SQLAlchemy mapper instance.
            Model: The SQLAlchemy model representing the Authorization table
            state_attr (str, None): Model attribute to use for lookup by
            OAuth flow state value. Defaults to id
        """
        self.db = db or FlaskDb
        self.Model = Model
        self.state_attr = kwargs.get("state_attr", "state")

    def get(self, **kwargs):
        """
        Use the provided kwargs to query for a unique Model record.
        The
        """
        val_for_state_attr = kwargs.pop("state", None)
        if val_for_state_attr:
            kwargs[self.state_attr] = val_for_state_attr
        query = self.build_query(**kwargs)
        return query.one_or_none()

    def search(self, **kwargs):
        query = self.build_query(**kwargs)
        return query.all()

    def save(self, org: Org, commit=True):
        self.db.session.add(org)
        if commit:
            self.db.session.commit()

    def delete(self, org: Org, commit=True):
        self.db.session.delete(org)
        if commit:
            self.db.session.commit()

    def build_query(self, **kwargs):
        query = self.Model.query
        for field_name, field_value in kwargs.items():
            field = getattr(self.Model, field_name, None)
            if field is None:
                raise KeyError(f"{field_name} is invalid for {self.Model}")
            query = query.filter(field == field_value)
        return query


class TokenMgrBase:
    """
    Manager implementation must minimally provide the below methods.

    The Manager class provides methods to interact with the
    OAuth API to authorize apps and request tokens. It also
    provides methods for interacting with the provided Store implementation.
    """

    def __init__(self, store=None, refresh_after_minutes=30, **kwargs):  # noqa
        self.store = store or SqlaStore()
        self.refresh_after_minutes = refresh_after_minutes

    def get(self, **kwargs):
        """Get 0 or 1 auth objects based on the provided kwargs."""
        return self.store.get(**kwargs)

    def search(self, **kwargs):
        """Search for 1 or more auth objects based on the provided kwargs."""
        return self.store.search(**kwargs)

    def save(self, org, **kwargs):
        """Save the provided auth object to the store."""
        return self.store.save(org, **kwargs)

    def delete(self, org, **kwargs):
        """Remove the provided auth object from the store."""
        return self.store.delete(org, **kwargs)

    def save_token_response(self, org, token_resp: TokenResponse):
        try:
            org.access_token = token_resp.access_token
            org.refresh_token = token_resp.refresh_token
            org.access_expires = token_resp.access_expires
            org.refresh_expires = token_resp.refresh_expires
            self.save(org)
        except Exception as exc:
            log.exception(f"Cannot save {token_resp=} to {org=}")
            raise TokenMgrError("Org update failed")

    def _should_refresh(self, org):
        """Return True if access_expires is less than refresh_after_minutes."""
        if not all([org.access_token, org.access_expires]):
            return True
        access_expires = datetime.fromtimestamp(org.access_expires)

        # access_token is expiring in less than 4 hours
        if access_expires - (timedelta(seconds=self.refresh_after_minutes * 60)) < datetime.now():
            return True
        return False

    def auth_url(self, state: str, org: Org) -> str:
        raise NotImplementedError

    def access_token(self, **kwargs) -> str:
        raise NotImplementedError

    def send_refresh_request(self, org: Org) -> TokenResponse:
        """Refresh tokens for the provided org."""
        raise NotImplementedError

    def send_token_request(self, auth_code: str, org: Org) -> TokenResponse:
        """Request tokens using the granted authorization code."""
        raise NotImplementedError

    @staticmethod
    def parse_token_response(resp_data: dict) -> TokenResponse:
        """
        Verify all required values are present in an auth response.
        Return the data in a TokenResponse ready for committing to the store.

        Implement in child class to handle vendor-specific responses

        Args:
            resp_data (dict): Content of a successful auth request

        Returns:
            TokenResponse
        """
        raise NotImplementedError

    @staticmethod
    def parse_auth_response(query_args) -> tuple:
        """
        Return auth_code and state from the query args in the
        redirected authorization response.
        Raise exception if an error is present or is either
        the code or state are missing.

        According to
         https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.2
        the code, state, error param names are mandatory
        (error_description is optional) so the same parsing logic
        should apply to all tools.

        Args:
            query_args: Query args from auth response

        Returns:
            (tuple): auth_code and state strings
        """
        if "error" in query_args:
            error_text = f"{query_args['error']} {query_args.get('error_description', '')}"
            raise TokenMgrError(f"Authorization Failed: {error_text}")

        auth_code = query_args.get("code")
        state = query_args.get("state")

        if not (auth_code and state):
            log.error(f"Unexpected Auth Response: {query_args}")
            raise TokenMgrError("Authorization Failed: Unexpected Auth Response")

        return auth_code, state


def expires_seconds_to_timestamp(seconds: float, base_dt: datetime = None) -> float:
    """
    Add the provided seconds to the provided datetime object
    and return the new value as a timestamp

    Args:
        base_dt (datetime): base datetime instance
        seconds (float): Seconds/MS to add to based_dt

    Returns:
        (float): New timestamp
    """
    base_dt = base_dt or datetime.now()
    sec_delta = timedelta(seconds=seconds)
    later = base_dt + sec_delta
    return later.timestamp()
