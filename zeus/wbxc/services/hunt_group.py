import re
import logging
from copy import deepcopy
from zeus import registry as reg
from zeus.exceptions import ZeusBulkOpFailed
from zeus.shared.helpers import deep_get
from zeus.shared import request_builder as rb
from .shared import WbxcBulkSvc, WbxcBulkTask, build_number_lookup_params
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from zeus.services import BrowseSvc, ExportSvc, DetailSvc, UploadTask, RowLoadResp
from zeus.wbxc.wbxc_models.hunt_groups import PayloadAgent, PayloadAltNum, WbxcHuntGroup, WbxcHuntGroupAgent, WbxcHuntGroupAltNumber

log = logging.getLogger(__name__)


def build_payload(
    model_data: dict,
    current_data: dict,
    agent_action: str,
    model_agents: list[PayloadAgent] | None,
):
    payload_fields = [
        rb.ChangedField("name"),
        rb.ChangedField("phoneNumber"),
        rb.ChangedField("extension"),
        rb.ChangedField("languageCode"),
        rb.ChangedField("firstName"),
        rb.ChangedField("lastName"),
        rb.ChangedField("timeZone"),
        rb.ChangedField("huntGroupCallerIdForOutgoingCallsEnabled", "allow_number_as_clid"),
        rb.ChangedField("callPolicies"),
        rb.ValuedField("agents"),
    ]

    agents = build_agents_payload(
        agent_action=agent_action,
        model_agents=model_agents,
        current_agents=current_data.get("agents", []),
    )
    call_policy = build_call_policy_payload(
        model_data=model_data,
        current_call_policy=current_data.get("callPolicies", {}),
    )

    return rb.RequestBuilder(
        fields=payload_fields,
        data=model_data,
        current=current_data,
        agents=agents,
        callPolicies=call_policy,
    )


def build_call_policy_payload(
    model_data: dict, current_call_policy: dict | None = None
) -> rb.RequestBuilder | None:
    """
    Create a request for the callPolicies object of a hunt group
    CREATE/UPDATE request.

    This includes simple properties and nested objects for forward no answer, busy and unreachable
    (business continuity). The forwarding objects are built as separate RequestBuilder
    instances.

    The structure of the request is:
    ```
    {
        "policy": str,
        "waitingEnabled": bool,
        "allowMembersToControlGroupBusyEnabled": bool,
        "groupBusyEnabled": bool,
        "businessContinuity": { ... },
        "businessContinuityRedirect": { ... },
        "busyRedirect": { ... },
        "noAnswer": { ... }
    }
    ```

    Args:
        model_data (dict): Dictionary created from a WbxcHuntGroup model
        current_call_policy (dict | None): GET response for the current hunt group (for UPDATE's)
         or None (for CREATEs)

    Returns:
        (RequestBuilder | None): RequestBuilder instance or None if the RequestBuilder includes no
         changes/values.
    """
    current_call_policy = current_call_policy or {}

    na_req = rb.RequestBuilder(
        fields=[
            rb.ChangedField("nextAgentEnabled", "advance_to_next_agent"),
            rb.ChangedField("nextAgentRings", "advance_after_rings"),
            rb.ChangedField("forwardEnabled", "forward_na_enabled"),
            rb.ChangedField("numberOfRings", "forward_na_rings"),
            rb.ChangedField("destination", "forward_na_destination"),
            rb.ChangedField("destinationVoicemailEnabled", "forward_na_vm"),
        ],
        data=model_data,
        current=current_call_policy,
    )

    busy_req = rb.RequestBuilder(
        fields=[
            rb.ChangedField("enabled", "forward_busy_enabled"),
            rb.ChangedField("destination", "forward_busy_destination"),
            rb.ChangedField("destinationVoicemailEnabled", "forward_busy_vm"),
        ],
        data=model_data,
        current=current_call_policy,
    )

    ur_req = rb.RequestBuilder(
        [
            rb.ChangedField("enabled", "forward_ur_enabled"),
            rb.ChangedField("destination", "forward_ur_destination"),
            rb.ChangedField("destinationVoicemailEnabled", "forward_ur_vm"),
        ],
        data=model_data,
        current=current_call_policy,
    )

    call_policy_fields = [
        rb.ChangedField("policy", "hunt_policy"),
        rb.ChangedField("waitingEnabled", "advance_when_busy"),
        rb.ChangedField("groupBusyEnabled", "hunt_busy_enabled"),
        rb.ChangedField("allowMembersToControlGroupBusyEnabled", "hunt_busy_allow_users"),
        rb.ChangedField("noAnswer"),
        rb.ChangedField("busyRedirect"),
        rb.ChangedField("businessContinuityRedirect"),
    ]
    req = rb.RequestBuilder(
        fields=call_policy_fields,
        data=model_data,
        current=current_call_policy,
        noAnswer=na_req,
        busyRedirect=busy_req,
        businessContinuityRedirect=ur_req,
    )
    if req.payload_is_changed():
        return req

    return None


