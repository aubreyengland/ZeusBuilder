import logging
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from ..zoom_models import ZoomEmergencyLocation
from .shared import ZoomBulkSvc, ZoomEmerAddrCreateTask
from ..zoom_simple import ZoomSimpleClient, ZoomServerFault

log = logging.getLogger(__name__)


class ZoomEmergencyLocationPayload:
    """
    Zoom emergency location payload logic shared by CREATE and UPDATE
    services
    """

    def build_payload(self: ZoomBulkSvc, emer_addr_id: str) -> dict:
        include = {
            "name",
            "bssid",
            "private_ip",
            "public_ip",
            "minimum_match_criteria",
        }
        payload = self.model.to_payload(include=include)

        # Site only required for orgs with site enabled
        site_id = self.lookup.site_id_or_none(self.model.site_name)
        if site_id:
            payload["site_id"] = site_id

        if self.model.new_name:
            payload["name"] = self.model.new_name

        # Only include elin_phone_number_id in payload if a value for elin is provided because
        # empty value will cause model to fail on Nomadic sites.
        if self.model.elin:
            payload["elin_phone_number_id"] = self.model.elin

        if self.model.parent_location_name:
            parent_location = self.lookup.location(self.model.parent_location_name, site_id)
            payload["parent_location_id"] = parent_location["id"]

        payload["emergency_address_id"] = emer_addr_id

        return payload


@reg.bulk_service("zoom", "emergency_locations", "CREATE")
class ZoomEmergencyLocationCreateSvc(ZoomBulkSvc, ZoomEmergencyLocationPayload):

    def run(self):
        emer_addr_id = self.get_emergency_address_id()
        payload = self.build_payload(emer_addr_id)
        self.current = self.client.phone_locations.create(payload)

    def get_emergency_address_id(self):
        task = ZoomEmerAddrCreateTask(self)
        emer_addr = task.run()
        self.rollback_tasks.append(task)
        return emer_addr["id"]

    def rollback(self):
        if self.current:
            self.client.phone_locations.delete(self.current["id"])

        for task in self.rollback_tasks:
            task.rollback()


@reg.bulk_service("zoom", "emergency_locations", "UPDATE")
class ZoomEmergencyLocationUpdateSvc(ZoomBulkSvc, ZoomEmergencyLocationPayload):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.is_updated = False

    def run(self):
        self.get_current()
        emer_addr_id = self.get_emergency_address_id()
        payload = self.build_payload(emer_addr_id)
        self.client.phone_locations.update(self.current["id"], payload)
        self.is_updated = True

    def get_current(self):
        site_id = self.lookup.site_id_or_none(self.model.site_name)
        self.current = self.lookup.location(self.model.name, site_id)

    def get_emergency_address_id(self):
        task = ZoomEmerAddrCreateTask(self)
        emer_addr = task.run()
        self.rollback_tasks.append(task)
        return emer_addr["id"]

    def rollback(self):
        if self.is_updated:
            self.client.phone_locations.update(self.current["id"], self.current)

        for task in self.rollback_tasks:
            task.rollback()


@reg.bulk_service("zoom", "emergency_locations", "DELETE")
class ZoomEmergencyLocationDeleteSvc(ZoomBulkSvc):

    def run(self):
        site_id = self.lookup.site_id_or_none(self.model.site_name)
        self.current = self.lookup.location(self.model.name, site_id)
        self.client.phone_locations.delete(self.current["id"])


@reg.browse_service("zoom", "emergency_locations")
class ZoomEmergencyLocationBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomEmergencyLocationModelBuilder(self.client)

        for resp in builder.locations_by_id.values():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoom", "emergency_locations")
class ZoomEmergencyLocationExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomEmergencyLocation.schema()["data_type"]
        builder = ZoomEmergencyLocationModelBuilder(self.client)

        for resp in builder.locations_by_id.values():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomEmergencyLocationModelBuilder:
    """
    Shared model builder class for Zoom Emergency Location
    Browse and Export services.
    """

    def __init__(self, client):
        self.client: ZoomSimpleClient = client
        self._locations_by_id = {}

    def get_sites(self):
        """Zoom org with sites disabled will raise Exception"""
        try:
            return list(self.client.phone_sites.list())
        except ZoomServerFault:
            return []

    @property
    def locations_by_id(self):
        if not self._locations_by_id:
            sites = self.get_sites()
            if not sites:
                self._locations_by_id = {
                    loc["id"]: loc for loc in self.client.phone_locations.list()
                }
            else:
                for site in sites:
                    for loc in self.client.phone_locations.list(site_id=site["id"]):
                        self._locations_by_id[loc["id"]] = loc

        return self._locations_by_id

    def build_model(self, resp):
        site_name = deep_get(resp, "site.name", default="")
        elin = deep_get(resp, "elin.phone_number", default="")
        emergency_address = resp.get("emergency_address", {})

        parent_id = resp.get("parent_location_id")
        if parent_id:
            parent_location = self.locations_by_id[parent_id]["name"]
        else:
            parent_location = ""

        model = ZoomEmergencyLocation.safe_build(
                action="IGNORE",
                name=resp["name"],
                elin=elin,
                site_name=site_name,
                bssid=resp.get("bssid", ""),
                public_ip=resp.get("public_ip", ""),
                private_ip=resp.get("private_ip", ""),
                parent_location_name=parent_location,
                minimum_match_criteria=resp["minimum_match_criteria"],
                **emergency_address,
        )

        return model
