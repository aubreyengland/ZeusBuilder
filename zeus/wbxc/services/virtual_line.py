import logging
from .shared import (
    WbxcBulkSvc,
    WbxcBulkTask,
    WbxcLookup,
    parse_call_permissions,
    parse_call_forwarding,
    to_us_e164
)
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from werkzeug.utils import secure_filename
from zeus.shared.data_type_models import yn_to_bool
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from zeus.wbxc.wbxc_models import WbxcVirtualLine
from zeus.exceptions import ZeusFileNotFoundError
from zeus.wbxc.services import shared_calling_tasks as sh
from zeus.services import BrowseSvc, ExportSvc, UploadTask, RowLoadResp

log = logging.getLogger(__name__)


class WbxcVirtualLineSvc(WbxcBulkSvc):
    """
    Parent class for CREATE and UPDATE services
    with shared methods and attributes
    """

    def __init__(self, client, model, busy_wav_bytes=None, no_ans_wav_bytes=None, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: WbxcVirtualLine = model
        self.emergency_callback_number_id: dict = {}
        self.music_on_hold_announcement: dict = {}
        self.busy_wav_bytes = busy_wav_bytes
        self.no_ans_wav_bytes = no_ans_wav_bytes

    def get_emergency_callback_number_id(self):
        if self.model.emergency_callback_type == "LOCATION_MEMBER_NUMBER" and self.model.emergency_callback_number:
            available_ecbn = self.lookup.ecbn_available_number(
                self.client.virtual_line_ecbn_availablenumbers.list,
                self.current["id"],
                self.model.emergency_callback_number
            )
            self.emergency_callback_number_id = deep_get(available_ecbn, "owner.id", "")

    def get_music_on_hold_announcement(self):
        if self.model.fileName and self.model.level:
            self.music_on_hold_announcement = self.lookup.announcement(
                self.model.fileName, self.model.level, self.current["location"]["id"]
            )

    def update_virtual_line(self):
        task = WbxcVirtualLineUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_directory_search(self):
        task = WbxcVirtualLineDirectorySearchUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_caller_id(self):
        task = sh.WbxcCallerIdUpdateTask(
            self, self.client.virtual_line_caller_id
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_emergency_callback(self):
        task = sh.WbxcEmergencyCallBackUpdateTask(
            self, self.client.virtual_line_emergency_call_back
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_incoming_permission(self):
        task = sh.WbxcIncomingPermissionUpdateTask(
            self, self.client.virtual_line_incoming_permission
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_outgoing_permission(self):
        task = sh.WbxcOutgoingPermissionUpdateTask(
            self, self.client.virtual_line_outgoing_permission
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_music_on_hold(self):
        task = sh.WbxcMusicOnHoldUpdateTask(
            self, self.client.virtual_line_music_on_hold
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_call_waiting(self):
        task = sh.WbxcCallWaitingUpdateTask(
            self, self.client.virtual_line_call_waiting
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_call_forwarding(self):
        task = sh.WbxcCallForwardingUpdateTask(
            self, self.client.virtual_line_call_forwarding
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_barge_in(self):
        task = sh.WbxcBargeInUpdateTask(
            self, self.client.virtual_line_barge_in
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_call_bridge(self):
        task = sh.WbxcCallBridgeUpdateTask(
            self, self.client.virtual_line_call_bridge
        )
        task.run()
        self.rollback_tasks.append(task)

    def upload_busy_greeting(self):
        task = sh.WbxcBusyGreetingUploadTask(
            self, self.client.virtual_line_busy_voicemail_greeting
        )
        task.run()
        self.rollback_tasks.append(task)

    def upload_no_answer_greeting(self):
        task = sh.WbxcNoAnswerGreetingUploadTask(
            self, self.client.virtual_line_no_answer_voicemail_greeting
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail(self):
        task = sh.WbxcVoicemailUpdateTask(
            self, self.client.virtual_line_voicemail
        )
        task.run()
        self.rollback_tasks.append(task)

    def reset_voicemail_pin(self):
        task = sh.WbxcResetVoicemailPinTask(
            self, self.client.virtual_line_reset_voicemail_pin
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail_passcode(self):
        task = sh.WbxcVoicemailPasscodeUpdateTask(
            self, self.client.virtual_line_voicemail_passcode
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_call_recording(self):
        task = sh.WbxcCallRecordingUpdateTask(
            self, self.client.virtual_line_call_recording
        )
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("wbxc", "virtual_lines", "CREATE")
class WbxcVirtualLineCreateSvc(WbxcVirtualLineSvc):
    """
    Creates the Virtual Line.

    If other feature fields are populated an update
    will run for user convenience.

    If any update fails, the virtual line will be deleted
    in a rollback.
    """

    def run(self):
        self.create_virtual_line()

        self.current = self.client.virtual_lines.get(self.current["id"])

        self.get_emergency_callback_number_id()
        self.get_music_on_hold_announcement()

        self.update_directory_search()
        self.update_caller_id()
        self.update_emergency_callback()
        self.update_incoming_permission()
        self.update_outgoing_permission()
        self.update_music_on_hold()
        self.update_call_waiting()
        self.update_call_forwarding()
        self.update_barge_in()
        self.update_call_bridge()
        self.upload_busy_greeting()
        self.upload_no_answer_greeting()
        self.update_voicemail()
        self.reset_voicemail_pin()
        self.update_voicemail_passcode()
        self.update_call_recording()

    def create_virtual_line(self):
        """
        The API response only returns the ID.
        `get_current()` method will be used to get the
        virtual line details used for update tasks.

        RA NOTE: Even if the display name is included in the payload
        The API automatically reconfigured the display name with the
        model `firstName` `lastName` values which can cause an issue
        during a lookup if there is a mismatch.
        Work around is to use `get_current()` with the json response
        from `CREATE` instead of a lookup.
        """
        payload = self.build_payload()
        self.current = self.client.virtual_lines.create(payload=payload)

    def build_payload(self):
        include = {
            "firstName",
            "lastName",
            "displayName",
            "phoneNumber",
            "extension",
        }

        location = self.lookup.location(self.model.location)

        payload = self.model.to_payload(include=include, drop_unset=True)
        payload["locationId"] = location["id"]

        return payload

    def rollback(self):
        if self.current:
            self.client.virtual_lines.delete(self.current["id"])


@reg.bulk_service("wbxc", "virtual_lines", "UPDATE")
class WbxcVirtualLineUpdateSvc(WbxcVirtualLineSvc):

    def run(self):
        self.get_current()

        self.get_emergency_callback_number_id()
        self.get_music_on_hold_announcement()

        self.update_virtual_line()
        self.update_directory_search()
        self.update_caller_id()
        self.update_emergency_callback()
        self.update_incoming_permission()
        self.update_outgoing_permission()
        self.update_music_on_hold()
        self.update_call_waiting()
        self.update_call_forwarding()
        self.update_barge_in()
        self.update_call_bridge()
        self.upload_busy_greeting()
        self.upload_no_answer_greeting()
        self.update_voicemail()
        self.reset_voicemail_pin()
        self.update_voicemail_passcode()
        self.update_call_recording()

    def get_current(self):
        number = self.model.phoneNumber or self.model.extension
        self.current = self.lookup.virtual_line(
            self.model.firstName,
            self.model.lastName,
            number=number,
            location=self.model.location
        )


class WbxcVirtualLineUpdateTask(WbxcBulkTask):
    """
    Update virtual line settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcVirtualLineSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.virtual_lines.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self):
        payload = {}
        if self.model.new_firstName:
            payload["firstName"] = self.model.new_firstName

        if self.model.new_lastName:
            payload["lastName"] = self.model.new_lastName

        include = {
            "displayName",
            "phoneNumber",
            "extension",
            "announcementLanguage",
            "timeZone",
        }
        model_payload = self.model.to_payload(include=include, drop_unset=True)
        payload.update(model_payload)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client.virtual_lines.update(
                self.svc.current["id"], payload=self.svc.current
            )


class WbxcVirtualLineDirectorySearchUpdateTask(WbxcBulkTask):
    """
    Update the directory search for a designated Virtual Line.

    The update request is sent only if the relevant model
    fields have a value.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcVirtualLineSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.virtual_line_directory_search.update(self.svc.current["id"], payload=payload)
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.directorySearchEnabled:
            payload["enabled"] = yn_to_bool(self.model.directorySearchEnabled)

        return payload

    def rollback(self):
        if self.was_updated:
            dir_enabled = self.svc.current.get("directorySearchEnabled", False)
            rollback_payload = {"enabled": dir_enabled}

            self.client.virtual_line_directory_search.update(
                self.svc.current["id"], payload=rollback_payload
            )


@reg.bulk_service("wbxc", "virtual_lines", "DELETE")
class WbxcVirtualLineDeleteSvc(WbxcBulkSvc):

    def run(self):
        number = self.model.phoneNumber or self.model.extension
        self.current = self.lookup.virtual_line(
            self.model.firstName,
            self.model.lastName,
            number=number,
            location=self.model.location
        )
        self.client.virtual_lines.delete(self.current["id"])


@reg.upload_task("wbxc", "virtual_lines")
class WbxcVirtualLineUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            self.validate_wav_file(row)
        except ZeusFileNotFoundError as exc:
            return RowLoadResp(index=idx, error=exc.message)

        return super().validate_row(idx, row)

    def validate_wav_file(self, row):
        action = row.get("Action")
        sendBusyCalls_file = row.get("Send Busy Calls File")
        sendUnansweredCalls_file = row.get("Send Unanswered Calls File")

        if sendBusyCalls_file and action in ["CREATE", "UPDATE"]:
            if secure_filename(sendBusyCalls_file).lower() not in self.svc.wav_files:
                raise ZeusFileNotFoundError(f"Wav file '{sendBusyCalls_file}' not found")

        if sendUnansweredCalls_file and action in ["CREATE", "UPDATE"]:
            if secure_filename(sendUnansweredCalls_file).lower() not in self.svc.wav_files:
                raise ZeusFileNotFoundError(f"Wav file '{sendUnansweredCalls_file}' not found")


@reg.browse_service("wbxc", "virtual_lines")
class WbxcVirtualLineBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WbxcVirtualLineBrowseModelBuilder(self.client)

        for resp in self.client.virtual_lines.list():
            model = builder.build_model(resp)
            rows.append(model)

        return rows


@reg.export_service("wbxc", "virtual_lines")
class WbxcVirtualLineExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = WbxcVirtualLine.schema()["data_type"]
        builder = WbxcVirtualLineModelBuilder(self.client)

        for resp in self.client.virtual_lines.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("displayName", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcVirtualLineModelBuilder:
    """
    Model builder class for Webex Virtual Line Export
    Parent class for Browse
    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)

    def build_model(self, resp):
        identifier = resp["id"]
        virtual_line_settings = self.get_virtual_line_settings(identifier)
        caller_id = self.get_caller_id(identifier)
        emergency_callback = self.get_emergency_callback(identifier)
        incoming_permission = self.get_incoming_permission(identifier)
        outgoing_permission = self.get_outgoing_permission(identifier)
        call_forwarding = self.get_call_forwarding(identifier)
        music_on_hold = self.get_music_on_hold(identifier)
        call_waiting = self.get_call_waiting(identifier)
        barge_in = self.get_barge_in(identifier)
        call_bridge = self.get_call_bridge(identifier)
        voicemail = self.get_voicemail(identifier)
        call_recording = self.get_call_recording(identifier)

        return WbxcVirtualLine.safe_build(
            **virtual_line_settings,
            **caller_id,
            **emergency_callback,
            **incoming_permission,
            **outgoing_permission,
            **call_forwarding,
            **music_on_hold,
            **call_waiting,
            **barge_in,
            **call_bridge,
            **voicemail,
            **call_recording,
        )

    def get_virtual_line_settings(self, identifier):
        resp = self.client.virtual_lines.get(identifier)

        return {
            "displayName": resp.get("displayName", ""),
            "firstName": resp.get("firstName", ""),
            "lastName": resp.get("lastName", ""),
            "location": deep_get(resp, "location.name", ""),
            "phoneNumber": to_us_e164(deep_get(resp, "number.external", "")),
            "extension": deep_get(resp, "number.extension", ""),
            "announcementLanguage": resp.get("announcementLanguage", ""),
            "timeZone": resp.get("timeZone", ""),
            "directorySearchEnabled": resp.get("directorySearchEnabled", ""),
        }

    def get_caller_id(self, identifier):
        resp = self.client.virtual_line_caller_id.get(identifier)

        return {
            "caller_id_number_type": resp.get("selected", ""),
            "customNumber": resp.get("customNumber", ""),
            "caller_id_name_type": resp.get("externalCallerIdNamePolicy", ""),
            "caller_id_name_other": resp.get("customExternalCallerIdName", ""),
            "caller_id_first_name": resp.get("firstName", ""),
            "caller_id_last_name": resp.get("lastName", ""),
            "blockInForwardCallsEnabled": resp.get("blockInForwardCallsEnabled", ""),
        }

    def get_emergency_callback(self, identifier):
        resp = self.client.virtual_line_emergency_call_back.get(identifier)

        def convert_none(value):
            return "" if value == "NONE" else value

        return {
            "emergency_callback_type": convert_none(resp.get("selected", "")),
            "emergency_callback_number": deep_get(resp, "locationMemberInfo.phoneNumber", ""),
        }

    def get_incoming_permission(self, identifier):
        resp = self.client.virtual_line_incoming_permission.get(identifier)

        return {
            "internal_custom": resp.get("useCustomEnabled", ""),
            "internalCallsEnabled": resp.get("internalCallsEnabled", ""),
            "collectCallsEnabled": resp.get("collectCallsEnabled", ""),
            "externalTransfer": resp.get("externalTransfer", ""),
        }

    def get_outgoing_permission(self, identifier):
        resp = self.client.virtual_line_outgoing_permission.get(identifier)
        call_permissions = parse_call_permissions(resp)
        call_permissions["external_custom"] = resp.get("useCustomEnabled", "")

        return call_permissions

    def get_call_forwarding(self, identifier):
        resp = self.client.virtual_line_call_forwarding.get(identifier)
        return parse_call_forwarding(resp)

    def get_music_on_hold(self, identifier):
        resp = self.client.virtual_line_music_on_hold.get(identifier)
        return {
            "mohEnabled": resp.get("mohEnabled", ""),
            "greeting": resp.get("greeting", ""),
            "fileName": deep_get(resp, "audioAnnouncementFile.fileName", default=""),
            "level": deep_get(resp, "audioAnnouncementFile.level", default=""),
        }

    def get_call_waiting(self, identifier):
        resp = self.client.virtual_line_call_waiting.get(identifier)

        return {
            "callWaitingEnabled": resp.get("enabled", ""),
        }

    def get_barge_in(self, identifier):
        resp = self.client.virtual_line_barge_in.get(identifier)
        return {
            "barge_enabled": resp.get("enabled", ""),
            "toneEnabled": resp.get("toneEnabled", ""),
        }

    def get_call_bridge(self, identifier):
        resp = self.client.virtual_line_call_bridge.get(identifier)
        return {
            "warningToneEnabled": resp.get("warningToneEnabled", ""),
        }

    def get_voicemail(self, identifier):
        resp = self.client.virtual_line_voicemail.get(identifier)
        return {
            "vm_enabled": resp.get("enabled", ""),
            "sendAllCalls_enabled": deep_get(resp, "sendAllCalls.enabled", default=""),
            "sendBusyCalls_enabled": deep_get(resp, "sendBusyCalls.enabled", default=""),
            "sendBusyCalls_greeting": deep_get(resp, "sendBusyCalls.greeting", default=""),
            "sendUnansweredCalls_enabled": deep_get(resp, "sendUnansweredCalls.enabled", default=""),
            "sendUnansweredCalls_greeting": deep_get(resp, "sendUnansweredCalls.greeting", default=""),
            "sendUnansweredCalls_file": deep_get(resp, "sendUnansweredCalls.file", default=""),
            "sendUnansweredCalls_numberOfRings": deep_get(resp, "sendUnansweredCalls.numberOfRings", default=""),
            "transferToNumber_enabled": deep_get(resp, "transferToNumber.enabled", default=""),
            "transferToNumber_destination": deep_get(resp, "transferToNumber.destination", default=""),
            "emailCopyOfMessage_enabled": deep_get(resp, "emailCopyOfMessage.enabled", default=""),
            "emailCopyOfMessage_emailId": deep_get(resp, "emailCopyOfMessage.emailId", default=""),
            "notifications_enabled": deep_get(resp, "notifications.enabled", default=""),
            "notifications_destination": deep_get(resp, "notifications.destination", default=""),
            "messageStorage_mwiEnabled": deep_get(resp, "messageStorage.mwiEnabled", default=""),
            "messageStorage_storageType": deep_get(resp, "messageStorage.storageType", default=""),
            "messageStorage_externalEmail": deep_get(resp, "messageStorage.externalEmail", default=""),
            "faxMessage_enabled": deep_get(resp, "faxMessage.enabled", default=""),
            "faxMessage_phoneNumber": deep_get(resp, "faxMessage.phoneNumber", default=""),
            "faxMessage_extension": deep_get(resp, "faxMessage.extension", default=""),
        }

    def get_call_recording(self, identifier):
        resp = self.client.virtual_line_call_recording.get(identifier)
        return {
            "recording_enabled": resp.get("enabled", ""),
            "record": resp.get("record", ""),
            "recordVoicemailEnabled": resp.get("recordVoicemailEnabled", ""),
            # "startStopAnnouncementEnabled": resp.get("startStopAnnouncementEnabled", ""),
            "start_stop_internalCallsEnabled": deep_get(resp, "startStopAnnouncement.internalCallsEnabled", default=""),
            "start_stop_pstnCallsEnabled": deep_get(resp, "startStopAnnouncement.pstnCallsEnabled", default=""),
            "record_notification": deep_get(resp, "notification.type", default=""),
            "repeat_enabled": deep_get(resp, "repeat.enabled", default=""),
            "repeat_interval": deep_get(resp, "repeat.interval", default=""),
        }


class WbxcVirtualLineBrowseModelBuilder(WbxcVirtualLineModelBuilder):
    """
    Model builder class for Webex Location Calling Browse.
    Only Location Calling Settings are included.
    """

    def build_model(self, resp):
        identifier = resp["id"]
        virtual_line_settings = self.get_virtual_line_settings(identifier)

        return WbxcVirtualLine.safe_build(
            # phoneNumber=deep_get(resp, "number.external", ""),
            **virtual_line_settings,
        )
