import time
import logging
from requests import Session
from typing import Iterator

RETRY_RESPONSE_CODES = (429,)

log = logging.getLogger(__name__)


class WxccServerFault(Exception):
    def __init__(self, response):
        message = self._message(response)
        super().__init__(message)
        self.message = message
        self.response = response

    @staticmethod
    def _message(response):
        """
        Parse Wxcc API error in one of two body formats:

        Observed:
        ```
        {
            "error": {
                "key": "400",
                "message": [{"description": "name: should not be null or blank."}],
            },
            "trackingId": "ccconfig_11fb8ddb-0985-4184-a8ce-2c6e3a5d30b8",
        ```
        Documented:
        ```
        {
            "errors": [
                {
                    "key": 400,
                    "message": "Authorization header is missing or empty"
                }
            ],
            "trackingId": "GTWY_12345678-90ab-cdef-1234-567890abcdef_0"
        }
        ```
        """
        message = response.text
        try:
            body = response.json()
            if "error" in body:
                message = body["error"]["message"][0]["description"]
            elif "errors" in body:
                message = body["errors"][0]["message"]
        except Exception:
            log.warning(f"could not parse message from Wxcc error response: {response.text}")

        return message


class WxccRateLimitError(WxccServerFault):
    def __init__(self, response):
        super().__init__(response)
        self.retry_after = int(response.headers.get("Retry-After", 5)) or 5


def check_wxcc_response(response):
    if response.ok:
        return

    if response.status_code in RETRY_RESPONSE_CODES:
        raise WxccRateLimitError(response)

    raise WxccServerFault(response)


class WxccSession(Session):
    def __init__(self, access_token, base_url, verify=True, timeout=15):
        super().__init__()
        self.verify = verify
        self.base_url = base_url
        self.timeout = timeout
        self._max_attempts = 3
        self.org_id = access_token.split("_")[2]
        self.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })

    def send_request(self, method, url, **kwargs):
        attempt = kwargs.pop("attempt", 1)
        resp = self.request(method, url, **kwargs)

        try:
            check_wxcc_response(resp)
        except WxccRateLimitError as exc:
            log.warning(f"WxccRateLimitError on attempt {attempt}/{self._max_attempts}. {url=} {exc.retry_after=}")

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

    def __init__(self, session):
        self.session: WxccSession = session
        self.org_id = session.org_id

    @property
    def base_url(self):
        return self.session.base_url

    def url(self, identifier: str = "") -> str:
        """
        Construct the request url from the identifier provided.
        Final url is made up of:
        self.base_url / self.uri / identifier / path

        Examples:
            self.uri = "skill"
            self.path = ""
            identifier = ""
            Returns: "{base_url}/skill"
        """
        path_items = []
        for item in (self.uri, identifier, self.path):
            item = str(item).lstrip("/")
            if item:
                path_items.append(item)

        path = "/".join(path_items)

        return f"{self.base_url}/organization/{self.session.org_id}/{path}"

    def _get(self, url, params=None) -> dict:
        resp = self.session.get(url, params=params)
        return resp.json()

    def _paged_get(self, url, params=None) -> Iterator[dict]:
        while True:
            resp = self.session.get(url, params=params)
            data = resp.json()

            yield from data

            next_url = resp.links.get("next", {}).get("url")

            if not next_url:
                return

            url = f"{self.base_url}{next_url}"
            # next url includes query params so clear the params
            # arg otherwise query params will be duplicated
            params = None


class GetEndpointMixin:
    def get(self: Endpoint, identifier, **params):
        return self._get(self.url(identifier), params=params)


class ListEndpointMixin:
    def list(self: Endpoint, **params) -> Iterator[dict]:
        """
        Perform paged gets and yield the returned items
        """
        url = self.url()
        yield from self._paged_get(url, params)


class CreateEndpointMixin:
    def create(self: Endpoint, payload: dict, **params) -> dict:
        resp = self.session.post(self.url(), json=payload, params=params)
        return resp.json()


class UpdateEndpointMixin:
    def update(self: Endpoint, identifier, payload, **params) -> None:
        resp = self.session.put(self.url(identifier), json=payload, params=params)
        return resp.json()


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
