import re
import time
import logging
from pydantic import BaseModel, Field
from ...shared.helpers import deep_get
from zeus.shared import request_builder as rb
from zeus import registry as reg
from zeus.exceptions import ZeusBulkOpFailed
from zeus.wbxc.wbxc_models import devices as wm
from zeus.wbxc.wbxc_simple import WbxcSimpleClient, WbxcServerFault
from .supported_devices import build_supported_devices_map, normalized_model
from zeus.services import BrowseSvc, ExportSvc, DetailSvc, UploadTask, RowLoadResp
from .shared import WbxcBulkSvc, WbxcLookup, WbxcBulkTask, build_number_lookup_params
from .device_settings import WbxcDeviceSettingsModelBuilder

log = logging.getLogger(__name__)


class NumberLookup(BaseModel):
    """Represents the details necessary to assign a Webex Number as a device member."""

    extension: str = ""
    phoneNumber: str = ""
    owner_id: str
    owner_type: str
    location_id: str
    location_name: str

    @classmethod
    def model_from_resp(cls, resp: dict):
        return cls(
            owner_id=deep_get(resp, "owner.id"),
            owner_type=deep_get(resp, "owner.type"),
            location_id=deep_get(resp, "location.id"),
            location_name=deep_get(resp, "location.name"),
            **resp,
        )


class CurrentMember(BaseModel):
    """Represents a Webex Calling Number assignment to a device line key"""

    id: str = Field(description="Unique ID of the member")
    extension: str | None = Field(
        default=None, description="Extension associated with the Webex number"
    )
    phoneNumber: str | None = Field(
        default=None, description="E.164 number associated with the Webex number"
    )
    port: int = Field(description="Key on which the number line appears")
    lineType: str = Field(description="One of `PRIMARY` or `SHARED_CALL_APPEARANCE`")
    lineWeight: int = Field(
        description="Number of lines that have been configured for the person on the device??"
    )
    memberType: str = Field(description="One of `PEOPLE`, `PLACE`, `VIRTUAL_LINE`")
    primaryOwner: bool = Field(
        description="True if the device owner is also the number owner"
    )
    allowCallDeclineEnabled: bool = Field(
        description="When True, call declined from this appearance is declined on any other appearances of this number"
    )
    hotlineEnabled: bool = Field(description="Enables PLAR to the hotline destination")
    hotlineDestination: str | None = Field(
        default=None, description="Required if hotlineEnabled is True"
    )
    t38FaxCompressionEnabled: bool | None = Field(default=None, description="Required field for ATAs. Not present for non-ATA members")


