import re

# Extension Length used for validation, value and notes
EXT_MIN = 2
EXT_MAX = 10

OUTGOING_PERMISSION = (
    "ALLOW",
    "BLOCK",
    "AUTH_CODE",
    "TRANSFER_NUMBER_1",
    "TRANSFER_NUMBER_2",
    "TRANSFER_NUMBER_3",
)

PREFERRED_LANGUAGES = [
    "ar_SA",
    "id_ID",
    "cs_CZ",
    "da_DK",
    "de_DE",
    "en_US",
    "en_AU",
    "en_GB",
    "en_CA",
    "es_MX",
    "es_ES",
    "fr_CA",
    "fr_FR",
    "it_IT",
    "hu_HU",
    "nb_NO",
    "pl_PL",
    "pt_BR",
    "pt_PT",
    "ru_RU",
    "ro_RO",
    "es_CO",
    "nl_NL",
    "sv_SE",
    "tr_TR",
    "ko_KR",
    "ja_JP",
    "zh_CN",
    "zh_TW",
]

ANNOUNCEMENT_LANGUAGES = [
    ("ar_ae", "Arabic (United Arab Emirates)"),
    ("bg_bg", "Bulgarian (Bulgaria)"),
    ("ca_es", "Catalan (Spain)"),
    ("cs_cz", "Czech (Czech Republic)"),
    ("da_dk", "Danish (Denmark)"),
    ("de_de", "German"),
    ("en_au", "English (Australia)"),
    ("en_gb", "English (United Kingdom)"),
    ("en_nz", "English (New Zealand)"),
    ("en_us", "English"),
    ("es_co", "Spanish (Colombia)"),
    ("es_es", "Spanish (Spain)"),
    ("fi_fi", "Finnish (Finland)"),
    ("fr_ca", "Canadian French(Canada)"),
    ("fr_fr", "French"),
    ("hr_hr", "Croatian (Croatia)"),
    ("hu_hu", "Hungarian (Hungary)"),
    ("id_id", "Indonesian (Indonesia)"),
    ("it_it", "Italian"),
    ("iw_il", "Hebrew (Israel)"),
    ("ja_jp", "Japanese"),
    ("ko_kr", "Korean (South Korea)"),
    ("nb_no", "Bokmal Norwegian(Norway)"),
    ("nl_nl", "Dutch (Netherlands)"),
    ("pl_pl", "Polish (Poland)"),
    ("pt_br", "Portuguese (Brazilian)"),
    ("pt_pt", "Portuguese"),
    ("ro_ro", "Romanian (Romania)"),
    ("ru_ru", "Russian (Russia)"),
    ("sr_rs", "Serbian Cyrillic (Serbia)"),
    ("sv_se", "Swedish (Sweden)"),
    ("th_th", "Thai (Thailand)"),
    ("tr_tr", "Turkish (Turkey)"),
    ("vi_vn", "Vietnamese (Vietnam)"),
    ("zh_cn", "Chinese (China)"),
    ("zh_tw", "Chinese (Taiwan)"),
]


ASSIGNABLE_WEBEX_LICENSE_TYPES = (
    "Webex Calling - Standard",
    "Webex Calling - Professional",
    "Webex Calling - Attendant Console",
    "Webex Calling - Workspaces",
    "Webex Calling - Hot desk only",
    "Customer Experience - Essential",
    "Unified Communication Manager (UCM)",
    "Call on Webex (1:1 call, non-PSTN)",
)

WEBEX_CALLING_LICENSE_TYPES = (
    "Webex Calling - Standard",
    "Webex Calling - Professional",
    "Webex Calling - Attendant Console",
    "Webex Calling - Workspaces",
    "Webex Calling - Hot desk only",
    "Customer Experience - Essential",
)


def validate_phone_numbers(v):
    """
    Validate phone_numbers
    Value is one or more comma-separated E.164 numbers.
    Validator removes any extra characters inserted by excel
    """
    e164_rgx = re.compile(r"(\+[1-9]\d{1,14})")
    validated_numbers = []
    if not v:
        return v
    for item in re.split(r"\s*[,|;]\s*", v):
        if m := e164_rgx.search(item):
            validated_numbers.append(m.group(1))
        else:
            raise ValueError(f"Phone Number '{item}' is not valid in +E.164 format")
    return ",".join(validated_numbers)


def validate_e164_phone_number(value):
    """
    Convert the value to a valid E.164 number if possible or raise a ValueError.

    The value is expected to be a valid +E.164 number with or without the plus.

    If the value is falsey, return it unmodified to let upstream validation
    to determine if an empty value is allowed

    If the value does not include the plus but is valid otherwise, add the plus.
    """
    e164_rgx = re.compile(r"(^\+?[1-9]\d{1,14})$")
    if not value:
        return value

    number = re.sub(r"[^+\d]+", "", str(value))

    if not e164_rgx.match(number):
        raise ValueError(f"Phone Number '{value}' is not valid E.164 format")

    if not number.startswith("+"):
        number = f"+{number}"

    return number


def validate_extension(v):
    """
    Validate an extension length.
    """
    if not v:
        return v

    if v.lower() == "remove":
        return v

    pattern = rf"^\d{{{EXT_MIN},{EXT_MAX}}}$"
    if not re.match(pattern, v):
        raise ValueError(f"Must be between {EXT_MIN}-{EXT_MAX} digits in length")

    return v
