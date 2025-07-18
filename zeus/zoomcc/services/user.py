import logging
from zeus import registry as reg
from typing import List, Dict, Tuple
from collections import defaultdict
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from ..zoomcc_models import ZoomCCUser, ZoomCCUserSkill
from zeus.shared.data_type_models import yn_to_bool
from .shared import (
    ZoomCCBulkSvc,
    ZoomCCQueueAssignUsersTask,
    ZoomCCQueueRemoveUserTask,
    ZoomCCUserSkillsAssignTask,
    ZoomCCUserSkillRemoveTask,
)

log = logging.getLogger(__name__)


def build_payload(model: ZoomCCUser, role: dict) -> dict:
    """Create the payload for a user profile create or update request from the model."""
    return {
        "user_email": model.user_email,
        "role_id": role["role_id"],
        "user_access": model.user_access,
        "client_integration": model.client_integration,
        "channel_settings": {
            "multi_channel_engagements": {
                "enable": yn_to_bool(model.multi_channel_engagements),
                "max_agent_load": model.max_agent_load,
            },
            "concurrent_message_capacity": model.concurrent_message_capacity,
        },
    }


@reg.bulk_service("zoomcc", "users", "CREATE")
class ZoomCCUserCreateSvc(ZoomCCBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.skills_to_assign: List[ZoomCCUserSkill] = []
        self.queues_to_assign: List[Tuple[str, dict]] = []

    def run(self):
        self.get_skills_for_assignment()
        self.get_queues_for_assignment()
        self.create_user()
        self.assign_skills()
        self.assign_queues()

    def get_skills_for_assignment(self):
        for skill_category_name, skill_name, proficiency in self.model.skills_list:

            resp = self.lookup.skill_by_category_name(skill_name, skill_category_name)

            user_skill = ZoomCCUserSkill(
                skill_id=resp["skill_id"],
                skill_type=resp["skill_type"],
                skill_name=resp["skill_name"],
                skill_category_name=resp["skill_category_name"],
                user_proficiency_level=proficiency,
            )

            self.skills_to_assign.append(user_skill)

    def get_queues_for_assignment(self):
        for queue_type, queue_name in self.model.all_queues_list:
            queue = self.lookup.queue(queue_name)
            self.queues_to_assign.append((queue_type, queue))

    def create_user(self):
        role = self.lookup.role(self.model.role_name)
        payload = build_payload(self.model, role)
        self.current = self.client.cc_users.create(payload)

    def assign_skills(self):
        if self.skills_to_assign:
            task = ZoomCCUserSkillsAssignTask(self, self.current["user_id"], self.skills_to_assign)
            task.run()

    def assign_queues(self):
        for queue_type, queue in self.queues_to_assign:
            task = ZoomCCQueueAssignUsersTask(
                self,
                queue,
                users=[self.current],
                queue_type=queue_type,
            )
            task.run()

    def rollback(self):
        """No need to rollback tasks before deleting user."""
        if self.current:
            log.debug(f"{type(self).__name__} rollback: {self.current['user_email']=}")
            self.client.cc_users.delete(self.current["user_id"])


@reg.bulk_service("zoomcc", "users", "UPDATE")
class ZoomCCUserUpdateSvc(ZoomCCBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: ZoomCCUser = model
        self.current_skills: Dict[tuple, ZoomCCUserSkill] = {}
        self.skills_to_assign: List[ZoomCCUserSkill] = []
        self.skills_to_remove: List[ZoomCCUserSkill] = []
        self.queues_to_assign: List[Tuple[str, dict]] = []
        self.queues_to_remove: List[Tuple[str, dict]] = []
        self.is_updated = False

    def run(self):
        self.current = self.lookup.user(self.model.user_email)
        self.get_current_skills()
        self.get_skills_for_removal()
        self.get_queues_for_removal()
        self.get_skills_for_assignment()
        self.get_queues_for_assignment()
        self.update_user()
        self.remove_skills()
        self.remove_queues()
        self.assign_skills()
        self.assign_queues()

    def get_current_skills(self):
        for item in self.client.cc_users.list_skills(self.current["user_id"]):
            user_skill = ZoomCCUserSkill.parse_obj(item)
            key = (user_skill.skill_category_name, user_skill.skill_name)
            self.current_skills[key] = user_skill

    def get_skills_for_removal(self):
        for skill_category_name, skill_name in self.model.skills_to_remove_list:
            to_remove = self.current_skills.get((skill_category_name, skill_name))
            if to_remove:
                self.skills_to_remove.append(to_remove)

    def get_skills_for_assignment(self):
        """
        Parse the model.skills_list to build proposed user skill assignments.
        For each, check for a current user skill assignment for the skill.
        If no current assignment exists, add the proposed_user_skill for new assignment

        If a current assignment exists and differs from the proposed assignment, add
        the proposed_user_skill for assignment and add the current_user_skill for removal.
        This allows for proficiency value updates.

        If the current assignment is identical to the proposed assignment, do nothing.

        TODO: Parse skill category name and do lookup to get skill_category_id
              to include in skill lookup
        """
        for skill_category_name, skill_name, proficiency in self.model.skills_list:

            current_user_skill = self.current_skills.get((skill_category_name, skill_name))

            # Use current_user_skill to build proposed_user_skill if it exists
            # to avoid lookup call
            if current_user_skill:
                skill_resp = current_user_skill.dict()
            else:
                skill_resp = self.lookup.skill_by_category_name(skill_name, skill_category_name)

            proposed_user_skill = ZoomCCUserSkill(
                skill_id=skill_resp["skill_id"],
                skill_type=skill_resp["skill_type"],
                skill_name=skill_resp["skill_name"],
                skill_category_name=skill_resp["skill_category_name"],
                user_proficiency_level=proficiency,
            )

            if not current_user_skill:
                self.skills_to_assign.append(proposed_user_skill)

            elif current_user_skill != proposed_user_skill:
                self.skills_to_remove.append(current_user_skill)
                self.skills_to_assign.append(proposed_user_skill)

    def get_queues_for_removal(self):
        """
        Remove specified queues from the user.
        Current assignment not verified as unassign API call succeeds
        if queue is not assigned.
        """
        for queue_type, queue_name in self.model.all_queues_to_remove_list:
            queue = self.lookup.queue(queue_name)
            if self.lookup_current_queue_assignment(queue_type, queue):
                self.queues_to_remove.append((queue_type, queue))

    def get_queues_for_assignment(self):
        for queue_type, queue_name in self.model.all_queues_list:
            queue = self.lookup.queue(queue_name)
            if not self.lookup_current_queue_assignment(queue_type, queue):
                self.queues_to_assign.append((queue_type, queue))

    def lookup_current_queue_assignment(self, queue_type, queue):
        for assigned_user in self.client.cc_queues.list_users(queue_type, queue["queue_id"]):
            if self.current["user_id"] == assigned_user["user_id"]:
                return assigned_user

    def update_user(self):
        role = self.lookup.role(self.model.role_name)
        payload = build_payload(self.model, role)
        self.client.cc_users.update(self.current["user_id"], payload)
        self.is_updated = True

    def remove_skills(self):
        for user_skill in self.skills_to_remove:
            task = ZoomCCUserSkillRemoveTask(self,  self.current["user_id"], user_skill)
            task.run()
            self.rollback_tasks.append(task)

    def assign_skills(self):
        if self.skills_to_assign:
            task = ZoomCCUserSkillsAssignTask(self, self.current["user_id"], self.skills_to_assign)
            task.run()
            self.rollback_tasks.append(task)

    def remove_queues(self):
        for queue_type, queue in self.queues_to_remove:
            task = ZoomCCQueueRemoveUserTask(
                self,
                queue,
                user=self.current,
                queue_type=queue_type,
            )
            task.run()
            self.rollback_tasks.append(task)

    def assign_queues(self):
        for queue_type, queue in self.queues_to_assign:
            task = ZoomCCQueueAssignUsersTask(
                self,
                queue,
                users=[self.current],
                queue_type=queue_type,
            )
            task.run()
            self.rollback_tasks.append(task)

    def rollback(self):
        super().rollback()
        if self.is_updated:
            user_id = self.current["user_id"]
            payload = {
                "user_email": self.current["user_email"],
                "role_id": self.current["role_id"],
                "user_access": self.current["user_access"],
                "client_integration": self.current["client_integration"],
                "channel_settings": self.current["channel_settings"],
            }

            log.debug(f"{type(self).__name__} Rollback: {user_id=}")
            self.client.cc_users.update(user_id, payload)


@reg.bulk_service("zoomcc", "users", "DELETE")
class ZoomCCUserDeleteSvc(ZoomCCBulkSvc):

    def run(self):
        to_delete = self.lookup.user(self.model.user_email)
        self.client.cc_users.delete(to_delete["user_id"])


@reg.browse_service("zoomcc", "users")
class ZoomCCUserBrowseSvc(BrowseSvc):
    """
    Collect Zoom Contact Center users for a browse operation.
    To limit the number of request, this does not include skill
    or queue details.
    """

    def run(self):
        rows = []
        builder = ZoomCCUserModelBuilder(self.client)

        for resp in self.client.cc_users.list():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoomcc", "users")
class ZoomCCUserExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomCCUser.schema()["data_type"]
        builder = ZoomCCUserModelBuilder(self.client)

        for resp in self.client.cc_users.list():
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("user_email", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomCCUserModelBuilder:
    """
    Collect Zoom Contact Center user details and create
    models for export operations.

    Basic user details come from LIST contact center users

    Assigned skills require a GET assigned skills request for each user

    Queues are not available through the user API and require a LIST queues
    to get all queues followed by a GET assigned agents and GET assigned supervisors
    for each queue_id.
    """

    def __init__(self, client):
        self.client = client
        self._queues = []
        self._agent_queues_by_user_id = defaultdict(list)
        self._supervisor_queues_by_user_id = defaultdict(list)

    @property
    def queues(self):
        if not self._queues:
            self._queues = list(self.client.cc_queues.list())
        return self._queues

    @property
    def agent_queues_by_user_id(self):
        if not self._agent_queues_by_user_id:
            for queue in self.queues:
                for item in self.client.cc_queues.list_agents(queue["queue_id"]):
                    self._agent_queues_by_user_id[item["user_id"]].append(queue["queue_name"])

        return self._agent_queues_by_user_id

    @property
    def supervisor_queues_by_user_id(self):
        if not self._supervisor_queues_by_user_id:
            for queue in self.queues:
                for item in self.client.cc_queues.list_supervisors(queue["queue_id"]):
                    self._supervisor_queues_by_user_id[item["user_id"]].append(queue["queue_name"])

        return self._supervisor_queues_by_user_id

    # def populate_queue_maps(self):
    #     """
    #     Queue assignment type is not available through the user API, this
    #     info is available through the queues using the list queue agents
    #     and list queue supervisors endpoints for each queue ID.
    #
    #     This is done for every queue with queue names saved as a list
    #     keyed by user_id for dictionary lookup
    #     """
    #     for queue in self.client.cc_queues.list():
    #         queue_name = queue["queue_name"]
    #         queue_id = queue["queue_id"]
    #
    #         for item in self.client.cc_queues.list_agents(queue_id):
    #             self.agent_queues_by_user_id[item["user_id"]].append(queue_name)
    #
    #         for item in self.client.cc_queues.list_supervisors(queue_id):
    #             self.supervisor_queues_by_user_id[item["user_id"]].append(queue_name)
    # def build_models(self):
    #     models = []
    #     self.populate_queue_maps()
    #
    #     for user in self.client.cc_users.list():
    #         model = self.build_model(user)
    #         models.append(model)
    #
    #     return models

    @staticmethod
    def summary_data(resp):
        concurrent_message_capacity = deep_get(
            resp, "channel_settings.concurrent_message_capacity", default="0"
        )
        multi_channel_engagements = deep_get(
            resp, "channel_settings.multi_channel_engagements.enable", default=False
        )
        max_agent_load = deep_get(
            resp,
            "channel_settings.multi_channel_engagements.max_agent_load",
            default="",
        )

        return dict(
            max_agent_load=max_agent_load,
            multi_channel_engagements=multi_channel_engagements,
            concurrent_message_capacity=concurrent_message_capacity,
            **resp,
        )

    def build_model(self, resp: dict):
        return ZoomCCUser.safe_build(
                skills="",
                agent_queues="",
                supervisor_queues="",
                **self.summary_data(resp),
        )

    def build_detailed_model(self, resp: dict):
        user_id = resp["user_id"]

        summary_data = self.summary_data(resp)

        skills = ",".join(self.get_skill_assignments(user_id))
        agent_queues = ",".join(self.agent_queues_by_user_id[user_id])
        supervisor_queues = ",".join(self.supervisor_queues_by_user_id[user_id])

        return ZoomCCUser.safe_build(
            skills=skills,
            agent_queues=agent_queues,
            supervisor_queues=supervisor_queues,
            **summary_data,
        )

    def get_skill_assignments(self, user_id) -> list:
        """
        Get the skills assigned to the provided user_id and format them
        as expected by the model.

        Proficiency skills are formatted as skill_category:skill_name=user_proficiency_level.
        Text skills are formatted as skill_category:skill_name.
        """
        skill_assignments = []

        for resp in self.client.cc_users.list_skills(user_id):
            name = f"{resp['skill_category_name']}:{resp['skill_name']}"

            if "user_proficiency_level" in resp:
                assignment = f"{name}={resp['user_proficiency_level']}"
            else:
                assignment = name

            skill_assignments.append(assignment)

        return skill_assignments
