import logging
from .shared import (
    WbxcBulkSvc,
    WbxcBulkTask,
    WbxcLookup,
    remove_to_none,
    parse_call_permissions,
)
from zeus.wbxc.services import shared_calling_tasks as sh
from copy import deepcopy
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import ExportSvc
from zeus.shared.data_type_models import yn_to_bool
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from zeus.wbxc.wbxc_models import WbxcLocationCalling

log = logging.getLogger(__name__)


class WbxcLocationCallingSvc(WbxcBulkSvc):
    """
    Configure calling-related settings on an existing
    Webex Location.

    The location must already exist. The CREATE and UPDATE
    services are identical. Both are supported for user
    convenience.

    The Location will first be enabled for calling (if not already
    enabled) before the tasks to apply settings are run.
    """

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.current_calling_enabled: bool = False
        self.current_call_settings: dict = {}
        self.current_internal_dialing: dict = {}
        self.music_on_hold_announcement: dict = {}
        self.connection_route: dict = {}
        self.internal_dialing_route: dict = {}

    def run(self):
        self.get_current()
        self.enable_calling_for_location()

        self.get_connection_route()
        self.get_call_settings()
        self.get_internal_dialing()
        self.get_music_on_hold_announcement()

        self.update_connection_route()
        self.update_call_settings()
        self.update_internal_dialing()
        self.update_voicemail()
        self.update_voice_portal()
        self.update_outgoing_permission()
        self.update_outgoing_auto_transfer()
        self.update_music_on_hold()

    def get_current(self):
        self.current = self.lookup.location(self.model.name)
        self.current_calling_enabled = self.lookup.is_calling_enabled_for_location(
            self.current["id"]
        )

    def enable_calling_for_location(self):
        if not self.current_calling_enabled:
            task = WbxcLocationCallingEnableTask(self)
            task.run()

    def get_call_settings(self):
        """
        Get the call settings details for the location.
        This info is used by the call settings task and
        connection route task
        """
        self.current_call_settings = self.client.location_call_settings.get(
            self.current["id"]
        )

    def get_connection_route(self):
        """
        Lookup the trunk or route group associated with the
        connectionName in the model, if the field is populated
        """
        if self.model.connectionName:
            self.connection_route = self.lookup.routing_choice(self.model.connectionName)

    def get_internal_dialing(self):
        """
        Get the current internal dialing settings and the trunk/
        route group associated with the unknownExtensionRouteName
        in the model, if the field is populated
        """
        self.current_internal_dialing = self.client.location_internal_dialing.get(
            self.current["id"]
        )
        if self.model.unknownExtensionRouteName:
            self.internal_dialing_route = self.lookup.routing_choice(
                self.model.unknownExtensionRouteName
            )

    def get_music_on_hold_announcement(self):
        if self.model.fileName and self.model.level:
            self.music_on_hold_announcement = self.lookup.announcement(
                self.model.fileName, self.model.level, self.current["id"]
            )

    def update_connection_route(self):
        task = WbxcLocationCallingConnectionTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_call_settings(self):
        task = WbxcLocationCallingSettingsTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_internal_dialing(self):
        task = WbxcLocationCallingInternalDialingTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_voicemail(self):
        task = WbxcLocationCallingVoicemailTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_voice_portal(self):
        task = WbxcLocationCallingVoicePortalTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def update_outgoing_permission(self):
        task = WbxcLocationCallingOutgoingPermissionsTask(
            self, self.client.location_outgoing_permission
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_outgoing_auto_transfer(self):
        task = sh.WbxcOutgoingAutoTransferUpdateTask(
            self, self.client.location_outgoing_auto_transfer
        )
        task.run()
        self.rollback_tasks.append(task)

    def update_music_on_hold(self):
        task = WbxcLocationCallingMusicOnHoldTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("wbxc", "location_calling", "CREATE")
class WbxcLocationCallingCreateSvc(WbxcLocationCallingSvc):
    pass


@reg.bulk_service("wbxc", "location_calling", "UPDATE")
class WbxcLocationCallingUpdateSvc(WbxcLocationCallingSvc):
    pass


class WbxcLocationCallingSettingsTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False
        self.update_payload = {}

    def run(self):
        self.update_payload = self.build_payload()
        if self.update_payload:
            self.client.location_call_settings.update(
                self.svc.current["id"], payload=self.update_payload
            )
            self.was_updated = True

    def build_payload(self):
        """
        call_settings request requires announcementLanguage. If it
        is not set in the model, use the Location's preferredLanguage
        (in lower-case otherwise an error will be returned). This will
        not always work as there are some differences in supported
        languages but, it allows us not to always require an announcementLanguage
        value in the workbook.
        """
        include = {
            "routingPrefix",
            "outsideDialDigit",
            "enforceOutsideDialDigit",
            "externalCallerIdName",
            "announcementLanguage",
        }
        payload = self.model.to_payload(include=include, drop_unset=True)

        default_ann_lang = self.svc.current.get("preferredLanguage")
        if "announcementLanguage" not in payload and default_ann_lang:
            payload["announcementLanguage"] = default_ann_lang.lower()

        if self.model.callingLineIdPhoneNumber:
            payload["callingLineId"] = self.build_calling_line_payload()

        return remove_to_none(payload)

    def build_calling_line_payload(self) -> dict:
        return {"phoneNumber": self.model.callingLineIdPhoneNumber}

    def rollback(self):
        """
        current_call_settings includes id and connection keys that
        we do not want to include in the request.
        """
        if self.was_updated:
            rollback_payload = {
                key: self.svc.current_call_settings[key]
                for key in self.update_payload
                if key in self.svc.current_call_settings
            }
            self.client.location_call_settings.update(
                self.svc.current["id"], payload=rollback_payload
            )


class WbxcLocationCallingConnectionTask(WbxcBulkTask):
    """
    Assign a PSTN connection (trunk or route group) to a Webex calling-enabled
    Location.

    The update request is made only if the new route differs from the current
    route.

    This task uses the same API endpoint as the Call Settings task but is
    implemented separately because the Webex API does not allow multiple
    updates to the same Location. See https://github.com/cdwlabs/zeus/issues/386.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.location_call_settings.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self):
        payload = {}
        new_route_id = deep_get(self.svc, "connection_route.id", default="")

        if new_route_id:
            current_route_id = deep_get(
                self.svc.current_call_settings, "connection.id", default=""
            )

            if new_route_id != current_route_id:
                payload["connection"] = {
                    "id": self.svc.connection_route["id"],
                    "type": self.svc.connection_route["type"],
                }

        return payload

    def rollback(self):
        if self.was_updated:
            log.info("Rollback of Location Connection settings not supported")


class WbxcLocationCallingInternalDialingTask(WbxcBulkTask):
    """
    Enable/disable unknown internal extension rerouting.

    The update request is sent only if at least one of the relevant
    model fields have a value.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.location_internal_dialing.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        """
        Use the current settings as a basis for the update payload
        and update it based on values derived from the model.
        """
        payload = {}
        if self.model.enableUnknownExtensionRoutePolicy or self.svc.internal_dialing_route:
            payload = deepcopy(self.svc.current_internal_dialing)

            if self.model.enableUnknownExtensionRoutePolicy:
                model_enable = yn_to_bool(self.model.enableUnknownExtensionRoutePolicy)
                payload["enableUnknownExtensionRoutePolicy"] = model_enable

            if self.svc.internal_dialing_route:
                payload["unknownExtensionRouteIdentity"] = self.svc.internal_dialing_route

        return payload

    def rollback(self):
        if self.was_updated:
            self.client.location_internal_dialing.update(
                self.svc.current["id"], payload=self.svc.current_internal_dialing
            )


class WbxcLocationCallingVoicemailTask(WbxcBulkTask):
    """
    Enable/disable voicemail transcription for the location.

    The update request is sent only if the model.voicemailTranscriptionEnabled
    field has a value.
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False
        self.current_voicemail: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_voicemail = self.client.location_voicemail.get(
                self.svc.current["id"]
            )

            self.client.location_voicemail.update(self.svc.current["id"], payload=payload)
            self.was_updated = True

    def build_payload(self) -> dict:
        payload = self.model.to_payload(
            include={"voicemailTranscriptionEnabled"}, drop_unset=True
        )
        return payload

    def rollback(self):
        if self.was_updated:
            self.client.location_voicemail.update(
                self.svc.current["id"], payload=self.current_voicemail
            )


class WbxcLocationCallingVoicePortalTask(WbxcBulkTask):
    """
    Update voice portal configuration for the location.

    The update request is sent if:
     - Any voice portal-related fields in the model have a value
     - The constructed payload will result in a configuration change

    The current passcode is not available through the API so any
    model with a passcode will result in an update request
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False
        self.update_payload = {}
        self.current_voiceportal: dict = {}
        self.payload_include = {
            "languageCode",
            "extension",
            "phoneNumber",
            "firstName",
            "lastName"
        }

    def run(self):
        self.update_payload = self.build_payload()
        if self.update_payload:
            self.current_voiceportal = self.client.location_voiceportal.get(
                self.svc.current["id"]
                )
            payload = self.backfill_update_payload(self.update_payload)

            self.client.location_voiceportal.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        """
        Update request requires languageCode and one of extension or phoneNumber
        so back-fill the payload with current values for any missing include fields
        """
        payload = self.model.to_payload(include=self.payload_include, drop_unset=True)

        if self.model.voicePortalName:
            payload["name"] = self.model.voicePortalName

        if self.model.passcode:
            payload["passcode"] = {
                "newPasscode": self.model.passcode,
                "confirmPasscode": self.model.passcode,
            }

        return payload

    def backfill_update_payload(self, payload):
        if payload:
            for field in ["name", *self.payload_include]:
                if field not in payload and field in self.current_voiceportal:
                    payload[field] = self.current_voiceportal[field]

        return payload

    def rollback(self):
        """
        current_voiceportal includes keys not valid for an update
        request (id, language) so a specific rollback payload is
        created using only the keys included in the update
        """
        if self.was_updated:
            rollback_payload = {
                key: self.current_voiceportal[key]
                for key in self.update_payload
                if key in self.current_voiceportal
            }
            self.client.location_voiceportal.update(
                self.svc.current["id"], payload=rollback_payload
            )


class WbxcLocationCallingOutgoingPermissionsTask(sh.WbxcOutgoingPermissionUpdateTask):
    """
    Task for managing outgoing calling permissions for a location.

    The `build_payload` method is customized because the `useCustomEnabled`
    attribute does not exist for a location.
    """

    def build_payload(self) -> dict:
        payload = {}

        calling_permissions = self.process_call_permissions()
        if calling_permissions:
            payload["callingPermissions"] = calling_permissions

        return payload


class WbxcLocationCallingMusicOnHoldTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False
        self.current_music_on_hold: dict = {}

    def run(self):
        payload = self.build_payload()
        if payload:
            self.current_music_on_hold = self.client.location_music_on_hold.get(
                self.svc.current["id"]
            )

            self.client.location_music_on_hold.update(
                self.svc.current["id"], payload=payload
            )
            self.was_updated = True

    def build_payload(self) -> dict:
        model_include = {"callHoldEnabled", "callParkEnabled", "greeting"}
        audio_file_include = {"id", "fileName", "mediaFileType", "level"}
        payload = self.model.to_payload(include=model_include, drop_unset=True)

        if self.svc.music_on_hold_announcement:
            payload["audioFile"] = {
                key: value
                for key, value in self.svc.music_on_hold_announcement.items()
                if key in audio_file_include
            }

        return payload

    def rollback(self):
        if self.was_updated:
            payload = self.current_music_on_hold
            self.client.location_music_on_hold.update(
                self.svc.current["id"], payload=payload
            )


class WbxcLocationCallingEnableTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLocationCallingSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        self.client.location_call_settings.enable_webex_calling(payload=payload)

    def build_payload(self):
        """
        address.addressLine2 cannot be less than 1 or greater than 80 characters.
        address2 is removed from the payload if empty instead of converting to None since
        the documentation states it's not required in the payload.

        announcementLanguage is required. If it is not set in the model,
        use the Location's preferredLanguage (in lower-case otherwise an
        error will be returned). This will not always work as there are
        some differences in supported languages but, it allows us not
        to require an announcementLanguage value in the workbook.
        """
        payload_address = {
            k: v for k, v in
            self.svc.current["address"].items()
            if k != "address2"
        }

        current_address2 = deep_get(self.svc.current, "address.address2", None)
        if current_address2:
            payload_address["address2"] = current_address2

        payload = {
            "id": self.svc.current["id"],
            "name": self.svc.current["name"],
            "address": payload_address,
            "timeZone": self.svc.current["timeZone"],
            "announcementLanguage": self.model.announcementLanguage,
            "preferredLanguage": self.svc.current["preferredLanguage"],
        }

        default_ann_lang = self.svc.current.get("preferredLanguage")
        if not payload["announcementLanguage"] and default_ann_lang:
            payload["announcementLanguage"] = default_ann_lang.lower()

        return payload


@reg.export_service("wbxc", "location_calling")
class WbxcLocationCallingExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        lookup = WbxcLookup(self.client)
        data_type = WbxcLocationCalling.schema()["data_type"]
        builder = WbxcLocationCallingModelBuilder(self.client)

        for resp in self.client.locations.list():
            if lookup.is_calling_enabled_for_location(resp["id"]):
                try:
                    model = builder.build_model(resp)
                    rows.append(model)
                except Exception as exc:
                    error = getattr(exc, "message", str(exc))
                    errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcLocationCallingModelBuilder:
    """
    Model builder class for Webex Location Calling export
    Only calling-enabled locations are included
    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)

    def build_models(self):
        models = []
        for resp in self.client.locations.list():
            calling_enabled = self.lookup.is_calling_enabled_for_location(resp["id"])
            if not calling_enabled:
                continue

            model = self.build_model(resp)
            models.append(model)

        return models

    def build_model(self, resp):
        identifier = resp["id"]
        calling_settings = self.get_calling_settings(identifier)
        internal_dialing = self.get_internal_dialing(identifier)
        voicemail = self.get_voicemail(identifier)
        voiceportal = self.get_voiceportal(identifier)
        outgoing_permissions = self.get_outgoing_permissions(identifier)
        outgoing_auto_transfer = self.get_outgoing_auto_transfer(identifier)
        music_on_hold = self.get_music_on_hold(identifier)

        return WbxcLocationCalling.safe_build(
            name=resp["name"],
            **calling_settings,
            **internal_dialing,
            **voicemail,
            **voiceportal,
            **outgoing_permissions,
            **outgoing_auto_transfer,
            **music_on_hold,
        )

    def get_calling_settings(self, identifier):
        resp = self.client.location_call_settings.get(identifier)
        connection_id = deep_get(resp, "connection.id", default="")
        connection_name = (
            self.lookup.routing_choice(connection_id) if connection_id else {}
        )

        return {
            "routingPrefix": resp.get("routingPrefix", ""),
            "outsideDialDigit": resp.get("outsideDialDigit", ""),
            "enforceOutsideDialDigit": resp.get("enforceOutsideDialDigit", ""),
            "externalCallerIdName": resp.get("externalCallerIdName", ""),
            "announcementLanguage": resp.get("announcementLanguage", ""),
            "callingLineIdPhoneNumber": deep_get(resp, "callingLineId.phoneNumber", ""),
            "connectionType": deep_get(resp, "connection.type", ""),
            "connectionName": connection_name.get("name", ""),
        }

    def get_internal_dialing(self, identifier):
        resp = self.client.location_internal_dialing.get(identifier)
        return {
            "enableUnknownExtensionRoutePolicy": resp["enableUnknownExtensionRoutePolicy"],
            "unknownExtensionRouteName": deep_get(
                resp, "unknownExtensionRouteIdentity.name", default=""
            ),
        }

    def get_voicemail(self, identifier):
        return self.client.location_voicemail.get(identifier)

    def get_voiceportal(self, identifier):
        resp = self.client.location_voiceportal.get(identifier)
        return {
            "voicePortalName": resp["name"],
            "languageCode": resp.get("languageCode", ""),
            "extension": resp.get("extension", ""),
            "phoneNumber": resp.get("phoneNumber", ""),
            "firstName": resp.get("firstName", ""),
            "lastName": resp.get("lastName", ""),
        }

    def get_outgoing_permissions(self, identifier):
        resp = self.client.location_outgoing_permission.get(identifier)
        return parse_call_permissions(resp)

    def get_outgoing_auto_transfer(self, identifier):
        return self.client.location_outgoing_auto_transfer.get(identifier)

    def get_music_on_hold(self, identifier):
        resp = self.client.location_music_on_hold.get(identifier)
        return {
            "callHoldEnabled": resp.get("callHoldEnabled", ""),
            "callParkEnabled": resp.get("callParkEnabled", ""),
            "greeting": resp.get("greeting", ""),
            "fileName": deep_get(resp, "audioFile.fileName", default=""),
            "level": deep_get(resp, "audioFile.level", default=""),
        }
