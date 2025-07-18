from typing import Iterator
from .base import CRUDEndpoint


class Subnets(CRUDEndpoint):
    """
    Subnets associated with an **Emergency Address/Location.**
    Different than the subnets under a Network Site.
    """

    uri = "Skype.Ncs/subnets"

    def get(self, subnet: str) -> dict:
        """
        Get a subnet. Subnets have no ID, the `subnet` string is used as the identifier.

        Args:
            subnet (str): The subnet to retrieve.

        Returns:
            dict: A dictionary containing the subnet.
        """
        return self._get(self.url(subnet))

    def list(self, locationId: str = None) -> Iterator[dict]:
        """
        Get a list of subnets.

        Args:
            locationId (str, optional): Filter list by location ID the subnets belong to. Defaults to `None`.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the subnets.
        """
        params = {}
        if locationId:
            params["locationId"] = locationId

        return self._get(self.url("filters"), params=params)

    def create(self, payload: dict) -> None:
        """
        Create a subnet. Both `create` & `update` are `PUT` operations.
        Will overwrite an existing subnet if it already exists.

        Args:
            payload (dict): The payload to create the subnet with.
                ```
                {
                    "locationId": "0",
                    "subnet": "10.99.99.0",
                    "description": "subnet 99",
                }
                ```

        Returns:
            None: Unlike most create operations, due to being a PUT
        """
        self.session.put(self.url(payload["subnet"]), params=payload)

    def update(self, subnet: str, payload: dict) -> None:
        """
        Update a subnet. Both `create` & `update` are `PUT` operations.
        Will create the subnet if it does not exist.

        Args:
            subnet (str): The subnet to update.
            payload (dict): The payload to update the subnet with.
                ```
                {
                    "locationId": "1",
                    "subnet": "10.99.99.0",
                    "description": "subnet 99",
                }
                ```
        """
        self.session.put(self.url(subnet), params=payload)

    def delete(self, subnet: str) -> None:
        """
        Delete a subnet.

        Args:
            subnet (str): The subnet to delete.
        """
        self.session.delete(self.url(subnet))


class Switches(CRUDEndpoint):
    """Switches associated with an Emergency Address/Location."""

    uri = "Skype.Ncs/switches"

    def get(self, chassisId: str) -> dict:
        """
        Get a Switch. Switches have no ID, the `chassisId` string is used as the identifier.

        Args:
            chassisId (str): The chassis ID of the Switch to retrieve.

        Returns:
            dict: A dictionary containing the Switch.
        """
        return self._get(self.url(chassisId))

    def list(self, locationId: str = None) -> Iterator[dict]:
        """
        Get a list of Switches.

        Args:
            locationId (str, optional): Filter list by location ID the Switches belong to. Defaults to `None`.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the Switches.
        """
        params = {}
        if locationId:
            params["locationId"] = locationId

        return self._get(self.url("filters"), params=params)

    def create(self, payload: dict) -> None:
        """
        Create a Switch. Both `create` & `update` are `PUT` operations.
        Will overwrite an existing Switch if it already exists.
        Network endpoints are different from the other endpoints. They use URL query parameters instead of JSON payloads.

        Args:
            payload (dict): The payload to create the Switch with.
                ```
                {
                    "locationId": "0",
                    "chassisId": "00-00-00-00-99-99",
                    "description": "switch 99",
                }
                ```

        Returns:
            None: Unlike most create operations, due to being a PUT
        """
        self.session.put(self.url(payload["chassisId"]), params=payload)

    def update(self, chassisId: str, payload: dict) -> None:
        """
        Update a Switch. Both `create` & `update` are `PUT` operations.
        Will create the Switch if it does not exist.

        Args:
            chassisId (str): The chassis ID of the Switch to update.
            payload (dict): The payload to update the Switch with.
                ```
                {
                    "locationId": "1",
                    "chassisId": "00-00-00-00-99-99",
                    "description": "switch 99",
                }
                ```
        """
        self.session.put(self.url(chassisId), params=payload)

    def delete(self, chassisId: str) -> None:
        """
        Delete a Switch.

        Args:
            chassisId (str): The chassis ID of the Switch to delete.
        """
        self.session.delete(self.url(chassisId))


