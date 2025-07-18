import re
from copy import deepcopy
from pydantic import Field, validator, BaseModel, root_validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm

LINE_TYPES = ("line", "primary", "monitor", "park", "sd", "open", "closed", "mode")


class WbxcDeviceLine(BaseModel):
    idx: int = Field(description="Line appearance index")
    type: dm.OneOfStr(LINE_TYPES, required=False) = Field(
        default="",
        wb_key="Line {IDX} Type",
        doc_required="Conditional",
    )
    number: str = Field(
        default="",
        wb_key="Line {IDX} Number",
        doc_required="Conditional",
        doc_value="Number or extension associated with line or speed dial",
    )
    label: str = Field(
        default="",
        wb_key="Line {IDX} Label",
        doc_required="No",
        doc_value="Label for line or speed dial",
        doc_notes="Label is not supported for ATA devices"
    )
    allow_decline: dm.OptYN = Field(
        default="",
        wb_key="Line {IDX} Allow Decline",
        doc_required="No",
        doc_notes="Applicable to line types: `line`, `primary`",
    )
    hotline_enabled: dm.OptYN = Field(
        default="",
        wb_key="Line {IDX} Hotline Enabled",
        doc_required="No",
        doc_notes="Applicable to line types: `line`, `primary`",
    )
    hotline_destination: str = Field(
        default="",
        wb_key="Line {IDX} Hotline Destination",
        doc_required="Conditional",
        doc_value="Hotline destination number",
        doc_notes="Required if hotline is enabled. Not applicable to speed dials",
    )
    t38_enabled: dm.OptYN = Field(
        default="",
        wb_key="Line {IDX} T38",
        doc_required="No",
        doc_notes="Only applicable ATA devices",
    )

    def to_wb(self):
        wb_row = {}
        idx = self.idx
        for wb_key, field in self.indexed_wb_keys(idx).items():
            key = wb_key.format(IDX=idx)
            value = getattr(self, field.name)
            wb_row[key] = dm.to_wb_str(value)

        return wb_row

    def to_payload(self, *, drop_unset=False, include=None, exclude=None) -> dict:
        """
        Convert the model to a dictionary suitable for use in an API request.

        Starts by using the built-in `model.dict()` method to convert the model to dictionary and,
        potentially, drop keys based on the `include` and `exclude` params

        Then uses the custom `__to_payload__` method from custom field types or
        the `default_to_payload_converter` function to get the value.

        """
        if exclude:
            exclude = set(exclude)
        else:
            exclude = set()
        # always exclude action column
        exclude.add("action")

        payload = {}
        model_obj = self.dict(include=include, exclude=exclude)

        for field in self.__fields__.values():
            if field.name not in model_obj:
                continue

            converter = getattr(field.type_, "__to_payload__", dm.default_to_payload_converter)
            converter(field, model_obj, payload, drop_unset)

        return payload

    @classmethod
    def indexed_wb_keys(cls, idx: int) -> dict:
        """
        Return a dictionary with wb_keys using the provided idx integer
        as keys and the associated field as values
        """
        field_by_indexed_wb_key = {}
        for field in cls.__fields__.values():
            wb_key = field.field_info.extra.get("wb_key")

            if wb_key:
                field_by_indexed_wb_key[wb_key.format(IDX=idx)] = field

        return field_by_indexed_wb_key

    @classmethod
    def model_doc_fields(cls):
        """Generate doc fields for the help page and worksheet template using Line index: 1"""
        doc_idx = "1"
        doc_fields = []

        for field_name, schema in cls.schema()["properties"].items():
            field = cls.__fields__[field_name]
            doc_name = ""

            if schema.get("wb_key"):
                doc_name = schema["wb_key"].format(IDX=doc_idx)

            if not doc_name or schema.get("doc_ignore"):
                continue

            field_schema = deepcopy(schema)
            field_schema["doc_key"] = doc_name

            doc_field = dm.DataTypeFieldDoc.from_data_type_field(field, field_schema)

            doc_fields.append(doc_field)

        return doc_fields


