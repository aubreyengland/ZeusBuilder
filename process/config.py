# config.py not used at the moment

# Default alert email list
DEFAULT_ALERT_RECIPIENTS = [
    "safety@heb.com",
    "911-notify@heb.com"
]

# Default routing rule config
DEFAULT_ROUTING_RULE = {
    "Rule Name": "3-DIGIT EXTEN TO 7 DIGIT EXTN",
    "Number Pattern": r"^([0-8])(\d{2})$",
    "Routing Path": "Other Sites"
}

# Default shared line group members, if needed in future
DEFAULT_SLG_MEMBERS = [
    "Lobby", "Security", "Support"
]

# Template and sheet name constants (if you want to centralize these too)
SHEET_NAMES = {
    "sites": "Sites",
    "alerts": "Alerts",
    "call_queues": "Call Queues",
    "common_areas": "Common Areas",
    "routing_rules": "Routing Rules",
    "devices": "Devices",
}