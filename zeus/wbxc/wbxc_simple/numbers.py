from .base import Endpoint


class LocationNumbers(Endpoint):
    """
    https://developer.webex.com/docs/api/v1/numbers

    Custom methods for LIST, CREATE, UPDATE, DELETE because a location id is required
    in the URL
    Ex:
        /telephony/config/locations/{locationId}/numbers
    """
    uri = "telephony/config/locations"
    path = "numbers"

    def list(self, **params):
        """
        Custom method necessary because the uri differs from other
        numbers methods.
        LIST/GET: `/telephony/config`
        """
        url = self.url(uri="telephony/config")

        list_key = "phoneNumbers"
        yield from self._paged_get(url, list_key, params)

    def create(self, location_id, payload, **params):
        """
        Custom method for CREATE because a location id is required
        in the URL
        Ex:
            /telephony/config/locations/{locationId}/numbers
        """
        url = self.url(uri=self.uri, identifier=location_id, path=self.path)
        self.session.post(url, json=payload, params=params)

    def update(self, location_id, payload, **params):
        url = self.url(uri=self.uri, identifier=location_id, path=self.path)
        self.session.put(url, json=payload, params=params)

    def delete(self, location_id, payload, **params):
        url = self.url(uri=self.uri, identifier=location_id, path=self.path)
        self.session.delete(url, json=payload, params=params)
