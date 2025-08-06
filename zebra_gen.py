#!/usr/bin/env python3
import argparse
import csv
import logging
import os
import re
import json
import requests 
import pandas as pd
from requests.auth import HTTPBasicAuth
from zeus.zoom.zoom_simple import ZoomSimpleClient as zsc
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if present

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#access_token = os.getenv("ZOOM_S2S_ACCESS_TOKEN")

def get_new_s2s_token() -> str:
    """
    Fetch a new Zoom Server-to-Server (S2S) access token using client credentials.
    """
    account_id = os.getenv("ZOOM_S2S_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_S2S_CLIENT_ID")
    client_secret = os.getenv("ZOOM_S2S_CLIENT_SECRET")
    if not all([account_id, client_id, client_secret]):
        logger.error("Missing Zoom API credentials in environment variables.")
        return ""

    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={account_id}"
    try:
        response = requests.post(url, auth=HTTPBasicAuth(client_id, client_secret))
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token", "")
    except Exception as e:
        logger.error(f"Error fetching new S2S token: {e}")
        return ""

# read site list from xlsx file
def read_site_list(file_path: str) -> list:
    """
    Read a list of sites from an Excel file.
    The file should have a single column with site names.
    """
    
    header = "Site List for ZebraGen"

    try:
        
        df = pd.read_excel(file_path, header=header)
        return df[0].tolist()  # Return the first column as a list
    except Exception as e:
        logger.error(f"Error reading site list from {file_path}: {e}")
        return []

def process_device_type_resp(resp: dict) -> tuple:
    """
    Split the API device_type value into the type and model values necessary to create a device.
    For "other" devices, return type "other" and an empty model.
    """
    resp_device_type = str(resp.get("device_type", "")).strip().lower()
    if resp_device_type == "other":
        return "other", ""
    split_device_type = re.split(r"\s+", resp_device_type, maxsplit=1)
    if len(split_device_type) > 1:
        return split_device_type[0], split_device_type[1]
    return split_device_type[0], ""


def get_provision_data(client, device_id: str) -> dict:
    """
    Get the provision data for a given device ID.
    """
    try:
        response = client.phone_devices.get(device_id)
        return response.get("provision", {})
    except Exception as e:
        logger.error(f"Error fetching provision data for device {device_id}: {e}")
        return {}


def get_sip_account_details(provision_data: dict) -> dict:
    """
    Extract SIP account details from the provision data.
    Returns a dict with keys:
      - sip_password
      - sip_domain
      - outbound_proxy
      - user_name
      - authorization_id
      - shared_line (if available)
    """
    sip_accounts = provision_data.get("sip_accounts", [])
    if not sip_accounts:
        return {}
    sip_account = sip_accounts[0]  # Use the first account
    return {
        "sip_password": sip_account.get("password", ""),
        "sip_domain": sip_account.get("sip_domain", ""),
        "outbound_proxy": sip_account.get("outbound_proxy", ""),
        "user_name": sip_account.get("user_name", ""),
        "authorization_id": sip_account.get("authorization_id", ""),
        "shared_line": sip_account.get("shared_line", {}),
    }


def strip_port(value: str) -> str:
    """
    Remove any port from the given value.
    E.g., "7008961376.zoom.us:5091" becomes "7008961376.zoom.us"
    """
    if not value:
        return ""
    return value.partition(":")[0]


def format_dep_name(display_name: str) -> str:
    """
    Format the department name from the display name.

    Expected pattern: "<extension> <dept>-W"
    For example, "439 BKY_MGR-W" becomes "bky_mgr_439".

    The function extracts the digits at the beginning as the extension,
    and the remaining text (before "-W") as the department name.
    It then removes spaces and hyphens from the department name, lowercases it,
    and appends the extension at the end, separated by an underscore.

    If the display name doesn't match the expected pattern, it falls back to
    simply removing spaces and hyphens and lowercasing.
    """
    display_name = display_name.strip()
    pattern = r"^(?P<ext>\d+)\s+(?P<dept>.+)-W$"
    m = re.match(pattern, display_name, re.IGNORECASE)
    if m:
        ext = m.group("ext")
        dept = m.group("dept")
        # Remove spaces and hyphens and lowercase
        dept_clean = dept.replace(" ", "").replace("-", "").lower()
        return f"{dept_clean}_{ext}"
    else:
        # Fallback: remove spaces and hyphens, lowercase the whole string
        return display_name.replace(" ", "").replace("-", "").lower()


