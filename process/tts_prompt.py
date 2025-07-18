import pandas as pd
import os
import re
from migrator.utils import find_excel_files

DEFAULT_ENGLISH_TTS_PROMPT = [
    "{GREETING}",
    "We are located at {LOCATION}",
    "{STORE_HOURS}",
    "If you would like to reach our pharmacy, please call: {RX_NUMBER}.",
    "Our menu options have changed.",
    "{ZOOM_MENU}"
]

DEFAULT_SPANISH_TTS_PROMPT = [
    "Gracias por llamar a H-E-B.",
    "Estamos ubicados en la esquina de {LOCATION}",
    "{STORE_HOURS}",
    "Para comunicarse con la farmacia, por favor llame al {RX_NUMBER}.",
    "Nuestras opciones de menú han cambiado.",
    "{ZOOM_MENU}"
]



def extract_call_flow_data(file_path: str) -> dict:
    cf = pd.read_excel(file_path, sheet_name="CALL FLOW", header=None)
    key_col = cf.columns[0]
    val_col = cf.columns[1]

    get_value = lambda key: cf.loc[cf[key_col].str.upper() == key, val_col].iloc[0] if not cf.loc[cf[key_col].str.upper() == key].empty else ""

    greeting = str(get_value("GREETING-")).strip()
    location = str(get_value("LOCATION")).strip()

    if location.lower().startswith("located at"):
        location = location[10:].strip()
    location_spanish = location.replace(" and ", " y ")

    store_hours = str(get_value("STORE HOURS")).strip()
    rx_number = extract_rx_phone_number(cf)

    # Generate both menus
    zoom_menu_en = extract_zoom_menu(cf, language="en")
    zoom_menu_es = extract_zoom_menu(cf, language="es")

    return {
        "greeting": greeting,
        "location": location,
        "location_spanish": location_spanish,
        "rx_number": rx_number,
        "store_hours": store_hours,
        "zoom_menu_en": zoom_menu_en,
        "zoom_menu_es": zoom_menu_es,
    }
    
def extract_rx_phone_number(cf) -> str:
    key_col = cf.columns[0]
    val_col = cf.columns[1]
    get_value = lambda key: cf.loc[cf[key_col].str.upper() == key, val_col].iloc[0] if not cf.loc[cf[key_col].str.upper() == key].empty else ""

    rx_value = str(get_value("RX NUMBER")).strip()
    if not rx_value:
        return ""

    match = re.search(r'(\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})', rx_value)
    return match.group(0) if match else rx_value


def extract_zoom_menu(cf, language="en") -> str:

    try:
        raw_menu_cell = cf.iat[7, 2]

        # Check if it is NaN using pandas
        if pd.isna(raw_menu_cell):
            return ""

        raw_menu = str(raw_menu_cell)
        if not raw_menu.strip():
            return ""

        lines = raw_menu.strip().split("\n")
        parsed_lines = []

                # Mapping for Spanish translations
        spanish_map = {
            "Curbside": "Curbside",  # You can adjust if needed
            "Bakery": "Panadería",
            "Floral": "Florería",
            "Deli": "Delicatessen",
            "Grocery": "Abarrotes",
            "Meat Market": "Carnicería",
            "Produce": "Frutas y Verduras",
            "Seafood": "Mariscos",
            "Customer Service": "Servicio al Cliente",
            "Drug": "Farmacia",
            "Market": "Carnicería",  # If "Market" meant meat market
        }

        for line in lines:
            match = re.match(r"\s*(\d+)\.\s*(.+?)\s*\((\d+)\)", line)
            if match:
                num, desc, _ = match.groups()
                desc_clean = desc.replace("Transfer to", "").replace("Transfer To", "").replace("HG", "").strip()
                                
                if "Service Shared line" in desc:
                    desc_clean = "Customer Service"
                
                if language == "es" and desc_clean in spanish_map:
                    desc_clean_translated = spanish_map[desc_clean]
                else:
                    desc_clean_translated = desc_clean

                parsed_lines.append(f"Para {desc_clean_translated}, presione {num}." if language == "es" else f"For {desc_clean_translated}, press {num}.")
            else:
                if "Spanish" in line and language != "es":
                    parsed_lines.append("To listen to this menu in Spanish, press 1.")

        return "\n\n".join(parsed_lines)
    except Exception as e:
        return f"[Error extracting menu: {e}]"


def create_tts_prompt(flows: dict, language: str) -> str:
    if language.lower() == "en":
        template = DEFAULT_ENGLISH_TTS_PROMPT
        location_value = flows["location"]
        zoom_menu_value = flows["zoom_menu_en"]
        store_hours_value = flows["store_hours"]
    else:
        template = DEFAULT_SPANISH_TTS_PROMPT
        location_value = flows.get("location_spanish", flows["location"])
        zoom_menu_value = flows["zoom_menu_es"]
        store_hours_value = flows["store_hours"]

        # Translate store hours if present
        if store_hours_value and store_hours_value.lower() != "nan":
            if "7 AM to 10 PM" in store_hours_value:
                store_hours_value = "Nuestro horario de tienda es de 7 de la mañana a 10 de la noche — todos los días."
            elif "6 AM to 11 PM" in store_hours_value:
                store_hours_value = "Nuestro horario de tienda es de 6 de la mañana a 11 de la noche — todos los días."
            else:
                # Default fallback conversion
                store_hours_value = "Nuestro horario de tienda es de 6 de la mañana a 11 de la noche — todos los días."
    prompt = []
    
    for line in template:
        # Skip line if it contains RX_NUMBER and there's no value
        if "{RX_NUMBER}" in line and (not flows["rx_number"] or flows["rx_number"].lower() == "nan"):
            continue

        # Skip line if it contains STORE_HOURS and there's no value
        if "{STORE_HOURS}" in line and (not flows["store_hours"] or flows["store_hours"].lower() == "nan"):
            continue
        
    
        line = line.replace("{GREETING}", flows["greeting"])
        line = line.replace("{LOCATION}", location_value)
        line = line.replace("{RX_NUMBER}", flows["rx_number"])
        line = line.replace("{ZOOM_MENU}", zoom_menu_value)
        line = line.replace("{STORE_HOURS}", store_hours_value)
        prompt.append(line)

    return "\n\n".join(prompt)


def generate_tts_files(input_source: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    files = [input_source] if os.path.isfile(input_source) else find_excel_files(input_source)

    for file_path in files:
        raw_corp = os.path.basename(file_path).split()[1]
        flows = extract_call_flow_data(file_path)

        # English
        txt_en = create_tts_prompt(flows, language="en")
        en_path = os.path.join(output_dir, f"CORP {raw_corp}-ENGLISH.txt")
        with open(en_path, "w", encoding="utf-8") as f:
            f.write(txt_en)

        # Spanish
        txt_es = create_tts_prompt(flows, language="es")
        es_path = os.path.join(output_dir, f"CORP {raw_corp}-SPANISH.txt")
        with open(es_path, "w", encoding="utf-8") as f:
            f.write(txt_es)