@reg.data_type("wbxc", "devices")
class WbxcDevice(dm.DataTypeBase):
    """
    ### Model
    The value for the Model column should match the value shown in the 'Device type' field when creating a device in Control Hub. For example:
    * Cisco 7821
    * Cisco 8851
    * Cisco 191
    * Cisco VG420 ATA

    > NOTE: Due to current limitations in the Webex Devices APIs, Zeus does not support 9800 model devices.
    >
    > * Model 9800 devices are not included in device exports.
    > * Model 9800 devices cannot be created or updated through bulk import.

    ### Device Assignee
    Devices can be assigned to a user or workspace by providing a unique identifier. Specify the user's Webex
    email address for user assignment. For workspaces, provide one of the following:
    * Workspace phone number
    * Workspace display name
    * Workspace extension

    Phone number is the preferred identifier as it is guaranteed unique. If the workspace does not have an
    assigned phone number, the display name or extension can be used, but the value must be unique in
    the org.

    ### Line Number
    The `Line X Number` values can be phone numbers or extensions. Phone number is preferred as it is guaranteed unique.

    NANP phone numbers can be specified as +E.164, 11-digit or 10-digit. Phone numbers where the country code is not '11
    should always be full +E.164 format.

    > NOTE
    >
    > Currently, extensions must be unique.
    > Please post a request to the Zeus Webex Space if there is a need to support overlapping dial plans.

    ### Layout
    The line key layout can be customized as part of the device import by specifying the desired line type
    in the `Line X Type` columns.

    Using the basic/default layout, line keys are automatically populated in the following order:
    * The user's primary extension (always line 1)
    * Shared/virtual line appearances
    * Monitored call park numbers assigned to the device owner
    * Monitored numbers assigned to the device owner

    A custom layout can be used to:
    * Guarantee a specific line key placement
    * Configure line key speed dials

    As custom layout is created if:
    * Any line key types other than `primary` and `line` are specified
    * The Custom Layout column is set to `Y`

    #### Line Key Types

    The supported line types are:

    * **primary**: Reserves the line key for a primary line appearance. This is the only supported value for
    `Line 1 Type`.
    * **line**: Reserves the line key for a shared/virtual line appearance. The shared line number and label are
    taken from the `Line X Number` and `Line X Label` columns.
    * **sd**: Configures the line key as a speed dial. The speed dial number and label are taken from the
    `Line X Number` and `Line X Label` columns.
    * **monitor**: Reserves the line key to be populated by an extension monitored by the user.
    * **park**: Reserves the line to be populated by a call park extension monitored by the user.
    * **open**: Allows the line to be used as-needed for lines/monitor/park extensions.
    * **closed**: Prevents the line from being used for lines/monitor/park extensions.
    * **mode**: Reserves the line for mode management.

    ### Primary Lines
    Line 1 on a Webex device is always the owner's primary line. `Line 1 Type` and `Line 1 Number`
    cannot be changed, but `Line 1 Label`, `Line 1 Allow Decline`, `Line 1 Hotline Enabled` and
    `Line 1 Hotline Destination` values can be modified.

    The "Line 1" columns can be omitted or left blank if no changes to the modifiable values are
    intended and no other primary appearances are included. If they are populated, the type must be 'primary' and the number must match
    the owner's primary extension/number.

    Multiple appearances of the primary line can be assigned to a device; however, they must be on consecutive
    line keys. For instance, to add three appearances of the primary line to a device:
    * The `Line 1 Type`, `Line 2 Type` and `Line 3 Type` values must all be 'primary'.
    * The `Line 1 Number`, `Line 2 Number` and `Line 3 Number` values must all be the owner's primary extension/number.

    ### Shared/Virtual Lines
    Additional line appearances can be imported by adding `Line X Type`, `Line X Number` columns
    to the worksheet, with `X` indicating the line index number. The line index number determines
    the relative order of lines. The actual line key a shared/virtual line populates is determined by
    the layout.

    Line appearance updates always replace the existing line appearances with those from the worksheet. So
    the worksheet should include all line appearances that should appear on the device after the update.
    Any current line appearances on the device that are not included in the submitted worksheet will be
    removed.

    ### Expansion Modules
    If a device has a Key Expansion Module (KEM) attached, and you need to customize the
    button layout, enter the KEM model in this column. The supported values are:
    * `KEM_14_KEYS`
    * `KEM_18_KEYS`
    * `KEM_20_KEYS`

    It is not necessary to indicate the number of KEMs that will be attached to the device as the
    custom layout will include entries for the maximum number of buttons.

    Check [help.webex.com](help.webex.com) for details on KEM support for various phone models and potential limitations.
    For instance, KEM_18_KEYS does not support shared line appearances currently.
    """
    mac: str = Field(
        wb_key="MAC Address",
        doc_required="Yes",
        doc_value="Twelve-character, Alpha-numeric",
        doc_notes="Do not include spaces or punctuation. Must be unique and valid for the device type",
        test_value="0027908022f1",
    )
    model: str = Field(
        wb_key="Model",
        doc_required="Yes",
        doc_value="Valid model for the device type",
        doc_notes=(
            "Should match the 'Product' name in Control Hub."
            " Examples: 'Cisco 8811', 'Cisco 9851'."
            " Cisco 9800 models are currently not supported"
        ),
    )
    assignee: str = Field(
        default="",
        wb_key="Assignee",
        doc_required="Conditional",
        doc_value="User email or workspace unique identifier",
        doc_notes="Required for `CREATE`. See [Device Assignee](device.md#device-assignee)",
    )
    tags: str = Field(
        default="",
        wb_key="Tags",
        doc_required="No",
        doc_value="Zero or more tags. Seperated by commas. `UPDATE` operation replaces all current tags.",
    )
    expansion_module: str = Field(
        default="",
        wb_key="Expansion Module",
        doc_required="No",
        doc_value="Expansion module type",
        doc_notes="One of: `KEM_14_KEYS`, `KEM_18_KEYS`, `KEM_20_KEYS`"
    )
    custom_layout: dm.OptYN = Field(
        default="",
        wb_key="Custom Layout",
        doc_required="No",
        doc_notes=(
            "Set to `Y` to create a custom layout based on the Line Type columns "
            "for models that support custom layouts"
        ),
    )
    lines: list[WbxcDeviceLine] = Field(default=[])
    apply_changes: dm.OptYN = Field(
        default="",
        wb_key="Apply Changes",
        doc_required="No",
        doc_notes="Set to `Y` to apply changes made by an `UPDATE`",
    )

    @validator("model")
    def validate_model(cls, v, values, field):
        """
        Do not allow 9800's to be imported due to API issues
        https://github.com/cdwlabs/zeus/issues/524
        """
        if values.get("action") in ("CREATE", "UPDATE"):
            if re.search(r"98\d\d", str(v)):
                raise ValueError("9800 model device are not supported")

        return v

    @validator("assignee")
    def validate_assignee(cls, v, values, field):
        """assignee must be provided for CREATE."""
        return dm.validate_value_for_create(v, values, field)

    @validator("expansion_module")
    def validate_expansion_module(cls, v, values, field):
        """Verify KEM module name if action is CREATE or UPDATE."""
        kem_names = ("KEM_14_KEYS", "KEM_18_KEYS", "KEM_20_KEYS")
        kem_value = str(v).upper()

        if values.get("action") in ("CREATE", "UPDATE"):
            if kem_value and kem_value not in kem_names:
                raise ValueError(f"Expansion Module must be one of {','.join(kem_names)}")

        return kem_value

    @root_validator()
    def validate_lines(cls, values):
        """
        Ensure the list of lines meet the primary line requirements:
        - Line 1, if present must be type: primary
        - Lines 2+ may be type: primary only if all previous lines
          are also primary and match the same number
        """
        if not values.get("action") in ("CREATE", "UPDATE"):
            return values

        lines = values.get("lines")
        if not lines:
            return values

        # Ensure lines list is sorted by idx
        lines = sorted(lines, key=lambda ln: ln.idx)
        values["lines"] = lines

        line_1 = next((ln for ln in lines if ln.idx == 1), None)
        if line_1 and line_1.type != "primary":
            raise ValueError("Line 1 Type must be 'primary'")

        # Verify multiple primary line appearances are consecutive
        # and all match the line_1 number
        prev_line = line_1
        for line in lines:
            if line == line_1:
                continue

            if line.type == "primary":
                if not line_1:
                    raise ValueError("Multiple primary lines requires Line 1 to be included")

                if any([
                    prev_line.type != "primary",
                    prev_line.number != line.number,
                    prev_line.idx != line.idx - 1,
                ]):
                    raise ValueError(
                        "Multiple primary lines must all have the same number "
                        "and be on consecutive line keys."
                    )

            prev_line = line

        return values

    @property
    def tags_list(self) -> list:
        """Return comma/semicolon-separated tags string as list."""
        if self.tags:
            return re.split(r"\s*[,|;]\s*", self.tags)
        return []

    @property
    def is_custom_layout(self) -> bool:
        """
        Return True if a custom layout is required for this device
        A custom layout is required if the custom_layout field is True
        or the line keys include any types other than 'line', 'primary'
        """
        has_feature_lines = any([line.type not in ("line", "primary") for line in self.lines])
        return dm.yn_to_bool(self.custom_layout) or has_feature_lines

    @classmethod
    def model_doc(cls):
        """Add Line 1 doc field object to model docs."""
        doc = super().model_doc()

        line_doc_fields = WbxcDeviceLine.model_doc_fields()
        doc.doc_fields.extend(line_doc_fields)
        return doc

    def to_wb(self) -> dict:
        """Custom method to add `Skill #` keys to the wb row dictionary"""
        row = super().to_wb()
        for item in sorted(self.lines, key=lambda x: x.idx):
            row.update(item.to_wb())
        return row

    class Config:
        title = "Devices"
        schema_extra = {
            "data_type": "devices",
            "id_field": "mac_address",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "detail": True,
                "help_doc": True,
            },
        }
