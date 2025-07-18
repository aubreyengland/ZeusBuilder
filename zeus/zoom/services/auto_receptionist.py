import logging
from . import shared
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusBulkOpFailed
from zeus.zoom.zoom_models import (
    ZoomAutoReceptionist,
    IvrMenuAction,
    IvrNoEntryAction,
    CallHandlingAction,
)
from zeus.services import BrowseSvc, ExportSvc, DetailSvc

log = logging.getLogger(__name__)


class ZoomAutoReceptionistBulkSvc(shared.ZoomBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current_ivr: dict = {}
        self.endpoint = client.phone_auto_receptionists

    def update_auto_receptionist(self):
        task = ZoomAutoReceptionistUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def remove_phone_numbers(self):
        task = shared.ZoomPhoneNumberRemoveTask(self, endpoint=self.endpoint)
        task.run()
        self.rollback_tasks.append(task)

    def assign_phone_numbers(self):
        task = shared.ZoomPhoneNumberAssignTask(self, endpoint=self.endpoint)
        task.run()
        self.rollback_tasks.append(task)

    def update_ivr(self):
        task = ZoomAutoReceptionistIvrTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_menu_actions(self):
        """
        Update IVR API only supports a single key_action in each request
        """
        for menu_action in self.model.menu_actions_list:
            if menu_action["action"]:
                task = ZoomAutoReceptionistMenuActionTask(self, menu_action)
                task.run()
                self.rollback_tasks.append(task)


@reg.bulk_service("zoom", "auto_receptionists", "CREATE")
class ZoomAutoReceptionistCreateSvc(ZoomAutoReceptionistBulkSvc):

    def run(self):
        resp = self.create_auto_receptionist()
        self.current = self.client.phone_auto_receptionists.get(resp["id"])
        self.current_ivr = self.client.phone_auto_receptionists.get_ivr(
            self.current["id"]
        )
        self.update_auto_receptionist()
        self.update_ivr()
        self.update_menu_actions()
        self.assign_phone_numbers()

    def create_auto_receptionist(self):
        task = ZoomAutoReceptionistCreateTask(self)
        resp = task.run()
        self.rollback_tasks.append(task)
        return resp


@reg.bulk_service("zoom", "auto_receptionists", "UPDATE")
class ZoomAutoReceptionistUpdateSvc(ZoomAutoReceptionistBulkSvc):
    action = "UPDATE"

    def run(self):
        self.get_current()
        self.update_auto_receptionist()
        self.update_ivr()
        self.update_menu_actions()
        self.remove_phone_numbers()
        self.assign_phone_numbers()

    def get_current(self):
        """
        get_ivr will fail if the auto receptionist business hour routing action
        is not IVR. Other actions are not supported yet so fail the update
        # TODO: Support updating call handling action
        """
        self.current = self.lookup.auto_receptionist(self.model.extension_number)
        try:
            self.current_ivr = self.client.phone_auto_receptionists.get_ivr(self.current["id"])
        except Exception:
            raise ZeusBulkOpFailed(f"{self.model.name} routing action is not 'IVR'. Other actions current not supported")


@reg.bulk_service("zoom", "auto_receptionists", "DELETE")
class ZoomAutoReceptionistDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.auto_receptionist(self.model.extension_number)
        self.client.phone_auto_receptionists.delete(self.current["id"])


class ZoomAutoReceptionistCreateTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.create_resp: dict = {}

    def run(self):
        payload = self.build_payload()
        self.create_resp = self.client.phone_auto_receptionists.create(payload=payload)
        return self.create_resp

    def build_payload(self) -> dict:
        payload = {"name": self.model.name}
        if self.model.site_name:
            site = self.svc.lookup.site(self.model.site_name)
            payload["site_id"] = site["id"]

        return payload

    def rollback(self) -> None:
        if self.create_resp:
            self.client.phone_auto_receptionists.delete(self.create_resp["id"])


class ZoomAutoReceptionistUpdateTask(shared.ZoomBulkTask):
    """
    Update Auto Receptionist basic settings such as, name, extension, timezone
    Extension is the unique identifier for Auto Receptionists, so it is updated
    based on the value in the 'new_extension' field.
    """
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomAutoReceptionistCreateSvc = svc
        self.payload: dict = {}

    def run(self):
        self.build_payload()
        if self.payload:
            self.client.phone_auto_receptionists.update(
                self.svc.current["id"], self.payload
            )

    def build_payload(self):
        payload = self.model.to_payload(
            include={"timezone", "audio_prompt_language"}, drop_unset=True
        )

        payload.update(self.get_site_id_for_update())
        payload.update(self.get_name_for_update())
        payload.update(self.get_extension_for_update())

        self.payload = payload

    def get_name_for_update(self) -> dict:
        """Include name in the payload if it differs from the current name"""
        current_name = self.svc.current.get("name")
        if self.model.name != current_name:
            return {"name": self.model.name}
        return {}

    def get_extension_for_update(self) -> dict:
        """
        Include extension_number in the payload if the model value
        differs from the current extension.

        The model.new_extension_number is used, if set, otherwise
        the model.extension_number is used. This supports
        changing the auto-assign extension to the `model.extension_number`
        value during CREATE operations or changing the extension in an
        UPDATE operation to `model.new_extension_number`.
        """
        current_ext = self.svc.current.get("extension_number")
        update_ext = self.model.new_extension_number or self.model.extension_number
        if update_ext and update_ext != current_ext:
            return {"extension_number": update_ext}
        return {}

    def get_site_id_for_update(self) -> dict:
        """
        Determine if site_id should be included in the update payload.
        site_id should only be included if:
         - there is a current site id
         - model.site_name has a value
         - site_id lookup returns a value
         - the model site id differs from current

        The site id will not be present in current when this task is
        run as part of `CREATE` action, which is fine as the site is set
        in the create request.
        """
        current_site_id = deep_get(self.svc.current, "site.id", default=None)

        if all([current_site_id, self.model.site_name]):
            model_site_id = self.svc.lookup.site_id_or_none(self.model.site_name)

            if model_site_id != current_site_id:
                return {"site_id": model_site_id}

        return {}

    def rollback(self):
        payload = {
            key: self.svc.current[key]
            for key in self.payload
            if key in self.svc.current
        }
        if "site_id" in self.payload:
            payload["site_id"] = self.svc.current["site"]["id"]

        if payload:
            self.client.phone_auto_receptionists.update(self.svc.current["id"], payload)


class ZoomAutoReceptionistIvrTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomAutoReceptionistBulkSvc = svc
        self.has_run: bool = False

    @property
    def current_audio_prompt_repeat(self):
        return deep_get(
            self.svc.current_ivr,
            "caller_enters_no_action.audio_prompt_repeat",
            3
        )

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.phone_auto_receptionists.update_ivr(
                self.svc.current["id"], payload=payload
            )
            self.has_run = True

    def build_payload(self):
        """
        Currently, only support 'caller_enters_no_action' portion of the IVR update
        request.
        """
        no_action_payload = self.build_no_action_payload()
        if no_action_payload:
            return {"caller_enters_no_action": no_action_payload}
        return {}

    def build_no_action_payload(self):
        no_action_payload = {}
        model_action = self.svc.model.no_entry_action
        model_target = self.svc.model.no_entry_target

        if model_action:
            action_enum = IvrNoEntryAction.from_name_or_value(model_action)

            no_action_payload["action"] = action_enum.value

            if model_target:
                no_action_payload.update(
                    self.get_forward_to_extension_id(action_enum, model_target)
                )

            # Request will fail if audio_prompt_repeat is not included.Use model value if set or current value
            no_action_payload["audio_prompt_repeat"] = (
                    self.model.audio_prompt_repeat
                    or self.current_audio_prompt_repeat
            )

        return no_action_payload

    def get_audio_prompt_repeat(self):
        """
        Request will fail if audio_prompt_repeat is not included. Use model value if set or current value
        """
        current_repeat = deep_get(
            self.svc.current_ivr, "caller_enters_no_action.audio_prompt_repeat", 3
        )
        return self.model.audio_prompt_repeat or current_repeat

    def get_forward_to_extension_id(self, action, target):

        match action:
            case action.User:
                resp = self.svc.lookup.user(target)
                payload = {"forward_to_extension_id": resp["extension_id"]}

            case action.CommonArea:
                resp = self.svc.lookup.common_area(target)
                payload = {"forward_to_extension_id": resp["id"]}

            case action.AutoReceptionist:
                resp = self.svc.lookup.auto_receptionist(target)
                payload = {"forward_to_extension_id": resp["extension_id"]}

            case action.CallQueue:
                resp = self.svc.lookup.call_queue(target)
                payload = {"forward_to_extension_id": resp["extension_id"]}

            case action.SharedLineGroup:
                resp = self.svc.lookup.shared_line_group(target)
                payload = {"forward_to_extension_id": resp["extension_id"]}

            case action.CiscoPolyPhone | action.ContactCenter:
                raise ZeusBulkOpFailed(f"Unsupported menu action: '{action}'")

            case _:  # Disabled has no payload
                payload = {}

        return payload

    def build_rollback_payload(self):
        payload = {}
        current = self.svc.current_ivr.get("caller_enters_no_action") or {}
        action = current.get("action")
        forward_to_id = deep_get(current, "forward_to.extension_id", None)

        if action:
            payload["action"] = action
            payload["audio_prompt_repeat"] = self.current_audio_prompt_repeat

        if forward_to_id:
            payload["forward_to_extension_id"] = forward_to_id

        if payload:
            return {"caller_enters_no_action": payload}

        return {}

    def rollback(self) -> None:
        if self.has_run:
            payload = self.build_rollback_payload()
            if payload:
                self.client.phone_auto_receptionists.update_ivr(
                    self.svc.current["id"], payload=payload
                )


class ZoomAutoReceptionistMenuActionTask(shared.ZoomBulkTask):
    def __init__(self, svc, menu_action, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: ZoomAutoReceptionistBulkSvc = svc
        self.menu_action: dict = menu_action
        self.has_run: bool = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.phone_auto_receptionists.update_ivr(
                self.svc.current["id"], payload=payload
            )
            self.has_run = True

    def build_payload(self):
        payload = {}
        if self.menu_action["action"]:
            action = IvrMenuAction.from_name_or_value(self.menu_action["action"])
            payload = {
                "key": self.menu_action["key"],
                "action": action.value,
            }
            target = self.get_menu_action_target(action)
            if target:
                payload.update(target)

        return {"key_action": payload}

    def get_menu_action_target(self, action) -> dict:
        target = self.menu_action["target"]

        match action:
            case action.User:
                resp = self.svc.lookup.user(target)
                payload = {"target": {"extension_id": resp["extension_id"]}}

            case action.CommonArea:
                resp = self.svc.lookup.common_area(target)
                payload = {"target": {"extension_id": resp["id"]}}

            case action.AutoReceptionist:
                resp = self.svc.lookup.auto_receptionist(target)
                payload = {"target": {"extension_id": resp["extension_id"]}}

            case action.ZoomRoom:
                resp = self.svc.lookup.room(target)
                payload = {"target": {"extension_id": resp["extension_id"]}}

            case action.CallQueue:
                resp = self.svc.lookup.call_queue(target)
                payload = {"target": {"extension_id": resp["extension_id"]}}

            case action.PhoneNumber:
                payload = {"target": {"phone_number": target}}

            case action.SharedLineGroup:
                resp = self.svc.lookup.shared_line_group(target)
                payload = {"target": {"extension_id": resp["extension_id"]}}

            case action.ExternalContact:
                resp = self.svc.lookup.external_contact(target)
                payload = {"target": {"extension_id": resp["external_contact_id"]}}

            case action.UserVoicemail:
                resp = self.svc.lookup.user(target)
                payload = {
                    "target": {"extension_id": resp["extension_id"]},
                    "voicemail_greeting_id": "",
                }

            case action.CurrentExtensionVoiceMail:
                payload = {
                    "target": {"extension_id": self.svc.current["id"]},
                    "voicemail_greeting_id": "",
                }

            case action.AutoReceptionistVoicemail:
                resp = self.svc.lookup.auto_receptionist(target)
                payload = {
                    "target": {"extension_id": resp["extension_id"]},
                    "voicemail_greeting_id": "",
                }

            case action.CallQueueVoicemail:
                resp = self.svc.lookup.call_queue(target)
                payload = {
                    "target": {"extension_id": resp["extension_id"]},
                    "voicemail_greeting_id": "",
                }

            case action.CiscoPolyPhone | action.ContactCenter | action.MeetingService | action.MeetingServiceNumber:
                raise ZeusBulkOpFailed(f"Unsupported menu action: '{action}'")

            case _:
                # Other cases (Disabled, RepeatGreeting, etc.) have no target
                payload = {}

        return payload

    def build_rollback_payload(self):
        current_key_actions = self.svc.current_ivr.get("key_actions") or []
        rollback_action = next(
            (c for c in current_key_actions if c["key"] == self.menu_action["key"]), {}
        )
        if not rollback_action:
            rollback_action = {"key": self.menu_action["key"], "action": "-1"}
        return {"key_action": rollback_action}

    def rollback(self):
        if self.has_run:
            payload = self.build_rollback_payload()
            self.client.phone_auto_receptionists.update_ivr(
                self.svc.current["id"], payload=payload
            )


@reg.browse_service("zoom", "auto_receptionists")
class ZoomAutoReceptionistBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomAutoReceptionistModelBuilder(self.client)

        for resp in self.client.phone_auto_receptionists.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.detail_service("zoom", "auto_receptionists")
class ZoomAutoReceptionistDetailSvc(DetailSvc):

    def run(self):
        builder = ZoomAutoReceptionistModelBuilder(self.client)
        detail_id = self.browse_row["detail_id"]
        resp = self.client.phone_auto_receptionists.get(detail_id)
        model = builder.build_detailed_model(resp)
        data = model.dict()
        data["menu_entries"] = self.parse_menu_entries(model)

        return data

    @staticmethod
    def parse_menu_entries(model):
        """
        convert the model menu entries fields into a
        list of dictionaries ready for the detail table.
        """
        rows = []
        key_mappings = [(str(r), str(r)) for r in range(0, 10)]
        key_mappings += [("s", "*"), ("p", "#")]
        for field_key, col_key in key_mappings:
            row = {
                "key": col_key,
                "action": getattr(model, f"key_{field_key}_action", ""),
                "extension": getattr(model, f"key_{field_key}_target", ""),
            }
            rows.append(row)

        return rows


@reg.export_service("zoom", "auto_receptionists")
class ZoomAutoReceptionistExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = ZoomAutoReceptionist.schema()["data_type"]
        builder = ZoomAutoReceptionistModelBuilder(self.client)

        for resp in self.client.phone_auto_receptionists.list():
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomAutoReceptionistModelBuilder:
    def __init__(self, client):
        self.client = client

    def build_model(self, resp: dict):
        return ZoomAutoReceptionist.safe_build(**self.summary_data(resp))

    def build_detailed_model(self, resp):
        summary_data = self.summary_data(resp)
        ivr_data = self.ivr_data(resp)

        return ZoomAutoReceptionist.safe_build(
            **summary_data,
            **ivr_data,
        )

    @staticmethod
    def summary_data(resp: dict):
        site_name = deep_get(resp, "site.name", default="")
        phone_numbers = ",".join(
            p["number"] for p in resp.get("phone_numbers") or []
        )

        return dict(
            name=resp["name"],
            site_name=site_name,
            phone_numbers=phone_numbers,
            timezone=resp.get("timezone"),
            extension_number=resp.get("extension_number", ""),
            audio_prompt_language=resp.get("audio_prompt_language", ""),
        )

    def ivr_data(self, resp):
        ivr_resp = self.get_ivr(resp)
        audio_prompt = deep_get(ivr_resp, "audio_prompt.name", default="")
        ivr_data = {
            "audio_prompt": "" if audio_prompt == "Default" else audio_prompt,
            "audio_prompt_repeat": deep_get(
                ivr_resp, "caller_enters_no_action.audio_prompt_repeat", default=""
            ),
        }

        key_actions = ivr_resp.get("key_actions") or []
        ivr_data.update(self.build_menu_entries(key_actions))

        timeout = ivr_resp.get("caller_enters_no_action") or {}
        if timeout:
            ivr_data.update(self.build_no_entry_action(timeout))

        return ivr_data

    def build_menu_entries(self, key_actions: list):
        key_field_map = {"*": "s", "#": "p"}
        menu_entries = {}

        for item in key_actions:
            key = key_field_map.get(item["key"], item["key"])

            action = action_value = str(item.get("action", ""))
            target = target_value = item.get("target", "")

            if action:
                action_value, target_value = self.build_menu_action(action, target)

            menu_entries[f"key_{key}_action"] = action_value
            menu_entries[f"key_{key}_target"] = target_value

        return menu_entries

    def build_menu_action(self, action: str, target: dict) -> tuple:
        try:
            action_enum = IvrMenuAction.from_name_or_value(action)
        except Exception:
            log.warning(f"Unexpected IVR action value: '{action}'")
            return str(action), "UNKNOWN"

        match action:
            case action_enum.Disabled | action_enum.RepeatGreeting | action_enum.PreviousMenu | action_enum.RootMenu:
                target_value = ""

            case action_enum.PhoneNumber:
                target_value = target["number"]

            case action_enum.ExternalContact:
                # Only includes extension_id, which is the external_contact_id
                target_value = self.get_external_contact(target)

            case _:  # Try for extension in supported action types
                target_value = target.get("extension_number", "UNKNOWN")

        return action_enum.wb_value(), target_value

    @staticmethod
    def build_no_entry_action(timeout: dict) -> dict:
        no_entry_action = action = str(timeout["action"])
        target = timeout.get("forward_to") or {}
        no_entry_target = "UNKNOWN"

        try:
            action_enum = IvrNoEntryAction.from_name_or_value(action)
        except Exception:
            log.warning(f"Unexpected Ivr timeout value: '{action}'")
        else:
            no_entry_action = action_enum.wb_value()

            match action:
                case action_enum.Disconnect:
                    no_entry_target = ""

                case _:
                    no_entry_target = target.get("extension_number", "UNKNOWN")

        return {
            "no_entry_action": no_entry_action,
            "no_entry_target": no_entry_target,
        }

    def get_ivr(self, auto_recept: dict) -> dict:
        """
        Get the IVR configuration for the auto receptionist
        if the business hours routing action is IVR.  If not
        return an empty dictionary
        """
        ivr = {}
        try:
            routing_action = self.get_business_hour_action(auto_recept["extension_id"])
        except Exception as exc:
            log.warning(f"Unknown routing action for {auto_recept}: {exc}")
        else:
            if routing_action == CallHandlingAction.IVR:
                ivr = self.client.phone_auto_receptionists.get_ivr(auto_recept["id"])

        return ivr

    def get_business_hour_action(self, auto_recept_id):
        resp = self.client.phone_call_handling.get(auto_recept_id)
        bus_hours = resp.get("business_hours") or []
        call_handling = next((
            item for item in bus_hours
            if item.get("sub_setting_type") == "call_handling"
        ), {})
        routing_action = deep_get(call_handling, "settings.routing.action", default=None)
        return CallHandlingAction.from_name_or_value(routing_action)

    def get_external_contact(self, target: dict):
        try:
            resp = self.client.phone_external_contacts.get(target["extension_id"])
        except Exception as exc:
            log.warning(f"Unable to get external contact for menu action target: {target}: {exc}")
            target_value = "UNKNOWN"
        else:
            if "extension_number" in resp:
                target_value = resp["extension_number"]
            else:
                target_value = resp["name"]

        return target_value
