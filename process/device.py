import os
import pandas as pd
from migrator.models import StoreDevice
from migrator.utils import find_excel_files, extract_corp_info, format_full_extension

def extract_devices(file_path: str) -> list[StoreDevice]:
    try:
        df = pd.read_excel(file_path, sheet_name="Zoom Import Sheet")
        result = extract_corp_info(file_path)
        if not result:
            return []

        site, raw_corp_number = result  # Unpack the tuple
        corp_number = site.corp_number  # Processed corp number
        site_name = f"CORP {raw_corp_number} {site.region}".strip()  # Combine CORP XYZ and REGION

        devices = []

        for _, row in df.iterrows():
            raw_ext = row.get("Extension")
            if pd.isna(raw_ext):
                continue
            three_digit_extension = str(int(float(raw_ext))).zfill(3)
            extension = format_full_extension(corp_number, three_digit_extension)
            
            if not extension:
                continue
            name = str(row.get("First Name or")).strip().upper()
            device_type = str(row.get("Type") or "").strip().lower()
            raw_model = str(row.get("Phone Model") or "").strip().lower()
            is_edge_device = raw_model in {"edge-e100", "edge-e350"}
            is_analog = "analog" in device_type

            if is_edge_device:
                final_phone_brand = "Polycom"
                final_phone_model = raw_model
                if "rx" in name.lower():
                    final_template = "RX 350 - Disable BT, WIFI, Enable USB Persistence"
                else:
                    final_template = str(row.get("Phone Provision Template") or "").strip()
            elif is_analog:
                final_phone_brand = ""
                final_phone_model = "grandstream"
                final_template = ""
                device_type = "Grandstream"
            else:
                final_phone_brand = "Other"
                final_phone_model = ""
                final_template = ""
        
            # Always build assignee
            assignee = str(int(float(extension))).zfill(3)
            final_assignee = f"{corp_number}0{three_digit_extension}"
            # Only generate MAC if not edge device (treated as "other")
            
            if is_analog:
                mac_address = ""  # blank for analog devices
            elif final_phone_brand == "Other":
                mac_address = f"ffffff{corp_number}{three_digit_extension}"
            else:
                mac_address = ""  # blank for other devices
            # Build default device object
            device = StoreDevice(
                corp_number=corp_number,
                name=f"{three_digit_extension} {name}".strip(),
                site_name=site_name,  # Use the combined CORP XYZ REGION
                extension=extension,
                phone=final_phone_brand,
                type=final_phone_brand,
                phone_model=final_phone_model,
                phone_provision_template=final_template,
                device_type=device_type,
                assignee=final_assignee,
                mac_address=mac_address,
            )

            devices.append(device)

        return devices

    except Exception as e:
        print(f"❌ Error extracting devices from {file_path}: {e}")
        return []


def build(input_folder: str) -> pd.DataFrame:
    rows = []
    for file_path in find_excel_files(input_folder):
        result = extract_corp_info(file_path)
        if not result:
            continue
        site, _ = result
        site_name = f"CORP {site.corp_number} {site.region}".strip()
        for device in extract_devices(file_path):
            phone_brand = "Poly" if device.phone.strip().lower() == "poly" else device.phone
            
            rows.append({
                "Action": "IGNORE",
                "Name": device.name,
                "MAC Address": device.mac_address,
                "Site": device.site_name,  # Use device.site_name instead of local site_name
                "Type": phone_brand,
                "Model": device.phone_model,
                "Template": device.phone_provision_template,
                "Assignee": device.assignee
            })
    return pd.DataFrame(rows)

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Devices"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)