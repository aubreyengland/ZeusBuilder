import re
from typing import TypedDict

from pydantic import BaseModel, validator, Field

from .shared import PREFERRED_LANGUAGES
from zeus import registry as reg
from zeus.shared import data_type_models as dm

HUNT_POLICY_TYPES = ("REGULAR", "CIRCULAR", "UNIFORM", "SIMULTANEOUS", "WEIGHTED")


class WbxcHuntGroupAgent(BaseModel):
    idx: int
    firstName: str = ""
    lastName: str = ""
    phoneNumber: str = ""
    extension: str = ""
    weight: int = 0
    type: str = ""
    number: str = ""

    @validator("number", always=True, pre=True)
    def validate_number(cls, v, values, field):
        if v:
            return v

        phone_number = values.get("phoneNumber")
        extension = values.get("extension")

        return phone_number or extension


class WbxcHuntGroupAltNumber(BaseModel):
    idx: int
    phoneNumber: str
    ringPattern: str = "NORMAL"


@reg.data_type("wbxc", "hunt_groups")
class WbxcHuntGroup(dm.DataTypeBase):
    """
    ### Agents
    Hunt group agents are identified in the workbook the phone number or extension. The number must be unique.
    Agents may be users, virtual lines or workspaces.

    #### Agent Columns
    Multiple agents can be added/removed by adding `Agent #` columns. Add a column for each
    agent with incrementing headers. Ex: `Agent 1`, `Agent 2`, `Agent 3`.

    #### Agent Action
    The `Agent Action` column indicates the action taken for an `UPDATE`.
    Options are `ADD`, `REPLACE`, `REMOVE`.

    #### Agent Weights
    For weighted hunt groups, an optional weight value can be assigned to each agent using the `number=weight`
    format.  For example `1000=50,+12025551234=50`.

    > Agent Weight Notes:
    >
    > * Weights only apply hunt groups using the Weighted algorithm.
    > * Total agent weights must equal 100.
    > * Due to API issues, updating weights on existing agents does not work.
    > * To update an agents weight, first remove the agent from the group and re-add them with the new weight.

    ### Alternate Numbers
    Are identified in the workbook phone number.

    #### Alternate Number Columns
    Multiple alternate numbers can be added/removed by adding `Alternate Numbers #` columns.
    Add a column for each number with incrementing headers.

    Ex: `Alternate Number 1`, `Alternate Number 2`.

    #### Alternate Number Action
    The `Alternate Number Action` column indicates the action taken for an `UPDATE`.
    Options are `ADD`, `REPLACE`, `REMOVE`.

    #### Ring Patterns
    Custom ring patterns can be specified for an alternate number in the format: `[PHONE NUMBER]=[RING PATTERN]`.
    Options are: `NORMAL`, `LONG_LONG`, `SHORT_SHORT_LONG`, `SHORT_LONG_SHORT`.

    Ex: `+12025551234=LONG_LONG`.
    """

    name: str = Field(wb_key="Name", doc_required="Yes", doc_notes="Name must be unique within the location.")
    location_name: str = Field(wb_key="Location", doc_required="Yes")
    extension: str = Field(
        default="",
        wb_key="Extension",
        doc_required="Conditional",
        doc_notes="Either `Extension` or `Phone Number` must be provided",
    )
    phoneNumber: str = Field(
        default="",
        wb_key="Phone Number",
        doc_required="Conditional",
        doc_notes="Either `Extension` or `Phone Number` must be provided",
    )
    number: str = Field(
        default="",
        description="Unique ID field populate by a validator with either phoneNumber or extension."
    )
    hunt_policy: str = Field(
        default="",
        wb_key="Hunt Policy",
        doc_required="Conditional",
        doc_value="One of `REGULAR`, `CIRCULAR`, `UNIFORM`, `SIMULTANEOUS`, `WEIGHTED`",
        doc_notes="Required for `CREATE` and `UPDATE`",
    )
    languageCode: str = Field(
        default="",
        wb_key="Language",
        doc_required="No",
        doc_value="Supported language code. Ex: `en_US`, `fr_FR`, `it_IT`",
    )
    timeZone: str = Field(
        default="",
        wb_key="Timezone",
        doc_required="No",
        doc_value="Ex: America/New_York",
    )
    firstName: str = Field(
        default="",
        wb_key="First Name",
        doc_required="No",
        doc_notes="Displayed when hunt group calls are forwarded",
    )
    lastName: str = Field(
        default="",
        wb_key="Last Name",
        doc_required="No",
        doc_notes="Displayed when hunt group calls are forwarded",
    )
    advance_when_busy: dm.OptYN = Field(
        default="",
        wb_key="Advance When Busy",
        doc_required="No",
        doc_notes="Set to `Y` to advanced to next agent if selected agent line is busy"
    )
    hunt_busy_enabled: dm.OptYN = Field(
        default="",
        wb_key="Hunt Busy Enabled",
        doc_required="No",
        doc_notes="Set to `Y` to busy-out the hunt group"
    )
    hunt_busy_allow_users: dm.OptYN = Field(
        default="",
        wb_key="Allow Users To Enable Hunt Busy",
        doc_required="No",
    )
    advance_to_next_agent: dm.OptYN = Field(
        default="",
        wb_key="Advance To Next Agent",
        doc_required="No",
    )
    advance_after_rings: str = Field(
        default="",
        wb_key="Advance After Set Number Of Rings",
        doc_required="No",
        doc_value="1 - 20",
    )
    forward_na_enabled: dm.OptYN = Field(
        default="",
        wb_key="Forward No Answer Enabled",
        doc_required="No",
    )
    forward_na_destination: str = Field(
        default="",
        wb_key="Forward No Answer Destination",
        doc_required="No",
        doc_value="Extension or Phone number",
    )
    forward_na_vm: dm.OptYN = Field(
        default="",
        wb_key="Forward No Answer To VM",
        doc_required="No",
        doc_notes="If `Y`, will forward to configured destination's voicemail",
    )
    forward_na_rings: str = Field(
        default="",
        wb_key="Forward No Answer Number Of Rings",
        doc_required="No",
        doc_value="1 - 20",
    )
    forward_busy_enabled: dm.OptYN = Field(
        default="",
        wb_key="Forward Busy Enabled",
        doc_required="No",
    )
    forward_busy_destination: str = Field(
        default="",
        wb_key="Forward Busy Destination",
        doc_required="No",
        doc_value="Extension or Phone number",
    )
    forward_busy_vm: dm.OptYN = Field(
        default="",
        wb_key="Forward Busy To VM",
        doc_required="No",
        doc_notes="If `Y`, will forward to configured destination's voicemail",
    )
    forward_ur_enabled: dm.OptYN = Field(
        default="",
        wb_key="Forward Unreachable Enabled",
        doc_required="No",
    )
    forward_ur_destination: str = Field(
        default="",
        wb_key="Forward Unreachable Destination",
        doc_required="No",
        doc_value="Extension or Phone number",
    )
    forward_ur_vm: dm.OptYN = Field(
        default="",
        wb_key="Forward Unreachable VM",
        doc_required="No",
        doc_notes="If `Y`, will forward to configured destination's voicemail",
    )
    allow_number_as_clid: dm.OptYN = Field(
        default="",
        wb_key="Allow Number As Caller ID",
        doc_required="No",
    )
    distinctiveRing: dm.OptYN = Field(
        default="",
        wb_key="Distinctive Ring",
        doc_required="No",
    )
    agent_action: dm.OneOfStr(("ADD", "REMOVE", "REPLACE"), required=False) = Field(
        default="",
        wb_key="Agent Action",
        doc_notes="Action to take on any Agent columns",
    )
    agents: list[WbxcHuntGroupAgent] = Field(
        default=[],
        doc_key="Agent 1",
        doc_required="No",
        doc_value="Extension or phone number of user, common area or virtual line with optional weight",
        doc_notes="See [Agents](hunt_groups.md#agents)",
    )
    alternate_number_action: dm.OneOfStr(("ADD", "REMOVE", "REPLACE"), required=False) = Field(
        default="",
        wb_key="Alternate Number Action",
        doc_notes="Action to take on any Alternate Number columns",
    )
    alternate_numbers: list[WbxcHuntGroupAltNumber] = Field(
        default=[],
        doc_key="Alternate Number 1",
        doc_required="No",
        doc_value="Phone number with optional distinctive ring",
        doc_notes="See [Alternate Numbers](hunt_groups.md#alternate-numbers)",
    )

    @validator("number", always=True, pre=True)
    def validate_number(cls, v, values, field):
        if values["action"] in ("CREATE", "UPDATE"):
            phone_number = values.get("phoneNumber")
            extension = values.get("extension")

            if not phone_number and not extension:
                raise ValueError("Either 'Phone Number' or 'Extension' must be provided")

            return phone_number or extension

        return v

    @validator("hunt_policy", always=True)
    def validate_hunt_policy(cls, v, values, field):
        """
        Validation done here instead of using a OneOf field
        because it is not included in API LIST response so will
        not be populated for a Browse operation
        """
        val = str(v).upper()
        if values["action"] in ("CREATE", "UPDATE"):
            if val not in HUNT_POLICY_TYPES:
                raise ValueError(
                    f'Hunt Policy must be one of{",".join(f"`{h}`" for h in HUNT_POLICY_TYPES)}'
                )
        return val

    @validator("languageCode", always=True)
    def validate_language_code(cls, v, values, field):
        """Hunt group creation fails unless code is all lower-case"""
        if v and values["action"] in ("CREATE", "UPDATE"):
            lang = str(v).lower()
            for code in PREFERRED_LANGUAGES:
                if lang == code.lower():
                    return lang
            raise ValueError(f"Language: '{v}' is invalid")

        return v

    def to_wb(self) -> dict:
        row = super().to_wb()
        for agent in sorted(self.agents, key=lambda x: x.idx):
            row[f"Agent {agent.idx}"] = f"{agent.number}={agent.weight}"

        for altnum in sorted(self.alternate_numbers, key=lambda x: x.idx):
            row[f"Alternate Number {altnum.idx}"] = f"{altnum.phoneNumber}={altnum.ringPattern}"

        return row

    class Config:
        title = "Hunt Groups"
        schema_extra = {
            "data_type": "hunt_groups",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "detail": True,
                "help_doc": True,
            },
        }


