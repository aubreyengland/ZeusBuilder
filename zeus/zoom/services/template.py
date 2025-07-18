import logging
from zeus import registry as reg
from ..zoom_models import ZoomTemplate
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from .shared import ZoomBulkSvc, ZoomBulkTask
from zeus.shared.data_type_models import yn_to_bool
from zeus.zoom.zoom_simple import ZoomSimpleClient, ZoomServerFault

log = logging.getLogger(__name__)


@reg.bulk_service("zoom", "templates", "CREATE")
class ZoomTemplateCreateSvc(ZoomBulkSvc):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.phone_setting_templates.create(payload)

        task = ZoomTemplateUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def build_payload(self):
        payload = {
            "name": self.model.name,
            "type": self.model.type,
            "description": self.model.description,
        }
        if self.model.site_name:
            payload["site_id"] = self.lookup.site(self.model.site_name)["id"]

        return payload

    def rollback(self):
        super().rollback()
        if self.current:
            log.warning(
                "Zoom template CREATE rollback not possible as template deletion not supported."
            )


@reg.bulk_service("zoom", "templates", "UPDATE")
class ZoomTemplateUpdateSvc(ZoomBulkSvc):

    def run(self):
        site_id = self.lookup.site_id_or_none(self.model.site_name)
        self.current = self.lookup.user_template(self.model.name, site_id)

        task = ZoomTemplateUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


class ZoomTemplateUpdateTask(ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.is_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.phone_setting_templates.update(self.svc.current["id"], payload)
            self.is_updated = True

    def build_payload(self):
        include = {"description", "policy", "profile", "user_settings"}
        payload = self.model.to_payload(include=include, drop_unset=True)

        if self.model.new_name:
            payload["name"] = self.model.new_name

        if self.model.voicemail_enable:
            policy = payload.setdefault("policy", {})
            vm_policy = policy.setdefault("voicemail", {})
            vm_policy["enable"] = yn_to_bool(self.model.voicemail_enable)
        
        if self.model.call_forwarding_enable:
            policy = payload.setdefault("policy", {})
            cf_policy = policy.setdefault("call_forwarding", {})
            cf_policy["enable"] = yn_to_bool(self.model.call_forwarding_enable)
        
        if self.model.call_forwarding_type:
            policy = payload.setdefault("policy", {})
            cf_policy = policy.setdefault("call_forwarding", {})
            cf_policy["type"] = self.model.call_forwarding_type
        return payload


@reg.browse_service("zoom", "templates")
class ZoomTemplateBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomTemplateModelBuilder(self.client)

        for resp in builder.list_account_and_site_templates():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoom", "templates")
class ZoomTemplateExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomTemplate.schema()["data_type"]
        builder = ZoomTemplateModelBuilder(self.client)

        for resp in builder.list_account_and_site_templates():
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomTemplateModelBuilder:
    """
    ZoomTemplate model builder shared by Zoom Template Browse and Export services.
    The Phone Setting Templates LIST API takes a site_id param. Without this,
    only system-wide templates are returned. In order to get templates for
    all sites, the LIST API must be called for each site id.
    System-wide templates are also returned when a site_id is provided,
    so the templates are stored in a dict keyed by template id during collection.
    """

    def __init__(self, client):
        self.client: ZoomSimpleClient = client
        self.templates_by_id = {}

    def get_sites(self):
        """Zoom org with sites disabled will raise Exception"""
        try:
            return list(self.client.phone_sites.list())
        except ZoomServerFault:
            return []

    def list_account_and_site_templates(self):
        """
        Combine account-level and site-level templates into a single
        iterator response.

        The templates.list API will only return site-level templates if a
        site_id is provided. Account-level templates are returned if a site_id is
        omitted.

        Note: account-level templates are also returned with site-level templates
        when provided a site_id. To prevent returning account-level templates more
        than once, a check is done against the templates_by_id dict before including
        site-level results in the return value.
        """
        site_ids_and_names = [(site["id"], site["name"]) for site in self.get_sites()]
        site_ids_and_names.insert(0, (None, ""))

        for resp in self.client.phone_setting_templates.list():
            resp["site_name"] = ""
            self.templates_by_id[resp["id"]] = resp

        for site in self.get_sites():
            for resp in self.client.phone_setting_templates.list(site_id=site["id"]):
                if resp["id"] not in self.templates_by_id:
                    resp["site_name"] = site["name"]
                    self.templates_by_id[resp["id"]] = resp

        return list(self.templates_by_id.values())

    @staticmethod
    def build_model(resp: dict):
        return ZoomTemplate.safe_build(
            action="IGNORE",
            name=resp["name"],
            type=resp.get("type", "commonArea"),
            site_name=resp.get("site_name", ""),
            description=resp.get("description", ""),
        )

    def build_detailed_model(self, resp: dict):
        # type key is missing from common area templates for some reason so set the value if the
        # key is missing since the model requires a type value.
        template = self.client.phone_setting_templates.get(resp["id"])
        template_type = template.get("type", "commonArea")

        voicemail_enable = deep_get(template, "policy.voicemail.enable", default="")
        call_forwarding_enable = deep_get(template, "policy.call_forwarding.enable", default="")
        call_forwarding_type = deep_get(template, "policy.call_forwarding.type", default="")

        return ZoomTemplate.safe_build(
            action="IGNORE",
            name=template["name"],
            type=template_type,
            site_name=resp.get("site_name", ""),
            voicemail_enable=voicemail_enable,
            description=template.get("description", ""),
            call_forwarding_type=call_forwarding_type,
            call_forwarding_enable=call_forwarding_enable,
            policy=template.get("policy", {}),
            profile=template.get("profile", {}),
            user_settings=template.get("user_settings", {}),
        )
