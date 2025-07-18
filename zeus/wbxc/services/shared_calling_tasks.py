import logging
from .shared import (
    WbxcBulkTask,
    remove_to_none,
    convert_call_permissions,
    convert_call_forwarding,
    convert_voicemail,
    backfill_payload_with_current
)
from zeus.shared.data_type_models import yn_to_bool

log = logging.getLogger(__name__)


class WbxcCallerIdUpdateTask(WbxcBulkTask):
    """
    Configure Caller ID settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_caller_id_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_caller_id_method = client_caller_id_method
        self.was_updated = False
        self.current_caller_id: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_caller_id = self.client_caller_id_method.get(
                self.svc.current["id"]
            )
            payload = backfill_payload_with_current(payload, self.current_caller_id)

            self.client_caller_id_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self):
        """
        Update request requires 'caller_id_number_type'
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
            payload["firstName"] = self.model.caller_id_first_name

        if self.model.caller_id_last_name:
            payload["lastName"] = self.model.caller_id_last_name

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_caller_id_method.update(
                self.svc.current["id"], payload=self.current_caller_id
            )


class WbxcEmergencyCallBackUpdateTask(WbxcBulkTask):
    """
    Configure emergency callback number settings.

    - Users without individual telephone numbers, such as extension-only users,
      must be set up (ECBN) to enable them to make emergency calls.
    - These users can either utilize the default ECBN for their location
      or be assigned another specific telephone number from that location
      for emergency purposes

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_emergency_callback_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_emergency_callback_method = client_emergency_callback_method
        self.was_updated = False
        self.current_emergency_callback: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_emergency_callback = self.client_emergency_callback_method.get(
                self.svc.current["id"]
            )

            self.client_emergency_callback_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self):
        """
        Update request requires 'selected'
        """
        payload = {}

        if self.model.emergency_callback_type:
            payload["selected"] = self.model.emergency_callback_type

        if self.svc.emergency_callback_number_id:
            payload["locationMemberId"] = self.svc.emergency_callback_number_id

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_emergency_callback_method.update(
                self.svc.current["id"], payload=self.current_emergency_callback
            )


class WbxcIncomingPermissionUpdateTask(WbxcBulkTask):
    """
    Modify Incoming Permission settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_incoming_permission_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_incoming_permission_method = client_incoming_permission_method
        self.was_updated = False
        self.current_incoming_permission: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_incoming_permission = self.client_incoming_permission_method.get(
                self.svc.current["id"]
            )

            self.client_incoming_permission_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self):
        include = {
            "internalCallsEnabled",
            "collectCallsEnabled",
            "externalTransfer",
        }
        payload = self.model.to_payload(include=include, drop_unset=True)

        if self.model.internal_custom:
            payload["useCustomEnabled"] = yn_to_bool(self.model.internal_custom)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_incoming_permission_method.update(
                self.svc.current["id"], payload=self.current_incoming_permission
            )


class WbxcOutgoingPermissionUpdateTask(WbxcBulkTask):
    """
    Update outgoing call permissions.

    An update request sent if any of the permission-related
    model fields has a value.
    """

    def __init__(self, svc, client_outgoing_permission_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_outgoing_permission_method = client_outgoing_permission_method
        self.was_updated = False
        self.current_outgoing_permission: dict = {}
        self.model_fields = {
            "internal_call",
            "internal_call_transfer",
            "toll_free",
            "toll_free_transfer",
            "national",
            "national_transfer",
            "international",
            "international_transfer",
            "operator_assisted",
            "operator_assisted_transfer",
            "chargeable_directory_assisted",
            "chargeable_directory_assisted_transfer",
            "special_services_i",
            "special_services_i_transfer",
            "special_services_ii",
            "special_services_ii_transfer",
            "premium_services_i",
            "premium_services_i_transfer",
            "premium_services_ii",
            "premium_services_ii_transfer",
        }

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_outgoing_permission = self.client_outgoing_permission_method.get(
                self.svc.current["id"]
            )

            self.client_outgoing_permission_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}

        if self.model.external_custom:
            payload["useCustomEnabled"] = yn_to_bool(self.model.external_custom)

        calling_permissions = self.process_call_permissions()
        if calling_permissions:
            payload["callingPermissions"] = calling_permissions

        return payload

    def process_call_permissions(self) -> list:
        model_permissions = self.model.to_payload(
            include=self.model_fields, drop_unset=True
        )

        return convert_call_permissions(model_permissions)

    def rollback(self):
        if self.was_updated:
            self.client_outgoing_permission_method.update(
                self.svc.current["id"], payload=self.current_outgoing_permission
            )