def filter_devices_by_number(devices: list, prefix: str) -> list:
    """
    Filter the devices list to include only those whose "number" (last 3 digits of the extension number)
    starts with the given prefix.
    """
    filtered = []
    for device in devices:
        ext_number_full = str(device.get("assignee", {}).get("extension_number", ""))
        if ext_number_full:
            last3 = ext_number_full[-3:]
            if last3.startswith(prefix):
                filtered.append(device)
    return filtered


def dept_name_formatter(display_name: str) -> str:
    """
    Format the department name by converting it to lowercase and removing a trailing "-w"
    (case-insensitive). For example, "COSMETICS-W" becomes "cosmetics".
    """
    if not display_name:
        return ""
    display_name = display_name.lower().strip()
    if display_name.endswith("-w"):
        display_name = display_name[:-2].strip()
    return display_name


def format_site_name(site_name: str) -> str:
    """
    Extract the first group of digits from the site name and format it as a 5-digit number with leading zeros.
    For example, "CORP 195" becomes "00195". If no digits are found, return the original site name.
    """

    m = re.search(r"\d+", site_name)
    if m:
        number = int(m.group(0))
        return f"{number:05d}"
    return site_name


def lookup_dep_name(ext_number_last3) -> str:
    """
    Lookup the department name based on the number.
    """
    # Check if the last 3 digits of the extension number are in the department names dictionary
    # If found, return the corresponding department name
    # Otherwise, return an empty string

    dep_names = {
            "381": 'estore_381',
            "400": 'tsl_400',
            "401": 'tsl_401',
            "402": 'tsl_402',
            "403": 'tsl_403',
            "404": 'tsl_404',
            "405": 'tsl_405',
            "406": 'mic_406',
            "407": 'mic_407',
            "408": 'mic_408',
            "409": 'mic_409',
            "410": 'tsl_410',
            "418": 'receiving',
            "419": 'cft_419',
            "420": 'cft_420',
            "421": 'market',
            "425": 'kosher_425',
            "428": 'seafood',
            "429": 'market_manager',
            "430": 'bakery',
            "431": 'panaderia',
            "439": 'bakery_manager',
            "441": 'beauty',
            "444": 'drug_store',
            "445": 'sous_chef',
            "446": 'gas',
            "448": 'gm_manager',
            "449": 'drug_store_manager',
            "450": 'tx_backyard',
            "455": 'pharmacy',
            "458": 'catering',
            "460": 'deli',
            "461": 'cremeria',
            "462": 'true_tx_bbq',
            "463": 'foh_mgr',
            "464": 'cafe_manager',
            "465": 'executive_chef',
            "469": 'deli_manager',
            "472": 'beer_wine',
            "473": 'bulk_foods',
            "474": 'healthy_living',
            "475": 'grocery_475',
            "476": 'grocery_476',
            "477": 'grocery_manager_477',
            "478": 'estore_478',
            "479": 'grocery_manager_479',
            "481": 'career_coach',
            "482": 'shelf_edge',
            "483": 'maintenance_483',
            "484": 'maintenance_484',
            "485": 'service_485',
            "486": 'service_486',
            "488": 'service_manager_488',
            "489": 'service_manager_489',
            "490": 'produce',
            "491": 'aguas_frescas',
            "494": 'showtime',
            "495": 'foodie_495',
            "496": 'customer_champion',
            "497": 'connections',
            "498": 'blooms',
            "499": 'produce_manager',
            "857": 'cstore_857',
            "858": 'cstore_858',
            "859": 'cstore_859'
        }

    if ext_number_last3 in dep_names:
        return dep_names[ext_number_last3]
    return f"{ext_number_last3} (Not found - Unknown Department)"

