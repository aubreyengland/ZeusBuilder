import logging
from zeus import registry as reg
from typing import Dict, Optional
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from ..zoomcc_models import ZoomCCSkill, ZoomCCUserSkill
from .shared import (
    ZoomCCBulkSvc,
    ZoomCCSkillCreateTask,
    ZoomCCSkillUpdateTask,
    ZoomCCUserSkillsAssignTask,
    ZoomCCUserSkillRemoveTask,
)

log = logging.getLogger(__name__)


@reg.bulk_service("zoomcc", "skills", "CREATE")
class ZoomCCSkillCreateSvc(ZoomCCBulkSvc):
    """Add a new ZoomCC Skill to an existing Skill Category."""

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: ZoomCCSkill = model
        self.skill_category: dict = {}
        self.skill_assignment_by_user_id: Dict[str, int] = {}

    def run(self):
        self.skill_category = self.lookup.skill_category(self.model.skill_category_name)
        self.get_users_for_assignment()
        self.create_skill()
        self.assign_users()

    def create_skill(self):
        task = ZoomCCSkillCreateTask(
            self,
            skill_name=self.model.skill_name,
            skill_category_id=self.skill_category["skill_category_id"],
        )
        self.current = task.run()
        self.rollback_tasks.append(task)

    def get_users_for_assignment(self):
        """
        Lookup the user id for each assign-to email and save the
        user_id and proficiency value to the skill_assignment_by_user_id
        attribute keyed by the user id.

        This is used to build UserSkills for the skill assignment task later
        but done before skill creation to allow lookup errors here to fail
        the operation before the skill is created.
        """
        for email, proficiency in self.model.users_list:
            user = self.lookup.user(email.strip())

            self.skill_assignment_by_user_id[user["user_id"]] = proficiency

    def assign_users(self):
        """
        Create a UserSkill instance for each user_id, proficiency item and
        pass this to the ZoomCCUserSkillsAssignTask
        No need to save the task for rollback since removing the skill will take care of this.
        """
        for user_id, proficiency in self.skill_assignment_by_user_id.items():
            user_skill = ZoomCCUserSkill(
                skill_id=self.current["skill_id"],
                skill_type=self.current["skill_type"],
                skill_name=self.current["skill_name"],
                skill_category_name=self.current["skill_category_name"],
                user_proficiency_level=proficiency,
            )
            task = ZoomCCUserSkillsAssignTask(self, user_id, [user_skill])
            task.run()


@reg.bulk_service("zoomcc", "skills", "UPDATE")
class ZoomCCSkillUpdateSvc(ZoomCCBulkSvc):
    """
    Update an existing ZoomCC Skill.

    Must provide skill category id to lookup since skill names are not globally-unique.
    """

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: ZoomCCSkill = model
        self.user_skill_assignment_by_user_id: Dict[str, ZoomCCUserSkill] = {}
        self.user_skill_removal_by_user_id: Dict[str, ZoomCCUserSkill] = {}

    def run(self):
        self.get_current()
        self.get_user_skills_for_removal()
        self.get_user_skills_for_assignment()
        self.update_skill()
        self.remove_users()
        self.assign_users()

    def get_current(self):
        self.current = self.lookup.skill_by_category_name(
            self.model.skill_name, self.model.skill_category_name
        )

    def update_skill(self):
        if self.model.new_skill_name:
            task = ZoomCCSkillUpdateTask(self, self.model.new_skill_name)
            task.run()
            self.rollback_tasks.append(task)

    def get_user_skills_for_assignment(self):
        """
        Parse the model.users_list to build proposed user skill assignments.
        For each, check for a current user skill assignment for the user.
        If no current assignment exists, add the proposed_user_skill for new assignment

        If a current assignment exists and differs from the proposed assignment, add
        the proposed_user_skill for assignment and add the current_user_skill for removal.
        This allows for proficiency value updates.

        If the current assignment is identical to the proposed assignment, do nothing.
        """
        for email, proficiency in self.model.users_list:

            user_skill = ZoomCCUserSkill(
                skill_id=self.current["skill_id"],
                skill_type=self.current["skill_type"],
                skill_name=self.current["skill_name"],
                skill_category_name=self.current["skill_category_name"],
                user_proficiency_level=proficiency,
            )

            user = self.lookup.user(email.strip())
            current_user_skill = self.lookup_current_user_skill_assignment(user)

            if not current_user_skill:
                self.user_skill_assignment_by_user_id[user["user_id"]] = user_skill

            elif current_user_skill != user_skill:
                self.user_skill_removal_by_user_id[user["user_id"]] = current_user_skill
                self.user_skill_assignment_by_user_id[user["user_id"]] = user_skill

    def get_user_skills_for_removal(self):
        for email in self.model.users_to_remove_list:
            user = self.lookup.user(email)
            user_skill = self.lookup_current_user_skill_assignment(user)

            if user_skill:
                self.user_skill_removal_by_user_id[user["user_id"]] = user_skill
            else:
                raise ZeusBulkOpFailed(
                    f"Skill {self.current['skill_name']} not currently assigned to user {user['user_email']}"
                )

    def lookup_current_user_skill_assignment(self, user: dict) -> Optional[ZoomCCUserSkill]:
        """
        Lookup the current skill assignment for the provided user.
        This provides the current max_proficiency_level value that will be necessary
        to roll back the skill removal task and determine if an assignment is necessary

        """
        existing = self.client.cc_users.list_skills(
            user["user_id"], skill_category_id=self.current["skill_category_id"]
        )
        for entry in existing:
            if entry["skill_name"] == self.current["skill_name"]:
                return ZoomCCUserSkill.parse_obj(entry)

        return None

    def assign_users(self):
        for user_id, user_skill in self.user_skill_assignment_by_user_id.items():
            task = ZoomCCUserSkillsAssignTask(self, user_id, [user_skill])
            task.run()
            self.rollback_tasks.append(task)

    def remove_users(self):
        for user_id, user_skill in self.user_skill_removal_by_user_id.items():
            task = ZoomCCUserSkillRemoveTask(self, user_id, user_skill)
            task.run()
            self.rollback_tasks.append(task)


