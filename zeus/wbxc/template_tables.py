from functools import partial

from zeus import registry as reg
from zeus.wbxc import wbxc_models as wm
from zeus.views.template_table import (
    TemplateTableCol,
    TemplateTable,
    bulk_table_columns,
    bulk_table,
    detail_columns,
)


@reg.browse_table("wbxc", "devices")
def browse_devices_table(rows=None):
    data_type = "devices"
    return TemplateTable(
        data_type=data_type,
        rows=rows,
        columns=[
            TemplateTableCol("mac", "MAC Address"),
            TemplateTableCol("model", "Model"),
            TemplateTableCol("tags", "Tags"),
            *detail_columns(data_type),
        ],
    )


@reg.browse_table("wbxc", "hunt_groups")
def browse_hunt_group_table(rows=None):
    data_type = "hunt_groups"
    return TemplateTable(
        data_type=data_type,
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("location_name", "Location"),
            TemplateTableCol("extension", "Extension"),
            TemplateTableCol("phoneNumber", "Phone Number"),
            TemplateTableCol("location_id", hidden=True),
            *detail_columns(data_type),
        ],
    )


@reg.browse_table("wbxc", "locations")
def browse_locations_table(rows=None):
    data_type = "locations"
    return TemplateTable(
        data_type=data_type,
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("address1", "Address 1"),
            TemplateTableCol("address2", "Address 2"),
            TemplateTableCol("city", "City"),
            TemplateTableCol("state", "State"),
            TemplateTableCol("postalCode", "Zip Code"),
            TemplateTableCol("country", "Country"),
            TemplateTableCol("timeZone", "Time Zone"),
            TemplateTableCol("preferredLanguage", "Email Language"),
            *detail_columns(data_type),
        ],
    )


@reg.browse_table("wbxc", "location_calling")
def browse_location_calling_table(rows=None):
    return TemplateTable(
        data_type="location_calling",
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("callingLineIdPhoneNumber", "Main Number"),
            TemplateTableCol("routingPrefix", "Routing Prefix"),
            TemplateTableCol(
                "enableUnknownExtensionRoutePolicy", "Route Unknown Extensions"
            ),
            TemplateTableCol("unknownExtensionRouteName", "Route Unknown Calls to"),
            TemplateTableCol("outsideDialDigit", "Outbound Dial Digit"),
            TemplateTableCol("enforceOutsideDialDigit", "Outbound Dial Digit Enforcement"),
            TemplateTableCol("externalCallerIdName", "External Caller ID Name"),
        ],
    )


@reg.browse_table("wbxc", "migrations")
def browse_migration_table(rows=None):
    data_type = "migrations"
    return TemplateTable(
        data_type=data_type,
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("type", "Type"),
            TemplateTableCol("first_name", "End User First Name"),
            TemplateTableCol("last_name", "End User Last Name"),
            TemplateTableCol("calling_license", "WebEx Calling License Type"),
            TemplateTableCol("phone_number", "WebEx Calling e164 Phone Number"),
            TemplateTableCol("extension", "WebEx Calling e164 Extension"),
            *detail_columns(data_type)
        ],
    )


@reg.browse_table("wbxc", "numbers")
def browse_numbers_table(rows=None):
    return TemplateTable(
        data_type="numbers",
        rows=rows,
        columns=[
            TemplateTableCol("phone_number_start", "Phone Number"),
            TemplateTableCol("extension", "Extension"),
            TemplateTableCol("location_name", "Location"),
            TemplateTableCol("state", "State"),
            TemplateTableCol("owner_type", "Owner Type"),
            TemplateTableCol("owner_name", "Owner Name"),
        ],
    )


@reg.browse_table("wbxc", "user_calling")
def browse_user_calling_table(rows=None):
    data_type = "user_calling"
    return TemplateTable(
        data_type=data_type,
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("phoneNumber", "Phone Number"),
            TemplateTableCol("extension", "Extension"),
            *detail_columns(data_type),
        ],
    )


@reg.browse_table("wbxc", "virtual_lines")
def browse_virtual_lines_table(rows=None):
    return TemplateTable(
        data_type="virtual_lines",
        rows=rows,
        columns=[
            TemplateTableCol("firstName", "First Name"),
            TemplateTableCol("lastName", "Last Name"),
            TemplateTableCol("displayName", "Display Name"),
            TemplateTableCol("location", "Location"),
            TemplateTableCol("phoneNumber", "Phone Number"),
            TemplateTableCol("extension", "Extension"),
            TemplateTableCol("announcementLanguage", "Announcement Language"),
            TemplateTableCol("timeZone", "Time Zone"),
            TemplateTableCol("directorySearchEnabled", "Directory Search"),
        ],
    )


@reg.browse_table("wbxc", "voicemail_groups")
def browse_voicemail_group_table(rows=None):
    data_type = "voicemail_groups"
    return TemplateTable(
        data_type=data_type,
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("location", "Location"),
            TemplateTableCol("phoneNumber", "Phone Number"),
            TemplateTableCol("extension", "Extension"),
            TemplateTableCol("enabled", "Enabled"),
            TemplateTableCol("location_id", hidden=True),
            *detail_columns(data_type),
        ],
    )


