import re
from copy import deepcopy
from typing import List
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from pydantic import BaseModel, Field, validator

SKILL_TYPES = ("TEXT", "PROFICIENCY", "BOOLEAN", "ENUM")


@reg.data_type("wxcc", "skills")
class WxccSkill(dm.DataTypeBase):
    name: str = Field(wb_key="Name", doc_required="Yes", test_value="Test Skill")
    description: str = Field(default="", wb_key="Description", doc_required="No")
    active: dm.ReqYN = Field(wb_key="Active")
    skillType: dm.OneOfStr(values=SKILL_TYPES, required=True) = Field(wb_key="Type")
    serviceLevelThreshold: str = Field(
        wb_key="Service Level Threshold",
        doc_required="Yes",
        doc_value="Time interval in seconds",
        test_value="30"
    )
    enum_names: str = Field(
        default="",
        wb_key="Enum Names",
        doc_required="Conditional",
        doc_value="Comma/semicolon separated list of Enum names",
        doc_note="Required for `CREATE` and `UPDATE` if Type is `ENUM`. Provided values replace any existing values.",
    )

    @property
    def enum_names_list(self):
        if not self.enum_names:
            return []
        return [name.strip() for name in re.split(r"\s*[,|;]\s*", self.enum_names)]

    @validator("enum_names", always=True)
    def validate_enum_names(cls, v, values, field):
        if values.get("skillType") == "ENUM":
            dm.validate_value_for_create(v, values, field)
            dm.validate_value_for_update(v, values, field)
        return v

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
            "sort_order": 0
        }


class WxccActiveSkill(BaseModel):
    idx: int = Field(description="Skill index")
    name: str = Field(
        default="",
        wb_key="Skill Name {IDX}",
        doc_required="Conditional",
        doc_value="Skill name",
        doc_notes=(
            "At least one skill name is required for `CREATE`."
            " Add `Skill Name 2`, `Skill Name 3`, etc columns as needed."
            " See [Skills](skill_profiles.md#skills)"
        ),
    )
    value: str = Field(
        default="",
        wb_key="Skill Value {IDX}",
        doc_required="Conditional",
        doc_value="Skill value",
        doc_notes=(
            "At least one skill value is required for `CREATE`."
            " Add `Skill Value 2`, `Skill Value 3`, etc columns as needed."
            " See [Skills](skill_profiles.md#skills)"
        ),
    )
    type: str = ""

    def to_wb(self):
        wb_row = {}
        idx = self.idx
        for wb_key, field in self.indexed_wb_keys(idx).items():
            key = wb_key.format(IDX=idx)
            value = getattr(self, field.name)
            wb_row[key] = dm.to_wb_str(value)

        return wb_row

    @classmethod
    def indexed_wb_keys(cls, idx: int) -> dict[str, Field]:
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


@reg.data_type("wxcc", "skill_profiles")
class WxccSkillProfile(dm.DataTypeBase):
    """
    ### Skills
    NOTE: Zeus does not currently support assigning Enum skills to skill profiles.

    #### Skill Columns
    Multiple skills can be added/removed from a skill profile by adding `Skill Name` and `Skill Value`
    column pairs. Add a column pair for each skill with incrementing headers.
    Ex: `Skill Name 1`, `Skill Value 1`; `Skill Name 2`, `Skill Value 2`.

    _Skill Values_

    The values for skill value cells must be of type int, boolean, or string.
    Examples:

    - Proficiency skill: `5`
    - Boolean skill: `True`
    - Text skill: `SomeText`

    #### Skill Action
    The `Skill Action` column indicates the action taken for the specified skills for an `UPDATE`.
    Options are `ADD`, `REPLACE`, `REMOVE`.
    """
    name: str = Field(wb_key="Name", doc_required="Yes", test_value="Test Skill Profile")
    description: str = Field(default="", wb_key="Description", doc_required="No")
    skill_action: dm.OneOfStr(("ADD", "REMOVE", "REPLACE"), required=False) = Field(
        default="",
        wb_key="Skill Action",
        doc_required="Conditional",
        doc_notes="Required for `UPDATE`. Action to take on any Skill columns",
    )
    skills: list[WxccActiveSkill] = Field(default=[])

    @classmethod
    def model_doc(cls):
        """Add Skill Name/Value 1 doc field object to model docs."""
        doc = super().model_doc()

        skill_doc_fields = WxccActiveSkill.model_doc_fields()
        doc.doc_fields.extend(skill_doc_fields)
        return doc

    def to_wb(self) -> dict:
        row = super().to_wb()
        for skill in sorted(self.skills, key=lambda x: x.idx):
            row[f"Skill Name {skill.idx}"] = skill.name
            row[f"Skill Value {skill.idx}"] = skill.value

        return row

    class Config:
        title = "Skill Profiles"
        schema_extra = {
            "data_type": "skill_profiles",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
            "sort_order": 1
        }


