"""Utility classes taken from zoom.us python client"""

import requests
from urllib.parse import quote
from requests.auth import HTTPBasicAuth


def require_keys(d:dict, keys, allow_none=True):
    """Require that the object have the given keys

    :param d: The dict the check
    :param keys: The keys to check :attr:`obj` for. This can either be a single
                 string, or an iterable of strings.
                 
                 If the iterable has a nested dict, such as:
                 {
                     "action": "create",
                     "user_info": {
                         "email": "fake.email@cdw.com",
                         "first_name": "End",
                         "last_name": "User",
                         "type": 1,
                         "feature": {"zoom_phone": True},
                     },
                 }
                 
                 Then the inner keys need to be passsed in as a tuple, with the
                 outer key being the first tuple object, and the inner key being
                 the 2nd tuple object. [e.g. ("user_info", "email")]
                 

    :param allow_none: Whether ``None`` values are allowed
    :raises:
        :ValueError: If any of the keys are missing from the obj
    """
    if isinstance(keys, str):
        keys = [keys]
    for k in keys:
        if isinstance(k, tuple):
            if k[0] not in d:
                raise ValueError("'{}' must be set".format(k[0]))
            elif k[1] not in d[k[0]]:
                if isinstance(d[k[0]], list):
                    for inner_dict in d[k[0]]:
                        if k[1] not in inner_dict:
                            raise ValueError("'{}' must be set".format(k[1]))
                else:
                    raise ValueError("'{}' must be set".format(k[1]))
        elif k not in d:
            raise ValueError("'{}' must be set".format(k))
        elif not allow_none and d[k] is None:
            raise ValueError("'{}' cannot be None".format(k))
    return True


def date_to_str(d):
    """Convert date and datetime objects to a string

    Note, this does not do any timezone conversion.

    :param d: The :class:`datetime.date` or :class:`datetime.datetime` to
              convert to a string
    :returns: The string representation of the date
    """
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def encode_uuid(val):
    """Encode UUID as described by ZOOM API documentation

    > Note: Please double encode your UUID when using this API if the UUID
    > begins with a '/'or contains ‘//’ in it.

    :param val: The UUID to encode
    :returns: The encoded UUID
    """
    if val[0] == "/" or "//" in val:
        val = quote(quote(val, safe=""), safe="")
    return val


def generate_server_to_server_token(
    account_id: str,
    client_id: str,
    client_secret: str,
):
    token_request = requests.post(
        f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={account_id}",
        auth=HTTPBasicAuth(client_id, client_secret),
    )
    if token_request.ok:
        try:
            return token_request.json()["access_token"]
        except:
            raise RuntimeError(
                "Token was not set, or error received from POST. POST Response: %s"
                % token_request.text
            )
    else:
        raise RuntimeError(
            "Token was not set, or error received from POST. POST Response: %s"
            % token_request.text
        )


def refresh_token(refresh_token, client_id, client_secret):
    token_request = requests.post(
        url="https://zoom.us/oauth/token",
        params=dict(grant_type="refresh_token", refresh_token=refresh_token),
        auth=HTTPBasicAuth(client_id, client_secret),
    )
    if token_request.ok:
        try:
            token_json = token_request.json()
            del token_json["token_type"], token_json["scope"], token_json["expires_in"]
            return token_json
        except:
            raise RuntimeError(
                f"Token was not refreshed, or error received from POST. POST Response: {token_request.text}"
            )
    else:
        raise RuntimeError(
            f"Token was not refreshed, or error received from POST. POST Response: {token_request.text}"
        )


def revoke_token(access_token, client_id, client_secret):
    token_request = requests.post(
        url="https://zoom.us/oauth/revoke",
        # The actual Zoom API expects the parameter of `token`, not access
        # token, which is why this params dict has that key instead of our
        # standard `access_token` which is used everywhere else.
        params=dict(token=access_token),
        auth=HTTPBasicAuth(client_id, client_secret),
    )
    if token_request.ok:
        try:
            return token_request.json()
        except:
            raise RuntimeError(
                f"Token was not revoked, or error received from POST. POST Response: {token_request.text}"
            )
    else:
        raise RuntimeError(
            f"Token was not revoked, or error received from POST. POST Response: {token_request.text}"
        )
