import time
import logging
from requests import Session
from requests.exceptions import ConnectTimeout
from typing import Iterator

RETRY_RESPONSE_CODES = (429,)

log = logging.getLogger(__name__)


class MsTeamsServerFault(Exception):
    def __init__(self, response):
        message = self._message(response)
        super().__init__(message)
        self.message = message
        self.response = response

    @staticmethod
    def _message(response):
        try:
            res = response.json()
            message = res.get("detail") or res.get("message") or res
            # Include first validation failure if present
            if "errors" in res:
                first_msg = res["errors"][0].get("message") or ""
                first_field = res["errors"][0].get("field") or ""
                message = f"{message} {first_msg} {first_field}"
        except Exception:
            message = response.text
            if response.status_code == 500 and response.text == "":
                message = "HTTP 500 Internal Server Error. Microsoft occasionally responds with this error even when the action succeeeds. Please verify the action was successful."

        return message


class MsTeamsRateLimitError(MsTeamsServerFault):
    def __init__(self, response):
        super().__init__(response)
        self.retry_after = int(response.headers.get("Retry-After", 10)) or 10


def check_msteams_response(response):
    if response.ok:
        return

    # MS Teams Skype API does not currently return 429 Too Many Requests, but may be in the future
    if response.status_code in RETRY_RESPONSE_CODES:
        raise MsTeamsRateLimitError(response)

    raise MsTeamsServerFault(response)


class MsTeamsSession(Session):
    def __init__(self, access_token, base_url, verify=True, timeout=15):
        super().__init__()
        self.verify = verify
        self.base_url = base_url
        self.timeout = timeout
        self._max_attempts = 3
        self.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Accept": None,  # set to None to avoid 500 errors
                "Accept-Encoding": None,  # set to None to avoid 500 errors
                # Content-Type automatically set by requests
            }
        )

    def send_request(self, method, url, **kwargs):
        attempt = kwargs.pop("attempt", 1)
        try:
            resp = self.request(method, url, **kwargs)
        except ConnectTimeout as exc:
            """
            MS Teams Skype API does not have traditional rate limiting, as it is unofficial.
            Instead of responding, connections will time out after 1-2 minutes.
            This seems to occur after roughly 500 requests in a short period of time.
            So we must catch the timeout and retry the request.
            """
            log.warning(
                f"ConnectTimeout on attempt {attempt}/{self._max_attempts}. {url=} {exc=}"
            )
            if attempt < self._max_attempts:
                time.sleep(5)
                return self.send_request(method, url, attempt=attempt + 1, **kwargs)
            else:
                raise

        try:
            check_msteams_response(resp)
        except MsTeamsRateLimitError as exc:
            log.warning(
                f"MsTeamsRateLimitError on attempt {attempt}/{self._max_attempts}. {url=} {exc.retry_after=}"
            )

            if attempt < self._max_attempts:
                time.sleep(exc.retry_after)
                return self.send_request(method, url, attempt=attempt + 1, **kwargs)
            else:
                raise

        return resp

    def get(self, url, params=None, **kwargs):
        return self.send_request("GET", url, params=params, **kwargs)

    def post(self, url, params=None, data=None, json=None, **kwargs):
        return self.send_request("POST", url, params=params, data=data, json=json, **kwargs)

    def put(self, url, params=None, data=None, json=None, **kwargs):
        return self.send_request("PUT", url, params=params, data=data, json=json, **kwargs)

    def patch(self, url, params=None, data=None, json=None, **kwargs):
        return self.send_request(
            "PATCH", url, params=params, data=data, json=json, **kwargs
        )

    def delete(self, url, **kwargs):
        return self.send_request("DELETE", url, **kwargs)


class Endpoint:
    """Endpoint class with common methods."""

    uri = ""
    path = ""

    def __init__(self, session):
        self.session: MsTeamsSession = session

    @property
    def base_url(self):
        return self.session.base_url

    def url(self, identifier: str = "") -> str:
        """
        Construct the request url from the identifier provided.
        Final url is made up of:
        self.base_url / self.uri / identifier / path

        Examples:
            self.uri = "phone/users"
            self.path = ""
            identifier = ""
            Returns: "{base_url}/phone/users"

            self.uri = "phone/users"
            self.path = ""
            identifier = "1"
            Returns: "{base_url}/phone/users/1"

            self.uri = "phone/users"
            self.path = "calling_plans"
            identifier = "1"
            Returns: "{base_url}/phone/users/1/calling_plans"
        """
        path_items = []
        for item in (self.uri, identifier, self.path):
            item = str(item).lstrip("/")
            if item:
                path_items.append(item)

        path = "/".join(path_items)

        return f"{self.base_url}/{path}"

    def _get(self, url, params=None) -> dict:
        resp = self.session.get(url, params=params)
        return resp.json()

    def _paged_get(self, url, key, params=None) -> Iterator[dict]:
        """
        Perform paged gets and yield the returned items

        *Not currently used
        """
        while True:
            resp = self.session.get(url, params=params)
            data = resp.json()

            yield from data.get(key, [])

            npt = data.get("next_page_token")

            if npt:
                params["next_page_token"] = npt
            else:
                return


class GetEndpointMixin:
    def get(self: Endpoint, identifier, **params):
        return self._get(self.url(identifier), params=params)


class ListEndpointMixin:
    def list(self: Endpoint, **params) -> Iterator[dict]:
        """
        Perform a get and yield the returned items.

        *Pagination is not used, a single GET can retrieve all items for most endpoints.
        Some endpoints support Count & Skip queries, but not all.
        So if a specific endpoint requires pagination, it will need it's own list method.
        """
        return self._get(self.url(), params=params)


class CreateEndpointMixin:
    def create(self: Endpoint, payload: dict, **params) -> dict:
        resp = self.session.post(self.url(), json=payload, params=params)
        return resp.json()


class UpdateEndpointMixin:
    def update(self: Endpoint, identifier, payload, **params) -> None:
        """
        Update the item with the provided identifier.

        *Teams API updates are not consistent. Recommend creating endpoint specific update methods.
        Some endpoints require the identifier in the json payload instead of URL.
        """
        payload["id"] = identifier
        self.session.patch(self.url(), json=payload, params=params)


class DeleteEndpointMixin:
    def delete(self: Endpoint, identifier, **params) -> None:
        self.session.delete(self.url(identifier), params=params)


class CRUDEndpoint(
    Endpoint,
    GetEndpointMixin,
    ListEndpointMixin,
    CreateEndpointMixin,
    UpdateEndpointMixin,
    DeleteEndpointMixin,
):
    pass
