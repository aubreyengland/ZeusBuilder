from zeus import registry as reg
from zeus.views import TemplateTableCol, TemplateTable


@reg.browse_table("zoomcc", "users")
def browse_user_table(rows=None):
    return TemplateTable(
        data_type="users",
        rows=rows,
        columns=[
            TemplateTableCol("user_email"),
            TemplateTableCol("role_name", "Role"),
            TemplateTableCol("user_access", "User Access"),
            TemplateTableCol("client_integration", "Client Integration"),
            TemplateTableCol("multi_channel_engagements", "Multi Channel"),
            TemplateTableCol("max_agent_load", "Max Load"),
            TemplateTableCol("concurrent_message_capacity", "Max Msgs"),
        ],
    )


@reg.browse_table("zoomcc", "dispositions")
def browse_disposition_table(rows=None):
    return TemplateTable(
        data_type="dispositions",
        rows=rows,
        columns=[
            TemplateTableCol("disposition_name", "Name"),
            TemplateTableCol("disposition_description", "Description"),
            TemplateTableCol("status", "Status"),
        ],
    )


@reg.browse_table("zoomcc", "skills")
def browse_skill_table(rows=None):
    return TemplateTable(
        data_type="skills",
        rows=rows,
        columns=[
            TemplateTableCol("skill_name", "Name"),
            TemplateTableCol("skill_category_name", "Skill Category"),
        ],
    )


@reg.browse_table("zoomcc", "skill_categories")
def browse_skill_category_table(rows=None):
    return TemplateTable(
        data_type="skill_categories",
        rows=rows,
        columns=[
            TemplateTableCol("skill_category_name", "Name"),
            TemplateTableCol("skill_type", "Type"),
            TemplateTableCol("skill_category_description", "Description"),
            TemplateTableCol("skills", "Skills"),
            TemplateTableCol("max_proficiency_level", "Max Prof."),
        ],
    )


@reg.browse_table("zoomcc", "queues")
def browse_queue_table(rows=None):
    return TemplateTable(
        data_type="queues",
        rows=rows,
        columns=[
            TemplateTableCol("queue_name"),
            TemplateTableCol("queue_description", "Description"),
            TemplateTableCol("channel_type"),
            TemplateTableCol("distribution_name", "Distribution"),
            TemplateTableCol("wrap_up_time", "Wrap Up Time"),
            TemplateTableCol("short_abandon_threshold", "Short Abandon Threshold"),
            TemplateTableCol("max_wait_time_value", "Max Wait Time"),
            TemplateTableCol("max_engagement_in_queue", "Max Engagements"),
        ],
    )
