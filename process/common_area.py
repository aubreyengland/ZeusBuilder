import os
import pandas as pd
from migrator.models import StoreCommonArea
from migrator.utils import find_excel_files
from migrator.utils import extract_corp_info
from migrator.utils import format_full_extension
from migrator.utils import resolve_region

def extract_common_areas(file_path: str) -> list[StoreCommonArea]:
    try:
        df = pd.read_excel(file_path, sheet_name="Zoom Import Sheet")

        filename = os.path.basename(file_path)
        corp_number = filename.split()[1]

        # Include all rows with a valid extension
        ca_df = df[df["Extension"].apply(lambda x: pd.notna(x) and str(x).strip() != "")]

        common_areas = []
        for _, row in ca_df.iterrows():
            init_name = str(row.get("First Name or", "") or "").strip()
            raw_ext = row.get("Extension")
            if pd.isna(raw_ext):
                continue
            three_digit_extension = str(int(float(raw_ext))).zfill(3)

            # Clean up name: remove trailing extension if it exists
            name_clean = str(init_name).strip()
            if name_clean.endswith(three_digit_extension):
                name_clean = name_clean[: -len(three_digit_extension)].strip()

            # Final display name format: EXTENSION + cleaned name, uppercase
            display_name = f"{three_digit_extension} {name_clean}".strip().upper()

            ca = StoreCommonArea(
                corp_number=corp_number,
                name=display_name,
                extension=three_digit_extension,
            )
            common_areas.append(ca)

        return common_areas

    except Exception as e:
        print(f"Error extracting common areas from {file_path}: {e}")
        return []

def build(input_folder: str) -> pd.DataFrame:
    rows = []

    for file_path in find_excel_files(input_folder):
        result = extract_corp_info(file_path)
        if not result:
            continue

        site, raw_corp_number = result  # Unpack the tuple

        # Ensure raw_corp_number is zero-padded
        raw_corp_number = raw_corp_number.zfill(3)

        # Resolve the region
        region = resolve_region(raw_corp_number)
        if region == "UNKNOWN":
            print(f"Warning: Region not found for corp number {raw_corp_number}")

        site_name = f"CORP {raw_corp_number} {region}".strip()

        for ca in extract_common_areas(file_path):
            department = site_name
            if "RX" in ca.name.upper():
                department += " RX"
            elif "E-STORE" in ca.name.upper():
                department += " E-STORE"

            rows.append({
                "Action": "CREATE",
                "Name": ca.name,
                "Extension": ca.extension,
                "New Extension": "", 
                "Phone Numbers": "",
                "Site": site_name,  # Use the combination of CORP XYZ and REGION
                "Calling Plans": "US/CA Unlimited Calling Plan",
                "Caller ID": f"CORP {site.corp_number} MAIN NUMBER",
                "Timezone": "America/Chicago",
                "Address Line 1": site.parsed_address.address_line1,
                "Address Line 2": site.parsed_address.address_line2,
                "City": site.parsed_address.city,
                "State": site.parsed_address.state,
                "ZIP": site.parsed_address.zip_code,
                "Country": "US",
                "Area Code": "",
                "Department": department, 
                "Cost Center": site_name,
            })
        
        #create a update row for the common areas with "REG" or "STORE PAGE" in the name to block country code
        for ca in extract_common_areas(file_path):
            if "REG" in ca.name.upper():
            
                rows.append({
                    "Action": "UPDATE",
                    "Name": ca.name,
                    "Extension": format_full_extension(site.corp_number, ca.extension),  # write the full extension here
                    "New Extension": "", 
                    "Phone Numbers": "",
                    "Site": site_name,  # Use the combination of CORP XYZ and REGION
                    "Calling Plans": "US/CA Unlimited Calling Plan",
                    "Caller ID": f"CORP {site.corp_number} MAIN NUMBER",
                    "Timezone": "America/Chicago",
                    "Address Line 1": site.parsed_address.address_line1,
                    "Address Line 2": site.parsed_address.address_line2,
                    "City": site.parsed_address.city,
                    "State": site.parsed_address.state,
                    "ZIP": site.parsed_address.zip_code,
                    "Country": "US",
                    "Area Code": "",
                    "Department": department, 
                    "Cost Center": site_name,
                    "Block Country Code": "US",
            })
        page_row = {
            "Action": "CREATE",
            "Name": "100 STORE PAGE",
            "Extension": "100",
            "New Extension": "",
            "Phone Numbers": "",
            "Site": site_name,  # Use the combination of CORP XYZ and REGION
            "Calling Plans": "US/CA Unlimited Calling Plan",
            "Caller ID": f"CORP {site.corp_number} MAIN NUMBER",
            "Timezone": "America/Chicago",
            "Address Line 1": site.parsed_address.address_line1,
            "Address Line 2": site.parsed_address.address_line2,
            "City": site.parsed_address.city,
            "State": site.parsed_address.state,
            "ZIP": site.parsed_address.zip_code,
            "Country": "US",
            "Area Code": "",
            "Department": site_name, 
            "Cost Center": site_name,
        }
        page_block_row = {
            "Action": "UPDATE",
            "Name": "100 STORE PAGE",
            "Extension": format_full_extension(site.corp_number, "100"), 
            "New Extension": "",
            "Phone Numbers": "",
            "Site": site_name,  # Use the combination of CORP XYZ and REGION
            "Calling Plans": "US/CA Unlimited Calling Plan",
            "Caller ID": f"CORP {site.corp_number} MAIN NUMBER",
            "Timezone": "America/Chicago",
            "Address Line 1": site.parsed_address.address_line1,
            "Address Line 2": site.parsed_address.address_line2,
            "City": site.parsed_address.city,
            "State": site.parsed_address.state,
            "ZIP": site.parsed_address.zip_code,
            "Country": "US",
            "Area Code": "",
            "Department": site_name, 
            "Cost Center": site_name,
            "Block Country Code": "US",
        }
        
        rows.append(page_row)
        rows.append(page_block_row)
        prompt_rec_row = {
            "Action": "CREATE",
            "Name": "595 PROMPT RECORDER",
            "Extension": "595",
            "New Extension": "",
            "Phone Numbers": "",
            "Site": site_name,  # Use the combination of CORP XYZ and REGION
            "Calling Plans": "US/CA Unlimited Calling Plan",
            "Caller ID": f"CORP {site.corp_number} MAIN NUMBER",
            "Timezone": "America/Chicago",
            "Address Line 1": site.parsed_address.address_line1,
            "Address Line 2": site.parsed_address.address_line2,
            "City": site.parsed_address.city,
            "State": site.parsed_address.state,
            "ZIP": site.parsed_address.zip_code,
            "Country": "US",
            "Area Code": "",
            "Department": site_name, 
            "Cost Center": site_name,
        }
        rows.append(prompt_rec_row)
    

    df = pd.DataFrame(rows)
    df["Extension"] = df["Extension"].astype(str)

    return df

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Common Areas"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)