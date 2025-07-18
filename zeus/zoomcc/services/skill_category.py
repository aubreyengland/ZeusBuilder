import logging
from zeus import registry as reg
from collections import defaultdict
from zeus.services import BrowseSvc, ExportSvc
from ..zoomcc_models import ZoomCCSkillCategory
from zeus.exceptions import ZeusBulkOpFailed
from .shared import (
    ZoomCCBulkSvc,
    ZoomCCBulkTask,
    ZoomCCSkillCreateTask,
    ZoomCCSkillDeleteTask,
)

log = logging.getLogger(__name__)


@reg.bulk_service("zoomcc", "skill_categories", "CREATE")
class ZoomCCSkillCategoryCreateSvc(ZoomCCBulkSvc):
    """
    Create a new ZoomCC Skill Category with associated skills based on the provided model.

    When run:
     - Runs the `ZoomCCSkillCategoryCreateTask` to create the skill category and appends the
       task to the `rollback_tasks` list.
     - Runs an instance of `ZoomCCSkillCreateTask` for each skill name in `model.skills_to_add_list`.
       The tasks are not added to the `rollback_tasks` list because the skills are automatically
       deleted along with the category.

    Upon rollback:
      - Deletes the Skill Category, which will also delete all associated skills
    """

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: ZoomCCSkillCategory = model

    def run(self):
        self.create_skill_category()
        self.add_skills()

    def create_skill_category(self):
        task = ZoomCCSkillCategoryCreateTask(self)
        self.current = task.run()
        self.rollback_tasks.append(task)

    def add_skills(self):
        """
        No necessary to save tasks for rollback as they will be
        deleted along with category.
        """
        for skill_name in self.model.skills_to_add_list:
            task = ZoomCCSkillCreateTask(
                self,
                skill_name=skill_name,
                skill_category_id=self.current["skill_category_id"],
            )
            task.run()

    def rollback(self):
        if self.current:
            self.client.cc_skill_categories.delete(self.current["skill_category_id"])


@reg.bulk_service("zoomcc", "skill_categories", "UPDATE")
class ZoomCCSkillCategoryUpdateSvc(ZoomCCBulkSvc):
    """
    Updates an existing ZoomCC Skill Category based on the provided model.

    When run:
     - Does API lookup of the skill category and sets the `current` dict attribute.
       Lookup failure will raise `ZeusBulkOpFailed` and end the operation with an error.
     - Gets skills the current associated with the category for use in the add and remove skill methods.
     - Runs the `ZoomCCSkillCategoryUpdateTask` to update simple skill category properties
       and appends the task to the `rollback_tasks` list.
     - Iterates over `model.skills_to_add_list` and checks if the skill already exists for this category.
       If so, continue failing the operation.
       If not, runs an instance of `ZoomCCSkillCreateTask` and appends the task to the `rollback_tasks` list.
     - Iterates over `model.skill_to_remove_list` and checks if the skill exists for this category.
       If so runs an instance of `ZoomCCSkillDeleteTask`and appends the task to the `rollback_tasks` list.
       If not, raises `ZeusBulkOpFailed` indicating the expected skill is not found.

    Upon rollback:
      - The default rollback behavior (defined in the parent `rollback` method) is executed to
        run the `rollback` methods on each task in the `rollback_tasks` list.
    """

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: ZoomCCSkillCategory = model
        self.current_skills_by_name: dict = {}
        self.is_updated = False

    def run(self):
        self.current = self.lookup.skill_category(self.model.skill_category_name)
        self.get_current_skills()
        self.update_skill_category()
        self.add_skills()
        self.remove_skills()

    def update_skill_category(self):
        task = ZoomCCSkillCategoryUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def get_current_skills(self):
        """
        Get the category's current skills and save them to the `current_skills_by_name` dictionary
        for use by the `add_skills` and `remove_skills` methods
        """
        current_skills = self.client.cc_skills.list(skill_category_id=self.current["skill_category_id"])
        self.current_skills_by_name = {
            skill["skill_name"]: skill for skill in current_skills
        }

    def add_skills(self):
        for skill_name in self.model.skills_to_add_list:

            # Do not fail operation if skill already exists
            if skill_name in self.current_skills_by_name:
                continue

            task = ZoomCCSkillCreateTask(
                self,
                skill_name=skill_name,
                skill_category_id=self.current["skill_category_id"],
            )
            task.run()

            self.rollback_tasks.append(task)

    def remove_skills(self):
        for skill_name in self.model.skills_to_remove_list:
            skill = self.current_skills_by_name.get(skill_name)

            if not skill:
                raise ZeusBulkOpFailed(
                    f"Skill to remove: {skill_name} not found for category {self.model.skill_category_name}")

            task = ZoomCCSkillDeleteTask(self, skill)
            task.run()

            self.rollback_tasks.append(task)