@reg.data_type("wxcc", "teams")
class WxccTeam(dm.DataTypeBase):
    name: str = Field(wb_key="Name", doc_required="Yes", test_value="Test Team")
    active: dm.ReqYN = Field(wb_key="Active", required="Yes")
    teamStatus: dm.OneOfStr(("IN_SERVICE", "OUT_OF_SERVICE", "NOT_AVAILABLE")) = Field(
        wb_key="Team Status",
        doc_values="One of `IN_SERVICE`, `NOT_AVAILABLE`"
    )
    teamType: dm.OneOfStr(("AGENT", "CAPACITY")) = Field(wb_key="Team Type")
    site_name: str = Field(
        wb_key="Site Name",
        required="Yes",
        doc_required="Yes",
        doc_value="Existing Wxcc site name",
        test_value="Test Site",
    )
    dialedNumber: str = Field(
        default="",
        wb_key="DN",
        doc_required="Conditional",
        doc_value="Valid extension or E.164 number",
        doc_notes="Required for `CAPACITY` type",
    )
    capacity: str = Field(
        default="",
        wb_key="Capacity",
        doc_required="Conditional",
        doc_value="Integer > 0",
        doc_notes="Required for `CAPACITY` type",
    )
    desktop_layout_name: str = Field(
        default="",
        wb_key="Desktop Layout Name",
        doc_required="No",
        doc_value="Name of existing Wxcc Desktop Layout",
        doc_notes="Only applicable to `AGENT` type",
    )
    multimedia_profile_name: str = Field(
        default="",
        wb_key="Multimedia Profile Name",
        doc_required="No",
        doc_value="Name of existing Wxcc Multimedia Profile",
        doc_notes="Only applicable to `AGENT` type",
    )
    skill_profile_name: str = Field(
        default="",
        wb_key="Skill Profile Name",
        doc_required="No",
        doc_value="Name of existing Wxcc Skill Profile",
        doc_notes="Only applicable to `AGENT` type",
    )
    agents: str = Field(
        default="",
        wb_key="Agents",
        doc_required="No",
        doc_value="One or more comma-separated email addresses",
    )

    @property
    def agent_list(self):
        if not self.agents:
            return []
        return [agent.strip() for agent in re.split(r"\s*[,|;]\s*", self.agents)]

    class Config:
        title = "Teams"
        schema_extra = {
            "data_type": "teams",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
            "sort_order": 2
        }


ENTRY_POINT_TYPES = ("INBOUND", "OUTBOUND")

CHANNEL_TYPES = (
    "CHAT",
    "EMAIL",
    "FAX",
    "OTHERS",
    "SOCIAL_CHANNEL",
    "TELEPHONY",
    "VIDEO",
)
SOCIAL_CHANNEL_TYPES = ("MESSAGEBIRD", "MESSENGER", "WHATSAPP")


