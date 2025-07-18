import re
import logging
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from typing import List, Union, Tuple, Optional
from pydantic import Field, EmailStr, validator, BaseModel

log = logging.getLogger(__name__)


class ZoomCCUserSkill(BaseModel):
    """
    Model used to ensure consistent and valid data is passed to
    ZoomCCUserSkillsAssignTask and ZoomCCUserSkillRemoveTask tasks from
    the User and Skill services.

    user_proficiency_level is not used for text skill types but may still
    be provided by the user in the workbook or returned by the API. It is
    forced to None in the validator for text skills to ensure
    it cannot influence an equality check between two otherwise-identical
    skil_type=text instances. Otherwise, an UPDATE operation may try to
    assign an already assigned skill and result in an error.

    The user_proficiency_level value range is validated for proficiency skills
    because the ZoomCC API accepts 0, but it results in an invalid assignment
    in the Zoom UI. The upper limit (currently 5) is also enforced because
    the API error does not include the skill name in the error message, which
    may be confusing when assigning multiple skills to a user.
    """

    skill_id: str
    skill_type: str
    skill_name: str
    skill_category_name: str
    user_proficiency_level: Optional[int] = None

    @validator("user_proficiency_level", pre=True)
    def validate_user_proficiency_level(cls, v, values):
        """
        Ensure user_proficiency_level is None for text skill_type
        in order to ensure instance equality checks are accurate

        Ensure user_proficiency_level is an integer between 1-5 for proficiency skill_type.
        """
        if values["skill_type"] == "text":
            return None

        err = f"A proficiency value between 1-5 is required for skill: {values['skill_name']} assignment"

        if not v:
            raise ValueError(err)

        match = re.match(r"^([1-5])$", str(v).strip())
        if not match:
            raise ValueError(err)

        return int(match.group(1))

    @property
    def unique_name(self):
        return f"{self.skill_category_name}:{self.skill_name}"


zoomcc_queue_channel_types = ("voice",  "video", "messaging")

zoomcc_queue_distribution_map = {
    0: "Longest Idle",
    1: "Sequential",
    2: "Rotating",
    3: "Simultaneous",
    4: "Most Available",
    5: "Manual",
}


