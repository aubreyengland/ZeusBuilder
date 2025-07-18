import logging
from typing import List
from zeus import registry as reg
from .. import zoomcc_models as zm
from collections import defaultdict
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from .shared import (
    ZoomCCBulkSvc,
    ZoomCCBulkTask,
    ZoomCCQueueAssignUsersTask,
    ZoomCCQueueRemoveUserTask,
)

log = logging.getLogger(__name__)


class ZoomCCQueueSvc(ZoomCCBulkSvc):
    """
    parent class for CREATE and UPDATE services with shared methods
    for user and disposition assignment
    """

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: zm.ZoomCCQueue = model
        self.current_user_ids: dict = {"agent": [], "supervisor": []}
        self.current_disposition_ids: list = []
        self.assignments: dict = {"agent": [], "supervisor": [], "disposition": []}

    def get_current_users(self):
        for queue_type in ("agent", "supervisor"):
            users = self.client.cc_queues.list_users(queue_type, self.current["queue_id"])
            self.current_user_ids[queue_type] = [u["user_id"] for u in users]

    def get_current_dispositions(self):
        dispositions = self.client.cc_queues.list_dispositions(self.current["queue_id"])
        self.current_disposition_ids = [d["disposition_id"] for d in dispositions]

    def get_users_for_assignment(self):
        for user_type, user_email in self.model.all_users_list:
            user = self.lookup.user(user_email)
            self.assignments[user_type].append(user)

    def get_dispositions_for_assignment(self):
        for disposition_name in self.model.dispositions_list:
            disposition = self.lookup.disposition(disposition_name)
            self.assignments["disposition"].append(disposition)

    def assign_users(self):
        for queue_type in ("agent", "supervisor"):
            current_user_ids_for_queue_type = self.current_user_ids[queue_type]
            potential_assignments = self.assignments[queue_type]

            to_assign = [
                u for u in potential_assignments
                if u["user_id"] not in current_user_ids_for_queue_type
            ]

            if to_assign:
                task = ZoomCCQueueAssignUsersTask(
                    svc=self,
                    queue=self.current,
                    users=to_assign,
                    queue_type=queue_type,
                )
                task.run()
                self.rollback_tasks.append(task)

    def assign_dispositions(self):
        potentials_assignments = self.assignments["disposition"]

        to_assign = [
            d for d in potentials_assignments
            if d["disposition_id"] not in self.current_disposition_ids
        ]

        if to_assign:
            task = ZoomCCQueueAssignDispositionsTask(self, to_assign)
            task.run()
            self.rollback_tasks.append(task)

    def update_queue(self):
        task = ZoomCCQueueUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("zoomcc", "queues", "CREATE")
class ZoomCCQueueCreateSvc(ZoomCCQueueSvc):

    def run(self):
        self.get_users_for_assignment()
        self.get_dispositions_for_assignment()
        self.create_queue()
        self.update_queue()
        self.assign_users()
        self.assign_dispositions()

    def create_queue(self):
        payload = {
            "queue_name": self.model.queue_name,
            "queue_description": self.model.queue_description,
            "channel_types": [self.model.channel_type.lower()],
        }
        self.current = self.client.cc_queues.create(payload)

    def rollback(self):
        if self.current:
            log.debug(f"{type(self).__name__} rollback: {self.current=}")
            self.client.cc_queues.delete(self.current["queue_id"])


