from .base import Endpoint, GetEndpointMixin, UpdateEndpointMixin

class PersonCallingBehavior(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/user-call-settings/read-person's-calling-behavior

    Retrieves the calling behavior and UC Manager Profile settings for the person which includes overall
    calling behavior and calling UC Manager Profile ID.

    Webex Calling Behavior controls which Webex telephony application and which UC Manager Profile is to be
    used for a person.

    An organization has an organization-wide default Calling Behavior that may be overridden
    for individual persons.

    UC Manager Profiles are applicable if your organization uses Jabber in Team Messaging mode or
    Calling in Webex (Unified CM).

    The UC Manager Profile also has an organization-wide default and may be overridden for individual persons.

    This API requires a full, user, or read-only administrator auth token with a scope of spark-admin:people_read.

    Support 'GET' and 'PUT' operations
    """
    uri = "people"
    path = "features/callingBehavior"