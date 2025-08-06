#!/usr/bin/env python3
import os
import base64
import requests
import pyperclip
import logging
from urllib.parse import urlencode
from dotenv import load_dotenv

# Load environment variables from .env if it exists
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of required environment variables for S2S OAuth
ZOOM_REQUIRED_CREDENTIALS = [
    "ZOOM_S2S_ACCOUNT_ID",
    "ZOOM_S2S_CLIENT_ID",
    "ZOOM_S2S_CLIENT_SECRET",
]
ZOOM_OAUTH_ENDPOINT = "https://zoom.us/oauth/token"


def environment_set() -> bool:
    """Return True if all required credentials are set in the environment."""
    return all(os.getenv(cred) for cred in ZOOM_REQUIRED_CREDENTIALS)


def generate_environment() -> dict:
    """
    Prompt the user for missing Zoom S2S credentials and write them to a .env file.
    Returns a dictionary with the credentials.
    """
    credentials = {}
    for cred in ZOOM_REQUIRED_CREDENTIALS:
        val = os.getenv(cred)
        if not val:
            val = input(f"Enter value for {cred}: ")
        credentials[cred] = val.strip()
    # Write the credentials to a .env file
    with open(".env", "w") as f:
        for k, v in credentials.items():
            f.write(f"{k}={v}\n")
    logger.info("Environment file '.env' created with provided credentials.")
    return credentials


def get_token(credentials: dict) -> str:
    """
    Request a Zoom S2S token using the account_credentials grant type.
    Returns the access token (and copies it to clipboard) if successful.
    """
    account_id = credentials["ZOOM_S2S_ACCOUNT_ID"]
    client_id = credentials["ZOOM_S2S_CLIENT_ID"]
    client_secret = credentials["ZOOM_S2S_CLIENT_SECRET"]

    # Prepare the POST body (URL-encoded)
    payload = {"grant_type": "account_credentials", "account_id": account_id}
    data = urlencode(payload)

    # Create the Basic Auth header
    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_b64}",
    }

    try:
        response = requests.post(ZOOM_OAUTH_ENDPOINT, data=data, headers=headers)
        response.raise_for_status()
        token_obj = response.json()
        return copy_token(token_obj)
    except Exception as e:
        logger.error(f"Error obtaining token: {e}")
        if response is not None:
            logger.error(response.text)
        return ""


def copy_token(token_obj: dict) -> str:
    """
    Copies the access token to the clipboard and logs it along with scopes.
    Returns the access token.
    """
    access_token = token_obj.get("access_token")
    scope = token_obj.get("scope", "")
    if access_token:
        pyperclip.copy(access_token)
        logger.info("Zoom S2S token copied to clipboard:")
        logger.info(access_token)
        logger.info("Scopes:")
        for s in scope.split():
            logger.info(s)
    else:
        logger.error("No access_token found in response.")
    return access_token

#update .env file with the new token
def update_env_file(key: str, value: str) -> str:
    """
    Update or add the given key-value pair in the .env file.
    """
    lines = []
    found = False
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")

    with open(".env", "w") as f:
        f.writelines(lines)

    logger.info(f"{key} updated in .env file.")
    return value

def get_env_file() -> str:
    """
    Get the .env file.
    """
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            env_file = f.read()
        return env_file
    else:
        logger.error("No .env file found.")
        return ""

def main():
    # Check if required credentials are present; if not, prompt and generate a .env file.
    if not environment_set():
        logger.info("Missing required environment variables. Prompting for values...")
        creds = generate_environment()
    else:
        creds = {cred: os.getenv(cred) for cred in ZOOM_REQUIRED_CREDENTIALS}

    token = get_token(creds)
    if token:
        logger.info("Token obtained successfully.")
    else:
        logger.error("Failed to obtain token.")
    
    # Update the .env file with the new token
    env_file = get_env_file()
    if env_file:
        update_env_file("ZOOM_S2S_ACCESS_TOKEN", token)
        logger.info("Token updated in .env file.")
    else:
        logger.error("Failed to update .env file with the new token.")
        


if __name__ == "__main__":
    main()
