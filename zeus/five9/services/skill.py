from zeus import registry as reg
from .shared import Five9BulkSvc
from ..five9_models import Five9Skill
from zeus.services import BrowseSvc, ExportSvc


@reg.bulk_service("five9", "skills", "CREATE")
class Five9SkillCreateSvc(Five9BulkSvc):

    def run(self):
        payload = self.build_payload()
        self.client.createSkill(payload)

    def build_payload(self):
        payload = self.model.to_payload(exclude={"newSkillName"})
        return {"skill": payload}


@reg.bulk_service("five9", "skills", "UPDATE")
class Five9SkillUpdateSvc(Five9BulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current = None

    def run(self):
        self.current = self.client.getSkillInfo(self.model.name)
        payload = self.build_payload()
        resp = self.client.modifySkill(payload)

    def build_payload(self):
        payload = self.model.to_payload(exclude={"newSkillName"})

        payload["id"] = self.current.skill.id
        if self.model.newSkillName:
            payload["name"] = self.model.newSkillName

        return payload


@reg.bulk_service("five9", "skills", "DELETE")
class Five9SkillDeleteSvc(Five9BulkSvc):

    def run(self):
        self.client.deleteSkill(self.model.name)


@reg.export_service("five9", "skills")
class Five9SkillExportSvc(ExportSvc):

    def run(self) -> dict:
        rows = []
        errors = []
        data_type = Five9Skill.schema()["data_type"]

        for resp in self.client.getSkills():
            try:
                model = Five9Skill.safe_build(resp.dict())
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


@reg.browse_service("five9", "skills")
class Five9SkillBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        for resp in self.client.getSkills():
            model = Five9Skill.safe_build(resp.dict())
            rows.append(model.dict())

        return rows
