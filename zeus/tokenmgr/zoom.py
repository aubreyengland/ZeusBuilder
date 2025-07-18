import jwt
import logging
from base64 import b64encode
from requests import Session
from datetime import datetime, timedelta
from urllib import parse as urllib_parse
from .mgr_base import (
    TokenMgrBase,
    SqlaStore,
    TokenMgrError,
    TokenResponse,
    expires_seconds_to_timestamp,
)

log = logging.getLogger(__name__)

ZOOM_API_ENDPOINT = "https://api.zoom.us/v2"
ZOOM_AUTH_ENDPOINT = "https://zoom.us/oauth/authorize"
ZOOM_REFRESH_ENDPOINT = "https://zoom.us/oauth/token"
ZOOM_SCOPES = [
    "user:read",
    "meeting:read",
    "phone:read",
]

ZOOM_OAUTH_DEFAULTS = {
    "api_endpoint": ZOOM_API_ENDPOINT,
    "auth_endpoint": ZOOM_AUTH_ENDPOINT,
    "token_endpoint": ZOOM_REFRESH_ENDPOINT,
}


class ZoomTokenMgr(TokenMgrBase):
    """
    Manager class for Zoom Oauth apps.

    The Manager class provides methods to interact with the
    Zoom API to authorize apps and request tokens. It also
    provides methods for interacting with the provided Store class.
    """

    def __init__(self, store=None, refresh_after_minutes=30, **kwargs):
        """
        Manager class for Zoom Oauth apps.

        Args:
            store: SqlaStore instance for database access
            refresh_after_minutes (int): Calling the access_token method
             will automatically refresh if the token is older than this
             value in minutes
        """
        store = store or SqlaStore()
        super().__init__(store, refresh_after_minutes, **kwargs)
        self.session = Session()

    def access_token(self, org, force_refresh=False) -> str:
        """
        Convenience method to refresh the access token upon access.
        The refresh will only occur if the current token is older than
        the "refresh_after_minutes" attribute.

        Args:
            org (ProvisioningOrg): ProvisioningOrg instance
            force_refresh (bool): Make refresh request regardless of
             current access token age
        """
        if not self._should_refresh(org) and not force_refresh:
            return org.access_token

        token_resp = self.send_refresh_request(org)
        self.save_token_response(org, token_resp)
        return org.access_token

    def auth_url(self, state, oauth_app):
        """
        Construct the authorization URL for the provided auth object.

        Args:
            state (str): Value unique to this authorization that will be returned for verification
            oauth_app: (OAuthApp): OAuthApp instance

        Returns:
            (str): Authorization URL
        """
        url = f"{oauth_app.auth_endpoint}?"

        params = {
            "client_id": oauth_app.client_id,
            "response_type": "code",
            "redirect_uri": oauth_app.redirect_uri,
            "state": state,
        }

        return url + urllib_parse.urlencode(params, quote_via=urllib_parse.quote)

    def send_refresh_request(self, org) -> TokenResponse:
        """
        Refresh tokens for the provided org.

        Args:
            org: (ProvisioningOrg): ProvisioningOrg instance

        Returns:
            (dict): Dict with access/refresh tokens and expirations
        """
        body = {
            "grant_type": "refresh_token",
            "refresh_token": org.refresh_token,
        }
        resp_data = self._send_request(org.oauth.token_endpoint, org.oauth.client_id, org.oauth.client_secret, body)
        return self.parse_token_response(resp_data)

    def send_token_request(self, auth_code, org) -> TokenResponse:
        """
        Request tokens using the granted authorization code

        Args:
            auth_code (str): Code provided for this authorization attempt
            org: (ProvisioningOrg): Wxcc ProvisioningOrg instance

        Returns:
            TokenResponse
        """
        body = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": org.oauth.redirect_uri,
        }
        resp_data = self._send_request(org.oauth.token_endpoint, org.oauth.client_id, org.oauth.client_secret, body)
        return self.parse_token_response(resp_data)

    @staticmethod
    def parse_token_response(resp_data: dict) -> TokenResponse:
        """
        Verify all required values are present in an auth response and return them
        in a dictionary ready for committing to the store.

        Args:
            resp_data (dict): Content of a successful auth request

        Returns:
            TokenResponse
        """
        if not all(
            [
                "access_token" in resp_data,
                "refresh_token" in resp_data,
                "expires_in" in resp_data,
            ]
        ):
            err = resp_data.get("errorMessage") or "Unrecognized Response"
            raise TokenMgrError(f"Zoom Auth Request Failed: {err}")

        access_expires = expires_seconds_to_timestamp(resp_data["expires_in"])
        refresh_expires = refresh_expires_from_decoded_token(resp_data["refresh_token"])

        return TokenResponse(
            access_token=resp_data["access_token"],
            refresh_token=resp_data["refresh_token"],
            access_expires=access_expires,
            refresh_expires=refresh_expires,
        )

    def _send_request(self, token_url: str, client_id: str, client_secret: str, body: dict) -> dict:
        """
        Send request to get or refresh tokens using the provided body
        and credentials.

        Raise an exception on an HTTP error or an error response body.

        Args:
            token_url (str): Zoom Token URL
            client_id (str): Zoom app client_id
            client_secret (str): Zoom app client_secret
            body (dict): Content for token get or refresh request

        Returns:
            (dict): Content returned in a success response
        """
        auth_token = b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_token}",
        }

        resp = self.session.request("POST", url=token_url, headers=headers, data=body, timeout=10)
        if not resp.ok:
            log.exception(
                f"Zoom Auth Request Failed: {token_url} {resp.status_code} {resp.reason} {resp.text}"
            )
            try:
                err_data = resp.json()
                err = err_data.get("error") or err_data.get("reason") or "Unknown Error"
            except Exception:
                err = "Unknown Error"
            raise TokenMgrError(f"Zoom Auth Request Failed: {err}")

        return resp.json()


def refresh_expires_from_decoded_token(token):
    """
    Decode the token as a jwt and return the 'exp' value for the expiry value.
    If this fails, return a reasonably safe value less than
    the documented expiry of 90 days.
    """
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        expiry = float(decoded["exp"])
    except Exception:
        log.exception(f"token decode failed")
        expiry = (datetime.now() + timedelta(days=30)).timestamp()

    return expiry