class WbxcDeviceBulkSvc(WbxcBulkSvc):
    """Attributes and methods common to the CREATE and UPDATE services."""

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: wm.WbxcDevice = model
        self.current_members: list[CurrentMember] = []
        self.current_layout: dict = {}
        self.member_numbers: dict[str, NumberLookup] = {}
        self._model_support_data: dict = {}

    @property
    def model_support_data(self) -> dict:
        if not self._model_support_data:
            model_str = normalized_model(self.model.model)
            supported_devices = build_supported_devices_map()
            self._model_support_data = supported_devices.get(model_str, {})
        return self._model_support_data

    @property
    def current_owner_id(self):
        if "personId" in self.current:
            return self.current["personId"]
        else:
            return self.current["workspaceId"]

    def get_current_members(self):
        """Get the current member line appearances assigned to the device."""

        for resp in self.client.device_members.get(self.current["id"])["members"]:
            self.current_members.append(CurrentMember(**resp))

    def get_member_numbers(self):
        """
        Lookup member number details for the line appearances of type: 'line' or 'primary'.
        This allows the request to fail before any change occurs if a number does not exist.
        """
        for line in self.model.lines:
            if line.type in ("primary", "line"):
                self.member_numbers[line.number] = self.lookup_member_number(line.number)

    def lookup_member_number(self, number):
        for params in build_number_lookup_params(number):
            try:
                resp = self.lookup.number(**params)
                return NumberLookup.model_from_resp(resp)
            except ZeusBulkOpFailed:
                continue

        raise ZeusBulkOpFailed(f"Number: {number} not found in available lines for {self.model.mac}")

    def verify_line_1_number_is_not_changed(self):
        """
        If a Line 1 number is defined in the model,
        verify the number matches the current line 1 on the
        device. If not, fail the operation as we do not want to allow
        changing the primary line on a device. The API allows it, but
        it is not possible to do through Control Hub.
        """
        line1_model = next(
            (line for line in self.model.lines if line.idx == 1),
            None,
        )
        current_line1 = next(
            (line for line in self.current_members if line.port == 1), None
        )

        if line1_model and current_line1:
            line1_member = self.member_numbers.get(line1_model.number)
            if not line1_member or line1_member.owner_id != current_line1.id:
                raise ZeusBulkOpFailed("Cannot change Line 1 number")

    def verify_layout_button_count(self):
        """
        If the model indicates a custom layout, check that
        we know the number of line keys to include. This is necessary
        because a custom layout with fewer than the supported entries
        is not automatically padded out with open lines.

        Only need to resort to the supported_devices data if the
        current layout is 'default' because we can get the correct
        count for the current layout if it is customized.
        """
        if self.model.is_custom_layout and not self.current_layout.get("lineKeys"):
            if not self.model_support_data:
                raise ZeusBulkOpFailed(
                    f"Cannot determine line key count for model: {self.model.model}"
                )

    def verify_kem_support(self):
        """
        If the expansion_module field is populated, check the supported model
        data to verify the KEM is supported for the device model.
        """
        if self.model.expansion_module:
            support_data = self.model_support_data

            if not support_data:
                raise ZeusBulkOpFailed(
                    f"Cannot determine line key count for model: {self.model.model}"
                )

            if self.model.expansion_module not in support_data.get("kemModuleType", []):
                raise ZeusBulkOpFailed(
                    f"Expansion module: {self.model.expansion_module} not supported for model: {self.model.model}"
                )

    def update_device_members(self):
        self.verify_line_1_number_is_not_changed()
        task = WbxcDeviceMembersUpdateTask(self)
        task.run()
        self.rollback_tasks.append(task)


@reg.bulk_service("wbxc", "devices", "CREATE")
class WbxcDeviceCreateSvc(WbxcDeviceBulkSvc):
    def run(self):
        self.verify_layout_button_count()
        self.verify_kem_support()

        payload = self.build_payload()
        self.current = self.client.devices.create(payload)

        self.get_current_members()
        self.get_member_numbers()

        self.update_device_members()
        self.update_device_layout()
        self.update_device_tags()

    def build_payload(self) -> wm.WbxcDevice:
        payload = self.model.to_payload(include={"mac", "model"})

        if "@" in self.model.assignee:
            person = self.lookup.user(name=self.model.assignee)

            payload["personId"] = person["id"]
        else:
            payload["placeId"] = self.lookup_workspace_id(self.model.assignee)

        return payload

    def lookup_workspace_id(self, assignee) -> str:
        """
        Determine if the workspace is identified by name or number.
        Integer conversion will succeed for extension or E.164
        number, signaling a lookup by number. Integer conversion
        failure signals lookup by name.
        """
        try:
            int(assignee)
        except ValueError:
            ws = self.lookup.workspace_by_name(name=assignee)
        else:
            ws = self.lookup.workspace_by_number(number=assignee)

        return ws["id"]

    def update_device_layout(self):
        if self.model.is_custom_layout:
            task = WbxcDeviceLayoutUpdateTask(self)
            task.run()
            self.rollback_tasks.append(task)

    def update_device_tags(self):
        if self.model.tags_list:
            # Attempting to add tags immediately after device creation appears
            # to succeed, but the tags are not added.
            time.sleep(2)
            task = WbxcDeviceUpdateTagsTask(self)
            task.run()

    def rollback(self):
        if self.current:
            self.client.devices.delete(device_id=self.current["id"])