@reg.data_type("wxcc", "entry_points")
class WxccEntryPoint(dm.DataTypeBase):
    """
    NOTE:
    Import of `SOCIAL_CHANNEL` entry points is currently not supported.
    """
    name: str = Field(wb_key="Name", doc_required="Yes", test_value="Test Entry Point")
    active: dm.ReqYN = Field(wb_key="Active")
    channelType: dm.OneOfStr(CHANNEL_TYPES) = Field(
        wb_key="Channel Type",
        doc_notes="Must be one of 'CHAT','EMAIL','FAX','OTHERS','SOCIAL_CHANNEL','TELEPHONY','VIDEO'",
    )
    entryPointType: dm.OneOfStr(ENTRY_POINT_TYPES) = Field(
        wb_key="Entry Point Type",
        doc_notes="Must be one of 'INBOUND','OUTBOUND'",
    )
    timezone: str = Field(
        default="",
        wb_key="Timezone",
        doc_required="No",
        doc_value="Ex: America/New_York",
    )
    description: str = Field(
        default="",
        wb_key="Description",
        doc_required="No"
    )
    serviceLevelThreshold: str = Field(
        default="",
        wb_key="SLA",
        doc_required="Conditional",
        doc_value="Integer > 0",
        doc_notes="Not applicable to `SOCIAL_CHANNEL` type. Required for other types",
    )
    overflowNumber: str = Field(
        default="",
        wb_key="Overflow Number",
        doc_required="No",
        doc_value="Valid dial-able number",
        doc_notes="Only applicable to `TELEPHONY` channel type",
    )
    subscriptionId: str = Field(
        default="",
        wb_key="Subscription Id",
        doc_required="No",
        doc_notes="Not currently functional due to API issue",
    )
    maximumActiveContacts: str = Field(
        default="",
        wb_key="Maximum Active Contacts",
        doc_required="Conditional",
        doc_value="Integer > 0",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    controlFlowScriptUrl: str = Field(
        default="",
        wb_key="Control Flow Script URL",
        doc_required="No",
        doc_notes="Application only to `TELEPHONY` channel type",
    )
    moh_name: str = Field(
        default="",
        wb_key="Music On Hold",
        doc_required="No",
        doc_value="Case-sensitive audio file name.  Ex: SampleAudioSource.wav",
        doc_notes="MOH Name for `INBOUND` and `OUTBOUND` entry point type",
    )
    queue_name: str = Field(
        default="",
        wb_key="Outdial Queue",
        doc_required="No",
        doc_notes="Queue Name for `OUTBOUND` entry point type",
    )

    class Config:
        title = "Entry Points"
        schema_extra = {
            "data_type": "entry_points",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
            "sort_order": 4
        }


QUEUE_TYPES = ("INBOUND", "OUTBOUND")
QUEUE_SKILL_ROUTING_TYPES = ("BEST_AVAILABLE_AGENT", "LONGEST_AVAILABLE_AGENT")
QUEUE_ROUTING_TYPES = ("SKILLS_BASED", "LONGEST_AVAILABLE_AGENT")


class WxccCallDistributionGroup(BaseModel):
    agentGroups: List[str]
    duration: int = 0
    order: int = 1


@reg.data_type("wxcc", "queues")
class WxccQueue(dm.DataTypeBase):
    """
    ### Call Distribution Groups
    An Inbound Queue must contain at least one Call Distribution Group with at least one [Team](teams.md) assigned.
    An Inbound Queue may contain multiple Call Distribution Groups and each group may contain
    multiple [Teams](teams.md).
    When multiple Call Distribution Groups are defined, unanswered calls are routed to subsequent groups based
    on the associated duration value.

    This configuration for the first Call Distribution Group is reflected in the provisioning workbook through
    the following columns:

    * **Call Distribution Group 1 Teams**: One or more comma-separate [Team](teams.md) names.
    * **Call Distribution Group 1 Duration**: Time in seconds that calls unanswered by the previous group should
    route to this group. Value is always `0` for Group 1.

    To build queues with multiple groups, insert additional `Call Distribution Group X Teams`
    and `Call Distribution Group X Duration` columns.
    """

    name: str = Field(wb_key="Name", doc_required="Yes", test_value="Test Queue")
    description: str = Field(default="", wb_key="Description", doc_required="No")
    active: dm.ReqYN = Field(wb_key="Active")
    channelType: dm.OneOfStr(CHANNEL_TYPES) = Field(wb_key="Channel Type")
    queueType: dm.OneOfStr(QUEUE_TYPES) = Field(wb_key="Queue Type")
    routingType: dm.OneOfStr(QUEUE_ROUTING_TYPES, required=False) = Field(
        default="",
        wb_key="Routing Type",
        doc_required="Conditional",
        doc_notes="Required for `INBOUND` queue type"
    )
    skillBasedRoutingType: dm.OneOfStr(QUEUE_SKILL_ROUTING_TYPES, required=False) = Field(
        default="",
        wb_key="Skill Based Routing Type",
        doc_required="Conditional",
        doc_notes="Required for `SKILLS_BASED` routing type"
    )
    callDistributionGroups: List[WxccCallDistributionGroup] = Field(
        doc_required="Yes",
        doc_key="Call Distribution Group 1 Teams",
        doc_value="One or more comma-separated team names",
        doc_notes="See [Call Distribution Groups](queues.md#call-distribution-groups)",
        test_value=lambda: [{"agentGroups": ["Test Group"], "order": 1, "duration": 0}]
    )
    timezone: str = Field(
        default="",
        wb_key="Timezone",
        doc_required="No",
        doc_value="Ex: America/New_York",
    )
    maxTimeInQueue: str = Field(
        wb_key="Maximum Time in Queue",
        doc_required="Yes",
        doc_value="Integer > 0",
        test_value="30",
    )
    checkAgentAvailability: dm.OptYN = Field(
        default="",
        wb_key="Check Agent Availability",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` queue type"
    )
    maxActiveContacts: str = Field(
        default="",
        wb_key="Maximum Active Contacts",
        doc_required="Conditional",
        doc_value="Integer > 0",
        doc_notes="Required for `TELEPHONY` queue type",
    )
    outdialCampaignEnabled: dm.OptYN = Field(default="", wb_key="Outdial Campaign Enabled")
    overflowNumber: str = Field(
        default="",
        wb_key="Overflow Number",
        doc_required="No",
        doc_value="A valid dial-able number",
    )
    serviceLevelThreshold: str = Field(
        default="",
        wb_key="SLA",
        doc_required="Conditional",
        doc_value="Integer > 0",
        doc_notes="Required for `TELEPHONY` queue type",
    )
    subscriptionId: str = Field(
        default="",
        wb_key="Subscription Id",
        doc_required="No",
        doc_notes="Not currently functional due to API issue",
    )
    parkingPermitted: dm.OptYN = Field(
        default="",
        wb_key="Parking Permitted",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    monitoringPermitted: dm.OptYN = Field(
        default="",
        wb_key="Monitoring Permitted",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    recordingPermitted: dm.OptYN = Field(
        default="",
        wb_key="Recording Permitted",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    pauseRecordingPermitted: dm.OptYN = Field(
        default="",
        wb_key="Pause Recording Permitted",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    recordingAllCallsPermitted: dm.OptYN = Field(
        default="",
        wb_key="Recording All Calls Permitted",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    recordingPauseDuration: str = Field(
        default="",
        wb_key="Recording Pause Duration",
        doc_required="Conditional",
        doc_value="Integer > 0",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    controlFlowScriptUrl: str = Field(
        default="",
        wb_key="Control Flow Script URL",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    ivrRequeueUrl: str = Field(
        default="",
        wb_key="IVR Requeue URL",
        doc_required="Conditional",
        doc_notes="Required for `TELEPHONY` channel type",
    )
    music_in_queue_file: str = Field(
        default="",
        wb_key="Default Music in Queue Media File Name",
        doc_required="Conditional",
        doc_value="Name of existing media file",
        doc_notes="Required for `TELEPHONY` channel type",
    )

    @classmethod
    def model_doc(cls):
        """Add Call Distribution Group 1 Duration doc field object to model docs."""
        doc = super().model_doc()
        duration_doc = dm.DataTypeFieldDoc(
            doc_name="Call Distribution Group 1 Duration",
            doc_required="No",
            doc_value="Time in seconds that calls unanswered by the previous group should route to this group",
            doc_notes="Value is always 0 for the first group",
            field_type="str",
        )

        try:
            idx = [d.doc_name for d in doc.doc_fields].index("Call Distribution Group 1 Teams")
            doc.doc_fields.insert(idx+1, duration_doc)
        except Exception:
            doc.doc_fields.append(duration_doc)

        return doc

    def to_wb(self) -> dict:
        row = super().to_wb()
        for group in self.callDistributionGroups:
            idx = group.order
            teams = ";".join(group.agentGroups)
            row[f"Call Distribution Group {idx} Teams"] = teams
            row[f"Call Distribution Group {idx} Duration"] = group.duration

        return row

    class Config:
        title = "Queues"
        schema_extra = {
            "data_type": "queues",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
            "sort_order": 3
        }
