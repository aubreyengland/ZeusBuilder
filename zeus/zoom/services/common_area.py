import logging
from . import shared
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from .shared import ZoomBulkTask, ZoomBulkSvc
from zeus.zoom.zoom_models import ZoomCommonArea

log = logging.getLogger(__name__)


@reg.bulk_service("zoom", "common_areas", "CREATE")
class ZoomCommonAreaCreateSvc(ZoomBulkSvc):

    def run(self):
        self.create_common_area()
        self.assign_phone_numbers()
        self.assign_emergency_address()
        self.update_common_area()

    def create_common_area(self):
        """
        Run the CREATE task and use the returned ID to
        get full object details for use by the UPDATE task.

        Only the CREATE task needs to be saved for rollback
        """
        task = ZoomCommonAreaCreateTask(self)
        resp = task.run()
        self.rollback_tasks.append(task)
        self.current = self.client.phone_common_areas.get(resp["id"])

    def assign_phone_numbers(self):
        task = shared.ZoomPhoneNumberAssignTask(self, endpoint=self.client.phone_common_areas)
        task.run()

    def assign_emergency_address(self):
        task = shared.ZoomEmerAddrAssignTask(self, endpoint=self.client.phone_common_areas)
        task.run()

    def update_common_area(self):
        task = ZoomCommonAreaUpdateTask(self, endpoint=self.client.phone_common_areas)
        task.run()


@reg.bulk_service("zoom", "common_areas", "UPDATE")
class ZoomCommonAreaUpdateSvc(ZoomBulkSvc):

    def run(self):
        self.get_current()
        #self.update_calling_plans()
        #self.update_phone_numbers()
        self.update_emergency_address()
        self.update_common_area_outbound_calling()
        #self.update_common_area_settings()

    def get_current(self):
        """Full GET request is necessary to get outbound_caller_ids"""
        resp = self.lookup.common_area(self.model.extension_number)
        self.current = self.client.phone_common_areas.get(resp["id"])

    def update_calling_plans(self):
        """
        Add/remove calling plans to match the plans on the model.
        The Add task must be run before the Remove task because a
        common area must have at least one calling plan assigned

        These tasks are also used for Phone Users so the API endpoint is
        passed as an init argument
        """
        for Task in (shared.ZoomCallingPlanAssignTask, shared.ZoomCallingPlanRemoveTask):
            task = Task(self, endpoint=self.client.phone_common_areas)
            task.run()
            self.rollback_tasks.append(task)

    def update_phone_numbers(self):
        """
        Add/remove phone numbers to match the phone numbers on the model
        The Remove task is run first to avoid hitting the number limit.

        These tasks are also used for Phone Users so the API endpoint is
        passed as an init argument
        """
        for Task in (shared.ZoomPhoneNumberRemoveTask, shared.ZoomPhoneNumberAssignTask):
            task = Task(self, endpoint=self.client.phone_common_areas)
            task.run()
            self.rollback_tasks.append(task)

    def update_emergency_address(self):
        """
        Update the emergency address to match the value in the model.

        This task is also used for Phone Users so the API endpoint is
        passed as an init argument.
        """
        task = shared.ZoomEmerAddrAssignTask(self, endpoint=self.client.phone_common_areas)
        task.run()
        self.rollback_tasks.append(task)

    def update_common_area_settings(self):
        task = ZoomCommonAreaUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_common_area_outbound_calling(self):
        task = ZoomOutboundCallingUpdateTask(self)
        task.run()


