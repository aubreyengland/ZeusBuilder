import pandas as pd
import os
import re
from migrator.utils import find_excel_files

# Key action + target structure (these values match the pattern in the example)
DEFAULT_ENGLISH_TTS_PROMPT = [
    "Thank you for calling H-E-B.",
    "{LOCATION}.",
    "Our store hours are 6 AM to 11 PM — daily.",
    "If you would like to reach our pharmacy, please call: {RX_NUMBER}.",
    "Our menu options have changed.",
    "To listen to this menu in Spanish, press 1.",
    "For Curbside, press 2.",
    "For Bakery, press 3.",
    "For Floral, press 4.",
    "For Deli, press 5.",
    "For Grocery, press 6.",
    "For Meat Market, press 7.",
    "For Produce, press 8.",
    "For Seafood, press 9.",
    "For Customer Service, press 0.",
]

DEFAULT_SPANISH_TTS_PROMPT = [
    "Gracias por llamar a H-E-B.",
    "Estamos ubicados en la esquina de {LOCATION}.",
    "Nuestro horario de tienda es de 6 de la mañana a 11 de la noche — todos los días.",
    "Para comunicarse con la farmacia, por favor llame al {RX_NUMBER}.",
    "Nuestras opciones de menú han cambiado.",
    "Para Curbside, presione 2.",
    "Para Panadería, presione 3.",
    "Para Florería, presione 4.",
    "Para Delicatessen, presione 5.",
    "Para Abarrotes, presione 6.",
    "Para Carnicería, presione 7.",
    "Para Frutas y Verduras, presione 8.",
    "Para Mariscos, presione 9.",
    "Para Servicio al Cliente, presione 0.",
]


def extract_call_flow_data(file_path: str) -> dict:
    cf = pd.read_excel(file_path, sheet_name="CALL FLOW")
    key_col = cf.columns[0]
    val_col = cf.columns[1]
    get_value = lambda key: cf.loc[cf[key_col].str.upper() == key, val_col].iloc[0]
    
    return {
        "location": get_value("LOCATION"),
        "rx_number": extract_rx_phone_number(file_path),
    }
    
def extract_rx_phone_number(file_path: str) -> str:
    #Extract the phone number from the value in the RX Number key
    cf = pd.read_excel(file_path, sheet_name="CALL FLOW")
    key_col = cf.columns[0]
    val_col = cf.columns[1]
    get_value = lambda key: cf.loc[cf[key_col].str.upper() == key, val_col].iloc[0]
    rx_number = get_value("RX NUMBER")
    # Extract the phone number using regex that matches (xxx) xxx-xxxx or xxx-xxx-xxxx
    match = re.search(r'(\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})', rx_number)
    if match:
        return match.group(0)
    else:
        return rx_number.strip()

def create_tts_prompt(corp_number: str, site_name: str, flows: dict, language: str) -> str:
    if language.lower() == "en":
        template = DEFAULT_ENGLISH_TTS_PROMPT
    else:
        template = DEFAULT_SPANISH_TTS_PROMPT

    filled = []
    for line in template:
        line = line.replace("{LOCATION}", flows["location"])
        line = line.replace("{RX_NUMBER}", flows["rx_number"])
        filled.append(line)

    # Join with two newlines to preserve a blank line between each
    return "\n\n".join(filled)


def generate_tts_files(input_source: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    if os.path.isfile(input_source):
        paths = [input_source]
    else:
        # directory: filter to this CORP
        corp = os.path.basename(output_dir).split('_')[1]
        all_files = find_excel_files(input_source)
        paths = [p for p in all_files if os.path.basename(p).split()[1] == corp]
    for file_path in paths:
        # extract corp from filename, e.g. "CORP 092 ..."
        raw_corp = os.path.basename(file_path).split()[1]
        flows = extract_call_flow_data(file_path)

        # English
        txt_en = create_tts_prompt(raw_corp, f"CORP {raw_corp}", flows, language="en")
        en_path = os.path.join(output_dir, f"CORP {raw_corp}-ENGLISH.txt")
        with open(en_path, "w", encoding="utf-8") as f:
            f.write(txt_en)

        # Spanish
        txt_es = create_tts_prompt(raw_corp, f"CORP {raw_corp}", flows, language="es")
        es_path = os.path.join(output_dir, f"CORP {raw_corp}-SPANISH.txt")
        with open(es_path, "w", encoding="utf-8") as f:
            f.write(txt_es)