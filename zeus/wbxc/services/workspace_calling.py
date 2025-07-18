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
from werkzeug.utils import secure_filename
from zeus.shared.helpers import deep_get
from zeus.wbxc.services import shared_calling_tasks as sh
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from zeus.wbxc.wbxc_models import WbxcWorkspaceCalling, WbxcMonitor
from zeus.exceptions import ZeusBulkOpFailed, ZeusFileNotFoundError
from zeus.services import BrowseSvc, ExportSvc, UploadTask, RowLoadResp
from .user_calling import WbxcCallingLicenseMap

log = logging.getLogger(__name__)


def is_calling_enabled_for_workspace(resp) -> bool:
    """
    Validates if a workspace is enabled with Calling.
    Used by Update and Export tasks.
    """
    calling_type = deep_get(resp, "calling.type", "")
    return calling_type == "webexCalling"


class WbxcWorkspaceCallingSvc(WbxcBulkSvc):
    """
    Parent class for CREATE and UPDATE services
    with shared methods and attributes
    """

    def __init__(self, client, model, busy_wav_bytes=None, no_ans_wav_bytes=None, **kwargs):
        super().__init__(client, model, **kwargs)
        self.license_id: str = ""
        self.license_type: str = ""
        self.professional_license: bool = False
        self.associated_numbers: dict = {}
        self.emergency_callback_number_id: str = ""
        self.music_on_hold_announcement: dict = {}
        self.busy_wav_bytes = busy_wav_bytes
        self.no_ans_wav_bytes = no_ans_wav_bytes
        self.monitored_lines: list = []

    def validate_calling_for_workspace(self):
        calling_enabled = is_calling_enabled_for_workspace(self.current)
        if not calling_enabled:
            raise ZeusBulkOpFailed(
                f"Workspace '{self.model.name}' is not enabled for Calling."
            )

    def get_associated_numbers(self):
        self.associated_numbers = (
            self.client.workspace_associated_numbers.get(self.current["id"])
        )

    def get_emergency_callback_number_id(self):
        if self.model.emergency_callback_type == "LOCATION_MEMBER_NUMBER" and self.model.emergency_callback_number:
            available_ecbn = self.lookup.ecbn_available_number(
                self.client.workspace_ecbn_available_phonenumbers.list,
                self.current["id"],
                self.model.emergency_callback_number
            )
            self.emergency_callback_number_id = deep_get(available_ecbn, "owner.id", "")

    def get_music_on_hold_announcement(self):
        if self.model.fileName and self.model.level:
            self.music_on_hold_announcement = self.lookup.announcement(
                self.model.fileName, self.model.level, self.current["locationId"]
            )

    def get_monitored_lines(self):
        for monitor in self.model.monitoring:
            if not monitor.number:
                continue
            if identifier := self.lookup.monitor_id(monitor.number, monitor.location_name):
                self.monitored_lines.append(identifier)

    def update_calling(self):
        task = WbxcWorkspaceCallingUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_caller_id(self):
        task = WbxcWorkspaceCallingCallerIdUpdateTask(
            self, self.client.workspace_caller_id
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_emergency_callback(self):
        task = sh.WbxcEmergencyCallBackUpdateTask(
            self, self.client.workspace_emergency_call_back
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_incoming_permission(self):
        task = sh.WbxcIncomingPermissionUpdateTask(
            self, self.client.workspace_incoming_permission
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_outgoing_permission(self):
        task = sh.WbxcOutgoingPermissionUpdateTask(
            self, self.client.workspace_outgoing_permission
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_outgoing_auto_transfer(self):
        task = sh.WbxcOutgoingAutoTransferUpdateTask(
            self, self.client.workspace_transfer_numbers
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_music_on_hold(self):
        task = sh.WbxcMusicOnHoldUpdateTask(self, self.client.workspace_music_on_hold)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_waiting(self):
        task = sh.WbxcCallWaitingUpdateTask(self, self.client.workspace_call_waiting)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_forwarding(self):
        task = sh.WbxcCallForwardingUpdateTask(self, self.client.workspace_call_forwarding)
        task.run()
        self.rollback_tasks.append(task)

    def update_anonymous_call_reject(self):
        task = sh.WbxcAnonymousCallRejectUpdateTask(
            self, self.client.workspace_anonymous_call_reject
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_barge_in(self):
        task = sh.WbxcBargeInUpdateTask(self, self.client.workspace_barge_in)
        task.run()
        self.rollback_tasks.append(task)

    def update_do_not_disturb(self):
        task = sh.WbxcDoNotDisturbUpdateTask(self, self.client.workspace_do_not_disturb)
        task.run()
        self.rollback_tasks.append(task)

    def update_compression(self):
        task = sh.WbxcCompressionUpdateTask(self, self.client.workspace_compression)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_bridge(self):
        task = sh.WbxcCallBridgeUpdateTask(self, self.client.workspace_call_bridge)
        task.run()
        self.rollback_tasks.append(task)

    def upload_busy_greeting(self):
        task = sh.WbxcBusyGreetingUploadTask(
            self, self.client.workspace_busy_voicemail_greeting
        )
        task.run()
        self.rollback_tasks.append(task)

    def upload_no_answer_greeting(self):
        task = sh.WbxcNoAnswerGreetingUploadTask(
            self, self.client.workspace_no_answer_voicemail_greeting
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail(self):
        task = sh.WbxcVoicemailUpdateTask(self, self.client.workspace_voicemail)
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail_passcode(self):
        task = sh.WbxcVoicemailPasscodeUpdateTask(
            self, self.client.workspace_voicemail_passcode
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_monitoring(self):
        task = sh.WbxcMonitoringUpdateTask(
            self, self.client.workspace_monitoring
        )
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("wbxc", "workspace_calling", "CREATE")
class WbxcWorkspaceCallingCreateSvc(WbxcWorkspaceCallingSvc):
    """
    Creates the Workspace and adds the Calling license.

    If other feature fields are populated, an update
    will run for user convenience.

    If any update fails, the Workspace will be deleted
    in a rollback.
    """
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)

    def run(self):
        self.get_license()
        self.create_workspace()

        if self.license_type in ("Workspaces", "Professional"):
            self.get_emergency_callback_number_id()
            self.get_music_on_hold_announcement()
            self.get_monitored_lines()

            self.update_caller_id()
            self.update_emergency_callback()
            self.update_incoming_permission()
            self.update_outgoing_permission()
            self.update_outgoing_auto_transfer()
            self.update_music_on_hold()
            self.update_call_waiting()
            self.update_call_forwarding()
            self.update_compression()
            self.update_monitoring()

        if self.license_type == "Professional":
            self.update_anonymous_call_reject()
            self.update_barge_in()
            self.update_do_not_disturb()
            self.update_call_bridge()
            self.upload_busy_greeting()
            self.upload_no_answer_greeting()
            self.update_voicemail()
            self.update_voicemail_passcode()

    def get_license(self):
        """
        Get the license ID and set the license type attribute for Workspace
        creation.
        """
        license_name = f"Webex Calling - {self.model.licenses}"
        resp = self.lookup.license(license_name, self.model.sub_id)

        self.license_id = resp["id"]
        self.license_type = self.model.licenses

    def create_workspace(self):
        """
        The locationId, workspaceLocationId, floorId, indoorNavigation, capacity, type,
        notes and hotdeskingStatus parameters are optional, and omitting them will result
        in the creation of a workspace without these values set, or set to their default

        When creating a webexCalling workspace, `locationId`, `supportedDevices` and either
        a `phoneNumber` or `extension` or is required
        """
        payload = self.build_payload()
        self.current = self.client.workspaces.create(payload=payload)

    def build_payload(self):
        include = {
            "type",
            "capacity",
            "hotdeskingStatus",
            "notes",
            "supportedDevices",
        }
        payload = self.model.to_payload(include=include, drop_unset=True)

        # hotdeskingStatus must be on for hot-desk only
        if self.license_type == "Hot desk only":
            payload["hotdeskingStatus"] = "on"

        payload["displayName"] = self.model.name

        payload["calling"] = self.build_webex_calling_payload()

        return payload

    def build_webex_calling_payload(self) -> dict:
        """
        Builds the CREATE payload for Webex Calling Workspace.

        Assigns the phone number and/or extension if the license type is Workspaces
        or Professional
        """
        licenses = [self.license_id] if self.license_id else []
        location = self.lookup.location(self.model.location)
        webex_calling_payload = {
            "locationId": location["id"],
            "licenses": [self.license_id],
        }

        if self.license_type != "Hot desk only":
            if self.model.phoneNumber:
                webex_calling_payload["phoneNumber"] = self.model.phoneNumber
            if self.model.extension:
                webex_calling_payload["extension"] = self.model.extension

        return {
            "type": "webexCalling",
            "webexCalling": webex_calling_payload
        }

    def rollback(self):
        if self.current:
            self.client.workspaces.delete(self.current["id"])


@reg.bulk_service("wbxc", "workspace_calling", "UPDATE")
class WbxcWorkspaceCallingUpdateSvc(WbxcWorkspaceCallingSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.license_map: WbxcCallingLicenseMap | None = None
        self.current_license_type: str = "'"

    def run(self):
        self.get_current()
        self.get_org_calling_licenses()
        self.get_current_license_type()
        self.get_update_license_type()
        self.get_update_license_id()
        # self.validate_calling_for_workspace()  # RA NOTE: Do we want to automatically add calling to an existing WS?
        if self.license_type != "Hot desk only":
            self.get_associated_numbers()

            self.get_emergency_callback_number_id()
            self.get_music_on_hold_announcement()
            self.get_monitored_lines()

        self.update_calling()

        if self.license_type != "Hot desk only":
            self.update_caller_id()
            self.update_emergency_callback()
            self.update_incoming_permission()
            self.update_outgoing_permission()
            self.update_outgoing_auto_transfer()
            self.update_music_on_hold()
            self.update_call_waiting()
            self.update_call_forwarding()
            self.update_compression()
            self.update_monitoring()

        if self.license_type == "Professional":
            self.update_anonymous_call_reject()
            self.update_barge_in()
            self.update_do_not_disturb()
            self.update_call_bridge()
            self.upload_busy_greeting()
            self.upload_no_answer_greeting()
            self.update_voicemail()
            self.update_voicemail_passcode()

    def get_current(self):
        number = self.model.phoneNumber or self.model.extension
        self.current = self.lookup.workspace(
            self.model.name,
            number=number,
            location=self.model.location
        )

    def get_org_calling_licenses(self):
        resp = self.client.licenses.list()
        self.license_map = WbxcCallingLicenseMap(resp)

    def get_current_license_type(self):
        """
        Identify the current license type based on the assigned calling license
        or set to an empty string if the workspace is not currently licensed for calling
        """
        # TODO: Update WbxcCallingLicenseMap method arguments to better support user and workspace responses
        current_license_ids = deep_get(self.current, "calling.webexCalling", default={})
        current_license_names = self.license_map.get_assigned_calling_license_names(current_license_ids)

        if "Webex Calling - Professional" in current_license_names:
            self.current_license_type = "Professional"
        elif "Webex Calling - Hot desk only" in current_license_names:
            self.current_license_type = "Hot desk only"
        else:
            self.current_license_type = "Workspaces"

    def get_update_license_type(self):
        """
        Determine the license type for the workspace after the update.

        If the model.licenses value is set, use this value. It is either the current
        license type or the intended upgraded license type, but in either case, this is the type
        that should be used to determine which upgrade tasks to run

        If the Workspace is currently licenses for calling, use the current license type as
        it will not change

        Otherwise, raise an exception because we require an explicit license type in order to
        enable calling.
        """
        if self.model.licenses:
            self.license_type = self.model.licenses
        elif self.current_license_type:
            self.license_type = self.current_license_type
        else:
            raise ZeusBulkOpFailed(f"A Calling License must be specified to enable calling for an existing workspace")

    def get_update_license_id(self):
        """
        Determine if a license ID should be included in the update payload based on
        the current_license_type and model license_type.

        If the current and model license types are the same, no license change is being
        made.

        Otherwise, find the license ID associated with the license type and sub id (if present)
        from the model.
        """
        if self.current_license_type != self.license_type:

            license_name = f"Webex Calling - {self.license_type}"

            org_licenses_of_type = [
                item for item in self.license_map.calling_licenses
                if item["name"] == license_name
            ]

            if self.model.sub_id:
                org_licenses_of_type = [
                    item for item in org_licenses_of_type
                    if item["subscriptionId"] == self.model.sub_id
                ]

            if not org_licenses_of_type:
                raise ZeusBulkOpFailed(f"{license_name} license type not found")

            self.license_id = org_licenses_of_type[0]["id"]


class WbxcWorkspaceCallingUpdateTask(WbxcBulkTask):
    """
    Updates the Webex Calling enabled workspace Phone Number and Extension.
    This update uses the standard Workspace API.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcWorkspaceCallingSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.workspaces.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        """
        Documentation states to include all details for the workspace
        that are present in a GET request for the workspace details.
        Not including the optional capacity, type or notes fields will
        result in the fields no longer being defined for the workspace.

        workspaceLocationId must be ommited from the payload
        - error: locationId and workspaceLocationId cannot be used together

        RA 9/6/24 NOTE: Not including capacity, type or notes fields
        in the payload does not result in fields not being defined.
        """
        new_name = self.model.new_name
        payload = {"displayName": new_name} if new_name else {}

        include = {
            "type",
            "capacity",
            "hotdeskingStatus",
            "notes",
        }
        ws_setttings = self.model.to_payload(include=include, drop_unset=True)
        payload.update(ws_setttings)

        if self.svc.license_type != "Hot desk only":
            include_calling = {
                "phoneNumber",
                "extension",
                "licenses",
            }
            if self.model.to_payload(include=include_calling, drop_unset=True):
                payload["calling"] = self.build_webex_calling_payload()

        return remove_to_none(payload, replacement_value="")

    def build_webex_calling_payload(self) -> dict:
        """
        Builds the UPDATE payload for the Webex Calling workspace.

        NOTE:
         - When updating webexCalling information, a locationId and either a phoneNumber or
        extension or both is required.
         - Licenses field can be set with a list of Webex Calling license IDs, if desired.
         - If multiple license IDs are provided, the oldest suitable one will be applied.
         - If a previously applied license ID is omitted, it will be replaced with one
        from the list provided.
         - If the licenses field is omitted, the current calling license will be retained.

        ```
        "calling": {
            "type": "webexCalling",
            "webexCalling": {
                "phoneNumber": "+19302121058",
                "extension": "3344",
                "locationId": "Y2lzY29zc....."
                "licenses": ["Y2lzY29z....."],
            }
        }
        ```
        """
        current_phone_numbers = self.svc.associated_numbers.get("phoneNumbers", [{}])
        current_phone_number = current_phone_numbers[0].get("external", "")
        current_extension = current_phone_numbers[0].get("extension", "")

        phone_number = self.model.phoneNumber or current_phone_number
        extension = self.model.extension or current_extension

        location_id = self.svc.current["locationId"]

        licenses = [self.svc.license_id] if self.svc.license_id else []

        webex_calling = {
            **({"phoneNumber": phone_number} if phone_number else {}),
            **({"extension": extension} if extension else {}),
            **({"locationId": location_id} if phone_number or extension else {}),
            **({"licenses": licenses} if licenses else {}),
        }

        return {
            "type": "webexCalling",
            "webexCalling": webex_calling
        }

    def rollback(self):
        if self.was_updated:
            self.client.workspaces.update(
                self.svc.current["id"], payload=self.svc.current
            )


class WbxcWorkspaceCallingCallerIdUpdateTask(sh.WbxcCallerIdUpdateTask):
    """
    Configure a workspace's Caller ID settings using shared WbxcCallerIdUpdateTask

    The `build_payload` method is customized because the first_name and last_name
    keys differ for a workspace payload.
    """

    def build_payload(self):
        """
        Update request requires 'caller_id_type'
        so back-fill the payload with current values for any missing include fields
        """
        include = {
            "customNumber",
            "blockInForwardCallsEnabled",
        }
        payload = self.model.to_payload(include=include, drop_unset=True)

        if self.model.caller_id_number_type:
            payload["selected"] = self.model.caller_id_number_type

        if self.model.caller_id_name_type:
            payload["externalCallerIdNamePolicy"] = self.model.caller_id_name_type

        if self.model.caller_id_name_other:
            payload["customExternalCallerIdName"] = self.model.caller_id_name_other

        if self.model.caller_id_first_name:
            payload["displayName"] = self.model.caller_id_first_name

        if self.model.caller_id_last_name:
            payload["displayDetail"] = self.model.caller_id_last_name

        return payload

    def rollback(self):
        if self.was_updated:
            self.client.workspace_caller_id.update(
                self.svc.current["id"], payload=self.current_caller_id
            )


@reg.bulk_service("wbxc", "workspace_calling", "DELETE")
class WbxcWorkspaceCallingDeleteSvc(WbxcBulkSvc):

    def run(self):
        number = self.model.phoneNumber or self.model.extension
        self.current = self.lookup.workspace(
            self.model.name,
            number=number,
            location=self.model.location
        )
        self.client.workspaces.delete(self.current["id"])


@reg.upload_task("wbxc", "workspace_calling")
class WbxcWorkspaceCallingUploadTask(UploadTask):

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


@reg.browse_service("wbxc", "workspace_calling")
class WbxcWorkspaceCallingBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WbxcWorkspaceCallingBrowseModelBuilder(self.client)
        for resp in self.client.workspaces.list():
            if is_calling_enabled_for_workspace(resp):
                model = builder.build_model(resp)
                rows.append(model.dict())

        return rows


@reg.export_service("wbxc", "workspace_calling")
class WbxcWorkspaceCallingExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = WbxcWorkspaceCalling.schema()["data_type"]
        builder = WbxcWorkspaceCallingModelBuilder(self.client)

        for resp in self.client.workspaces.list():
            if is_calling_enabled_for_workspace(resp):
                try:
                    model = builder.build_model(resp)
                    rows.append(model)
                except Exception as exc:
                    error = getattr(exc, "message", str(exc))
                    errors.append({"name": resp.get("displayName", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcWorkspaceCallingModelBuilder:
    """
    Model builder class for Webex Workspace Calling Export
    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)
        self._locations_by_id: dict | None = None

    @property
    def locations_by_id(self):
        if self._locations_by_id is None:
            self._locations_by_id = {
                resp["id"]: resp["name"]
                for resp in
                self.client.locations.list()
            }

        return self._locations_by_id

    def build_model(self, resp):
        identifier = resp["id"]
        location_name = self.get_location_name(resp)
        calling_license, sub_id = self.get_calling_license(resp)

        associated_numbers = self.get_associated_numbers(identifier, calling_license)
        emergency_callback = self.get_emergency_callback(identifier, calling_license)
        incoming_permission = self.get_incoming_permission(identifier, calling_license)
        outgoing_permission = self.get_outgoing_permission(identifier, calling_license)
        outgoing_auto_transfer = self.get_outgoing_auto_transfer(identifier, calling_license)
        call_waiting = self.get_call_waiting(identifier, calling_license)
        call_forwarding = self.get_call_forwarding(identifier, calling_license)
        compression = self.get_compression(identifier, calling_license)

        caller_id = self.get_caller_id(identifier, calling_license)
        music_on_hold = self.get_music_on_hold(identifier, calling_license)

        anonymous_call_reject = self.get_anonymous_call_reject(identifier, calling_license)
        barge_in = self.get_barge_in(identifier, calling_license)
        call_bridge = self.get_call_bridge(identifier, calling_license)
        do_not_disturb = self.get_do_not_disturb(identifier, calling_license)
        voicemail = self.get_voicemail(identifier, calling_license)
        monitoring = self.get_monitoring(identifier, calling_license)

        model = WbxcWorkspaceCalling.safe_build(
            name=resp["displayName"],
            type=resp.get("type", ""),
            capacity=resp.get("capacity", ""),
            hotdeskingStatus=resp.get("hotdeskingStatus", ""),
            notes=resp.get("notes", ""),
            supportedDevices=resp.get("supportedDevices", ""),
            licenses=calling_license,
            sub_id=sub_id,
            location=location_name,
            **associated_numbers,
            **caller_id,
            **emergency_callback,
            **incoming_permission,
            **outgoing_permission,
            **outgoing_auto_transfer,
            **music_on_hold,
            **call_waiting,
            **call_forwarding,
            **anonymous_call_reject,
            **barge_in,
            **call_bridge,
            **do_not_disturb,
            **compression,
            **voicemail,
            **monitoring,
        )

        return model

    @staticmethod
    def add_monitoring_to_row(row, monitor_dict):
        monitoring = monitor_dict.get("monitoring", [])
        for monitor in monitoring:
            index = monitor.column_id
            row[f"Monitored Number {index}"] = monitor.number
            row[f"Monitored Location {index}"] = monitor.location_name

        return row

    def get_location_name(self, resp):
        location_id = resp.get("locationId")
        if location_id:
            return self.locations_by_id.get(location_id, "")

        return ""

    def get_calling_license(self, resp):
        """
        Extracts the calling license ID from the Workspace JSON response
        then retrieves the license details, and extracts the license type
        and subscription ID.
        """
        license_name, sub_id = "", ""
        license_id = deep_get(resp, "calling.webexCalling.licenses", [""])[0]
        if license_id:
            license_resp = self.client.licenses.get(license_id)
            license_name = license_resp.get("name", "")
            sub_id = license_resp.get("subscriptionId", "")

        return license_name, sub_id

    def get_associated_numbers(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_associated_numbers.get(identifier)
        associated_numbers = resp.get("phoneNumbers", [])
        associated_number = self.get_primary_number(associated_numbers)

        return {
            "phoneNumber": associated_number.get("external", ""),
            "extension": associated_number.get("extension", ""),
        }

    @staticmethod
    def get_primary_number(numbers) -> dict:
        return next((num for num in numbers if num["primary"]), {})

    def get_caller_id(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_caller_id.get(identifier)

        return {
            "caller_id_number_type": resp.get("selected", ""),
            "customNumber": resp.get("customNumber", ""),
            "caller_id_name_type": resp.get("externalCallerIdNamePolicy", ""),
            "caller_id_name_other": resp.get("customExternalCallerIdName", ""),
            "caller_id_first_name": resp.get("displayName", ""),
            "caller_id_last_name": resp.get("displayDetail", ""),
            "blockInForwardCallsEnabled": resp.get("blockInForwardCallsEnabled", ""),
        }

    def get_emergency_callback(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_emergency_call_back.get(identifier)

        def convert_none(value):
            return "" if value == "NONE" else value

        return {
            "emergency_callback_type": convert_none(resp.get("selected", "")),
            "emergency_callback_number": deep_get(resp, "locationMemberInfo.phoneNumber", ""),
        }

    def get_incoming_permission(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_incoming_permission.get(identifier)

        return {
            "internal_custom": resp.get("useCustomEnabled", ""),
            "internalCallsEnabled": resp.get("internalCallsEnabled", ""),
            "collectCallsEnabled": resp.get("collectCallsEnabled", ""),
            "externalTransfer": resp.get("externalTransfer", ""),
        }

    def get_outgoing_permission(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_outgoing_permission.get(identifier)
        call_permissions = parse_call_permissions(resp)
        call_permissions["external_custom"] = resp.get("useCustomEnabled", "")

        return call_permissions

    def get_outgoing_auto_transfer(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_transfer_numbers.get(identifier)
        return {
            "autoTransferNumber1": resp.get("autoTransferNumber1", ""),
            "autoTransferNumber2": resp.get("autoTransferNumber2", ""),
            "autoTransferNumber3": resp.get("autoTransferNumber3", ""),
        }

    def get_music_on_hold(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_music_on_hold.get(identifier)
        return {
            "mohEnabled": resp.get("mohEnabled", ""),
            "greeting": resp.get("greeting", ""),
            "fileName": deep_get(resp, "audioAnnouncementFile.fileName", default=""),
            "level": deep_get(resp, "audioAnnouncementFile.level", default=""),
        }

    def get_call_waiting(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_call_waiting.get(identifier)

        return {
            "callWaitingEnabled": resp.get("enabled", ""),
        }

    def get_call_forwarding(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_call_forwarding.get(identifier)
        return parse_call_forwarding(resp)

    def get_anonymous_call_reject(self, identifier, calling_license):
        if "Professional" in calling_license:
            resp = self.client.workspace_anonymous_call_reject.get(identifier)
            return {
                "anonymous_enabled": resp.get("enabled", ""),
            }
        return {}

    def get_barge_in(self, identifier, calling_license):
        if "Professional" in calling_license:
            resp = self.client.workspace_barge_in.get(identifier)
            return {
                "barge_enabled": resp.get("enabled", ""),
                "toneEnabled": resp.get("toneEnabled", ""),
            }

        return {}

    def get_call_bridge(self, identifier, calling_license):
        if "Professional" in calling_license:
            resp = self.client.workspace_call_bridge.get(identifier)
            return {
                "warningToneEnabled": resp.get("warningToneEnabled", ""),
            }
        return {}

    def get_do_not_disturb(self, identifier, calling_license):
        if "Professional" in calling_license:
            resp = self.client.workspace_do_not_disturb.get(identifier)
            return {
                "dnd_enabled": resp.get("enabled", ""),
                "ringSplashEnabled": resp.get("ringSplashEnabled", ""),
            }

        return {}

    def get_compression(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_compression.get(identifier)
        return {
            "compression": resp.get("compression", ""),
        }

    def get_voicemail(self, identifier, calling_license):
        if "Professional" in calling_license:
            resp = self.client.workspace_voicemail.get(identifier)
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

        return {}

    def get_monitoring(self, identifier, calling_license):
        if "Hot desk only" in calling_license:
            return {}

        resp = self.client.workspace_monitoring.get(identifier)
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


class WbxcWorkspaceCallingBrowseModelBuilder(WbxcWorkspaceCallingModelBuilder):
    """
    Model builder class for Webex Workspace Calling Browse
    """

    def __init__(self, client):
        super().__init__(client)
        self.calling_enabled = False

    def build_model(self, resp):
        identifier = resp["id"]
        location_name = self.get_location_name(resp)
        license_name, sub_id = self.get_calling_license(resp)
        associated_numbers = self.get_associated_numbers(identifier, license_name)

        return WbxcWorkspaceCalling.safe_build(
            name=resp["displayName"],
            location=location_name,
            licenses=license_name,
            sub_id=sub_id,
            **associated_numbers,
        )