@reg.bulk_service("zoomcc", "skill_categories", "DELETE")
class ZoomCCSkillCategoryDeleteSvc(ZoomCCBulkSvc):

    def run(self):
        to_delete = self.lookup.skill_category(self.model.skill_category_name)
        self.client.cc_skill_categories.delete(to_delete["skill_category_id"])


class ZoomCCSkillCategoryCreateTask(ZoomCCBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.created_skill_category: dict = {}

    def run(self) -> dict:
        payload = {
            "skill_type": self.model.skill_type,
            "skill_category_name": self.model.skill_category_name,
            "skill_category_description": self.model.skill_category_description,
        }
        if self.model.skill_type == "proficiency":
            payload["max_proficiency_level"] = self.model.max_proficiency_level

        log.debug(f"{type(self).__name__} run: {payload=}")
        self.created_skill_category = self.client.cc_skill_categories.create(payload)
        return self.created_skill_category

    def rollback(self):
        if self.created_skill_category:
            log.debug(
                f"{type(self).__name__} rollback: {self.created_skill_category=}"
            )
            to_delete = self.created_skill_category["skill_category_id"]
            self.client.cc_skill_categories.delete(to_delete)


class ZoomCCSkillCategoryUpdateTask(ZoomCCBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.is_updated = False

    def run(self):
        log.debug(f"{type(self).__name__} run: {self.model.skill_category_name=}")
        self._update(self.model.dict())
        self.is_updated = True

    def rollback(self):
        if self.is_updated:
            log.debug(f"{type(self).__name__} rollback: {self.model.skill_category_name=}")
            self._update(self.svc.current)

    def _update(self, obj: dict):
        """Send request for update or rollback task."""
        payload = self.build_payload(obj)
        id_ = self.svc.current["skill_category_id"]
        self.client.cc_skill_categories.update(id_, payload)

    @staticmethod
    def build_payload(obj: dict):
        name = obj.get("new_skill_category_name") or obj["skill_category_name"]
        payload = {
            "skill_category_name": name,
            "skill_category_description": obj.get("skill_category_description", ""),
        }
        if obj["skill_type"] == "proficiency":
            payload["max_proficiency_level"] = obj["max_proficiency_level"]

        return payload


@reg.browse_service("zoomcc", "skill_categories")
class ZoomCCSkillCategoryBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomCCSkillCategoryModelBuilder(self.client)

        for resp in self.client.cc_skill_categories.list():
            model = builder.build_model(resp)
            rows.append(model)

        return rows


@reg.export_service("zoomcc", "skill_categories")
class ZoomCCSkillCategoryExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomCCSkillCategory.schema()["data_type"]
        builder = ZoomCCSkillCategoryModelBuilder(self.client)

        for resp in self.client.cc_skill_categories.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("skill_category_name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomCCSkillCategoryModelBuilder:
    """
    Collect Zoom Contact Center Skill details and create
    models for export operations.

    Basic Skill details come from LIST contact center Skills.
    Skill set membership requires a GET for each set.
    """

    def __init__(self, client):
        self.client = client
        self._skill_names_by_category_id = None

    @property
    def skill_names_by_category_id(self):
        if self._skill_names_by_category_id is None:
            self._skill_names_by_category_id = defaultdict(list)

            for skill in self.client.cc_skills.list():
                skill_name = skill["skill_name"]
                skill_category_id = skill["skill_category_id"]
                self._skill_names_by_category_id[skill_category_id].append(skill_name)

        return self._skill_names_by_category_id

    def build_model(self, resp):
        skill_names_list = self.skill_names_by_category_id.get(resp["skill_category_id"], [])

        model = ZoomCCSkillCategory.safe_build(
            skills=",".join(skill_names_list),
            **resp,
        )

        return model