def build_agents_payload(
    agent_action: str,
    model_agents: list[PayloadAgent],
    current_agents=list[PayloadAgent] | None,
) -> list[PayloadAgent]:
    """
    Create the agents payload for a hunt group CREATE or UPDATE request.
    The payload contents depend on the agent_action value.
    - REPLACE: The provided agents is the payload value. No need to consider current_agents.
    - ADD: The provided agents are appended to current if the entry does not already exist in current_agents.
    - REMOVE: The provided agents are removed from current if they exist.

    Args:
        agent_action (str): ADD, REPLACE, REMOVE
        model_agents (list): List of IDs/weight dicts
        current_agents (list): List of IDs/weight dicts

    Returns:
        (list): List of IDs/weight dicts
    """
    current_agents = current_agents or []

    if not agent_action or not model_agents:
        return []

    def agents_by_id(agents):
        return {agent["id"]: agent.get("weight", 0) for agent in agents}

    if agent_action == "REPLACE":
        # Replace existing with provided
        payload_by_id = agents_by_id(model_agents)

    elif agent_action == "REMOVE":
        # Remove provided agents from existing, if present
        payload_by_id = agents_by_id(current_agents)
        for entry in model_agents:
            payload_by_id.pop(entry["id"], None)

    else:
        # ADD action
        # append agents to current agents, ensuring no duplicates
        payload_by_id = agents_by_id(current_agents)
        for entry in model_agents:
            if payload_by_id.get(entry["id"]) != entry["weight"]:
                payload_by_id[entry["id"]] = entry["weight"]

    if payload_by_id == agents_by_id(current_agents):
        # If no change, return empty list so ValuedField will be excluded from payload
        return []

    return [{"id": id_, "weight": weight} for id_, weight in payload_by_id.items()]


def build_alternate_numbers_for_payload(
    model: WbxcHuntGroup, current_alt_number_settings=None
) -> list[PayloadAltNum]:
    current_alt_number_settings = current_alt_number_settings or {}
    current_alt_numbers = {
        item["phoneNumber"]: item.get("ringPattern", "NORMAL")
        for item in current_alt_number_settings.get("alternateNumbers") or []
    }
    payload_alt_numbers = deepcopy(current_alt_numbers)

    if model.alternate_number_action == "REPLACE":
        payload_alt_numbers = {altnum.phoneNumber: altnum.ringPattern for altnum in model.alternate_numbers}

    elif model.alternate_number_action == "REMOVE":
        for item in model.alternate_numbers:
            payload_alt_numbers.pop(item.phoneNumber, None)

    else:
        for altnum in model.alternate_numbers:
            if payload_alt_numbers.get(altnum.phoneNumber) != altnum.ringPattern:
                payload_alt_numbers[altnum.phoneNumber] = altnum.ringPattern

    if payload_alt_numbers == current_alt_numbers:
        return []

    return [
        {"phoneNumber": number, "ringPattern": pattern}
        for number, pattern in payload_alt_numbers.items()
    ]


