from zeus import registry as reg
from pydantic import Field, validator
from zeus.shared import data_type_models as dm
from zeus.wbxc.wbxc_models import WbxcMonitor
from zeus.wbxc.wbxc_models.shared import OUTGOING_PERMISSION, validate_phone_numbers, validate_extension


@reg.data_type("wbxc", "user_calling")
class WbxcUserCalling(dm.DataTypeBase):
    action: dm.OneOfStr(("CREATE", "UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action",
        doc_notes="Users cannot be deleted.",
    )
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Email address of the User",
        test_value="admin@cdw.com",
    )
    phoneNumber: str = Field(
        default="",
        wb_key="Phone Number",
        doc_required="No",
        doc_value="E164 number.",
        doc_notes="End user phone number.",
    )
    extension: str = Field(
        default="",
        wb_key="Extension",
        doc_required="No",
        doc_notes="End user extension.",
    )
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
        doc_notes="Flag to indicate if the virtual line can receive internal calls.",
    )
    collectCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Incoming Collect Calls",
        doc_required="No",
        doc_notes="Flag to indicate if the virtual line can receive collect calls.",
    )
    externalTransfer: dm.OneOfStr(
        ("ALLOW_ALL_EXTERNAL", "ALLOW_ONLY_TRANSFERRED_EXTERNAL", "BLOCK_ALL_EXTERNAL"), required=False) = Field(
        default="",
        wb_key="Incoming External Calls",
        doc_required="No",
        doc_notes="Indicate call transfer setting."
    )
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers from the virtual line can make these types of calls.",
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
        doc_notes="Callers at from the virtual line can make these types of calls.",
    )
    premium_services_ii_transfer: dm.OptYN = Field(
        default="",
        wb_key="Premium Services II Transfer",
        doc_required="No",
        doc_notes="If enabled, allows the person to transfer or forward these types of calls.",
    )
    mohEnabled: dm.OptYN = Field(
        default="",
        wb_key="MoH Enabled",
        doc_required="No",
        doc_notes="Music on hold is enabled or disabled for the virtual line.",
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
    callWaitingEnabled: dm.OptYN = Field(
        default="",
        wb_key="Call Waiting Enabled",
        doc_required="No",
        doc_notes="Call Waiting state.",
    )
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
    warningToneEnabled: dm.OptYN = Field(
        default="",
        wb_key="Call Bridge Tone Enabled",
        doc_required="No",
        doc_notes="Call Bridge Warning Tone feature is enabled or disabled.",
    )
    hoteling_enabled: dm.OptYN = Field(
        default="",
        wb_key="Hoteling Enabled",
        doc_required="No",
        doc_notes="Hoteling feature is enabled or disabled.",
    )
    ringDevicesForClickToDialCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Ring Devices for Click to Dial",
        doc_required="No",
        doc_notes="If enabled, indicates to ring devices for outbound Click to Dial calls.",
    )
    ringDevicesForGroupPageEnabled: dm.OptYN = Field(
        default="",
        wb_key="Ring Devices for Group Page",
        doc_required="No",
        doc_notes="If enabled, indicates to ring devices for inbound Group Pages.",
    )
    ringDevicesForCallParkEnabled: dm.OptYN = Field(
        default="",
        wb_key="Ring Devices for Call Park",
        doc_required="No",
        doc_notes="If enabled, indicates to ring devices for Call Park recalled.",
    )
    browserClientEnabled: dm.OptYN = Field(
        default="",
        wb_key="Browser Client Enabled",
        doc_required="No",
        doc_notes="If enabled, the browser Webex Calling application is enabled for use.",
    )
    desktopClientEnabled: dm.OptYN = Field(
        default="",
        wb_key="Desktop Client Enabled",
        doc_required="No",
        doc_notes="If enabled, the desktop Webex Calling application is enabled for use.",
    )
    tabletClientEnabled: dm.OptYN = Field(
        default="",
        wb_key="Tablet Client Enabled",
        doc_required="No",
        doc_notes="If enabled, the tablet Webex Calling application is enabled for use.",
    )
    mobileClientEnabled: dm.OptYN = Field(
        default="",
        wb_key="Mobile Client Enabled",
        doc_required="No",
        doc_notes="If enabled, the mobile Webex Calling application is enabled for use.",
    )
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
    compression: dm.OneOfStr(("ON", "OFF"), required=False) = Field(
        default="",
        wb_key="Compression",
        doc_required="No",
        doc_notes="Audio Compression is enabled or disabled.",
    )
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
    reset_voicemail_pin: dm.OptYN = Field(
        default="",
        wb_key="Reset Voicemail PIN",
        doc_required="No",
        doc_notes="`Y` Resets the voicemail PIN back to the default PIN set by the admin.",
    )
    voicemail_passcode: str = Field(
        default="",
        wb_key="Voicemail Passcode",
        doc_required="No",
        doc_value="VM passcode",
        doc_notes="Set passcode to access voicemail group when calling.",
    )
    recording_enabled: dm.OptYN = Field(
        default="",
        wb_key="Call Record Enabled",
        doc_required="No",
        doc_notes="Enable or disable Call Recording.",
    )
    record: dm.OneOfStr(("On Demand with User Initiated Start", "Always", "Always with Pause/Resume", "Never"),
                        required=False) = Field(
        default="",
        wb_key="Record Type",
        doc_required="No",
        doc_notes="Call recording scenario.",
    )
    recordVoicemailEnabled: dm.OptYN = Field(
        default="",
        wb_key="Record VM",
        doc_required="No",
        doc_notes="Enable or disable voicemail messages recording.",
    )
    start_stop_pstnCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Start Stop PSTN",
        doc_required="No",
        doc_notes="Enable or disable if announcement is played when call recording starts and ends for PSTN calls.",
    )
    start_stop_internalCallsEnabled: dm.OptYN = Field(
        default="",
        wb_key="Start Stop Internal",
        doc_required="No",
        doc_notes="Enable or disable if announcement is played when call recording starts and ends for internal calls.",
    )
    record_notification: dm.OneOfStr(("None", "Beep", "Play Announcement"), required=False) = Field(
        default="",
        wb_key="Record Notification",
        doc_required="No",
        doc_notes="Enable or disable recording notifications",
    )
    repeat_enabled: dm.OptYN = Field(
        default="",
        wb_key="Repeat Enabled",
        doc_required="No",
        doc_notes="Enable or disable call recording tone at the designated interval.",
    )
    repeat_interval: str = Field(
        default="",
        wb_key="Repeat Interval",
        doc_required="No",
        doc_value="Number",
        doc_notes="Interval at which warning tone 'beep' will be played. This interval is an integer from 10 to 1800 seconds"
    )
    enableCallParkNotification: dm.OptYN = Field(
        default="",
        wb_key="Monitored Call Park Notification",
        doc_required="No",
        doc_notes="",
    )
    monitoring: list[WbxcMonitor] = Field(
        default=[],
        doc_key="Monitored Number 1",
        doc_required="No",
        doc_value="Existing phone number or extension to monitor",
        doc_notes="Additional Monitor Number X and Monitor Location X columns can be added as needed",
    )
    calling_license_names: list = Field(
        default=[],
        description="Holds list of Webex Calling license names for display in detail view only."
    )

    @classmethod
    def model_doc(cls):
        """Add Monitored Location 1 doc field object to model docs."""
        doc = super().model_doc()
        location_doc = dm.DataTypeFieldDoc(
            doc_name="Monitored Location 1",
            doc_required="Conditional",
            doc_value="Webex location associated with the monitored number",
            doc_notes="Required if a corresponding Monitored Number is specified",
            field_type="str",
        )

        try:
            idx = [d.doc_name for d in doc.doc_fields].index("Monitored Number 1")
            doc.doc_fields.insert(idx+1, location_doc)
        except Exception:
            doc.doc_fields.append(location_doc)

        return doc

    def to_wb(self):
        row = super().to_wb()
        for item in self.monitoring:
            index = item.column_id
            row[f"Monitored Number {index}"] = item.number
            row[f"Monitored Location {index}"] = item.location_name

        return row

    @validator("phoneNumber", "customNumber", always=True)
    def validate_phone_number(cls, v, values, field):
        """
        Verify number is in E164 format for
        CREATE or UPDATE operations.
        """
        if v and values["action"] in ("CREATE", "UPDATE"):
            return validate_phone_numbers(v)

        return v

    @validator("extension", "faxMessage_extension", always=True)
    def validate_extension(cls, v, values, field):
        """
        Verify number is the correct length.
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
        title = "User Calling"
        schema_extra = {
            "data_type": "user_calling",
            "id_field": "name",
            "supports": {
                "browse": True,
                "detail": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
