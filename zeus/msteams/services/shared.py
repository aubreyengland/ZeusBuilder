import logging
from typing import Union
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BulkSvc, BulkTask, SvcClient
from ..msteams_simple import MsTeamsSimpleClient, MsTeamsServerFault

log = logging.getLogger(__name__)


class MsTeamsBulkSvc(BulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.client: MsTeamsSimpleClient = client
        self.lookup = MsTeamsLookup(client)


class MsTeamsBulkTask(BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: MsTeamsBulkSvc = svc


class MsTeamsSvcClient(SvcClient):
    tool = "msteams"
    client_cls = MsTeamsSimpleClient


class MsTeamsLookup:
    def __init__(self, client):
        self.client: MsTeamsSimpleClient = client

    def emergency_address(
        self,
        lookup_addr: Union[str, dict],
        raise_if_multiple: bool = True,
        raise_if_exists: bool = False,
    ) -> dict:
        """
        Lookup emergency address by either description `str` or the whole address `dict`.
        This flexibility is provided because MS does not require any fields to be unique
        and some services will only have the address description to lookup with.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Use `raise_if_multiple=False` on `DELETE` operations where it's not as important to be specific.

        Args:
        - lookup_addr (str or dict): Either the address description or the whole address dictionary.
        - raise_if_multiple (bool): Raises an error if multiple matches are found.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching emergency address,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching emergency address is found,
            if multiple matches are found when `raise_if_multiple` is True,
            if a match is found when `raise_if_exists` is True.
        """

        def lookup_str(d: dict):
            return (
                f"{d['description'] or ''} {d['companyName'] or ''} {d['houseNumber'] or ''} "
                f"{d['houseNumberSuffix'] or ''} {d['preDirectional'] or ''} {d['streetName'] or ''} "
                f"{d['streetSuffix'] or ''} {d['postDirectional'] or ''} {d['cityOrTown'] or ''} "
                f"{d['cityOrTownAlias'] or ''} {d['stateOrProvince'] or ''} {d['postalOrZipCode'] or ''} "
                f"{d['countyOrDistrict'] or ''} {d['country'] or ''} {d['elin'] or ''} {d['companyId'] or ''}".replace(
                    " ", ""
                )
            )

        matches = []
        looking_for = lookup_addr
        if isinstance(lookup_addr, str):
            for item in self.client.emergency_addresses.list(
                lookup_addr, populateUsersAndNumbers=True
            ):
                if looking_for.lower() == item["description"].lower():
                    matches.append(item)
        elif isinstance(lookup_addr, dict):
            for item in self.client.emergency_addresses.list(
                lookup_addr["description"], populateUsersAndNumbers=True
            ):
                looking_for = lookup_str(looking_for)
                if looking_for == lookup_str(item):
                    matches.append(item)
        else:
            raise ZeusBulkOpFailed(f"Invalid lookup_addr type '{type(lookup_addr)}'")

        if len(matches) == 0:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Emergency Address '{looking_for}' does not exist")
        elif len(matches) == 1:
            if raise_if_exists:
                raise ZeusBulkOpFailed(f"Emergency Address '{looking_for}' already exists")
            return matches[0]
        else:
            if raise_if_exists:
                raise ZeusBulkOpFailed(f"Emergency Address '{looking_for}' already exists")
            if raise_if_multiple:
                raise ZeusBulkOpFailed(
                    f"Multiple matches found for Emergency Address '{looking_for}'"
                )
            return matches[0]

    def emergency_location(
        self,
        address_description: str,
        location_name: str,
        raise_if_multiple: bool = True,
        raise_if_exists: bool = False,
    ) -> dict:
        """
        Lookup emergency location by `address_description` and `location_name`.
        It is valid for `location_name` to be an empty string when looking up default locations.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Args:
        - address_description (str): The address description the location belongs to.
        - location_name (str): The name of the location.
        - raise_if_multiple (bool): Raises an error if multiple matches are found.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching emergency location,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching emergency location is found,
            if multiple matches are found when `raise_if_multiple` is True,
            if a match is found when `raise_if_exists` is True.
        """
        matches = []
        for item in self.client.emergency_locations.list(
            description=address_description,
            includeDefault=True,
            populateUsersAndNumbers=True,
        ):
            if item["additionalInfo"] is None:
                item["additionalInfo"] = ""  # Normalize None to empty string
            if location_name.lower() == item["additionalInfo"].lower():
                matches.append(item)

        if len(matches) == 0:
            if raise_if_exists:
                return {}
            if location_name == "":
                raise ZeusBulkOpFailed(
                    f"Emergency Address '{address_description}' does not exist"
                )
            else:
                raise ZeusBulkOpFailed(
                    f"Emergency Location '{location_name}' does not exist at '{address_description}'"
                )
        elif len(matches) == 1:
            if raise_if_exists:
                raise ZeusBulkOpFailed(
                    f"Emergency Location '{location_name}' already exists at address '{matches[0]['description']}'"
                )
            return matches[0]
        else:
            if raise_if_exists:
                raise ZeusBulkOpFailed(
                    f"Emergency Location '{location_name}' already exists at address '{matches[0]['description']}'"
                )
            if raise_if_multiple:
                raise ZeusBulkOpFailed(
                    f"Multiple matches found for Emergency Location '{location_name}'"
                )
            return matches[0]

    def subnet(self, subnet: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup subnet by `subnet`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Args:
        - subnet (str): The subnet to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching subnet,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching subnet is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.subnets.get(subnet)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Subnet '{subnet}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Subnet '{subnet}' already exists")

        return resp

    def switch(self, chassis_id: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup switch by `chassis_id`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Args:
        - chassis_id (str): The switch chassis ID to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching switch,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching switch is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.switches.get(chassis_id)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Switch '{chassis_id}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Switch '{chassis_id}' already exists")

        return resp

    def port(self, chassis_id: str, port_id: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup port by `chassis_id` and `port_id`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Args:
        - chassis_id (str): The port chassis ID to lookup.
        - port_id (str): The port ID to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching port,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching port is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.ports.get(chassis_id, port_id)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(
                f"Port '{port_id}' on chassis '{chassis_id}' does not exist"
            )

        if raise_if_exists:
            raise ZeusBulkOpFailed(
                f"Port '{port_id}' on chassis '{chassis_id}' already exists"
            )

        return resp

    def wap(self, bssid: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup wireless access point by `bssid`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Args:
        - bssid (str): The BSSID of the WAP to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching wap,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching wap is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.waps.get(bssid)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Wireless Access Point '{bssid}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Wireless Access Point '{bssid}' already exists")

        return resp

    def trusted_ip(self, ip_address: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup trusted IP based on `ip_address`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates, because the API does not.

        Args:
        - ip_address (str): The ip address of the trusted IP to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching trusted ip,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching trusted ip is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.trusted_ips.get(ip_address)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Trusted IP '{ip_address}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Trusted IP '{ip_address}' already exists")

        return resp

    def emergency_calling_policy(self, name: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup Emergency Calling Policy based on `name`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates.

        Args:
        - name (str): The name/identity of the emergency calling policy to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching emergency calling policy,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching emergency calling policy is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.emergency_calling_policies.get(name)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Emergency Calling Policy '{name}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Emergency Calling Policy '{name}' already exists")

        return resp

    def network_site(self, name: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup Network Site based on `name`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates.

        Args:
        - name (str): The name/identity of the network site to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching network site,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching network site is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.network_sites.get(name, include_subnets=True)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Network Site '{name}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Network Site '{name}' already exists")

        return resp

    def network_region(self, name: str, raise_if_exists: bool = False) -> dict:
        """
        Lookup Network Region based on `name`.

        Use `raise_if_exists=True` on `CREATE` operations to prevent duplicates.

        Args:
        - name (str): The name/identity of the network region to lookup.
        - raise_if_exists (bool): Raises an error if a match is found.

        Returns:
        - dict: A dictionary of the matching network region,
            or an empty dictionary if no match is found and `raise_if_exists` is True.

        Raises:
        - ZeusBulkOpFailed: If no matching network region is found,
            if a match is found when `raise_if_exists` is True.
        """
        try:
            resp = self.client.network_regions.get(name)
        except MsTeamsServerFault:
            if raise_if_exists:
                return {}
            raise ZeusBulkOpFailed(f"Network Region '{name}' does not exist")

        if raise_if_exists:
            raise ZeusBulkOpFailed(f"Network Region '{name}' already exists")

        return resp


class MsTeamsEmergencyLocationDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, location, **kwargs):
        super().__init__(svc, **kwargs)
        self.location: dict = location
        self.was_deleted: bool = False

    def run(self):
        self.client.emergency_locations.delete(self.location["id"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            payload = {
                "civicAddressId": self.location["civicAddressId"],
                "additionalInfo": self.location["additionalInfo"],
                "elin": self.location["elin"],
            }
            self.client.emergency_locations.create(payload)


class MsTeamsSubnetDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, subnet, **kwargs):
        super().__init__(svc, **kwargs)
        self.subnet: dict = subnet
        self.was_deleted: bool = False

    def run(self):
        self.client.subnets.delete(self.subnet["subnet"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            self.client.subnets.create(self.subnet)


class MsTeamsSwitchDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, switch, **kwargs):
        super().__init__(svc, **kwargs)
        self.switch: dict = switch
        self.was_deleted: bool = False

    def run(self):
        self.client.switches.delete(self.switch["chassisId"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            self.client.switches.create(self.switch)


class MsTeamsPortDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, port, **kwargs):
        super().__init__(svc, **kwargs)
        self.port: dict = port
        self.was_deleted: bool = False

    def run(self):
        self.client.ports.delete(self.port["chassisId"], self.port["portId"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            self.client.ports.create(self.port)


class MsTeamsWAPDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, wap, **kwargs):
        super().__init__(svc, **kwargs)
        self.wap: dict = wap
        self.was_deleted: bool = False

    def run(self):
        self.client.waps.delete(self.wap["bssid"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            self.client.waps.create(self.wap)


class MsTeamsNetworkRegionCreateTask(MsTeamsBulkTask):
    def __init__(self, svc, network_region, **kwargs):
        super().__init__(svc, **kwargs)
        self.network_region: dict = network_region
        self.was_created: bool = False

    def run(self):
        self.client.network_regions.create(self.network_region)
        self.was_created = True

    def rollback(self):
        if self.was_created:
            self.client.network_regions.delete(self.network_region["Identity"])


class MsTeamsNetworkSiteCreateTask(MsTeamsBulkTask):
    def __init__(self, svc, network_site, **kwargs):
        super().__init__(svc, **kwargs)
        self.network_site: dict = network_site
        self.was_created: bool = False

    def run(self):
        self.client.network_sites.create(self.network_site)
        self.was_created = True

    def rollback(self):
        if self.was_created:
            self.client.network_sites.delete(self.network_site["Identity"])


class MsTeamsNetworkSiteUpdateTask(MsTeamsBulkTask):
    def __init__(self, svc, network_site, **kwargs):
        super().__init__(svc, **kwargs)
        self.network_site: dict = network_site
        self.was_updated: bool = False

    def run(self):
        self.client.network_sites.update(self.network_site["Identity"], self.network_site)
        self.was_updated = True

    def rollback(self):
        if self.was_updated:
            # Remove SiteAddress from network site if present, causes an error and is not needed
            if "SiteAddress" in self.svc.current:
                self.svc.current.pop("SiteAddress")
            self.client.network_sites.update(self.svc.current["Identity"], self.svc.current)


class MsTeamsNetworkSiteDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, network_site, **kwargs):
        super().__init__(svc, **kwargs)
        self.network_site: dict = network_site
        self.was_deleted: bool = False

    def run(self):
        self.client.network_sites.delete(self.network_site["Identity"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            self.client.network_sites.create(self.network_site)


class MsTeamsNetworkSiteSubnetCreateTask(MsTeamsBulkTask):
    def __init__(self, svc, subnet, **kwargs):
        super().__init__(svc, **kwargs)
        self.subnet: dict = subnet
        self.was_created: bool = False

    def run(self):
        self.client.network_site_subnets.create(self.subnet)
        self.was_created = True

    def rollback(self):
        if self.was_created:
            self.client.network_site_subnets.delete(self.subnet["Identity"])


class MsTeamsNetworkSiteSubnetUpdateTask(MsTeamsBulkTask):
    def __init__(self, svc, current_subnet, new_subnet, **kwargs):
        super().__init__(svc, **kwargs)
        self.current_subnet: dict = current_subnet
        self.new_subnet: dict = new_subnet
        self.was_updated: bool = False

    def run(self):
        self.client.network_site_subnets.update(
            self.new_subnet["Identity"], self.new_subnet
        )
        self.was_updated = True

    def rollback(self):
        if self.was_updated:
            # Add Identity to subnet (which is identical to SubnetID) if not present
            if "Identity" not in self.current_subnet:
                self.current_subnet["Identity"] = self.current_subnet["SubnetID"]
            self.client.network_site_subnets.update(
                self.current_subnet["Identity"], self.current_subnet
            )


class MsTeamsNetworkSiteSubnetDeleteTask(MsTeamsBulkTask):
    def __init__(self, svc, subnet, **kwargs):
        super().__init__(svc, **kwargs)
        self.subnet: dict = subnet
        self.was_deleted: bool = False

    def run(self):
        self.client.network_site_subnets.delete(self.subnet["SubnetID"])
        self.was_deleted = True

    def rollback(self):
        if self.was_deleted:
            # Add Identity to subnet (which is identical to SubnetID) if not present
            if "Identity" not in self.subnet:
                self.subnet["Identity"] = self.subnet["SubnetID"]
            self.client.network_site_subnets.create(self.subnet)