@reg.bulk_service("wbxc", "devices", "UPDATE")
class WbxcDeviceUpdateSvc(WbxcDeviceBulkSvc):
    def run(self):
        self.current = self.lookup.device(self.model.mac)
        self.get_current_layout()
        self.verify_layout_button_count()
        self.verify_kem_support()

        self.get_current_members()
        self.get_member_numbers()

        self.update_device_members()
        self.update_device_layout()
        self.update_device_tags()
        self.apply_changes()

    def get_current_layout(self):
        """
        Get the current layout for devices that support layouts.
        Catch the exception raised for ATAs.
        """
        try:
            self.current_layout = self.client.device_layout.get(self.current["id"])
        except WbxcServerFault:
            self.current_layout = {}

    def update_device_layout(self):
        """
        Run the layout update task if the model calls for a custom layout
        or if the model calls for a default layout and the current layout
        is custom.
        """
        if self.model.is_custom_layout or self.current_layout.get("layoutMode") == "CUSTOM":
            task = WbxcDeviceLayoutUpdateTask(self)
            task.run()
            self.rollback_tasks.append(task)

    def update_device_tags(self):
        """Empty tags in model results in removal of existing tags"""
        task = WbxcDeviceUpdateTagsTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def apply_changes(self):
        """
        Apply changes if indicated in the model but do not fail the operation
        if an error is returned.
        """
        if self.model.apply_changes == "Y":
            try:
                self.client.devices.apply_changes(self.current["id"])
            except WbxcServerFault as exc:
                log.warning(f"Apply changes for {self.model.mac} failed: {exc}")


class WbxcDeviceUpdateTagsTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.has_run = False

    def run(self):
        payload = self.build_payload(self.model.tags_list)
        self.client.devices.update(device_id=self.svc.current["id"], payload=payload)
        self.has_run = True

    @staticmethod
    def build_payload(tags_list: list[str]) -> list[dict]:
        op = "replace" if tags_list else "remove"

        return [
            {
                "op": op,
                "path": "tags",
                "value": tags_list or [],
            }
        ]

    def rollback(self) -> None:
        if self.has_run:
            payload = self.build_payload(self.svc.current["tags"])
            self.client.devices.update(device_id=self.svc.current["id"], payload=payload)


