# process/site.py

import pandas as pd
import re  # Add this import for regular expressions
from typing import Optional
from migrator.models import StoreData
from migrator.utils import find_excel_files
from migrator.utils import resolve_region



def extract_store_data(file_path: str) -> Optional[StoreData]:
    """
    Reads the "STORE INFORMATION" tab from the given workbook,
    extracts the CORP NUMBER and PHYSICAL ADDRESS,
    and returns a validated StoreData object.
    """
    # Extract the numeric corp number using a regular expression
    match = re.search(r'\b\d+\b', file_path.split("/")[-1])
    if not match:
        print(f"Invalid file name for corp number: {file_path}")
        return None

    corp_number = match.group(0)
    raw_corp_number = corp_number

    # If the corp number starts with "0", replace it with a 9
    if corp_number.startswith("0"):
        corp_number = "9" + corp_number[1:]

    # Check if the corp number is valid
    if not corp_number.isdigit():
        print(f"Invalid file name for corp number: {file_path}")
        return None

    try:
        # Read without a header since we use a key-value layout.
        df = pd.read_excel(file_path, sheet_name="STORE INFORMATION", header=None)
        
        physical_address = df[df[0] == "PHYSICAL ADDRESS"][1].values[0]
        region = resolve_region(raw_corp_number)
        # Return both processed and unprocessed corp numbers
        return StoreData.from_extracted(str(corp_number), str(physical_address), region=region), raw_corp_number
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None

def build(input_folder: str) -> pd.DataFrame:
    """
    Processes all input workbooks in the given folder to extract and build site data.
    Returns a DataFrame that contains the processed site data.
    """
    excel_files = find_excel_files(input_folder)
    store_list = []
    for file_path in excel_files:
        result = extract_store_data(file_path)
        if result:
            store, raw_corp_number = result
            store_list.append((store, raw_corp_number))
    # Convert the list of StoreData models to a list of dicts for DataFrame creation.
    rows = []
    
    for store, raw_corp_number in store_list:
        site_name = f"CORP {raw_corp_number} {store.region}".strip()
        rows.append({
            "Action": "CREATE",
            "Name": site_name,  # Use the unprocessed corp number for the Name
            "New Name": "",
            "Auto Receptionist": f"{site_name} - ENGLISH",  # Use unprocessed corp number
            "Site Code": store.corp_number,  # Use the processed corp number for Site Code
            "Extension Length": "4",
            "Address Line 1": store.parsed_address.address_line1,
            "Address Line 2": store.parsed_address.address_line2,
            "City": store.parsed_address.city,
            "State": store.parsed_address.state,
            "ZIP": store.parsed_address.zip_code,
            "Country": "US",
            "Transfer Site": ""
        })
    return pd.DataFrame(rows)


def write(dataframe: pd.DataFrame, writer):
    """
    Writes the site data DataFrame to a "Sites" sheet in the output workbook.
    """
    dataframe.to_excel(writer, sheet_name="Sites", index=False)