class Ports(CRUDEndpoint):
    """Ports associated with an Emergency Address/Location."""

    uri = "Skype.Ncs/ports"

    def get(self, chassisId: str, portId: str) -> dict:
        """
        Get a Port. Ports have no ID, the `chassisId` & `portId` strings are used as the identifier.

        Args:
            chassisId (str): The chassis ID of the Port to retrieve.
            portId (str): The port ID of the Port to retrieve.

        Returns:
            dict: A dictionary containing the Port.
        """
        return self._get(
            self.url("query"), params={"chassisId": chassisId, "portId": portId}
        )

    def list(self, locationId: str = None) -> Iterator[dict]:
        """
        Get a list of Ports.

        Args:
            locationId (str, optional): Filter list by location ID the Ports belong to. Defaults to `None`.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the Ports.
        """
        params = {}
        if locationId:
            params["locationId"] = locationId

        return self._get(self.url("filters"), params=params)

    def create(self, payload: dict) -> None:
        """
        Create a Port. Both `create` & `update` are `PUT` operations.
        Will overwrite an existing Port if it already exists.

        Ports are different from the other network endpoints. They use the traditional JSON payload.

        Args:
            payload (dict): The payload to create the Port with.
                ```
                {
                    "locationId": "0",
                    "chassisId": "00-00-00-00-99-99",
                    "portId": "99",
                    "description": "port 99",
                }
                ```

        Returns:
            None: Unlike most create operations, due to being a PUT
        """
        self.session.put(self.url(), json=payload)

    def update(self, chassisId: str, portId: str, payload: dict) -> None:
        """
        Update a Port. Both `create` & `update` are `PUT` operations.
        Will create the Port if it does not exist.

        Args:
            chassisId (str): The chassis ID of the Port to update.
            portId (str): The port ID of the Port to update.
            payload (dict): The payload to update the Port with.
                ```
                {
                    "locationId": "1",
                    "chassisId": "00-00-00-00-99-99",
                    "portId": "99",
                    "description": "port 99",
                }
                ```
        """
        if "chassisId" not in payload:
            payload["chassisId"] = chassisId
        if "portId" not in payload:
            payload["portId"] = portId

        self.session.put(self.url(), json=payload)

    def delete(self, chassisId: str, portId: str) -> None:
        """
        Delete a Port.

        Args:
            chassisId (str): The chassis ID of the Port to delete.
            portId (str): The port ID of the Port to delete.
        """
        self.session.delete(
            self.url("query"), params={"chassisId": chassisId, "portId": portId}
        )


class WirelessAccessPoints(CRUDEndpoint):
    """Wireless Access Points associated with an Emergency Address/Location."""

    uri = "Skype.Ncs/wirelessAccessPoints"

    def get(self, bssid: str) -> dict:
        """
        Get a Wireless Access Point. WAPs have no ID, the `bssid` string is used as the identifier.

        Args:
            bssid (str): The bssid of the WAP to retrieve.

        Returns:
            dict: A dictionary containing the WAP.
        """
        return self._get(self.url(bssid))

    def list(self, locationId: str = None) -> Iterator[dict]:
        """
        Get a list of Wireless Access Points.

        Args:
            locationId (str, optional): Filter list by location ID the WAPs belong to. Defaults to `None`.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the WAPs.
        """
        params = {}
        if locationId:
            params["locationId"] = locationId

        return self._get(self.url("filters"), params=params)

    def create(self, payload: dict) -> None:
        """
        Create a Wireless Access Point. Both `create` & `update` are `PUT` operations.
        Will overwrite an existing WAP if it already exists.

        Args:
            payload (dict): The payload to create the WAP with.
                ```
                {
                    "locationId": "0",
                    "bssid": "00-00-00-00-99-99",
                    "description": "wap 99",
                }
                ```

        Returns:
            None: Unlike most create operations, due to being a PUT
        """
        self.session.put(self.url(payload["bssid"]), params=payload)

    def update(self, bssid: str, payload: dict) -> None:
        """
        Update a Wireless Access Point. Both `create` & `update` are `PUT` operations.
        Will create the WAP if it does not exist.

        Args:
            bssid (str): The bssid of the WAP to update.
            payload (dict): The payload to update the WAP with.
                ```
                {
                    "locationId": "1",
                    "chassisId": "00-00-00-00-99-99",
                    "description": "wap 99",
                }
                ```
        """
        self.session.put(self.url(bssid), params=payload)

    def delete(self, bssid: str) -> None:
        """
        Delete a Wireless Access Point.

        Args:
            bssid (str): The bssid of the WAP to delete.
        """
        self.session.delete(self.url(bssid))


