from zeus import registry as reg
from zeus.views.template_table import TemplateTableCol, TemplateTable


@reg.browse_table("five9", "users")
def browse_user_table(rows=None):
    return TemplateTable(
        data_type="users",
        rows=rows,
        columns=[
            TemplateTableCol("userName", "User Name"),
            TemplateTableCol("firstName", "First Name"),
            TemplateTableCol("lastName", "Last Name"),
            TemplateTableCol("EMail", "Email"),
            TemplateTableCol("extension"),
        ],
    )


@reg.browse_table("five9", "skills")
def browse_skill_table(rows=None):
    return TemplateTable(
        data_type="skills",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("description"),
            TemplateTableCol("messageOfTheDay", "Message of the Day"),
            TemplateTableCol("routeVoiceMails", "Voicemail"),
        ],
    )


@reg.browse_table("five9", "prompts")
def browse_prompt_table(rows=None):
    return TemplateTable(
        data_type="prompts",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("description"),
            TemplateTableCol("type"),
        ],
    )


@reg.browse_table("five9", "dispositions")
def browse_disposition_table(rows=None):
    return TemplateTable(
        data_type="dispositions",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("description"),
            TemplateTableCol("type"),
            TemplateTableCol("useTimer", "Use Timer"),
            TemplateTableCol("attempts"),
            TemplateTableCol("timer"),
        ],
    )
