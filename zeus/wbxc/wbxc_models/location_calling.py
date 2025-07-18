from pydantic import Field, validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from zeus.wbxc.wbxc_models.shared import ANNOUNCEMENT_LANGUAGES, EXT_MIN, EXT_MAX, OUTGOING_PERMISSION


@reg.data_type("wbxc", "location_calling")
class WbxcLocationCalling(dm.DataTypeBase):
    action: dm.OneOfStr(("CREATE", "UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action",
        doc_notes=(
            "Select `CREATE` to enable Calling on an existing Location. "
            "Select `UPDATE` to modify an existing Calling-enabled Location."
        ),
    )
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="The name of an existing Webex location.",
        test_value="CDW",
    )
    announcementLanguage: str = Field(
        default="",
        wb_key="Announcement Language",
        doc_required="No",
        doc_value="Location's phone announcement language",
        doc_notes="",  # TODO: Add supported values to help doc
    )
    connectionType: dm.OneOfStr(("TRUNK", "ROUTE_GROUP"), required=False) = Field(
        default="",
        wb_key="PSTN Connection",
        doc_required="No",
        doc_value="Webex Calling location only supports TRUNK and ROUTE_GROUP connection type.",
        doc_notes="Only used by Export Service to indicate the connection type.",
    )
    connectionName: str = Field(
        default="",
        wb_key="PSTN Connection Name",
        doc_required="No",
        doc_value="TRUNK or ROUTE_GROUP Name.",
        doc_notes="This field is relevant only when using LGW. Only supported for `CREATE` action.",
    )
    callingLineIdPhoneNumber: str = Field(
        default="",
        wb_key="Main Number",
        doc_required="No",
        doc_value="Directory Number / Main number in E.164 Format",
    )
    routingPrefix: str = Field(
        default="",
        wb_key="Routing Prefix",
        doc_required="No",
        doc_value=f"{EXT_MIN}-{EXT_MAX} Digits (i.e. 12 or 1234567) or REMOVE to reset to None",
        doc_notes=(
            "The prefix number that can be dialed to reach the extensions at this location. "
            "Must be unique and not conflict with extension."
        ),
    )
    enableUnknownExtensionRoutePolicy: dm.OptYN = Field(
        default="",
        wb_key="Route Unknown Extensions",
        doc_required="No",
        doc_notes=(
            "When enabled, calls made from the Location to an "
            "unknown extension are routed to the selected route group/trunk."
        ),
    )
    unknownExtensionRouteName: str = Field(
        default="",
        wb_key="Route Unknown Calls to",
        doc_required="No",
        doc_value="Existing route group/trunk name.",
    )
    outsideDialDigit: str = Field(
        default="",
        wb_key="Outbound Dial Digit",
        doc_required="No",
        doc_value="0-9 or REMOVE to reset to None",
        doc_notes="Dialed to reach an outside line, default is None.",
    )
    enforceOutsideDialDigit: dm.OptYN = Field(
        default="",
        wb_key="Outbound Dial Digit Enforcement",
        doc_required="No",
        doc_notes="Enforcing outside dial digit at location level to make PSTN calls when True.",
    )
    externalCallerIdName: str = Field(
        default="",
        wb_key="External Caller ID Name",
        doc_required="No",
        doc_value="External Caller ID Name value. Unicode characters.",
    )
    voicemailTranscriptionEnabled: dm.OptYN = Field(
        default="",
        wb_key="VM Transcription",
        doc_required="No",
        doc_notes="Enable or disable voicemail transcription.",
    )
    voicePortalName: str = Field(
        default="",
        wb_key="Voice Portal Name",
        doc_required="No",
        doc_value="Voice Portal Name. The default is 'VM - Location Name'.",
    )
    languageCode: str = Field(
        default="",
        wb_key="Voice Portal Language Code",
        doc_required="Conditional",
        doc_value="Language code for voicemail group audio announcement.",
        doc_notes="Required when updating any Voice Portal settings.",
    )
    extension: str = Field(
        default="",
        wb_key="Voice Portal Extension",
        doc_required="Conditional",
        doc_value="Extension",
        doc_notes="Number or Extension is required when updating.",
    )
    phoneNumber: str = Field(
        default="",
        wb_key="Voice Portal Phone Number",
        doc_required="Conditional",
        doc_value="E.164 number",
        doc_notes="Number or Extension is required when updating.",
    )
    firstName: str = Field(
        default="",
        wb_key="Voice Portal First Name",
        doc_required="No",
        doc_value="Caller ID First Name.",
    )
    lastName: str = Field(
        default="",
        wb_key="Voice Portal Last Name",
        doc_required="No",
        doc_value="Caller ID Last Name.",
    )
    passcode: str = Field(
        default="",
        wb_key="Voice Portal Passcode",
        doc_required="No",
        doc_value="Voice Portal Admin Passcode.",
        doc_notes="Follows the Location Admin Passcode Requirements.",
    )
    internal_call: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Internal Call",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    internal_call_transfer: dm.OptYN = Field(
        default="",
        wb_key="Internal Call Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    toll_free: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Toll free",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    toll_free_transfer: dm.OptYN = Field(
        default="",
        wb_key="Toll free Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    national: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="National",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    national_transfer: dm.OptYN = Field(
        default="",
        wb_key="National Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    international: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="International",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    international_transfer: dm.OptYN = Field(
        default="",
        wb_key="International Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    operator_assisted: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Operator Assistance",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    operator_assisted_transfer: dm.OptYN = Field(
        default="",
        wb_key="Operator Assistance Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    chargeable_directory_assisted: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Chargeable Directory Assisted",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    chargeable_directory_assisted_transfer: dm.OptYN = Field(
        default="",
        wb_key="Chargeable Directory Assisted Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    special_services_i: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Special Services I",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    special_services_i_transfer: dm.OptYN = Field(
        default="",
        wb_key="Special Services I Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    special_services_ii: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Special Services II",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    special_services_ii_transfer: dm.OptYN = Field(
        default="",
        wb_key="Special Services II Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    premium_services_i: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Premium Services I",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    premium_services_i_transfer: dm.OptYN = Field(
        default="",
        wb_key="Premium Services I Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    premium_services_ii: dm.OneOfStr(OUTGOING_PERMISSION, required=False) = Field(
        default="",
        wb_key="Premium Services II",
        doc_required="No",
        doc_notes="Callers at this location can make these types of calls.",
    )
    premium_services_ii_transfer: dm.OptYN = Field(
        default="",
        wb_key="Premium Services II Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    # Location Auto Transfer Numbers
    autoTransferNumber1: str = Field(
        default="",
        wb_key="Transfer Number 1",
        doc_required="No",
        doc_value="Extension, E.164 formatted number or REMOVE.",
        doc_notes="DN Length cannot be more than 30.",
    )
    autoTransferNumber2: str = Field(
        default="",
        wb_key="Transfer Number 2",
        doc_required="No",
        doc_value="Extension, E.164 formatted number or REMOVE.",
        doc_notes="DN Length cannot be more than 30.",
    )
    autoTransferNumber3: str = Field(
        default="",
        wb_key="Transfer Number 3",
        doc_required="No",
        doc_value="Extension, E.164 formatted number or REMOVE.",
        doc_notes="DN Length cannot be more than 30.",
    )
    callHoldEnabled: dm.OptYN = Field(
        default="",
        wb_key="MoH Hold Enabled",
        doc_required="No",
        doc_notes="If enabled, music will be played when call is placed on hold.",
    )
    callParkEnabled: dm.OptYN = Field(
        default="",
        wb_key="MoH Park Enabled",
        doc_required="No",
        doc_notes="If enabled, music will be played when call is parked.",
    )
    greeting: dm.OneOfStr(("SYSTEM", "CUSTOM"), required=False) = Field(
        default="",
        wb_key="MoH Greeting",
        doc_required="Optional",
        doc_notes=(
            "Required when updating MoH settings. "
            "A media file, must have been previously selected/imported when choosing CUSTOM."
        ),
    )
    fileName: str = Field(
        default="",
        wb_key="MoH Filename",
        doc_required="No",
        doc_value="Audio announcement file name.",
    )
    level: dm.OneOfStr(("ORGANIZATION", "LOCATION"), required=False) = Field(
        default="",
        wb_key="MoH Level",
        doc_required="No",
        doc_notes="Audio announcement file type location.",
    )

    @validator("announcementLanguage", always=True)
    def validate_announcementLanguage(cls, v, values, field):
        """
        Verify announcementLanguage is set to one of the supported values for
        CREATE or UPDATE operations.
        """
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            lang = str(v).lower()
            for code, language in ANNOUNCEMENT_LANGUAGES:
                if lang == language.lower() or lang == code.lower():
                    return code

            raise ValueError(f"Invalid Announcement Language '{v}'.")

        return v

    @validator("languageCode", always=True)
    def validate_languageCode(cls, v, values, field):
        """
        Verify languageCode is one of the supported values for
        CREATE or UPDATE operations.
        """
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            lang = str(v).lower()
            for code, language in ANNOUNCEMENT_LANGUAGES:
                if lang == language.lower() or lang == code.lower():
                    return code

            raise ValueError(f"Invalid Language Code '{v}'.")

        return v

    @validator("routingPrefix", always=True)
    def validate_routingPrefix(cls, v, values, field):
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            if not 2 <= len(v) <= 7:
                raise ValueError("Routing Prefix must be 2 - 7 digits")
        return v

    class Config:
        title = "Location Calling"
        schema_extra = {
            "data_type": "location_calling",
            "id_field": "name",
            "supports": {
                "browse": False,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