class PayloadAgent(TypedDict):
    id: str
    weight: int


class PayloadAltNum(TypedDict):
    phoneNumber: str
    ringPattern: str


def split_hunt_group_agents(model_agents) -> list[PayloadAgent]:
    """
    Split the comma or semicolon separate agent string into a list of
    dictionaries.

    The `self.agents` value consists of one or more extension/phone numbers
    separated by a comma or semicolon. Each entry may optionally have an
    associated weight.

    Ex: `1000,+16085551234,2000=4,+16085553333=2`

    This is split into a list of dictionaries with `number` and `weight` keys.
    The `weight` value is "0" for entries where a weight is not included.

    Args:
        model_agents (str): Value from bulk model agents field

    Returns:
        agents_with_weights
    """
    agents_with_weights = []
    model_agents = model_agents.strip()
    if model_agents:
        for entry in re.split(r"\s*[,|;]\s*", model_agents):
            if "=" in entry:
                number, weight_str = re.split(r"\s*=\s*", entry)
                try:
                    weight = int(weight_str)
                except Exception:
                    raise ValueError(f"Weight: '{weight_str}' is invalid")
            else:
                number, weight = entry, 0
            agents_with_weights.append({"number": number, "weight": int(weight)})

    return agents_with_weights  # noqa


def split_hunt_group_alternate_numbers(model_alternate_numbers) -> list[PayloadAltNum]:
    """
    Split the comma or semicolon separate agent string into a list of
    dictionaries.

    The `self.agents` value consists of one or more extension/phone numbers
    separated by a comma or semicolon. Each entry may optionally have an
    associated weight.

    Ex: `1000,+16085551234,2000=4,+16085553333=2`

    This is split into a list of dictionaries with `number` and `weight` keys.
    The `weight` value is "0" for entries where a weight is not included.

    Args:
        model_alternate_numbers (str): Value from bulk model agents field

    Returns:
        model_alternate_numbers_with_patterns
    """
    model_alternate_numbers_with_patterns = []
    model_alternate_numbers = model_alternate_numbers.strip()
    if model_alternate_numbers:
        for entry in re.split(r"\s*[,|;]\s*", model_alternate_numbers):
            if "=" in entry:
                number, pattern = re.split(r"\s*=\s*", entry)
            else:
                number, pattern = entry, "NORMAL"
            model_alternate_numbers_with_patterns.append({"phoneNumber": number, "ringPattern": pattern})

    return model_alternate_numbers_with_patterns
