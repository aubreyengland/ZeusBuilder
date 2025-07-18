import logging
from zeus import registry as reg
from .shared import MsTeamsBulkSvc
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from ..msteams_models import MsTeamsSubnet
from ..msteams_simple import MsTeamsSimpleClient

log = logging.getLogger(__name__)


class MsTeamsSubnetValidation:
    """
    Shared validation class for MS Teams Subnet Create and Update services.
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
        if len(payload["subnet"]) < 1:
            raise ZeusBulkOpFailed("Subnet is required")
        if len(payload["description"]) < 1:
            raise ZeusBulkOpFailed("Description is required")

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload


@reg.bulk_service("msteams", "subnets", "CREATE")
class MsTeamsSubnetCreateSvc(MsTeamsBulkSvc, MsTeamsSubnetValidation):

    def run(self):
        payload = {
            "subnet": self.model.subnet,
            "description": self.model.description,
        }
        payload = self.validate(payload)
        self.lookup.subnet(self.model.subnet, raise_if_exists=True)
        parent_location = self.lookup.emergency_location(
            self.model.addressDescription, self.model.locationName
        )
        payload["locationId"] = parent_location["id"]
        self.client.subnets.create(payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "subnets", "UPDATE")
class MsTeamsSubnetUpdateSvc(MsTeamsBulkSvc, MsTeamsSubnetValidation):

    def run(self):
        payload = {
            "subnet": self.model.subnet,
            "description": self.model.description,
        }
        payload = self.validate(payload)
        self.current = self.lookup.subnet(self.model.subnet)
        parent_location = self.lookup.emergency_location(
            self.model.addressDescription, self.model.locationName
        )
        payload["locationId"] = parent_location["id"]
        self.client.subnets.update(payload["subnet"], payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "subnets", "DELETE")
class MsTeamsSubnetDeleteSvc(MsTeamsBulkSvc):

    def run(self):
        if len(self.model.subnet) < 1:
            raise ZeusBulkOpFailed("Subnet is required")
        self.current = self.lookup.subnet(self.model.subnet)
        self.client.subnets.delete(self.current["subnet"])


@reg.browse_service("msteams", "subnets")
class MsTeamsSubnetBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = MsTeamsSubnetModelBuilder(self.client)
        for resp in self.client.subnets.list():
            model = builder.build_model(resp)
            rows.append(model)

        return rows


@reg.export_service("msteams", "subnets")
class MsTeamsSubnetExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsSubnet.schema()["data_type"]
        builder = MsTeamsSubnetModelBuilder(self.client)

        for resp in self.client.subnets.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("subnet", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class MsTeamsSubnetModelBuilder:
    """
    Shared model builder class for MS Teams Subnet
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

        model = MsTeamsSubnet.safe_build(
            subnet=resp["subnet"] or "",
            description=resp["description"] or "",
            addressDescription=parent_location.get("description", ""),
            locationName=parent_location.get("additionalInfo", ""),
        )

        return model
