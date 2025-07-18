from functools import partial
from zeus import registry as reg
from zeus.shared.helpers import deep_get
from zeus.msteams.msteams_models import MsTeamsEmergencyCallingPolicy, MsTeamsNetworkSite
from zeus.views.template_table import (
    TemplateTableCol,
    TemplateTable,
    bulk_table,
    bulk_table_columns,
)


class AddrTableCol(TemplateTableCol):
    """Combine address fields into single value for a single address table column."""

    def value(self, row: dict):
        address_parts = [
            row.get("houseNumber", ""),
            row.get("houseNumberSuffix", ""),
            row.get("preDirectional", ""),
            row.get("streetName", ""),
            row.get("streetSuffix", ""),
            row.get("postDirectional", ""),
        ]
        address = " ".join(part for part in address_parts if part)
        address += f", {row.get('cityOrTown', '')}, {row.get('stateOrProvince', '')} {row.get('postalOrZipCode', '')}"
        return address.strip()


class LanLonTableCol(TemplateTableCol):
    """Displays pending message if latitude or longitude is missing."""

    def value(self, row: dict):
        if not row.get("latitude") or not row.get("longitude"):
            return "Pending"
        return deep_get(row, self.path)


@reg.browse_table("msteams", "emergency_addresses")
def browse_emergency_address_table(rows=None):
    return TemplateTable(
        data_type="emergency_addresses",
        rows=rows,
        columns=[
            TemplateTableCol("description"),
            TemplateTableCol("companyName", "Company"),
            AddrTableCol("Address"),
            TemplateTableCol("country"),
            TemplateTableCol("latitude"),
            TemplateTableCol("longitude"),
            TemplateTableCol("elin", "ELIN"),
        ],
    )


@reg.browse_table("msteams", "emergency_locations")
def browse_emergency_location_table(rows=None):
    return TemplateTable(
        data_type="emergency_locations",
        rows=rows,
        columns=[
            TemplateTableCol("name"),
            TemplateTableCol("elin", "ELIN"),
            TemplateTableCol("addressDescription", "Address Description"),
            AddrTableCol("Address"),
            TemplateTableCol("country"),
        ],
    )


@reg.browse_table("msteams", "subnets")
def browse_subnet_table(rows=None):
    return TemplateTable(
        data_type="subnets",
        rows=rows,
        columns=[
            TemplateTableCol("subnet"),
            TemplateTableCol("description"),
            TemplateTableCol("addressDescription", "Address Description"),
            TemplateTableCol("locationName", "Location Name"),
        ],
    )


@reg.browse_table("msteams", "switches")
def browse_switch_table(rows=None):
    return TemplateTable(
        data_type="switches",
        rows=rows,
        columns=[
            TemplateTableCol("chassisId", "Chassis ID"),
            TemplateTableCol("description"),
            TemplateTableCol("addressDescription", "Address Description"),
            TemplateTableCol("locationName", "Location Name"),
        ],
    )


@reg.browse_table("msteams", "ports")
def browse_port_table(rows=None):
    return TemplateTable(
        data_type="ports",
        rows=rows,
        columns=[
            TemplateTableCol("port"),
            TemplateTableCol("description"),
            TemplateTableCol("chassisId", "Chassis ID"),
            TemplateTableCol("addressDescription", "Address Description"),
            TemplateTableCol("locationName", "Location Name"),
        ],
    )


@reg.browse_table("msteams", "wireless_access_points")
def browse_wap_table(rows=None):
    return TemplateTable(
        data_type="wireless_access_points",
        rows=rows,
        columns=[
            TemplateTableCol("bssid", "BSSID"),
            TemplateTableCol("description"),
            TemplateTableCol("addressDescription", "Address Description"),
            TemplateTableCol("locationName", "Location Name"),
        ],
    )


