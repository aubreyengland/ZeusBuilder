import logging
from typing import List
from urllib.parse import quote_plus
from ..zoomcc_models import ZoomCCUserSkill
from zeus.exceptions import ZeusBulkOpFailed
from zeus.zoom.zoom_simple import ZoomSimpleClient
from zeus.services import BulkSvc, BulkTask, SvcClient

log = logging.getLogger(__name__)


class ZoomCCBulkSvc(BulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.client: ZoomSimpleClient = client
        self.lookup = ZoomCCLookup(client)


class ZoomCCBulkTask(BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomCCBulkSvc = svc


class ZoomCCSvcClient(SvcClient):
    tool = "zoomcc"
    client_cls = ZoomSimpleClient


class ZoomCCLookup:
    def __init__(self, client):
        self.client: ZoomSimpleClient = client
        self.current: dict = {}

    def disposition(self, disposition_name: str) -> dict:
        existing = self.client.cc_dispositions.list()
        match = next(
            (e for e in existing if e["disposition_name"] == disposition_name), None
        )
        if not match:
            raise ZeusBulkOpFailed(f"Disposition {disposition_name} Does Not Exist.")

        return match

    def disposition_set(self, disposition_set_name: str) -> dict:
        existing = self.client.cc_disposition_sets.list()
        match = next(
            (e for e in existing if e["disposition_set_name"] == disposition_set_name), None
        )
        if not match:
            raise ZeusBulkOpFailed(
                f"Disposition Set {disposition_set_name} Does Not Exist."
            )

        return match

    def queue(self, queue_name: str) -> dict:
        existing = self.client.cc_queues.list()
        match = next((e for e in existing if e["queue_name"] == queue_name), None)
        if not match:
            raise ZeusBulkOpFailed(f"Queue {queue_name} Does Not Exist.")

        return match

    def role(self, role_name: str) -> dict:
        existing = self.client.cc_roles.list()
        match = next((e for e in existing if e["role_name"] == role_name), None)
        if not match:
            raise ZeusBulkOpFailed(f"Role {role_name} Does Not Exist.")

        return match

    def skill(self, skill_name: str, skill_category_id: str) -> dict:
        """
        Get the skill with the provided name associated with the provided skill category id.

        A skill category is required for skill lookup because skill names are only unique within
        a skill category.
        """
        existing = self.client.cc_skills.list(skill_category_id=skill_category_id)
        match = next((e for e in existing if e["skill_name"] == skill_name), None)
        if not match:
            raise ZeusBulkOpFailed(f"Skill {skill_name} Does Not Exist.")

        return match

    def skill_by_category_name(self, skill_name: str, skill_category_name: str) -> dict:
        """
        Get the skill with the provided name associated with the provided skill category name.

        A skill category is required for skill lookup because skill names are only unique within
        a skill category.
        """
        skill_category = self.skill_category(skill_category_name)
        try:
            return self.skill(skill_name, skill_category["skill_category_id"])
        except ZeusBulkOpFailed:
            raise ZeusBulkOpFailed(f"Skill {skill_name} does not exist in category {skill_category_name}")

    def skill_category(self, skill_category_name: str) -> dict:
        existing = self.client.cc_skill_categories.list()
        match = next(
            (e for e in existing if e["skill_category_name"] == skill_category_name), None
        )
        if not match:
            raise ZeusBulkOpFailed(f"Skill Category {skill_category_name} Does Not Exist.")

        return match

    def user(self, email: str) -> dict:
        try:
            existing = self.client.cc_users.get(quote_plus(email))
        except Exception:
            raise ZeusBulkOpFailed(f"User {email} Does Not Exist.")

        return existing


class ZoomCCQueueAssignUsersTask(ZoomCCBulkTask):
    queue_type = ""

    def __init__(self, svc, queue, users, queue_type, **kwargs):
        super().__init__(svc, **kwargs)
        self.queue: dict = queue
        self.users: List[dict] = users
        self.queue_type: str = queue_type
        self.has_run = False

    def run(self):
        self._log("run")
        payload = {"user_ids": [user["user_id"] for user in self.users]}
        self.client.cc_queues.assign_users(self.queue_type, self.queue["queue_id"], payload)
        self.has_run = True

    def rollback(self):
        if self.has_run:
            self._log("rollback")
            for user in self.users:
                self.client.cc_queues.unassign_user(self.queue_type, self.queue["queue_id"], user["user_id"])

    def _log(self, op):
        users = ",".join(u.get("user_email", "") for u in self.users)
        log.debug(f"{type(self).__name__} {op}: {self.queue['queue_name']=}, {self.queue_type=}, {users=}")


class ZoomCCQueueRemoveUserTask(ZoomCCBulkTask):

    def __init__(self, svc, queue, user, queue_type, **kwargs):
        super().__init__(svc, **kwargs)
        self.queue: dict = queue
        self.user: dict = user
        self.queue_type: str = queue_type
        self.has_run = False

    def run(self):
        log.debug(
            f"{type(self).__name__} run: {self.queue['queue_name']=}, {self.queue_type=}, {self.user['user_email']=}")
        self.client.cc_queues.unassign_user(self.queue_type, self.queue["queue_id"], self.user["user_id"])
        self.has_run = True

    def rollback(self):
        if self.has_run:
            log.debug(
                f"{type(self).__name__} rollback: {self.queue['queue_name']=}, "
                f"{self.queue_type=}, {self.user['user_email']=}"
            )
            payload = {"user_ids": [self.user["user_id"]]}
            self.client.cc_queues.assign_users(self.queue_type, self.queue["queue_id"], payload)


class ZoomCCDispositionSetCreateTask(ZoomCCBulkTask):
    def __init__(self, svc, disposition_set_name, **kwargs):
        super().__init__(svc, **kwargs)
        self.disposition_set_name = disposition_set_name
        self.disposition_set: dict = {}

    def run(self):
        payload = {"disposition_set_name": self.disposition_set_name}
        log.debug(f"{type(self).__name__} run: {self.disposition_set_name}")
        self.disposition_set = self.client.cc_disposition_sets.create(payload)
        return self.disposition_set

    def rollback(self):
        if self.disposition_set:
            log.debug(f"{type(self).__name__} rollback: {self.disposition_set_name=}")
            self.client.cc_disposition_sets.delete(
                self.disposition_set["disposition_set_id"]
            )


class ZoomCCSkillCreateTask(ZoomCCBulkTask):
    def __init__(self, svc, skill_name, skill_category_id, **kwargs):
        super().__init__(svc, **kwargs)
        self.skill_name: str = skill_name
        self.skill_category_id: str = skill_category_id
        self.created_skill = None

    def run(self) -> dict:
        payload = {
            "skill_name": self.skill_name,
            "skill_category_id": self.skill_category_id,
        }
        log.debug(
            f"{type(self).__name__} run: {self.skill_name=}, {self.skill_category_id=}"
        )
        self.created_skill = self.client.cc_skills.create(payload)
        return self.created_skill

    def rollback(self):
        if self.created_skill:
            log.debug(
                f"{type(self).__name__} rollback: {self.skill_name=}, {self.skill_category_id=}"
            )
            self.client.cc_skills.delete(self.created_skill["skill_id"])


class ZoomCCSkillUpdateTask(ZoomCCBulkTask):
    def __init__(self, svc, new_skill_name, **kwargs):
        super().__init__(svc, **kwargs)
        self.new_skill_name: str = new_skill_name
        self.is_updated = False

    def run(self):
        payload = {"skill_name": self.new_skill_name}
        log.debug(f"{type(self).__name__} run: {self.svc.current=}, {self.new_skill_name}")
        self.client.cc_skills.update(self.svc.current["skill_id"], payload)
        self.is_updated = True

    def rollback(self):
        if self.is_updated:
            log.debug(f"{type(self).__name__} rollback: {self.svc.current=}")
            payload = {"skill_name": self.svc.current["skill_name"]}
            self.client.cc_skills.update(self.svc.current["skill_id"], payload)


class ZoomCCSkillDeleteTask(ZoomCCBulkTask):
    def __init__(self, svc, skill, **kwargs):
        super().__init__(svc, **kwargs)
        self.skill: dict = skill
        self.deleted = False
        self.client = svc.client

    def run(self):
        log.debug(f"{type(self).__name__} run: {self.skill=}")
        self.client.cc_skills.delete(self.skill["skill_id"])
        self.deleted = True

    def rollback(self):
        if self.deleted:
            payload = {
                "skill_name": self.skill["skill_name"],
                "skill_category_id": self.skill["skill_category_id"],
            }
            log.debug(f"{type(self).__name__} rollback: {self.skill=}")
            self.client.cc_skills.create(payload)


class ZoomCCUserSkillsAssignTask(ZoomCCBulkTask):
    def __init__(self, svc, user_id, user_skills, **kwargs):
        super().__init__(svc, **kwargs)
        self.user_id: str = user_id
        self.user_skills: List[ZoomCCUserSkill] = user_skills
        self.is_assigned = False

    def run(self):
        payload = build_user_skills_assign_payload(*self.user_skills)
        log.debug(f"{type(self).__name__} run: {self.user_id=}, {self.user_skills=}")
        self.client.cc_users.assign_skills(self.user_id, payload)
        self.is_assigned = True

    def rollback(self):
        if self.is_assigned:
            log.debug(
                f"{type(self).__name__} rollback: {self.user_id=}, {self.user_skills=}"
            )
            for user_skill in self.user_skills:
                self.client.cc_users.unassign_skill(self.user_id, user_skill.skill_id)


class ZoomCCUserSkillRemoveTask(ZoomCCBulkTask):
    def __init__(self, svc, user_id, user_skill, **kwargs):
        super().__init__(svc, **kwargs)
        self.user_id: str = user_id
        self.user_skill: ZoomCCUserSkill = user_skill
        self.is_removed = False

    def run(self):
        skill_id = self.user_skill.skill_id
        log.debug(f"{type(self).__name__} run: {self.user_id=}, {self.user_skill=}")
        self.client.cc_users.unassign_skill(self.user_id, skill_id)
        self.is_removed = True

    def rollback(self):
        if self.is_removed:
            payload = build_user_skills_assign_payload(self.user_skill)
            log.debug(
                f"{type(self).__name__} rollback: {self.user_id=}, {self.user_skill=}"
            )
            self.client.cc_users.assign_skills(self.user_id, payload)


def build_user_skills_assign_payload(*user_skills) -> dict:
    payload = []

    for user_skill in user_skills:
        entry = {"skill_id": user_skill.skill_id}

        if user_skill.skill_type == "proficiency":
            entry["max_proficiency_level"] = user_skill.user_proficiency_level

        payload.append(entry)

    return {"skills": payload}