@reg.bulk_service("zoomcc", "queues", "UPDATE")
class ZoomCCQueueUpdateSvc(ZoomCCQueueSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.removals: dict = {"agent": [], "supervisor": [], "disposition": []}

    def run(self):
        self.get_current()
        self.get_users_for_assignment()
        self.get_dispositions_for_assignment()
        self.get_users_for_removal()
        self.get_dispositions_for_removal()
        self.update_queue()
        self.remove_users()
        self.remove_dispositions()
        self.assign_users()
        self.assign_dispositions()

    def get_current(self):
        self.current = self.lookup.queue(self.model.queue_name)
        self.get_current_users()
        self.get_current_dispositions()

    def get_users_for_removal(self):
        for user_type, user_email in self.model.all_users_to_remove_list:
            user = self.lookup.user(user_email)
            self.removals[user_type].append(user)

    def get_dispositions_for_removal(self):
        for disposition_name in self.model.dispositions_to_remove_list:
            disposition = self.lookup.disposition(disposition_name)
            self.removals["disposition"].append(disposition)

    def remove_users(self):
        for queue_type in ("agent", "supervisor"):
            current_user_ids_for_queue_type = self.current_user_ids[queue_type]
            potential_removals = self.removals[queue_type]

            to_remove = [
                u for u in potential_removals
                if u["user_id"] in current_user_ids_for_queue_type
            ]

            for user in to_remove:
                task = ZoomCCQueueRemoveUserTask(
                    svc=self,
                    queue=self.current,
                    user=user,
                    queue_type=queue_type,
                )
                task.run()
                self.rollback_tasks.append(task)

    def remove_dispositions(self):
        potential_removals = self.removals["disposition"]

        to_remove = [
            d for d in potential_removals
            if d["disposition_id"] in self.current_disposition_ids
        ]

        for disposition in to_remove:
            task = ZoomCCQueueRemoveDispositionTask(self, disposition)
            task.run()
            self.rollback_tasks.append(task)


class ZoomCCQueueUpdateTask(ZoomCCBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.update_payload: dict = {}
        self.has_run: bool = False

    def run(self):
        self.build_update_payload()
        log.info(f"{self.update_payload=}")
        log.debug(f"{type(self).__name__} run: {self.model.queue_name=} {self.update_payload=}")
        self.client.cc_queues.update(self.svc.current["queue_id"], self.update_payload)
        self.has_run = True

    def build_update_payload(self):
        queue_name = self.model.new_queue_name or self.model.queue_name
        payload = {
            "queue_name": queue_name,
            "queue_description": self.model.queue_description,
            "channel_types": [self.model.channel_type.lower()],
            "distribution_type": self.get_distribution_type(),
        }

        if self.model.max_wait_time_value:
            payload["max_wait_time"] = zm.parse_time_value_to_seconds(
                self.model.max_wait_time_value
            )

        if self.model.wrap_up_time:
            payload["wrap_up_time"] = self.model.wrap_up_time

        if self.model.max_engagement_in_queue:
            payload["max_engagement_in_queue"] = self.model.max_engagement_in_queue

        # Currently disabled in model due to API issue
        # See https://github.com/cdwlabs/zeus/issues/334
        if self.model.short_abandon_threshold:
            threshold = int(self.model.short_abandon_threshold)
            enable = True if threshold > 0 else False
            payload["short_abandon"] = {"enable": enable, "threshold": threshold}

        self.update_payload = payload

    def get_distribution_type(self):
        for distribution_type in zm.zoomcc_queue_distribution_map:
            distribution_name = zm.zoomcc_queue_distribution_map[distribution_type].lower()
            if self.model.distribution_name.lower() == distribution_name:
                return distribution_type

        raise ZeusBulkOpFailed(
            f"Invalid distribution type: '{self.model.distribution_name}'"
        )

    def rollback(self):
        if self.has_run:
            log.debug(f"{type(self).__name__} rollback: {self.model.queue_name=}")
            payload = self.build_rollback_payload()
            self.client.cc_queues.update(self.svc.current["queue_id"], payload)

    def build_rollback_payload(self) -> dict:
        payload = {}
        for key, old_value in self.svc.current.items():
            if key in self.update_payload:

                if str(self.update_payload[key]) != str(old_value):
                    payload[key] = old_value

        return payload


class ZoomCCQueueAssignDispositionsTask(ZoomCCBulkTask):
    def __init__(self, svc, dispositions, **kwargs):
        super().__init__(svc, **kwargs)
        self.queue: dict = svc.current
        self.dispositions: List[dict] = dispositions
        self.has_run = False

    @property
    def disposition_ids(self):
        return [d["disposition_id"] for d in self.dispositions]

    @property
    def disposition_names(self):
        return [d["disposition_name"] for d in self.dispositions]

    def run(self):
        log.debug(
            f"{type(self).__name__} run: {self.queue['queue_name']=}, {self.disposition_names=}"
        )
        payload = {"disposition_ids": self.disposition_ids}
        self.client.cc_queues.assign_dispositions(self.queue["queue_id"], payload)
        self.has_run = True

    def rollback(self):
        if self.has_run:
            log.debug(
                f"{type(self).__name__} rollback: {self.queue['queue_name']=}, {self.disposition_names=}"
            )
            for disposition_id in self.disposition_ids:
                self.client.cc_queues.unassign_disposition(
                    self.queue["queue_id"], disposition_id
                )


class ZoomCCQueueRemoveDispositionTask(ZoomCCBulkTask):
    def __init__(self, svc, disposition, **kwargs):
        super().__init__(svc, **kwargs)
        self.queue: dict = svc.current
        self.disposition: dict = disposition
        self.has_run = False

    def run(self):
        log.debug(
            f"{type(self).__name__} run: {self.queue['queue_name']=}, "
            f"{self.disposition['disposition_name']=}"
        )
        self.client.cc_queues.unassign_disposition(
            self.queue["queue_id"], self.disposition["disposition_id"]
        )
        self.has_run = True

    def rollback(self):
        if self.has_run:
            log.debug(
                f"{type(self).__name__} rollback: {self.queue['queue_name']=}, {self.disposition=}"
            )
            payload = {"disposition_ids": [self.disposition["disposition_id"]]}
            self.client.cc_queues.assign_dispositions(self.queue["queue_id"], payload)


@reg.bulk_service("zoomcc", "queues", "DELETE")
class ZoomCCQueueDeleteSvc(ZoomCCBulkSvc):

    def run(self):
        to_delete = self.lookup.queue(self.model.queue_name)
        self.client.cc_queues.delete(to_delete["queue_id"])


@reg.browse_service("zoomcc", "queues")
class ZoomCCQueueBrowseSvc(BrowseSvc):
    """
    Collect Zoom Contact Center queues for a browse operation.
    To limit the number of request, this does not include
    user or disposition assignments.
    """

    def run(self):
        rows = []
        builder = ZoomCCQueueModelBuilder(self.client, lookup_id_fields=False)
        for resp in self.client.cc_queues.list():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoomcc", "queues")
class ZoomCCQueueExportSvc(ExportSvc):
    """
    Collect Zoom Contact Center queues for an export operation
    including user or disposition assignments.
    """

    def run(self):
        rows = []
        errors = []
        data_type = zm.ZoomCCQueue.schema()["data_type"]
        builder = ZoomCCQueueModelBuilder(self.client, lookup_id_fields=True)

        for resp in self.client.cc_queues.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("queue_name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomCCQueueModelBuilder:
    """
    Collect Zoom Contact Center queue details and create
    models for browse/export operations.

    The LIST request only provides name and channel type so a GET request
    for each queue is required.

    Additional API requests are necessary to include user and disposition assignments.
    These are only made if the `include_assignments` parameter is True.
    """

    def __init__(self, client, lookup_id_fields=False):
        self.client = client
        self.lookup_id_fields = lookup_id_fields
        self.agent_queues_by_queue_id = defaultdict(list)
        self.supervisor_queues_by_queue_id = defaultdict(list)

    def build_model(self, resp: dict):
        queue = self.client.cc_queues.get(resp["queue_id"])
        channel_type = queue["channel_types"][0]

        agents = self.get_queue_agents(queue)
        supervisors = self.get_queue_supervisors(queue)
        dispositions = self.get_queue_dispositions(queue)
        distribution_name = self.get_distribution_name(queue)
        max_wait_time_value = self.get_max_wait_time_value(queue)
        short_abandon_threshold = self.get_short_abandon_threshold(queue)

        model = zm.ZoomCCQueue.safe_build(
            queue_name=queue["queue_name"],
            agents=agents,
            supervisors=supervisors,
            channel_type=channel_type,
            dispositions=dispositions,
            distribution_name=distribution_name,
            max_wait_time_value=max_wait_time_value,
            queue_description=queue["queue_description"],
            wrap_up_time=queue.get("wrap_up_time") or "",
            short_abandon_threshold=short_abandon_threshold,
            max_engagement_in_queue=queue.get("max_engagement_in_queue") or "",
        )

        return model

    @staticmethod
    def get_max_wait_time_value(queue) -> str:
        formatted_value = ""

        if "max_wait_time" in queue:
            formatted_value = zm.convert_seconds_to_workbook_value(queue["max_wait_time"])

        return formatted_value

    @staticmethod
    def get_short_abandon_threshold(queue) -> str:
        threshold = ""
        if deep_get(queue, ["short_abandon", "enable"], default=False):
            threshold = deep_get(queue, ["short_abandon", "threshold"], default="")

        return threshold

    @staticmethod
    def get_distribution_name(queue) -> str:
        distribution_type = queue["distribution_type"]
        distribution_name = zm.zoomcc_queue_distribution_map.get(
            distribution_type, "NOTFOUND"
        )
        return distribution_name

    def get_queue_agents(self, queue) -> str:
        agent_emails = ""

        if self.lookup_id_fields:
            agents = [
                item["user_email"]
                for item in self.client.cc_queues.list_agents(queue["queue_id"])
            ]
            agent_emails = ",".join(agents)

        return agent_emails

    def get_queue_supervisors(self, queue) -> str:
        supervisor_emails = ""

        if self.lookup_id_fields:
            supervisors = [
                item["user_email"]
                for item in self.client.cc_queues.list_supervisors(queue["queue_id"])
            ]
            supervisor_emails = ",".join(supervisors)

        return supervisor_emails

    def get_queue_dispositions(self, queue) -> str:
        disposition_names = ""

        if self.lookup_id_fields:
            dispositions = [
                item["disposition_name"]
                for item in self.client.cc_queues.list_dispositions(queue["queue_id"])
            ]
            disposition_names = ",".join(dispositions)

        return disposition_names