@reg.bulk_service("wbxc", "hunt_groups", "CREATE")
class WbxcHuntGroupCreateSvc(WbxcBulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: WbxcHuntGroup = model
        self.client: WbxcSimpleClient = client
        self.payload_agents: list[dict] = []
        self.location: dict = {}

    def run(self):
        self.location = self.lookup.location(self.model.location_name)
        self.get_agents_to_add()
        self.create_hunt_group()
        self.add_alternate_numbers()

    def get_agents_to_add(self):
        for agent in self.model.agents:
            number = self.lookup_agent_number(agent.number)
            self.payload_agents.append(
                {"id": number["owner"]["id"], "weight": agent.weight}
            )

    def lookup_agent_number(self, number):
        for params in build_number_lookup_params(number):
            try:
                return self.lookup.number(**params)
            except ZeusBulkOpFailed:
                continue

        raise ZeusBulkOpFailed(f"Number: {number} not found")

    def create_hunt_group(self):
        model_data = self.model.to_payload(exclude={"agents"}, drop_unset=True)
        builder = build_payload(
            model_data=model_data,
            current_data={},
            agent_action=self.model.agent_action,
            model_agents=self.payload_agents,
        )
        payload = builder.payload()
        self.current = self.client.huntgroups.create(
            location_id=self.location["id"], payload=payload
        )

    def add_alternate_numbers(self):
        task = WbxcHuntGroupAltNumberTask(self)
        task.run()

    def rollback(self) -> None:
        if self.current:
            self.client.huntgroups.delete(self.location["id"], self.current["id"])


@reg.bulk_service("wbxc", "hunt_groups", "UPDATE")
class WbxcHuntGroupUpdateSvc(WbxcBulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: WbxcHuntGroup = model
        self.client: WbxcSimpleClient = client
        self.location: dict = {}
        self.payload_agents: list[PayloadAgent] = []

    def run(self):
        self.get_current()
        self.get_agents_for_update()
        self.update_hunt_group()
        self.update_alternate_numbers()

    def get_current(self):
        """
        Save location ID and name from LIST response into
        self.location for use by the update tasks
        """
        resp = self.lookup.hunt_group(self.model.name)
        self.location = {"id": resp["locationId"], "locationName": resp["locationName"]}
        self.current = self.client.huntgroups.get(resp["locationId"], resp["id"])

    def get_agents_for_update(self):
        for agent in self.model.agents:
            params = build_number_lookup_params(agent.number)
            number = self.lookup_agent_number(agent.number)
            agent_id = number["owner"]["id"]
            self.payload_agents.append({"id": agent_id, "weight": agent.weight})

    def lookup_agent_number(self, number):
        for params in build_number_lookup_params(number):
            try:
                return self.lookup.number(**params)
            except ZeusBulkOpFailed:
                continue

        raise ZeusBulkOpFailed(f"Number: {number} not found")
    def update_hunt_group(self):
        task = WbxcHuntGroupUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_alternate_numbers(self):
        task = WbxcHuntGroupAltNumberTask(self)
        task.run()


class WbxcHuntGroupAltNumberTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcHuntGroupCreateSvc | WbxcHuntGroupUpdateSvc = svc
        self.has_run: bool = False
        self.builder = None
        self.fields = [
            rb.ChangedField("distinctiveRing", alias="distinctiveRingEnabled"),
            rb.ValuedField("alternateNumbers"),
        ]

    def run(self):
        self.build_payload()
        payload = self.builder.payload()
        if payload:
            self.client.huntgroups.update(
                location_id=self.svc.location["id"],
                huntgroup_id=self.svc.current["id"],
                payload=payload,
            )
            self.has_run = True

    def build_payload(self):
        current_alt_number_settings = self.svc.current.get("alternateNumberSettings", {})
        payload_numbers = build_alternate_numbers_for_payload(
            model=self.model,
            current_alt_number_settings=current_alt_number_settings,
        )

        model_data = self.model.to_payload(drop_unset=True)
        self.builder = rb.RequestBuilder(
            fields=self.fields,
            data=model_data,
            current=current_alt_number_settings,
            alternateNumbers=payload_numbers,
        )

    def rollback(self) -> None:
        if self.has_run:
            rollback_payload = self.builder.rollback()
            if rollback_payload:
                self.client.huntgroups.update(
                    location_id=self.svc.location["id"],
                    huntgroup_id=self.svc.current["id"],
                    payload=rollback_payload,
                )


class WbxcHuntGroupUpdateTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcHuntGroupUpdateSvc = svc
        self.has_run: bool = False
        self.builder = None

    def run(self):
        self.build_payload()
        payload = self.builder.payload()
        if payload:
            self.client.huntgroups.update(
                location_id=self.svc.location["id"],
                huntgroup_id=self.svc.current["id"],
                payload=payload,
            )
            self.has_run = True

    def build_payload(self):
        model_data = self.model.to_payload(exclude={"agents"}, drop_unset=True)
        self.builder = build_payload(
            model_data=model_data,
            current_data=self.svc.current,
            agent_action=self.model.agent_action,
            model_agents=self.svc.payload_agents,
        )

    def rollback(self) -> None:
        if self.has_run:
            rollback_payload = self.builder.rollback()
            if rollback_payload:
                self.client.huntgroups.update(
                    location_id=self.svc.location["id"],
                    huntgroup_id=self.svc.current["id"],
                    payload=rollback_payload,
                )


@reg.bulk_service("wbxc", "hunt_groups", "DELETE")
class WbxcHuntGroupDeleteSvc(WbxcBulkSvc):
    def run(self):
        self.current = self.lookup.hunt_group(self.model.name)
        self.client.huntgroups.delete(
            location_id=self.current["locationId"], huntgroup_id=self.current["id"]
        )


@reg.upload_task("wbxc", "hunt_groups")
class WbxcHuntGroupUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            row["agents"] = self.build_agents(row)
            row["alternate_numbers"] = self.build_alternate_numbers(row)
        except Exception as exc:
            return RowLoadResp(index=idx, error=str(exc))

        return super().validate_row(idx, row)

    @staticmethod
    def build_agents(row):
        agents = []
        for col_header, value in row.items():
            if m := re.search(r"Agent\s*(\d+)", col_header):
                idx = m.group(1)

                if "=" in value:
                    number, weight_str = re.split(r"\s*=\s*", value)
                    try:
                        weight = int(weight_str)
                    except Exception:
                        raise ValueError(f"Weight: '{weight_str}' is invalid")
                else:
                    number, weight = value, 0

                if number:
                    agents.append(dict(idx=idx, number=number, weight=weight))

        return agents

    @staticmethod
    def build_alternate_numbers(row):
        altnums = []
        for col_header, value in row.items():
            if m := re.search(r"Alternate\s+Number\s*(\d+)", col_header):
                idx = m.group(1)

                if "=" in value:
                    number, pattern = re.split(r"\s*=\s*", value)
                else:
                    number, pattern = value, "REGULAR"

                if number:
                    altnums.append(dict(idx=idx, phoneNumber=number, ringPattern=pattern))

        return altnums


@reg.browse_service("wbxc", "hunt_groups")
class WbxcHuntGroupBrowseSvc(BrowseSvc):
    def run(self):
        rows = []

        for resp in self.client.huntgroups.list():
            model = self.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            row["location_id"] = resp["locationId"]
            rows.append(row)

        return rows

    @staticmethod
    def build_model(resp):
        return WbxcHuntGroup.safe_build(
            name=resp["name"],
            location_name=resp["locationName"],
            extension=resp.get("extension", ""),
            phoneNumber=resp.get("phoneNumber", ""),
        )


@reg.detail_service("wbxc", "hunt_groups")
class WbxcHuntGroupDetailSvc(DetailSvc):
    def run(self):
        builder = WbxcHuntGroupModelBuilder()
        detail_id = self.browse_row["detail_id"]
        location_id = self.browse_row["location_id"]
        location_name = self.browse_row["location_name"]
        resp = self.client.huntgroups.get(location_id, detail_id)
        model = builder.build_model(resp, location_name)
        detail_data = model.dict()
        # detail_data["agent_details"] = resp.get("agents") or []
        detail_data["alternate_number_details"] = deep_get(
            resp, "alternateNumberSettings.alternateNumbers", default=[]
        )

        return detail_data


@reg.export_service("wbxc", "hunt_groups")
class WbxcHuntGroupExportSvc(ExportSvc):
    def run(self):
        rows = []
        errors = []
        data_type = WbxcHuntGroup.schema()["data_type"]
        builder = WbxcHuntGroupModelBuilder()

        for item in self.client.huntgroups.list():
            try:
                resp = self.client.huntgroups.get(item["locationId"], item["id"])
                model = builder.build_model(resp, item["locationName"])
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": item.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcHuntGroupModelBuilder:
    def build_model(self, resp, location_name):
        hunt_busy_enabled = deep_get(
            resp, "callPolicies.groupBusyEnabled", default="UNKNOWN"
        )
        hunt_policy = deep_get(resp, "callPolicies.policy", default="UNKNOWN")
        hunt_busy_allow_users = deep_get(
            resp, "callPolicies.allowMembersToControlGroupBusyEnabled", default="UNKNOWN"
        )
        advance_when_busy = deep_get(resp, "callPolicies.waitingEnabled", default="UNKNOWN")
        distinctiveRing = deep_get(
            resp, "alternateNumberSettings.distinctiveRingEnabled", default=""
        )

        return WbxcHuntGroup.safe_build(
            name=resp["name"],
            extension=resp.get("extension", ""),
            phoneNumber=resp.get("phoneNumber", ""),
            location_name=location_name,
            firstName=resp.get("firstName", ""),
            lastName=resp.get("lastName", ""),
            languageCode=resp.get("languageCode", ""),
            timeZone=resp.get("timeZone", ""),
            allow_number_as_clid=resp.get("huntGroupCallerIdForOutgoingCallsEnabled", ""),
            distinctiveRing=distinctiveRing,
            hunt_busy_enabled=hunt_busy_enabled,
            hunt_policy=hunt_policy,
            hunt_busy_allow_users=hunt_busy_allow_users,
            advance_when_busy=advance_when_busy,
            agents=self.build_agents(resp),
            alternate_numbers=self.build_alternate_numbers(resp),
            **self.build_forward_na(resp),
            **self.build_forward_busy(resp),
            **self.build_forward_unreachable(resp),
        )

    @staticmethod
    def build_agents(resp) -> list:
        agents = []
        agent_resp = resp.get("agents") or []
        agent_numbers_with_optional_weights = []

        for idx, item in enumerate(agent_resp, 1):
            agent = WbxcHuntGroupAgent(
                idx=idx,
                phoneNumber=item.get("phoneNumber", ""),
                extension=item.get("extension", ""),
                firstName=item.get("firstName", ""),
                lastName=item.get("lastName", ""),
                weight=item.get("weight", 0),
                type=item.get("type", ""),
            )
            agents.append(agent)

        return agents

    @staticmethod
    def build_alternate_numbers(resp) -> list[WbxcHuntGroupAltNumber]:
        alternate_numbers_resp = deep_get(
            resp, "alternateNumberSettings.alternateNumbers", default=[]
        )
        alternate_numbers = [
            WbxcHuntGroupAltNumber(
                idx=idx,
                phoneNumber=item["phoneNumber"],
                ringPattern=item.get("ringPattern", "NORMAL")
            )
            for idx, item in enumerate(alternate_numbers_resp, 1)
        ]

        return alternate_numbers

    @staticmethod
    def build_forward_busy(resp) -> dict:
        fwd_resp = deep_get(resp, "callPolicies.busyRedirect", default={})

        return {
            "forward_busy_enabled": fwd_resp.get("enabled", ""),
            "forward_busy_destination": fwd_resp.get("destination", ""),
            "forward_busy_vm": fwd_resp.get("destinationVoicemailEnabled", False),
        }

    @staticmethod
    def build_forward_unreachable(resp) -> dict:
        fwd_resp = deep_get(resp, "callPolicies.businessContinuityRedirect", default={})

        return {
            "forward_ur_enabled": fwd_resp.get("enabled", ""),
            "forward_ur_destination": fwd_resp.get("destination", ""),
            "forward_ur_vm": fwd_resp.get("destinationVoicemailEnabled") or False,
        }

    @staticmethod
    def build_forward_na(resp) -> dict:
        fwd_resp = deep_get(resp, "callPolicies.noAnswer", default={})

        return {
            "forward_na_enabled": fwd_resp.get("forwardEnabled"),
            "forward_na_destination": fwd_resp.get("destination", ""),
            "forward_na_vm": fwd_resp.get("destinationVoicemailEnabled", ""),
            "forward_na_rings": fwd_resp.get("numberOfRings", ""),
            "advance_to_next_agent": fwd_resp.get("nextAgentEnabled", ""),
            "advance_after_rings": fwd_resp.get("nextAgentRings", ""),
        }
