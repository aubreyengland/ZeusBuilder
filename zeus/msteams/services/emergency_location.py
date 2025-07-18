import logging
import re

from .shared import (
    MsTeamsBulkSvc,
    MsTeamsSubnetDeleteTask,
    MsTeamsSwitchDeleteTask,
    MsTeamsPortDeleteTask,
    MsTeamsWAPDeleteTask,
    MsTeamsNetworkSiteCreateTask,
)
from zeus import registry as reg
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from ..msteams_models import MsTeamsEmergencyLocation
from ..msteams_simple import MsTeamsSimpleClient, MsTeamsServerFault

log = logging.getLogger(__name__)


class MsTeamsEmergencyLocationValidation:
    """
    Shared validation class for MS Teams Emergency Location Create and Update services.
    """

    @staticmethod
    def validate(action, payload):
        """
        Validates the payload. Nulls empty strings on optional fields.

        Args:
            payload (dict): The payload to validate.

        Raises:
            ZeusBulkOpFailed: If any required fields are missing or if they are not in the correct format.

        Returns:
            dict: The validated payload.
        """
        # Validate required fields
        if len(payload["additionalInfo"]) < 1:
            raise ZeusBulkOpFailed("Name is required")
        elif len(payload["additionalInfo"]) > 32:
            raise ZeusBulkOpFailed("Name must be 32 characters or less")

        # Apply same name restictions that Network Sites have in order to keep them consistent
        # Since there is a Create Network Site column
        if action == "CREATE" and not re.match(
            r"^[a-zA-Z0-9_. ]+$", payload["additionalInfo"]
        ):
            raise ZeusBulkOpFailed(
                "Name can only contain letters, digits, '_', '.', and spaces"
            )

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload


@reg.bulk_service("msteams", "emergency_locations", "CREATE")
class MsTeamsEmergencyLocationCreateSvc(MsTeamsBulkSvc, MsTeamsEmergencyLocationValidation):
    def run(self):
        payload = {
            "additionalInfo": self.model.name,
            "elin": self.model.elin,
        }
        payload = self.validate(self.model.action, payload)
        self.lookup.emergency_location(
            self.model.addressDescription, self.model.name, raise_if_exists=True
        )
        parent_address = self.lookup.emergency_address(self.model.addressDescription)
        payload["civicAddressId"] = parent_address["id"]
        self.current = self.client.emergency_locations.create(payload)

        if self.model.createNetworkSite:
            network_site_payload = {
                "Identity": self.model.name,
                "Description": f"Created from Emergency Location '{self.model.name}'",
            }
            try:
                task = MsTeamsNetworkSiteCreateTask(self, network_site_payload)
                task.run()
                self.rollback_tasks.append(task)
            except MsTeamsServerFault as e:
                if "already exists" in e.message:
                    pass
                else:
                    raise e
            except Exception as e:
                raise e

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "emergency_locations", "UPDATE")
class MsTeamsEmergencyLocationUpdateSvc(MsTeamsBulkSvc, MsTeamsEmergencyLocationValidation):
    def run(self):
        payload = {
            "additionalInfo": self.model.newName if self.model.newName else self.model.name,
            "elin": self.model.elin,
        }
        payload = self.validate(self.model.action, payload)
        if len(self.model.newName) > 0:
            # check if a location with the new name already exists at the same address
            self.lookup.emergency_location(
                self.model.addressDescription, self.model.newName, raise_if_exists=True
            )
        self.current = self.lookup.emergency_location(
            self.model.addressDescription, self.model.name
        )
        payload["civicAddressId"] = self.current["civicAddressId"]
        self.client.emergency_locations.update(self.current["id"], payload)

        if self.model.createNetworkSite:
            network_site_payload = {
                "Identity": self.model.name,
                "Description": f"Created from Emergency Location '{self.model.name}'",
            }
            try:
                task = MsTeamsNetworkSiteCreateTask(self, network_site_payload)
                task.run()
                self.rollback_tasks.append(task)
            except MsTeamsServerFault as e:
                if "already exists" in e.message:
                    pass
                else:
                    raise e
            except Exception as e:
                raise e

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "emergency_locations", "DELETE")
class MsTeamsEmergencyLocationDeleteSvc(MsTeamsBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.subnets_to_remove: list[dict] = []
        self.switches_to_remove: list[dict] = []
        self.ports_to_remove: list[dict] = []
        self.waps_to_remove: list[dict] = []

    def run(self):
        if len(self.model.name) < 1:
            raise ZeusBulkOpFailed("Name is required")
        if len(self.model.addressDescription) < 1:
            raise ZeusBulkOpFailed("Address Description is required")
        self.current = self.lookup.emergency_location(
            self.model.addressDescription, self.model.name, raise_if_multiple=False
        )
        self.check_if_location_is_in_use()
        self.get_subnets_for_deletion()
        self.get_switches_for_deletion()
        self.get_ports_for_deletion()
        self.get_waps_for_deletion()
        self.delete_subnets()
        self.delete_switches()
        self.delete_ports()
        self.delete_waps()
        self.delete_location()

    def check_if_location_is_in_use(self):
        if (
            self.current["numberOfVoiceUsers"] > 0
            or self.current["numberOfTelephoneNumbers"] > 0
        ):
            raise ZeusBulkOpFailed(
                f"Failed to delete location because {self.current['numberOfVoiceUsers']}"
                f" users and {self.current['numberOfTelephoneNumbers']} phone numbers are assigned to it."
            )

    def get_subnets_for_deletion(self):
        for subnet in self.client.subnets.list():
            if subnet["locationId"] == self.current["id"]:
                self.subnets_to_remove.append(subnet)

    def get_switches_for_deletion(self):
        for switch in self.client.switches.list():
            if switch["locationId"] == self.current["id"]:
                self.switches_to_remove.append(switch)

    def get_ports_for_deletion(self):
        for port in self.client.ports.list():
            if port["locationId"] == self.current["id"]:
                self.ports_to_remove.append(port)

    def get_waps_for_deletion(self):
        for wap in self.client.waps.list():
            if wap["locationId"] == self.current["id"]:
                self.waps_to_remove.append(wap)

    def delete_subnets(self):
        for subnet in self.subnets_to_remove:
            task = MsTeamsSubnetDeleteTask(self, subnet)
            task.run()
            self.rollback_tasks.append(task)

    def delete_switches(self):
        for switch in self.switches_to_remove:
            task = MsTeamsSwitchDeleteTask(self, switch)
            task.run()
            self.rollback_tasks.append(task)

    def delete_ports(self):
        for port in self.ports_to_remove:
            task = MsTeamsPortDeleteTask(self, port)
            task.run()
            self.rollback_tasks.append(task)

    def delete_waps(self):
        for wap in self.waps_to_remove:
            task = MsTeamsWAPDeleteTask(self, wap)
            task.run()
            self.rollback_tasks.append(task)

    def delete_location(self):
        self.client.emergency_locations.delete(self.current["id"])


@reg.browse_service("msteams", "emergency_locations")
class MsTeamsEmergencyLocationBrowseSvc(BrowseSvc):

    def run(self):
        builder = MsTeamsEmergencyLocationModelBuilder(self.client)
        rows = [loc for loc in builder.build_dicts_for_browse()]
        return rows


@reg.export_service("msteams", "emergency_locations")
class MsTeamsEmergencyLocationExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsEmergencyLocation.schema()["data_type"]
        builder = MsTeamsEmergencyLocationModelBuilder(self.client)

        for resp in builder.get_emergency_locations():
            try:
                model = builder.build_model(resp)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("additionalInfo", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class MsTeamsEmergencyLocationModelBuilder:
    """
    Shared model builder class for MS Teams Emergency Location
    Browse and Export services.
    """

    def __init__(self, client):
        self.client: MsTeamsSimpleClient = client

    def get_emergency_locations(self):
        """Return list of emergency locations"""
        try:
            return list(self.client.emergency_locations.list(includeDefault=False))
        except MsTeamsServerFault:
            return []

    @staticmethod
    def build_model(resp):
        model = MsTeamsEmergencyLocation.safe_build(
            addressDescription=resp["description"],
            name=resp["additionalInfo"],
            elin=resp["elin"],
        )

        return model

    def build_dicts_for_browse(self):
        # Includes extra address fields for browse
        models = []
        for resp in self.get_emergency_locations():
            models.append(
                dict(
                    addressDescription=resp["description"] or "",
                    name=resp["additionalInfo"] or "",
                    elin=resp["elin"] or "",
                    houseNumber=resp["houseNumber"] or "",
                    houseNumberSuffix=resp["houseNumberSuffix"] or "",
                    preDirectional=resp["preDirectional"] or "",
                    streetName=resp["streetName"] or "",
                    streetSuffix=resp["streetSuffix"] or "",
                    postDirectional=resp["postDirectional"] or "",
                    cityOrTown=resp["cityOrTown"] or "",
                    stateOrProvince=resp["stateOrProvince"] or "",
                    postalOrZipCode=resp["postalOrZipCode"] or "",
                    country=resp["country"] or "",
                )
            )

        return models