def lookup_site_info(formatted_site_number: str) -> str:
    """Lookup the site info in the site_info_dict.json file, based on the last three digits of the site name, and return the full site name.

    Args:
        formatted_site_name (str): _description_

    Returns:
        str: _description_
    """
    # Load the site info from the JSON file
    site_info_dict = json.load(open("site_info_dict.json"))
    # Extract the last three digits from the formatted site name
    last_three_digits = formatted_site_number[-3:]

    full_site_name = site_info_dict.get(last_three_digits, "")
    if not full_site_name:
        # If not found, return the formatted site name
        return f'{formatted_site_number} (Not found - Unknown Site)'
    return full_site_name

def build_csv_row(device: dict, client) -> dict:
    """
    Build a CSV row (a dict) containing all required 45 columns.
    For columns not provided by the API, default empty strings are used.
    """
    # Use process_device_type_resp to determine device type
    device_type, _ = process_device_type_resp(device)
    if device_type == "other":
        # For "other" devices, ensure full details (including provision data) are retrieved
        device = client.phone_devices.get(device["id"])

        # Format the site name
    raw_site_name = device.get("site", {}).get("name", "")
    formatted_site_number = format_site_name(raw_site_name)

    # Get SIP credentials from the provision data
    provision = device.get("provision", {})
    sip_details = get_sip_account_details(provision)

    def safe_str(val):
        try:
            if isinstance(val, float):
                return "{:.0f}".format(val)
            return str(val)
        except Exception:
            return ""

    sip_userid = safe_str(sip_details.get("authorization_id", ""))
    sip_sipid = safe_str(sip_details.get("user_name", ""))
    sip_password = safe_str(sip_details.get("sip_password", ""))

    # Get the last 3 digits of the assignee's extension number
    ext_number_full = str(device.get("assignee", {}).get("extension_number", ""))
    ext_number_last3 = ext_number_full[-3:] if ext_number_full else ""

    # disp_name = device.get("display_name", "")
    dep_name = lookup_dep_name(ext_number_last3)

    # Lookup the full site name based on the formatted site name
    full_site_name = lookup_site_info(formatted_site_number)

    pbx_name = f"ST-{formatted_site_number}-Zoom"

    row = {
        "site_name": formatted_site_number,  # 00195
        "site_info": full_site_name,  # Matches to List based on Store XYZ Number
        "site_multi": "TRUE",
        "dep_name": dep_name,  # Matches via Departement Match list
        "dep_info": full_site_name,  # Same Value as site_info
        "dep_auto": "TRUE",
        "dep_hidden": "FALSE",
        "dep_reserved": "FALSE",
        "dep_threshold": "",
        "dep_role": "",
        "dep_role_desc": "",
        "dep_code": "",
        "number": ext_number_last3,
        "ext_name": ext_number_last3,
        "ext_info": device.get("display_name", ""),
        "second_pbx_params": "",
        "reserved_uid": "",
        "pbx_name": pbx_name,  # ST-000XYZ-Zoom
        "profile_type": "Zoom",
        "sip_remhost": strip_port(sip_details.get("outbound_proxy", "")),
        "sip_sipid": sip_sipid,
        "sip_userid": sip_userid,
        "sip_mac": device.get("mac_address", ""),
        "sip_userpass": sip_password,
        "site_config": "HEB-Zoom",
        "dep_config": "HEB-Zoom",
        "ext_config": "",  #
        "sip_pbx_logo": "",
        "sip_device_type": "",
        "sip_transport": "TLS",
        "sip_remport": "5091",
        "sip_remhost2": "",
        "sip_remhost3": "",
        "sip_localport": "",
        "sip_realm": strip_port(sip_details.get("sip_domain", "")),
        "sip_vmnum": "",
        "sip_parknum": "*6",
        "sip_confnum": "",
        "sip_http_remhost": "",
        "sip_srtp": "TRUE",
        "sip_outboundproxy": "",
        "sip_linenumber": "",
        "sip_lineaddress": "",
        "sip_conferenceid": "",
        "sip_conferenceuri": "",
    }
    return row


