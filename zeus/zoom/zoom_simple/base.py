import time
import logging
from requests import Session
from typing import Iterator

RETRY_RESPONSE_CODES = (429,)

log = logging.getLogger(__name__)


class ZoomServerFault(Exception):
    def __init__(self, response):
        message = self._message(response)
        super().__init__(message)
        self.message = message
        self.response = response

    @staticmethod
    def _message(response):
        try:
            res = response.json()
            message = res["message"]
            # Include first validation failure if present
            if "errors" in res:
                first_msg = res["errors"][0].get("message") or ""
                first_field = res["errors"][0].get("field") or ""
                message = f"{message} {first_msg} {first_field}"
        except Exception:
            message = response.text

        return message


class ZoomRateLimitError(ZoomServerFault):
    def __init__(self, response):
        super().__init__(response)
        self.retry_after = int(response.headers.get("Retry-After", 5)) or 5


def check_zoom_response(response):
    if response.ok:
        return

    if response.status_code in RETRY_RESPONSE_CODES:
        raise ZoomRateLimitError(response)

    raise ZoomServerFault(response)


class ZoomSession(Session):
    def __init__(self, access_token, base_url="https://api.zoom.us/v2", verify=True, timeout=15):
        super().__init__()
        self.verify = verify
        self.base_url = base_url
        self.timeout = timeout
        self._max_attempts = 3
        self.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def send_request(self, method, url, **kwargs):
        attempt = kwargs.pop("attempt", 1)
        resp = self.request(method, url, **kwargs)

        try:
            check_zoom_response(resp)
        except ZoomRateLimitError as exc:
            log.warning(f"ZoomRateLimitError on attempt {attempt}/{self._max_attempts}. {url=} {exc.retry_after=}")

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
        return self.send_request("PATCH", url, params=params, data=data, json=json, **kwargs)

    def delete(self, url, **kwargs):
        return self.send_request("DELETE", url, **kwargs)


class Endpoint:
    """Endpoint class with common methods."""

    uri = ""
    path = ""
    list_key = ""

    def __init__(self, session):
        self.session: ZoomSession = session

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
        """
        if params is None:
            params = {}
        params.setdefault("page_size", 2000)
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
        Perform paged gets and yield the returned items
        found under the `list_key` object in the response.

        Most Zoom APIs are consistent between the LIST uri and
        the response object For example:

        LIST phone users uri:
            `/phone/users`

        LIST phone users response:
            ```
            ...
            "users": [
                <user objects>
            ],

            ```
        Where this consistency holds,the objects in the response
        can be found by using the last item in the uri path as the key.

        For endpoints where the data key in the response does not match
        the last item in the path, the `self.list_key` attribute can be
        set to override the default behavior.
        """
        url = self.url()
        list_key = self.list_key or url.split("/")[-1]
        yield from self._paged_get(url, list_key, params)


class CreateEndpointMixin:
    def create(self: Endpoint, payload: dict, **params) -> dict:
        resp = self.session.post(self.url(), json=payload, params=params)
        return resp.json()


class UpdateEndpointMixin:
    def update(self: Endpoint, identifier, payload, **params) -> None:
        self.session.patch(self.url(identifier), json=payload, params=params)


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
