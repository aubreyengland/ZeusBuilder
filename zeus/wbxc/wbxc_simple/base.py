import time
import logging
from requests import Session
from typing import Iterator
import re
import base64

RETRY_RESPONSE_CODES = (423, 429)

log = logging.getLogger(__name__)


class WbxcServerFault(Exception):
    def __init__(self, response):
        message = self._message(response)
        super().__init__(message)
        self.message = message
        self.response = response

    @staticmethod
    def _message(response):
        """
        Parse Wbxc API error in one of multiple body formats.
        Return a default error if response does not contain json
        content since it is most likely a html content.
        """
        message = "Invalid Request"
        try:
            body = response.json()
            message = (
                error_message_from_message(body)
                or error_message_from_description(body)
                or error_message_from_errors_list(body)
                or message
            )

        except Exception:
            log.warning(
                f"could not parse message from Wbxc error response: {response.text}"
            )

        return message


def error_message_from_message(body: dict):
    """
    Extract useful message from an error response body that includes
    a 'message' key with a string value. Ex:
    ```
    error_body_1 = {
        "errors": [{"description": "HERE IS THE MESSAGE TO RETURN"}],
        "message": "HERE IS THE MESSAGE TO RETURN",
        "trackingId": "ROUTERGW_b06ab6c7-a82d-4dee-925d-67339e27970b",
    }
    ```
    """
    try:
        message = body.get("message")
        if isinstance(message, str):
            return message
    except Exception:
        pass

    return None


def error_message_from_description(body: dict):
    """
    Extract a useful message from an error response body that includes
    a description.
    The description may contain an encapsulated error response from
    an upstream request. This is identified by the inclusion of `error = `
    in the description text. if this is found, only return this chunk,
    otherwise return the full description text

    See `test_wbxc_client_base` for examples of each format.
    """
    try:
        descr = body["error"][0]["message"][0]["description"]
    except Exception:
        return None

    if m := re.search(r"error\s*=\s*'(?:\[.+])?\s*(.+)'", descr):
        return m.group(1)
    return descr


def error_message_from_errors_list(body: list):
    """
    Extract the first useful message from an error response body that includes
    a list of error objects.

    See `test_wbxc_client_base` for examples of each format.
    """
    try:
        return body[0]["errors"][0]["errorMessage"]
    except Exception:
        return None


class WbxcRateLimitError(WbxcServerFault):
    def __init__(self, response):
        super().__init__(response)
        self.retry_after = int(response.headers.get("Retry-After", 5)) or 5


def check_wbxc_response(response):
    if response.ok:
        return

    if response.status_code in RETRY_RESPONSE_CODES:
        raise WbxcRateLimitError(response)

    raise WbxcServerFault(response)


class WbxcSession(Session):
    def __init__(self, access_token, base_url, verify=True, timeout=15):
        super().__init__()
        self.verify = verify
        self.base_url = base_url
        self.timeout = timeout
        self._max_attempts = 3
        # RA TODO: Add a way to add custom org IDs for third-party admin account
        org_id = access_token.split("_")[2]
        self.org_id = encode_org_id_to_base64(org_id)
        self.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
            }
        )

    def send_request(self, method, url, **kwargs):
        attempt = kwargs.pop("attempt", 1)
        resp = self.request(method, url, **kwargs)

        try:
            check_wbxc_response(resp)
        except WbxcRateLimitError as exc:
            log.warning(
                f"WbxcRateLimitError on attempt {attempt}/{self._max_attempts}. {url=} {exc.retry_after=}"
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
    list_key = ""

    def __init__(self, session):
        self.session: WbxcSession = session
        self.org_id = session.org_id

    @property
    def base_url(self):
        return self.session.base_url

    def url(self, identifier="", uri="", path="") -> str:
        """
        Construct the request url from the identifier provided.
        Final url is made up of:
        self.base_url / uri / identifier / path

        The orgId query param is automatically added since it is
        required for all requests.

        Examples:
            self.uri = "locations"
            self.path = ""
            identifier = ""
            Returns: "{base_url}/locations?orgId=<orgId>"

            self.uri = "telephony/config/locations"
            self.path = ""
            identifier = "ABCD"
            Returns: "{base_url}/telephony/config/locations/ABCD?orgId=<orgId>"

            self.uri = "telephony/config/locations"
            self.path = "voicemailGroups"
            identifier = "ABCD"
            Returns: "{base_url}/telephony/config/locations/ABCD/voicemailGroups?orgId=<orgId>"

        """
        uri = uri or self.uri
        path = path or self.path
        path_items = []

        for item in (uri, identifier, path):
            item = str(item).lstrip("/")
            if item:
                path_items.append(item)

        path = "/".join(path_items)

        # RA NOTE: Issue with GET request using /v1/workspaces?orgId={orgID}
        # When using the org UUID copied from Control Hub or API Token
        # The 400 error returned is expected as the API will only accept
        # the base64 encoded orgID that's returned by the /organizations API.
        # Workaround is to remove ?orgId={orgID} from the URL as it's only required
        # When accessing the API using a third-party admin account.

        # return f"{self.base_url}/{path}?orgId={self.session.org_id}"
        return f"{self.base_url}/{path}"

    def _get(self, url, params=None) -> dict:
        resp = self.session.get(url, params=params)
        return resp.json()

    def _paged_get(self, url, key, params=None) -> Iterator[dict]:
        """
        Perform paged gets and yield the returned items
        """
        while True:
            resp = self.session.get(url, params=params)
            data = resp.json()

            yield from data.get(key, [])

            url = resp.links.get("next", {}).get("url")

            if not url:
                return

            # next url includes query params so clear the params
            # arg otherwise query params will be duplicated
            params = None


class GetEndpointMixin:
    def get(self: Endpoint, identifier, **params):
        return self._get(self.url(identifier), params=params)


class ListEndpointMixin:
    def list(self: Endpoint, identifier="", **params) -> Iterator[dict]:
        """
        Perform paged gets and yield the returned items
        """
        url = self.url(identifier)
        list_key = self.list_key or self.uri.split("/")[-1]
        yield from self._paged_get(url, list_key, params)


class CreateEndpointMixin:
    def create(self: Endpoint, payload: dict, **params) -> dict:
        resp = self.session.post(self.url(), json=payload, params=params)
        return resp.json()


class UpdateEndpointMixin:
    def update(self: Endpoint, identifier, payload, **params) -> None:
        self.session.put(self.url(identifier), json=payload, params=params)


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


def encode_org_id_to_base64(org_id: str) -> str:
    """
    Encodes the organization ID by prepending it with the Webex base URL
    and converting the result to a base64-encoded string.

    Args:
        org_id (str): The standard organization ID (UUI) from an access token
         or Control Hub.

    Returns:
        str: Base64-encoded organization ID.

    Reference: https://developer.webex.com/docs/api/v1/identity-organization
    """
    org_url = f"ciscospark://us/ORGANIZATION/{org_id}"

    return base64.b64encode(org_url.encode('utf-8')).decode('utf-8')
