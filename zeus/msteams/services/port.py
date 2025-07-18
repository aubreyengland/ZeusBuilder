import logging
from zeus import registry as reg
from .shared import MsTeamsBulkSvc
from zeus.exceptions import ZeusBulkOpFailed
from ..msteams_models import MsTeamsPort
from zeus.services import BrowseSvc, ExportSvc
from ..msteams_simple import MsTeamsSimpleClient

log = logging.getLogger(__name__)


class MsTeamsPortValidation:
    """
    Shared validation class for MS Teams Port Create and Update services.
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
        if len(payload["portId"]) < 1:
            raise ZeusBulkOpFailed("Port is required")
        if len(payload["chassisId"]) < 1:
            raise ZeusBulkOpFailed("Chassis ID is required")
        if len(payload["description"]) < 1:
            raise ZeusBulkOpFailed("Description is required")

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload


@reg.bulk_service("msteams", "ports", "CREATE")
class MsTeamsPortCreateSvc(MsTeamsBulkSvc, MsTeamsPortValidation):

    def run(self):
        payload = {
            "chassisId": self.model.chassisId,
            "portId": self.model.port,
            "description": self.model.description,
        }
        payload = self.validate(payload)
        self.lookup.port(self.model.chassisId, self.model.port, raise_if_exists=True)
        parent_location = self.lookup.emergency_location(
            self.model.addressDescription, self.model.locationName
        )
        payload["locationId"] = parent_location["id"]
        self.client.ports.create(payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "ports", "UPDATE")
class MsTeamsPortUpdateSvc(MsTeamsBulkSvc, MsTeamsPortValidation):

    def run(self):
        payload = {
            "chassisId": self.model.chassisId,
            "portId": self.model.port,
            "description": self.model.description,
        }
        payload = self.validate(payload)
        self.current = self.lookup.port(self.model.chassisId, self.model.port)
        parent_location = self.lookup.emergency_location(
            self.model.addressDescription, self.model.locationName
        )
        payload["locationId"] = parent_location["id"]
        self.client.ports.update(payload["chassisId"], payload["portId"], payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "ports", "DELETE")
class MsTeamsPortDeleteSvc(MsTeamsBulkSvc):

    def run(self):
        if len(self.model.chassisId) < 1:
            raise ZeusBulkOpFailed("Chassis ID is required")
        if len(self.model.port) < 1:
            raise ZeusBulkOpFailed("Port is required")
        self.current = self.lookup.port(self.model.chassisId, self.model.port)
        self.client.ports.delete(self.current["chassisId"], self.current["portId"])


@reg.browse_service("msteams", "ports")
class MsTeamsPortBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = MsTeamsPortModelBuilder(self.client)
        for resp in self.client.ports.list():
            model = builder.build_model(resp)
            rows.append(model)

        return rows


@reg.export_service("msteams", "ports")
class MsTeamsPortExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsPort.schema()["data_type"]
        builder = MsTeamsPortModelBuilder(self.client)

        for resp in self.client.ports.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("portId", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class MsTeamsPortModelBuilder:
    """
    Shared model builder class for MS Teams Port
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
        model = MsTeamsPort.safe_build(
            chassisId=resp["chassisId"] or "",
            port=resp["portId"] or "",
            description=resp["description"] or "",
            addressDescription=parent_location.get("description", ""),
            locationName=parent_location.get("additionalInfo", ""),
        )

        return model
