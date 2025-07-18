import re
import logging
from .shared import (
    WbxcBulkSvc,
    WbxcBulkTask,
    WbxcLookup,
    remove_to_none,
    parse_call_permissions,
    parse_call_forwarding,
)
from zeus import registry as reg
from collections import defaultdict
from werkzeug.utils import secure_filename
from zeus.shared.helpers import deep_get
from zeus.wbxc.wbxc_simple import WbxcSimpleClient, WbxcServerFault
from zeus.wbxc.services import shared_calling_tasks as sh
from zeus.wbxc.wbxc_models import WbxcUserCalling, WbxcMonitor
from zeus.wbxc.wbxc_models.shared import WEBEX_CALLING_LICENSE_TYPES
from zeus.exceptions import ZeusBulkOpFailed, ZeusFileNotFoundError
from zeus.services import BrowseSvc, DetailSvc, ExportSvc, UploadTask, RowLoadResp

log = logging.getLogger(__name__)


class WbxcCallingLicenseMap:
    """
    Provides methods to map user-assigned licenses to
    supported Webex Calling licenses based on license ID

    Used to ensure users are calling-enabled before bulk
    requests or including in browse/export requests.

    Can be used in the future to include license names in
    browse/export/detail requests.
    """
    def __init__(self, org_license_resp, calling_license_types=None):
        self.org_license_resp: list[dict] = org_license_resp
        self.calling_license_types = calling_license_types or WEBEX_CALLING_LICENSE_TYPES
        self._calling_licenses: list[dict] = []

    @property
    def calling_licenses(self):
        if not self._calling_licenses:
            self._calling_licenses = [
                item
                for item in self.org_license_resp
                if item.get("name") in self.calling_license_types
            ]
        return self._calling_licenses

    def get_assigned_calling_license_objs(self, user_resp: dict) -> list[dict]:
        user_license_ids = user_resp.get("licenses", [])
        return [
            item
            for item in
            self.calling_licenses
            if item["id"] in user_license_ids
        ]

    def get_assigned_calling_license_ids(self, user_resp: dict) -> list[str]:
        user_license_ids = user_resp.get("licenses", [])
        return [
            item["id"] for item in
            self.get_assigned_calling_license_objs(user_resp)
        ]

    def get_assigned_calling_license_names(self, user_resp: dict) -> list[str]:
        user_license_ids = user_resp.get("licenses", [])
        return [
            item["name"] for item in
            self.get_assigned_calling_license_objs(user_resp)
        ]

    def is_user_calling_enabled(self, user_resp: dict) -> bool:
        return bool(len(self.get_assigned_calling_license_ids(user_resp)))


