import re

from collections import defaultdict
from pydantic import Field, root_validator, validator, ValidationError
from zeus import registry as reg
from zeus.exceptions import ZeusConversionError
from zeus.shared import data_type_models as dm
from zeus.wbxc.wbxc_models import WbxcMonitor
from zeus.wbxc.wbxc_models.shared import OUTGOING_PERMISSION, validate_phone_numbers, validate_extension

WORKSPACE_CALLING_LICENSES = ("Professional", "Workspaces", "Hot desk only")


@reg.data_type("wbxc", "workspace_calling")
class WbxcWorkspaceCalling(dm.DataTypeBase):
    """
    ### Workspace Licensing
    Zeus supports three Webex Calling license types for workspaces:
    * Hot desk only: Supports a single device with no assigned extension or phone number.
    * Workspaces: Supports a single device with basic calling features
    * Professional: Allows multiple devices and additional features such as voicemail, recording, virtual lines

    See [Features available by license type for Webex Calling](https://help.webex.com/en-us/article/n1qbbp7/Features-available-by-license-type-for-Webex-Calling) for details.

    A Calling License must be specified to `CREATE` a workspace. Optionally, the Sub ID can be specified to ensure
    the license is pulled from the intended subscription. If a Sub ID is not provided, the first subscription found
    that includes the specified license type will be used.

    The license type can be upgraded by providing the new license type for an `UPDATE`. The license type cannot be downgraded.

    > NOTE: Cisco Calling Plan:
    >
    > Workspaces imported with a number tied to a Cisco Calling Plan will not be able to make outbound PSTN calls until the Cisco Calling Plan is enabled on the workspace in Control Hub.
    > This is done under Call Handling -> Outbound Permissions -> Cisco Calling Plan
    > Due to a limitation in the Webex Calling API, this must be done individually on each workspace.
    """
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="The name of the workspace.",
    )
    new_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable for `UPDATE` operation",
    )
    location: str = Field(
        default="",
        wb_key="Location",
        doc_required="Conditional",
        doc_value="Location name",
        doc_notes=(
            "Location associated with the workspace."
            "Required for `CREATE` action."
            "Field cannot be changed once configured."
        )
    )
    licenses: str = Field(
        default="",
        wb_key="Calling License",
        doc_required="No",
        doc_value="One of `Professional`, `Workspaces`, `Hot desk only`",
        doc_notes="If not provided for `CREATE`, `Workspaces` will be used."
    )
    sub_id: str = Field(
        default="",
        wb_key="Sub ID",
        doc_required="Conditional",
        doc_notes="Required if the license type exists in multiple subscriptions."
    )
    phoneNumber: str = Field(
        default="",
        wb_key="Phone Number",
        doc_required="Conditional",
        doc_value="E164 number.",
        doc_notes=(
            "End user phone number."
            "`phoneNumber` and/or `extension` Required for `CREATE` action."
        )
    )
    extension: str = Field(
        default="",
        wb_key="Extension",
        doc_required="Conditional",
        doc_notes=(
            "End user extension."
            "`phoneNumber` and/or `extension` Required for `CREATE` action."
        )
    )
    type: dm.OneOfStr(("notSet", "focus", "huddle", "meetingRoom", "open", "desk", "other"), required=False) = Field(
        default="",
        wb_key="Type",
        doc_required="No",
        doc_notes="The type that best describes the workspace.",
    )
    capacity: str = Field(
        default="",
        wb_key="Capacity",
        doc_required="No",
        doc_value="Number",
        doc_notes="How many people the workspace is suitable for. If set, must be 0 or higher."
    )
    hotdeskingStatus: dm.OneOfStr(("on", "off"), required=False) = Field(
        default="",
        wb_key="Hot Desking Status",
        doc_required="No",
        doc_notes="Hot desking status of the workspace.",
    )
    supportedDevices: dm.OneOfStr(("collaborationDevices", "phones"), required=False) = Field(
        default="",
        wb_key="Supported Devices",
        doc_required="Conditional",
        doc_notes=(
            "Workspace supports collaboration devices or MPP phones."
            "Required for `CREATE` action and defaults to collaboration devices if blank"
            "Field cannot be changed once configured."
        )
    )
    notes: str = Field(
        default="",
        wb_key="Notes",
        doc_required="No",
        doc_value="Notes associated to the workspace.",
    )
    # Workspace Caller ID
    caller_id_number_type: dm.OneOfStr(("DIRECT_LINE", "LOCATION_NUMBER", "CUSTOM"), required=False) = Field(
        default="",
        wb_key="Caller ID Number Type",
        doc_required="No",
        doc_notes=(
            "Which type of outgoing Caller ID will be used. This setting is for the number portion."
        ),
    )
    customNumber: str = Field(
        default="",
        wb_key="Caller ID Custom Number",
        doc_required="No",
        doc_notes=(
            "Custom number which will be shown if CUSTOM is selected as type."
            "This value must be a number from the virtual line's location, "
            "or from another location with the same country, PSTN provider as the virtual line."
        ),
    )
    caller_id_name_type: dm.OneOfStr(("DIRECT_LINE", "LOCATION", "OTHER"), required=False) = Field(
        default="",
        wb_key="Caller ID Name Type",
        doc_required="No",
        doc_notes=(
            "Which type of outgoing Caller ID will be used. This setting is for the number portion."
        ),
    )
    caller_id_name_other: str = Field(
        default="",
        wb_key="Caller ID Name Other",
        doc_required="No",
        doc_notes=(
            "Custom number which will be shown if CUSTOM is selected as type."
            "This value must be a number from the virtual line's location, "
            "or from another location with the same country, PSTN provider as the virtual line."
        ),
    )
    caller_id_first_name: str = Field(
        default="",
        wb_key="Caller ID First Name",
        doc_required="No",
        doc_value="",
    )
    caller_id_last_name: str = Field(
        default="",
        wb_key="Caller ID Last Name",
        doc_required="No",
        doc_value="",
    )
    blockInForwardCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Block Caller ID",
        doc_required="No",
        doc_notes="Block this virtual line's identity when receiving a call.",
    )
    # Workspace Emergency Call Back
    emergency_callback_type: dm.OneOfStr(("DIRECT_LINE", "LOCATION_ECBN", "LOCATION_MEMBER_NUMBER"),
                                         required=False) = Field(
        default="",
        wb_key="Emergency Callback Type",
        doc_required="No",
        doc_notes=(
            "The source from which the emergency calling line ID (CLID) is selected for an actual emergency call."
        ),
    )
    emergency_callback_number: str = Field(
        default="",
        wb_key="Emergency Callback Number",
        doc_required="No",
        doc_value="",
        doc_notes="E164 number within the location.",
    )
    # Workspace Incoming Permissions
    internal_custom: dm.OptYN = Field(
        default="",
        wb_key="Incoming Custom Enabled",
        doc_required="No",
        doc_notes="Incoming Permission state. If disabled, the default settings are used.",
    )
    internalCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Incoming Internal Calls",
        doc_required="No",
        doc_notes="Flag to indicate if the workspace can receive internal calls.",
    )
    collectCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Incoming Collect Calls",
        doc_required="No",
        doc_notes="Flag to indicate if the workspace can receive collect calls.",
    )
    externalTransfer: dm.OneOfStr(
        ("ALLOW_ALL_EXTERNAL", "ALLOW_ONLY_TRANSFERRED_EXTERNAL", "BLOCK_ALL_EXTERNAL"), required=False) = Field(
        default="",
        wb_key="Incoming External Calls",
        doc_required="No",
        doc_notes=(
            "Indicate call transfer setting."
        ),
    )
    # Workspace Outgoing Permissions
    external_custom: dm.OptYN = Field(
        default="",
        wb_key="External Custom Enabled",
        doc_required="No",
        doc_notes="Incoming Permission state. If disabled, the default settings are used.",
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
    # Workspace Auto Transfer Numbers
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
    # Workspace Music On Hold
    mohEnabled: dm.OptYN = Field(
        default="",
        wb_key="MoH Enabled",
        doc_required="No",
        doc_notes="Music on hold is enabled or disabled for the workspace.",
    )
    greeting: dm.OneOfStr(("DEFAULT", "CUSTOM"), required=False) = Field(
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
    # Workspace Call Forwarding
    always_enabled: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding Always Enabled",
        doc_required="No",
        doc_notes="'Always' call forwarding is enabled or disabled.",
    )
    always_destination: str = Field(
        default="",
        wb_key="Call Forwarding Always Phone Number",
        doc_required="Conditional",
        doc_value="Destination for 'Always' call forwarding. If enabled true, destination is required.",
    )
    always_vm: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding Always Send To Voicemail Enabled",
        doc_required="No",
        doc_notes=(
            "Indicates enabled or disabled state of sending incoming calls to voicemail."
            "The destination number must be an internal phone number or extension, and has voicemail enabled."
        ),
    )
    always_tone: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding Always Play Tone Enabled",
        doc_required="No",
        doc_notes="If true, a brief tone will be played on the person's phone when a call has been forwarded.",
    )
    busy_enabled: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding Busy Enabled",
        doc_required="No",
        doc_notes="'Busy' call forwarding is enabled or disabled.",
    )
    busy_destination: str = Field(
        default="",
        wb_key="Call Forwarding Busy Phone Number",
        doc_required="Conditional",
        doc_value="Destination for 'Busy' call forwarding. If enabled true, destination is required.",
    )
    busy_vm: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding Busy Send To Voicemail Enabled",
        doc_required="No",
        doc_notes=(
            "Indicates enabled or disabled state of sending incoming calls to voicemail."
            "The destination number must be an internal phone number or extension, and has voicemail enabled."
        ),
    )
    no_answer_enabled: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding No Answer Enabled",
        doc_required="No",
        doc_notes="'No Answer' call forwarding is enabled or disabled.",
    )
    no_answer_destination: str = Field(
        default="",
        wb_key="Call Forwarding No Answer Phone Number",
        doc_required="Conditional",
        doc_value="Destination for 'No Answer' call forwarding. If enabled true, destination is required.",
    )
    no_answer_rings: str = Field(
        default="",
        wb_key="Call Forwarding No Answer Number Of Rings",
        doc_required="No",
        doc_value="2 through 20",
        doc_notes="Number of rings before the call will be forwarded if unanswered.",
    )
    no_answer_vm: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding No Answer Send To Voicemail Enabled",
        doc_required="No",
        doc_notes=(
            "Indicates enabled or disabled state of sending incoming calls to voicemail."
            "The destination number must be an internal phone number or extension, and has voicemail enabled."
        ),
    )
    business_continuity_enabled: dm.OptYN = Field(
        default="",
        wb_key="Business Continuity Enabled",
        doc_required="No",
        doc_notes="'Business Continuity' is enabled or disabled.",
    )
    business_continuity_destination: str = Field(
        default="",
        wb_key="Business Continuity Phone Number",
        doc_required="Destination for 'Business Continuity'. If enabled true, destination is required.",
        doc_value="tbd.",
    )
    business_continuity_vm: dm.OptYN = Field(
        default="",
        wb_key="Business Continuity Send To Voicemail Enabled",
        doc_required="No",
        doc_notes=(
            "Indicates enabled or disabled state of sending incoming calls to voicemail."
            "The destination number must be an internal phone number or extension, and has voicemail enabled."
        ),
    )
    # Workspace Call Waiting
    callWaitingEnabled: dm.OptYN = Field(
        default="",
        wb_key="Call Waiting Enabled",
        doc_required="No",
        doc_notes="Call Waiting state.",
    )
    # Workspace Compression
    compression: dm.OneOfStr(("ON", "OFF"), required=False) = Field(
        default="",
        wb_key="Compression",
        doc_required="No",
        doc_notes="Audio Compression is enabled or disabled.",
    )
    # Workspace Anonymous
    anonymous_enabled: dm.OptYN = Field(
        default="",
        wb_key="Anonymous Rejection Enabled",
        doc_required="No",
        doc_notes="Anonymous Call Rejection feature is enabled or disabled.",
    )
    # Workspace Barge
    barge_enabled: dm.OptYN = Field(
        default="",
        wb_key="Barge In Enabled",
        doc_required="No",
        doc_notes="BargeIn feature is enabled or disabled.",
    )
    toneEnabled: dm.OptYN = Field(
        default="",
        wb_key="Barge Tone Enabled",
        doc_required="No",
        doc_notes="When enabled, a tone is played when someone barges into a call",
    )
    # Workspace Call Bridge
    warningToneEnabled: dm.OptYN = Field(
        default="",
        wb_key="Call Bridge Tone Enabled",
        doc_required="No",
        doc_notes="Call Bridge Warning Tone feature is enabled or disabled.",
    )
    # Workspace Do Not Disturbed
    dnd_enabled: dm.OptYN = Field(
        default="",
        wb_key="DND Enabled",
        doc_required="No",
        doc_notes="DoNotDisturb feature is enabled or disabled.",
    )
    ringSplashEnabled: dm.OptYN = Field(
        default="",
        wb_key="DND Ring Enabled",
        doc_required="No",
        doc_notes="enables ring reminder when you receive an incoming call while on Do Not Disturb",
    )
    # Workspace Voicemail
    vm_enabled: dm.OptYN = Field(
        default="",
        wb_key="VM Enabled",
        doc_required="No",
        doc_notes="Voicemail is enabled or disabled.",
    )
    sendAllCalls_enabled: dm.OptYN = Field(
        default="",
        wb_key="Send All to VM",
        doc_required="No",
        doc_notes="All calls will be sent to voicemail.",
    )
    sendBusyCalls_enabled: dm.OptYN = Field(
        default="",
        wb_key="Send Busy Calls Enabled",
        doc_required="No",
        doc_notes="Calls will be sent to voicemail when busy",
    )
    sendBusyCalls_greeting: dm.OneOfStr(("DEFAULT", "CUSTOM"), required=False) = Field(
        default="",
        wb_key="Send Busy Calls Greeting",
        doc_required="No",
        doc_notes="Indicates the greeting type played.",
    )
    sendBusyCalls_file: str = Field(
        default="",
        wb_key="Send Busy Calls File",
        doc_required="No",
        doc_value="Filename",
        doc_notes="",
    )
    sendUnansweredCalls_enabled: dm.OptYN = Field(
        default="",
        wb_key="Send Unanswered Calls Enabled",
        doc_required="No",
        doc_notes="Calls will be sent to voicemail when unanswered",
    )
    sendUnansweredCalls_greeting: dm.OneOfStr(("DEFAULT", "CUSTOM"), required=False) = Field(
        default="",
        wb_key="Send Unanswered Calls Greeting",
        doc_required="No",
        doc_notes="Indicates the greeting type played.",
    )
    sendUnansweredCalls_file: str = Field(
        default="",
        wb_key="Send Unanswered Calls File",
        doc_required="No",
        doc_value="Filename",
        doc_notes="",
    )
    sendUnansweredCalls_numberOfRings: str = Field(
        default="",
        wb_key="Send Unanswered Rings",
        doc_required="No",
        doc_value="2 through 20",
        doc_notes="Number of rings before the call will be forwarded if unanswered.",
    )
    transferToNumber_enabled: dm.OptYN = Field(
        default="",
        wb_key="Transfer 0 Enabled",
        doc_required="No",
        doc_notes="Enable or disable voicemail caller transfer to a destination by pressing zero (0)",
    )
    transferToNumber_destination: str = Field(
        default="",
        wb_key="Transfer 0 Destination",
        doc_required="No",
        doc_value="",
        doc_notes="Number voicemail caller will be transferred to when they press zero (0)",
    )
    emailCopyOfMessage_enabled: dm.OptYN = Field(
        default="",
        wb_key="Email Copy Enabled",
        doc_required="No",
        doc_notes="Enable or disable email copy of voicemail.",
    )
    emailCopyOfMessage_emailId: str = Field(
        default="",
        wb_key="Email Copy Address",
        doc_required="No",
        doc_value="",
        doc_notes="Email address to which the new voicemail audio will be sent.",
    )
    notifications_enabled: dm.OptYN = Field(
        default="",
        wb_key="Notifications Enabled",
        doc_required="No",
        doc_notes="Enable or disable notifications",
    )
    notifications_destination: str = Field(
        default="",
        wb_key="Notifications Destination",
        doc_required="No",
        doc_value="",
        doc_notes=(
            "Email address to which the notification will be sent."
            "For text messages, use an email to text message gateway like 2025551212@txt.att.net"
        )
    )
    messageStorage_mwiEnabled: dm.OptYN = Field(
        default="",
        wb_key="Storage MWI",
        doc_required="No",
        doc_notes="Enable or disable MWI",
    )
    messageStorage_storageType: dm.OneOfStr(("INTERNAL", "EXTERNAL"), required=False) = Field(
        default="",
        wb_key="Storage Type",
        doc_required="No",
        doc_notes="Designates which type of voicemail message storage is used.",
    )
    messageStorage_externalEmail: str = Field(
        default="",
        wb_key="Storage Email",
        doc_required="No",
        doc_value="",
        doc_notes="External email address to which the new voicemail audio will be sent.",
    )
    faxMessage_enabled: dm.OptYN = Field(
        default="",
        wb_key="Fax Message Enabled",
        doc_required="No",
        doc_notes="When enabled, FAX messages for new voicemails are sent to the designated number.",
    )
    faxMessage_phoneNumber: str = Field(
        default="",
        wb_key="Fax Message Number",
        doc_required="No",
        doc_value="",
        doc_notes="Designates FAX number",
    )
    faxMessage_extension: str = Field(
        default="",
        wb_key="Fax Message Extension",
        doc_required="No",
        doc_value="",
        doc_notes="Designates Optional FAX extension.",
    )
    # RA NOTE: PIN Reset API Currently not available
    # Workspace Reset Voicemail PIN
    # reset_voicemail_pin: dm.OptYN = Field(
    #     default="",
    #     wb_key="Reset Voicemail PIN",
    #     doc_required="No",
    #     doc_notes=("`Y` Resets the voicemail PIN back to the default PIN set by the admin."),
    # )
    # Workspace Voicemail Passcode
    voicemail_passcode: str = Field(
        default="",
        wb_key="Voicemail Passcode",
        doc_required="No",
        doc_value="VM passcode",
        doc_notes="Set passcode to access voicemail group when calling.",
    )
    # Workspace Monitoring
    enableCallParkNotification: dm.OptYN = Field(
        default="",
        wb_key="Monitored Call Park Notification",
        doc_required="No",
        doc_notes="",
    )
    monitoring: list[WbxcMonitor] = Field(
        default=[],
        doc_required="Yes",
        doc_value="",
        doc_notes=""
    )

    @classmethod
    def from_wb(cls, row):
        """
        Processes a workbook containing Monitored Number and Monitored Location columns
        and returns a dictionary with combined details for each column ID.

        ```
        num_dict = {
                "1": {"column_id": "1", "number": "1111", "location_name": "NYC"},
                "2": {"column_id": "2", "number": "+155512342222", "location_name": ""},
                "3": {"column_id": "3", "number": "3333", "location_name": "NYC"},
                "4": {"column_id": "4", "number": "4444", "location_name": ""},
                "5": {"column_id": "5", "number": "", "location_name": ""}
            }
        ```
        """
        num_dict = defaultdict(dict)
        for key, value in row.items():  # key= Monitor 1 value= 12345
            if match := re.match(r"Monitored Number\s*(\d+)", key):
                column_id = match.group(1)  # column_id 1
                num_dict[column_id].update({"column_id": column_id, "number": value})

            if match := re.match(r"Monitored Location\s*(\d+)", key):
                column_id = match.group(1)  # column_id 1
                num_dict[column_id].update({"location_name": value})

        monitor_objs = [WbxcMonitor(**n) for n in num_dict.values()]

        obj = {}
        try:
            for field_name, field in cls.__fields__.items():
                converter = getattr(field.type_, "__from_wb__", dm.default_from_wb_converter)
                converter(field, obj, row)

            obj["monitoring"] = monitor_objs

            return cls.parse_obj(obj)

        except ZeusConversionError:
            raise
        except ValidationError as exc:
            raise ZeusConversionError(error=dm.extract_first_validation_error(exc))
        except Exception as exc:
            raise ZeusConversionError(error=str(exc))

    def to_wb(self) -> dict:
        row = super().to_wb()
        for monitor in self.monitoring:
            idx = monitor.column_id
            row[f"Monitored Number {idx}"] = monitor.number
            row[f"Monitored Location {idx}"] = monitor.location_name

        return row

    @validator("location", always=True)
    def validate_location_for_create(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("supportedDevices", always=True)
    def validate_supportedDevices_for_create(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("licenses", always=True)
    def validate_licenses(cls, v, values, field):
        """
        Ensure a valid license is provided for a CREATE action.
        If a license is provided for UPDATE, ensure it is valid.
        """
        action = values.get("action")
        license_name = str(v).strip()
        license_name = re.sub(r"(Webex Calling\s*-?\s*)", "", license_name, flags=re.I)
        if action == "CREATE" or (action == "UPDATE" and license_name):
            if license_name.lower() not in [lic.lower() for lic in WORKSPACE_CALLING_LICENSES]:
                raise ValueError(f"License must be one of {', '.join(WORKSPACE_CALLING_LICENSES)}")

        return license_name

    @root_validator(pre=True)
    def check_phone_or_extension(cls, values):
        """
        Ensure a phone number or extension are provided for CREATE
        unless the license is Hot desk only
        """
        action = values.get("action")
        phone_number = values.get("phoneNumber")
        extension = values.get("extension")
        license_name = values.get("licenses")

        if all([
            action == "CREATE",
            str(license_name).lower() != "hot desk only",
            not phone_number,
            not extension,
        ]):
            raise ValueError(
                "Either Phone Number or Extension is required for CREATE operation."
            )
        return values

    @validator("phoneNumber", "customNumber", always=True)
    def validate_phone_number(cls, v, values, field):
        """
        Verify the number is in E164 format for
        CREATE or UPDATE operations.
        """
        if v and values["action"] in ("CREATE", "UPDATE"):
            return validate_phone_numbers(v)

        return v

    @validator("extension", "faxMessage_extension", always=True)
    def validate_extension(cls, v, values, field):
        """
        Verify the extension is the correct length.
        CREATE or UPDATE operations.
        """
        if v and values["action"] in ("CREATE", "UPDATE"):
            return validate_extension(v)

        return v

    @validator("no_answer_rings", "sendUnansweredCalls_numberOfRings", always=True)
    def validate_no_answer_rings(cls, v, values, field):
        if v and values["action"] in ("CREATE", "UPDATE"):
            if not v.isdigit():
                raise ValueError("Must be a digit")
            rings = int(v)
            if not (2 <= rings <= 20):
                raise ValueError("Must be between 2 and 20")

        return v

    class Config:
        title = "Workspace Calling"
        schema_extra = {
            "data_type": "workspace_calling",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
