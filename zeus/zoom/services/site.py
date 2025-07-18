import logging
from . import shared
from zeus import registry as reg
from ..zoom_models import ZoomSite
from zeus.shared.helpers import deep_get
from ..zoom_simple import ZoomSimpleClient
from zeus.services import BrowseSvc, ExportSvc

log = logging.getLogger(__name__)


@reg.bulk_service("zoom", "sites", "CREATE")
class ZoomSiteCreateSvc(shared.ZoomBulkSvc):

    def run(self):
        self.create_site()
        self.update_policy()

    def create_site(self):
        payload = {
            "name": self.model.name,
            "auto_receptionist_name": self.model.auto_receptionist,
            "default_emergency_address": self.model.emergency_address,
        }
        # Site code is required if enabled for tenant but should not be
        # included if not enabled
        if self.model.site_code:
            payload["site_code"] = self.model.site_code
        if self.model.short_extension_length:
            payload["short_extension"] = {"length": self.model.short_extension_length}

        self.current = self.client.phone_sites.create(payload)

    def update_policy(self):
        payload = self.model.to_payload(include={"policy"}, drop_unset=True)
        if payload:
            self.client.phone_sites.update(self.current["id"], payload)

    def rollback(self):
        """
        Use first existing site as transfer site since nothing should be associated to this
        site immediately after creation
        """
        if self.current:
            transfer_site = next((self.client.phone_sites.list()), None)
            if transfer_site:
                self.client.phone_sites.delete(
                    self.current["id"], transfer_site_id=transfer_site["id"]
                )


@reg.bulk_service("zoom", "sites", "UPDATE")
class ZoomSiteUpdateSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.site(self.model.name)
        payload = self.build_payload()
        self.client.phone_sites.update(self.current["id"], payload)

    def build_payload(self):
        payload = self.model.to_payload(include={"policy"}, drop_unset=True)

        if self.model.new_name:
            payload["name"] = self.model.new_name

        # If address is complete, include it in the update without checking
        # if it differs from the existing because that information is not
        # available in the site GET response
        if shared.is_emergency_address_complete(self.model):
            payload["default_emergency_address"] = self.model.emergency_address

        if self.model.site_code:
            payload["site_code"] = self.model.site_code
        if self.model.short_extension_length:
            payload["short_extension"] = {"length": self.model.short_extension_length}

        return payload


@reg.bulk_service("zoom", "sites", "DELETE")
class ZoomSiteDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.site(self.model.name)
        transfer_site = self.lookup.site(self.model.transfer_site_name)

        self.client.phone_sites.delete(
            self.current["id"], transfer_site_id=transfer_site["id"]
        )


class ZoomSitePolicyTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.is_updated = False

    def run(self):
        payload = self.build_payload()

        if payload:
            self.client.phone_sites.update(self.svc.current["id"], payload)
            self.is_updated = True

    def build_payload(self):
        payload = self.model.to_payload(include={"policy"}, drop_unset=True)
        return payload


@reg.browse_service("zoom", "sites")
class ZoomSiteBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomSiteBuilder(self.client)

        for resp in self.client.phone_sites.list():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoom", "sites")
class ZoomSiteExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomSite.schema()["data_type"]
        builder = ZoomSiteBuilder(self.client)

        for resp in self.client.phone_sites.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomSiteBuilder:
    def __init__(self, client):
        self.client: ZoomSimpleClient = client
        self._emer_addresses = None

    def get_emer_address(self, site_id) -> dict:
        if self._emer_addresses is None:
            self._emer_addresses = get_default_emergency_addresses(self.client)
        return self._emer_addresses.get(site_id) or {}

    def build_model(self, resp):

        site = self.client.phone_sites.get(resp["id"])

        # Only present if site codes are enabled
        site_code = site.get("site_code", "")
        short_extension_length = deep_get(site, "short_extension.length", default="")

        addr = self.get_emer_address(site["id"])
        auto_receptionist = resp["main_auto_receptionist"]["name"]

        model = ZoomSite.safe_build(
            action="IGNORE",
            name=site["name"],
            site_code=site_code,
            policy=site.get("policy") or {},
            auto_receptionist=auto_receptionist,
            short_extension_length=short_extension_length,
            **addr,
        )

        return model


def get_default_emergency_addresses(client: ZoomSimpleClient) -> dict:
    """
    Return a dictionary of emergency addresses flagged as default for
    as site keyed by the site id.

    level=0 param returns only account-level addresses and does not include
    personal addresses
    """
    default_addresses_by_site = {}
    includes = {"address_line1", "address_line2", "city", "state_code", "zip", "country"}

    for item in client.phone_emergency_addresses.list(level=0):
        if item["is_default"]:
            site_id = item["site"]["id"]
            addr = {k: v for k, v in item.items() if k in includes}
            default_addresses_by_site[site_id] = addr

    return default_addresses_by_site
