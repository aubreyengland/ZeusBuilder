import logging
from . import shared
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from zeus.zoom.zoom_models import ZoomExternalContact


log = logging.getLogger(__name__)


@reg.bulk_service("zoom", "external_contacts", "CREATE")
class ZoomExternalContactCreateSvc(shared.ZoomBulkSvc):

    def run(self):
        self.create_external_contact()

    def create_external_contact(self):
        task = ZoomExternalContactCreateTask(self)
        self.current = task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("zoom", "external_contacts", "UPDATE")
class ZoomExternalContactUpdateSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.external_contact(self.model.name)
        payload = self.build_payload()
        self.client.phone_external_contacts.update(
            self.current["external_contact_id"], payload
        )

    def build_payload(self):
        payload = self.model.to_payload(exclude={"new_name"})

        if self.model.new_name:
            payload["name"] = self.model.new_name

        if self.model.phone_numbers_list:
            payload["phone_numbers"] = self.model.phone_numbers_list
        else:
            payload["phone_numbers"] = []

        return payload


@reg.bulk_service("zoom", "external_contacts", "DELETE")
class ZoomExternalContactDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.external_contact(self.model.name)
        self.client.phone_external_contacts.delete(self.current["external_contact_id"])


class ZoomExternalContactCreateTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.created: dict = {}

    def run(self):
        payload = self.build_payload()

        self.created = self.client.phone_external_contacts.create(payload=payload)
        return self.created

    def build_payload(self) -> dict:
        payload = self.model.to_payload(exclude={"new_name"})

        if self.model.phone_numbers_list:
            payload["phone_numbers"] = self.model.phone_numbers_list

        else:
            payload["phone_numbers"] = []

        return payload

    def rollback(self):
        if self.created:
            self.client.phone_external_contacts.delete(self.created["id"])


@reg.browse_service("zoom", "external_contacts")
class ZoomExternalContactBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        for resp in self.client.phone_external_contacts.list():
            model = build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoom", "external_contacts")
class ZoomExternalContactExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomExternalContact.schema()["data_type"]

        for resp in self.client.phone_external_contacts.list():
            try:
                model = build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


def build_model(resp):
    phone_number_list = deep_get(resp, "phone_numbers", default=[])

    return ZoomExternalContact.safe_build(
        name=resp.get("name", ""),
        email=resp.get("email", ""),
        extension_number=resp.get("extension_number", ""),
        description=resp.get("description", ""),
        routing_path=resp.get("routing_path", ""),
        auto_call_recorded=resp.get("auto_call_recorded", ""),
        phone_numbers=",".join(phone_number_list),
    )
