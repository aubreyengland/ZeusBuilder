import re
import logging
from typing import Tuple, Union
from urllib.parse import quote_plus
from ..zoom_simple import ZoomSimpleClient
from zeus.exceptions import ZeusBulkOpFailed
from zeus.shared.helpers import deep_get
from zeus.services import BulkSvc, BulkTask, SvcClient

log = logging.getLogger(__name__)


class ZoomBulkSvc(BulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.client: ZoomSimpleClient = client
        self.lookup = ZoomLookup(client)


class ZoomBulkTask(BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomBulkSvc = svc


class ZoomSvcClient(SvcClient):
    tool = "zoom"
    client_cls = ZoomSimpleClient


class ZoomLookup:
    def __init__(self, client):
        self.client: ZoomSimpleClient = client
        self.current: dict = {}

    def location(self, location_name: str, site_id: str) -> dict:
        """
        Return the id for the location that matches location_name provided or
        raise ZeusBulkOpFailed if the location does not exist.
        """
        existing_locations = self.client.phone_locations.list(site_id=site_id)
        match = next((loc for loc in existing_locations if loc["name"] == location_name), None)
        if not match:
            raise ZeusBulkOpFailed(f"Location {location_name} Does Not Exist.")

        return match

    def provision_template(self, template_name: str) -> dict:
        """
        Return the provision template response that matches provided template_name
        raise ZeusBulkOpFailed if the template does not exist.
        """
        templates = self.client.phone_provision_templates.list()
        match = next((t for t in templates if t["name"] == template_name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Provision template {template_name} does not exist.")

        return match

    def device(self, mac_address: str, device_type: str) -> dict:
        """
        Return the id for the device that matches the provided mac address.

        Use the model filter to reduce number of results returned.

        Assigned and un-assigned devices require separate requests. If
        not returned by either, raise ZeusBulkOpFailed exception.

        Args:
            mac_address (str): Device MAC address
            device_type (str): Value from device model/payload 'type' field (Cisco, AudioCodes, etc.)

        Returns:
            (dict): List Phone Devices response
        """
        lookup_type = get_device_type_for_lookup(device_type)
        for type_ in ("assigned", "unassigned"):
            devices = self.client.phone_devices.list(type=type_, device_type=lookup_type)
            match = next(
                (device for device in devices if device["mac_address"] == mac_address), None
            )
            if match:
                return match

        raise ZeusBulkOpFailed(f"device type: {device_type} mac {mac_address} not found.")

    def common_area(self, extension: str, site_id: str = None) -> dict:
        """
        Find a common area by extension.
        Extension numbers are unique within a Zoom org (common area display names are not).
        If site_id is provided, limit search to that site.
        """
        extension = str(extension)
        params = {"site_id": site_id} if site_id else {}
        existing = self.client.phone_common_areas.list(**params)
        match = next(
            (
                item
                for item in existing
                if str(item["extension_number"]) == extension
            ),
            None,
        )

        if not match:
            raise ZeusBulkOpFailed(
                f"Common area with ext. {extension} not found."
            )

        return match

    def external_contact(self, name_or_ext: str) -> dict:
        """
        Return the external contact that matches the provided name
        or extension.
        Raise ZeusBulkOpFailed if the contact does not exist.

        Note: Multiple external contacts may have the same name.
        The function will return the first name match found.
        """
        name_or_ext = str(name_or_ext)
        key = "extension_number" if re.match(r"^\d+$", name_or_ext) else "name"

        match = next(
            (
                item for item in self.client.phone_external_contacts.list()
                if key in item and item[key] == name_or_ext
             ), None
        )

        if not match:
            raise ZeusBulkOpFailed(f"External contact with {key}: {name_or_ext} not found.")

        return match

    def phone_number(self, phone_number) -> dict:
        phone_numbers = self.client.phone_numbers.list()
        match = next((p for p in phone_numbers if p["number"] == phone_number), None)

        if not match:
            raise ZeusBulkOpFailed(f"Phone number {phone_number} not found.")

        return match

    def site_id_or_none(self, site_name: str) -> Union[str, None]:
        """
        Return None if site_name is empty string or return the site_id
        This avoids a bunch of `if model.site_name` conditionals in the services
        to check if sites are enabled for an org.
        """
        if site_name:
            return self.site(site_name)["id"]
        return None

    def site(self, site_name: str) -> dict:
        """
        Return the id for the site that matches `loc.site_name` or
        raise ZeusBulkOpFailed if the site does not exist.
        """
        sites = self.client.phone_sites.list()
        match = next((site for site in sites if site["name"] == site_name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Site {site_name} Does Not Exist.")

        return match

    def user_template(self, template_name: str, site_id=None) -> dict:
        """
        Return the id for the user setting templates assigned to the provided site_id
        that matches the provided template_name.
        Raise ZeusBulkOpFailed if the template is not found
        """
        params = dict(site_id=site_id) if site_id else dict()
        templates_for_site = self.client.phone_setting_templates.list(**params)
        match = next((t for t in templates_for_site if t["name"] == template_name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Template {template_name} Does Not Exist.")

        return match

    def user(self, email_or_ext):
        email_or_ext = str(email_or_ext)
        if "@" in email_or_ext:
            match = self.client.phone_users.get(quote_plus(email_or_ext))
        else:
            existing = self.client.phone_users.list(keyword=email_or_ext)
            match = next((item for item in existing if str(item["extension_number"]) == email_or_ext), None)

            if not match:
                raise ZeusBulkOpFailed(f"User with ext. {email_or_ext} Does Not Exist.")

        return match

    def assignee_id(self, assignee) -> str:
        assignee = str(assignee)
        if "@" in assignee:
            user = self.client.phone_users.get(assignee)
            assignee_id = user["extension_id"]
        else:
            assignee_id = self.common_area(assignee)["id"]

        return assignee_id

    def calling_plans(self, calling_plan_names: list) -> list:
        """
        Return calling plan id/name dicts for for the names in the calling_plan_names list.
        Raise ZeusBulkOpFailed if any of the names are not found.
        """
        matched_plans = []

        org_plans_by_fixed_name = {
            fix_calling_plan_name(plan["name"]): plan
            for plan in self.client.phone_plans.list_calling_plans()
        }

        for name in calling_plan_names:
            if match := org_plans_by_fixed_name.get(fix_calling_plan_name(name)):
                matched_plans.append(match)
            else:
                raise ZeusBulkOpFailed(f"Calling plan {name} Does Not Exist.")

        return matched_plans

    def role(self, role_name: str) -> dict:
        """
        Look for an existing Zoom Meeting Role that matches
        the provided role_name.  If found, return the role id.
        If not found, raise an exception to fail the operation.
        """
        for role in self.client.meeting_roles.list():
            if role_name.lower() == role["name"].lower():
                return role

        raise ZeusBulkOpFailed(f"Role '{role_name}' Not Found.")

    def emergency_address(self, addr: dict, site_id: str) -> dict:
        def lookup_str(d: dict):
            return f"{d['address_line1']}{d.get('address_line2', '')}{d['city']}"

        for item in self.client.phone_emergency_addresses.list():
            if lookup_str(addr) == lookup_str(item):
                return item

        raise ZeusBulkOpFailed(f"Emergency Address {lookup_str(addr)} Does Not Exist.")

    def auto_receptionist(self, extension: str, site_id: str = None) -> dict:
        """
        Return the id for the auto receptionist that matches the provided extension.
        Extension must be used since name is not guaranteed unique
        raise ZeusBulkOpFailed if it does not exist.
        If site_id is provided, limit search to that site.
        """
        params = {"site_id": site_id} if site_id else {}
        existing = self.client.phone_auto_receptionists.list(**params)
        match = next((item for item in existing if str(item["extension_number"]) == extension), None)

        if not match:
            raise ZeusBulkOpFailed(f"Auto Receptionist with ext. {extension} Does Not Exist.")

        return match

    def call_queue(self, extension: str, site_id: str = None) -> dict:
        """
        Return the call queue that matches the provided extension.
        If site_id is provided, limit search to that site.
        """
        params = {"site_id": site_id} if site_id else {}
        existing = self.client.phone_call_queues.list(**params)
        match = next((item for item in existing if str(item["extension_number"]) == extension), None)

        if not match:
            raise ZeusBulkOpFailed(f"Call Queue with ext. {extension} Does Not Exist.")

        return match

    def shared_line_group(self, extension: str) -> dict:
        existing = self.client.phone_shared_line_groups.list()
        match = next((item for item in existing if str(item["extension_number"]) == extension), None)

        if not match:
            raise ZeusBulkOpFailed(f"Shared line group with ext. {extension} Does Not Exist.")

        return match

    def room(self, extension: str) -> dict:
        existing = self.client.phone_rooms.list()
        match = next((item for item in existing if str(item["extension_number"]) == extension), None)

        if not match:
            raise ZeusBulkOpFailed(f"Zoom room with ext. {extension} Does Not Exist.")

        return match
    
    def audio_file(self, audio_file_name: str) -> dict:

        existing = self.client.phone_audios.list()
        match = next((item for item in existing if item["name"] == audio_file_name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Audio file {audio_file_name} Does Not Exist.")

        return match


def fix_calling_plan_name(name) -> str:
    """
    Convert Zoom Phone Calling Plan names to a normalized form that will allow comparisons
    between different sources.
    Phone User GET and Calling Plan LIST requests return calling plan names in a 'full' format.
    Ex:
      United Kingdom/Ireland Metered Calling Plan
      United States/Canada Unlimited Calling Plan

    The Phone User CREATE request requires the plans above to be:
      UK/Ireland Metered
      US/CA Unlimited

    Workbook input could potentially be in either form.

    To allow comparison of different values that represent the same plan, the provided name
    is converted to the 'short form' by replacing country names with abbreviations and removing
    'Calling Plan' or 'Zoom Phone'.

    The substitutions are based on documented examples here:
    https://marketplace.zoom.us/docs/api-reference/phone/methods/#operation/batchAddUsers

    The fixed value is returned lower-case to avoid case-mismatches with workbook values.

    Args:
        name (str): Calling plan name from workbook or API response

    Returns:
        fixed (str): name converted to 'short form' and lower-case
    """
    name = str(name)
    fixed = re.sub(r"\sCalling Plan$", "", name, flags=re.I)
    for pat, repl in [
        ("United States", "US"),
        ("Canada", "CA"),
        ("United Kingdom", "UK"),
        ("Australia", "AU"),
        ("New Zealand", "NZ"),
        ("Japan", "JP"),
        ("India", "IN"),
        (r"^Zoom Phone\s", ""),
    ]:
        fixed = re.sub(pat, repl, fixed, flags=re.I)
    return fixed.lower()


ZOOM_DEVICE_TYPES_CREATE_VALUES = {
    "algo": "Algo",
    "audiocodes": "AudioCodes",
    "cisco": "Cisco",
    "cyberdata": "CyberData",
    "grandstream": "Grandstream",
    "poly": "Poly",
    "yealink": "Yealink",
    "other": "Other",
}


def is_emergency_address_complete(model) -> bool:
    """
    Return True if all required emergency address
    attributes have a value
    """
    return all(
        [
            model.address_line1,
            model.city,
            model.state_code,
            model.zip,
            model.country,
        ]
    )


class ZoomEmerAddrGetOrCreateMixin:
    """
    Gets an existing Emergency Address object matching the provided address elements
    or creates a new one.

    Site is optional to support orgs without sites enabled but this has not been tested.

    Returns is_created bool to indicate if the address was created and the address obj.
    """

    def get_or_create_emer_addr(self: ZoomBulkTask) -> Tuple[bool, dict]:
        if not is_emergency_address_complete(self.model):
            raise ZeusBulkOpFailed("Emergency address is missing or incomplete")

        if self.model.site_name:
            site_id = self.svc.lookup.site(self.model.site_name)["id"]
        else:
            site_id = None

        try:
            emer_addr = self.svc.lookup.emergency_address(
                self.model.emergency_address, site_id
            )
            is_created = False

        except ZeusBulkOpFailed:
            payload = dict(**self.svc.model.emergency_address)
            if site_id:
                payload["site_id"] = site_id

            emer_addr = self.client.phone_emergency_addresses.create(payload)
            is_created = True

        return is_created, emer_addr


class ZoomEmerAddrCreateTask(ZoomBulkTask, ZoomEmerAddrGetOrCreateMixin):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.emer_addr: dict = {}
        self.is_created = False

    def run(self) -> dict:
        self.is_created, self.emer_addr = self.get_or_create_emer_addr()
        return self.emer_addr

    def rollback(self):
        if self.is_created:
            self.client.phone_emergency_addresses.delete(self.emer_addr["id"])


class ZoomEmerAddrAssignTask(ZoomBulkTask, ZoomEmerAddrGetOrCreateMixin):
    def __init__(self, svc, endpoint, **kwargs):
        super().__init__(svc, **kwargs)
        self.endpoint = endpoint
        self.emer_addr: dict = {}
        self.is_created = False
        self.has_run = False

    @property
    def current_emergency_address_id(self):
        return deep_get(self.svc.current, "emergency_address.id", None)

    def run(self):
        if is_emergency_address_complete(self.model):
            self.is_created, self.emer_addr = self.get_or_create_emer_addr()
            payload = self.build_payload()

            if payload:
                self.endpoint.update(self.svc.current["id"], payload)
                self.has_run = True

    def build_payload(self):
        payload = {}

        if self.emer_addr["id"] != self.current_emergency_address_id:
            payload["emergency_address_id"] = self.emer_addr["id"]

        return payload

    def rollback(self):
        if self.has_run:
            payload = {"emergency_address_id": self.current_emergency_address_id}
            self.endpoint.update(self.svc.current["id"], payload)

        if self.is_created:
            self.client.phone_emergency_addresses.delete(self.emer_addr["id"])


class ZoomPhoneNumberAssignTask(ZoomBulkTask):
    def __init__(self, svc, endpoint, **kwargs):
        super().__init__(svc, **kwargs)
        self.endpoint = endpoint

    def run(self):
        payload = self.build_payload()
        if payload:
            self.endpoint.assign_phone_numbers(self.svc.current["id"], payload)

    def build_payload(self) -> dict:
        payload = {}
        current_number_objects = self.svc.current.get("phone_numbers") or []
        current_phone_numbers = [num["number"] for num in current_number_objects]

        to_assign = []

        for number in self.model.phone_numbers_list:
            if number not in current_phone_numbers:
                resp = self.svc.lookup.phone_number(number)
                to_assign.append({"id": resp["id"], "number": resp["number"]})

        if to_assign:
            payload["phone_numbers"] = to_assign

        return payload


class ZoomPhoneNumberRemoveTask(ZoomBulkTask):
    def __init__(self, svc, endpoint, **kwargs):
        super().__init__(svc, **kwargs)
        self.endpoint = endpoint
        self._phone_numbers: list = []

    def run(self):
        self.get_phone_numbers_to_remove()
        for number in self._phone_numbers:
            self.endpoint.unassign_phone_number(self.svc.current["id"], number["id"])

    def get_phone_numbers_to_remove(self):
        current_number_objects = self.svc.current.get("phone_numbers") or []

        self._phone_numbers = [
            obj
            for obj in current_number_objects
            if obj["number"] not in self.model.phone_numbers_list
        ]


class ZoomCallingPlanAssignTask(ZoomBulkTask):
    def __init__(self, svc, endpoint, **kwargs):
        super().__init__(svc, **kwargs)
        self.endpoint = endpoint
        self._calling_plans = []

    def run(self):
        self.get_calling_plans_to_add()
        payload = self.build_payload()

        if payload:
            self.endpoint.assign_calling_plan(self.svc.current["id"], payload)

    def get_calling_plans_to_add(self):
        current_plan_objects = self.svc.current.get("calling_plans") or []

        fixed_current_plan_names = [
            fix_calling_plan_name(plan["name"]) for plan in current_plan_objects
        ]

        fixed_model_plan_names = [
            fix_calling_plan_name(name) for name in self.model.calling_plans_list
        ]

        names_to_add = [
            name for name in fixed_model_plan_names if name not in fixed_current_plan_names
        ]

        if names_to_add:
            self._calling_plans = [
                plan for plan in self.svc.lookup.calling_plans(names_to_add)
            ]

    def build_payload(self):
        payload = {}
        if self._calling_plans:
            payload = {
                "calling_plans": [{"type": plan["type"]} for plan in self._calling_plans]
            }

        return payload


class ZoomCallingPlanRemoveTask(ZoomBulkTask):
    def __init__(self, svc, endpoint, **kwargs):
        super().__init__(svc, **kwargs)
        self.endpoint = endpoint
        self._calling_plans = []

    def run(self):
        self.get_plans_to_remove()
        for plan in self._calling_plans:
            self.endpoint.unassign_calling_plan(self.svc.current["id"], plan["type"])

    def get_plans_to_remove(self):
        current_plan_objects = self.svc.current.get("calling_plans") or []
        fixed_model_plan_names = [
            fix_calling_plan_name(name) for name in self.model.calling_plans_list
        ]

        self._calling_plans = [
            obj
            for obj in current_plan_objects
            if fix_calling_plan_name(obj["name"]) not in fixed_model_plan_names
        ]


def get_device_type_for_lookup(device_type):
    """
    Return the provided device_type in the correct case for
    a DELETE or UPDATE request

    The phone_devices.LIST device_type param requires the value in
    lower-camel-case (which differs from the form required for CREATE

    """
    create_type = ZOOM_DEVICE_TYPES_CREATE_VALUES.get(device_type.lower(), device_type)
    lookup_type = create_type[0].lower() + create_type[1:]
    return lookup_type
