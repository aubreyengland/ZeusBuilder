import logging
from . import endpoints
from .base import WxccSession
log = logging.getLogger(__name__)


class WxccSimpleClient:

    def __init__(self, access_token, base_url="https://api.wxcc-us1.cisco.com", verify=True):
        session = WxccSession(access_token, base_url, verify)
        self.skills = endpoints.Skills(session)
        self.skill_profiles = endpoints.SkillProfiles(session)
        self.teams = endpoints.Teams(session)
        self.entry_points = endpoints.EntryPoints(session)
        self.queues = endpoints.Queues(session)
        self.sites = endpoints.Sites(session)
        self.multimedia_profiles = endpoints.MultimediaProfiles(session)
        self.desktop_layouts = endpoints.DesktopLayouts(session)
        self.users = endpoints.Users(session)
        self.user_profiles = endpoints.UserProfiles(session)
        self.desktop_layouts = endpoints.DesktopLayouts(session)
        self.audio_files = endpoints.AudioFiles(session)
