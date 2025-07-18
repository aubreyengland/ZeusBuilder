import logging
from zeus import registry as reg
from .shared import MsTeamsBulkSvc
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from ..msteams_models import MsTeamsTrustedIp

log = logging.getLogger(__name__)


class MsTeamsTrustedIpValidation:
    """
    Shared validation class for MS Teams Trusted IP Create and Update services.
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
        if len(payload["Identity"]) < 1:
            raise ZeusBulkOpFailed("IP Address is required")
        if len(payload["MaskBits"]) < 1:
            raise ZeusBulkOpFailed("Network Range is required")

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload


@reg.bulk_service("msteams", "trusted_ips", "CREATE")
class MsTeamsTrustedIpCreateSvc(MsTeamsBulkSvc, MsTeamsTrustedIpValidation):

    def run(self):
        payload = {
            "Identity": self.model.ipAddress,
            "Description": self.model.description,
            "MaskBits": self.model.networkRange,
        }
        payload = self.validate(payload)
        self.lookup.trusted_ip(self.model.ipAddress, raise_if_exists=True)
        self.client.trusted_ips.create(payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "trusted_ips", "UPDATE")
class MsTeamsTrustedIpUpdateSvc(MsTeamsBulkSvc, MsTeamsTrustedIpValidation):

    def run(self):
        payload = {
            "Identity": self.model.ipAddress,
            "Description": self.model.description,
            "MaskBits": self.model.networkRange,
        }
        payload = self.validate(payload)
        self.lookup.trusted_ip(self.model.ipAddress)
        self.client.trusted_ips.update(payload["Identity"], payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "trusted_ips", "DELETE")
class MsTeamsTrustedIpDeleteSvc(MsTeamsBulkSvc):

    def run(self):
        if len(self.model.ipAddress) < 1:
            raise ZeusBulkOpFailed("IP Address is required")
        self.current = self.lookup.trusted_ip(self.model.ipAddress)
        self.client.trusted_ips.delete(self.current["Identity"])


@reg.browse_service("msteams", "trusted_ips")
class MsTeamsTrustedIpBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        for resp in self.client.trusted_ips.list():
            model = MsTeamsTrustedIp.safe_build(
                ipAddress=resp["Identity"] or "",
                networkRange=resp["MaskBits"] or "",
                description=resp["Description"] or "",
            )
            rows.append(model)

        return rows


@reg.export_service("msteams", "trusted_ips")
class MsTeamsTrustedIpExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsTrustedIp.schema()["data_type"]

        for resp in self.client.trusted_ips.list():

            try:
                model = MsTeamsTrustedIp.safe_build(
                    ipAddress=resp["Identity"] or "",
                    networkRange=resp["MaskBits"] or "",
                    description=resp["Description"] or "",
                )
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("Identity", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}
