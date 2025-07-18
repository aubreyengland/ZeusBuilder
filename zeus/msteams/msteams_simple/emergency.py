from typing import Iterator
from .base import CRUDEndpoint


class Addresses(CRUDEndpoint):
    uri = "Skype.Ncs/civicAddresses"

    def list(
        self,
        description: str = None,
        city: str = None,
        populateUsersAndNumbers: bool = False,
        count: int = 0,
        skip: int = 0,
    ) -> Iterator[dict]:
        params = {}

        if description:
            params["description"] = description
        if city:
            params["city"] = city
        if populateUsersAndNumbers:
            params["populateNumberOfVoiceUsers"] = populateUsersAndNumbers
            params["populateNumberOfTelephoneNumbers"] = populateUsersAndNumbers
        if count:
            params["count"] = count
        if skip:
            params["skip"] = skip

        return self._get(self.url("filters"), params=params)


class Locations(CRUDEndpoint):
    uri = "Skype.Ncs/locations"

    def list(
        self,
        civicAddressId: str = None,
        description: str = None,
        city: str = None,
        includeDefault: bool = True,
        populateUsersAndNumbers: bool = False,
        count: int = 0,
        skip: int = 0,
    ) -> Iterator[dict]:
        params = {}

        if civicAddressId:
            params["civicAddressId"] = civicAddressId
        if description:
            params["description"] = description
        if city:
            params["city"] = city
        if populateUsersAndNumbers:
            params["populateNumberOfVoiceUsers"] = populateUsersAndNumbers
            params["populateNumberOfTelephoneNumbers"] = populateUsersAndNumbers
        if count:
            params["count"] = count
        if skip:
            params["skip"] = skip

        locations = self._get(self.url("filters"), params=params)

        # Remove isDefault locations
        if not includeDefault:
            locations = [location for location in locations if not location["isDefault"]]
        return locations


class CallingPolicies(CRUDEndpoint):
    uri = "Skype.Policy/configurations/TeamsEmergencyCallingPolicy"

    def get(self, name: str) -> dict:
        """
        Get a calling policy.

        They have no ID, the `name`\`Identity` string is used as the identifier.

        Args:
            name (str): The name of the calling policy.

        Returns:
            dict: A dictionary containing the calling policy.
        """
        return self._get(self.url(f"/configuration/{name}"))

    def list(self) -> Iterator[dict]:
        """
        Get a list of calling policies.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the calling policies.
        """
        return self._get(self.url())

    def create(self, payload: dict) -> None:
        """
        Create a calling policy.

        Args:
            payload (dict):
                ```
                {
                    "Identity": "Test Emergency Calling Policy",
                    "Description": "For testing purposes",
                    "EnhancedEmergencyServiceDisclaimer": "For testing purposes",
                    "ExternalLocationLookupMode": "Enabled",
                    "ExtendedNotifications": [
                        {
                            "EmergencyDialString": "911",
                            "NotificationMode": "NotificationOnly",
                            "NotificationDialOutNumber": "",
                            "NotificationGroup": "testuser@cdwprodev.com",
                        },
                        {
                            "EmergencyDialString": "912",
                            "NotificationMode": "ConferenceMuted",
                            "NotificationDialOutNumber": "12223334444",
                            "NotificationGroup": "testuser@cdwprodev.com;testguest@cdwprodev.com",
                        },
                        {
                            "EmergencyDialString": "913",
                            "NotificationMode": "ConferenceUnMuted",
                            "NotificationDialOutNumber": "12223334444",
                            "NotificationGroup": "testuser@cdwprodev.com",
                        },
                    ],
                    "NotificationMode": None,
                    "NotificationDialOutNumber": None,
                    "NotificationGroup": None,
                }
                ```

        Returns:
            None: Unlike most create operations
        """
        self.session.post(self.url(), json=payload)

    def update(self, name: str, payload: dict) -> None:
        """
        Update a calling policy.

        Args:
            name (str): The name of the calling policy.
            payload (dict):
                ```
                {
                    "Identity": "Test Emergency Calling Policy",
                    "Description": "For testing purposes",
                    "EnhancedEmergencyServiceDisclaimer": "For testing purposes",
                    "ExternalLocationLookupMode": "Enabled",
                    "ExtendedNotifications": [
                        {
                            "EmergencyDialString": "911",
                            "NotificationMode": "NotificationOnly",
                            "NotificationDialOutNumber": "",
                            "NotificationGroup": "testuser@cdwprodev.com",
                        },
                        {
                            "EmergencyDialString": "912",
                            "NotificationMode": "ConferenceMuted",
                            "NotificationDialOutNumber": "12223334444",
                            "NotificationGroup": "testuser@cdwprodev.com;testguest@cdwprodev.com",
                        },
                        {
                            "EmergencyDialString": "913",
                            "NotificationMode": "ConferenceUnMuted",
                            "NotificationDialOutNumber": "12223334444",
                            "NotificationGroup": "testuser@cdwprodev.com",
                        },
                    ],
                    "NotificationMode": None,
                    "NotificationDialOutNumber": None,
                    "NotificationGroup": None,
                }
                ```
        """
        self.session.put(self.url(f"/configuration/{name}"), json=payload)

    def delete(self, name: str) -> None:
        """
        Delete a calling policy.

        Args:
            name (str): The name of the calling policy.
        """
        self.session.delete(self.url(f"/configuration/{name}"))


class CallRoutingPolicies(CRUDEndpoint):
    uri = "Skype.Policy/configurations/TeamsEmergencyCallRoutingPolicy"

    def get(self, name: str) -> dict:
        """
        Get a call routing policy.

        They have no ID, the `name`\`Identity` string is used as the identifier.

        Args:
            name (str): The name of the call routing policy.

        Returns:
            dict: A dictionary containing the call routing policy.
        """
        return self._get(self.url(f"/configuration/{name}"))

    def list(self) -> Iterator[dict]:
        """
        Get a list of call routing policies.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the call routing policies.
        """
        return self._get(self.url())

    def create(self, payload: dict) -> None:
        """
        Create a call routing policy.

        Args:
            payload (dict):
                ```
                {
                    "Identity": "test1",
                    "Description": "test1",
                    "AllowEnhancedEmergencyServices": true,
                    "EmergencyNumbers": [
                        {
                            "EmergencyDialString": "911",
                            "EmergencyDialMask": "",
                            "OnlinePSTNUsage": "National"
                        }
                    ],
                }
                ```

        Returns:
            None: Unlike most create operations
        """
        self.session.post(self.url(), json=payload)

    def update(self, name: str, payload: dict) -> None:
        """
        Update a call routing policy.

        Args:
            name (str): The name of the call routing policy.
            payload (dict):
                ```
                {
                    "Description": "test1",
                    "AllowEnhancedEmergencyServices": true,
                    "EmergencyNumbers": [
                        {
                            "EmergencyDialString": "911",
                            "EmergencyDialMask": "",
                            "OnlinePSTNUsage": "National"
                        }
                    ],
                }
                ```
        """
        self.session.put(self.url(f"/configuration/{name}"), json=payload)

    def delete(self, name: str) -> None:
        """
        Delete a call routing policy.

        Args:
            name (str): The name of the call routing policy.
        """
        self.session.delete(self.url(f"/configuration/{name}"))