class TrustedIPs(CRUDEndpoint):
    """Trusted IPs for location based routing."""

    uri = "Skype.Policy/configurations/TenantTrustedIPAddress"

    def get(self, ip: str) -> dict:
        """
        Get a Trusted IP. Trusted IPs have no ID, the `Identity`/`IP Address` string is used as the identifier.

        Args:
            ip (str): The trusted IP to retrieve.

        Returns:
            dict: A dictionary containing the trusted IP.
        """
        return self._get(self.url(f"configuration/{ip}"))

    def list(self) -> Iterator[dict]:
        """
        Get a list of trusted ips.

        Returns:
            Iterator[dict]: An iterator of dictionaries representing the trusted ips.
        """
        return self._get(self.url())

    def create(self, payload: dict) -> dict:
        """
        Create a Trusted IP.

        Args:
            payload (dict): The payload to create the trusted IP with.
                ```
                {
                    "Identity": "1.1.1.1",
                    "Description": "Test trusted IP",
                    "MaskBits": 32,
                }
                ```

        Returns:
            dict: A dictionary containing the trusted IP.
        """
        self.session.post(self.url(), json=payload)

    def update(self, ip: str, payload: dict) -> None:
        """
        Update a trusted ip.

        Args:
            ip (str): The trusted ip to update.
            payload (dict): The payload to update the trusted ip with.
                ```
                {
                    "Identity": "1.1.1.1",
                    "Description": "Home office",
                    "MaskBits": 32
                }
                ```
        """
        self.session.put(self.url(f"configuration/{ip}"), json=payload)

    def delete(self, ip: str) -> None:
        """
        Delete a Trusted IP.

        Args:
            ip (str): The ip to delete.
        """
        self.session.delete(self.url(f"configuration/{ip}"))


class Regions(CRUDEndpoint):
    """Network regions are a collection of network sites."""

    uri = "Skype.Policy/configurations/TenantNetworkRegion"

    def get(self, name: str) -> dict:
        """
        Get a network region.
        They have no ID, the `name`\`Identity` string is used as the identifier.
        Args:
            name (str): The name of the network region.
        Returns:
            dict: A dictionary containing the network region.
        """
        return self._get(self.url(f"/configuration/{name}"))

    def list(self) -> Iterator[dict]:
        """
        Get a list of network regions.
        Returns:
            Iterator[dict]: An iterator of dictionaries representing the network regions.
        """
        return self._get(self.url())

    def create(self, payload: dict) -> None:
        """
        Create a network site.
        Args:
            payload (dict):
                ```
                {
                    "Identity": "Test4"
                }
                ```
        Returns:
            None: Unlike most create operations
        """
        self.session.post(self.url(), json=payload)

    def update(self) -> NotImplementedError:
        """
        Update a network region is **NOT** allowed.
        """
        raise NotImplementedError("Updating a network region is not allowed.")

    def delete(self, name: str) -> None:
        """
        Delete a network region.
        Args:
            name (str): The name of the network region.
        """
        self.session.delete(self.url(f"/configuration/{name}"))


class Sites(CRUDEndpoint):
    """Network sites are a collection of subnets and policies."""

    uri = "Skype.Policy/configurations/TenantNetworkSite"

    def get(self, name: str, include_subnets: bool = False) -> dict:
        """
        Get a network site.
        They have no ID, the `name`\`Identity` string is used as the identifier.
        Args:
            name (str): The name of the network site.
        Returns:
            dict: A dictionary containing the network site.
        """
        params = {}
        if include_subnets:
            params["ExpandSubnets"] = include_subnets

        return self._get(self.url(f"/configuration/{name}"), params=params)

    def list(self, include_subnets: bool = False) -> Iterator[dict]:
        """
        Get a list of network sites.
        Returns:
            Iterator[dict]: An iterator of dictionaries representing the network sites.
        """
        params = {}
        if include_subnets:
            params["ExpandSubnets"] = include_subnets

        return self._get(self.url(), params=params)

    def create(self, payload: dict) -> None:
        """
        Create a network site.
        Args:
            payload (dict):
                ```
                {
                    "Identity": "Test Site",
                    "Description": "For testing",
                    "NetworkRegionID": "Region Name",
                    "EnableLocationBasedRouting": True,
                    "EmergencyCallingPolicy": "Calling Policy 1",
                    "EmergencyCallRoutingPolicy": "Routing Policy 1",
                    "NetworkRoamingPolicy": "Roaming Policy 1"
                }
                ```
        Returns:
            None: Unlike most create operations
        """
        self.session.post(self.url(), json=payload)

    def update(self, name: str, payload: dict) -> None:
        """
        Update a network site.
        Args:
            name (str): The name of the network site.
            payload (dict):
                ```
                {
                    "Description": "For testing",
                    "NetworkRegionID": "Region Name",
                    "EnableLocationBasedRouting": True,
                    "EmergencyCallingPolicy": "Calling Policy 1",
                    "EmergencyCallRoutingPolicy": "Routing Policy 1",
                    "NetworkRoamingPolicy": "Roaming Policy 1"
                }
                ```
        """
        self.session.put(self.url(f"/configuration/{name}"), json=payload)

    def delete(self, name: str) -> None:
        """
        Delete a network site.
        Args:
            name (str): The name of the network site.
        """
        self.session.delete(self.url(f"/configuration/{name}"))


