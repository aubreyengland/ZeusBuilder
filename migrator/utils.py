import os
import pandas as pd
from migrator.models import StoreData
import json
_rx_map_cache = None
def extract_corp_info(file_path: str) -> tuple[StoreData, str] | None:
    """
    Extracts CORP NUMBER and PHYSICAL ADDRESS from the 'STORE INFORMATION' tab
    and returns a validated StoreData model along with the unprocessed corp number.
    """
    try:
        # Read the Excel sheet
        df = pd.read_excel(file_path, sheet_name="STORE INFORMATION", header=None)
        
        # Extract the raw corp number
        corp_rows = df[df[0] == "CORP NUMBER"]
        if corp_rows.empty or pd.isna(corp_rows.iloc[0, 1]):
            raise ValueError(f"Missing or empty CORP NUMBER in 'STORE INFORMATION' sheet of {file_path}")
        raw_corp_number = str(corp_rows.iloc[0, 1])

        # Process the corp number (e.g., replace leading '0' with '9')
        corp_number = raw_corp_number.zfill(3)  # Ensure it's 3 digits
        if corp_number.startswith("0"):
            corp_number = "9" + corp_number[1:]

        # Resolve the region
        region = resolve_region(raw_corp_number)

        # Extract the physical address
        address_rows = df[df[0] == "PHYSICAL ADDRESS"]
        if address_rows.empty or pd.isna(address_rows.iloc[0, 1]):
            raise ValueError(f"Missing or empty PHYSICAL ADDRESS in 'STORE INFORMATION' sheet of {file_path}")
        physical_address = str(address_rows.iloc[0, 1])

        # Return both processed and unprocessed corp numbers
        return StoreData.from_extracted(str(corp_number), str(physical_address), region=region), raw_corp_number
    except Exception as e:
        print(f"Error reading STORE INFORMATION from {file_path}: {e}")
        return None

REGION_MAP_PATH = "migrator/regions.json"    

