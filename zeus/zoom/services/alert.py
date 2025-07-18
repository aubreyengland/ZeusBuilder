import logging
from . import shared
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusBulkOpFailed
from zeus.zoom.zoom_models import ZoomAlert
from zeus.services import BrowseSvc, ExportSvc

log = logging.getLogger(__name__)


class ZoomAlertBulkSvc(shared.ZoomBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.endpoint = client.phone_alerts
        
    def create_alert(self):
        task = ZoomAlertCreateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_alert(self):
        task = ZoomAlertUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)
        
        

@reg.bulk_service("zoom", "alerts", "CREATE")
class ZoomAlertCreateSvc(ZoomAlertBulkSvc):

    def run(self):
        resp = self.create_alert()
        self.current = self.client.phone_alerts.get(resp["id"])


    def create_alert(self):
        task = ZoomAlertCreateTask(self)
        resp = task.run()
        self.rollback_tasks.append(task)
        return resp


@reg.bulk_service("zoom", "alerts", "UPDATE")
class ZoomAlertUpdateSvc(ZoomAlertBulkSvc):
    action = "UPDATE"

    def run(self):
        self.get_current()
        self.update_alert()
        self.update_members()

    def get_current(self):
        """ get the current Call Queue
        """
        self.current = self.get.alert(self.model.name)
        return self.current
    

class ZoomAlertCreateTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.create_resp: dict = {}

    def run(self):
        payload = self.build_payload()
        self.create_resp = self.client.phone_alerts.create(payload=payload)
        return self.create_resp

    def build_payload(self) -> dict:
        #validate name to contain less than 32 characters
        if len(self.model.name) > 32:
            raise ZeusBulkOpFailed(f"Alert {self.model.name} must be less than 32 characters for CREATE operation")
        
        payload = {"name": self.model.name}
        if self.model.site_name:
            site = self.svc.lookup.site(self.model.site_name)
            payload["site_id"] = site["id"]

        return payload

    def rollback(self) -> None:
        if self.create_resp:
            self.client.phone_alerts.delete(self.create_resp["id"])


class ZoomAlertUpdateTask(shared.ZoomBulkTask):
    """
    Update Alert basic settings such as, name, extension, timezone
    Extension is the unique identifier for Shared Line Groups, so it is updated
    based on the value in the 'new_extension' field.
    """
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomAlertCreateSvc = svc
        self.payload: dict = {}

    def run(self):
        self.build_payload()
        if self.payload:
            self.client.phone_alerts.update(
                self.svc.current["id"], self.payload
            )

    def build_payload(self):
        payload = self.model.to_payload(
            include={}, drop_unset=True
        )

        payload.update(self.get_site_id_for_update())
        payload.update(self.get_name_for_update())


        self.payload = payload

    def get_name_for_update(self) -> dict:
        """Include name in the payload if it differs from the current name"""
        current_name = self.svc.current.get("name")
        if self.model.name != current_name:
            return {"name": self.model.name}
        return {}

    def get_site_id_for_update(self) -> dict:
        """
        Determine if site_id should be included in the update payload.
        site_id should only be included if:
         - there is a current site id
         - model.site_name has a value
         - site_id lookup returns a value
         - the model site id differs from current

        The site id will not be present in current when this task is
        run as part of `CREATE` action, which is fine as the site is set
        in the create request.
        """
        current_site_id = deep_get(self.svc.current, "site.id", default=None)

        if all([current_site_id, self.model.site_name]):
            model_site_id = self.svc.lookup.site_id_or_none(self.model.site_name)

            if model_site_id != current_site_id:
                return {"site_id": model_site_id}

        return {}

    def rollback(self):
        payload = {
            key: self.svc.current[key]
            for key in self.payload
            if key in self.svc.current
        }
        if "site_id" in self.payload:
            payload["site_id"] = self.svc.current["site"]["id"]

        if payload:
            self.client.phone_alerts.update(self.svc.current["id"], payload)


    ##Missing Rollback

@reg.browse_service("zoom", "alerts")
class ZoomAlertBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomAlertModelBuilder(self.client)

        for resp in self.client.phone_alerts.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.bulk_service("zoom", "alerts", "DELETE")
class ZoomAlertDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.alert(self.model.name)
        self.client.phone_alerts.delete(self.current["id"])


@reg.export_service("zoom", "alerts")
class ZoomAlertExportSvc(ExportSvc):

    def run(self):
        rows = []
        data_type = ZoomAlert.schema()["data_type"]
        builder = ZoomAlertModelBuilder(self.client)

        for resp in self.client.phone_alerts.list():
            model = builder.build_detailed_model(resp)
            rows.append(model)

        return {data_type: rows}


class ZoomAlertModelBuilder:
    def __init__(self, client):
        self.client = client

    def build_model(self, resp: dict):
        return ZoomAlert.safe_build(**self.summary_data(resp))

    def build_detailed_model(self, resp):
        summary_data = self.summary_data(resp)
        
        return ZoomAlert.safe_build(
            **summary_data,
        )

    @staticmethod
    def summary_data(resp: dict):
        site_name = deep_get(resp, "site.name", default="")

        return dict(
            name=resp["name"],
            site_name=site_name,
        )
