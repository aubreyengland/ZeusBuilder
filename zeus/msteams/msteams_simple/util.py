"""Utility classes"""

import time
import requests
from urllib.parse import quote
from requests.auth import HTTPBasicAuth

def generate_token_with_password(username, password, tenant_id, client_id, client_secret):
	"""
	Convenience method for testing to generate a token for Teams API using username and password.
	Does not work if MFA is required.
	"""
	token_request = requests.post(
		url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
		headers={"Content-Type": "application/x-www-form-urlencoded"},
		data=dict(
			grant_type="password",
			username=username,
			password=password,
			client_id=client_id,
			client_secret=client_secret,
			scope="https://api.interfaces.records.teams.microsoft.com/user_impersonation",
		),
	)
	if token_request.ok:
		try:
			return token_request.json()["access_token"]
		except:
			raise RuntimeError(f"Token was not set, or error received from POST. Response: {token_request.text}")
	else:
		raise RuntimeError(f"Token was not set, or error received from POST. Response: {token_request.text}")