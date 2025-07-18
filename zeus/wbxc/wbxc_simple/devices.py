from .base import Endpoint, CreateEndpointMixin, GetEndpointMixin, UpdateEndpointMixin
from typing import Iterator


class Devices(Endpoint, CreateEndpointMixin, GetEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/devices

    Custom method for update as PATCH is required
    """
    uri = "devices"

    def list(self, **params) -> Iterator[dict]:
        url = self.url(uri=self.uri)
        list_key = "items"
        yield from self._paged_get(url, list_key, params)

    def delete(self, device_id, **params) -> None:
        url = self.url(identifier=device_id, uri=self.uri)
        self.session.delete(url, params=params)

    def update(self, device_id, payload: dict, **params) -> None:
        """
        UPDATE uses PATCH instead of put as Mixin uses and content-type header must be overridden
        """
        url = self.url(uri=f"{self.uri}/{device_id}")
        headers = {'content-type': 'application/json-patch+json'}
        self.session.patch(url, json=payload, params=params, headers=headers)

    def supported_devices(self, **params):
        """
        List of supported devices for an org
        """
        url = self.url(uri=self.uri)
        list_key = "devices"

        yield from self._paged_get(url, list_key, params)

    def apply_changes(self, device_id) -> None:
        """https://developer.webex.com/docs/api/v1/device-call-settings/apply-changes-for-a-specific-device"""
        uri = "telephony/config/devices"
        path = "actions/applyChanges/invoke"
        url = self.url(uri=uri, identifier=device_id, path=path)
        self.session.post(url)


class DeviceMembers(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/device-call-settings/get-device-members
    """
    uri = "telephony/config/devices"
    path = "members"

    def search(self, device_id: str, location_id: str, **params):
        url = self.url(device_id, self.uri, "availableMembers")
        yield from self._paged_get(url, "members", params)

    def update(self, identifier, payload, **params) -> None:
        return super().update(identifier, payload, **params)


class DeviceLayout(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/device-call-settings
    """
    uri = "telephony/config/devices"
    path = "layout"

    def update(self, identifier, payload, **params) -> None:
        return super().update(identifier, payload, **params)


class DeviceSettings(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/device-call-settings/get-device-settings
    """
    uri = "telephony/config/devices"
    path = "settings"

    def update(self, identifier, payload, **params) -> None:
        return super().update(identifier, payload, **params)
