import re
import logging
from typing import Optional
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BulkSvc, BulkTask, SvcClient
from ..wbxc_simple import WbxcSimpleClient, WbxcServerFault
from zeus.wbxc.wbxc_models.shared import validate_extension, validate_e164_phone_number

log = logging.getLogger(__name__)


class WbxcBulkSvc(BulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)


class WbxcBulkTask(BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcBulkSvc = svc


class WbxcSvcClient(SvcClient):
    tool = "wbxc"
    client_cls = WbxcSimpleClient


class WbxcLookup:
    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.current: dict = {}

    def device(self, mac: str) -> dict:
        """
        Retrieves device information based on provided MAC address

        Args:
            mac (str): The MAC of the device to retrieve

        Returns:
            dict: A dictionary containing information about the device.
                The dictionary includes attributes such as ID, display name, owner ID, model, etc.
        """
        device = next((self.client.devices.list(mac=mac)), None)

        if not device:
            raise ZeusBulkOpFailed(f"Device {mac} Does Not Exist.")

        return device

    def location(self, name: str) -> dict:
        """
        Retrieves location information based on the provided name.

        Parameters:
            name (str): The name of the location to retrieve.

        Returns:
            dict: A dictionary containing information about the location.
             The dictionary includes attributes such as ID, name,
             address, city, country, etc.

        Raises:
        - ZeusBulkOpFailed: If the location with the provided name does not exist.
        """
        existing_locations = self.client.locations.list()
        match = next((loc for loc in existing_locations if loc["name"] == name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Location '{name}' Does Not Exist.")

        return match

    def number(self, **params) -> dict:
        matches = list(
            self.client.numbers.list(**params)
        )
        if len(matches) > 1:
            raise ZeusBulkOpFailed(f"Multiple phone number matches for: {params}")

        if not matches:
            raise ZeusBulkOpFailed(f"Phone number not found using: {params}.")

        return matches[0]

    def device_member_by_number(self, device_id: str, location_id: str, number: str) -> dict:
        matches = list(
            self.client.device_members.search(
                device_id=device_id, location_id=location_id, phoneNumber=number
            )
        )
        if len(matches) > 1:
            raise ZeusBulkOpFailed(f"Multiple line member matches for {number}")

        if not matches:
            raise ZeusBulkOpFailed(f"No line member matches found for {number}")

        return matches[0]

    def device_member_by_ext(self, device_id: str, location_id: str, ext: str) -> dict:
        """
        Search for a device member by extension.
        The search returns extensions that contain the provided value so filter
        potential matches to exact matches.
        """
        resp = self.client.device_members.search(device_id=device_id, location_id=location_id, extension=ext)
        matches = [
            item for item in resp
            if item.get("extension") == ext
        ]
        if len(matches) > 1:
            raise ZeusBulkOpFailed(f"Multiple line member matches for {ext}")

        if not matches:
            raise ZeusBulkOpFailed(f"No line member matches found for {ext}")

        return matches[0]

    def hunt_group(self, name):
        existing = self.client.huntgroups.list()
        match = next((item for item in existing if item["name"] == name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Hunt Group {name} Not Found.")

        return match

    def location_call_setting(self, name: str) -> dict:
        """
        Retrieves location information based on the provided name.

        Parameters:
            name (str): The name of the location to retrieve.

        Returns:
            dict: A dictionary containing information about the location.
             The dictionary includes attributes such as ID, name, address,
             city, country, etc.

        Raises:
            ZeusBulkOpFailed: If the location with the provided name does not exist.
        """
        existing_locations = self.client.location_call_settings.list()
        match = next((loc for loc in existing_locations if loc["name"] == name), None)

        if not match:
            raise ZeusBulkOpFailed(f"Location '{name}' Does Not Exist.")

        return match

    def is_calling_enabled_for_location(self, identifier) -> bool:
        """
        Check if calling is enabled for a specific location.

        Parameters:
            identifier (str): The value of the ID of the location to check
             for calling enabled status.

        Returns:
            bool: True if calling is enabled for the location with the
             specified ID or name, False otherwise.
        """
        try:
            self.client.location_call_settings.get(identifier)
            return True
        except WbxcServerFault:
            return False

    def routing_choice(self, identifier: str) -> dict:
        """
        Retrieves Routes information based on the provided ID or name.
        Trunk and Route Group qualify as Route.

        Parameters:
            identifier (str): The ID or name of the location to retrieve.

        Returns:
            dict: A dictionary containing information about the Trunk or Route Group.
             The dictionary includes attributes such as ID, name, type.

        Raises:
          ZeusBulkOpFailed: If the Trunk or Route Group with the provided identifier does not exist.
        """
        routing_choices = list(self.client.location_route_choices.list())
        match = next((loc for loc in routing_choices if loc["name"] == identifier), None)

        if not match:
            match = next((loc for loc in routing_choices if loc["id"] == identifier), None)

        if not match:
            raise ZeusBulkOpFailed(f"Trunk or Route Group '{identifier}' Does Not Exist.")

        return match

    def supported_device(self, model: str) -> dict:
        """
        Retrieves supported device information based on the provided model.

        Parameters:
        - model (str): The model of the device to retrieve.

        Returns:
        - dict: A dictionary containing information about the device.

        Raises:
        - ZeusBulkOpFailed: If the device with the provided model does not exist.
        """
        supported_devices = self.client.devices.supported_devices()

        # Checks if the full device model is entered, ignores case
        match = next(
            (
                device
                for device in supported_devices
                if device["model"].casefold() == model.casefold()
            ),
            None,
        )

        if not match:
            raise ZeusBulkOpFailed(
                f"Model {model} is not supported. Check spelling and make sure to include the full model ('Cisco 8811' for example)."
            )

        return match

    def announcement(
            self, filename: str, level: str, identifier: Optional[str] = None
    ) -> dict:
        """
        Retrieves announcements information based on the provided filename, level, and identifier.

        Args:
            filename (str): The filename to search for
            level (str): The level of search, can be `ORGANIZATION` or `LOCATION`
            identifier (str, optional): The ID of the location if level is `LOCATION`
             Includes a parameter with the location ID

        Returns:
            dict: A dictionary containing information about the announcement, with attributes
             such as ID, name, fileName, etc.

        Raises:
            ZeusBulkOpFailed: If the combination of level and identifier is invalid.
            ZeusBulkOpFailed: If the announcement with the provided filename does not exist.
        """
        if level.upper() not in {"ORGANIZATION", "LOCATION"}:
            raise ZeusBulkOpFailed(
                f"Invalid level type '{level}'. It should be either 'ORGANIZATION' or 'LOCATION'."
            )

        if level.upper() == "LOCATION" and not identifier:
            raise ZeusBulkOpFailed(
                "Location identifier is required when level is 'LOCATION'."
            )

        params = {"locationId": identifier} if level.upper() == "LOCATION" else {}
        announcements = list(self.client.announcements.list(**params))

        match = next((a for a in announcements if a["fileName"] == filename), None)
        if not match:
            raise ZeusBulkOpFailed(
                f"Announcement file name '{filename}' does not exist in '{level}'."
            )

        return match

    def workspace_by_name(self, name, **params):
        """
        Find the unique workspace matching the provided name.

        Args:
            name (str): Workspace display name
            params (dict, None): Additional query params for the workspace LIST request
        """
        params = params.copy()
        params["displayName"] = name
        matches = [
            resp
            for resp in self.client.workspaces.list(**params)
            if resp["displayName"].lower() == name.lower()
        ]
        if len(matches) == 0:
            raise ZeusBulkOpFailed(f"Workspace '{name}' not found")

        if len(matches) > 1:
            raise ZeusBulkOpFailed(f"Multiple workspaces with display name: '{name}' found")

        return matches[0]

    def workspace_by_number(self, number, name=None) -> dict:
        """
        Find the unique workspace matching the provided number or extension.
        The workspace name can be provided to disambiguate in cases where multiple
        workspaces have the same extension but no E.164 number.

        Args:
            number (str, None): Workspace E.164 number or extension
            name (str, None): If provided, matching workspace display name must match
        """
        lookup_descr = f"number: {number}" f"{' display name: ' + name if name else ''}"

        params = {"ownerType": "PLACE"}
        if number.startswith("+"):
            params["phoneNumber"] = number
        else:
            params["extension"] = number

        matches = list(self.client.org_phone_numbers.list(**params))

        if name:
            matches = [
                match
                for match in matches
                if name.lower() == deep_get(match, "owner.firstName", default="").lower()
            ]

        if not matches:
            raise ZeusBulkOpFailed(f"Workspace matching {lookup_descr} not found")

        if len(matches) > 1:
            raise ZeusBulkOpFailed(f"Multiple workspaces match {lookup_descr}")

        workspace_id = matches[0]["owner"]["id"]
        return self.client.workspaces.get(workspace_id)

    def workspace(self, name: str, number: str = None, location: str = None) -> dict:
        """
        Retrieves workspace information based on the provided name.

        Parameters:
            name (str): The name of the workspace to retrieve.
            number (str, optional): The phone number or extension for additional filtering.
            location (str, optional): The location name associated with the phone number or extension.

        Returns:
            dict: A dictionary containing information about the workspace.

        Raises:
            ZeusBulkOpFailed: If no workspace exists with the given name, or if multiple workspaces are found
                and the provided phone number and location do not match any workspace.

        See https://github.com/cdwlabs/zeus/issues/504 for details.

        Lookup will fail if any of the following conditions are met:
        - Multiple matches are found with the exact name.
        - Both a location and an extension are provided.
        - No phone number is assigned.
        - An update to the extension is attempted.
        """
        params = {"displayName": name}
        workspaces = [
            resp
            for resp in self.client.workspaces.list(**params)
            if resp["displayName"].lower() == name.lower()
        ]
        not_exist_message = f"Workspace '{name}' Does Not Exist."

        if not workspaces:
            raise ZeusBulkOpFailed(not_exist_message)

        if len(workspaces) == 1:
            return workspaces[0]

        if not (number and location):
            raise ZeusBulkOpFailed(
                f"Multiple workspaces found for '{name}'. `Location` and either `Phone Number` or `Extension` must be provided."
            )

        for workspace in workspaces:
            associated_numbers = self.client.workspace_associated_numbers.get(
                workspace["id"]
            )
            phone_numbers = associated_numbers.get("phoneNumbers", [])
            workspace_location = deep_get(associated_numbers, "location.name", "")

            for phone_number in phone_numbers:
                if (
                        phone_number["primary"]
                        and (
                        phone_number["external"] == number
                        or phone_number["extension"] == number
                )
                        and workspace_location.lower() == location.lower()
                ):
                    return workspace

        raise ZeusBulkOpFailed(
            f"Multiple workspaces found for '{name}', but no match with the provided Number and Location."
        )

    def user(self, name: str, calling_data: bool = False) -> dict:
        """
        Retrieves user information based on the provided name.

        Parameters:
            name (str): The email address of the user to retrieve.
            calling_data (bool, optional): Whether to include calling data in the response. Defaults to False.

        Returns:
            dict: A dictionary containing information about the user.

        Raises:
            ZeusBulkOpFailed: If the user with the provided name does not exist.

        ```
        example response:
        {
            'id': 'Y2lzY....',
            'emails': ['admin@zeuslab.wbx.ai']
        }
        ```
        """
        if calling_data:
            params = {"email": name, "callingData": "true"}
        else:
            params = {"email": name}

        existing_users = list(self.client.users.list(**params))

        match = next(
            (
                user
                for user in existing_users
                if any(email.lower() == name.lower() for email in user.get("emails", []))
            ),
            None,
        )

        if not match:
            raise ZeusBulkOpFailed(f"User '{name}' Does Not Exist.")

        return match

    def license(self, name: str, sub_id: str = "") -> dict:
        """
        Retrieves license information based on the provided name and optional subscription ID.

        Parameters:
            name (str): The name of the license to retrieve.
            sub_id (str, optional): The subscription ID to match. Defaults to None.

        Returns:
            dict: A dictionary containing information about the license.

        Raises:
            ZeusBulkOpFailed: If no license with the provided name (and optional subscription ID) exists,
            or if multiple licenses with the same name (and optional subscription ID) are found.

        Example name:
            `Webex Calling - Professional`
            `Webex Calling - Workspaces`
        """
        licenses = self.client.licenses.list()

        matches = [
            lic
            for lic in licenses
            if lic["name"].lower() == name.lower()
               and (not sub_id or lic["subscriptionId"] == sub_id)
        ]

        if not matches and not sub_id:
            raise ZeusBulkOpFailed(f"License '{name}' Does Not Exist.")

        if not matches:
            raise ZeusBulkOpFailed(
                f"License '{name}' with the subscription '{sub_id}' does not exist."
            )

        if len(matches) == 1:
            return matches[0]

        raise ZeusBulkOpFailed(
            f"Multiple licenses with the name '{name}' found. The Subscription ID must be provided."
        )

    def virtual_line(
            self, first: str, last: str, number: str = None, location: str = None
    ) -> dict:
        """
        Retrieves virtual line information based on the provided name.

        Parameters:
            first (str): The first name of the virtual line to retrieve.
            last (str): The last name of the virtual line to retrieve.
            number (str, optional): The phone number or extension for additional filtering.
            location (str, optional): The location name associated with the phone number or extension.

        Returns:
            dict: A dictionary containing information about the virtual line.

        Raises:
            ZeusBulkOpFailed: If the virtual line with the provided name does not exist.

        Note:
        - Virtual Line list query using the `ownerName` utilizes the concatenation of the
          first and last names when the API filters the results.
        """
        if not first or not last:
            raise ZeusBulkOpFailed("Virtual Line first and last names must be provided.")

        owner_name = f"{first} {last}"
        params = {"ownerName": owner_name}
        virtual_lines = list(self.client.virtual_lines.list(**params))
        not_exist_message = f"Virtual Line '{owner_name}' Does Not Exist."

        if not virtual_lines:
            raise ZeusBulkOpFailed(not_exist_message)

        if len(virtual_lines) == 1:
            first_match = virtual_lines[0]["firstName"].lower() == first.lower()
            last_match = virtual_lines[0]["lastName"].lower() == last.lower()
            if first_match and last_match:
                return virtual_lines[0]
            raise ZeusBulkOpFailed(not_exist_message)

        if not (number and location):
            raise ZeusBulkOpFailed(
                f"Multiple Virtual Lines found for '{owner_name}'. `Location` and either `Phone Number` or `Extension` must be provided."
            )

        for virtual_line in virtual_lines:
            phone_numbers = virtual_line.get("number", {})
            primary_number = phone_numbers.get("primary")
            external_number = phone_numbers.get("external", "")
            extension_number = phone_numbers.get("extension", "")
            location_name = deep_get(virtual_line, "location.name", "")

            if (
                    virtual_line["firstName"].lower() == first.lower()
                    and virtual_line["lastName"].lower() == last.lower()
                    and primary_number
                    and to_us_e164(external_number) == number
                    or extension_number == number
                    and location_name.lower() == location.lower()
            ):
                return virtual_line

        raise ZeusBulkOpFailed(
            f"Multiple Virtual Lines for '{owner_name}', but no match with the provided Number and Location."
        )

    def voicemail_group(self, name: str) -> dict:
        """
        Retrieves voicemail group information based on the provided name.

        Parameters:
            name (str): The name of the voicemail group to retrieve.

        Returns:
            dict: A dictionary containing information about the voicemail group.

        Raises:
            ZeusBulkOpFailed: If the voicemail group with the provided name does not exist.
        """

        params = {"name": name}
        existing_voicemail_groups = list(self.client.voicemail_group.list(**params))

        match = next(
            (
                vmg
                for vmg in existing_voicemail_groups
                if vmg["name"].lower() == name.lower()
            ),
            None,
        )

        if not match:
            raise ZeusBulkOpFailed(f"Voicemail Group '{name}' Does Not Exist.")

        return match

    def org_phone_number(
            self,
            number: str = None,
            location: str = None,
            owner_id: str = None,
            owner_type: str = None,
    ) -> dict:
        """
        Retrieves the phone number details based on the provided E164 Phone Number,
        extension with the location name, or owner ID.

        Parameters:
            number (str, optional): The phone number or extension to retrieve.
            location (str, conditional): The location name if extension is searched.
            owner_id (str, optional): The owner ID to retrieve the phone number details.
            owner_type (str, optional)

        Returns:
            dict: A dictionary containing information about the phone number.

        Raises:
            ZeusBulkOpFailed: If the phone number with the provided criteria does not exist.
        """
        params = {}
        if owner_id:
            params = {"ownerId": owner_id}
        elif number:
            params = (
                {"phoneNumber": number} if number.startswith("+") else {"extension": number}
            )
        else:
            raise ValueError("Either `owner_id` or `number` must be provided.")

        if owner_type:
            params["ownerType"] = owner_type

        matched_numbers = list(self.client.org_phone_numbers.list(**params))

        if owner_id:
            match = matched_numbers[0] if matched_numbers else None
        else:
            match = next(
                (
                    num
                    for num in matched_numbers
                    if num.get("phoneNumber") == number
                       or num.get("extension") == number
                       and num["location"]["name"].lower() == location.lower()
                ),
                None,
            )
        if not match:
            if owner_id:
                raise ZeusBulkOpFailed(
                    f"Phone number or Extension with owner ID '{owner_id}' Does Not Exist."
                )
            elif number.startswith("+"):
                raise ZeusBulkOpFailed(f"Phone Number '{number}' Does Not Exist.")
            else:
                raise ZeusBulkOpFailed(
                    f"Extension '{number}' in location '{location}' Does Not Exist."
                )

        return match

    def call_park_extension(self, number: str, location: str) -> dict:
        params = {"extension": number}
        matched_extensions = list(self.client.call_park_extensions.list(**params))

        match = next(
            (
                num
                for num in matched_extensions
                if num.get("extension") == number
                   and num["locationName"].lower() == location.lower()
            ),
            None,
        )

        if not match:
            raise ZeusBulkOpFailed(
                f"Call Park Extension '{number}' in '{location}' Does Not Exist."
            )

        return match

    def monitor_id(self, number: str, location_name: str) -> str:
        """
        Retrieves the owner ID of the phone number, extension or call park
        used by user and workspace monitoring.

        If the phone number is not found, the same exception is raised from
        the 'org_phone_numbers' lookup. If the extension is not found, the method
        attempts to find the same extension/location in the 'call_park_extensions'
        lookup. If the extension is also not found, a new exception is raised.

        Parameters:
            number (str): The phone number in E164 or extension to look up.
            location_name (str): The location name where the number or extension is located.

        Returns:
            str: The owner ID if found.
        """
        unassigned_msg = f"Monitored Number '{number}' is unassigned."
        not_exist_msg = f"Phone Number '{number}' Does Not Exist."
        call_park_not_exist_msg = f"Monitored Extension or Call Park '{number}' in location '{location_name}' Does Not Exist."

        try:
            resp = self.org_phone_number(number, location_name)
            if "owner" not in resp:
                raise ZeusBulkOpFailed(unassigned_msg)

            return resp["owner"]["id"]

        except ZeusBulkOpFailed as e:
            if str(e) in [unassigned_msg, not_exist_msg]:
                raise e

            try:
                resp = self.call_park_extension(number, location_name)
                return resp["id"]

            except ZeusBulkOpFailed:
                raise ZeusBulkOpFailed(call_park_not_exist_msg)

    @staticmethod
    def ecbn_available_number(client_ecbn_method, identifier: str, number: str) -> dict:
        """
        Retrieves the emergency call back number that can be assigned
        to the user, workspace or virtual line that is associated with
        the same location.

        Parameters:
            client_ecbn_method : The method to call for retrieving available ECBNs.
            identifier (str): The ID of the user, workspace or virtual line to retrieve.
            number (str): The number of the ecbn to retrieve.

        Returns:
             dict: A dictionary containing information about the ecbn.

        Raises:
            ZeusBulkOpFailed: If the number provided does not exist.
        """
        params = {"phoneNumber": number}
        available_numbers = list(client_ecbn_method(identifier, **params))

        match = next(
            (num for num in available_numbers if num["phoneNumber"] == number), None
        )

        if not match:
            raise ZeusBulkOpFailed(
                f"Location Member Number '{number}' Does Not Exist for the location."
            )

        return match

    @staticmethod
    def primary_available_number(
            client_primary_numbers_method, location_id: str, number: str
    ) -> dict:
        """
        Retrieves the available numbers that can be assigned
        to the user, workspace or virtual line that is associated with
        the same location.

        Parameters:
            client_primary_numbers_method : The method to call for retrieving available ECBNs.
            location_id (str): The Location ID of the user, workspace or virtual line.
            number (str): The number to assign as primary.

        Returns:
             dict: A dictionary containing information about the ecbn.

        Raises:
            ZeusBulkOpFailed: If the number provided does not exist.
        """
        params = {"locationId": location_id}
        available_numbers = list(client_primary_numbers_method(**params))

        match = next(
            (num for num in available_numbers if num["phoneNumber"] == number), None
        )

        if not match:
            raise ZeusBulkOpFailed(
                f"Phone Number '{number}' Does Not Exist for the location."
            )

        return match


def remove_to_none(input_dict: dict, replacement_value=None) -> dict:
    """
    Replaces the string 'remove' (case-insensitive) with None in the values of a dictionary.

    Parameters:
        input_dict (dict): The input dictionary
        replacement_value (optional): The value to replace 'remove' with. Defaults to `None`.

    Returns:
        dict: Updated dictionary where 'remove' values are replaced with None.
    """
    updated_dict = {}
    for key, value in input_dict.items():
        if isinstance(value, dict):
            updated_dict[key] = remove_to_none(value, replacement_value)
        elif isinstance(value, str) and value.lower() == "remove":
            updated_dict[key] = replacement_value
        else:
            updated_dict[key] = value
    return updated_dict


def parse_call_permissions(resp: dict) -> dict:
    """
    Parses outgoing call permissions from a given JSON response.
    Used by export services for Locations, Users, Workspace,
    and Virtual Line outgoing permissions.
    """
    parsed = {}
    for item in resp.get("callingPermissions", []):
        permission = item["callType"].lower()
        action = item.get("action", "")
        transfer = item.get("transferEnabled", "")

        parsed[permission] = action
        parsed[f"{permission}_transfer"] = transfer
    return parsed


def convert_call_permissions(model_permissions: dict) -> list:
    """
    Convert the model permission fields into the format needed for the update payload.

    The model includes two fields for each permission.
     Field 1 Name:
      - matches permission name (ex: internal_call)
     Field 1 Value:
      - 'ALLOW' or 'BLOCK'
     Field 2 Name:
      - permission name with '_transfer' appended (ex: internal_call_transfer)
     Field 2 Value:
      - 'Y' or 'N' (converted to True/False by `to_payload` method)

    The models fields that refer to the same permission must be combined into a single JSON
    object:
    ```
    {
        'callType': <<PERMISSION NAME>>,
        'action': <<ALLOW or BLOCK>>,
        'transferEnabled': <<true or false>>
    }
    ```
    The `callType` key must be present. One of the `action` or `transferEnabled` keys may
    be missing if only one of the fields for the permission have a value.
    """
    by_permission_name = {}

    for key, value in model_permissions.items():

        if m := re.match(r"(\w+)_transfer$", key, re.I):
            permission_name = m.group(1).upper()
            entry_key = "transferEnabled"
        else:
            permission_name = key.upper()
            entry_key = "action"

        entry = by_permission_name.setdefault(
            permission_name, {"callType": permission_name}
        )
        entry[entry_key] = value

    return list(by_permission_name.values())


def convert_call_forwarding(model_call_forward: dict) -> dict:
    """
    Convert the model permission fields into the format needed for the update payload.
    """
    group_forwarding = {}
    key_mapping = {
        "always": "always",
        "busy": "busy",
        "no_answer": "noAnswer",
        "business_continuity": "businessContinuity",
    }
    value_mapping = {
        "destination": "destination",
        "vm": "destinationVoicemailEnabled",
        "enabled": "enabled",
        "rings": "numberOfRings",
        "tone": "ringReminderEnabled",
    }
    for key, value in model_call_forward.items():
        call_forward_type, call_forward_value = key.rsplit("_", 1)
        call_forward_type = key_mapping.get(call_forward_type, call_forward_type)
        call_forward_value = value_mapping.get(call_forward_value, call_forward_value)
        group_forwarding.setdefault(call_forward_type, {})[call_forward_value] = value

    return group_forwarding


def parse_call_forwarding(resp: dict) -> dict:
    """
    Parses call forwarding from a given JSON response.
    Used by export services for Users, Workspace,
    and Virtual Line call forwarding settings.
    """
    model_call_forward = {}
    key_mapping = {
        "always": "always",
        "busy": "busy",
        "noAnswer": "no_answer",
        "businessContinuity": "business_continuity",
    }
    value_mapping = {
        "destination": "destination",
        "destinationVoicemailEnabled": "vm",
        "enabled": "enabled",
        "numberOfRings": "rings",
        "ringReminderEnabled": "tone",
    }
    for call_forward_type, values in resp.get("callForwarding", {}).items():
        for key, value in values.items():
            if key == "systemMaxNumberOfRings":
                continue
            call_forward_type = key_mapping.get(call_forward_type, call_forward_type)
            key = value_mapping.get(key, key)
            model_key = f"{call_forward_type}_{key}"
            model_call_forward[model_key] = value

    business_continuity_values = resp.get("businessContinuity", {})
    for key, value in business_continuity_values.items():
        key = value_mapping.get(key, key)
        model_key = f"business_continuity_{key}"
        model_call_forward[model_key] = value

    return model_call_forward


def convert_voicemail(model_payload) -> dict:
    """
    Convert the model voicemail fields into the format needed for the update payload.

    The input dictionary keys are split by the first underscore into sections and attributes.

    - Section: Represents a configuration group (ex: sendAllCalls, sendBusyCalls).
    - Attribute: Represents a specific setting within that group (ex: enabled, greeting).

    The models fields that refer to the same section must be combined into a single JSON
    object:
    ```
    {
        "sendAllCalls_enabled": False,
        "sendBusyCalls_enabled": True,
        "sendBusyCalls_greeting": "CUSTOM"
    }
    ```
    Output:
    ```
    {
        "sendAllCalls": {"enabled": False},
        "sendBusyCalls": {"enabled": True,"greeting": "CUSTOM"}
    }
    ```
    Each section must be present, and the corresponding attributes are grouped under that section.
    """
    group_voicemail = {}

    for key, value in model_payload.items():
        section, attribute = key.split("_", 1)
        section_dict = group_voicemail.setdefault(section, {})
        section_dict[attribute] = value

    return group_voicemail


def backfill_payload_with_current(payload: dict, current: dict) -> dict:
    """
    Back-fills the payload with the current config in the same order,
    if the keys and values are missing from the model.
    ```
    payload = {
        "sendBusyCalls": {
            "enabled": False
        }
    }
    current = {
        "sendBusyCalls": {
            "enabled": True,
            "greeting": "DEFAULT"
        }
    }
    updated_payload = {
        "sendBusyCalls": {
            "enabled": False,
            "greeting": "DEFAULT"
        }
    }
    ```
    """
    for key, value in current.items():
        if key not in payload:
            payload[key] = value
        elif isinstance(value, dict) and isinstance(payload[key], dict):
            backfill_payload_with_current(payload[key], value)

    # Reorder the payload to match the order in `current`
    ordered_payload = {key: payload[key] for key in current.keys() if key in payload}

    # Add any remaining keys from payload that weren't in current
    extra_keys = {key: payload[key] for key in payload if key not in ordered_payload}
    ordered_payload.update(extra_keys)

    return ordered_payload


def to_us_e164(number: str) -> str:
    """
    Converts a given phone number to E.164 format for US/Canada numbers.
    Examples:
        to_us_e164("15554441234")
        "+15554441234"

        to_us_e164("1-555-444-1234")
        "+15554441234"

        to_us_e164("+1 555 444 1234")
        "+15554441234"

        to_us_e164("234567890")  # Invalid, should return as is
        "234567890"

        to_us_e164("1234")  # Invalid, should return as is
        "1234"
    """
    normalized_number = re.sub(r"[^\d+]", "", number)

    return (
        normalized_number
        if normalized_number.startswith("+")
        else f"+1{normalized_number}"
        if len(normalized_number) == 10
        else f"+{normalized_number}"
        if len(normalized_number) == 11 and normalized_number.startswith("1")
        else normalized_number
    )


def build_number_lookup_params(number: str) -> list[dict]:
    """
    Returns query param dictionaries for the number lookup.

    Because the get_member API returns phone numbers with the +CC,
    it's not possible to know if a value in the worksheet is a phone number
    or 10-digit extension. For this reason, params for a phone number lookup
    and an extension lookup are returned for 10-digit numbers.

    Numbers less than 10 digits will be assumed to be extensions and numbers
    greater than 10 digits or formatted as +E.164 will be assumed to be phone numbers.
    and only a single param will be returned.
    """
    param_sets = []
    pn_param = dict(phoneNumber=number, numberType="NUMBER", available=False)
    ext_param = dict(extension=number, numberType="EXTENSION")

    number = str(number).strip()

    if len(number) == 10:
        param_sets.append(pn_param)
        param_sets.append(ext_param)

    elif number.startswith("+"):
        param_sets.append(pn_param)

    elif len(number) < 10:
        param_sets.append(ext_param)

    else:
        param_sets.append(pn_param)

    return param_sets
