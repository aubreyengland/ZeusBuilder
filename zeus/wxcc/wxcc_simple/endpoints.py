from .base import CRUDEndpoint, Endpoint, GetEndpointMixin, ListEndpointMixin


class Skills(CRUDEndpoint):
    uri = "skill"


class SkillProfiles(CRUDEndpoint):
    uri = "skill-profile"


class Teams(CRUDEndpoint):
    uri = "team"


class EntryPoints(CRUDEndpoint):
    uri = "entry-point"


class Queues(CRUDEndpoint):
    uri = "contact-service-queue"


class Sites(Endpoint, GetEndpointMixin, ListEndpointMixin):
    uri = "site"


class MultimediaProfiles(Endpoint, GetEndpointMixin, ListEndpointMixin):
    uri = "multimedia-profile"


class DesktopLayouts(Endpoint, GetEndpointMixin, ListEndpointMixin):
    uri = "desktop-layout"


class Users(Endpoint, GetEndpointMixin, ListEndpointMixin):
    uri = "user"


class UserProfiles(Endpoint, GetEndpointMixin, ListEndpointMixin):
    uri = "user-profile"


class AudioFiles(Endpoint, GetEndpointMixin, ListEndpointMixin):
    uri = "audio-file"
