from .. import zoom_models as zm
from zeus import registry as reg
from .shared import ZoomBulkSvc
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc


class ZoomMeetingUserPayload:
    """Shared payload builder mixin for CREATE and UPDATE services"""

    def build_payload(self: ZoomBulkSvc):
        exclude = {"license_type", "language", "pronouns_option", "role", "status"}
        payload = self.model.to_payload(exclude=exclude)

        payload["type"] = lookup_static_id(
            "License Type", self.model.license_type, zm.LICENSE_TYPE
        )

        if self.model.language:
            payload["language"] = lookup_static_id(
                "Language", self.model.language, zm.USER_LANGUAGE
            )

        if self.model.pronouns_option:
            value = self.model.pronouns_option
            payload["pronouns_option"] = lookup_static_id(
                "Pronouns Option", value, zm.PRONOUNS_OPTION
            )

        if self.model.role:
            role = self.lookup.role(self.model.role)
            payload["role_id"] = role["id"]

        return payload


@reg.bulk_service("zoom", "users", "CREATE")
class ZoomMeetingUserCreateSvc(ZoomBulkSvc, ZoomMeetingUserPayload):

    def run(self):
        payload = {"action": "create", "user_info": self.build_payload()}
        self.current = self.client.meeting_users.create(payload=payload)


@reg.bulk_service("zoom", "users", "UPDATE")
class ZoomMeetingUserUpdateSvc(ZoomBulkSvc, ZoomMeetingUserPayload):

    def run(self):
        payload = self.build_payload()
        self.client.meeting_users.update(self.model.email, payload)


@reg.bulk_service("zoom", "users", "DELETE")
class ZoomMeetingUserDeleteSvc(ZoomBulkSvc):

    def run(self):
        self.client.meeting_users.delete(self.model.email)


def lookup_static_id(field, value, items):
    for item_id, item_value in items:
        if str(value).lower() == item_value.lower():
            return item_id

    supported = ",".join(lic[1] for lic in items)
    raise ZeusBulkOpFailed(
        message=f"Invalid {field}: '{value}'. Supported values: {supported}"
    )


@reg.browse_service("zoom", "users")
class ZoomMeetingUserBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomMeetingUserModelBuilder(self.client)

        for resp in self.client.meeting_users.list():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("zoom", "users")
class ZoomMeetingUserExportSvc(ExportSvc):

    def run(self) -> dict:
        rows = []
        errors = []
        data_type = zm.ZoomUser.schema()["data_type"]
        builder = ZoomMeetingUserModelBuilder(self.client)

        for resp in self.client.meeting_users.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("email", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomMeetingUserModelBuilder:
    def __init__(self, client):
        self.client = client

    def build_models(self):
        models = []
        for summary_user in self.client.meeting_users.list():
            resp = self.client.meeting_users.get(summary_user["id"])
            model = self.build_model(resp)
            models.append(model)

        return models

    def build_model(self, resp):
        license_type = self.lookup_static_value(resp.get("type"), zm.LICENSE_TYPE)
        language = self.lookup_static_value(resp.get("language"), zm.USER_LANGUAGE)
        pronouns_option = self.lookup_static_value(resp.get("pronouns_option"), zm.PRONOUNS_OPTION)

        return zm.ZoomUser.safe_build(
            resp,
            language=language,
            license_type=license_type,
            pronouns_option=pronouns_option,
        )

    @staticmethod
    def lookup_static_value(lookup_id, items: list, default_value="NOTFOUND"):
        for item_id, item_value in items:
            if str(lookup_id).lower() == str(item_id).lower():
                return item_value

        return default_value
