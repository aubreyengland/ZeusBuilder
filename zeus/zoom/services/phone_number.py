import logging
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from zeus.zoom.zoom_models import ZoomPhoneNumber

log = logging.getLogger(__name__)


@reg.browse_service("zoom", "phone_numbers")
class ZoomPhoneNumberBrowseSvc(BrowseSvc):

    def run(self):
        rows = []

        for phone_number in self.client.phone_numbers.list():
            model = build_model(phone_number)
            rows.append(model.dict())

        return rows


@reg.export_service("zoom", "phone_numbers")
class ZoomPhoneNumberExportSvc(ExportSvc):

    def run(self) -> dict:
        rows = []
        errors = []
        data_type = ZoomPhoneNumber.schema()["data_type"]

        for resp in self.client.phone_numbers.list():
            try:
                model = build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("number", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


def build_model(resp: dict) -> ZoomPhoneNumber:
    """Create a ZoomPhoneNumber instance from the provided API response."""
    emergency_address = resp.get("emergency_address") or {}
    site_name = deep_get(resp, "site.name", "")
    assignee = deep_get(resp, "assignee.name", "")
    return ZoomPhoneNumber.safe_build(
        action="IGNORE",
        number=resp["number"],
        assignee=assignee,
        type=resp["number_type"],
        source=resp["source"],
        status=resp["status"],
        site_name=site_name,
        **emergency_address
    )
