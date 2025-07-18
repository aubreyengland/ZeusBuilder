from .base import (
    Endpoint,
    GetEndpointMixin,
    ListEndpointMixin,
)


class Licenses(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get a list of all licenses in your organization and viewing license details

    https://developer.webex.com/docs/api/v1/licenses
    """

    uri = "licenses"
    list_key = "items"

    def assign(self, payload):
        """
        Assign licenses and attendee siteUrls to existing users.

        Utilizes PATCH request hence need to special function.

        https://developer.webex.com/docs/api/v1/licenses/assign-licenses-to-users

        Args:
            payload (dict): Body of request containing information about the update

        Returns:
            dict: The JSON response from the patch request.
        """
        resp = self.session.patch(self.url(uri=self.uri+"/users"), json=payload)
        return resp.json()
