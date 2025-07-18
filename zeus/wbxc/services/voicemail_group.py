import logging
from .shared import (
    WbxcBulkSvc,
    WbxcBulkTask,
    WbxcLookup,
    convert_voicemail,
)
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from zeus.wbxc.wbxc_models import WbxcVoicemailGroup
from zeus.services import BrowseSvc, ExportSvc, DetailSvc

log = logging.getLogger(__name__)


class WbxcVoicemailGroupSvc(WbxcBulkSvc):

    def __init__(self, client, model, busy_wav_bytes=None, no_ans_wav_bytes=None, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: WbxcVoicemailGroup
        self.location_id: dict = {}
        self.model_voicemail_settings_fields = {
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

    def update_voicemail_group(self):
        task = WbxcVoicemailGroupUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)

    # RA TODO: API is currently unavailable
    # def upload_greeting(self):
    #     task = WbxcVoicemailGroupGreetingTask()
    #     task.run()
    #     self.rollback_tasks.append(task)


@reg.bulk_service("wbxc", "voicemail_groups", "CREATE")
class WbxcVoicemailGroupCreateSvc(WbxcVoicemailGroupSvc):
    """
    Creates the Voicemail Group

    `enabled`, `greeting` and `greetingDescription` not applicable during
    CREATE. If they are populated an update will run for user convenience.

    If any update fails, the virtual line will be deleted in a rollback.
    """

    def run(self):
        self.get_location()
        self.create_voicemail_group()

        self.current = self.client.voicemail_group.get(self.current["id"], self.location_id)

        if self.model.to_payload(
                include={"enabled", "greeting", "greetingDescription"},
                drop_unset=True
        ):
            self.update_voicemail_group()
            # self.upload_greeting() RA TODO: API is currently unavailable

    def create_voicemail_group(self):
        """
        The API response only returns the ID.
        a separate `GET` will be used to get the
        voicemail group details used for the update tasks.
        """
        payload = self.build_payload()
        self.current = self.client.voicemail_group.create(self.location_id, payload=payload)

    def build_payload(self):
        include = {
            "name",
            "phoneNumber",
            "extension",
            "firstName",
            "lastName",
            "passcode",
            "languageCode",
            "enabled",
            "greeting",
            "greetingDescription",
        }
        payload = self.model.to_payload(include=include, drop_unset=True)

        model_vm_settings = self.model.to_payload(
            include=self.model_voicemail_settings_fields, drop_unset=True
        )
        voicemail_payload = convert_voicemail(model_vm_settings)

        payload.update(voicemail_payload)

        return payload

    def get_location(self):
        if self.model.location:
            location = self.lookup.location(self.model.location)
            self.location_id = location["id"]

    def rollback(self):
        if self.current:
            self.client.voicemail_group.delete(self.current["id"], self.location_id)


@reg.bulk_service("wbxc", "voicemail_groups", "UPDATE")
class WbxcVoicemailGroupUpdateSvc(WbxcVoicemailGroupSvc):

    def run(self):
        self.get_current()

        self.update_voicemail_group()
        # self.upload_greeting() RA TODO: API is currently unavailable

    def get_current(self):
        resp = self.lookup.voicemail_group(self.model.name)
        self.location_id = resp["locationId"]
        self.current = self.client.voicemail_group.get(
            resp["id"], self.location_id
        )


class WbxcVoicemailGroupUpdateTask(WbxcBulkTask):
    """
    """

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.client: WbxcSimpleClient
        self.svc: WbxcVoicemailGroupSvc = svc
        self.was_updated = False

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.voicemail_group.update(
                self.svc.current["id"],
                self.svc.location_id,
                payload=payload
            )
            self.was_updated = True

    def build_payload(self):
        """
        Uploading a busy greeting is currently unavailable via the API.

        When setting the `greeting` to 'Custom', a recording must already
        be uploaded via Control Hub. This automatically sets `"greetingUploaded": true`,
        which determines whether the API request will succeed. Additionally,
        when using a 'Custom' greeting, the filename `"greetingDescription"`
        must be included in the payload.
        """
        payload = {}
        if self.model.new_name:
            payload["name"] = self.model.new_name

        include = {
            "phoneNumber",
            "extension",
            "firstName",
            "lastName",
            "passcode",
            "languageCode",
            "enabled",
            "greeting",
            "greetingDescription",
        }
        model_vmg = self.svc.model.to_payload(include=include, drop_unset=True)
        payload.update(model_vmg)

        model_vm_settings = self.svc.model.to_payload(
            include=self.svc.model_voicemail_settings_fields, drop_unset=True
        )
        voicemail_payload = convert_voicemail(model_vm_settings)

        payload.update(voicemail_payload)

        return payload

    def rollback(self):
        if self.was_updated:
            self.client.voicemail_group.update(
                self.svc.current["id"],
                self.svc.location_id,
                payload=self.svc.current
            )


@reg.bulk_service("wbxc", "voicemail_groups", "DELETE")
class WbxcVoicemailGroupDeleteSvc(WbxcBulkSvc):

    def run(self):
        self.current = self.lookup.voicemail_group(self.model.name)
        self.client.voicemail_group.delete(
            self.current["id"], self.current["locationId"]
        )


@reg.browse_service("wbxc", "voicemail_groups")
class WbxcVoicemailGroupBrowseSvc(BrowseSvc):

    def run(self):
        rows = []

        for resp in self.client.voicemail_group.list():
            model = self.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            row["location_id"] = resp["locationId"]
            rows.append(row)

        return rows

    @staticmethod
    def build_model(resp):
        return WbxcVoicemailGroup.safe_build(
            name=resp["name"],
            enabled=resp["enabled"],
            location=resp["locationName"],
            extension=resp.get("extension", ""),
            phoneNumber=resp.get("phoneNumber", ""),
        )


@reg.detail_service("wbxc", "voicemail_groups")
class WbxcVoicemailGroupDetailSvc(DetailSvc):
    def run(self):
        builder = WbxcVoicemailGroupModelBuilder(self.client)
        detail_id = self.browse_row["detail_id"]
        location_id = self.browse_row["location_id"]
        location_name = self.browse_row["location"]

        resp = self.client.voicemail_group.get(detail_id, location_id)
        model = builder.build_model(resp, location_name)
        data = model.dict()

        return data


@reg.export_service("wbxc", "voicemail_groups")
class WbxcVoicemailGroupExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = WbxcVoicemailGroup.schema()["data_type"]
        builder = WbxcVoicemailGroupModelBuilder(self.client)

        for item in self.client.voicemail_group.list():
            try:
                resp = self.client.voicemail_group.get(item["id"], item["locationId"])
                model = builder.build_model(resp, item["locationName"])
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": item.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcVoicemailGroupModelBuilder:
    """
    Model builder class for Webex Voicemail Group
    Used by Export and Browse
    """

    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)

    @staticmethod
    def build_model(resp, location_name):

        return WbxcVoicemailGroup.safe_build(
            name=resp["name"],
            location=location_name,
            phoneNumber=resp.get("phoneNumber", ""),
            extension=resp.get("extension", ""),
            firstName=resp.get("firstName", ""),
            lastName=resp.get("lastName", ""),
            enabled=resp.get("enabled", ""),
            languageCode=resp.get("languageCode", ""),
            greeting=resp.get("greeting", ""),
            messageStorage_storageType=deep_get(resp, "messageStorage.storageType", default=""),
            messageStorage_externalEmail=deep_get(resp, "messageStorage.externalEmail", default=""),
            notifications_enabled=deep_get(resp, "notifications.enabled", default=""),
            notifications_destination=deep_get(resp, "notifications.destination", default=""),
            faxMessage_enabled=deep_get(resp, "faxMessage.enabled", default=""),
            faxMessage_phoneNumber=deep_get(resp, "faxMessage.phoneNumber", default=""),
            faxMessage_extension=deep_get(resp, "faxMessage.extension", default=""),
            transferToNumber_enabled=deep_get(resp, "transferToNumber.enabled", default=""),
            transferToNumber_destination=deep_get(resp, "transferToNumber.destination", default=""),
            emailCopyOfMessage_enabled=deep_get(resp, "emailCopyOfMessage.enabled", default=""),
            emailCopyOfMessage_emailId=deep_get(resp, "emailCopyOfMessage.emailId", default=""),
        )