class WbxcDeviceMembersUpdateTask(WbxcBulkTask):
    """Update members (line appearances) on a device."""

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcDeviceBulkSvc = svc
        self.has_run = False
        self.member_payload_fields = [
            rb.RequiredField("allowCallDeclineEnabled", "allow_decline"),
            rb.RequiredField("hotlineEnabled", "hotline_enabled"),
            rb.RequiredField("id"),
            rb.RequiredField("lineType"),
            rb.RequiredField("lineWeight"),
            rb.RequiredField("port", alias="idx"),
            rb.RequiredField("primaryOwner", "allow_number_as_clid"),
            rb.ValuedField("lineLabel", "label"),
            rb.ValuedField("hotlineDestination", "hotline_destination"),
            rb.ValuedField("t38FaxCompressionEnabled", "t38_enabled"),
        ]

    @property
    def is_model_ata(self) -> bool:
        model_type = self.svc.model_support_data.get("type")
        return model_type == "ATA"

    def run(self):
        payload = self.build_payload()
        if payload:
            self.client.device_members.update(self.svc.current["id"], payload)
            self.has_run = True

    def build_payload(self) -> dict:
        """
        Build the payload from the line appearance line types in the model.

        Only include a primary line type if it is line 1, as
        any other primary lines are reflected in the lineWeight payload
        value.
        """
        members = []
        for line in self.model.lines:
            if line.type not in ("line", "primary"):
                continue

            if line.type == "primary" and line.idx != 1:
                continue

            member_payload = self.build_line_payload(line)
            members.append(member_payload)

        if members:
            self.ensure_payload_includes_line1(members)
            return {"members": members}

        return {}

    def build_line_payload(self, line_model: wm.WbxcDeviceLine) -> dict:
        """
        Create a line payload dict for the provided line model.

        The source for payload values differs for line additions vs.
        updates to existing lines.

        For updates to existing lines, the lineType and primaryOwner
        are taken from the corresponding current member entry.

        For new lines, a call to the `search_members` API is required to get the lineType.
        The primaryOwner is determined based on comparison of the line owner and device owner.
        The lineWeight is always one except for multiple primary lines.
        """
        line_weight = self.get_line_weight(line_model.idx)
        number = self.svc.member_numbers[line_model.number]
        member_details = next(
            (m for m in self.svc.current_members if m.id == number.owner_id), None
        )
        if member_details:
            member_payload = rb.RequestBuilder(
                fields=self.member_payload_fields,
                data=line_model.to_payload(drop_unset=True),
                current=member_details.dict(),
                lineWeight=line_weight,
            ).payload()

        else:
            member_details = self.member_search(number)
            primary_owner = True if self.svc.current_owner_id == number.owner_id else False

            member_payload = rb.RequestBuilder(
                fields=self.member_payload_fields,
                data=line_model.to_payload(drop_unset=True),
                current=member_details,
                lineWeight=line_weight,
                primaryOwner=primary_owner,
            ).payload()

        if self.is_model_ata:
            return self.fixup_member_payload_for_ata(member_payload)

        return member_payload

    @staticmethod
    def fixup_member_payload_for_ata(member_payload: dict):
        """
        Make adjustments to a member payload required for assignment to an ATA .
        - t38FaxCompressionEnabled must be present
        - lineLabel must not be present
        """
        if "t38FaxCompressionEnabled" not in member_payload:
            member_payload["t38FaxCompressionEnabled"] = False

        member_payload.pop("lineLabel", None)

        return member_payload

    def get_line_weight(self, line_idx) -> int:
        """
        Determine the lineWeight value based on the provided line index
        and other line members.
        If this is line 1 (the primary line), the weight is the count of all primary
        lines.
        Otherwise, the lineWeight is always 1
        """
        if line_idx == 1:
            primary_lines = len(
                [line for line in self.model.lines if line.type == "primary"]
            )
            return primary_lines or 1
        return 1

    def member_search(self, number: NumberLookup) -> dict:
        search_params = {}
        if number.phoneNumber:
            return self.svc.lookup.device_member_by_number(
                self.svc.current["id"],
                location_id=number.location_id,
                number=number.phoneNumber,
            )
        else:
            return self.svc.lookup.device_member_by_ext(
                self.svc.current["id"],
                location_id=number.location_id,
                ext=number.extension,
            )

    def ensure_payload_includes_line1(self, members: list[dict]):
        """
        Ensure the payload includes an entry for line 1. If not (because it was not
        specified in the worksheet row), Create an entry for it from the current
        member and add this to the list of members.

        The lineWeight does not need to be checked because the model validates that
        line 1 is present if multiple primary lines are defined.
        """
        payload_line_1 = next((m for m in members if m["port"] == 1), None)
        current_line_1 = next((m for m in self.svc.current_members if m.port == 1), None)
        if current_line_1 and not payload_line_1:
            members.append(
                rb.RequestBuilder(
                    fields=self.member_payload_fields,
                    data={},
                    current=current_line_1.dict(),
                ).payload()
            )

    def rollback(self):
        if self.has_run:
            rollback_payload = self.svc.current_members
            if rollback_payload:
                self.client.device_members.update(self.svc.current["id"], rollback_payload)