@reg.bulk_service("zoomcc", "skills", "DELETE")
class ZoomCCSkillDeleteSvc(ZoomCCBulkSvc):
    """
    Delete a ZoomCC Skill.

    Must provide skill category id to lookup since skill names are not globally-unique.
    """

    def run(self):
        to_delete = self.lookup.skill_by_category_name(
            self.model.skill_name, self.model.skill_category_name
        )
        self.client.cc_skills.delete(to_delete["skill_id"])


@reg.browse_service("zoomcc", "skills")
class ZoomCCSkillBrowseSvc(BrowseSvc):
    """
    Collect Zoom Contact Center Skills for a browse operation.
    """

    def run(self):
        rows = [model.dict() for model in self.build_models()]

        return rows

    def build_models(self):
        models = []

        for skill in self.client.cc_skills.list():
            model = ZoomCCSkill.safe_build(
                skill_name=skill["skill_name"],
                skill_category_name=skill["skill_category_name"],
            )
            models.append(model)

        return models


@reg.export_service("zoomcc", "skills")
class ZoomCCSkillExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomCCSkill.schema()["data_type"]
        builder = ZoomCCSkillModelBuilder(self.client)

        for resp in self.client.cc_skills.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("skill_name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomCCSkillModelBuilder:
    """
    Collect Zoom Contact Center Skill details and create
    models for export operations.

    Basic Skill details come from LIST contact center Skills.
    User assignment details come from LIST contact center Skill Users.
    Proficiency details come from LIST contact center User Skills.
    """

    def __init__(self, client):
        self.client = client

    def get_user_proficiency_level(self, user_id, skill: dict) -> str:
        """
        Get the user skill assignment details for the provided proficiency skill and
        provided user_id using the Users API and return the user_proficiency_level value
        """
        assignments = self.client.cc_users.list_skills(user_id, skill_category_id=skill["skill_category_id"])
        assignment_for_skill = next(a for a in assignments if a["skill_id"] == skill["skill_id"])
        return assignment_for_skill["user_proficiency_level"]

    def get_users(self, skill) -> str:
        """
        Get users assigned to the provided skills and return them as a comma-separated string
        formatted for the worksheet Skills column.
        For text skills, only the user email addresses are returned.
        For proficiency skills, each assigned user is returned in the format email=proficiency
        """
        entries = []

        for user in self.client.cc_skills.list_users(skill["skill_id"]):
            if skill["skill_type"] == "text":
                entries.append(user["user_email"])
            else:
                proficiency_level = self.get_user_proficiency_level(user["user_id"], skill)
                entries.append(f"{user['user_email']}={proficiency_level}")

        return ",".join(entries)

    def build_model(self, resp):
        model = ZoomCCSkill.safe_build(
            skill_name=resp["skill_name"],
            skill_category_name=resp["skill_category_name"],
            users=self.get_users(resp),
        )

        return model
