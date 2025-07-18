import logging
from zeus import registry as reg
from .shared import MsTeamsBulkSvc
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from ..msteams_simple import MsTeamsSimpleClient
from ..msteams_models import MsTeamsWirelessAccessPoint

log = logging.getLogger(__name__)


class MsTeamsWirelessAccessPointValidation:
    """
    Shared validation class for MS Teams WAP Create and Update services.
    """

    def validate(self, payload):
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
        if len(payload["bssid"]) < 1:
            raise ZeusBulkOpFailed("BSSID is required")
        if len(payload["description"]) < 1:
            raise ZeusBulkOpFailed("Description is required")

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload


@reg.bulk_service("msteams", "wireless_access_points", "CREATE")
class MsTeamsWirelessAccessPointCreateSvc(
    MsTeamsBulkSvc, MsTeamsWirelessAccessPointValidation
):
    def run(self):
        payload = {
            "bssid": self.model.bssid,
            "description": self.model.description,
        }
        payload = self.validate(payload)
        self.lookup.wap(self.model.bssid, raise_if_exists=True)
        parent_location = self.lookup.emergency_location(
            self.model.addressDescription, self.model.locationName
        )
        payload["locationId"] = parent_location["id"]
        self.client.waps.create(payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "wireless_access_points", "UPDATE")
class MsTeamsWirelessAccessPointUpdateSvc(
    MsTeamsBulkSvc, MsTeamsWirelessAccessPointValidation
):
    def run(self):
        payload = {
            "bssid": self.model.bssid,
            "description": self.model.description,
        }
        payload = self.validate(payload)
        self.current = self.lookup.wap(self.model.bssid)
        parent_location = self.lookup.emergency_location(
            self.model.addressDescription, self.model.locationName
        )
        payload["locationId"] = parent_location["id"]
        self.client.waps.update(payload["bssid"], payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "wireless_access_points", "DELETE")
class MsTeamsWirelessAccessPointDeleteSvc(MsTeamsBulkSvc):

    def run(self):
        if len(self.model.bssid) < 1:
            raise ZeusBulkOpFailed("BSSID is required")
        self.current = self.lookup.wap(self.model.bssid)
        self.client.waps.delete(self.current["bssid"])


@reg.browse_service("msteams", "wireless_access_points")
class MsTeamsWirelessAccessPointBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = MsTeamsWirelessAccessPointModelBuilder(self.client)

        for resp in self.client.waps.list():
            model = builder.build_model(resp)
            rows.append(model)

        return rows


@reg.export_service("msteams", "wireless_access_points")
class MsTeamsWirelessAccessPointExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsWirelessAccessPoint.schema()["data_type"]
        builder = MsTeamsWirelessAccessPointModelBuilder(self.client)

        for resp in self.client.waps.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("bssid", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class MsTeamsWirelessAccessPointModelBuilder:
    """
    Shared model builder class for MS Teams WAP
    Browse and Export services.
    """

    def __init__(self, client):
        self.client: MsTeamsSimpleClient = client
        self.locations_by_id = {}

    def get_parent_location(self, location_id):
        if location_id not in self.locations_by_id:
            try:
                self.locations_by_id[location_id] = self.client.emergency_locations.get(location_id)
            except Exception:
                # Ignore missing parent location
                self.locations_by_id[location_id] = {}

        return self.locations_by_id[location_id]

    def build_model(self, resp):
        parent_location = self.get_parent_location(resp["locationId"])

        model = MsTeamsWirelessAccessPoint.safe_build(
            bssid=resp["bssid"] or "",
            description=resp["description"] or "",
            addressDescription=parent_location.get("description", ""),
            locationName=parent_location.get("additionalInfo", ""),
        )

        return model