class WbxcDeviceLayoutUpdateTask(WbxcBulkTask):
    """Update line layout on a device."""

    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcDeviceBulkSvc = svc
        self.has_run = False
        self.default_mode_payload = {"layoutMode": "DEFAULT", "userReorderEnabled": False}

    @property
    def supported_line_count(self) -> int:
        """
        Return the number of supported lines based on the supported devices data.
        return 'numberOfLineKeyButtons' if present, or
        return 'numberOfLinePorts' (for ATAs) or
        return 1
        """
        data = self.svc.model_support_data
        return data.get("numberOfLineKeyButtons") or data.get("numberOfLinePorts") or 1

    @property
    def kem_line_count(self) -> int:
        """Return the number of lines on the KEM module specified in the model."""
        line_count = 0

        if self.model.expansion_module:
            try:
                line_count = int(
                    re.search(r"KEM_(\d+)", self.model.expansion_module).group(1)
                )
            except Exception as exc:
                raise ZeusBulkOpFailed(
                    f"Invalid expansion module model: {self.model.expansion_module}"
                )

        return line_count

    def build_line_key_layout_template(self) -> dict:
        """
        Create a template for the new layout payload
        If the current layout is customized, use this to create the template.
        If the current layout is default, it will not indicate how many lines the model
        supports, so use the constant dict to get the # of lines and build a template
        with all line types 'open'

        Returns:
            (dict): key is the line index, value is a line key template dictionary.
        """
        current_layout = deep_get(self.svc, "current_layout.lineKeys", default=[])

        if current_layout:
            template = {entry["lineKeyIndex"]: entry for entry in current_layout}

        else:
            template = {1: {"lineKeyIndex": 1, "lineKeyType": "PRIMARY_LINE"}}

            for idx in range(2, self.supported_line_count + 1):
                template[idx] = {"lineKeyIndex": idx, "lineKeyType": "OPEN"}

        return template

    def build_kem_layout_template(self):
        kem_layout = {}
        line_idx = self.supported_line_count + 1
        kem_count = self.svc.model_support_data["kemModuleCount"]
        total_lines_for_kem = self.kem_line_count * 2

        for kem_idx in range(1, kem_count + 1):
            for key_idx in range(1, total_lines_for_kem + 1):
                kem_layout[line_idx] = {
                    "kemModuleIndex": kem_idx,
                    "kemKeyIndex": key_idx,
                    "kemKeyType": "OPEN",
                }
                line_idx += 1

        return kem_layout

    def run(self):
        payload = self.build_payload()
        self.client.device_layout.update(self.svc.current["id"], payload)
        self.has_run = True

    def build_payload(self):
        if self.model.is_custom_layout:
            payload = {
                "layoutMode": "CUSTOM",
                "lineKeys": self.build_custom_line_keys_payload(),
            }

            if self.model.expansion_module:
                payload["kemModuleType"] = self.model.expansion_module
                payload["kemKeys"] = self.build_custom_kem_keys_payload()
        else:
            payload = self.default_mode_payload

        return payload

    def build_custom_line_keys_payload(self):
        template = self.build_line_key_layout_template()
        next_shared_line_index = 1
        shared_line_indexes_by_number = {}
        for line in self.model.lines:
            if line.idx == 1:
                continue  # Line 1 should always be primary, do not attempt to modify

            if line.idx not in template:
                continue

            api_line_type = get_api_line_type(line.type)
            entry = {"lineKeyIndex": line.idx, "lineKeyType": api_line_type}

            # Each unique shared line must have a sharedLineKeyIndex.
            # This is incremented for each unique shared line.
            # If a number has multiple appearances, the same sharedLineIndex must be used
            if api_line_type == "SHARED_LINE":
                if line.number not in shared_line_indexes_by_number:
                    shared_line_indexes_by_number[line.number] = next_shared_line_index
                    next_shared_line_index += 1

                shared_line_index = shared_line_indexes_by_number[line.number]

                entry["sharedLineIndex"] = shared_line_index

            elif line.type == "sd":
                entry["lineKeyValue"] = line.number
                entry["lineKeyLabel"] = line.label

            template[line.idx] = entry

        return [template[idx] for idx in sorted(template)]

    def build_custom_kem_keys_payload(self):
        template = self.build_kem_layout_template()
        for line in self.model.lines:
            if line.idx not in template:
                continue

            api_line_type = get_api_line_type(line.type)
            template[line.idx]["kemKeyType"] = api_line_type

            if line.type == "sd":
                template[line.idx]["kemKeyValue"] = line.number
                template[line.idx]["kemKeyLabel"] = line.label

        return [template[idx] for idx in sorted(template)]

    def rollback(self):
        if self.svc.current_layout:
            rollback_payload = self.svc.current_layout
        else:
            rollback_payload = self.default_mode_payload

        self.client.device_layout.update(self.svc.current["id"], rollback_payload)