@reg.bulk_service("zoom", "common_areas", "DELETE")
class ZoomCommonAreaDeleteSvc(ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.common_area(self.model.extension_number)
        self.client.phone_common_areas.delete(self.current["id"])


class ZoomCommonAreaCreateTask(ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.created: dict = {}

    def run(self):
        payload = self.build_payload()

        self.created = self.client.phone_common_areas.create(payload=payload)
        return self.created

    def build_payload(self) -> dict:
        payload = self.model.to_payload(include={"display_name", "extension_number"})

        site_id = self.svc.lookup.site_id_or_none(self.model.site_name)
        if site_id:
            payload["site_id"] = site_id

        payload["calling_plans"] = self.svc.lookup.calling_plans(
            self.model.calling_plans_list
        )

        return payload

    def rollback(self):
        if self.created:
            self.client.phone_common_areas.delete(self.created["id"])


class ZoomCommonAreaUpdateTask(ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.has_run = False
        self.update_payload: dict = {}

    @property
    def current_outbound_caller_id(self):
        current_caller_ids = self.svc.current.get("outbound_caller_ids") or []
        return next(
            (
                entry["number"] for entry in current_caller_ids
                if entry.get("is_default")
            ), ""
        )

    def run(self):
        self.build_payload()

        if self.update_payload:
            self.client.phone_common_areas.update(self.svc.current["id"], self.update_payload)
            self.has_run = True

    def build_payload(self):
        if self.model.new_extension_number:
            self.update_payload["extension_number"] = self.model.new_extension_number

        current_site_name = deep_get(self.svc.current, "site.name", default="")
        if ([
            self.model.site_name,
            self.model.site_name != current_site_name
        ]):
            self.update_payload["site_id"] = self.svc.lookup.site_id_or_none(self.model.site_name)

        current_outbound_caller_id = self.current_outbound_caller_id
        if all([
            self.model.outbound_caller_id,
            self.model.outbound_caller_id != current_outbound_caller_id
        ]):
            self.update_payload["outbound_caller_id"] = self.model.outbound_caller_id

        current_timezone = deep_get(self.svc.current, "timezone", default="")
        if all([self.model.timezone, self.model.timezone != current_timezone]):
            self.update_payload["timezone"] = self.model.timezone
            
        current_cost_center = deep_get(self.svc.current, "cost_center", default="")
        if all([self.model.cost_center, self.model.cost_center != current_cost_center]):
            self.update_payload["cost_center"] = self.model.cost_center
        
        current_department = deep_get(self.svc.current, "department", default="")
        if all([self.model.department, self.model.department != current_department]):
            self.update_payload["department"] = self.model.department
            

    def rollback(self) -> None:
        rollback_payload = {}

        if self.has_run:
            if "extension_number" in self.update_payload:
                rollback_payload["extension_number"] = self.svc.current["extension_number"]
            if "site_id" in self.update_payload:
                rollback_payload["site_id"] = deep_get(self.svc.current, "site.id", default=None)
            if "outbound_caller_id" in self.update_payload:
                rollback_payload["outbound_caller_id"] = self.current_outbound_caller_id
            if "timezone" in self.update_payload:
                rollback_payload["timezone"] = self.svc.current["timezone"]
            if "cost_center" in self.update_payload:
                rollback_payload["cost_center"] = self.svc.current.get("cost_center", "")
            if "department" in self.update_payload:
                rollback_payload["department"] = self.svc.current.get("department", "")
                

            if rollback_payload:
                self.client.phone_common_areas.update(self.svc.current["id"], rollback_payload)


class ZoomOutboundCallingUpdateTask(ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.has_run = False
        self.update_payload: dict = {}

    def block_outbound_calling(self):
        return self.model.block_country_code

    def run(self):
        if not self.model.block_country_code:
            log.debug(
                "No block country code set on model — skipping block outbound calling update."
            )
            return  
        self.build_payload()
        if self.update_payload:

            resp = self.client.phone_common_areas.block_outbound_calling(self.svc.current["id"], self.update_payload)
            
            self.has_run = True

    def build_payload(self):
        # Check if the model has a country code to block
        block_country_code = self.model.block_country_code
        self.update_payload = {
            "country_regions": [
                {
                    "iso_code": block_country_code,
                    "rule": 2,
                    "delete_existing_exception_rules": False,
                }
            ]
        }


@reg.browse_service("zoom", "common_areas")
class ZoomCommonAreaBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomCommonAreaModelBuilder(self.client)

        for resp in self.client.phone_common_areas.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.export_service("zoom", "common_areas")
class ZoomCommonAreaExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomCommonArea.schema()["data_type"]
        builder = ZoomCommonAreaModelBuilder(self.client)

        for resp in self.client.phone_common_areas.list():
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("display_name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomCommonAreaModelBuilder:
    def __init__(self, client):
        self.client = client

    def build_model(self, resp: dict):
        return ZoomCommonArea.safe_build(**self.summary_data(resp))

    def build_detailed_model(self, resp: dict):
        common_area_details = self.client.phone_common_areas.get(resp["id"])
        emergency_address = common_area_details.get("emergency_address") or {}

        current_caller_ids = common_area_details.get("outbound_caller_ids") or []
        outbound_caller_id = next(
            (
                entry["number"] for entry in current_caller_ids
                if entry.get("is_default")
            ), ""
        )

        return ZoomCommonArea.safe_build(
            timezone=common_area_details.get("timezone", ""),
            outbound_caller_id=outbound_caller_id,
            **self.summary_data(resp),
            **emergency_address,
        )

    @staticmethod
    def summary_data(resp: dict):
        site_name = deep_get(resp, "site.name", default="")
        calling_plans_list = [c["name"] for c in resp.get("calling_plans") or []]
        phone_number_list = [n["number"] for n in resp.get("phone_numbers") or []]

        return dict(
            site_name=site_name,
            display_name=resp["display_name"],
            extension_number=resp["extension_number"],
            phone_numbers=",".join(phone_number_list),
            calling_plans=",".join(calling_plans_list),
        )
