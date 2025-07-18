import logging
from . import shared
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusBulkOpFailed
from zeus.zoom.zoom_models import ZoomRoutingRule
from zeus.services import BrowseSvc, ExportSvc

log = logging.getLogger(__name__)


class ZoomRoutingRuleBulkSvc(shared.ZoomBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.endpoint = client.phone_routing_rules
        
    def create_routing_rule(self):
        task = ZoomRoutingRuleCreateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_routing_rule(self):
        task = ZoomRoutingRuleUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("zoom", "routing_rules", "CREATE")
class ZoomRoutingRuleCreateSvc(ZoomRoutingRuleBulkSvc):

    def run(self):
        self.create_routing_rule()


    def create_routing_rule(self):
        task = ZoomRoutingRuleCreateTask(self)
        resp = task.run()
        self.rollback_tasks.append(task)
        return resp


@reg.bulk_service("zoom", "routing_rules", "UPDATE")
class ZoomRoutingRuleUpdateSvc(ZoomRoutingRuleBulkSvc):
    action = "UPDATE"

    def run(self):
        self.get_current()
        self.update_routing_rule()

    def get_current(self):
        self.current = self.lookup.routing_rule(self.model.name)
        return self.current

class ZoomRoutingRuleCreateTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.create_resp: dict = {}

    def run(self):
        payload = self.build_payload()
        print(f"Creating routing rule with payload: {payload}")
        self.create_resp = self.client.phone_routing_rules.create(payload=payload)
        return self.create_resp

    def build_payload(self) -> dict:

        if len(self.model.name) > 32:
            raise ZeusBulkOpFailed(f"Routing Rule {self.model.name} must be less than 32 characters for CREATE operation")

        payload = self.model.to_payload(include={"number_pattern", "translation", "sip_group_id"})
        payload["name"] = self.model.name
        
        if self.model.rule_type:
            payload["type"] = self.model.rule_type_fix

        if self.model.site:
            site = self.svc.lookup.site(self.model.site)
            payload["site_id"] = site["id"]


        return payload
    

    def rollback(self) -> None:
        if self.create_resp:
            self.client.phone_routing_rules.delete(self.create_resp["id"])


class ZoomRoutingRuleUpdateTask(shared.ZoomBulkTask):
    """
    Update routing_rule basic settings such as, name, extension, timezone
    Extension is the unique identifier for Shared Line Groups, so it is updated
    based on the value in the 'new_extension' field.
    """
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomRoutingRuleCreateSvc = svc
        self.payload: dict = {}

    def run(self):
        self.build_payload()
        if self.payload:
            self.client.phone_routing_rules.update(
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

        if all([current_site_id, self.model.site]):
            model_site_id = self.svc.lookup.site_id_or_none(self.model.site)

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
            self.client.phone_routing_rules.update(self.svc.current["id"], payload)


    ##Missing Rollback

@reg.browse_service("zoom", "routing_rules")
class ZoomRoutingRuleBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomRoutingRuleModelBuilder(self.client)

        for resp in self.client.phone_routing_rules.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.bulk_service("zoom", "routing_rules", "DELETE")
class ZoomRoutingRuleDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.routing_rule(self.model.name)
        self.client.phone_routing_rules.delete(self.current["id"])


@reg.export_service("zoom", "routing_rules")
class ZoomRoutingRuleExportSvc(ExportSvc):

    def run(self):
        rows = []
        data_type = ZoomRoutingRule.schema()["data_type"]
        builder = ZoomRoutingRuleModelBuilder(self.client)
 
        for resp in self.client.phone_routing_rules.list():
            model = builder.build_detailed_model(resp)
            rows.append(model)
 
        return {data_type: rows}


class ZoomRoutingRuleModelBuilder:
    def __init__(self, client, lookup=None):
        self.client = client
        self.lookup = lookup

    def build_model(self, resp: dict):
        return ZoomRoutingRule.safe_build(**self.summary_data(resp))

    def build_detailed_model(self, resp):
        summary_data = self.summary_data(resp)
        return ZoomRoutingRule.safe_build(**summary_data)

    def summary_data(self, resp: dict):
        site_id = resp.get("site_id", "")
        site = site_id

        routing_path = resp.get("routing_path", {})
        sip_group_id = routing_path.get("sip_group", {}).get("id", "")
        rule_type = routing_path.get("type", "")

        return dict(
            name=resp.get("name", ""),
            site=site,
            translation_rule=resp.get("translation", ""),
            number_pattern=resp.get("number_pattern", ""),
            rule_type=rule_type,
            sip_group_id=sip_group_id,
        )
