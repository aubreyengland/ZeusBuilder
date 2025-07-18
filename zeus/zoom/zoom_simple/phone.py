import logging
from typing import Iterator
from . import ZoomServerFault
from .base import (
    CRUDEndpoint,
    Endpoint,
    GetEndpointMixin,
    ListEndpointMixin,
    UpdateEndpointMixin,
    CreateEndpointMixin,
)

log = logging.getLogger(__name__)


class PhoneUsers(Endpoint, GetEndpointMixin, ListEndpointMixin, UpdateEndpointMixin):
    """
    Zoom Phone User API does not support user deletion.
    Must use MeetingUsers.update_settings to set zoom_phone: false
    """

    uri = "phone/users"

    def get_profile_settings(self, user_id: str):
        url = self.url(f"{user_id}/settings")
        return self._get(url)

    def create(self, payload: dict, **params) -> dict:
        resp = self.session.post(self.url("batch"), json=payload, params=params)
        return resp.json()

    def update_profile_settings(self, identifier, payload, **params) -> None:
        url = self.url(f"{identifier}/settings")
        self.session.patch(url, json=payload, params=params)

    def assign_calling_plan(self, identifier: str, payload: list) -> None:
        """
        Assign calling plans to an existing Zoom Phone User.

        The calling plans must be provided as a list of dictionaries
        with a 'type' key containing the integer ID for the calling plan
        to assign. An optional 'billing_account_id' can be provided but this is only
        needed for Indian calling plans

        Args:
            identifier (str): ID or email of the Zoom phone user
            payload (list): List of calling plan dictionaries
        """
        url = self.url(f"{identifier}/calling_plans")
        self.session.post(url, json=payload)

    def unassign_calling_plan(
        self, identifier: str, calling_plan_type: str, **params
    ) -> None:
        """
        Un-assign a calling plan to an existing Zoom Phone User.
        Accepts 'billing_account_id' as query param

        Args:
            identifier (str): ID or email of the Zoom phone user
            calling_plan_type (str): Calling plan type value
        """
        url = self.url(f"{identifier}/calling_plans/{calling_plan_type}")
        self.session.delete(url, params=params)

    def assign_phone_numbers(self, identifier: str, payload: dict) -> dict:
        url = self.url(f"{identifier}/phone_numbers")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_phone_number(self, identifier: str, phone_number_id: str) -> None:
        url = self.url(f"{identifier}/phone_numbers/{phone_number_id}")
        self.session.delete(url)

    def list_caller_id(self, identifier: str, **params):
        url = self.url(f"{identifier}/outbound_caller_id/customized_numbers")
        yield from self._paged_get(url, "customize_numbers", params)

    def add_caller_id(self, identifier: str, payload: dict):
        """
        Payload ex:
            {"phone_number_ids": ["55JUZPwERHuGttd_j4qBsQ"]}
        """
        url = self.url(f"{identifier}/outbound_caller_id/customized_numbers")
        self.session.post(url, json=payload)

    def remove_caller_id(self, identifier: str, phone_number_ids: list):
        url = self.url(f"{identifier}/outbound_caller_id/customized_numbers")
        params = dict(customize_ids=phone_number_ids)
        self.session.delete(url, params=params)


class PhoneSites(CRUDEndpoint):
    uri = "phone/sites"

    def get_settings(self, site_id: str, setting_type: str = None):
        if setting_type:
            url = self.url(f"{site_id}/settings/{setting_type}")
        else:
            url = self.url(f"{site_id}/settings")

        return self._get(url)

    def add_settings(self, site_id: str, setting_type: str, payload: dict):
        """
        setting_type must be one of holiday_hours,security
        """
        url = self.url(f"{site_id}/settings/{setting_type}")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def update_settings(self, site_id: str, setting_type: str, payload: dict):
        """
        setting_type must be one of local_based_routing, business_hours, closed_hours, holiday_hours
        outbound_caller_id, audio_prompt, desk_phone, dial_by_name, billing_account
        """
        url = self.url(f"{site_id}/settings/{setting_type}")
        self.session.patch(url, json=payload)

    def delete_settings(self, site_id: str, setting_type: str, setting_value: str):
        """
        setting_type must be one of holiday_hours,security
        setting_val must be a holiday hour setting ID or device type
        """
        url = self.url(f"{site_id}/settings/{setting_type}")
        param_name = "holiday_id" if setting_type == "holiday_hours" else "device_type"
        self.session.delete(url, params={param_name: setting_value})

    def list_caller_id(self, site_id: str, **params):
        url = self.url(f"{site_id}/outbound_caller_id/customized_numbers")
        yield from self._paged_get(url, "customize_numbers", params)

    def add_caller_id(self, site_id: str, payload: dict):
        """
        RequestBuilder ex:
            {"phone_number_ids": ["55JUZPwERHuGttd_j4qBsQ"]}
        """
        url = self.url(f"{site_id}/outbound_caller_id/customized_numbers")
        self.session.post(url, json=payload)

    def remove_caller_id(self, site_id: str, phone_number_ids: list):
        url = self.url(f"{site_id}/outbound_caller_id/customized_numbers")
        params = dict(customize_ids=phone_number_ids)
        self.session.delete(url, params=params)


