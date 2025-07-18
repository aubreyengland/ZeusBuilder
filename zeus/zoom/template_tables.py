from zeus import registry as reg
from zeus.zoom import zoom_models as zm
from zeus.views import TemplateTableCol, TemplateTable, bulk_table, detail_columns


class AddrTableCol(TemplateTableCol):
    """Combine address fields into single value for a single address table column."""

    def value(self, row: dict):
        street = row["address_line1"]
        if row.get("address_line2"):
            street += f" {row['address_line2']}"
        return f"{street} {row['city']}, {row['state_code']} {row['zip']}"


@reg.browse_table("zoom", "users")
def browse_user_table(rows=None):
    return TemplateTable(
        data_type="users",
        rows=rows,
        columns=[
            TemplateTableCol("email"),
            TemplateTableCol("first_name"),
            TemplateTableCol("last_name"),
            TemplateTableCol("status"),
            TemplateTableCol("role"),
        ],
    )


@reg.browse_table("zoom", "phone_users")
def browse_phone_user_table(rows=None):
    return TemplateTable(
        data_type="phone_users",
        rows=rows,
        columns=[
            TemplateTableCol("email"),
            TemplateTableCol("site_name", "Site"),
            TemplateTableCol("calling_plans"),
            TemplateTableCol("extension_number", "Extension"),
            TemplateTableCol("phone_numbers"),
        ],
    )


@reg.browse_table("zoom", "sites")
def browse_site_table(rows=None):
    return TemplateTable(
        data_type="sites",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("site_code"),
            TemplateTableCol("short_extension_length", "Ext. Length"),
            TemplateTableCol("auto_receptionist"),
            AddrTableCol("address"),
        ],
    )


@reg.browse_table("zoom", "templates")
def browse_template_table(rows=None):
    return TemplateTable(
        data_type="templates",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("type"),
            TemplateTableCol("site_name", "Site"),
        ],
    )


@reg.browse_table("zoom", "devices")
def browse_device_table(rows=None):
    return TemplateTable(
        data_type="devices",
        rows=rows,
        columns=[
            TemplateTableCol("display_name"),
            TemplateTableCol("mac_address"),
            TemplateTableCol("type"),
            TemplateTableCol("model"),
            TemplateTableCol("assignee"),
            TemplateTableCol("template_name", "Template"),
        ],
    )


@reg.browse_table("zoom", "emergency_locations")
def browse_emergency_location_table(rows=None):
    return TemplateTable(
        data_type="emergency_locations",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("site_name", "Site"),
            AddrTableCol("address"),
            TemplateTableCol("parent_location_name", "Parent"),
        ],
    )


@reg.browse_table("zoom", "common_areas")
def browse_common_area_table(rows=None):
    return TemplateTable(
        data_type="common_areas",
        rows=rows,
        columns=[
            TemplateTableCol("display_name"),
            TemplateTableCol("site_name", "Site"),
            TemplateTableCol("calling_plans"),
            TemplateTableCol("extension_number", "Extension"),
            TemplateTableCol("phone_numbers"),
            TemplateTableCol("department"),
            TemplateTableCol("cost_center"),
        ],
    )


@reg.browse_table("zoom", "phone_numbers")
def browse_phone_number_table(rows=None):
    return TemplateTable(
        data_type="phone_numbers",
        rows=rows,
        columns=[
            TemplateTableCol("number"),
            TemplateTableCol("type"),
            TemplateTableCol("status"),
            TemplateTableCol("assignee"),
            TemplateTableCol("site_name", "Site"),
        ],
    )


@reg.browse_table("zoom", "external_contacts")
def browse_external_contact_table(rows=None):
    return TemplateTable(
        data_type="external_contacts",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("email"),
            TemplateTableCol("extension_number"),
            TemplateTableCol("phone_numbers"),
        ],
    )


@reg.browse_table("zoom", "auto_receptionists")
def browse_auto_receptionist_table(rows=None):
    data_type = "auto_receptionists"
    return TemplateTable(
        rows=rows,
        data_type=data_type,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("extension_number"),
            TemplateTableCol("site_name"),
            TemplateTableCol("phone_numbers"),
            TemplateTableCol("timezone"),
            TemplateTableCol("audio_prompt_language"),
            *detail_columns(data_type),
        ],
    )


@reg.bulk_table("zoom", "phone_users")
def bulk_phone_user_table(rows=None):
    return bulk_table(data_type="phone_users", columns=[
        TemplateTableCol("email"),
        TemplateTableCol("extension_number", "Extension"),
        TemplateTableCol("phone_numbers"),
        TemplateTableCol("site_name", "Site"),
        TemplateTableCol("outbound_caller_id", "Caller ID"),
        TemplateTableCol("template_name", "Template"),
        TemplateTableCol("calling_plans"),
        TemplateTableCol("address_line1", "Address Line 1"),
        TemplateTableCol("address_line2", "Address Line 2"),
        TemplateTableCol("city"),
        TemplateTableCol("state_code", "State"),
        TemplateTableCol("zip", "ZIP"),
        TemplateTableCol("country"),
        TemplateTableCol("voicemail_enable"),
    ], rows=rows, title=zm.ZoomPhoneUser.schema()["title"])


@reg.bulk_table("zoom", "sites")
def bulk_site_table(rows=None):
    return bulk_table(data_type="sites", columns=[
        TemplateTableCol("name"),
        TemplateTableCol("new_name"),
        TemplateTableCol("site_code"),
        TemplateTableCol("short_extension_length", "Extension Length"),
        TemplateTableCol("auto_receptionist"),
        TemplateTableCol("address_line1", "Address Line 1"),
        TemplateTableCol("address_line2", "Address Line 2"),
        TemplateTableCol("city"),
        TemplateTableCol("state_code", "State"),
        TemplateTableCol("zip", "ZIP"),
        TemplateTableCol("country"),
        TemplateTableCol("transfer_site_name", "Transfer Site"),
    ], rows=rows, title=zm.ZoomSite.schema()["title"])


@reg.bulk_table("zoom", "templates")
def bulk_template_table(rows=None):
    return bulk_table(data_type="templates", columns=[
        TemplateTableCol("name"),
        TemplateTableCol("type"),
        TemplateTableCol("site_name"),
        TemplateTableCol("new_name"),
        TemplateTableCol("description"),
        TemplateTableCol("voicemail_enable"),
        TemplateTableCol("call_forwarding_enable"),
        TemplateTableCol("call_forwarding_type"),
    ], rows=rows, title=zm.ZoomTemplate.schema()["title"])

@reg.bulk_table("zoom", "routing_rules")
def bulk_routing_rule_table(rows=None):
    return bulk_table(data_type="routing_rules", columns=[
        TemplateTableCol("name"),
        TemplateTableCol("site_name"),
        TemplateTableCol("number_pattern"),
        TemplateTableCol("translation"),
        TemplateTableCol("rule_type"),
    ], rows=rows, title=zm.ZoomRoutingRule.schema()["title"])
    
@reg.bulk_table("zoom", "alerts")
def bulk_alert_table(rows=None):
    return bulk_table(data_type="alerts", columns=[
        TemplateTableCol("name"),
        TemplateTableCol("site_name"),
        TemplateTableCol("alert_type"),
        TemplateTableCol("alert_status"),
        TemplateTableCol("alert_description"),
    ], rows=rows, title=zm.ZoomAlert.schema()["title"])