@reg.browse_table("wbxc", "workspace_calling")
def browse_workspace_calling_table(rows=None):
    return TemplateTable(
        data_type="workspace_calling",
        rows=rows,
        columns=[
            TemplateTableCol("name", "Name"),
            TemplateTableCol("location", "Location"),
            TemplateTableCol("licenses", "Calling License"),
            TemplateTableCol("sub_id", "Sub ID"),
            TemplateTableCol("phoneNumber", "Phone Number"),
            TemplateTableCol("extension", "Extension"),
        ],
    )


@reg.bulk_table("wbxc", "hunt_groups")
def bulk_hunt_group_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(wm.WbxcHuntGroup)
    columns.extend(hunt_group_agent_columns(rows))
    columns.extend(hunt_group_altnum_columns(rows))

    return bulk_table(
        data_type="hunt_groups",
        columns=columns,
        rows=rows,
        title="Hunt Groups",
    )


@reg.bulk_table("wbxc", "licenses")
def bulk_licenses_table(rows=None):
    columns = bulk_table_columns(wm.WbxcLicense)
    columns.extend(license_columns(rows))

    return bulk_table(
        data_type="licenses",
        columns=columns,
        rows=rows,
        title="Licenses",
    )


@reg.bulk_table("wbxc", "user_calling")
def bulk_user_calling_table(rows=None):
    table_rows, add_col = create_monitoring_columns(rows)
    columns = bulk_columns_with_monitoring(wm.WbxcUserCalling, add_col)
    return bulk_table(
        wm.WbxcUserCalling, columns=columns, rows=table_rows, title="User Calling"
    )


@reg.bulk_table("wbxc", "workspace_calling")
def bulk_workspace_calling_table(rows=None):
    table_rows, add_col = create_monitoring_columns(rows)
    columns = bulk_columns_with_monitoring(wm.WbxcWorkspaceCalling, add_col)
    return bulk_table(
        wm.WbxcWorkspaceCalling, columns=columns, rows=table_rows, title="Workspace Calling"
    )


def create_monitoring_columns(rows=None):
    """
    Processes a list of rows, where each row contains monitoring details
    in a "monitoring" field. For each row, it extracts monitoring numbers and location
    names based on their "column_id" and constructs a table row with dynamically
    named columns (e.g., "number_1", "location_name_1", etc.). It also determines the
    maximum "column_id" across all rows to create additional columns for the template table.

    Returns:
        table_rows (list[dict]):
        - A list of rows, where each row includes the original values and
        dynamically named columns for monitoring numbers and location names.

        additional_columns (list[TemplateTableCol]):
        - A list of `TemplateTableCol` objects representing the additional columns
        created based on the maximum "column_id" found.

    """
    rows = rows or []
    max_col = max(
        (int(col.get("column_id", 0)) for row in rows for col in row["monitoring"]),
        default=0,
    )

    table_rows = []
    for row in rows:
        tr = row.copy()

        for col in row["monitoring"]:
            column_id = col.get("column_id")
            if column_id:
                tr[f"number_{column_id}"] = col.get("number", "")
                tr[f"location_name_{column_id}"] = col.get("location_name", "")

        table_rows.append(tr)

    additional_columns = []
    for i in range(1, max_col + 1):
        additional_columns.append(TemplateTableCol(f"number_{i}", f"Monitored Number {i}"))
        additional_columns.append(
            TemplateTableCol(f"location_name_{i}", f"Monitored Location {i}")
        )

    return table_rows, additional_columns


def bulk_columns_with_monitoring(model, monitoring_cols):
    id_field = model.schema()["id_field"]
    data_type = model.schema()["data_type"]
    columns = [TemplateTableCol("action", grid_track="80px")]

    for name, field in model.schema()["properties"].items():
        wb_key = field.get("wb_key")

        if not wb_key or name == "action":
            continue

        if name == id_field:
            grid_track = "minmax(max-content, auto)"

        else:
            grid_track = "minmax(min-content, auto)"

        columns.append(TemplateTableCol(name=name, title=wb_key, grid_track=grid_track))

    columns.extend(monitoring_cols)
    return columns


def create_column(
    entry: dict, name_prefix: str, title_prefix: str, getter
) -> TemplateTableCol:
    idx = entry["idx"]
    return TemplateTableCol(
        name=f"{name_prefix}_{idx}",
        title=f"{title_prefix} {idx}",
        value_getter=getter,
    )


