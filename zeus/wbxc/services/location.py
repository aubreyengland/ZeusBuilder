import logging
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc, DetailSvc
from zeus.wbxc.wbxc_models import WbxcLocation, WbxcLocationCalling
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from .shared import WbxcBulkSvc, WbxcBulkTask, WbxcLookup, parse_call_permissions

log = logging.getLogger(__name__)


def build_address_payload(model: WbxcLocation, drop_unset=False) -> dict:
    """
    Create the address payload based on the current value and the provided model.
    Ensure all address attributes are included-using model values where they differ
    from the existing values.
    """
    includes = {"address1", "address2", "city", "state", "country", "postalCode"}
    payload = model.to_payload(include=includes, drop_unset=drop_unset)
    if payload.get("address2", "").lower() == "remove":
        payload["address2"] = ""
    return payload


@reg.bulk_service("wbxc", "locations", "CREATE")
class WbxcLocationCreateSvc(WbxcBulkSvc):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.locations.create(payload=payload)

    def build_payload(self):
        return {
            "name": self.model.name,
            "timeZone": self.model.timeZone,
            "address": build_address_payload(self.model),
            "preferredLanguage": self.model.preferredLanguage,
            "latitude": self.model.latitude,
            "longitude": self.model.longitude,
            "notes": self.model.notes,
        }


@reg.bulk_service("wbxc", "locations", "UPDATE")
class WbxcLocationUpdateSvc(WbxcBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)

    def run(self):
        self.current = self.lookup.location(self.model.name)
        task = WbxcLocationUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


class WbxcLocationUpdateTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.update_payload: dict = {}

    def run(self):
        self.build_payload()
        self.client.locations.update(self.svc.current["id"], payload=self.update_payload)

    def build_payload(self):
        """
        Create an update payload including values that differ from the current values.

        NOTE: name, preferredLanguage and address are required on any UPDATE even though
        the documentation states it's not. Adding them here to the payload if there are any changes.
        """
        current_lang = self.svc.current.get("preferredLanguage", "")
        address = self.svc.current["address"].copy()
        address.update(build_address_payload(self.model, drop_unset=True))
        payload = {
            "address": address,
            "preferredLanguage": current_lang,
            "name": self.model.new_name or self.model.name,
        }

        includes = {"timeZone", "preferredLanguage", "latitude", "longitude", "notes"}
        model_payload = self.model.to_payload(include=includes, drop_unset=True)
        payload.update(model_payload)

        self.update_payload = payload

    def rollback(self):
        if self.update_payload:
            payload = {key: self.svc.current.get(key) for key in self.update_payload}
            self.client.locations.update(self.svc.current["id"], payload=payload)


@reg.browse_service("wbxc", "locations")
class WbxcLocationBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WbxcLocationModelBuilder(self.client)

        for resp in self.client.locations.list():
            model = builder.build_browse_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.detail_service("wbxc", "locations")
class WbxcLocationDetailSvc(DetailSvc):

    def run(self):
        builder = WbxcLocationCallingModelBuilder(self.client)

        resp = self.client.locations.get(self.browse_row["detail_id"])
        model = builder.build_model(resp)
        return model


@reg.export_service("wbxc", "locations")
class WbxcLocationExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = WbxcLocation.schema()["data_type"]
        builder = WbxcLocationModelBuilder(self.client)

        for resp in self.client.locations.list():
            try:
                model = builder.build_export_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcLocationModelBuilder:
    """
    Model builder class for Webex Location basic configuration
    (no calling configuration details).

    Calling enabled status is included for use in the browse table.
    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)

    def build_browse_model(self, resp: dict):
        return WbxcLocation.safe_build(
            **self.summary_data(resp),
        )

    def build_export_model(self, resp: dict):
        calling_enabled = self.lookup.is_calling_enabled_for_location(resp["id"])
        return WbxcLocation.safe_build(
            **self.summary_data(resp),
            calling_enabled=calling_enabled,
        )

    @staticmethod
    def summary_data(resp: dict) -> dict:
        address = resp.get("address") or {}

        return dict(
            name=resp["name"],
            timeZone=resp.get("timeZone", ""),
            preferredLanguage=resp.get("preferredLanguage", ""),
            latitude=resp.get("latitude", ""),
            longitude=resp.get("longitude", ""),
            notes=resp.get("notes", ""),
            # calling_enabled=calling_enabled,
            **address
        )


class WbxcLocationCallingModelBuilder:
    """
    Model builder class for Webex Location Calling export
    Only calling-enabled locations are included
    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)

    def build_model(self, resp: dict):
        calling_enabled = self.lookup.is_calling_enabled_for_location(resp["id"])
        if not calling_enabled:
            return None

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