@reg.browse_table("msteams", "trusted_ips")
def browse_trusted_ip_table(rows=None):
    return TemplateTable(
        data_type="trusted_ips",
        rows=rows,
        columns=[
            TemplateTableCol("ipAddress", "IP Address"),
            TemplateTableCol("networkRange", "Network Range"),
            TemplateTableCol("description"),
        ],
    )


@reg.browse_table("msteams", "emergency_calling_policies")
def browse_emergency_calling_policy_table(rows=None):
    return TemplateTable(
        data_type="emergency_calling_policies",
        rows=rows,
        columns=[
            TemplateTableCol("Identity", "Name"),
            TemplateTableCol("Description"),
            TemplateTableCol("ExternalLocationLookupMode", "External Location Lookup Mode"),
            TemplateTableCol("DialStringsCount", "Dial Strings"),
        ],
    )


@reg.browse_table("msteams", "network_sites")
def browse_network_sites_table(rows=None):
    return TemplateTable(
        data_type="network_sites",
        rows=rows,
        columns=[
            TemplateTableCol("Identity", "Name"),
            TemplateTableCol("Description"),
            TemplateTableCol("NetworkRegionID", "Network Region"),
            TemplateTableCol("EnableLocationBasedRouting", "Location Based Routing"),
            TemplateTableCol("NetworkRoamingPolicy", "Network Roaming Policy"),
            TemplateTableCol("EmergencyCallingPolicy", "Emergency Calling Policy"),
            TemplateTableCol("EmergencyCallRoutingPolicy", "Emergency Call Routing Policy"),
            TemplateTableCol("SubnetsCount", "Subnets"),
        ],
    )


