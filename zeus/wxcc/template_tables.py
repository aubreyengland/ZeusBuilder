from functools import partial
from zeus import registry as reg
from zeus.wxcc.wxcc_models import WxccQueue, WxccSkillProfile
from zeus.views.template_table import TemplateTableCol, TemplateTable, bulk_table, bulk_table_columns, detail_columns


@reg.browse_table("wxcc", "entry_points")
def browse_entry_point_table(rows=None):
    return TemplateTable(
        data_type="entry_points",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("active"),
            TemplateTableCol("entryPointType", "Type"),
            TemplateTableCol("channelType", "Channel Type"),
            TemplateTableCol("serviceLevelThreshold", "SLA"),
            TemplateTableCol("moh_name", "Music On Hold"),
            TemplateTableCol("queue_name", "Outdial Queue")
        ],
    )


@reg.browse_table("wxcc", "queues")
def browse_queue_table(rows=None):
    rows = rows or []
    return TemplateTable(
        data_type="queues",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("active"),
            TemplateTableCol("queueType", "Queue Type"),
            TemplateTableCol("channelType", "Channel Type"),
            TemplateTableCol("call_distribution_groups_count", "Call Dist. Groups"),
            *detail_columns("queues"),
        ],
    )


@reg.browse_table("wxcc", "skills")
def browse_skill_table(rows=None):
    return TemplateTable(
        data_type="skills",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("description"),
            TemplateTableCol("active"),
            TemplateTableCol("serviceLevelThreshold", "Service Level Threshold"),
            TemplateTableCol("enum_names", "Enum Names"),
        ],
    )


@reg.browse_table("wxcc", "skill_profiles")
def browse_skill_profile_table(rows=None):
    return TemplateTable(
        data_type="skill_profiles",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("description"),
            TemplateTableCol("skills_count", title="Skills"),
            *detail_columns("skill_profiles"),
        ],
    )


@reg.browse_table("wxcc", "teams")
def browse_team_table(rows=None):
    return TemplateTable(
        data_type="teams",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("active"),
            TemplateTableCol("site_name", "Site"),
            TemplateTableCol("teamType", "Team Type"),
        ],
    )


def cdg_team_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create TemplateTableCol instances for each unique call dist. group
    index across all rows.

    Each row will have a 'callDistributionGroups' key that holds a list of 0 or
    more dictionaries with the following keys:
     - order (int): Relative order for the row's groups
     - agentGroups (list): List of team names
     - duration (int)

    Args:
        rows: (list): List of dictionaries representing Queues worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the entry order
    """

    def team_getter(idx_, row_):
        for entry_ in row_.get("callDistributionGroups", []):
            if entry_["order"] == idx_:
                return ";".join(entry_["agentGroups"])
        return ""

    def duration_getter(idx_, row_):
        for entry_ in row_.get("callDistributionGroups", []):
            if entry_["order"] == idx_:
                return entry_["duration"]
        return ""

    columns = {}

    for row in rows:
        for entry in row.get("callDistributionGroups", []):
            idx = entry["order"]

            team_col = TemplateTableCol(
                f"cdg_team_{idx}",
                title=f"Call Distribution Group {idx} Teams",
                value_getter=partial(team_getter, idx)
            )

            duration_col = TemplateTableCol(
                f"cdg_duration_{idx}",
                title=f"Call Distribution Group {idx} Duration",
                value_getter=partial(duration_getter, idx)
            )
            columns[idx] = [team_col, duration_col]

    sorted_columns = []

    for idx in sorted(columns):
        sorted_columns.extend(columns[idx])

    return sorted_columns


@reg.bulk_table("wxcc", "queues")
def bulk_queue_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(WxccQueue)
    columns.extend(cdg_team_columns(rows))

    return bulk_table(
        data_type="queues",
        columns=columns,
        rows=rows,
        title="Queues",
    )


def skill_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create an TemplateTableCol instance for each unique skill
    index across all rows.

    Each row will have a 'skills' key that holds a list of 0 or
    more WxccActiveSkill instances with 'idx', 'name' and 'value'
    keys.

    Args:
        rows: (list): List of dictionaries representing Skill Profiles worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the entry index
    """

    def _getter(field, idx_, row_):
        for entry_ in row_.get("skills") or []:
            if entry_["idx"] == idx_:
                return entry_[field]
        return ""

    skill_cols = [
        ("name", "Name"),
        ("value", "Value")
    ]

    columns_by_idx = {}

    for row in rows:
        for entry in row.get("skills") or []:
            idx = entry["idx"]

            if idx not in columns_by_idx:
                columns_by_idx[idx] = [
                    TemplateTableCol(
                        name=f"skill_{field_name}_{idx}",
                        title=f"Skill {title_suffix} {idx}",
                        value_getter=partial(_getter, field_name, idx),
                    )
                    for field_name, title_suffix in skill_cols
                ]

    sorted_columns = []

    for idx in sorted(columns_by_idx):
        sorted_columns.extend(columns_by_idx[idx])

    return sorted_columns


@reg.bulk_table("wxcc", "skill_profiles")
def bulk_skill_profile_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(WxccSkillProfile)
    columns.extend(skill_columns(rows))

    return bulk_table(
        data_type="skill_profiles",
        columns=columns,
        rows=rows,
        title="Skill Profiles",
    )