@reg.data_type("zoomcc", "queues")
class ZoomCCQueue(dm.DataTypeBase):
    """
    ### Distribution Methods
    Each queue must be assigned a distribution method, however, some methods
    are only valid for specific channel types. Below are the supported channel
    types for each distribution method.

    - Longest Idle. Valid for channel types: voice or video.
    - Sequential. Valid for channel types: voice or video.
    - Rotating. Valid for channel types: voice or video.
    - Simultaneous. Valid for channel types: voice or video.
    - Most Available. Valid for channel type: messaging.
    - Manual. Valid for channel types: voice or video.
    """

    queue_name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        test_value="Zeus Test Queue 1",
    )
    queue_description: str = Field(wb_key="Description", doc_required="No")
    channel_type: str = Field(
        wb_key="Channel Type",
        doc_required="Yes",
        doc_value="One of `voice`, `video`, `messaging`",
        doc_notes="Legacy channel types: `sms`, `chat` have been replaced by `messaging` and can no longer be created",
        test_value="voice",
    )
    distribution_name: str = Field(
        wb_key="Distribution",
        doc_required="Yes",
        doc_value="One of `Longest Idle`, `Sequential`, `Rotating`, `Simultaneous`, `Most Available`, `Manual`",
        test_value="Longest Idle",
    )
    wrap_up_time: str = Field(
        default="",
        wb_key="Wrap Up Time",
        doc_required="No",
        doc_value="Wrap up time between 0 - 300 seconds",
    )
    short_abandon_threshold: str = Field(
        default="",
        # wb_key="Short Abandon Threshold",  # Hide field due to https://github.com/cdwlabs/zeus/issues/334
        doc_required="No",
        doc_value="Short abandon threshold between 1 - 255 seconds",
        doc_notes="Set to `0` to disable",
    )
    max_wait_time_value: str = Field(
        default="",
        wb_key="Max Wait Time",
        doc_required="No",
        doc_value="Max wait time in seconds, minutes or hours. Examples: `10s`, `30m`, `4h`",
        doc_notes="Note: Due to Zoom API limitations, the Max Wait Time cannot be disabled",
    )
    max_engagement_in_queue: str = Field(
        default="",
        wb_key="Max Engagements",
        doc_required="No",
        doc_value=(
            "Determines the number of queued contacts before subsequent contacts are routed to the "
            "overflow destination. Value must be between 1 - 3000."
        ),
        doc_notes=(
            "Note: This value can be set up to 5000 in the Zoom web portal, "
            "however; the Zoom API limits the maximum to 3000"
        ),
    )
    agents: str = Field(
        default="",
        wb_key="Agents",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
    )
    supervisors: str = Field(
        default="",
        wb_key="Supervisors",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
    )
    dispositions: str = Field(
        default="",
        wb_key="Dispositions",
        doc_required="No",
        doc_value="One or more disposition names separated by a comma or semicolon ",
    )
    agents_to_remove: str = Field(
        default="",
        wb_key="Agents To Remove",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    supervisors_to_remove: str = Field(
        default="",
        wb_key="Supervisors To Remove",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    dispositions_to_remove: str = Field(
        default="",
        wb_key="Dispositions To Remove",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    new_queue_name: str = Field(
        default="",
        wb_key="New Queue Name",
        doc_required="No",
        doc_notes="Only applicable to `UPDATE` operations",
    )

    @validator("max_wait_time_value")
    def validate_max_wait_time_value(cls, v):
        """Ensure the value can be converted to seconds but store the string value."""
        time_val_str = str(v).strip()
        if time_val_str:
            parse_time_value_to_seconds(time_val_str)
        return time_val_str

    @property
    def agents_list(self) -> list:
        if self.agents:
            return re.split(r"\s*[,|;]\s*", self.agents)
        return []

    @property
    def supervisors_list(self) -> list:
        if self.supervisors:
            return re.split(r"\s*[,|;]\s*", self.supervisors)
        return []

    @property
    def all_users_list(self) -> List[Tuple[str, str]]:
        """Combine agent and supervisor assignments into one list as (assignment type, email) tuples."""
        all_users = []
        all_users.extend([("agent", name) for name in self.agents_list])
        all_users.extend([("supervisor", name) for name in self.supervisors_list])
        return all_users

    @property
    def dispositions_list(self) -> list:
        if self.dispositions:
            return re.split(r"\s*[,|;]\s*", self.dispositions)
        return []

    @property
    def dispositions_to_remove_list(self) -> List[Tuple[str, str]]:
        if self.dispositions_to_remove:
            return re.split(r"\s*[,|;]\s*", self.dispositions_to_remove)
        return []

    @property
    def agents_to_remove_list(self) -> list:
        if self.agents_to_remove:
            return re.split(r"\s*[,|;]\s*", self.agents_to_remove)
        return []

    @property
    def supervisors_to_remove_list(self) -> list:
        if self.supervisors_to_remove:
            return re.split(r"\s*[,|;]\s*", self.supervisors_to_remove)
        return []

    @property
    def all_users_to_remove_list(self) -> List[Tuple[str, str]]:
        all_users = []
        all_users.extend([("agent", name) for name in self.agents_to_remove_list])
        all_users.extend([("supervisor", name) for name in self.supervisors_to_remove_list])
        return all_users

    class Config:
        title = "Queues"
        schema_extra = {
            "data_type": "queues",
            "id_field": "queue_name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoomcc", "users")
class ZoomCCUser(dm.DataTypeBase):
    """
    ### Skills
    Skills can be assigned to users as part of `CREATE` or `UPDATE` operations using the `Skills` column.
    The proficiency value for an already-assigned proficiency queue can also be changed by specifying the
    new proficiency value in the `Skills` column.

    Skills can be removed from users as part of an `UPDATE` operation using the `Skills To Remove` column.

    Because the same skill name can exist in multiple skill categories, skills must be indicated as `category:name`
    (text skills) or `category:name=proficiency` (proficiency skills). Multiple skills can be assigned by separating
    them by comma or semicolon.

    **Examples**

    Assign the skill *PC* in the text-based skill category *DesktopSupport*:
        `HelpDesk:PC`

    Assign the skills *Android* and *IOS* in the proficiency-based skill category *MobileSupport*:
        `MobileSupport:Android=5,MobileSupport:IOS=5`

    ### Queues
    Queues can be assigned to users as agents using the `Agent Queues` column or supervisors using
    the `Supervisor Queues` column.

    Queues can be removed from users as part of an `UPDATE` operation using the `Agent Queues To Remove` and
    `Supervisor Queues To Remove` columns.

    Multiple queues can be assigned by separating the queue names with a comma or semicolon.
    """

    user_email: EmailStr = Field(
        wb_key="Email Address",
        doc_required="Yes",
        doc_value="Email address of existing Zoom user",
        test_value="testuser@xyz.com",
    )
    role_name: str = Field(
        wb_key="Role",
        doc_required="Yes",
        doc_value="Existing Zoom CC Role",
    )
    client_integration: str = Field(
        wb_key="Client Integration",
        doc_required="Yes",
        doc_value="One of `Default`, `Salesforce`, `Zendesk`, `ServiceNow`, `Microsoft_Dynamics_365`",
        doc_notes="The integration must be enabled and configured with in the Zoom account",
        test_value="Default",
    )
    concurrent_message_capacity: str = Field(
        wb_key="Max Message Concurrency",
        doc_required="Yes",
        doc_value="0 - 20",
    )
    user_access: str = Field(
        wb_key="User Access",
        doc_required="Yes",
        doc_value="One of `active`, `inactive`",
    )
    agent_queues: str = Field(
        default="",
        wb_key="Agent Queues",
        doc_required="No",
        doc_value="One or more Zoom CC queue names separated by a comma or semicolon. Example: `Billing,Sales`. ",
    )
    supervisor_queues: str = Field(
        default="",
        wb_key="Supervisor Queues",
        doc_required="No",
        doc_value="One or more Zoom CC queue names separated by a comma or semicolon. Example: `Billing,Sales`. ",
    )
    skills: str = Field(
        default="",
        wb_key="Skills",
        doc_required="No",
        doc_value=(
            "One or more Zoom CC skills in the format `category:skill` for text skills "
            "or `skill category:skill=proficiency` for proficiency skills. "
        ),
        doc_notes=(
            "Text skill example: `HelpDesk:PC,HelpDesk:Mac`. "
            "Proficiency skill example: `HelpDesk:IOS=3,HelpDesk:Android=4`. "
        ),
    )

    multi_channel_engagements: dm.ReqYN = Field(
        wb_key="Multi Channel Engagements",
        doc_notes="Determines if user will receive voice or video engagements while handling chat and SMS engagements.",
    )
    max_agent_load: str = Field(
        default="",
        wb_key="Max Agent Load",
        doc_required="Conditional",
        doc_value="1 - 100",
        doc_notes="Required if `Multi Channel Engagements` is enabled",
        test_value="100",
    )
    skills_to_remove: str = Field(
        default="",
        wb_key="Skills To Remove",
        doc_required="No",
        doc_value=(
            "One or more currently-assigned skills in the format `category:skill` "
            "separated by comma or semicolon. "
        ),
        doc_notes="Only applicable to `UPDATE` operations",
    )
    agent_queues_to_remove: str = Field(
        default="",
        wb_key="Agent Queues To Remove",
        doc_required="No",
        doc_value="One or more currently-assigned agent queues separated by comma or semicolon. ",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    supervisor_queues_to_remove: str = Field(
        default="",
        wb_key="Supervisor Queues To Remove",
        doc_required="No",
        doc_value="One or more currently-assigned supervisor queues separated by comma or semicolon. ",
        doc_notes="Only applicable to `UPDATE` operations",
    )

    @validator("max_agent_load")
    def validate_max_agent_load(cls, v, values):
        """Ensure max_agent_load is set if multi_channel_engagements is `Y`"""
        if not v and values.get("multi_channel_engagements") == "Y":
            raise ValueError(
                f"Max Agent Load must be provided if Multi Channel Engagements is enabled"
            )
        return v

    @validator("skills", "skills_to_remove")
    def validate_skills(cls, v, values):
        if v:
            parse_user_skills_with_unique_skill_names(v)
        return v

    @property
    def agent_queues_list(self) -> list:
        if self.agent_queues:
            return re.split(r"\s*[,|;]\s*", self.agent_queues)
        return []

    @property
    def supervisor_queues_list(self) -> list:
        if self.supervisor_queues:
            return re.split(r"\s*[,|;]\s*", self.supervisor_queues)
        return []

    @property
    def all_queues_list(self) -> List[Tuple[str, str]]:
        """Combine agent and supervisor queue names into one list as (queue_type, name) tuples."""
        all_queues = []
        all_queues.extend([("agent", name) for name in self.agent_queues_list])
        all_queues.extend([("supervisor", name) for name in self.supervisor_queues_list])
        return all_queues

    @property
    def skills_list(self) -> List[tuple]:
        """
        Return as a list of (skill category, skill name, proficiency) tuples.
        Proficiency will be None if not included for text skills.
        """
        parsed_skills_to_assign = []

        if self.skills:
            parsed_skills_to_assign = parse_user_skills_with_unique_skill_names(self.skills)

        return parsed_skills_to_assign

    @property
    def skills_to_remove_list(self) -> List[Tuple[str, str]]:
        """
        Pass items through parse_user_skills to convert to (skill category, skill name, proficiency)
        tuples in case proficiency values were unnecessarily included but
        return only the skill category, skill name
        """
        parsed_skills_to_remove = []

        if self.skills_to_remove:
            split_skills_to_remove = parse_user_skills_with_unique_skill_names(
                self.skills_to_remove
            )
            parsed_skills_to_remove = [(p[0], p[1]) for p in split_skills_to_remove]

        return parsed_skills_to_remove

    @property
    def agent_queues_to_remove_list(self) -> list:
        if self.agent_queues_to_remove:
            return re.split(r"\s*[,|;]\s*", self.agent_queues_to_remove)
        return []

    @property
    def supervisor_queues_to_remove_list(self) -> list:
        if self.supervisor_queues_to_remove:
            return re.split(r"\s*[,|;]\s*", self.supervisor_queues_to_remove)
        return []

    @property
    def all_queues_to_remove_list(self) -> List[Tuple[str, str]]:
        all_queues = []
        all_queues.extend([("agent", name) for name in self.agent_queues_to_remove_list])
        all_queues.extend(
            [("supervisor", name) for name in self.supervisor_queues_to_remove_list]
        )
        return all_queues

    class Config:
        title = "Users"
        schema_extra = {
            "data_type": "users",
            "id_field": "user_email",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoomcc", "dispositions")
class ZoomCCDisposition(dm.DataTypeBase):
    disposition_name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Name of the disposition",
    )
    disposition_description: str = Field(
        wb_key="Description",
        doc_required="No",
        doc_value="Description of the disposition",
    )
    status: str = Field(
        wb_key="Status",
        doc_required="Yes",
        doc_value="One of `active`, `inactive`",
    )
    disposition_sets: str = Field(
        default="",
        wb_key="Disposition Sets",
        doc_required="No",
        doc_value=(
            "One or more Zoom CC Disposition Set names separated by a comma or semi-colon. "
            "Example: `DispositionSet1,DispositionSet12`."
        ),
        doc_notes="`UPDATE` operations can add new disposition set assignments but cannot remove existing assignments",
    )

    @property
    def disposition_sets_list(self) -> list:
        """Return comma/semicolon-separated disposition sets string, as a list."""
        if self.disposition_sets:
            return re.split(r"\s*[,|;]\s*", self.disposition_sets)
        return []

    class Config:
        title = "Dispositions"
        schema_extra = {
            "data_type": "dispositions",
            "id_field": "disposition_name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoomcc", "skills")
class ZoomCCSkill(dm.DataTypeBase):
    """
    ### User Assignment
    Skills can be assigned to users as part of `CREATE` or `UPDATE` operations by entering the user
    email addresses(s) in the `Users` column. The proficiency value for an already-assigned proficiency
    queue can also be changed by specifying the new proficiency value in the `Skills` column.

    Skills can be removed from users as part of an `UPDATE` operation by entering the user email addresses(s)
    in the `Users To Remove` column.

    For assignment to proficiency skills the entries must be in the format `email=proficiency`.
    Example: `agent1@xyz.com=1,agent2@xyz.com=2`.

    """

    skill_name: str = Field(
        wb_key="Name",
        doc_required="Yes",
    )
    skill_category_name: str = Field(
        wb_key="Skill Category",
        doc_required="Yes",
        doc_value="Skill category to which this skill is assigned",
        doc_notes="Only applicable to `CREATE` operations",
    )
    new_skill_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    users: str = Field(
        default="",
        wb_key="Users",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
        doc_notes=(
            "For proficiency skills, the user proficiency value must also be indicated. "
            "Example: `agent1@xyz.com=3`"
        ),
    )
    users_to_remove: str = Field(
        default="",
        wb_key="Users To Remove",
        doc_required="No",
        doc_value="One or more Zoom CC user email addresses separated by a comma or semicolon ",
        doc_notes="Only applicable to `UPDATE` operations",
    )

    @property
    def users_list(self) -> List[tuple]:
        """
        Skill assignments parsed into email, proficiency tuples.
        Proficiency will be None if not included for text skills.
        """
        parsed_users = []

        if self.users:
            split_users = re.split(r"\s*[,|;]\s*", self.users)
            parsed_users = parse_user_skills(split_users)

        return parsed_users

    @property
    def users_to_remove_list(self) -> List[str]:
        """
        Pass items through parse_user_skills to convert to email, proficiency tuples.
        in case proficiency values were unnecessarily included but
        return only the emails
        """
        parsed_users_to_remove = []
        if self.users_to_remove:

            split_users_to_remove = re.split(r"\s*[,|;]\s*", self.users_to_remove)
            parsed_users_to_remove = [
                p[0] for p in parse_user_skills(split_users_to_remove)
            ]

        return parsed_users_to_remove

    class Config:
        title = "Skills"
        schema_extra = {
            "data_type": "skills",
            "id_field": "skill_name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoomcc", "skill_categories")
class ZoomCCSkillCategory(dm.DataTypeBase):
    skill_category_name: str = Field(wb_key="Name", doc_required="Yes")
    skill_type: dm.OneOfStr(("text", "proficiency"), required=True) = Field(wb_key="Type")
    skill_category_description: str = Field(
        wb_key="Description",
        doc_required="No",
        doc_value="Skill category description",
    )
    skills: str = Field(
        default="",
        wb_key="Skills",
        doc_required="No",
        doc_value="One or more comma/semicolon-separated skill names to create along with this category",
    )
    max_proficiency_level: str = Field(
        default="",
        wb_key="Max Proficiency Level",
        doc_required="Conditional",
        doc_value="Value 1 - 5",
        doc_notes="Required for skill type: `proficiency`",
    )
    new_skill_category_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    skills_to_remove: str = Field(
        default="",
        wb_key="Skills To Remove",
        doc_required="No",
        doc_value="One or more comma/semicolon-separated existing skills to remove from this category",
        doc_notes="Only applicable to `UPDATE` operations",
    )

    @property
    def skills_to_add_list(self) -> list:
        if self.skills:
            return re.split(r"\s*[,|;]\s*", self.skills)
        return []

    @property
    def skills_to_remove_list(self) -> list:
        if self.skills_to_remove:
            return re.split(r"\s*[,|;]\s*", self.skills_to_remove)
        return []

    class Config:
        title = "Skill Categories"
        schema_extra = {
            "data_type": "skill_categories",
            "id_field": "skill_category_name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


def parse_user_skills_with_unique_skill_names(
    skill_assignment_str,
) -> List[Tuple[str, str, Union[str, None]]]:
    parsed_skills_to_assign = []
    skill_assignment_str = skill_assignment_str or ""

    if skill_assignment_str:
        split_skills_to_assign = re.split(r"\s*[,|;]\s*", skill_assignment_str)

        for category_colon_name, proficiency in parse_user_skills(split_skills_to_assign):
            split_name = re.split(r"\s*:\s*", category_colon_name)
            if not len(split_name) == 2:
                raise ValueError(
                    f"Skill: '{category_colon_name}' is invalid. Skill Identifiers"
                    f" must be in format 'skill category:skill name'"
                )

            parsed_skills_to_assign.append((split_name[0], split_name[1], proficiency))

    return parsed_skills_to_assign


def parse_user_skills(user_skills: List[str]) -> List[Tuple[str, Union[str, None]]]:
    """
    Parse the split comma/semicolon-separated user skills assignment values
    from the Skill and User models into a list of tuples.

    The first value in each tuple is the skill name (if coming from a User model)
    or user email address (if coming from a Skill model).
    The second value is the proficiency value, if provided or None.

    Assignments to proficiency skills must include a proficiency value and should be formatted
    as `skill name=1`, `user@xyz.com=2`.

    Assignments to test skills do not require a proficiency value and should just contain the
    skill name or email address, however, we must account for the possibility that users will
    include the proficiency value in the workbook.

    The skill type may not be known at the point when this function is called, so it accommodates
    both formats and leaves it to the calling service or API request to validate values.

    Each list item is parsed into a (name, proficiency) tuple whether a proficiency value is provided
    or not for consistency.

    Examples:
    >>> parse_user_skills([' u1@xyz.com'])
    [('u1@xyz.com', None)]
    >>> parse_user_skills(['Test Skill 1'])
    [('Test Skill 1', None)]
    >>> parse_user_skills(['Test Skill 1 = 1'])
    [('Test Skill 1', '1')]
    >>> parse_user_skills(['Test Skill 1=1', 'Test Skill 2=2 '])
    [('Test Skill 1', '1'), ('Test Skill 2', '2')]
    >>> parse_user_skills([' u1@xyz.com', 'u2@xyz.com'])
    [('u1@xyz.com', None), ('u2@xyz.com', None)]
    >>> parse_user_skills(['u1@xyz.com=1', 'u2@xyz.com=2'])
    [('u1@xyz.com', '1'), ('u2@xyz.com', '2')]
    >>> parse_user_skills([])
    []
    """
    parsed_user_skills = []

    for user_skill in user_skills:

        name_proficiency_split = re.split(r"\s*=\s*", str(user_skill), maxsplit=2)

        name: str = name_proficiency_split[0].strip()

        if len(name_proficiency_split) == 2:
            proficiency = name_proficiency_split[-1].strip()
        else:
            proficiency = None

        parsed_user_skills.append((name, proficiency))

    return parsed_user_skills


def parse_time_value_to_seconds(time_value: str) -> int:
    """
    Parse a workbook time value which may be in seconds, minutes or hours
    into seconds or raise an Exception if the value cannot be parsed

    Expected format is an integer followed by 's', 'm', 'h' but will
    accommodate variations by just looking at the first letter.

    If a bare integer is provided, assume it is already in seconds

    Examples:
    >>> parse_time_value_to_seconds('30')
    30
    >>> parse_time_value_to_seconds('30s')
    30
    >>> parse_time_value_to_seconds('30 secs')
    30
    >>> parse_time_value_to_seconds('4m')
    240
    >>> parse_time_value_to_seconds('4 MINUTES')
    240
    >>> parse_time_value_to_seconds('1Hr')
    3600
    >>> parse_time_value_to_seconds('12 Hours')
    43200
    """
    time_value = time_value.lower().strip()
    if time_value.isdigit():
        return int(time_value)

    if m := re.match(r"^(\d+)\s*s", time_value):
        return int(m.group(1))

    if m := re.match(r"^(\d+)\s*m", time_value):
        return int(m.group(1)) * 60

    if m := re.match(r"^(\d+)\s*h", time_value):
        return int(m.group(1)) * 3600

    raise ValueError(
        "Value must be formatted in seconds or minutes or hours. Ex: 30s, 5m, 12h"
    )


def convert_seconds_to_workbook_value(seconds_value: str) -> str:
    """
    Convert a string representing a number of seconds into the most conscise format
    for the workbook.

    Workbook format is an integer followed by 's', 'm' or 'h' (seconds, minutes or hours).
    Only whole values are allowed.

    Examples:
    >>> convert_seconds_to_workbook_value("")
    ''
    >>> convert_seconds_to_workbook_value("30")
    '30s'
    >>> convert_seconds_to_workbook_value("60")
    '1m'
    >>> convert_seconds_to_workbook_value("62")
    '62s'
    >>> convert_seconds_to_workbook_value("7200")
    '2h'
    >>> convert_seconds_to_workbook_value("5400")
    '90m'
    """
    workbook_value = ""

    if str(seconds_value).strip():
        seconds = int(str(seconds_value).strip())

        if seconds >= 3600 and seconds % 3600 == 0:
            workbook_value = f"{int(seconds / 3600)}h"
        elif seconds >= 60 and seconds % 60 == 0:
            workbook_value = f"{int(seconds / 60)}m"
        else:
            workbook_value = f"{seconds}s"

    return workbook_value