class PhoneEmergencyAddresses(CRUDEndpoint):
    uri = "phone/emergency_addresses"


class PhoneLocations(CRUDEndpoint):
    uri = "phone/locations"


class PhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin, UpdateEndpointMixin):
    uri = "phone/numbers"

    def list(self, **params) -> Iterator[dict]:
        url = self.url()
        yield from self._paged_get(url, "phone_numbers", params)

    def assign_to_emergency_number_pool(self, payload: dict) -> dict:
        url = self.url("emergency_number_pools/phone_numbers")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_from_emergency_number_pool(self, phone_number_id: str) -> None:
        url = self.url(f"emergency_number_pools/phone_numbers/{phone_number_id}")
        self.session.delete(url)


class PhoneDevices(CRUDEndpoint):
    uri = "phone/devices"

    def sync_desk_phones(self, payload: dict) -> None:
        url = self.url("sync")
        self.session.post(url, json=payload)

    def reboot_desk_phone(self, device_id: str) -> None:
        url = self.url(f"{device_id}/reboot")
        self.session.post(url)

    def assign_entities(self, device_id: str, payload: dict) -> None:
        url = self.url(f"{device_id}/extensions")
        self.session.post(url, json=payload)

    def unassign_entity(self, device_id: str, extension_id: str) -> None:
        url = self.url(f"{device_id}/extensions/{extension_id}")
        self.session.delete(url)


class PhoneRooms(Endpoint, GetEndpointMixin, ListEndpointMixin, UpdateEndpointMixin):
    uri = "phone/rooms"

    def assign_calling_plans(self, room_id: str, payload: dict) -> None:
        url = self.url(f"{room_id}/calling_plans")
        self.session.post(url, json=payload)

    def remove_calling_plan(self, room_id: str, calling_plan_type: int) -> None:
        url = self.url(f"{room_id}/calling_plans/{calling_plan_type}")
        self.session.delete(url)

    def assign_phone_numbers(self, room_id: str, payload: dict) -> None:
        url = self.url(f"{room_id}/phone_numbers")
        self.session.post(url, json=payload)

    def remove_phone_numbers(self, room_id: str, phone_number_id: str) -> None:
        url = self.url(f"{room_id}/phone_numbers/{phone_number_id}")
        self.session.delete(url)


class PhonePlans(Endpoint):
    uri = "phone/plans"

    def list_plan_info(self):
        resp = self.session.get(self.url())
        return resp.json()

    def list_calling_plans(self):
        url = f"{self.base_url}/phone/calling_plans"
        resp = self.session.get(url)
        return resp.json()["calling_plans"]


class PhoneSettingTemplates(
    Endpoint, GetEndpointMixin, ListEndpointMixin, CreateEndpointMixin, UpdateEndpointMixin
):
    uri = "phone/setting_templates"

    def list(self, **params) -> Iterator[dict]:
        url = self.url()
        key = "templates"
        yield from self._paged_get(url, key, params)


class PhoneProvisionTemplates(CRUDEndpoint):
    uri = "phone/provision_templates"


class PhoneCallHandling(Endpoint, GetEndpointMixin):
    uri = "phone/extension"
    path = "call_handling/settings"

    def add(self, extension_id, setting_type, payload) -> dict:
        """
        Add call handling settings of the provided type for the provided extension.
        setting_types are 'business_hours', 'closed_hours', 'holiday_hours'
        """
        url = f"{self.url(extension_id)}/{setting_type}"
        resp = self.session.post(url, json=payload)
        return resp.json()

    def update(self, extension_id, setting_type, payload) -> None:
        """
        Update call handling settings of the provided type for the provided extension.
        setting_types are 'business_hours', 'closed_hours', 'holiday_hours'
        """
        url = f"{self.url(extension_id)}/{setting_type}"
        self.session.patch(url, json=payload)

    def delete(self, extension_id, setting_type, setting_id) -> None:
        """
        Delete call handling settings of the provided type for the provided extension.
        setting_types are 'call_forwarding_id', 'holiday_id'
        setting_id must be the unique ID for the call_forwarding or holiday to delete
        """
        url = f"{self.url(extension_id)}/{setting_type}"
        params = {setting_type: setting_id}
        self.session.delete(url, params=params)


