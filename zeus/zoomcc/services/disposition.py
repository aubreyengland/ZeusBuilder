import logging
from zeus import registry as reg
from collections import defaultdict
from zeus.services import BrowseSvc, ExportSvc
from ..zoomcc_models import ZoomCCDisposition
from .shared import ZoomCCBulkSvc, ZoomCCBulkTask

log = logging.getLogger(__name__)


def build_payload(model: ZoomCCDisposition) -> dict:
    """Create the payload for a disposition create or update request from the model."""
    return {
        "disposition_name": model.disposition_name,
        "disposition_description": model.disposition_description,
        "status": str(model.status).lower(),
    }


@reg.bulk_service("zoomcc", "dispositions", "CREATE")
class ZoomCCDispositionCreateSvc(ZoomCCBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.disposition_sets_to_assign = []

    def run(self):
        """
        Step 1. Lookup needed disposition set IDs

        Step 2. Create the disposition

        Step 3. Add disposition to sets

        """
        self.get_disposition_sets()
        self.create_disposition()
        self.assign_to_disposition_sets()

    def create_disposition(self):
        payload = build_payload(self.model)
        self.current = self.client.cc_dispositions.create(payload)

    def assign_to_disposition_sets(self):
        for disposition_set in self.disposition_sets_to_assign:
            task = ZoomCCDispositionAssignSetTask(self, disposition_set)
            task.run()
            self.rollback_tasks.append(task)

    # def create_disposition_set(self):
    #     """
    #     Create the disposition set if it doesn't exist.
    #     """
    #     for disposition_set in self.model.disposition_sets:
    #         self.current = self.lookup.disposition_set(disposition_set)
    #         if not self.current:
    #             self.ZoomCCDispositionSetCreateTask(disposition_set)
    #     payload = build_payload(self.model)
    #     self.current = self.client.cc_disposition_sets.create(payload)

    def get_disposition_sets(self):
        for disposition_set_name in self.model.disposition_sets_list:
            # TODO: must catch exception if set doesn't exist and create
            resp = self.lookup.disposition_set(disposition_set_name)
            self.disposition_sets_to_assign.append(resp)

    def rollback(self):
        if self.current:
            disposition_id = self.current["disposition_id"]
            log.debug(f"{type(self).__name__} Rollback: {disposition_id=}")
            self.client.cc_dispositions.delete(disposition_id)


@reg.bulk_service("zoomcc", "dispositions", "UPDATE")
class ZoomCCDispositionUpdateSvc(ZoomCCBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.is_updated = False
        self.disposition_sets_to_assign = []

    def run(self):
        """
        Step 1. Get current disposition
        Step 2. Lookup needed disposition set IDs
        Step 3. Update disposition
        Step 4. Assign to sets
        """
        self.current = self.lookup.disposition(self.model.disposition_name)
        self.get_disposition_sets()
        self.update_disposition()
        self.assign_to_disposition_sets()

    def get_disposition_sets(self):
        for disposition_set_name in self.model.disposition_sets_list:
            # TODO: must catch exception if set doesn't exist and create
            summary = self.lookup.disposition_set(disposition_set_name)
            resp = self.client.cc_disposition_sets.get(summary["disposition_set_id"])

            if not self.is_currently_assigned(resp):
                self.disposition_sets_to_assign.append(resp)

    def update_disposition(self):
        payload = build_payload(self.model)
        self.client.cc_dispositions.update(self.current["disposition_id"], payload)
        self.is_updated = True

    def assign_to_disposition_sets(self):
        for disposition_set in self.disposition_sets_to_assign:
            task = ZoomCCDispositionAssignSetTask(self, disposition_set)
            task.run()
            self.rollback_tasks.append(task)

    def is_currently_assigned(self, disposition_set: dict) -> bool:
        current_assigned_dispositions = disposition_set.get("dispositions") or []
        return self.current["disposition_id"] in [d["disposition_id"] for d in current_assigned_dispositions]

    def rollback(self):
        super().rollback()
        if self.is_updated:
            disposition_id = self.current["disposition_id"]
            payload = {
                "disposition_name": self.current["disposition_name"],
                "disposition_description": self.current["disposition_description"],
                "status": self.current["status"],
            }

            log.debug(f"{type(self).__name__} Rollback: {disposition_id=}")
            self.client.cc_dispositions.update(disposition_id, payload)


class ZoomCCDispositionAssignSetTask(ZoomCCBulkTask):
    def __init__(self, svc, disposition_set, **kwargs):
        super().__init__(svc, **kwargs)
        self.set_id = disposition_set["disposition_set_id"]
        self.disposition_id = self.svc.current["disposition_id"]
        self.disposition_set: dict = disposition_set
        self.updated = False

    @property
    def current_disposition_ids(self) -> list:
        current_ids = self.disposition_set.get("dispositions") or []
        return [d["disposition_id"] for d in current_ids]

    def run(self):
        payload = self.current_disposition_ids + [self.disposition_id]
        log.debug(f"{type(self).__name__} run: {self.disposition_id=}, {self.set_id=}")
        self.client.cc_disposition_sets.update(self.set_id, {"disposition_ids": payload})
        self.updated = True

    def rollback(self):
        if self.updated:
            log.debug(
                f"{type(self).__name__} rollback: {self.disposition_id=}, {self.set_id=}"
            )
            payload = {"disposition_ids": self.current_disposition_ids}
            self.client.cc_disposition_sets.upate(self.set_id, payload)


@reg.bulk_service("zoomcc", "dispositions", "DELETE")
class ZoomCCDispositionDeleteSvc(ZoomCCBulkSvc):

    def run(self):
        to_delete = self.lookup.disposition(self.model.disposition_name)
        self.client.cc_dispositions.delete(to_delete["disposition_id"])


@reg.browse_service("zoomcc", "dispositions")
class ZoomCCDispositionBrowseSvc(BrowseSvc):
    """
    Collect Zoom Contact Center dispositions for a browse operation.
    """

    def run(self):
        rows = []
        for disposition in self.client.cc_dispositions.list():
            model = ZoomCCDisposition.safe_build(
                status=disposition["status"],
                disposition_name=disposition["disposition_name"],
                disposition_description=disposition["disposition_description"],
            )
            rows.append(model.dict())

        return rows


@reg.export_service("zoomcc", "dispositions")
class ZoomCCDispositionExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomCCDisposition.schema()["data_type"]
        builder = ZoomCCDispositionModelBuilder(self.client)

        for resp in self.client.cc_dispositions.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("disposition_name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomCCDispositionModelBuilder:
    """
    Collect Zoom Contact Center disposition details and create
    models for export operations.

    Basic disposition details come from LIST contact center dispositions.
    Disposition set membership requires a GET for each set.
    """

    def __init__(self, client):
        self.client = client
        self._set_names_by_disp_id = None

    @property
    def set_names_by_disp_id(self):
        if self._set_names_by_disp_id is None:
            self._set_names_by_disp_id = defaultdict(list)
            for summary in self.client.cc_disposition_sets.list():
                resp = self.client.cc_disposition_sets.get(summary["disposition_set_id"])
                disposition_set_name = resp["disposition_set_name"]

                assigned_dispositions = resp.get("dispositions") or []
                for assigned_disposition in assigned_dispositions:
                    disposition_id = assigned_disposition["disposition_id"]
                    self._set_names_by_disp_id[disposition_id].append(disposition_set_name)

        return self._set_names_by_disp_id

    def build_model(self, resp: dict):

        disposition_set_names = self.set_names_by_disp_id.get(resp["disposition_id"], [])

        return ZoomCCDisposition.safe_build(
            status=resp["status"],
            disposition_name=resp["disposition_name"],
            disposition_sets=",".join(disposition_set_names),
            disposition_description=resp["disposition_description"],
        )