class SiteSubnets(CRUDEndpoint):
    """
    Subnets associated with a **network site.**
    Different than the subnets under Emergency Address/Location.
    """

    uri = "Skype.Policy/configurations/TenantNetworkSubnet"

    def get(self, name: str) -> dict:
        """
        Get a network site subnet.
        They have no ID, the `name`\`Identity` string is used as the identifier.
        Args:
            name (str): The name of the network site.
        Returns:
            dict: A dictionary containing the network site subnet.
        """
        return self._get(self.url(f"/configuration/{name}"))

    def list(self) -> Iterator[dict]:
        """
        Get a list of network sites subnets.
        Returns:
            Iterator[dict]: An iterator of dictionaries representing the network sites subnets.
        """
        return self._get(self.url())

    def create(self, payload: dict) -> None:
        """
        Create a network site subnet.
        Args:
            payload (dict):
                ```
                {
                    "NetworkSiteID": "Network Site Name",
                    "Identity": "10.0.1.0",
                    "SubnetID": "10.0.1.0",
                    "MaskBits": "24",
                    "Description": "For testing"
                }
                ```
        Returns:
            None: Unlike most create operations
        """
        self.session.post(self.url(), json=payload)

    def update(self, name: str, payload: dict) -> None:
        """
        Update a network site subnet.
        Args:
            name (str): The name of the network site subnet.
            payload (dict):
                ```
                {
                    "NetworkSiteID": "Network Site Name",
                    "MaskBits": "30",
                    "Description": "For testing updated"
                }
                ```
        """
        self.session.put(self.url(f"/configuration/{name}"), json=payload)

    def delete(self, name: str) -> None:
        """
        Delete a network site subnet.
        Args:
            name (str): The name of the network site subnet.
        """
        self.session.delete(self.url(f"/configuration/{name}"))


class RoamingPolicies(CRUDEndpoint):
    """Network roaming policies get assigned to network sites."""

    uri = "Skype.Policy/configurations/TeamsNetworkRoamingPolicy"

    def get(self, name: str) -> dict:
        """
        Get a network roaming policy.
        They have no ID, the `name`\`Identity` string is used as the identifier.
        Args:
            name (str): The name of the network roaming policy.
        Returns:
            dict: A dictionary containing the network roaming policy.
        """
        return self._get(self.url(f"/configuration/{name}"))

    def list(self) -> Iterator[dict]:
        """
        Get a list of network roaming policies.
        Returns:
            Iterator[dict]: An iterator of dictionaries representing the network roaming policies.
        """
        return self._get(self.url())

    def create(self, payload: dict) -> None:
        """
        Create a network roaming policy.
        Args:
            payload (dict):
                ```
                {
                    "Identity": "Roaming Policy Name",
                    "Description": "For testing",
                    "AllowIPVideo": True,
                    "MediaBitRateKb": 50000
                }
                ```
        Returns:
            None: Unlike most create operations
        """
        self.session.post(self.url(), json=payload)

    def update(self, name: str, payload: dict) -> None:
        """
        Update a network roaming policy.
        Args:
            payload (dict):
                ```
                {
                    "Description": "For testing updated",
                    "AllowIPVideo": True,
                    "MediaBitRateKb": 50000
                }
                ```
        """
        self.session.put(self.url(f"/configuration/{name}"), json=payload)

    def delete(self, name: str) -> None:
        """
        Delete a network roaming policy.
        Args:
            name (str): The name of the network roaming policy.
        """
        self.session.delete(self.url(f"/configuration/{name}"))
