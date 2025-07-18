from pydantic import Field, validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from zeus.wbxc.wbxc_models.shared import ANNOUNCEMENT_LANGUAGES, validate_phone_numbers, validate_extension


@reg.data_type("wbxc", "voicemail_groups")
class WbxcVoicemailGroup(dm.DataTypeBase):
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Name of the voicemail group",
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
        doc_notes="Location name of the Voicemail Group"
    )
    phoneNumber: str = Field(
        default="",
        wb_key="Phone Number",
        doc_required="No",
        doc_value="E164 number.",
        doc_notes="Voicemail group phone number.",
    )
    extension: str = Field(
        default="",
        wb_key="Extension",
        doc_required="Conditional",
        doc_value="Voicemail group extension",
        doc_notes="Required for `CREATE`",
    )
    firstName: str = Field(
        default="",
        wb_key="First Name",
        doc_required="No",
        doc_value="Caller ID First Name.",
    )
    lastName: str = Field(
        default="",
        wb_key="Last Name",
        doc_required="No",
        doc_value="Caller ID Last Name.",
    )
    passcode: str = Field(
        default="",
        wb_key="Passcode",
        doc_required="Conditional",
        doc_value="VM passcode",
        doc_notes="Set passcode to access voicemail group when calling. Required for `CREATE`",
    )
    enabled: dm.OptYN = Field(
        default="",
        wb_key="Enabled",
        doc_required="No",
        doc_notes="Voicemail is enabled or disabled.",
    )
    languageCode: str = Field(
        default="",
        wb_key="Language Code",
        doc_required="Conditional",
        doc_value="Announcement language. Ex: en_US",
        doc_notes="Required for `CREATE`",  # TODO: Add supported values to help doc
    )
    greeting: dm.OneOfStr(("DEFAULT", "CUSTOM"), required=False) = Field(
        default="",
        wb_key="Greeting",
        doc_required="No",
        doc_notes=(
            "DEFAULT indicates the default greeting will be played."
            "CUSTOM indicates a custom .wav file will be played."
        )
    )
    greetingDescription: str = Field(
        default="",
        wb_key="Greeting Description",
        doc_required="No",
        doc_value="",
        doc_notes="CUSTOM greeting for previously uploaded",
    )
    messageStorage_storageType: dm.OneOfStr(("INTERNAL", "EXTERNAL"), required=False) = Field(
        default="",
        wb_key="Storage Type",
        doc_required="Conditional",
        doc_value="Designates which type of voicemail message storage is used.",
        doc_notes="Required for `CREATE`",
    )
    messageStorage_externalEmail: str = Field(
        default="",
        wb_key="Storage Email",
        doc_required="No",
        doc_value="",
        doc_notes="External email address to which the new voicemail audio will be sent.",
    )
    notifications_enabled: dm.OptYN = Field(
        default="",
        wb_key="Notifications Enabled",
        doc_required="Conditional",
        doc_notes="Enable or disable notifications. Required for `CREATE`",
    )
    notifications_destination: str = Field(
        default="",
        wb_key="Notifications Destination",
        doc_required="Conditional",
        doc_value=(
            "Email address to which the notification will be sent."
            "For text messages, use an email to text message gateway like 2025551212@txt.att.net"
        ),
        doc_notes = "Required for `CREATE`",
    )
    faxMessage_enabled: dm.OptYN = Field(
        default="",
        wb_key="Fax Message Enabled",
        doc_required="Conditional",
        doc_notes="Required for `CREATE`",
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
    transferToNumber_enabled: dm.OptYN = Field(
        default="",
        wb_key="Transfer 0 Enabled",
        doc_required="Conditional",
        doc_notes="Required for `CREATE`.",
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
        doc_required="Conditional",
        doc_notes="Required for `CREATE`",
    )
    emailCopyOfMessage_emailId: str = Field(
        default="",
        wb_key="Email Copy Address",
        doc_required="No",
        doc_value="",
        doc_notes="Email address to which the new voicemail audio will be sent.",
    )

    @validator(
        "location",
        "extension",
        "passcode",
        "languageCode",
        "messageStorage_storageType",
        "notifications_enabled",
        "faxMessage_enabled",
        "transferToNumber_enabled",
        "emailCopyOfMessage_enabled",
        always=True
    )
    def validate_location_for_create(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("location", always=True)
    def validate_location_for_update(cls, v, values, field):
        return dm.validate_value_for_update(v, values, field)

    @validator("languageCode", always=True)
    def validate_languageCode(cls, v, values, field):
        """
        Verify languageCode is one of the supported values for
        CREATE or UPDATE operations.
        """
        if v and values["action"] in ("CREATE", "UPDATE"):
            lang = str(v).lower()
            for code, language in ANNOUNCEMENT_LANGUAGES:
                if lang == language.lower() or lang == code.lower():
                    return code

            raise ValueError(f"Invalid Language Code '{v}'.")

        return v

    @validator("phoneNumber", "faxMessage_phoneNumber", always=True)
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

    class Config:
        title = "Voicemail Groups"
        schema_extra = {
            "data_type": "voicemail_groups",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "detail": True,
                "upload": True,
                "help_doc": True,
            },
        }
