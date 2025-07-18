import logging
from . import shared
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc
from zeus.zoom.zoom_models import ZoomPhoneUser
from zeus.shared.data_type_models import yn_to_bool

log = logging.getLogger(__name__)


@reg.bulk_service("zoom", "phone_users", "CREATE")
class ZoomPhoneUserCreateSvc(shared.ZoomBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current_profile_settings: dict = {}

    def run(self):
        self.create_phone_user()
        self.assign_emergency_address()
        self.apply_policy()

    def create_phone_user(self):
        task = ZoomPhoneUserCreateTask(self)
        self.current = task.run()
        self.rollback_tasks.append(task)

    def assign_emergency_address(self):
        """
        Emergency address not supported in batch create API so must
        be set using the update API
        """
        task = shared.ZoomEmerAddrAssignTask(self, endpoint=self.client.phone_users)
        task.run()
        self.rollback_tasks.append(task)

    def apply_policy(self):
        """
        Policy settings not supported in batch create API so must
        be set using the update API
        """
        task = ZoomPhoneUserPolicyTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("zoom", "phone_users", "UPDATE")
class ZoomPhoneUserUpdateSvc(shared.ZoomBulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current_profile_settings: dict = {}

    def run(self):
        self.get_current()

        self.update_calling_plans()
        self.update_phone_numbers()
        self.update_emergency_address()
        self.assign_caller_id_number()
        self.update_phone_user()

    def get_current(self):
        self.current = self.client.phone_users.get(self.model.email)
        self.current_profile_settings = self.client.phone_users.get_profile_settings(self.model.email)

    def update_calling_plans(self):
        """
        Add/remove calling plans to match the plans on the model.
        The Add task must be run before the Remove task because a
        phone user must have at least one calling plan assigned

        These tasks are also used for Common Areas so the API endpoint is
        passed as an init argument
        """
        for Task in (shared.ZoomCallingPlanAssignTask, shared.ZoomCallingPlanRemoveTask):
            task = Task(self, endpoint=self.client.phone_users)
            task.run()
            self.rollback_tasks.append(task)

    def update_phone_numbers(self):
        """
        Add/remove phone numbers to match the phone numbers on the model
        The Remove task is run first to avoid hitting the user phone number limit.

        These tasks are also used for Common Areas so the API endpoint is
        passed as an init argument
        """
        for Task in (shared.ZoomPhoneNumberRemoveTask, shared.ZoomPhoneNumberAssignTask):
            task = Task(self, endpoint=self.client.phone_users)
            task.run()
            self.rollback_tasks.append(task)

    def update_emergency_address(self):
        """
        Update the emergency address to match the value in the model.

        This task is also used for Common Areas so the API endpoint is
        passed as an init argument.
        """
        task = shared.ZoomEmerAddrAssignTask(self, endpoint=self.client.phone_users)
        task.run()
        self.rollback_tasks.append(task)

    def assign_caller_id_number(self):
        """
        Phone numbers must be made assigned as valid caller ID numbers
        for each user before the number can used as an outbound caller id number.
        """
        task = ZoomCallerIDAssignTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_phone_user(self):
        """
        Update user basic settings, profile settings and policy settings.

        These updates run last because:
        - ZoomCallerIDAssignTask must run before the outbound_caller_id profile setting can be updated
        - Avoids the need run `get_current` again so subsequent tasks have accurate values.
        """
        for Task in (ZoomPhoneUserUpdateTask, ZoomPhoneUserPolicyTask, ZoomPhoneUserProfileTask):
            task = Task(self)
            task.run()
            self.rollback_tasks.append(task)


@reg.bulk_service("zoom", "phone_users", "DELETE")
class ZoomPhoneUserDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        payload = {"feature": {"zoom_phone": False}}
        self.client.meeting_users.update_settings(self.model.email, payload)


class ZoomPhoneUserCreateTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.has_run: bool = False

    def run(self):
        payload = self.build_payload()

        resp = self.client.phone_users.create(payload={"users": [payload]})
        self.has_run = True
        return resp[0]

    def build_payload(self):
        include = {"email", "extension_number", "site_name", "template_name", "outbound_caller_id"}
        payload = self.model.to_payload(include=include, drop_unset=True)

        if self.model.phone_numbers_list:
            payload["phone_numbers"] = self.model.phone_numbers_list

        payload["calling_plans"] = [
            shared.fix_calling_plan_name(name) for name in self.model.calling_plans_list
        ]

        return payload

    def rollback(self):
        if self.has_run:
            payload = {"feature": {"zoom_phone": False}}
            self.client.meeting_users.update_settings(self.model.email, payload)


class ZoomPhoneUserPolicyTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.has_run = False
        self.update_payload: dict = {}

    def run(self):
        self.build_payload()

        if self.update_payload:
            self.client.phone_users.update(self.svc.current["id"], self.update_payload)
            self.has_run = True

    def build_payload(self):
        """
        Build a Phone User Profile UPDATE payload using any policy-related
        items in the provided batch request.

        This is used for all UPDATE requests and for CREATE requests that
        have policy settings that cannot be set during creation.
        """
        payload = self.model.to_payload(include={"policy"}, drop_unset=True)
        if self.model.voicemail_enable:
            policy = payload.setdefault("policy", {})
            vm_policy = policy.setdefault("voicemail", {})
            vm_policy["enable"] = yn_to_bool(self.model.voicemail_enable)

        self.update_payload = payload

    def rollback(self):
        """
        Reset any policy objects updated to the original values.
        The entire original policy object is not used because any policy
        settings locked at the account level would cause the request to fail.
        Including only objects there were successfully changed should avoid
        these failures
        """
        current_policy = self.svc.current.get("policy") or {}
        if self.has_run:
            rollback_policy = {}
            for key in self.update_payload.get("policy") or {}:
                if key in current_policy:
                    rollback_policy[key] = current_policy[key]

            if rollback_policy:
                self.client.phone_users.update(self.svc.current["id"], {"policy": rollback_policy})


class ZoomPhoneUserUpdateTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.has_run = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.phone_users.update(self.svc.current["id"], payload)
            self.has_run = True

    def build_payload(self):
        payload = {}

        if self.model.site_name:
            site_id = self.svc.lookup.site(self.model.site_name)["id"]
        else:
            site_id = None

        if site_id and site_id != self.svc.current["site_id"]:
            payload["site_id"] = site_id

        if self.model.template_name:
            template = self.svc.lookup.user_template(self.model.template_name, site_id)
            payload["template_id"] = template["id"]

        if str(self.model.extension_number) != str(self.svc.current["extension_number"]):
            payload["extension_number"] = self.model.extension_number

        return payload


class ZoomPhoneUserProfileTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomPhoneUserUpdateSvc = svc
        self.has_run = False

    @property
    def current_outbound_caller_id(self):
        return deep_get(self.svc.current_profile_settings, "outbound_caller.number", default="")

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.phone_users.update_profile_settings(self.svc.current["id"], payload)
            self.has_run = True

    def build_payload(self):
        payload = {}

        if (
                self.model.outbound_caller_id
                and self.model.outbound_caller_id != self.current_outbound_caller_id
        ):
            payload["outbound_caller_id"] = self.model.outbound_caller_id

        return payload

    def rollback(self):
        if self.has_run:
            payload = {"outbound_caller_id": self.current_outbound_caller_id}
            self.client.phone_users.update_profile_settings(self.svc.current["id"], payload)


class ZoomCallerIDAssignTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.current_caller_id: list = []
        self.to_assign_ids: list = []

    def run(self):
        self.current_caller_id = list(self.client.phone_users.list_caller_id(self.model.email))
        payload = self.build_payload()
        if payload:
            self.client.phone_users.add_caller_id(self.svc.current["id"], payload)

    def build_payload(self) -> dict:
        payload = {}
        current_caller_id_numbers = [num["phone_number"] for num in self.current_caller_id]

        if (
                self.model.outbound_caller_id
                and self.model.outbound_caller_id not in current_caller_id_numbers
        ):
            resp = self.svc.lookup.phone_number(self.model.outbound_caller_id)
            self.to_assign_ids.append(resp["id"])
            payload["phone_number_ids"] = self.to_assign_ids

        return payload

    def rollback(self) -> None:
        for phone_number_id in self.to_assign_ids:
            self.client.phone_users.remove_caller_id(self.svc.current["id"], phone_number_id)


@reg.browse_service("zoom", "phone_users")
class ZoomPhoneUserBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomPhoneUserModelBuilder(self.client)
        for resp in self.client.phone_users.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.export_service("zoom", "phone_users")
class ZoomPhoneUserExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomPhoneUser.schema()["data_type"]
        builder = ZoomPhoneUserModelBuilder(self.client)

        for resp in self.client.phone_users.list():
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("email", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomPhoneUserModelBuilder:
    def __init__(self, client):
        self.client = client

    def build_model(self, resp: dict):
        return ZoomPhoneUser.safe_build(**self.user_summary_data(resp))

    def build_detailed_model(self, resp: dict):
        user_details = self.client.phone_users.get(resp["id"])
        voicemail_enable = deep_get(user_details, "policy.voicemail.enable", "")
        emergency_address = user_details.get("emergency_address") or {}
        outbound_caller_id = self.get_outbound_caller_id(user_details["id"])

        return ZoomPhoneUser.safe_build(
            policy=user_details["policy"],
            voicemail_enable=voicemail_enable,
            outbound_caller_id=outbound_caller_id,
            **self.user_summary_data(resp),
            **emergency_address,
        )

    @staticmethod
    def user_summary_data(resp: dict):
        site_name = deep_get(resp, "site.name", default="")
        calling_plans_list = [c["name"] for c in resp.get("calling_plans") or []]
        phone_number_list = [n["number"] for n in resp.get("phone_numbers") or []]

        return dict(
            email=resp["email"],
            site_name=site_name,
            calling_plans=",".join(calling_plans_list),
            extension_number=resp["extension_number"],
            phone_numbers=",".join(phone_number_list),
        )

    def get_outbound_caller_id(self, user_id):
        resp = self.client.phone_users.get_profile_settings(user_id)
        return deep_get(resp, "outbound_caller.number", default="")
