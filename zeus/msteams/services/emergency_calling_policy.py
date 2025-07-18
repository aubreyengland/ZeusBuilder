import re
import logging
from zeus import registry as reg
from .shared import MsTeamsBulkSvc
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc, UploadTask, RowLoadResp
from ..msteams_models import MsTeamsEmergencyCallingPolicy, MsTeamsEmergencyDialString
from ..msteams_simple import MsTeamsSimpleClient

log = logging.getLogger(__name__)


class MsTeamsEmergencyCallingPolicyRequestBuilder:
    """
    Shared request builder class for MS Teams Emergency Calling Policy Create and Update services.
    """

    def build_request(self, model: MsTeamsEmergencyCallingPolicy) -> dict:
        """
        Builds and validates the request payload. Nulls empty strings on optional fields.

        Args:
            model (MsTeamsEmergencyCallingPolicy): The model containing the data to be validated.

        Raises:
            ZeusBulkOpFailed: If any required fields are missing or if they are not in the correct format.

        Returns:
            dict: A validated request payload.
        """
        payload = model.to_payload()

        # Validate required fields
        if len(payload["Identity"]) < 1:
            raise ZeusBulkOpFailed("Name is required")

        # Convert boolean to Enabled/Disabled
        payload["ExternalLocationLookupMode"] = self.convert_model_lookup_mode_to_req(
            payload["ExternalLocationLookupMode"]
        )

        # Convert model DialStrings to ExtendedNotifications
        payload["ExtendedNotifications"] = []
        for dial_string in payload["DialStrings"]:
            if (
                "EmergencyDialString" not in dial_string
                or len(dial_string["EmergencyDialString"]) < 1
            ):
                raise ZeusBulkOpFailed("Emergency Dial String is required")
            elif dial_string["EmergencyDialString"] == "default":
                payload["NotificationMode"] = self.convert_model_notification_mode_to_req(
                    dial_string.pop("NotificationMode", None)
                )
                payload["NotificationDialOutNumber"] = dial_string.pop(
                    "NotificationDialOutNumber", None
                )
                payload["NotificationGroup"] = dial_string.pop("NotificationGroup", None)
                continue
            payload["ExtendedNotifications"].append(
                {
                    "EmergencyDialString": dial_string.pop("EmergencyDialString"),
                    "NotificationMode": self.convert_model_notification_mode_to_req(
                        dial_string.pop("NotificationMode", None)
                    ),
                    "NotificationDialOutNumber": dial_string.pop(
                        "NotificationDialOutNumber", None
                    ),
                    "NotificationGroup": dial_string.pop("NotificationGroup", None),
                }
            )

        # Remove the model DialStrings from the payload
        payload.pop("DialStrings")

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload

    @staticmethod
    def convert_model_lookup_mode_to_req(mode: bool) -> str:
        if mode is True:
            return "Enabled"
        return "Disabled"

    @staticmethod
    def convert_model_notification_mode_to_req(mode: str) -> str | None:
        if mode == "NOTIFICATION_ONLY":
            return "NotificationOnly"
        elif mode == "CONFERENCE_MUTED":
            return "ConferenceMuted"
        elif mode == "CONFERENCE_UNMUTED":
            return "ConferenceUnMuted"
        return None


@reg.bulk_service("msteams", "emergency_calling_policies", "CREATE")
class MsTeamsEmergencyCallingPolicyCreateSvc(
    MsTeamsBulkSvc, MsTeamsEmergencyCallingPolicyRequestBuilder
):

    def run(self):
        payload = self.build_request(self.model)
        self.lookup.emergency_calling_policy(self.model.Identity, raise_if_exists=True)
        self.client.emergency_calling_policies.create(payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "emergency_calling_policies", "UPDATE")
class MsTeamsEmergencyCallingPolicyUpdateSvc(
    MsTeamsBulkSvc, MsTeamsEmergencyCallingPolicyRequestBuilder
):

    def run(self):
        payload = self.build_request(self.model)
        self.lookup.emergency_calling_policy(self.model.Identity)
        self.client.emergency_calling_policies.update(self.model.Identity, payload)

    def rollback(self):
        pass  # no tasks to rollback


@reg.bulk_service("msteams", "emergency_calling_policies", "DELETE")
class MsTeamsEmergencyCallingPolicyDeleteSvc(MsTeamsBulkSvc):

    def run(self):
        if len(self.model.Identity) < 1:
            raise ZeusBulkOpFailed("Name is required")
        self.current = self.lookup.emergency_calling_policy(self.model.Identity)
        self.client.emergency_calling_policies.delete(self.current["Identity"])


