import re
from typing import List
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusConversionError
from pydantic import BaseModel, validator, Field, root_validator

disposition_types_that_use_type_params = [
    "RedialNumber",
    "DoNotDial",
]

disposition_types_that_do_not_use_type_params = [
    "FinalDisp",
    "AddActiveNumber",
    "FinalApplyToCampaigns",
    "AddAndFinalize",
    "AddAllNumbers",
]

tts_prompt_languages = [
    "en-GB",  # English (GB)
    "en-US",  # English (US)
    "fr-CA",  # France (CA)
    "de-DE",  # German (DE)
    "es-ES",  # Spanish (ES)
    # "pt-br", # Portuguese (BR) In VCC dropdown but API does not accept
]


@reg.data_type("five9", "dispositions")
class Five9Disposition(dm.DataTypeBase):
    """
    ### Disposition Types
    Zeus has been tested with the following disposition types:

    * RedialNumber
    * DoNotDial
    * FinalDisp
    * AddActiveNumber
    * FinalApplyToCampaigns
    * AddAndFinalize
    """

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Unique disposition name",
        test_value="Test Disposition 1",
    )
    type: str = Field(
        wb_key="Type",
        doc_required="Yes",
        doc_value="One of [Five9 Disposition Types](dispositions.md#disposition-types)",
        test_value="FinalDisp",
    )
    description: str = Field(default="", wb_key="Description", doc_required="No")
    attempts: str = Field(
        default="",
        wb_key="Attempts",
        doc_required="Conditional",
        doc_value="1 - 99",
        doc_notes="Required for `RedialNumber` creation<br/>Only applicable to `RedialNumber`",
    )
    allowChangeTimer: dm.OptYN = Field(
        default="",
        wb_key="Allow Change",
        doc_required="No",
        doc_notes="Only applicable to `RedialNumber` and `DoNotDial` types",
    )
    agentMustCompleteWorksheet: dm.OptYN = Field(default="", wb_key="Agent Must Complete")
    agentMustConfirm: dm.OptYN = Field(
        default="", wb_key="Agent Must Confirm", doc_required="No"
    )
    resetAttemptsCounter: dm.OptYN = Field(
        default="", wb_key="Reset Attempts", doc_required="No"
    )
    sendEmailNotification: dm.OptYN = Field(
        default="", wb_key="Send Email", doc_required="No"
    )
    sendIMNotification: dm.OptYN = Field(default="", wb_key="Send IM", doc_required="No")
    trackAsFirstCallResolution: dm.OptYN = Field(
        default="",
        wb_key="Track As First Call",
    )
    timer: str = Field(
        default="",
        wb_key="Timer",
        doc_required="Conditional",
        doc_value="Days:Hours:Minutes (ex: `0:0:15`)",
        doc_notes="Required for `RedialNumber` and `DoNotDial` types",
    )
    useTimer: dm.OptYN = Field(
        default="",
        wb_key="Use Timer",
        doc_required="Conditional",
        doc_notes="Required for `RedialNumber` and `DoNotDial` types",
    )

    @validator("timer", pre=True)
    def validate_timer(cls, v):
        """
        Validate timer format is days:hours:minutes (ex: 0:1:30).
        Try to account for Excel automatic time formatting that
        may change '12:30:00' into '12:30:00 AM'
        """
        if v:
            if m := re.search(r"(\d+:\d+:\d+)", str(v)):
                return m.group(1)
            else:
                raise ValueError("Timer must be in format days:hours:minutes (0:1:30)")
        return v

    @validator("useTimer", pre=True)
    def validate_use_timer_set_for_dial_types(cls, v, values):
        """
        Five9 API requires a `useTimer` value if `typeParameters` are specified
        Only disposition types 'RedialNumber' and 'DoNotDial' use `typeParameters`
        so require a value for these types.
        Ideally we would rely on the API response to report
        the error but the Five9 disposition API fails with Java stacktrace in
        response if useTimer field is required but missing
        """
        type_ = values.get("type")
        if type_ in disposition_types_that_use_type_params:
            if not v:
                raise ValueError(f"'Use Timer' must be set for {type_} dispositions")
        return str(v)

    class Config:
        title = "Dispositions"
        schema_extra = {
            "data_type": "dispositions",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("five9", "skills")
class Five9Skill(dm.DataTypeBase):

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Unique skill name",
        doc_notes="Can be up to 140 characters",
        test_value="Test Skill 1",
    )
    newSkillName: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Provide for `UPDATE` to change skill name",
    )
    description: str = Field(default="", wb_key="Description", doc_required="No")
    messageOfTheDay: str = Field(default="", wb_key="Message Of The Day", doc_required="No")
    routeVoiceMails: dm.ReqYN = Field(wb_key="Voicemail Required")

    class Config:
        title = "Skills"
        schema_extra = {
            "data_type": "skills",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("five9", "prompts")
class Five9Prompt(dm.DataTypeBase):
    """
    Both TTS and Wav file based prompts are supported.

    ### TTS Prompts
    In order to import TTS prompts, enter the prompt text in the `Prompt Text` column.

    ### Wav Prompts
    In order to import Wav prompts, enter the name of th prompt wav file in the `Wav File` column.

    A WaV file for each prompt must be uploaded to Zeus in a ZIP file. The ZIP file should include all the Wav files
    referenced in the worksheet.

    WaV file requirements:

    * File name must end with a `.wav` extension.
    * File name must match the value for the corresponding prompt in the `Wav File` worksheet column.
    * File format must be G711 mu-law, mono, 8000 Hz.

    ### Prompt Languages
    Prompts can be assigned multiple languages by including language/region code(s) separate by commas in the
    `Languages` column.

    The default language (`en-US`) is assigned to all prompt automatically. A value in the `Languages` column is only
    necessary to assign languages in addition to the default.

    Any language supported by Five9 can be assigned to a prompt, however, only a subset of the supported languages
    are supported by the TTS Builder. If the `Languages` column for a TTS prompt includes a language that is not
    supported by the TTS Builder, the TTS language will be set to the system default language.

    Based on testing, the following languages are supported by the TTS Builder.

     - `en-GB` English (GB)
     - `en-US` English (US)
     - `fr-CA` France (CA)
     - `de-DE` German (DE)
     - `es-ES` Spanish (ES)

    > NOTE: **Prompt Language Limitations**
    > Be aware of the following limitations when importing prompts with multiple languages:
    >
    > - An `UPDATE` operation can add languages but cannot remove languages from a prompt.
    > - Zeus does not currently support per-language prompt text.
    > - Zeus does not currently support per-language wav files.
    """

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Unique prompt name",
        test_value="Test Prompt",
    )
    description: str = Field(default="", wb_key="Description", doc_required="No")
    prompt_text: str = Field(
        default="",
        wb_key="Prompt Text",
        doc_required="Conditional",
        doc_value="Text that will be converted into speech by the Five9 TTS Builder",
        doc_notes="Required for `CREATE` and `UPDATE` of TTS prompts. Leave blank for Wav prompts.",
    )
    wav_file: str = Field(
        default="",
        wb_key="Wav File",
        doc_required="Conditional",
        doc_value="Name of the wav file for this prompt. see [Prompt Wav Files](prompts.md#prompt-wav-files)",
        doc_notes="Required for `CREATE` and `UPDATE` of Wav prompts. Leave blank for TTS prompts.",
    )
    languages: str = Field(
        default="",
        wb_key="Languages",
        doc_required="Optional",
        doc_value="One or more comma-separated [Prompt Language Codes](prompts.md#prompt-languages)",
        doc_notes="Example: `en-GB,fr-CA`",
    )
    type: str = Field(default="")

    @root_validator(pre=True)
    def validate_type(cls, values):
        """
        Prompt type is based on value in either wav_file or prompt_text fields.
        If both have a value, wav_file is used
        """
        prompt_type = ""
        wav_file = values.get("wav_file")
        prompt_text = values.get("prompt_text")

        if wav_file:
            prompt_type = "PreRecorded"
        elif prompt_text:
            prompt_type = "TTSGenerated"

        if not prompt_type:
            raise ValueError("Either 'Wav File' or 'Prompt Text' must be provided")

        values["type"] = prompt_type
        return values

    @property
    def languages_list(self):
        """Return comma/semicolon-separated languages string as list."""
        if self.languages:
            return re.split(r"\s*[,|;]\s*", self.languages)
        return []

    class Config:
        title = "Prompts"
        schema_extra = {
            "data_type": "prompts",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


FIVE9_ROLES = ("admin", "agent", "supervisor", "reporting")


class Five9Permission(BaseModel):
    type: str
    value: dm.ReqYN

    def to_payload(self):
        return {"type": self.type, "value": dm.yn_to_bool(self.value)}


@reg.data_type("five9", "users")
class Five9User(dm.DataTypeBase):
    """
    ### Skill Assignment
    [Skills](skills.md) can be assigned directly to a user or through a Five9 User Profile. If the User is assigned a
    User Profile, Skills cannot be modified on the User.

    ### User Roles and Permissions
    Permissions for the agent, admin, supervisor or reporting roles can be assigned to users by referencing
    permissions defined on the [Permissions](permission_profiles.md) worksheet.
    """

    userName: str = Field(wb_key="Username", doc_required="Yes", test_value="testuser1")
    EMail: str = Field(
        wb_key="Email Address", doc_required="Yes", test_value="testuser1@xyz.com"
    )
    extension: str = Field(
        wb_key="Extension",
        doc_required="Yes",
        doc_value="4-6 digit extension",
        doc_notes="Extension length depends on VCC configuration",
        test_value="777777",
    )
    canChangePassword: dm.ReqYN = Field(wb_key="Can Change Password", doc_required="Yes")
    mustChangePassword: dm.ReqYN = Field(wb_key="Must Change Password", doc_required="Yes")
    alwaysRecorded: dm.ReqYN = Field(wb_key="Record Agent Calls", doc_required="Yes")
    firstName: str = Field(
        default="",
        wb_key="First Name",
        doc_required="No",
    )
    lastName: str = Field(
        default="",
        wb_key="Last Name",
        doc_required="No",
    )
    password: str = Field(
        default="",
        wb_key="Password",
        doc_required="Conditional",
        doc_value="Must be at least 8 characters. Complexity requirements based on VCC password policy.",
        doc_notes="Required for `CREATE`, optional for `UPDATE`",
        test_value="password123",
    )
    agent_permissions_name: str = Field(
        default="",
        wb_key="Agent Role Permissions",
        doc_required="No",
        doc_value="Name of defined permissions for the agent role",
        doc_notes=(
            "If provided, must match a row with type `agent` on the [Permissions](permission_profiles.md) worksheet"
        ),
    )
    admin_permissions_name: str = Field(
        default="",
        wb_key="Admin Role Permissions",
        doc_required="No",
        doc_value="Name of defined permissions for the admin role",
        doc_notes=(
            "If provided, must match a row with type `admin` on the [Permissions](permission_profiles.md) worksheet"
        ),
    )
    supervisor_permissions_name: str = Field(
        default="",
        wb_key="Supervisor Role Permissions",
        doc_required="No",
        doc_value="Name of defined permissions for the supervisor role",
        doc_notes=(
            "If provided, must match a row with type `supervisor` "
            "on the [Permissions](permission_profiles.md) worksheet"
        ),
    )
    reporting_permissions_name: str = Field(
        default="",
        wb_key="Reporting Role Permissions",
        doc_required="No",
        doc_value="Name of defined permissions for the reporting role",
        doc_notes=(
            "If provided, must match a row with type "
            "`reporting` on the [Permissions](permission_profiles.md) worksheet"),
    )
    skills: str = Field(
        default="",
        wb_key="Skills",
        doc_required="No",
        doc_value="One or more `name=level` entries separated by semi-colon. Example: `Billing=1;Sales=2`. ",
        doc_notes="If cell is empty, no skill changes are made. To remove all skills set this value to `~`",
    )
    enableVoice: str = Field(
        wb_key="Voice",
        doc_required="Yes",
        doc_value="0 or 1",
        doc_notes="Max allowed for media type",
        test_value="1",
    )
    enableChat: str = Field(
        wb_key="Chat",
        doc_required="Yes",
        doc_value="0 - 127",
        doc_notes="Max allowed for media type",
        test_value="0",
    )
    enableEmail: str = Field(
        wb_key="Email",
        doc_required="Yes",
        doc_value="0 - 127",
        doc_notes="Max allowed for media type",
        test_value="4",
    )
    enableSocial: str = Field(
        wb_key="Social",
        doc_required="Yes",
        doc_value="0 - 127",
        doc_notes="Max allowed for media type",
        test_value="6",
    )
    userProfileName: str = Field(
        default="",
        wb_key="User Profile",
        doc_required="No",
        doc_value="Existing Five9 user profile name",
    )
    federationId: str = Field(
        default="",
        wb_key="Federation ID",
        doc_required="No",
        doc_value="Username or email address",
        doc_notes="For use with single sign-on",
    )
    agent_permissions: List[Five9Permission] = Field(default=[])
    admin_permissions: List[Five9Permission] = Field(default=[])
    supervisor_permissions: List[Five9Permission] = Field(default=[])
    reporting_permissions: List[Five9Permission] = Field(default=[])
    phoneNumber: str = Field(default="")

    @validator("password")
    def validate_password(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @classmethod
    def from_wb(cls, row: dict):
        """
        Populate the permissions fields from permission profiles
        built by the Five9PermissionProfileUpload task and saved
        to the `permissions_by_role` key on each user row. Then
        Call super().from_wb
        """
        perms_by_role = row.get("permissions_by_role", [])
        for role in FIVE9_ROLES:
            wb_column_key = f"{role.title()} Role Permissions"
            model_field = f"{role.lower()}_permissions"
            profile_name = row.get(wb_column_key)
            row[model_field] = []

            if profile_name:
                try:
                    row[model_field] = deep_get(target=perms_by_role, path=[role.lower(), profile_name.lower()])
                except ValueError:
                    raise ZeusConversionError(f"Permissions name: '{profile_name}' for role: '{role}' not found")

        return super().from_wb(row)

    class Config:
        title = "Users"
        schema_extra = {
            "data_type": "users",
            "id_field": "userName",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("five9", "permission_profiles")
class Five9PermissionProfile(dm.DataTypeBase):
    """
    One or more sets of [Five9 User](users.md) permissions can be defined on a **Permissions** worksheet and
    referenced on the **Users** worksheet.

    The first column of the worksheet must be the `Name` column. This defines the value used to refer to the profile
    on the **Users** worksheet.
    The second column of the worksheet must be the `Role` column. This defines the role to which the permissions apply.

    Subsequent columns should be incrementing permission columns (ex: `Permission 1`, `Permission 2`, etc.).
    The value for each permission column must be in the form PermissionName=Y/N (ex: `ReceiveTransfer=Y`,
    `ProcessVoiceMail=N`).

    A [Five9 Org Export](export.md) will include a **Permissions** worksheet with all the unique combinations
    of permissions assigned to existing users.

    ### Role Removal
    In order to remove the Admin or Supervisor role from a user, add a row on the Permissions worksheet with no
    permissions defined.
    Assigning this to a user on the Users worksheet and performing an `UPDATE` will remove the role.

    > NOTE: **Permission Caveats**
    > Be aware of the following permission-related caveats:
    >
    > - Attempting to set the `AccessBillingApplication` admin permission will result in an error unless the account
    in use has this permission enabled.
    > - It is not necessary to define every possible permission for a role, however, do not assume undefined
    permissions will be disabled.

    ### Provisioning Worksheet
    The worksheet must be named **Permissions** and should include columns as detailed in the following table.
    Any additional columns in the worksheet will be ignored.

    | Column Name     | Required | Supported Values                                                                    | Notes |
    |---------------- |----------|-------------------------------------------------------------------------------------|-------|
    | Name            | Yes      | Arbitrary name used to identify permissions on the [Users](users.md) worksheet      |       |
    | Role            | Yes      | One of `admin`,`agent`,`supervisor`,`reporting`                                     |       |
    | Permission 1    | Yes      | Permission name and value (ex: `ReceiveTransfer=Y`) or leave blank for role removal |       |
    | Permission 2..X | No       | Additional incrementing Permission columns as needed                                |       |

    ### Permissions Worksheet Example

    | Name              | Role       | Permission 1               | Permission 2       | Permission 3         | Permission 4           |
    |-------------------|------------|----------------------------|--------------------|----------------------|------------------------|
    | Agent Perms       | agent      | ReceiveTransfer=Y          | ProcessVoiceMail=N | DeleteVoiceMail=Y    | TransferVoiceMail=Y    |
    | Supervisor Perms  | supervisor | Agents=Y                   | AllSkills=Y        | BargeInMonitor=Y     | BillingInfo=Y          |
    | Admin Perms       | admin      | AccessBillingApplication=N | AccessConfigANI=Y  | CanUseAdminSoapApi=Y | EditCallAttachedData=Y |
    | Remove Admin Role | admin      |                            |                    |                      |                        |

    ### User Worksheet Referencing Permissions Example

    | Action | Email Address      | Username           | Extension | Agent Role Permissions | Supervisor Role Permissions | Admin Role Permissions |
    |--------|--------------------|--------------------|-----------|------------------------|-----------------------------|------------------------|
    | CREATE | agent@xyz.com      | agent@xyz.com      | 8888      | Agent Perms            |                             |                        |
    | CREATE | supervisor@xyz.com | supervisor@xyz.com | 8889      | Agent Perms            | Supervisor Perms            |                        |
    | CREATE | newadmin@xyz.com   | newadmin@xyz.com   | 8890      |                        |                             | Admin Perms            |
    | UPDATE | oldadmin@xyz.com   | oldadmin@xyz.com   | 8891      |                        |                             | Remove Admin Role      |

    """

    action: dm.OneOfStr(("IGNORE",), required=True) = Field(
        wb_key="Action", default="IGNORE", doc_ignore=True
    )
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Arbitrary name used to identify permissions on the [Users](users.md) worksheet"
    )
    role: dm.OneOfStr(("admin", "agent", "supervisor", "reporting",), required=True) = Field(wb_key="Role")
    permissions: List[Five9Permission] = Field(
        default=[],
        doc_required="Yes",
        doc_value="Permission name with setting (`Y` to enable, `N` to disable)",
        doc_notes="See the [example](permissions_profile.md#permissions-worksheet-example) above"
    )

    @classmethod
    def from_wb(cls, obj):
        """
        Build a Five9PermissionProfile object from the provided row
        dictionary.

        The row dictionary has a mandatory 'Name' key. Any other keys
        are permission names with Y/N value.

        A permission with an empty value is dropped.

        Non-boolean values trigger a conversion exception to prevent invalid values
        slipping through to import operations as a non-boolean value is treated as TRUE
        by the Five9 API.
        """
        perm_list = []

        for key, value in obj.items():
            if not value or not re.match(r"permission\s*\d+", key, re.I):
                continue

            split_perm = re.split(r"\s*=\s*", value)
            if not len(split_perm) == 2:
                raise ZeusConversionError(
                    error=f"{key}: '{value}' is invalid. Must be in format 'PermissionName=Value' with value 'Y' or 'N'"
                )

            perm_type, perm_value = [val.strip() for val in split_perm]
            perm_list.append(Five9Permission(type=perm_type, value=perm_value))

        return cls(name=obj.get("Name"), role=obj.get("Role"), permissions=perm_list)

    def to_wb(self):
        row = {"Name": self.name, "Role": self.role}
        for idx, perm in enumerate(self.permissions, 1):
            key = f"Permission {idx}"
            name = perm.type
            value = dm.to_wb_str(perm.value)
            row[key] = f"{name}={value}"

        return row

    class Config:
        title = "Permissions"
        schema_extra = {
            "data_type": "permission_profiles",
            "id_field": "name",
            "supports": {
                "browse": False,
                "export": False,
                "bulk": False,
                "upload": True,
                "help_doc": True,
            },
            "doc_template": "five9_perms.jinja2",
        }


media_types_map = {
    "VOICE": "enableVoice",
    "CHAT": "enableChat",
    "SOCIAL": "enableSocial",
    "EMAIL": "enableEmail",
    "VIDEO": "enableVideo",
    "CASE": "enableCase",
}