class WbxcOutgoingAutoTransferUpdateTask(WbxcBulkTask):
    """
    Configure transfer numbers for the outbound permission
    """
    def __init__(self, svc, client_transfer_numbers_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_transfer_numbers_method = client_transfer_numbers_method
        self.was_updated = False
        self.current_outgoing_auto_transfer: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_outgoing_auto_transfer = self.client_transfer_numbers_method.get(
                self.svc.current["id"]
            )

            self.client_transfer_numbers_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        include = {"autoTransferNumber1", "autoTransferNumber2", "autoTransferNumber3"}
        payload = self.model.to_payload(include=include, drop_unset=True)
        return remove_to_none(payload)

    def rollback(self):
        if self.was_updated:
            self.client_transfer_numbers_method.update(
                self.svc.current["id"], payload=self.current_outgoing_auto_transfer
            )


class WbxcMusicOnHoldUpdateTask(WbxcBulkTask):
    def __init__(self, svc, client_music_on_hold_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_music_on_hold_method = client_music_on_hold_method
        self.was_updated = False
        self.current_music_on_hold: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_music_on_hold = self.client_music_on_hold_method.get(
                self.svc.current["id"]
            )

            self.client_music_on_hold_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        model_include = {"mohEnabled", "greeting"}
        audio_file_include = {"id", "fileName", "mediaFileType", "level"}
        payload = self.model.to_payload(include=model_include, drop_unset=True)

        if self.svc.music_on_hold_announcement:
            payload["audioAnnouncementFile"] = {
                key: value
                for key, value in self.svc.music_on_hold_announcement.items()
                if key in audio_file_include
            }

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_music_on_hold_method.update(
                self.svc.current["id"], payload=self.current_music_on_hold
            )


class WbxcCallForwardingUpdateTask(WbxcBulkTask):
    """
    Update Call Forwarding settings.

    An update request sent if any of the permission-related
    model fields has a value.
    """

    def __init__(self, svc, client_call_forwarding_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_call_forwarding_method = client_call_forwarding_method
        self.was_updated = False
        self.current_call_forwarding: dict = {}
        self.model_call_forwarding_fields = {
            "always_enabled",
            "always_destination",
            "always_vm",
            "always_tone",
            "busy_enabled",
            "busy_destination",
            "busy_vm",
            "no_answer_enabled",
            "no_answer_destination",
            "no_answer_rings",
            "no_answer_vm",
        }
        self.model_business_continuity_fields = {
            "business_continuity_enabled",
            "business_continuity_destination",
            "business_continuity_vm",
        }

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_call_forwarding = self.client_call_forwarding_method.get(
                self.svc.current["id"]
            )
            payload = backfill_payload_with_current(
                payload, self.current_call_forwarding
                )

            self.client_call_forwarding_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        """
        The model will be the base for the update payload.
        The payload will be back filled with the current settings.
        If certain keys are missing, they will get cleared or defaulted.
        """
        payload = {}

        call_forwarding = self.process_call_forwarding()
        if call_forwarding :
            payload["callForwarding"] = call_forwarding

        business_continuity = self.process_business_continuity()
        if business_continuity:
            payload.update(business_continuity)

        return payload

    def process_call_forwarding(self):
        model_call_forwarding = self.model.to_payload(
            include=self.model_call_forwarding_fields, drop_unset=True
        )
        return convert_call_forwarding(model_call_forwarding)

    def process_business_continuity(self):
        model_business_continuity = self.model.to_payload(
            include=self.model_business_continuity_fields, drop_unset=True
        )
        return convert_call_forwarding(model_business_continuity)

    def rollback(self):
        if self.was_updated:
            self.client_call_forwarding_method.update(
                self.svc.current["id"], payload=self.current_call_forwarding
            )


class WbxcCallWaitingUpdateTask(WbxcBulkTask):
    """
    Enable/disable Call Waiting.

    The update request is sent only if the `model.callWaitingEnabled`
    field has a value.
    """

    def __init__(self, svc, client_call_waiting_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_call_waiting_method = client_call_waiting_method
        self.was_updated = False
        self.current_call_waiting: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_call_waiting = self.client_call_waiting_method.get(
                self.svc.current["id"]
            )

            self.client_call_waiting_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.callWaitingEnabled:
            payload["enabled"] = yn_to_bool(self.model.callWaitingEnabled)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_call_waiting_method.update(
                self.svc.current["id"], payload=self.current_call_waiting
            )


class WbxcAnonymousCallRejectUpdateTask(WbxcBulkTask):
    """
    Updates anonymous call settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_anonymous_call_reject_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_anonymous_call_reject_method = client_anonymous_call_reject_method
        self.was_updated = False
        self.current_anonymous_call_reject: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_anonymous_call_reject = self.client_anonymous_call_reject_method.get(
                self.svc.current["id"]
            )
            self.client_anonymous_call_reject_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.anonymous_enabled:
            payload["enabled"] = yn_to_bool(self.model.anonymous_enabled)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_anonymous_call_reject_method.update(
                self.svc.current["id"], payload=self.current_anonymous_call_reject
            )


class WbxcBargeInUpdateTask(WbxcBulkTask):
    """
    Updates barge in call settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_barge_in_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_barge_in_method = client_barge_in_method
        self.was_updated = False
        self.current_barge_in: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_barge_in = self.client_barge_in_method.get(
                self.svc.current["id"]
            )

            self.client_barge_in_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.barge_enabled:
            payload["enabled"] = yn_to_bool(self.model.barge_enabled)

        if self.model.toneEnabled:
            payload["toneEnabled"] = yn_to_bool(self.model.toneEnabled)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_barge_in_method.update(
                self.svc.current["id"], payload=self.current_barge_in
            )


class WbxcDoNotDisturbUpdateTask(WbxcBulkTask):
    """
    Updates DoNotDisturb settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_do_not_disturb_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_do_not_disturb_method = client_do_not_disturb_method
        self.was_updated = False
        self.current_do_not_disturb: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_do_not_disturb = self.client_do_not_disturb_method.get(
                self.svc.current["id"]
            )

            self.client_do_not_disturb_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.dnd_enabled:
            payload["enabled"] = yn_to_bool(self.model.dnd_enabled)

        if self.model.ringSplashEnabled:
            payload["ringSplashEnabled"] = yn_to_bool(self.model.ringSplashEnabled)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_do_not_disturb_method.update(
                self.svc.current["id"], payload=self.current_do_not_disturb
            )


class WbxcCompressionUpdateTask(WbxcBulkTask):
    """
    Updates compression settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_compression_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_compression_method = client_compression_method
        self.was_updated = False
        self.current_compression: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_compression = self.client_compression_method.get(
                self.svc.current["id"]
            )

            self.client_compression_method.update(self.svc.current["id"], payload=payload)
            self.was_updated = True

    def build_payload(self) -> dict:
        include = {"compression"}
        payload = self.model.to_payload(include=include, drop_unset=True)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_compression_method.update(
                self.svc.current["id"], payload=self.current_compression
            )


class WbxcCallBridgeUpdateTask(WbxcBulkTask):
    """
    Updates call bridge warning tone settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_call_bridge_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_call_bridge_method = client_call_bridge_method
        self.was_updated = False
        self.current_call_bridge: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_call_bridge = self.client_call_bridge_method.get(
                self.svc.current["id"]
            )

            self.client_call_bridge_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        include = {"warningToneEnabled"}
        payload = self.model.to_payload(include=include, drop_unset=True)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_call_bridge_method.update(
                self.svc.current["id"], payload=self.current_call_bridge
            )


class WbxcHotelingUpdateTask(WbxcBulkTask):
    """
    Updates hoteling settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_hoteling_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_hoteling_method = client_hoteling_method
        self.was_updated = False
        self.current_hoteling: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_hoteling = self.client_hoteling_method.get(self.svc.current["id"])
            self.client_hoteling_method.update(self.svc.current["id"], payload=payload)
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.hoteling_enabled:
            payload["enabled"] = yn_to_bool(self.model.hoteling_enabled)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_hoteling_method.update(
                self.svc.current["id"], payload=self.current_hoteling
            )


class WbxcBusyGreetingUploadTask(WbxcBulkTask):
    def __init__(self, svc, client_busy_voicemail_greeting_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_busy_voicemail_greeting_method = client_busy_voicemail_greeting_method
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client_busy_voicemail_greeting_method.upload(
                self.svc.current["id"], files=payload
                )
            self.was_updated = True

    def build_payload(self) -> dict:
        if self.model.sendBusyCalls_file:
            return {
                "file": (
                    self.model.sendBusyCalls_file,
                    self.svc.busy_wav_bytes,
                    "audio/wav"
                    )
                }

    def rollback(self):
        pass


class WbxcNoAnswerGreetingUploadTask(WbxcBulkTask):
    def __init__(self, svc, client_no_answer_voicemail_greeting_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_no_answer_voicemail_greeting_method = client_no_answer_voicemail_greeting_method
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client_no_answer_voicemail_greeting_method.upload(
                self.svc.current["id"], files=payload
                )
            self.was_updated = True

    def build_payload(self) -> dict:
        if self.model.sendUnansweredCalls_file:
            return {
                "file": (
                    self.model.sendUnansweredCalls_file,
                    self.svc.no_ans_wav_bytes,
                    "audio/wav"
                    )
                }

    def rollback(self):
        pass


class WbxcResetVoicemailPinTask(WbxcBulkTask):
    """
    Reset the voicemail PIN back to the default PIN set by the admin.

    The update request is sent only if the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_reset_voicemail_pin_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_reset_voicemail_pin_method = client_reset_voicemail_pin_method
        self.was_updated = False

    def run(self):
        reset_voicemail_pin = yn_to_bool(self.model.reset_voicemail_pin)

        if reset_voicemail_pin:
            self.client_reset_voicemail_pin_method.reset(self.svc.current["id"])
            self.was_updated = True

    def rollback(self):
        pass


class WbxcVoicemailPasscodeUpdateTask(WbxcBulkTask):
    """
    Updates the voicemail passcode.

    The update request is sent only if the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_voicemail_passcode_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_voicemail_passcode_method = client_voicemail_passcode_method
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client_voicemail_passcode_method.update(self.svc.current["id"], payload=payload)
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}

        if self.model.voicemail_passcode:
            payload["passcode"] = self.model.voicemail_passcode

        return payload

    def rollback(self):
        pass


class WbxcVoicemailUpdateTask(WbxcBulkTask):
    """
    Updates voicemail settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, client_voicemail_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_voicemail_method = client_voicemail_method
        self.was_updated = False
        self.current_voicemail: dict = {}
        self.model_voicemail_fields = {
            "sendAllCalls_enabled",
            "sendBusyCalls_enabled",
            "sendBusyCalls_greeting",
            "sendUnansweredCalls_enabled",
            "sendUnansweredCalls_greeting",
            "sendUnansweredCalls_numberOfRings",
            "transferToNumber_enabled",
            "transferToNumber_destination",
            "emailCopyOfMessage_enabled",
            "emailCopyOfMessage_emailId",
            "notifications_enabled",
            "notifications_destination",
            "messageStorage_mwiEnabled",
            "messageStorage_storageType",
            "messageStorage_externalEmail",
            "faxMessage_enabled",
            "faxMessage_phoneNumber",
            "faxMessage_extension",
        }

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_voicemail = self.client_voicemail_method.get(
                self.svc.current["id"]
            )
            payload = backfill_payload_with_current(payload, self.current_voicemail)

            self.client_voicemail_method.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = {}
        if self.model.vm_enabled:
            payload["enabled"] = yn_to_bool(self.model.vm_enabled)

        model_payload = self.model.to_payload(include=self.model_voicemail_fields, drop_unset=True)
        voicemail_payload = convert_voicemail(model_payload)
        payload.update(voicemail_payload)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client_voicemail_method.update(
                self.svc.current["id"], payload=self.current_voicemail
            )


class WbxcCallRecordingUpdateTask(WbxcBulkTask):
    """
    Updates call recording settings.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """
    def __init__(self, svc, client_call_recording_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_call_recording_method = client_call_recording_method
        self.was_updated = False
        self.current_call_recording: dict = {}

    def run(self):
        payload = self.build_payload()
        # RA TODO: Potential issue on payload backfill
        if payload:
            self.current_call_recording = self.client_call_recording_method.get(
                self.svc.current["id"]
            )

            self.client_call_recording_method.update(
                self.svc.current["id"], payload=payload
                )
            self.was_updated = True

    def build_payload(self) -> dict:
        """
        Return payload early if `recording_enabled` is set to `False`.

        This prevents the error: '[Error 4410] Service is not assigned
        to this subscriber: Call Recording'.
        """
        payload = {}

        if self.model.recording_enabled:
            recording_enabled = yn_to_bool(self.model.recording_enabled)
            payload["enabled"] = recording_enabled

            if not recording_enabled:
                return payload

        if self.model.record:
            payload["record"] = self.model.record

        if self.model.recordVoicemailEnabled:
            payload["recordVoicemailEnabled"] = yn_to_bool(self.model.recordVoicemailEnabled)

        if self.model.recording_enabled:
            payload["enabled"] = yn_to_bool(self.model.recording_enabled)

        if self.model.record_notification:
            payload["notification"] = self.get_notification(self.model.record_notification)

        if self.model.repeat_enabled or self.model.repeat_interval:
            payload["repeat"] = self.get_repeat(
                self.model.repeat_enabled,
                self.model.repeat_interval
            )

        if self.model.start_stop_internalCallsEnabled or self.model.start_stop_pstnCallsEnabled:
            payload["startStopAnnouncement"] = self.get_start_stop_announcement(
                self.model.start_stop_internalCallsEnabled,
                self.model.start_stop_pstnCallsEnabled
            )

        return payload

    def get_notification(self, record_notification):
        """
        The API response may include "None" as a value,
        but "None" is not valid for updates.
        """
        if record_notification == "Beep":
            return {"enabled": True, "type": "Beep"}
        elif record_notification == "Play Announcement":
            return {"enabled": True, "type": "Play Announcement"}
        else:
            return {"enabled": False}

    def get_repeat(self, repeat_enabled, repeat_interval):
        repeat = {}

        if repeat_interval:
            repeat["interval"] = repeat_interval

        if repeat_enabled:
            repeat["enabled"] = yn_to_bool(repeat_enabled)

        return backfill_payload_with_current(
            repeat, self.current_call_recording.get("repeat", {})
        )

    def get_start_stop_announcement(self, internal_calls_enabled, pstn_calls_enabled):
        announcement = {}

        if internal_calls_enabled:
            announcement["internalCallsEnabled"] = yn_to_bool(internal_calls_enabled)

        if pstn_calls_enabled:
            announcement["pstnCallsEnabled"] = yn_to_bool(pstn_calls_enabled)

        return announcement

    def rollback(self):
        if self.was_updated:
            self.client_call_recording_method.update(
                self.svc.current["id"], payload=self.current_call_recording
            )


class WbxcMonitoringUpdateTask(WbxcBulkTask):
    """
    Updates monitoring settings.

    The update request is sent only if the `enableCallParkNotification`
    field has a value and/or the `monitored_lines` field is populated.
    """

    def __init__(self, svc, client_monitoring_method, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc = svc
        self.client_monitoring_method = client_monitoring_method
        self.was_updated = False
        self.current_monitoring: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_monitoring = self.client_monitoring_method.get(
                self.svc.current["id"]
            )

            self.client_monitoring_method.update(self.svc.current["id"], payload=payload)
            self.was_updated = True

    def build_payload(self) -> dict:
        include = {"enableCallParkNotification"}
        payload = self.model.to_payload(include=include, drop_unset=True)
        if self.svc.monitored_lines:
            payload["monitoredElements"] = self.svc.monitored_lines

        return payload

    def rollback(self):
        if self.was_updated:
            payload = self.convert_current_monitoring_to_payload(self.current_monitoring)
            self.client_monitoring_method.update(
                self.svc.current["id"], payload=payload
            )

    def convert_current_monitoring_to_payload(self, current: dict) -> dict:
        """
        Converts the current monitoring data into a `UPDATE` payload format.
        Used for the rollback method.

        Example input:
        ```
        {
            "callParkNotificationEnabled": false,
            "monitoredElements": [
                {"member": {"id": "member_id_1"}},
                {"callparkextension": {"id": "callpark_id_1"}}
            ]
        }
        ```
        Example output:
        ```
        {
            "enableCallParkNotification": false,
            "monitoredElements": ["member_id_1", "callpark_id_1"]
        }
        ```
        """
        enable_call_park_notification = current.get("callParkNotificationEnabled", False)

        monitored_elements = []
        for element in current.get("monitoredElements", []):
            if "member" in element:
                monitored_elements.append(element["member"]["id"])
            elif "callparkextension" in element:
                monitored_elements.append(element["callparkextension"]["id"])

        return {
            "enableCallParkNotification": enable_call_park_notification,
            "monitoredElements": monitored_elements
        }