@reg.upload_task("msteams", "emergency_calling_policies")
class MsTeamsEmergencyCallingPolicyUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            row["DialStrings"] = self.build_dial_strings(row)
        except Exception as exc:
            _ = RowLoadResp(index=idx, error=str(exc))
        return super().validate_row(idx, row)

    @staticmethod
    def build_dial_strings(row):
        """
        Convert multiple dial string values into a single list value.
        Row will have one or more keys 'Dial String X', 'Dial String X Notification Mode'.

        Turn these into a list of dictionaries.

        Example:
            row = {
                "Dial String 1": "911",
                "Dial String 1 Notification Mode": "CONFERENCE_MUTED",
                "Dial String 1 Notification Number": "12223334444",
                "Dial String 1 Notification Emails": "user1@xyz.com;user2@xyz.com",
                "Dial String 2": "912",
                "Dial String 2 Notification Mode": "CONFERENCE_MUTED",
                "Dial String 2 Notification Number": "12223334444",
                "Dial String 2 Notification Emails": "user1@xyz.com;user2@xyz.com",
            }
        Returns:
            [
                {
                    "idx": 1,
                    "EmergencyDialString": "911",
                    "NotificationMode": "CONFERENCE_MUTED",
                    "NotificationDialOutNumber": "12223334444",
                    "NotificationGroup": "user1@xyz.com;user2@xyz.com",
                },
                {
                    "idx": 2,
                    "EmergencyDialString": "912",
                    "NotificationMode": "CONFERENCE_MUTED",
                    "NotificationDialOutNumber": "12223334444",
                    "NotificationGroup": "user1@xyz.com;user2@xyz.com",
                },
            ]
        """
        dial_strings = []
        for key in row:
            if m := re.search(r"Dial\sString\s(\d+)$", key):

                if not row[key]:
                    continue

                order = m.group(1)

                mode_key = f"Dial String {order} Notification Mode"
                number_key = f"Dial String {order} Notification Number"
                emails_key = f"Dial String {order} Notification Emails"

                dial_strings.append(
                    dict(
                        idx=order,
                        EmergencyDialString=row[key],
                        NotificationMode=row.get(mode_key),
                        NotificationDialOutNumber=row.get(number_key),
                        NotificationGroup=row.get(emails_key),
                    )
                )

        return dial_strings


@reg.browse_service("msteams", "emergency_calling_policies")
class MsTeamsEmergencyCallingPolicyBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = MsTeamsEmergencyCallingPolicyModelBuilder(self.client)
        for resp in self.client.emergency_calling_policies.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = model.Identity
            row["DialStringsCount"] = len(builder.build_dial_strings(resp))
            rows.append(row)
        return rows


@reg.export_service("msteams", "emergency_calling_policies")
class MsTeamsEmergencyCallingPolicyExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsEmergencyCallingPolicy.schema()["data_type"]
        builder = MsTeamsEmergencyCallingPolicyModelBuilder(self.client)

        for resp in self.client.emergency_calling_policies.list():
            # save identity for error here because the key is popped
            # in the model builder
            identity = resp.get("Identity", "unknown")
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": identity, "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class MsTeamsEmergencyCallingPolicyModelBuilder:
    """
    Shared model builder class for MS Teams Emergency Calling Policy
    Browse and Export services.
    """

    def __init__(self, client):
        self.client: MsTeamsSimpleClient = client

    def build_model(self, resp: dict) -> MsTeamsEmergencyCallingPolicy:
        summary_data = {k: v for k, v in resp.items() if k != "ExtendedNotifications"}
        summary_data["Identity"] = self.get_identity_name(resp.pop("Identity"))
        summary_data["ExternalLocationLookupMode"] = self.get_lookup_mode(
            resp.pop("ExternalLocationLookupMode")
        )
        return MsTeamsEmergencyCallingPolicy.safe_build(**summary_data, DialStrings=[])

    def build_detailed_model(self, resp: dict) -> MsTeamsEmergencyCallingPolicy:
        dial_strings = self.build_dial_strings(resp)
        return MsTeamsEmergencyCallingPolicy.safe_build(
            Identity=self.get_identity_name(resp.pop("Identity")),
            ExternalLocationLookupMode=self.get_lookup_mode(
                resp.pop("ExternalLocationLookupMode")
            ),
            **resp,
            DialStrings=dial_strings,
        )

    def build_dial_strings(self, resp: dict) -> list[dict]:
        dial_strings = []

        if resp.get("NotificationGroup") or resp.get("NotificationDialOutNumber"):
            dial_strings.append(
                MsTeamsEmergencyDialString(
                    idx=1,
                    EmergencyDialString="default",
                    NotificationMode=self.get_notification_mode(
                        resp.pop("NotificationMode")
                    ),
                    **resp,
                )
            )

        for idx, dial_string in enumerate(
            resp.pop("ExtendedNotifications", []), start=len(dial_strings) + 1
        ):
            dial_strings.append(
                MsTeamsEmergencyDialString(
                    idx=idx,
                    NotificationMode=self.get_notification_mode(
                        dial_string.pop("NotificationMode")
                    ),
                    **dial_string,
                )
            )
        return dial_strings

    def get_identity_name(self, identity: str) -> str:
        return identity.removeprefix("Tag:")

    def get_lookup_mode(self, mode: str) -> bool:
        return True if mode == "Enabled" else False

    def get_notification_mode(self, mode: str) -> str:
        if mode is None:
            return ""
        elif mode.lower() == "notificationonly":
            return "NOTIFICATION_ONLY"
        elif mode.lower() == "conferencemuted":
            return "CONFERENCE_MUTED"
        elif mode.lower() == "conferenceunmuted":
            return "CONFERENCE_UNMUTED"
        return ""