@reg.bulk_service("wbxc", "devices", "DELETE")
class WbxcDevicesDeleteSvc(WbxcBulkSvc):
    """
    Queries for ID of the device based on the provided MAC.
    Deletes all (should only be one) found devices
    """

    def run(self):
        to_delete = self.lookup.device(self.model.mac)
        self.client.devices.delete(device_id=to_delete["id"])


@reg.upload_task("wbxc", "devices")
class WbxcDeviceUploadTask(UploadTask):
    def validate_row(self, idx: int, row: dict):
        try:
            row["lines"] = self.build_line_appearances(row)
        except Exception as exc:
            return RowLoadResp(index=idx, error=str(exc))
        return super().validate_row(idx, row)

    @staticmethod
    def build_line_appearances(row):
        """Create LineAppearance models for each set of Line X columns in the row."""
        lines = []
        for key in row:
            if m := re.search(r"Line\s(\d+)\sType", key, re.I):

                if not row[key]:
                    continue

                idx = m.group(1)
                obj = {"idx": idx}

                for wb_key, field in wm.WbxcDeviceLine.indexed_wb_keys(idx).items():
                    if wb_key in row:
                        obj[field.name] = row[wb_key]

                lines.append(wm.WbxcDeviceLine.parse_obj(obj))

        return lines


@reg.browse_service("wbxc", "devices")
class WbxcDevicesBrowseSvc(BrowseSvc):
    def run(self):
        rows = []
        builder = WbxcDeviceModelBuilder(self.client)

        params = {"type": "phone"}
        for resp in self.client.devices.list(**params):
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            rows.append(row)

        return rows


@reg.detail_service("wbxc", "devices")
class WbxcDeviceDetailSvc(DetailSvc):
    def run(self):
        builder = WbxcDeviceModelBuilder(self.client)
        detail_id = self.browse_row["detail_id"]

        resp = self.client.devices.get(detail_id)
        data = builder.build_detailed_model(resp)

        return data


@reg.export_service("wbxc", "devices")
class WbxcDevicesExportTask(ExportSvc):
    def run(self):
        rows = []
        errors = []
        data_type = wm.WbxcDevice.schema()["data_type"]
        builder = WbxcDeviceModelBuilder(self.client)

        params = {"type": "phone"}
        for resp in self.client.devices.list(**params):

            try:
                model = builder.build_export_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": self.error_row_name(resp), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}

    @staticmethod
    def error_row_name(resp):
        """
        Construct the most useful identifier from the list response.
        Use MAC address if present, otherwise use displayName or id.
        Include model if present as well.
        """
        mac = resp.get("mac", "")
        display = resp.get("displayName", "")
        model = resp.get("product", "unknown model")
        name = mac or display or resp["id"]
        return f"{name} ({model})"


class WbxcDeviceModelBuilder:
    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)
        self._model_support_data: dict = {}

    def build_model(self, resp: dict):
        return wm.WbxcDevice.safe_build(**self.summary_data(resp))

    def build_export_model(self, resp: dict):
        return wm.WbxcDevice.safe_build(
            **self.summary_data(resp),
            **self.get_layout(resp),
            assignee=self.get_assignee(resp),
        )

    def build_detailed_model(self, resp: dict):
        details = self.build_export_model(resp).dict()
        details["settings"] = self.build_device_settings(resp)
        return details

    def get_assignee(self, resp: dict):
        assignee = ""

        if resp.get("personId"):
            assignee = self.get_user_assignee(resp["personId"])
        elif resp.get("workspaceId"):
            assignee = self.get_workspace_assignee(resp["workspaceId"])

        return assignee

    def get_user_assignee(self, person_id: str) -> str:
        try:
            person = self.client.users.get(person_id, callingData=True)
        except WbxcServerFault:
            return ""

        return person.get("emails", [])[0]

    def get_workspace_assignee(self, workspace_id: str) -> str:
        """
        Attempt to get the number associated with the workspace that owns the device.
        The API will return an error if the workspace is not licensed for calling,
        which would be the case for devices configured for hybrid calling.

        Return the phoneNumber if present or the extension if not

        If neither a phone number nor extension are found, it is likely a hot-desk only
        device. In this case, there is no choice but to get the workspace name.
        """

        try:
            assign_num_resp = self.client.workspace_associated_numbers.get(workspace_id)
        except WbxcServerFault:
            assign_num_resp = {}

        number = next((num for num in assign_num_resp.get("phoneNumbers", []) if num["primary"]), {})
        assignee = number.get("external") or number.get("extension") or ""

        if not assignee:
            ws_resp = self.client.workspaces.get(workspace_id)
            assignee = ws_resp["displayName"]

        return assignee

    def get_layout(self, resp: dict):
        builder = WbxcDeviceLayoutBuilder(self.client)
        lines = builder.build_layout(resp)
        return {
            "lines": lines,
            "custom_layout": builder.is_custom_layout(),
            "expansion_module": builder.expansion_module(),
        }

    @staticmethod
    def summary_data(resp: dict):
        return dict(
            mac=resp.get("mac", ""),
            model=resp.get("product", ""),
            tags=",".join(str(tag) for tag in resp.get("tags", [])),
        )

    def build_device_settings(self, resp: dict):
        builder = WbxcDeviceSettingsModelBuilder(self.client)
        return builder.build_model(resp).dict()


