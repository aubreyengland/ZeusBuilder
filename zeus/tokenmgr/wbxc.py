import logging
from requests import Session
from urllib import parse as urllib_parse
from .mgr_base import TokenMgrBase, SqlaStore, TokenResponse, TokenMgrError, expires_seconds_to_timestamp

log = logging.getLogger(__name__)

WBXC_API_ENDPOINT = "https://webexapis.com/v1/"
WBXC_AUTH_ENDPOINT = "https://webexapis.com/v1/authorize"
WBXC_REFRESH_ENDPOINT = "https://webexapis.com/v1/access_token"

WBXC_SCOPES = [
    "Identity:contact",
    "identity:organizations_read",
    "identity:organizations_rw",
    "identity:tokens_read",
    "spark:organizations_read",
    "spark-admin:devices_read",
    "spark-admin:devices_write",
    "spark-admin:licenses_read",
    "spark-admin:locations_read",
    "spark-admin:locations_write",
    "spark-admin:people_read",
    "spark-admin:people_write",
    "spark-admin:telephony_pstn_read",
    "spark-admin:telephony_pstn_write",
    "spark-admin:telephony_config_read",
    "spark-admin:telephony_config_write",
    "spark-admin:workspace_locations_read",
    "spark-admin:workspace_locations_write",
    "spark-admin:workspaces_read",
    "spark-admin:workspaces_write",
]

WBXC_OAUTH_DEFAULTS = {
    "scopes": WBXC_SCOPES,
    "api_endpoint": WBXC_API_ENDPOINT,
    "auth_endpoint": WBXC_AUTH_ENDPOINT,
    "token_endpoint": WBXC_REFRESH_ENDPOINT,
}


class WbxcTokenMgr(TokenMgrBase):
    """
    Manager class for Webex Calling Oauth integrations.

    The Manager class provides methods to interact with the
    Wbxc API to authorize integration and request tokens. It also
    provides methods for interacting with the provided Store class.
    """

    def __init__(self, store=None, refresh_after_minutes=120, **kwargs):
        """
        Manager class for Webex Calling Oauth integrations.

        Args:
            store: StoreInterface implementation for authorization
             storage and retrieval
            refresh_after_minutes (int): Calling the access_token method
             will automatically refresh if the token is older than this
             value in minutes
        """
        store = store or SqlaStore()
        super().__init__(store, refresh_after_minutes, **kwargs)
        self.session = Session()

    def access_token(self, org, force_refresh=False):
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

        scopes = " ".join(oauth_app.scopes)
        params = {
            "client_id": oauth_app.client_id,
            "response_type": "code",
            "redirect_uri": oauth_app.redirect_uri,
            "scope": scopes,
            "state": state,
        }
        return url + urllib_parse.urlencode(params, quote_via=urllib_parse.quote)

    def send_token_request(self, auth_code, org) -> TokenResponse:
        """
        Use Webex Calling Api to attempt authorization of the provided auth object.

        Args:
            auth_code (str): Code provided for this authorization attempt
            org: (ProvisioningOrg): Webex Calling ProvisioningOrg instance

        Returns:
            TokenResponse
        """
        body = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": org.oauth.client_id,
            "client_secret": org.oauth.client_secret,
            "redirect_uri": org.oauth.redirect_uri,
        }
        resp_data = self._send_request(org.oauth.token_endpoint, body)
        return self.parse_token_response(resp_data)

    def send_refresh_request(self, org) -> TokenResponse:
        """
        Use Webex Calling Api to attempt refreshing the provided auth object.

        Args:
            org: (ProvisioningOrg): ProvisioningOrg instance

        Returns:
            TokenResponse
        """
        body = {
            "grant_type": "refresh_token",
            "refresh_token": org.refresh_token,
            "client_id": org.oauth.client_id,
            "client_secret": org.oauth.client_secret,
        }
        resp_data = self._send_request(org.oauth.token_endpoint, body)
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
                "refresh_token_expires_in" in resp_data,
            ]
        ):
            err = resp_data.get("errorMessage") or "Unrecognized Response"
            raise TokenMgrError(f"Webex Calling Auth Request Failed: {err}")

        access_expires = expires_seconds_to_timestamp(resp_data["expires_in"])
        refresh_expires = expires_seconds_to_timestamp(resp_data["refresh_token_expires_in"])

        return TokenResponse(
            access_token=resp_data["access_token"],
            refresh_token=resp_data["refresh_token"],
            access_expires=access_expires,
            refresh_expires=refresh_expires,
        )

    def _send_request(self, token_url: str, body: dict) -> dict:
        """
        Send request to get or refresh tokens using the provided body.

        Raise an exception on an HTTP error or an error response body.

        Args:
            token_url (str): Webex token URL
            body (dict): Content for token get or refresh request

        Returns:
            (dict): Content returned in a success response
        """

        resp = self.session.request("POST", url=token_url, data=body, timeout=10)
        if not resp.ok:
            log.exception(
                f"Webex Calling Auth Request Failed: {token_url} {resp.status_code} {resp.reason} {resp.text}"
            )
            try:
                err_data = resp.json()
                err = err_data.get("message") or "Unknown Error"
            except Exception:
                err = "Unknown Error"
            raise TokenMgrError(err)

        return resp.json()
