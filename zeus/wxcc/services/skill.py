import logging
from zeus import registry as reg
from .shared import WxccBulkSvc
from zeus.wxcc import wxcc_models as wm
from zeus.services import BrowseSvc, ExportSvc

log = logging.getLogger(__name__)


@reg.bulk_service("wxcc", "skills", "CREATE")
class WxccSkillCreateSvc(WxccBulkSvc):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.skills.create(payload=payload)

    def build_payload(self):
        payload = self.model.to_payload(exclude={"enum_names"})
        if self.model.skillType == "ENUM":
            payload["enumSkillValues"] = [
                {"name": enum_name}
                for enum_name in self.model.enum_names_list
            ]

        return payload


@reg.bulk_service("wxcc", "skills", "UPDATE")
class WxccSkillUpdateSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.skill(self.model.name)
        payload = self.build_payload()
        self.client.skills.update(self.current["id"], payload=payload)

    def build_payload(self):
        payload = self.model.to_payload(exclude={"enum_names"})

        if self.model.skillType == "ENUM":
            payload["enumSkillValues"] = self.build_enum_skill_payload()

        payload["id"] = self.current["id"]

        return payload

    def build_enum_skill_payload(self):
        enum_skill_payload = []

        current_enum_skills_by_name = {
            item["name"]: item["id"]
            for item in
            self.current.get("enumSkillValues") or []
        }

        for name in self.model.enum_names_list:
            entry = {"name": name}
            if name in current_enum_skills_by_name:
                entry["id"] = current_enum_skills_by_name[name]
            enum_skill_payload.append(entry)

        return enum_skill_payload


@reg.bulk_service("wxcc", "skills", "DELETE")
class WxccSkillDeleteSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.skill(self.model.name)
        self.client.skills.delete(self.current["id"])


@reg.browse_service("wxcc", "skills")
class WxccSkillBrowseSvc(BrowseSvc):

    def run(self):
        rows = []

        for resp in self.client.skills.list():
            model = wm.WxccSkill.safe_build(resp, enum_names=build_enum_names(resp))
            rows.append(model.dict())

        return rows


@reg.export_service("wxcc", "skills")
class WxccSkillExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = wm.WxccSkill.schema()["data_type"]

        for resp in self.client.skills.list():
            try:
                model = wm.WxccSkill.safe_build(resp, enum_names=build_enum_names(resp))
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


def build_enum_names(resp: dict) -> str:
    enum_names_list = [
        item.get("name")
        for item in
        resp.get("enumSkillValues") or []
        if item.get("name")
    ]

    return ";".join(enum_names_list)
