#!/usr/bin/env python3
import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import argparse
from zeus.zoom import zoom_simple as zsc
from zeus.zoom.services.shared import ZoomLookup



# -------- Load .env --------
load_dotenv()

CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")

# Mapping from abbreviation to Zoom type
TYPE_MAP = {
    "AR": "auto_receptionist",
    "CA": "common_area",
    "CQ": "call_queue"
}

def get_s2s_access_token(client_id, client_secret, account_id):
    url = "https://zoom.us/oauth/token"
    params = {
        "grant_type": "account_credentials",
        "account_id": account_id
    }
    response = requests.post(url, params=params, auth=HTTPBasicAuth(client_id, client_secret))
    if response.ok:
        access_token = response.json().get("access_token")
        print("✅ Got Zoom access token.")
        return access_token
    else:
        raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")

def assign_number(phone_number, ext_type_abbrev, ext_assignment, site_id, access_token, lookup_instance):
    target_type = TYPE_MAP.get(ext_type_abbrev.upper())
    if not target_type:
        print(f"❌ Unknown Extension Type abbreviation: {ext_type_abbrev} for {phone_number}")
        return False

    phone_obj = lookup_instance.phone_number(phone_number)
    if not phone_obj:
        print(f"⚠️ Phone number {phone_number} not found in Zoom.")
        return False

    if target_type == "auto_receptionist":
        obj = lookup_instance.auto_receptionist(ext_assignment, site_id)
        if not obj:
            print(f"⚠️ Auto Receptionist {ext_assignment} not found in site {site_id}.")
            return False
        svc = zsc.ZoomSimpleClient(access_token)
        try:
            svc.phone_auto_receptionists.assign_phone_numbers(obj["id"], {"phone_numbers": [{"id": phone_obj["id"]}]})
        except zsc.ZoomServerFault as e:
            if "already been assigned" in str(e).lower():
                print(f"⚠️ Phone number {phone_number} is already assigned to Auto Receptionist {ext_assignment}.")
                return False
            else:
                raise e
    elif target_type == "common_area":
        obj = lookup_instance.common_area(ext_assignment, site_id)
        if not obj:
            print(f"⚠️ Common Area {ext_assignment} not found in site {site_id}.")
            return False
        svc = zsc.ZoomSimpleClient(access_token)
        try:
            svc.phone_common_areas.assign_phone_numbers(obj["id"], {"phone_numbers": [{"id": phone_obj["id"]}]})
        except zsc.ZoomServerFault as e:
            if "already been assigned" in str(e).lower():
                print(f"⚠️ Phone number {phone_number} is already assigned to Common Area {ext_assignment}.")
                return False
            else:
                raise e
    elif target_type == "call_queue":
        obj = lookup_instance.call_queue(ext_assignment, site_id)
        if not obj:
            print(f"⚠️ Call Queue {ext_assignment} not found in site {site_id}.")
            return False
        svc = zsc.ZoomSimpleClient(access_token)
        try:
            svc.phone_call_queues.assign_phone_numbers(obj["id"], {"phone_numbers": [{"id": phone_obj["id"]}]})
        except zsc.ZoomServerFault as e:
            if "already been assigned" in str(e).lower():
                print(f"⚠️ Phone number {phone_number} is already assigned to Call Queue {ext_assignment}.")
                return False
            else:
                raise e
    else:
        print(f"❌ Unsupported Extension Type: {ext_type_abbrev} for {phone_number}")
        return False

    print(f"✅ Assigned {phone_number} to {ext_type_abbrev} ({ext_assignment}) at site '{obj['site']['name']}'")
    return True

def read_excel(file_path):
    df = pd.read_excel(file_path)
    expected_cols = {'Phone Number', 'Extension Type', 'Extension Assignment', 'Site Name', 'UPDATE'}
    if not expected_cols.issubset(df.columns):
        raise ValueError(f"Excel file must contain columns: {expected_cols}")
    return df


def main():


    if not CLIENT_ID or not CLIENT_SECRET or not ACCOUNT_ID:
        raise Exception("Missing Zoom credentials in .env file.")

    parser = argparse.ArgumentParser(description="Assign Zoom phone numbers from Excel file.")
    parser.add_argument("--input", required=True, help="Path to Excel file containing phone assignments")
    args = parser.parse_args()
    excel_file = args.input

    access_token = get_s2s_access_token(CLIENT_ID, CLIENT_SECRET, ACCOUNT_ID)
    svc = zsc.ZoomSimpleClient(access_token)
    lookup_instance = ZoomLookup(svc)
    df = read_excel(excel_file)

    for _, row in df.iterrows():
        phone_number = str(row["Phone Number"]).strip()
        if phone_number.endswith(".0"):
            phone_number = phone_number[:-2]
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
        ext_type_abbrev = str(row["Extension Type"]).strip()
        ext_assignment = str(row["Extension Assignment"]).strip()
        site_name = str(row["Site Name"]).strip()

        update_flag = str(row["UPDATE"]).strip().lower()
        if update_flag != "true":
            print(f"⚠️ Skipping row — UPDATE flag is not True for Extension {ext_assignment}.")
            continue

        if not phone_number or not ext_type_abbrev or not ext_assignment or not site_name:
            print(f"⚠️ Skipping row — missing required values. Phone: '{phone_number}', Type: '{ext_type_abbrev}', Assignment: '{ext_assignment}', Site: '{site_name}'")
            continue

        site_obj = lookup_instance.site(site_name)
        if not site_obj:
            print(f"⚠️ Site '{site_name}' not found, skipping assignment for phone {phone_number}.")
            continue
        site_id = site_obj["id"]

        assign_number(phone_number, ext_type_abbrev, ext_assignment, site_id, access_token, lookup_instance)
        time.sleep(1.0)  # Avoid API rate limits

if __name__ == "__main__":
    main()