class WbxcUserCallingSvc(WbxcBulkSvc):
    """
    Parent class for CREATE and UPDATE services
    with shared methods and attributes
    """

    def __init__(self, client, model, busy_wav_bytes=None, no_ans_wav_bytes=None, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current_calling_licenses: list = []
        self.emergency_callback_number_id: str = ""
        self.music_on_hold_announcement: dict = {}
        self.busy_wav_bytes = busy_wav_bytes
        self.no_ans_wav_bytes = no_ans_wav_bytes
        self.monitored_lines: list = []
        self.user_phone_number: dict = {}
        self.license_map: WbxcCallingLicenseMap | None = None

    @property
    def current_user_location_id(self):
        """
        Return the current user's locationId value.
        This should be in the self.current dictionary but may be missing
        if the org is FedRAMP https://github.com/cdwlabs/zeus/issues/543
        If missing, look up the user's number/extension and return the
        locationId in that response
        """
        if "locationId" in self.current:
            return self.current["locationId"]

        params = {
            "ownerType": "PEOPLE",
            "ownerId": self.current["id"],
        }
        # Include phone_number in params if possible. Otherwise, include extension
        phone_number = self.user_phone_number.get("directNumber", "")
        extension = self.user_phone_number.get("extension", "")
        if phone_number:
            params["phoneNumber"] = phone_number
        elif extension:
            params["extension"] = extension

        resp = self.lookup.number(**params)
        location_id = deep_get(resp, "location.id", default=None)

        if not location_id:
            raise ZeusBulkOpFailed(f"Cannot determine location for {self.model.name}")

        return location_id

    def run(self):
        self.get_current()
        self.get_org_calling_licenses()
        self.get_current_calling_licenses()
        self.get_user_phone_number()

        self.get_emergency_callback_number_id()
        self.get_music_on_hold_announcement()
        self.get_monitored_lines()

        self.update_calling()
        self.update_caller_id()
        self.update_emergency_callback()
        self.update_incoming_permission()
        self.update_outgoing_permission()
        self.update_music_on_hold()
        self.update_call_forwarding()
        self.update_call_waiting()
        self.update_barge_in()
        self.update_call_bridge()
        self.update_hoteling()
        self.update_applications()
        self.update_do_not_disturb()
        self.update_compression()
        self.upload_busy_greeting()
        self.upload_no_answer_greeting()
        self.update_voicemail()
        self.reset_voicemail_pin()
        self.update_voicemail_passcode()
        self.update_call_recording()
        self.update_monitoring()

    def get_current(self):
        resp = self.lookup.user(self.model.name)
        self.current = self.client.users.get(resp["id"], callingData=True)

    def get_org_calling_licenses(self):
        resp = self.client.licenses.list()
        self.license_map = WbxcCallingLicenseMap(resp)

    def get_current_calling_licenses(self):
        self.current_calling_licenses = self.license_map.get_assigned_calling_license_ids(self.current)
        if not self.current_calling_licenses:
            raise ZeusBulkOpFailed(
                f"User '{self.model.name}' is not enabled for Calling."
            )

    def get_user_phone_number(self):
        numbers = self.client.user_phone_numbers.get(self.current["id"], preferE164Format=True)
        self.user_phone_number = next(
            (
                number
                for number in numbers.get("phoneNumbers", [])
                if number.get("primary") is True
            ),
            {}
        )

    def get_emergency_callback_number_id(self):
        if self.model.emergency_callback_type == "LOCATION_MEMBER_NUMBER" and self.model.emergency_callback_number:
            available_ecbn = self.lookup.ecbn_available_number(
                self.client.user_ecbn_availablenumbers.list,
                self.current["id"],
                self.model.emergency_callback_number
            )
            self.emergency_callback_number_id = deep_get(available_ecbn, "owner.id", "")

    def get_music_on_hold_announcement(self):
        if self.model.fileName and self.model.level:
            self.music_on_hold_announcement = self.lookup.announcement(
                self.model.fileName, self.model.level, self.current_user_location_id
            )

    def get_monitored_lines(self):
        for monitor in self.model.monitoring:
            if not monitor.number:
                continue
            if identifier := self.lookup.monitor_id(monitor.number, monitor.location_name):
                self.monitored_lines.append(identifier)

    def update_calling(self):
        task = WbxcUserCallingTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_caller_id(self):
        task = sh.WbxcCallerIdUpdateTask(self, self.client.user_caller_id)
        task.run()
        self.rollback_tasks.append(task)

    def update_emergency_callback(self):
        task = sh.WbxcEmergencyCallBackUpdateTask(self, self.client.user_emergency_call_back)
        task.run()
        self.rollback_tasks.append(task)

    def update_incoming_permission(self):
        task = sh.WbxcIncomingPermissionUpdateTask(self, self.client.user_incoming_permission)
        task.run()
        self.rollback_tasks.append(task)

    def update_outgoing_permission(self):
        task = sh.WbxcOutgoingPermissionUpdateTask(self, self.client.user_outgoing_permission)
        task.run()
        self.rollback_tasks.append(task)

    def update_music_on_hold(self):
        task = sh.WbxcMusicOnHoldUpdateTask(self, self.client.user_music_on_hold)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_forwarding(self):
        task = sh.WbxcCallForwardingUpdateTask(self, self.client.user_call_forwarding)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_waiting(self):
        task = sh.WbxcCallWaitingUpdateTask(self, self.client.user_call_waiting)
        task.run()
        self.rollback_tasks.append(task)

    def update_barge_in(self):
        task = sh.WbxcBargeInUpdateTask(self, self.client.user_barge_in)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_bridge(self):
        task = sh.WbxcCallBridgeUpdateTask(self, self.client.user_call_bridge)
        task.run()
        self.rollback_tasks.append(task)

    def update_hoteling(self):
        task = sh.WbxcHotelingUpdateTask(self, self.client.user_hoteling)
        task.run()
        self.rollback_tasks.append(task)

    def update_applications(self):
        task = WbxcUserApplicationsUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_do_not_disturb(self):
        task = sh.WbxcDoNotDisturbUpdateTask(self, self.client.user_do_not_disturb)
        task.run()
        self.rollback_tasks.append(task)

    def update_compression(self):
        task = sh.WbxcCompressionUpdateTask(self, self.client.user_compression)
        task.run()
        self.rollback_tasks.append(task)

    def upload_busy_greeting(self):
        task = sh.WbxcBusyGreetingUploadTask(
            self, self.client.user_busy_voicemail_greeting
        )
        task.run()
        self.rollback_tasks.append(task)

    def upload_no_answer_greeting(self):
        task = sh.WbxcNoAnswerGreetingUploadTask(
            self, self.client.user_no_answer_voicemail_greeting
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail(self):
        task = sh.WbxcVoicemailUpdateTask(self, self.client.user_voicemail)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_recording(self):
        task = sh.WbxcCallRecordingUpdateTask(self, self.client.user_call_recording)
        task.run()
        self.rollback_tasks.append(task)

    def reset_voicemail_pin(self):
        task = sh.WbxcResetVoicemailPinTask(self, self.client.user_reset_voicemail_pin)
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail_passcode(self):
        task = sh.WbxcVoicemailPasscodeUpdateTask(self, self.client.user_voicemail_passcode)
        task.run()
        self.rollback_tasks.append(task)

    def update_monitoring(self):
        task = sh.WbxcMonitoringUpdateTask(self, self.client.user_monitoring)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("wbxc", "user_calling", "CREATE")
class WbxcUserCallingCreateSvc(WbxcUserCallingSvc):
    pass


@reg.bulk_service("wbxc", "user_calling", "UPDATE")
class WbxcUserCallingUpdateSvc(WbxcUserCallingSvc):
    pass


class WbxcUserCallingTask(WbxcBulkTask):
    """
    Updates the users phone number and/or extension utilizing
    the license assign method.
    """
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcUserCallingSvc = svc
        self.update_payload: dict = {}
        self.model: WbxcUserCalling
        self.current_phone_number: str = self.svc.user_phone_number.get("directNumber", "")
        self.current_extension: str = self.svc.user_phone_number.get("extension", "")

    def run(self):
        self.build_update_payload()
        if self.update_payload:
            try:
                self.client.licenses.assign(self.update_payload)
            except WbxcServerFault as e:
                if str(e) == "license assignment for user failed":
                    raise ZeusBulkOpFailed(
                        "Phone number or extension assignment failed. The number may be non-existent or already in use."
                    ) from e
                else:
                    raise  # Re-raise the original exception if it's a different message

    def build_update_payload(self):
        """
        Builds the payload for updating the phone number and extension.

        No changes occur if:
        - Both the phone number and extension are the same as the current values.
        - The phone number is empty and the extension is the same as the current value.
        - The extension is empty and the phone number is the same as the current value.
        """
        if (
            (self.model.phoneNumber == self.current_phone_number and self.model.extension == self.current_extension) or
            (self.model.phoneNumber == "" and self.model.extension == self.current_extension) or
            (self.model.extension == "" and self.model.phoneNumber == self.current_phone_number)
        ):
            return {}

        if self.model.phoneNumber or self.model.extension:
            self.update_payload = {
                "email": self.svc.current.get("emails", [])[0],
                "personId": self.svc.current["id"],
                "orgId": self.svc.current["orgId"],
                "licenses": [self.build_webex_calling_license_properties()],
            }

    def build_webex_calling_license_properties(self):
        """
        This method constructs a payload for updating the Webex Calling license with
        the phone number and extension values. The following conditions determine
        the values included in the payload:

        Updates if:
        - `model.phoneNumber` is different from the current value.
        - `model.extension` is different from the current value.

        Existing values added to the payload if:
        - `model.phoneNumber` is empty, and `model.extension` needs to be updated.
        - `model.extension` is empty, and `model.phoneNumber` needs to be updated.

        Remove extension if:
        - The word "remove" is present in `model.extension`, the extension field
          in the payload will be set to `None`.
        """
        phone_number = self.model.phoneNumber or self.current_phone_number
        extension = self.model.extension or self.current_extension
        return remove_to_none({
            "id": self.svc.current_calling_licenses[0],
            "operation": "add",
            "properties": {
                "locationId": self.svc.current_user_location_id,
                "phoneNumber": phone_number,
                "extension": extension,
            }
        })

    def build_rollback_payload(self) -> dict:
        rollback_license = {
            "id": self.svc.current_calling_licenses[0],
            "operation": "add",
            "properties": {
                "locationId": self.svc.current_user_location_id,
                "phoneNumber": self.current_phone_number,
                "extension": self.current_extension,
            }
        }

        return {
            "email": self.model.name,
            "personId": self.svc.current["id"],
            "orgId": self.svc.current["orgId"],
            "licenses": [rollback_license],
        }

    def rollback(self):
        if self.update_payload:
            rollback_payload = self.build_rollback_payload()
            if rollback_payload:
                self.client.licenses.assign(payload=rollback_payload)


class WbxcUserApplicationsUpdateTask(WbxcBulkTask):
    """
    Update the application settings for the user.

    The update request is sent only if the relevant model
    fields have a value.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcUserCallingSvc = svc
        self.was_updated = False
        self.current_applications: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_applications = self.client.user_applications.get(
                self.svc.current["id"]
            )

            self.client.user_applications.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        include = {
            "ringDevicesForClickToDialCallsEnabled",
            "ringDevicesForGroupPageEnabled",
            "ringDevicesForCallParkEnabled",
            "browserClientEnabled",
            "desktopClientEnabled",
            "tabletClientEnabled",
            "mobileClientEnabled",
        }
        payload = self.model.to_payload(include=include, drop_unset=True)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client.user_applications.update(
                self.svc.current["id"], payload=self.current_applications
            )


@reg.upload_task("wbxc", "user_calling")
class WbxcUserCallingUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            self.validate_wav_file(row)
            row["monitoring"] = self.build_monitor(row)
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

    @staticmethod
    def build_monitor(row):
        num_dict = defaultdict(dict)

        for key, value in row.items():
            if match := re.match(r"Monitored Number\s*(\d+)", key):
                column_id = match.group(1)
                num_dict[column_id].update({"column_id": column_id, "number": value})

            if match := re.match(r"Monitored Location\s*(\d+)", key):
                column_id = match.group(1)
                num_dict[column_id].update({"location_name": value})

        return [WbxcMonitor(**n) for n in num_dict.values()]


@reg.export_service("wbxc", "user_calling")
class WbxcUserCallingExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = WbxcUserCalling.schema()["data_type"]
        builder = WbxcUserCallingModelBuilder(self.client)

        for resp in self.client.users.list(callingData=True):
            if builder.license_map.is_user_calling_enabled(resp):
                try:
                    model = builder.build_detailed_model(resp)
                    rows.append(model)
                except Exception as exc:
                    name = resp.get("emails", ["unknown"])[0]
                    error = getattr(exc, "message", str(exc))
                    errors.append({"name": name, "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


@reg.browse_service("wbxc", "user_calling")
class WbxcUserCallingBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WbxcUserCallingModelBuilder(self.client)

        for resp in self.client.users.list(callingData=True):
            if builder.license_map.is_user_calling_enabled(resp):
                model = builder.build_model(resp)
                row = model.dict()
                row["detail_id"] = resp["id"]
                rows.append(row)

        return rows


@reg.detail_service("wbxc", "user_calling")
class WbxcUserCallingDetailSvc(DetailSvc):

    def run(self):
        builder = WbxcUserCallingModelBuilder(self.client)
        resp = self.client.users.get(self.browse_row["detail_id"])
        return builder.build_detailed_model(resp)


class WbxcUserCallingModelBuilder:
    """
    Model builder class for WebexUser Calling Export

    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)
        self._org_calling_license_ids = set()
        self._license_map: WbxcCallingLicenseMap | None = None

    @property
    def license_map(self):
        if not self._license_map:
            resp = self.client.licenses.list()
            self._license_map = WbxcCallingLicenseMap(resp)
        return self._license_map

    @staticmethod
    def build_model(resp: dict):
        phone_number = next(
            (
                item["value"] for item in resp.get("phoneNumbers", [])
                if item["primary"] and item["type"] == "work"
            ),
            ""
        )
        return WbxcUserCalling.safe_build(
            name=resp["emails"][0],
            phoneNumber=phone_number,
            extension=resp.get("extension", ""),
        )

    def build_detailed_model(self, resp):
        """
        Fully-populate the WbxcUserCalling model for export or detail jobs.

        Note: The calling-related API requests will fail with a 403 error for
        improperly-configured users in control hub that are licensed
        for Webex Calling but do not have a number assigned. This is not
        a valid configuration but has been seen in the field. In those cases,
        return a model indicating that a number is not assigned as an indicator
        to the user.
        """
        identifier = resp["id"]
        name = resp.get("emails", [])[0]

        try:
            associated_numbers = self.get_associated_numbers(identifier)
        except WbxcServerFault as exc:
            log.warning(f"Associated number lookup for personId: {identifier} failed: {exc.message}")
            return WbxcUserCalling.safe_build(name=name, phoneNumber="NOT ASSIGNED", extension="NOT ASSIGNED")

        caller_id = self.get_caller_id(identifier)
        emergency_callback = self.get_emergency_callback(identifier)
        incoming_permission = self.get_incoming_permission(identifier)
        outgoing_permission = self.get_outgoing_permission(identifier)
        call_forwarding = self.get_call_forwarding(identifier)
        music_on_hold = self.get_music_on_hold(identifier)
        call_waiting = self.get_call_waiting(identifier)
        barge_in = self.get_barge_in(identifier)
        call_bridge = self.get_call_bridge(identifier)
        hoteling = self.get_hoteling(identifier)
        applications = self.get_applications(identifier)
        do_not_disturb = self.get_do_not_disturb(identifier)
        compression = self.get_compression(identifier)
        voicemail = self.get_voicemail(identifier)
        call_recording = self.get_call_recording(identifier)
        monitoring = self.get_monitoring(identifier)

        calling_license_names = self.license_map.get_assigned_calling_license_names(resp)

        return WbxcUserCalling.safe_build(
            name=name,
            calling_license_names=calling_license_names,
            **associated_numbers,
            **caller_id,
            **emergency_callback,
            **incoming_permission,
            **outgoing_permission,
            **call_forwarding,
            **music_on_hold,
            **call_waiting,
            **barge_in,
            **call_bridge,
            **hoteling,
            **applications,
            **do_not_disturb,
            **compression,
            **voicemail,
            **call_recording,
            **monitoring,
        )

    def get_associated_numbers(self, identifier):
        resp = self.client.user_phone_numbers.get(identifier, preferE164Format="True")
        primary_number = next(
            (num for num in resp.get("phoneNumbers", []) if num.get("primary")), {}
        )

        return {
            "phoneNumber": primary_number.get("directNumber"),
            "extension": primary_number.get("extension"),
        }

    def get_caller_id(self, identifier):
        resp = self.client.user_caller_id.get(identifier)

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
        resp = self.client.user_emergency_call_back.get(identifier)

        def convert_none(value):
            return "" if value == "NONE" else value

        return {
            "emergency_callback_type": convert_none(resp.get("selected", "")),
            "emergency_callback_number": deep_get(resp, "locationMemberInfo.phoneNumber", ""),
        }

    def get_incoming_permission(self, identifier):
        resp = self.client.user_incoming_permission.get(identifier)

        return {
            "internal_custom": resp.get("useCustomEnabled", ""),
            "internalCallsEnabled": resp.get("internalCallsEnabled", ""),
            "collectCallsEnabled": resp.get("collectCallsEnabled", ""),
            "externalTransfer": resp.get("externalTransfer", ""),
        }

    def get_outgoing_permission(self, identifier):
        resp = self.client.user_outgoing_permission.get(identifier)
        call_permissions = parse_call_permissions(resp)
        call_permissions["external_custom"] = resp.get("useCustomEnabled", "")

        return call_permissions

    def get_call_forwarding(self, identifier):
        resp = self.client.user_call_forwarding.get(identifier)
        return parse_call_forwarding(resp)

    def get_music_on_hold(self, identifier):
        resp = self.client.user_music_on_hold.get(identifier)
        return {
            "mohEnabled": resp.get("mohEnabled", ""),
            "greeting": resp.get("greeting", ""),
            "fileName": deep_get(resp, "audioAnnouncementFile.fileName", default=""),
            "level": deep_get(resp, "audioAnnouncementFile.level", default=""),
        }

    def get_call_waiting(self, identifier):
        resp = self.client.user_call_waiting.get(identifier)
        return {
            "callWaitingEnabled": resp.get("enabled", ""),
        }

    def get_barge_in(self, identifier):
        resp = self.client.user_barge_in.get(identifier)
        return {
            "barge_enabled": resp.get("enabled", ""),
            "toneEnabled": resp.get("toneEnabled", ""),
        }

    def get_call_bridge(self, identifier):
        resp = self.client.user_call_bridge.get(identifier)
        return {
            "warningToneEnabled": resp.get("warningToneEnabled", ""),
        }

    def get_hoteling(self, identifier):
        resp = self.client.user_hoteling.get(identifier)
        return {
            "hoteling_enabled": resp.get("enabled", ""),
        }

    def get_applications(self, identifier):
        resp = self.client.user_applications.get(identifier)
        return {
            "ringDevicesForClickToDialCallsEnabled": resp.get("ringDevicesForClickToDialCallsEnabled", ""),
            "ringDevicesForGroupPageEnabled": resp.get("ringDevicesForGroupPageEnabled", ""),
            "ringDevicesForCallParkEnabled": resp.get("ringDevicesForCallParkEnabled", ""),
            "browserClientEnabled": resp.get("browserClientEnabled", ""),
            "desktopClientEnabled": resp.get("desktopClientEnabled", ""),
            "tabletClientEnabled": resp.get("tabletClientEnabled", ""),
            "mobileClientEnabled": resp.get("mobileClientEnabled", ""),
        }

    def get_do_not_disturb(self, identifier):
        resp = self.client.user_do_not_disturb.get(identifier)
        return {
            "dnd_enabled": resp.get("enabled", ""),
            "ringSplashEnabled": resp.get("ringSplashEnabled", ""),
        }

    def get_compression(self, identifier):
        resp = self.client.user_compression.get(identifier)
        return {
            "compression": resp.get("compression", ""),
        }

    def get_voicemail(self, identifier):
        resp = self.client.user_voicemail.get(identifier)
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
        resp = self.client.user_call_recording.get(identifier)
        return {
            "recording_enabled": resp.get("enabled", ""),
            "record": resp.get("record", ""),
            "recordVoicemailEnabled": resp.get("recordVoicemailEnabled", ""),
            "start_stop_internalCallsEnabled": deep_get(resp, "startStopAnnouncement.internalCallsEnabled", default=""),
            "start_stop_pstnCallsEnabled": deep_get(resp, "startStopAnnouncement.pstnCallsEnabled", default=""),
            "record_notification": deep_get(resp, "notification.type", default=""),
            "repeat_enabled": deep_get(resp, "repeat.enabled", default=""),
            "repeat_interval": deep_get(resp, "repeat.interval", default=""),
        }

    def get_monitoring(self, identifier):
        resp = self.client.user_monitoring.get(identifier)
        monitoring = self.build_monitoring(resp)

        return {
            "enableCallParkNotification": resp.get("callParkNotificationEnabled", ""),
            "monitoring": monitoring
        }

    @staticmethod
    def build_monitoring(resp: dict):
        monitored_elements = resp.get("monitoredElements", [])

        if not monitored_elements:
            return []

        monitoring = []
        for index, monitored in enumerate(monitored_elements, start=1):
            column_id = str(index)
            number = ""
            location_name = ""

            if "member" in monitored:
                numbers = deep_get(monitored, "member.numbers", default=[])
                number = next((num.get("external") or num.get("extension") for num in numbers), "")
                location_name = deep_get(monitored, "member.location", default="")
            elif "callparkextension" in monitored:
                number = deep_get(monitored, "callparkextension.extension", default="")
                location_name = deep_get(monitored, "callparkextension.location", default="")

            monitoring.append(WbxcMonitor(column_id=column_id, number=number, location_name=location_name))

        return monitoring