class PhoneLineKeys(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    uri = "phone/extension"
    path = "line_keys"

    def delete(self, extension_id, line_key_id) -> None:
        url = f"{self.url(extension_id)}/{line_key_id}"
        self.session.delete(url)


class PhoneCommonAreas(CRUDEndpoint):
    uri = "phone/common_areas"

    def get_settings(self, identifier: str) -> dict:
        """
        Lists devices common area is set on.

        Args:
            identifier (str): Common area ID or common area extension ID.
        """
        url = self.url(f"{identifier}/settings")
        return self._get(url)

    def add_settings(self, identifier: str, setting_type: str) -> dict:
        """
        Add the common area setting according to the setting type, specifically for desk phones.

        Args:
            identifier (str): Common area ID or common area extension ID.
            setting_type (str): Must be one of desk_phone
        """
        url = self.url(f"{identifier}/settings/{setting_type}")
        resp = self.session.post(url)
        return resp.json()

    def update_settings(self, identifier: str, setting_type: str, payload: dict) -> None:
        """
        Args:
            identifier (str): Common area ID or common area extension ID.
            setting_type (str): Must be one of desk_phone
            payload (dict): desk_phone payload
        """
        url = self.url(f"{identifier}/settings/{setting_type}")
        self.session.patch(url, json=payload)

    def delete_settings(self, identifier: str, setting_type: str, device_id: str) -> None:
        """
        Remove device association from the common area
        Args:
            identifier (str): Common area ID or common area extension ID.
            setting_type (str): Must be one of desk_phone
            device_id (str): ID of device to remove from common area
        """
        url = self.url(f"{identifier}/settings/{setting_type}")
        self.session.delete(url, params={"device_id": device_id})

    def assign_calling_plan(self, identifier: str, payload: list) -> None:
        """
        Assign calling plans to an existing Common Area.

        The calling plans must be provided as a list of dictionaries
        with a 'type' key containing the integer ID for the calling plan
        to assign. An optional 'billing_account_id' can be provided but this is only
        needed for Indian calling plans

        Args:
            identifier (str): Common area ID or common area extension ID.
            payload (list): List of calling plan dictionaries
        """
        url = self.url(f"{identifier}/calling_plans")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_calling_plan(
        self, identifier: str, calling_plan_type: str, **params
    ) -> None:
        """
        Un-assign a calling plan to an existing Common Area.
        Accepts 'billing_account_id' as query param

        Args:
            identifier (str): Common area ID or common area extension ID.
            calling_plan_type (str): Calling plan type value
        """
        url = self.url(f"{identifier}/calling_plans/{calling_plan_type}")
        self.session.delete(url, params=params)

    def assign_phone_numbers(self, identifier: str, payload: dict) -> None:
        """
        Args:
            identifier (str): Common area ID or common area extension ID.
            payload (dict): Dict of phone numbers or id values
            {"phone_numbers": [{"number": "+12243416415","id": "TqH98ec8RVCu6Z00aBv9ow"}]}
        """
        url = self.url(f"{identifier}/phone_numbers")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_phone_number(self, identifier: str, phone_number_id: str) -> None:
        """
        Args:
            identifier (str): Common area ID or common area extension ID.
            phone_number_id (str): The phone number or the phone number ID.
        """
        url = self.url(f"{identifier}/phone_numbers/{phone_number_id}")
        self.session.delete(url)
        
    def block_outbound_calling(self, identifier: str, payload: dict) -> None:
        """
        Update outbound calling for a common area by country or region.

        Args:
            identifier (str): Common area ID or common area extension ID.
            payload (dict): Payload to block outbound calling.
        """
        url = self.url(f"{identifier}/outbound_calling/countries_regions")
        self.session.patch(url, json=payload)


class PhoneExternalContacts(CRUDEndpoint):
    uri = "phone/external_contacts"


class PhoneAutoReceptionists(CRUDEndpoint):
    uri = "phone/auto_receptionists"

    def get_ivr(self, identifier: str, **params) -> dict:
        """
        Get IVR configuration for an auto receptionist
        Supported params:
         - hours_type business_hours (default), closed_hours
         - holiday_id

        If the auto receptionist call handling action is not
        IVR, the request will return a 200 but with no data (which
        will raise a JSONDecodeError). Reraise as a ZoomServerFault.

        Args:
            identifier (str): Auto receptionist ID
        """
        url = self.url(f"{identifier}/ivr")
        try:
            return self._get(url)
        except Exception:
            raise ZoomServerFault(f"No IVR routing found for {identifier=}, {params=}")

    def update_ivr(self, identifier: str, payload: dict) -> None:
        """
        Args:
            identifier (str): Auto receptionist ID or common area extension ID.
            payload (dict): Auto receptionist IVR payload
        """
        url = self.url(f"{identifier}/ivr")
        self.session.patch(url, json=payload)

    def assign_phone_numbers(self, identifier: str, payload: dict) -> dict:
        url = self.url(f"{identifier}/phone_numbers")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_phone_number(self, identifier: str, phone_number_id: str) -> None:
        url = self.url(f"{identifier}/phone_numbers/{phone_number_id}")
        self.session.delete(url)


class PhoneCallQueues(CRUDEndpoint):
    uri = "phone/call_queues"

    def list_call_queues(self, **params) -> Iterator[dict]:
        url = self.url()
        yield from self._paged_get(url, "call_queues", params)
        
    def assign_phone_numbers(self, identifier: str, payload: dict) -> dict:
        """
        Assign phone numbers to a call queue.

        Args:
            identifier (str): Call queue ID or call queue extension ID.
            payload (dict): Dict of phone numbers or id values
            {"phone_numbers": [{"number": "+12243416415","id": "TqH98ec8RVCu6Z00aBv9ow"}]}
        """
        url = self.url(f"{identifier}/phone_numbers")
        resp = self.session.post(url, json=payload)
        return resp.json()


class PhoneSharedLineGroups(CRUDEndpoint):
    uri = "phone/shared_line_groups"

    def list_shared_line_groups(self, **params) -> Iterator[dict]:
        url = self.url()
        yield from self._paged_get(url, "shared_line_groups", params)


class PhoneAlerts(CRUDEndpoint):
    uri = "phone/alert_settings"
    identifier = "alertSettingId"

    def list_alert_settings(self, **params) -> Iterator[dict]:
        """
        List all alert settings with optional filters.

        Supported query parameters:
            - site_id
            - target_type
            - target_id
            - module
            - page_size
            - next_page_token

        Returns:
            Iterator over alert setting dictionaries.
        """
        url = self.url()
        yield from self._paged_get(url, "alert_settings", params)

    def delete(self, identifier: str) -> None:
        """
        Delete a specific alert setting by identifier.

        Args:
            identifier (str): The alert setting ID.
        """
        url = self.url(f"{identifier}")
        self.session.delete(url)

class PhoneRoutingRules(CRUDEndpoint):
    identifier = "routing_rule_id"
    uri = "phone/routing_rules"

    def list_routing_rules(self, **params):
        """
        List all routing rules.

        The Zoom API returns a *bare list* (not an envelope with a key),
        so we cannot reuse the generic `_paged_get` helper that expects
        a dictionary.  We therefore make the call directly and yield the
        items.
        """
        url = self.url()
        resp = self.session.get(url, params=params)
        data = resp.json()

        log.debug(f"Routing rules list response: {data}")

        # Future‑proof: if Zoom ever wraps the response in an object,
        # gracefully handle the `"routing_rules"` key.
        if isinstance(data, dict):
            data = data.get("routing_rules", [])

        yield from data

    def get_routing_rule(self, identifier: str) -> dict:
        """
        Get a specific routing rule by identifier.

        Args:
            identifier (str): The routing rule ID.
        """
        url = self.url(f"{identifier}")
        return self._get(url)

    def update_routing_rule(self, identifier: str, payload: dict) -> None:
        """
        Update a specific routing rule by identifier.

        Args:
            identifier (str): The routing rule ID.
            payload (dict): The updated routing rule data.
        """
        url = self.url(f"{identifier}")
        self.session.patch(url, json=payload)

    def delete_routing_rule(self, identifier: str) -> None:
        """
        Delete a specific routing rule by identifier.


        Args:
            identifier (str): The routing rule ID to delete.
        """
        url = self.url(f"{identifier}")
        self.session.delete(url)


class PhoneAudios(CRUDEndpoint):
    uri = "phone/audios"
    identifier = "audio_id"
