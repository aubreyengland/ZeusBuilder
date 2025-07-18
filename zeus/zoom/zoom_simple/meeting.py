from typing import Iterator
from .base import CRUDEndpoint


class MeetingUsers(CRUDEndpoint):
    uri = "users"

    def me(self) -> dict:
        return self._get(self.url("me"))

    def check_email(self, email) -> bool:
        res = self._get(self.url("email"), params={"email": email})
        return res["existed_email"]

    def summary(self) -> dict:
        return self._get(self.url("summary"))

    def get_settings(self, user_id: str, **params) -> dict:
        url = self.url(f"{user_id}/settings")
        return self._get(url, params=params)

    def update_settings(self, user_id: str, payload: dict, **params):
        url = self.url(f"{user_id}/settings")
        self.session.patch(url, json=payload, params=params)


class MeetingRoles(CRUDEndpoint):
    uri = "roles"

    def list_members(self, role_id) -> Iterator[dict]:
        url = self.url(f"{role_id}/members")
        yield from self._paged_get(url, "members")

    def assign_members(self, role_id, payload: list) -> dict:
        """
        Assign users to a role.

        Args:
            role_id (str): instance ID of the role in question
            payload (list): List of dictionaries with 'id'
                            and 'email' keys for each user to assign

        Returns:
            (dict): Includes 'add_at' key with timestamp of assignment and
                    'ids' key with count of assignments
        """
        url = self.url(f"{role_id}/members")
        resp = self.session.post(url, json=payload)
        return resp.json()