def hunt_group_agent_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create a TemplateTableCol instance for each unique agent
    index across all rows.

    Supply a custom getter function to the TemplateTableCol so the correct
    agent entry is extracted and correctly formatted for each
    column.

    Each row will have an 'agents' key that holds a list of 0 or
    more agent dictionaries with 'idx', 'number' and 'weight'
    keys.

    Args:
        rows: (list): List of dictionaries representing Hunt Group worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the entry index
    """

    def agent_getter(idx_, row_):
        for entry_ in row_.get("agents") or []:
            if entry_["idx"] == idx_:
                return f"{entry_['number']}={entry_['weight']}"
        return ""

    columns_by_idx = {}

    for row in rows:

        for entry in row.get("agents") or []:
            idx = entry["idx"]
            columns_by_idx[idx] = create_column(
                entry, "agent", "Agent", partial(agent_getter, idx)
            )

    return [columns_by_idx[idx] for idx in sorted(columns_by_idx)]


def hunt_group_altnum_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create a TemplateTableCol instance for each unique alternate number
    index across all rows.

    Supply a custom getter function to the TemplateTableCol so the correct
    alternate number entry is extracted and correctly formatted for each
    column.

    Each row will have an 'alternate_numbers' key that holds a list of 0 or
    more alternate_number dictionaries with 'idx', 'phoneNumber' and 'ringPattern'
    keys.

    Args:
        rows: (list): List of dictionaries representing Hunt Group worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the entry index
    """

    def altnum_getter(idx_, row_):
        for entry_ in row_.get("alternate_numbers") or []:
            if entry_["idx"] == idx_:
                return f"{entry_['phoneNumber']}={entry_['ringPattern']}"
        return ""

    columns_by_idx = {}

    for row in rows:

        for entry in row.get("alternate_numbers") or []:
            idx = entry["idx"]
            columns_by_idx[idx] = create_column(
                entry, "alternate_number", "Alternate Number", partial(altnum_getter, idx)
            )

    return [columns_by_idx[idx] for idx in sorted(columns_by_idx)]


def license_columns(rows: list[dict]) -> list[TemplateTableCol]:

    def license_getter(idx_, row_):
        for entry_ in row_.get("licenses") or []:
            if entry_["idx"] == idx_:
                return f"{entry_['license']}={entry_['operation']}"
        return ""

    columns_by_idx = {}

    for row in rows:
        for entry in row.get("licenses") or []:
            idx = entry["idx"]
            columns_by_idx[idx] = create_column(entry, "license", "License", partial(license_getter, idx))

    return [columns_by_idx[idx] for idx in sorted(columns_by_idx)]


def device_line_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create TemplateTableCol instances for each unique line appearance
    index across all rows.

    Args:
        rows: (list): List of dictionaries representing the Devices worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the index
    """

    def _getter(field, idx_, row_):
        for entry_ in row_.get("lines", []):
            if entry_["idx"] == idx_:
                return entry_[field]
        return ""

    line_cols = [
        ("type", "Type"),
        ("number", "Number"),
        ("label", "Label"),
        ("allow_decline", "Allow Decline"),
        ("hotline_enabled", "Hotline Enabled"),
        ("hotline_destination", "Hotline Destination"),
        ("t38_enabled", "T38 Enable"),
    ]
    columns = {}

    for row in rows:
        for entry in row.get("lines", []):
            idx = entry["idx"]

            if idx not in columns:
                columns[idx] = [
                    TemplateTableCol(
                        f"line_{field_name}_{idx}",
                        title=f"Line {idx} {title_suffix}",
                        value_getter=partial(_getter, field_name, idx),
                    )
                    for field_name, title_suffix in line_cols
                ]

    sorted_columns = []

    for idx in sorted(columns):
        sorted_columns.extend(columns[idx])

    return sorted_columns


@reg.bulk_table("wbxc", "devices")
def bulk_device_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(wm.WbxcDevice)
    columns.extend(device_line_columns(rows))

    return bulk_table(
        data_type="devices",
        columns=columns,
        rows=rows,
        title="Devices",
    )


def device_settings_enhanced_mcast_destination_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create TemplateTableCol instances for each Enhanced Multicast Destination
    index across all rows.

    Args:
        rows: (list): List of dictionaries representing the Device Settings worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the index
    """

    def _getter(field, idx_, row_):
        for entry_ in row_.get("enhanced_mcast_destinations", []):
            if entry_["idx"] == idx_:
                return entry_[field]
        return ""

    line_cols = [
        ("destination", "Destination"),
        ("xmlapp", "XMLApp"),
        ("timer", "Timer"),
    ]
    columns = {}

    for row in rows:
        for entry in row.get("enhanced_mcast_destinations", []):
            idx = entry["idx"]

            if idx not in columns:
                columns[idx] = [
                    TemplateTableCol(
                        f"enhanced_multicast_{field_name}_{idx}",
                        title=f"Enhanced Multicast {idx} {title_suffix}",
                        value_getter=partial(_getter, field_name, idx),
                    )
                    for field_name, title_suffix in line_cols
                ]

    sorted_columns = []

    for idx in sorted(columns):
        sorted_columns.extend(columns[idx])

    return sorted_columns


@reg.bulk_table("wbxc", "device_settings")
def bulk_device_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(wm.WbxcDeviceSettings)
    columns.extend(device_settings_enhanced_mcast_destination_columns(rows))

    return bulk_table(
        data_type="device_settings",
        columns=columns,
        rows=rows,
        title="Device Settings",
    )
