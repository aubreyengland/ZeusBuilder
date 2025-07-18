import logging
from . import phone
from . import meeting
from . import contactcenter
from .base import ZoomSession

log = logging.getLogger(__name__)


class ZoomSimpleClient:
    def __init__(self, access_token, base_url="https://api.zoom.us/v2", verify=True):
        session = ZoomSession(access_token, base_url, verify)
        self.meeting_users = meeting.MeetingUsers(session)
        self.meeting_roles = meeting.MeetingRoles(session)
        self.phone_users = phone.PhoneUsers(session)
        self.phone_sites = phone.PhoneSites(session)
        self.phone_rooms = phone.PhoneRooms(session)
        self.phone_plans = phone.PhonePlans(session)
        self.phone_devices = phone.PhoneDevices(session)
        self.phone_numbers = phone.PhoneNumbers(session)
        self.phone_locations = phone.PhoneLocations(session)
        self.phone_line_keys = phone.PhoneLineKeys(session)
        self.phone_call_queues = phone.PhoneCallQueues(session)
        self.phone_call_handling = phone.PhoneCallHandling(session)
        self.phone_shared_line_groups = phone.PhoneSharedLineGroups(session)
        self.phone_setting_templates = phone.PhoneSettingTemplates(session)
        self.phone_provision_templates = phone.PhoneProvisionTemplates(session)
        self.phone_emergency_addresses = phone.PhoneEmergencyAddresses(session)
        self.phone_common_areas = phone.PhoneCommonAreas(session)
        self.phone_external_contacts = phone.PhoneExternalContacts(session)
        self.phone_auto_receptionists = phone.PhoneAutoReceptionists(session)
        self.phone_alerts = phone.PhoneAlerts(session)
        self.phone_routing_rules = phone.PhoneRoutingRules(session)
        self.phone_audios = phone.PhoneAudios(session)
        self.cc_users = contactcenter.ContactCenterUsers(session)
        self.cc_skills = contactcenter.ContactCenterSkills(session)
        self.cc_skill_categories = contactcenter.ContactCenterSkillCategories(session)
        self.cc_queues = contactcenter.ContactCenterQueues(session)
        self.cc_dispositions = contactcenter.ContactCenterDispositions(session)
        self.cc_disposition_sets = contactcenter.ContactCenterDispositionSets(session)
        self.cc_roles = contactcenter.ContactCenterRoles(session)