def load_region_map() -> dict:
    try:
        with open(REGION_MAP_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Region map file not found at {REGION_MAP_PATH}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Failed to parse region map JSON: {e}")
        return {}

_region_by_corp = load_region_map()

def resolve_region(corp_number: str, override: str | None = None) -> str | None:
    """
    Returns the region for a given corp number.
    Override takes precedence over fallback mapping.
    """
    if override:
        return override.strip().upper()
    return _region_by_corp.get(corp_number.zfill(3))

def normalize_extension(value) -> str:
    """Converts a numeric or string extension to a clean 3-digit string. Returns '' if invalid."""
    try:
        if pd.isna(value):
            return ""
        return str(int(float(value))).zfill(3)
    except (ValueError, TypeError):
        return ""

def format_full_extension(corp_number: str, extension: str) -> str:
    """
    Formats the full 7-digit extension by combining corp code and 3-digit extension.

    - If corp starts with '0': replace '0' with '9', then append '0' and 3-digit extension (e.g., 063 + 123 → 9630123)
    - Otherwise: append '0' and 3-digit extension (e.g., 567 + 123 → 5670123)
    """
    ext = str(extension).strip()
    if ext.isdigit():
        ext = ext.zfill(3)
    return f"{corp_number}0{ext}"

def find_excel_files(input_folder: str) -> list[str]:
   """
   Finds all discovery docs in the input folder that match the expected naming pattern.
   Expected format: 'CORP XYZ DISCOVERY DOC.xlsx'
   """
   try:
       return [
           os.path.join(input_folder, f)
           for f in os.listdir(input_folder)
           if f.startswith("CORP ") and f.endswith("DISCOVERY DOC.xlsx")
       ]
   except FileNotFoundError:
       print(f"❌ Input folder not found: {input_folder}")
       return []
   except NotADirectoryError:
       print(f"❌ '{input_folder}' is not a directory")
       return []

ALERT_EMAILS = ["telecom2@heb.com", "ZoomPhoneStores@heb.com"]
    
LINE_KEY_SETS = {
    "RX": [
        {"key_number": "2", "type": "call_park", "number": "*804", "alias": ""},
        {"key_number": "3", "type": "call_park", "number": "*805", "alias": ""},
        {"key_number": "4", "type": "call_park", "number": "*806", "alias": ""},
        {"key_number": "4", "type": "call_park", "number": "*806", "alias": ""},
        {"key_number": "5","type": "speed_dial", "number": "18668136769", "alias": "ROC"},
        {"key_number": "6","type": "speed_dial", "number": "15159691998", "alias": "RX VM"},
        {"key_number": "7","type": "speed_dial", "number": "2109362999", "alias": "HEB CA"},
        {"key_number": "8","type": "speed_dial", "number": "100", "alias": "STORE PAGE"},
    ],
    "BUSCTR+BOOKKEEPING": [
        {"key_number": "2", "type": "call_park", "number": "*801", "alias": ""},
        {"key_number": "3", "type": "call_park", "number": "*802", "alias": ""},
        {"key_number": "4", "type": "call_park", "number": "*803", "alias": ""},
        {"key_number": "5", "type": "line", "number": "{corp_ext}0863", "alias": ""},
        {"key_number": "6", "type": "speed_dial", "number": "100", "alias": "STORE PAGE"},
        {"key_number": "7", "type": "speed_dial", "number": "678", "alias": "CURBSIDE"},
        {"key_number": "8", "type": "speed_dial", "number": "*88{corp_ext}", "alias": "NIGHT MODE"},
        {"key_number": "9", "type": "speed_dial", "number": "600", "alias": "MIC COVERAGE"},
        {"key_number": "10", "type": "speed_dial", "number": "608", "alias": "CCMs"},
        {"key_number": "11", "type": "speed_dial", "number": "683", "alias": "MAINT"},
        {"key_number": "12", "type": "speed_dial", "number": "607", "alias": "GROCERY"},
        {"key_number": "13", "type": "speed_dial", "number": "671", "alias": "DAIRY"},
        {"key_number": "14", "type": "speed_dial", "number": "603", "alias": "BAKERY"},
        {"key_number": "15", "type": "speed_dial", "number": "604", "alias": "DRUGSTORE"},
        {"key_number": "16", "type": "speed_dial", "number": "641", "alias": "COSMETICS"},
        {"key_number": "17", "type": "speed_dial", "number": "609", "alias": "PRODUCE"},
        {"key_number": "18", "type": "speed_dial", "number": "698", "alias": "FLORAL"},
        {"key_number": "19", "type": "speed_dial", "number": "606", "alias": "DELI"},
        {"key_number": "20", "type": "speed_dial", "number": "605", "alias": "RX"},
        {"key_number": "21", "type": "speed_dial", "number": "611", "alias": "MIC"},
        {"key_number": "22", "type": "speed_dial", "number": "614", "alias": "STORE DIRECTOR"},
        {"key_number": "23", "type": "speed_dial", "number": "615", "alias": "UNIT DIRECTOR"},
        {"key_number": "24", "type": "speed_dial", "number": "617", "alias": "ASST DIRECTOR"},
        {"key_number": "25", "type": "speed_dial", "number": "681", "alias": "ADMIN"},
        {"key_number": "26", "type": "speed_dial", "number": "686", "alias": "BOOKKEEPING"},
        {"key_number": "27", "type": "speed_dial", "number": "2109362999", "alias": "HEB CA"},
        {"key_number": "28", "type": "speed_dial", "number": "699", "alias": "O-NIGHT COVERAGE"},
    ],
    "DEFAULT": [
        {"key_number": "2", "type": "speed_dial", "number": "100", "alias": "STORE PAGE"},
        {"key_number": "3", "type": "speed_dial", "number": "678", "alias": "CURBSIDE"},
        {"key_number": "4", "type": "speed_dial", "number": "600", "alias": "MIC COVERAGE"},
        {"key_number": "5", "type": "speed_dial", "number": "608", "alias": "CCMs"},
        {"key_number": "6", "type": "speed_dial", "number": "683", "alias": "MAINT"},
        {"key_number": "7", "type": "speed_dial", "number": "607", "alias": "GROCERY"},
        {"key_number": "8", "type": "speed_dial", "number": "671", "alias": "DAIRY"},
        {"key_number": "9", "type": "speed_dial", "number": "603", "alias": "BAKERY"},
        {"key_number": "10", "type": "speed_dial", "number": "604", "alias": "DRUGSTORE"},
        {"key_number": "11", "type": "speed_dial", "number": "641", "alias": "COSMETICS"},
        {"key_number": "12", "type": "speed_dial", "number": "609", "alias": "PRODUCE"},
        {"key_number": "13", "type": "speed_dial", "number": "698", "alias": "FLORAL"},
        {"key_number": "14", "type": "speed_dial", "number": "606", "alias": "DELI"},
        {"key_number": "15", "type": "speed_dial", "number": "605", "alias": "RX"},
        {"key_number": "16", "type": "speed_dial", "number": "611", "alias": "MIC"},
        {"key_number": "17", "type": "speed_dial", "number": "614", "alias": "STORE DIRECTOR"},
        {"key_number": "18", "type": "speed_dial", "number": "615", "alias": "UNIT DIRECTOR"},
        {"key_number": "19", "type": "speed_dial", "number": "617", "alias": "ASST DIRECTOR"},
        {"key_number": "20", "type": "speed_dial", "number": "681", "alias": "ADMIN"},
        {"key_number": "21", "type": "speed_dial", "number": "686", "alias": "BOOKKEEPING"},
        {"key_number": "22", "type": "speed_dial", "number": "2109362999", "alias": "HEB CA"},
        {"key_number": "23", "type": "speed_dial", "number": "699", "alias": "O-NIGHT COVERAGE"},
    ],    
}


RX_NUMBER_MAP_FILE = "migrator/store-rx.json"

# Load the RX number mapping from a JSON file
def load_rx_number_map() -> dict:
    if not os.path.exists(RX_NUMBER_MAP_FILE):
        raise FileNotFoundError(f"RX number map file not found: {RX_NUMBER_MAP_FILE}")

    with open(RX_NUMBER_MAP_FILE, 'r') as f:
        return json.load(f)
    
def extract_rx_number(file_path: str) -> str:
    """
    Extracts the RX number from the given file path.
    The RX number is expected to be in a JSON file format.
    """
    global _rx_map_cache
    try:
        if _rx_map_cache is None:
            _rx_map_cache = load_rx_number_map()
        filename = os.path.basename(file_path)
        corp_number = filename.split()[1]
        return _rx_map_cache.get(corp_number, "")
    except Exception as e:
        print(f"Error extracting RX number from {file_path}: {e}")
        return ""