class WbxcDeviceLayoutBuilder:
    """
    Get the line members and layout for a device
    and use to build a line of WbxcLineDevice models
    with idx values reflecting the actual button layout
    of the device.
    """

    def __init__(self, client):
        self.client = client
        self.layout_resp: dict = {}
        self.members_resp: dict = {}
        self.positions_by_type: dict[str, list[int]] = {}
        self._models_by_pos: dict[int, wm.WbxcDeviceLine] = {}

    def _build_positions_by_type(self, resp):
        """
        Create a list of line positions for each line type
        in a custom layout in order to assign those positions
        as requested.

        For the default layout (or custom layout without line keys),
        assume all OPEN line types.
        """
        line_keys = self.layout_resp.get("lineKeys", [])

        if not line_keys:
            self.positions_by_type["OPEN"] = list(range(1, 129))
            return

        kem_keys = self.layout_resp.get("kemKeys", [])
        kem_idx_base = self.get_number_of_phone_buttons(resp["product"])

        for item in line_keys:
            idx = item["lineKeyIndex"]
            for_type = self.positions_by_type.setdefault(item["lineKeyType"], [])
            if idx not in for_type:
                for_type.append(idx)
                for_type.sort()

        for item in kem_keys:
            idx = kem_idx_base + item["kemKeyIndex"]
            for_type = self.positions_by_type.setdefault(item["kemKeyType"], [])
            if idx not in for_type:
                for_type.append(idx)
                for_type.sort()

    @staticmethod
    def get_number_of_phone_buttons(phone_model: str):
        """
        Return the numberOfLineKeyButtons on the phone model for use
        to determine the position of kem lines.
        The first kem line position will be this value + 1

        If data for the phone model is not available, return 10 as
        the best guess. This may not be accurate but, in this case, it is better
        than failing the export
        """
        model_data = build_supported_devices_map()
        model_str = normalized_model(phone_model)
        return deep_get(model_data, [model_str, "numberOfLineKeyButtons"], default=10)

    def is_custom_layout(self):
        if self.layout_resp.get("layoutMode") == "CUSTOM":
            return True
        return False

    def expansion_module(self):
        return self.layout_resp.get("kemModuleType", "")

    def build_layout(self, resp: dict):
        """
        Get the layout and members for the device and
        build WbxcDeviceLine models to accurately reflect
        the positions of the lines on the device.

        This will include shared lines and speed dials as they
        appear on the device.

        For custom layouts, it will also include park, monitor
        position but NOT the details of the park/monitor numbers.

        For default layouts, no information regarding potential
        park/monitor lines is available

        Returns:
            List of WbxcDeviceLine instances
        """
        # fault will be raised for devices that don't support custom layout
        try:
            self.layout_resp = self.client.device_layout.get(resp["id"])
        except WbxcServerFault:
            self.layout_resp = {}

        try:
            self.members_resp = self.client.device_members.get(resp["id"])
        except WbxcServerFault as e:
            if "Group access device not found" in str(e):
                self.members_resp = {}
            else:
                raise
        self._build_positions_by_type(resp)
        self._build_from_layout()
        self._build_from_members()

        return [self._models_by_pos[idx] for idx in sorted(self._models_by_pos)]

    def get_position_for_type(self, line_type: str) -> int:
        """
        Return the next available line position for the provided line type
        or, if no positions for the type are available, return the position
        for the next OPEN line.

        If a custom layout does not have a position for the line_type, raise an
        exception to be handled by the caller.
        """
        if self.positions_by_type.get(line_type):
            return self.positions_by_type[line_type].pop(0)

        if self.positions_by_type.get("OPEN"):
            return self.positions_by_type["OPEN"].pop(0)

        raise ValueError(f"Invalid idx request for {line_type} in layout {self.layout_resp}")

    def _build_from_layout(self):
        """Create a WbxcDeviceLine instance for each entry in a custom layout."""
        line_idx = 1
        line_keys = self.layout_resp.get("lineKeys", [])
        for item in line_keys:
            model_line_type = get_model_line_type(item["lineKeyType"])

            self._models_by_pos[line_idx] = wm.WbxcDeviceLine(
                idx=line_idx,
                type=model_line_type,
                number=item.get("lineKeyValue", ""),
                label=item.get("lineKeyLabel", ""),
            )

            line_idx += 1

        kem_keys = self.layout_resp.get("kemKeys", [])
        for item in kem_keys:
            model_line_type = get_model_line_type(item["kemKeyType"])

            self._models_by_pos[line_idx] = wm.WbxcDeviceLine(
                idx=line_idx,
                type=model_line_type,
                number=item.get("kemKeyValue", ""),
                label=item.get("kemKeyLabel", ""),
            )

            line_idx += 1

    def _build_from_members(self):
        """
        Create a WbxcDeviceLine instance for each primary
        and shared line appearance assigned to this device.

        In order to show the lines in the worksheet at the same position as they
        appear on the device, check the device's layout for the next
        available position for the line type.

        The lineWeight indicates how many times the member appears on
        the device, so create multiple instances of the same member if
        lineWeight is > 1.

        If there is no available line or open position for the member, the member will
        be skipped. This can occur for customs, layouts that do not have open or line
        positions for all members assigned to the device. These won't appear on the
        device when registered, so excluding them from the export is accurate.
        """
        members = sorted(self.members_resp.get("members", []), key=lambda m: m["port"])
        for member in members:

            # Convert the member type to the layout type to look up the index
            layout_type = "PRIMARY_LINE" if member["primaryOwner"] else "SHARED_LINE"

            for _ in range(0, member["lineWeight"]):
                try:
                    idx = self.get_position_for_type(layout_type)
                except ValueError:
                    log.warning(f"No position in layout for member: {member}")
                    continue

                number = member.get("phoneNumber") or member.get("extension") or ""

                self._models_by_pos[idx] = wm.WbxcDeviceLine(
                    idx=idx,
                    number=number,
                    label=member.get("lineLabel", ""),
                    type=get_model_line_type(layout_type),
                    allow_decline=member.get("allowCallDeclineEnabled", ""),
                    hotline_enabled=member.get("hotlineEnabled", ""),
                    hotline_destination=member.get("hotlineDestination", ""),
                    t38_enabled=member.get("t38FaxCompressionEnabled", ""),
                )


LINE_TYPE_MAP = [
    ("line", "SHARED_LINE"),
    ("primary", "PRIMARY_LINE"),
    ("monitor", "MONITOR"),
    ("park", "CALL_PARK_EXTENSION"),
    ("sd", "SPEED_DIAL"),
    ("open", "OPEN"),
    ("closed", "CLOSED"),
    ("mode", "MODE_MANAGEMENT"),
]


def get_model_line_type(api_line_type: str) -> str:
    for model_type, api_type in LINE_TYPE_MAP:
        if api_line_type.lower() == api_type.lower():
            return model_type
    return ""


def get_api_line_type(model_line_type: str) -> str:
    for model_type, api_type in LINE_TYPE_MAP:
        if model_line_type.lower() == model_type.lower():
            return api_type

    return ""