def dial_string_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create TemplateTableCol instances for each unique dial string
    index across all rows.

    Each row will have a 'DialStrings' key that holds a list of 0 or
    more dictionaries with the following keys:
     - idx (int): Relative order for the row's dial strings
     - EmergencyDialString (str)
     - NotificationMode (str)
     - NotificationDialOutNumber (str)
     - NotificationGroup (str)


    Args:
        rows: (list): List of dictionaries representing Emergency Calling Policies worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the entry order
    """

    def dial_string_getter(idx_, row_):
        for entry_ in row_.get("DialStrings", []):
            if entry_["idx"] == idx_:
                return entry_["EmergencyDialString"]
        return ""

    def notification_mode_getter(idx_, row_):
        for entry_ in row_.get("DialStrings", []):
            if entry_["idx"] == idx_:
                return entry_["NotificationMode"]
        return ""

    def notification_dial_out_number_getter(idx_, row_):
        for entry_ in row_.get("DialStrings", []):
            if entry_["idx"] == idx_:
                return entry_["NotificationDialOutNumber"]
        return ""

    def notification_group_getter(idx_, row_):
        for entry_ in row_.get("DialStrings", []):
            if entry_["idx"] == idx_:
                return entry_["NotificationGroup"]
        return ""

    columns = {}

    for row in rows:
        for entry in row.get("DialStrings", []):
            idx = entry["idx"]

            dial_string_col = TemplateTableCol(
                f"EmergencyDialString{idx}",
                title=f"Dial String {idx}",
                value_getter=partial(dial_string_getter, idx),
            )

            notification_mode_col = TemplateTableCol(
                f"NotificationMode{idx}",
                title=f"Notification Mode {idx}",
                value_getter=partial(notification_mode_getter, idx),
            )

            notification_dial_out_number_col = TemplateTableCol(
                f"NotificationDialOutNumber{idx}",
                title=f"Notification Dial Out Number {idx}",
                value_getter=partial(notification_dial_out_number_getter, idx),
            )

            notification_group_col = TemplateTableCol(
                f"NotificationGroup{idx}",
                title=f"Notification Group {idx}",
                value_getter=partial(notification_group_getter, idx),
            )

            columns[idx] = [
                dial_string_col,
                notification_mode_col,
                notification_dial_out_number_col,
                notification_group_col,
            ]

    sorted_columns = []

    for idx in sorted(columns):
        sorted_columns.extend(columns[idx])

    return sorted_columns


@reg.bulk_table("msteams", "emergency_calling_policies")
def bulk_emergency_calling_policy_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(MsTeamsEmergencyCallingPolicy)
    columns.extend(dial_string_columns(rows))

    return bulk_table(
        data_type="emergency_calling_policies",
        columns=columns,
        rows=rows,
        title="Emergency Calling Policies",
    )


@reg.bulk_table("msteams", "emergency_addresses")
def bulk_emergency_address_table(rows=None):
    return TemplateTable(
        data_type="emergency_addresses",
        rows=rows,
        columns=[
            TemplateTableCol("action"),
            TemplateTableCol("description", grid_track="minmax(max-content, auto)"),
            TemplateTableCol("companyName", "Company Name"),
            TemplateTableCol("houseNumber", "House Number"),
            TemplateTableCol("houseNumberSuffix", "House Number Suffix"),
            TemplateTableCol("preDirectional", "Pre Directional"),
            TemplateTableCol("streetName", "Street Name"),
            TemplateTableCol("streetSuffix", "Street Suffix"),
            TemplateTableCol("postDirectional", "Post Directional"),
            TemplateTableCol("cityOrTown", "City"),
            TemplateTableCol("cityOrTownAlias", "City Alias"),
            TemplateTableCol("stateOrProvince", "State"),
            TemplateTableCol("postalOrZipCode", "Zip Code"),
            TemplateTableCol("countyOrDistrict", "County"),
            TemplateTableCol("country"),
            LanLonTableCol("latitude"),
            LanLonTableCol("longitude"),
            TemplateTableCol("elin", "ELIN"),
            TemplateTableCol("companyId", "Company Tax ID"),
        ],
    )


def subnet_columns(rows: list[dict]) -> list[TemplateTableCol]:
    """
    Create TemplateTableCol instances for each unique subnet
    index across all rows.

    Each row will have a 'Subnets' key that holds a list of 0 or
    more dictionaries with the following keys:
     - idx (int): Relative order for the row's dial strings
     - SubnetID (str)
     - MaskBits (str)
     - Description (str)


    Args:
        rows: (list): List of dictionaries representing Network Sites worksheet
        rows.

    Returns:
        (list): List of TemplateTableCol instances sorted by the entry order
    """

    def subnet_id_getter(idx_, row_):
        for entry_ in row_.get("Subnets", []):
            if entry_["idx"] == idx_:
                return entry_["SubnetID"]
        return ""

    def mask_bits_getter(idx_, row_):
        for entry_ in row_.get("Subnets", []):
            if entry_["idx"] == idx_:
                return entry_["MaskBits"]
        return ""

    def desc_getter(idx_, row_):
        for entry_ in row_.get("Subnets", []):
            if entry_["idx"] == idx_:
                return entry_["Description"]
        return ""

    columns = {}

    for row in rows:
        for entry in row.get("Subnets", []):
            idx = entry["idx"]

            subnet_col = TemplateTableCol(
                f"SubnetID{idx}",
                title=f"Subnet {idx}",
                value_getter=partial(subnet_id_getter, idx),
            )

            mask_bits_col = TemplateTableCol(
                f"MaskBits{idx}",
                title=f"Network Range {idx}",
                value_getter=partial(mask_bits_getter, idx),
            )

            description_col = TemplateTableCol(
                f"Description{idx}",
                title=f"Description {idx}",
                value_getter=partial(desc_getter, idx),
            )

            columns[idx] = [
                subnet_col,
                mask_bits_col,
                description_col,
            ]

    sorted_columns = []

    for idx in sorted(columns):
        sorted_columns.extend(columns[idx])

    return sorted_columns


@reg.bulk_table("msteams", "network_sites")
def bulk_network_sites_table(rows=None):
    rows = rows or []
    columns = bulk_table_columns(MsTeamsNetworkSite)
    columns.extend(subnet_columns(rows))

    return bulk_table(
        data_type="network_sites",
        columns=columns,
        rows=rows,
        title="Network Sites",
    )