def build_csv_rows(devices: list, client) -> list:
    """
    Build a list of CSV rows from device API responses.
    """
    rows = []
    for device in devices:
        device_type, _ = process_device_type_resp(device)
        if device_type == "other":
            rows.append(build_csv_row(device, client))
    return rows


def filter_devices_by_site(devices: list, site_name_filter: str) -> list:
    """
    Filter the device list to include only those whose site name contains the given site_name_filter (case-insensitive).
    """
    if not site_name_filter:
        return devices
    filtered = []
    for device in devices:
        site_name = device.get("site", {}).get("name", "")
        if site_name_filter.lower() in site_name.lower():
            filtered.append(device)
    return filtered


def filter_devices_by_display_name(devices: list, suffix: str) -> list:
    """
    Filter the devices list to include only those whose display_name ends with the given suffix.
    """
    return [
        device
        for device in devices
        if device.get("display_name", "").strip().endswith(suffix)
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Extract third-party SIP credentials for Zoom devices into CSV format."
    )
    parser.add_argument(
        "--site", required=True, help="Site name to filter devices (e.g., 'Main Site')"
    )
    parser.add_argument(
        "--site-list",
        default="site_list.xlsx",
        help="Path to the Excel file containing site names (default: site_list.xlsx)",
    )
    parser.add_argument(
        "--output",
        default="sip_credentials.csv",
        help="Output CSV file name (default: sip_credentials.csv)",
    )
    args = parser.parse_args()

    # Generate a S2S token using environment variables
    token = get_new_s2s_token()
    if not token:
        logger.error("Failed to generate S2S token.")
        return
    logger.info("Using S2S token: %s", token[:10] + "..." if token else "None")

    # Initialize the Zoom API client with the S2S token
    client = zsc(token)

    # Retrieve devices of type "other"
    devices = client.phone_devices.list(type_filter="other")

    # Filter devices by the given site name
    devices = filter_devices_by_site(devices, args.site)
    if not devices:
        logger.info("No devices found for site '%s'.", args.site)
        return
    
    
    # Further filter devices to only those whose display_name ends with "-W"
    devices = filter_devices_by_display_name(devices, "-W")
    logger.info("Found %d Zebra devices on Zoom for site '%s' - prepping to write to Zebra CSV", len(devices), args.site)
    if not devices:
        logger.info(
            "WARNING: No devices found for site '%s'. Validate Zoom Site Name and 3rd party devices built before proceeding", args.site
        )
        return

    # Build CSV rows (only for devices of type "other")
    rows = build_csv_rows(devices, client)
    if not rows:
        logger.info("No SIP credentials found for site '%s'.", args.site)
        return

    # Define CSV column order (45 columns)
    fieldnames = [
        "site_name",
        "site_info",
        "site_multi",
        "dep_name",
        "dep_info",
        "dep_auto",
        "dep_hidden",
        "dep_reserved",
        "dep_threshold",
        "dep_role",
        "dep_role_desc",
        "dep_code",
        "number",
        "ext_name",
        "ext_info",
        "second_pbx_params",
        "reserved_uid",
        "pbx_name",
        "profile_type",
        "sip_remhost",
        "sip_sipid",
        "sip_userid",
        "sip_mac",
        "sip_userpass",
        "site_config",
        "dep_config",
        "ext_config",
        "sip_pbx_logo",
        "sip_device_type",
        "sip_transport",
        "sip_remport",
        "sip_remhost2",
        "sip_remhost3",
        "sip_localport",
        "sip_realm",
        "sip_vmnum",
        "sip_parknum",
        "sip_confnum",
        "sip_http_remhost",
        "sip_srtp",
        "sip_outboundproxy",
        "sip_linenumber",
        "sip_lineaddress",
        "sip_conferenceid",
        "sip_conferenceuri",
    ]

    # Write the rows to CSV
    try:
        with open(args.output, "w", newline="", encoding="utf-8") as csvfile:
            logger.info("Writing Zebra SIP credential CSV to %s", args.output)
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        logger.info("CSV export completed successfully: %s", args.output)
    except Exception as e:
        logger.error("Failed to write CSV: %s", e)


if __name__ == "__main__":
    main()
