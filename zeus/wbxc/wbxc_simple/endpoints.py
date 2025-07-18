from typing import Iterator

from .base import (
    Endpoint,
    GetEndpointMixin,
    CreateEndpointMixin,
    ListEndpointMixin,
    UpdateEndpointMixin,
    DeleteEndpointMixin,
    CRUDEndpoint,
)


class Announcements(Endpoint, GetEndpointMixin, ListEndpointMixin, DeleteEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/features-announcement-repository
    """

    uri = "telephony/config/announcements"
    list_key = "announcements"

    def upload(self, files, data):
        resp = self.session.post(self.url(), files=files, data=data)
        return resp.json()


class AnnouncementsLocation(Endpoint):
    """
    Custom methods for GET, CREATE, UPDATE, DELETE because a location id is required in the URL

    Ex:
        /telephony/config/locations/{locationId}/announcements
        /telephony/config/locations/{locationId}/announcements/{announcementId}

    https://developer.webex.com/docs/api/v1/features-announcement-repository/fetch-repository-usage-for-announcements-in-a-location
    """

    uri = "telephony/config/locations"
    path = "announcements"

    def get(self, identifier, location_id, **params) -> dict:
        base_url = self.url(location_id)
        url = f"{base_url}/{identifier}"
        return self._get(url, params=params)

    def upload(self, location_id, files, data) -> dict:
        resp = self.session.post(self.url(location_id), files=files, data=data)
        return resp.json()

    def delete(self, identifier, location_id, **params) -> None:
        base_url = self.url(location_id)
        url = f"{base_url}/{identifier}"
        self.session.delete(url, params=params)


class OrgPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/numbers/get-phone-numbers-for-an-organization-with-given-criterias
    """

    uri = "telephony/config/numbers"
    list_key = "phoneNumbers"


class CallParkExtensions(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/features-call-park/read-the-list-of-call-park-extensions
    """

    uri = "telephony/config/callParkExtensions"
    list_key = "callParkExtensions"


class Locations(
    Endpoint, GetEndpointMixin, ListEndpointMixin, CreateEndpointMixin, UpdateEndpointMixin
):
    """
    https://developer.webex.com/docs/api/v1/locations
    """

    uri = "locations"
    list_key = "items"


class LocationCallSettings(
    Endpoint, GetEndpointMixin, ListEndpointMixin, UpdateEndpointMixin
):
    """
    Working with Webex Calling-related settings on Webex Location objects. The
    Locations must already exist in the org.
    Supports standard LIST, GET, UPDATE and a POST method to enable calling
    on an existing location

    https://developer.webex.com/docs/api/v1/location-call-settings
    """

    uri = "telephony/config/locations"
    list_key = "locations"

    def enable_webex_calling(self, payload) -> dict:
        """
        Enable Webex Calling for a location created using the Locations. Create method
        The payload must include the id of an already-exiting location.

        Returns:
            (dict): with 'id' key only
        """
        resp = self.session.post(self.url(), json=payload)
        return resp.json()


class LocationInternalDialing(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Manage internal dialing settings for an existing Webex location.
    Only GET and UPDATE are supported.

    https://developer.webex.com/docs/api/v1/location-call-settings-call-handling/read-the-internal-dialing-configuration-for-a-location
    """

    uri = "/telephony/config/locations"
    path = "internalDialing"


class LocationRouteChoices(Endpoint, ListEndpointMixin):
    """
    List trunks and route groups in the organization. Only LIST is supported.

    https://developer.webex.com/docs/api/v1/location-call-settings/read-the-list-of-routing-choices
    """

    uri = "telephony/config/routeChoices"
    list_key = "routeIdentities"


class LocationVoicemail(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update voicemail settings for a calling-enabled location

    https://developer.webex.com/docs/api/v1/location-call-settings-voicemail
    """

    uri = "/telephony/config/locations"
    path = "voicemail"


class LocationVoicePortal(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    uri = "/telephony/config/locations"
    path = "voicePortal"


class VoicemailGroup(Endpoint):
    """
    https://developer.webex.com/docs/api/v1/location-call-settings-voicemail

    Custom methods for GET, CREATE, UPDATE, DELETE because a location id is required
    in the URL

    Ex:
        /telephony/config/locations/{locationId}/voicemailGroups
        /v1/telephony/config/locations/{locationId}/voicemailGroups/{voicemailGroupId}
    """

    uri = "telephony/config/locations"
    path = "voicemailGroups"

    def list(self, **params):
        """
        Custom method necessary because the uri differs from other
        voicemailGroup methods.
        LIST: `/telephony/config`
        UPDATE, CREATE: `/telephony/config/locations`
        """
        url = self.url(uri="telephony/config")
        list_key = "voicemailGroups"
        yield from self._paged_get(url, list_key, params)

    def create(self, location_id, payload: dict, **params) -> dict:
        url = self.url(uri=f"{self.uri}/{location_id}")
        resp = self.session.post(url, json=payload, params=params)
        return resp.json()

    def get(self, identifier, location_id, **params) -> dict:
        base_url = self.url(location_id)
        url = f"{base_url}/{identifier}"
        resp = self.session.get(url, params=params)
        return resp.json()

    def update(self, identifier, location_id, payload: dict, **params) -> None:
        base_url = self.url(location_id)
        url = f"{base_url}/{identifier}"
        self.session.put(url, json=payload, params=params)

    def delete(self, identifier, location_id, **params) -> None:
        base_url = self.url(location_id)
        url = f"{base_url}/{identifier}"
        self.session.delete(url, params=params)


class LocationOutgoingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    uri = "/telephony/config/locations"
    path = "outgoingPermission"


class LocationOutgoingAutoTransferNumber(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    uri = "/telephony/config/locations"
    path = "outgoingPermission/autoTransferNumbers"


class LocationMusicOnHold(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    uri = "/telephony/config/locations"
    path = "musicOnHold"


class LocationPSTNConnectionOptions(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    GET the list of PSTN connection options available for a location

    https://developer.webex.com/docs/api/v1/pstn/retrieve-pstn-connection-options-for-a-location
    """

    uri = "telephony/pstn/locations"
    path = "connectionOptions"
    list_key = "items"

    # RA NOTE: Full CRUD to be completed at a later date.
    # This will be used for locating the MoH file for Location MoH.


class LocationPSTNConnection(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update the PSTN connection details for a location

    https://developer.webex.com/docs/api/v1/pstn/setup-pstn-connection-for-a-location
    https://developer.webex.com/docs/api/v1/pstn/retrieve-pstn-connection-for-a-location
    """

    uri = "telephony/pstn/locations"
    path = "connection"


# RA NOTE: Issue with GET request using /v1/workspaces?orgId={orgID}
# The 400 error returned when using the org UUID copied from Control Hub
# is expected as the API will only accept the base64 encoded orgID that's
# returned by the /organizations API.
# Workaround is to remove ?orgId={orgID} from the URL as it's only required
# When accessing the API using a third-party admin account
class Workspaces(CRUDEndpoint):
    """
    https://developer.webex.com/docs/api/v1/workspaces
    """

    uri = "workspaces"
    list_key = "items"


class WorkspaceCallForwarding(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Forwarding Settings for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-call-forwarding-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-call-forwarding-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/callForwarding"


class WorkspaceCallWaiting(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Waiting Settings for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-call-waiting-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-call-waiting-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/callWaiting"


class WorkspaceCallerID(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Caller ID Settings for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/read-caller-id-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-caller-id-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/callerId"


class WorkspaceMonitoring(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Monitoring Settings for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-monitoring-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-monitoring-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/monitoring"


class WorkspaceMusicOnHold(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Music On Hold Settings for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-music-on-hold-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-music-on-hold-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "musicOnHold"


class WorkspaceIncomingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Incoming Permission for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-incoming-permission-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-incoming-permission-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/incomingPermission"


class WorkspaceOutgoingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Outgoing Permission for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-outgoing-permission-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-outgoing-permission-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/outgoingPermission"


class WorkspaceEmergencyCallbackNumber(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update the Emergency Callback settings for a designated Workspace

    https://developer.webex.com/docs/api/v1/emergency-services-settings/get-a-workspace-emergency-callback-number
    https://developer.webex.com/docs/api/v1/emergency-services-settings/update-a-workspace-emergency-callback-number
    """

    uri = "telephony/config/workspaces"
    path = "emergencyCallbackNumber"


class WorkspaceEmergencyCallbackNumberDependencies(Endpoint, GetEndpointMixin):
    """
    Get the emergency callback number dependencies for a specific Workspace

    https://developer.webex.com/docs/api/v1/emergency-services-settings/retrieve-workspace-emergency-callback-number-dependencies
    """

    uri = "telephony/config/workspaces"
    path = "emergencyCallbackNumber/dependencies"


# RA: TODO Access Codes for a Workspace
# https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-access-codes-for-a-workspace


class WorkspaceCallIntercept(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Intercept for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/read-call-intercept-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-call-intercept-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/intercept"


class WorkspaceTransferNumbers(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Transfer Numbers for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-transfer-numbers-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-transfer-numbers-settings-for-a-workspace
    """

    uri = "workspaces"
    path = "features/outgoingPermission/autoTransferNumbers"


class WorkspaceAssociatedNumbers(Endpoint, GetEndpointMixin):
    """
    Get the PSTN phone numbers associated with a specific workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/list-numbers-associated-with-a-specific-workspace
    """

    uri = "workspaces"
    path = "features/numbers"


class WorkspaceAvailablePhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get PSTN numbers that are available to be assigned as a workspace's phone number

    https://developer.webex.com/docs/api/v1/workspace-call-settings/get-workspace-available-phone-numbers
    """

    uri = "telephony/config/workspaces/availableNumbers"
    list_key = "phoneNumbers"


class WorkspaceECBNAvailablePhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get PSTN numbers that are available to be assigned as a workspace's emergency callback number

    https://developer.webex.com/docs/api/v1/workspace-call-settings/get-workspace-ecbn-available-phone-numbers
    """

    uri = "telephony/config/workspaces"
    path = "emergencyCallbackNumber/availableNumbers"
    list_key = "phoneNumbers"


class WorkspaceCallForwardAvailablePhoneNumbers(
    Endpoint, GetEndpointMixin, ListEndpointMixin
):
    """
    Get PSTN numbers that are available to be assigned as a workspace's call forward number

    https://developer.webex.com/docs/api/v1/workspace-call-settings/get-workspace-call-forward-available-phone-numbers
    """

    uri = "telephony/config/workspaces"
    path = "callForwarding/availableNumbers"
    list_key = "phoneNumbers"


class WorkspaceCallInterceptAvailablePhoneNumbers(
    Endpoint, GetEndpointMixin, ListEndpointMixin
):
    """
    Get PSTN numbers that are available to be assigned as a workspace's call intercept number

    https://developer.webex.com/docs/api/v1/workspace-call-settings/get-workspace-call-intercept-available-phone-numbers
    """

    uri = "telephony/config/workspaces"
    path = "callIntercept/availableNumbers"
    list_key = "phoneNumbers"


class WorkspaceAnonymousCallReject(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Anonymous Call Settings for a Workspace
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-anonymous-call-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-anonymous-call-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "anonymousCallReject"


class WorkspaceBargeIn(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Barge In Call Settings for a Workspace
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-barge-in-call-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-barge-in-call-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "bargeIn"


class WorkspaceDoNotDisturb(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update DoNotDisturb Settings for a Workspace
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-donotdisturb-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "doNotDisturb"


class WorkspaceCallBridge(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Bridge Warning Tone Settings for a Workspace
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-call-bridge-warning-tone-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-call-bridge-warning-tone-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "callBridge"


class WorkspacePushToTalk(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Push-to-Talk Settings for a Workspace
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/read-push-to-talk-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-push-to-talk-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "pushToTalk"


class WorkspacePrivacy(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Privacy Settings for a Workspace

    https://developer.webex.com/docs/api/v1/workspace-call-settings/retrieve-privacy-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-privacy-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "privacy"


class WorkspaceVoicemail(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Voicemail settings for a Workspace
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/read-voicemail-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-voicemail-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "voicemail"


class WorkspaceBusyVoicemailGreeting(Endpoint):
    """
    Configure Busy Voicemail Greeting for a Place
    Request will need to be a multipart/form-data request rather than JSON, using the audio/wav Content-Type.
    Waveform Audio File Format, .wav, encoded audio file
        NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-busy-voicemail-greeting-for-a-place
    """

    uri = "telephony/config/workspaces"
    path = "voicemail/actions/uploadBusyGreeting/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class WorkspaceNoAnswerVoicemailGreeting(Endpoint):
    """
    NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-no-answer-voicemail-greeting-for-a-place
    """

    uri = "telephony/config/workspaces"
    path = "voicemail/actions/uploadNoAnswerGreeting/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class WorkspaceVoicemailPasscode(Endpoint, UpdateEndpointMixin):
    """
    NOTE: This API is only available for professional licensed workspaces

    https://developer.webex.com/docs/api/v1/workspace-call-settings/modify-voicemail-passcode-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "voicemail/passcode"


class WorkspaceCompression(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Compression Settings for a User

    https://developer.webex.com/docs/api/v1/device-call-settings/get-device-settings-for-a-workspace
    https://developer.webex.com/docs/api/v1/device-call-settings/update-device-settings-for-a-workspace
    """

    uri = "telephony/config/workspaces"
    path = "devices/settings"


class VirtualLines(CRUDEndpoint):
    """
    Get a list of all Virtual Lines

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings
    """

    uri = "telephony/config/virtualLines"
    list_key = "virtualLines"


class VirtualLineCallRecording(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update call recording settings for a virtual line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-call-recording-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-call-recording-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "callRecording"


class VirtualLineDirectorySearch(Endpoint, UpdateEndpointMixin):
    """
    Get or Update the directory search for a designated Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/update-directory-search-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "directorySearch"


class VirtualLineEmergencyCallbackNumber(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update the Emergency Callback settings for a designated Virtual Line

    https://developer.webex.com/docs/api/v1/emergency-services-settings/get-the-virtual-line's-emergency-callback-settings
    https://developer.webex.com/docs/api/v1/emergency-services-settings/update-a-virtual-line's-emergency-callback-settings
    """

    uri = "telephony/config/virtualLines"
    path = "emergencyCallbackNumber"


class VirtualLineEmergencyCallbackNumberDependencies(Endpoint, GetEndpointMixin):
    """
    Get the emergency callback number dependencies for a specific virtual line.

    https://developer.webex.com/docs/api/v1/emergency-services-settings/get-dependencies-for-a-virtual-line-emergency-callback-number
    """

    uri = "telephony/config/virtualLines"
    path = "emergencyCallbackNumber/dependencies"


class VirtualLineCallerID(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Caller ID Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-caller-id-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-caller-id-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "callerId"


class VirtualLineCallWaiting(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Waiting Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-call-waiting-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-call-waiting-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "callWaiting"


class VirtualLineCallForwarding(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Forwarding Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-call-forwarding-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-call-forwarding-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "callForwarding"


class VirtualLineIncomingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Incoming Permission Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-incoming-permission-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-incoming-permission-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "incomingPermission"


class VirtualLineOutgoingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Outgoing Permission Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/retrieve-a-virtual-line's-outgoing-calling-permissions-settings
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/modify-a-virtual-line's-outgoing-calling-permissions-settings
    """

    uri = "telephony/config/virtualLines"
    path = "outgoingPermission"


class VirtualLineIntercept(
    Endpoint, GetEndpointMixin, UpdateEndpointMixin, CreateEndpointMixin
):
    """
    Get or Update Intercept Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-call-intercept-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-call-intercept-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "intercept"


class VirtualLineAgentAvailableCallerIds(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get the list of call queues and hunt groups available for caller ID use by this virtual line as an agent

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/retrieve-agent's-list-of-available-caller-ids
    """

    uri = "telephony/config/virtualLines"
    path = "agent/availableCallerIds"
    list_key = "availableCallerIds"


class VirtualLineAgentCallerId(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Intercept Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/retrieve-agent's-caller-id-information
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/modify-agent's-caller-id-information
    """

    uri = "telephony/config/virtualLines"
    path = "agent/callerId"


class VirtualLineVoicemail(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Voicemail Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-voicemail-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-voicemail-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "voicemail"


class VirtualLineBusyVoicemailGreeting(Endpoint):
    """
    Configure a virtual line's Busy Voicemail Greeting by uploading
    a Waveform Audio File Format, .wav, encoded audio file

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-busy-voicemail-greeting-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "voicemail/actions/uploadBusyGreeting/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class VirtualLineNoAnswerVoicemailGreeting(Endpoint):
    """
    Configure a virtual line's No Answer Voicemail Greeting by uploading
    a Waveform Audio File Format, .wav, encoded audio file

    https://developer.webex.com/docs/api/v1/workspace-call-settings/configure-no-answer-voicemail-greeting-for-a-place
    """

    uri = "telephony/config/virtualLines"
    path = "voicemail/actions/uploadNoAnswerGreeting/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class VirtualLineResetVoicemailPin(Endpoint):
    """
    Custom post needed since the ID is required in the URL
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/reset-voicemail-pin-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "voicemail/actions/resetPin/invoke"

    def reset(self, identifier, payload: dict, **params) -> dict:
        url = self.url(uri=f"{self.uri}/{identifier}")
        resp = self.session.post(url, json=payload, params=params)
        return resp


class VirtualLineVoicemailPasscode(Endpoint, UpdateEndpointMixin):
    """
    Update Voicemail Passcode for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/modify-a-virtual-line's-voicemail-passcode
    """

    uri = "telephony/config/virtualLines"
    path = "voicemail/passcode"


class VirtualLineMusicOnHold(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Music On Hold Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/retrieve-music-on-hold-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-music-on-hold-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "musicOnHold"


class VirtualLinePushToTalk(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Push-to-Talk Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-push-to-talk-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-push-to-talk-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "pushToTalk"


class VirtualLineCallBridge(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Bridge Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-call-bridge-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-call-bridge-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "callBridge"


class VirtualLineBargeIn(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Barge In Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/read-barge-in-settings-for-a-virtual-line
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-barge-in-settings-for-a-virtual-line
    """

    uri = "telephony/config/virtualLines"
    path = "bargeIn"


class VirtualLinePrivacy(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Barge In Settings for a Virtual Line

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/get-a-virtual-line's-privacy-settings
    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/configure-a-virtual-line's-privacy-settings
    """

    uri = "telephony/config/virtualLines"
    path = "privacy"


class VirtualLineFaxMessageAvailableNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    List PSTN numbers that are available to be assigned as a virtual line's FAX message number

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/get-virtual-line-fax-message-available-phone-numbers
    """

    uri = "telephony/config/virtualLines"
    path = "faxMessage/availableNumbers"
    list_key = "phoneNumbers"


class VirtualLineCallForwardingAvailableNumbers(
    Endpoint, GetEndpointMixin, ListEndpointMixin
):
    """
    List PSTN numbers that are available to be assigned as a virtual line's call forward number

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/get-virtual-line-call-forward-available-phone-numbers
    """

    uri = "telephony/config/virtualLines"
    path = "callForwarding/availableNumbers"
    list_key = "phoneNumbers"


class VirtualLineAvailableNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    List PSTN numbers that are available to be assigned as a virtual line's phone number

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/get-virtual-line-available-phone-numbers
    """

    uri = "telephony/config/virtualLines/availableNumbers"
    list_key = "phoneNumbers"


class VirtualLineECBNAvailableNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    List PSTN numbers that can be assigned as a virtual line's emergency callback number

    https://developer.webex.com/docs/api/v1/virtual-line-call-settings/get-virtual-line-ecbn-available-phone-numbers
    """

    uri = "telephony/config/virtualLines"
    path = "emergencyCallbackNumber/availableNumbers"
    list_key = "phoneNumbers"


class Users(CRUDEndpoint):
    """
    https://developer.webex.com/docs/api/v1/people
    """

    uri = "people"
    list_key = "items"


class UserApplications(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Application Services Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-a-person's-application-services-settings
    https://developer.webex.com/docs/api/v1/user-call-settings/modify-a-person's-application-services-settings
    """

    uri = "people"
    path = "features/applications"


class UserBargeIn(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Barge In Call Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-barge-in-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-barge-in-settings-for-a-person
    """

    uri = "people"
    path = "features/bargeIn"


class UserCallForwarding(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Forwarding Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-forwarding-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-call-forwarding-settings-for-a-person
    """

    uri = "people"
    path = "features/callForwarding"


class UserCallIntercept(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Intercept for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-call-intercept-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-call-intercept-settings-for-a-person
    """

    uri = "people"
    path = "features/intercept"


class UserCallInterceptGreeting(Endpoint):
    """
    Configure a person's Call Intercept Greeting by uploading
    a Waveform Audio File Format, .wav, encoded audio file

    https://developer.webex.com/docs/api/v1/user-call-settings/configure-call-intercept-greeting-for-a-person
    """

    uri = "people"
    path = "features/intercept/actions/announcementUpload/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class UserCallRecording(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update call recording settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-call-recording-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-call-recording-settings-for-a-person
    """

    uri = "people"
    path = "features/callRecording"


class UserCallWaiting(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Waiting Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-call-waiting-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-call-waiting-settings-for-a-person
    """

    uri = "people"
    path = "features/callWaiting"


class UserCallerID(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Caller ID Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-caller-id-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-caller-id-settings-for-a-person
    """

    uri = "people"
    path = "features/callerId"


class UserCallingBehavior(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Calling Behavior Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-person's-calling-behavior
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-a-person's-calling-behavior
    """

    uri = "people"
    path = "features/callingBehavior"


class UserDoNotDisturb(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update DoNotDisturb Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-do-not-disturb-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-do-not-disturb-settings-for-a-person
    """

    uri = "people"
    path = "features/doNotDisturb"


class UserExecutiveAssistant(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Executive Assistant Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-executive-assistant-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/read-hoteling-settings-for-a-person
    """

    uri = "people"
    path = "features/executiveAssistant"


class UserHoteling(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Hoteling Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-hoteling-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-hoteling-settings-for-a-person
    """

    uri = "people"
    path = "features/hoteling"


class UserMonitoring(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Monitoring Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-a-person's-monitoring-settings
    https://developer.webex.com/docs/api/v1/user-call-settings/modify-a-person's-monitoring-settings
    """

    uri = "people"
    path = "features/monitoring"


# RA TODO: Move Users
# https://developer.webex.com/docs/api/v1/user-call-settings/validate-or-initiate-move-users-job


class UserMusicOnHold(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Music On Hold Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-music-on-hold-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-music-on-hold-settings-for-a-person
    """

    uri = "telephony/config/people"
    path = "musicOnHold"


class UserIncomingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Incoming Permission for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-incoming-permission-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-incoming-permission-settings-for-a-person
    """

    uri = "people"
    path = "features/incomingPermission"


class UserOutgoingPermission(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Outgoing Permission for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-a-person's-outgoing-calling-permissions-settings
    https://developer.webex.com/docs/api/v1/user-call-settings/modify-a-person's-outgoing-calling-permissions-settings
    """

    uri = "people"
    path = "features/outgoingPermission"


class UserPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get and list a person's phone numbers including alternate numbers.

    https://developer.webex.com/docs/api/v1/user-call-settings/get-a-list-of-phone-numbers-for-a-person
    """

    uri = "people"
    path = "features/numbers"
    list_key = "phoneNumbers"


class UserAlternateNumbers(Endpoint, UpdateEndpointMixin):
    """
    Update phone number Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/assign-or-unassign-numbers-to-a-person
    """

    uri = "telephony/config/people"
    path = "numbers"


class UserPreferredAnswerEndpoint(
    Endpoint, GetEndpointMixin, UpdateEndpointMixin, ListEndpointMixin
):
    """
    Get or Update Preferred Answer Endpoint settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/get-preferred-answer-endpoint
    https://developer.webex.com/docs/api/v1/user-call-settings/modify-preferred-answer-endpoint
    """

    uri = "telephony/config/people"
    path = "preferredAnswerEndpoint"
    list_key = "endpoints"


class UserPrivacy(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Preferred Answer Endpoint settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/get-a-person's-privacy-settings
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-a-person's-privacy-settings
    """

    uri = "people"
    path = "features/privacy"


class UserPushToTalk(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Push-to-Talk settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-push-to-talk-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-push-to-talk-settings-for-a-person
    """

    uri = "people"
    path = "features/pushToTalk"


class UserReception(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Receptionist Client Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-receptionist-client-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-receptionist-client-settings-for-a-person
    """

    uri = "people"
    path = "features/reception"


# RA TODO: User Schedules CRUD
# https://developer.webex.com/docs/api/v1/user-call-settings/list-of-schedules-for-a-person

# RA TODO: Shared-Line Appearance Members. Shared lines for the Webex App
# https://developer.webex.com/docs/api/v1/user-call-settings/get-shared-line-appearance-members


class UserVoicemail(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Voicemail settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-voicemail-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-voicemail-settings-for-a-person
    """

    uri = "people"
    path = "features/voicemail"


class UserBusyVoicemailGreeting(Endpoint):
    """
    Configure Busy Voicemail Greeting for a User
    Request will need to be a multipart/form-data request rather than JSON, using the audio/wav Content-Type.
    Waveform Audio File Format, .wav, encoded audio file

    https://developer.webex.com/docs/api/v1/user-call-settings/configure-busy-voicemail-greeting-for-a-person
    """

    uri = "people"
    path = "features/voicemail/actions/uploadBusyGreeting/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class UserNoAnswerVoicemailGreeting(Endpoint):
    """
    Configure No Answer Voicemail Greeting for a User
    Request will need to be a multipart/form-data request rather than JSON, using the audio/wav Content-Type.
    Waveform Audio File Format, .wav, encoded audio file

    https://developer.webex.com/docs/api/v1/user-call-settings/configure-no-answer-voicemail-greeting-for-a-person
    """

    uri = "people"
    path = "features/voicemail/actions/uploadNoAnswerGreeting/invoke"

    def upload(self, identifier, files):
        self.session.post(self.url(identifier), files=files)


class UserResetVoicemailPin(Endpoint):
    """
    Custom post needed since the ID is required in the URL
    https://developer.webex.com/docs/api/v1/user-call-settings/reset-voicemail-pin
    """

    uri = "people"
    path = "features/voicemail/actions/resetPin/invoke"

    def reset(self, identifier, payload: dict, **params) -> dict:
        url = self.url(uri=f"{self.uri}/{identifier}")
        resp = self.session.post(url, json=payload, params=params)
        return resp


class UserVoicemailPasscode(Endpoint, UpdateEndpointMixin):
    """
    Update Voicemail Passcode for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/modify-a-person's-voicemail-passcode
    """

    uri = "telephony/config/people"
    path = "voicemail/passcode"


class UserAgentAvailableCallerIds(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get the list of call queues and hunt groups available for caller ID use by this user as an agent

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-agent's-list-of-available-caller-ids
    """

    uri = "telephony/config/people"
    path = "agent/availableCallerIds"
    list_key = "availableCallerIds"


class UserAgentCallerId(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Agent's Caller ID settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-agent's-caller-id-information
    https://developer.webex.com/docs/api/v1/user-call-settings/modify-agent's-caller-id-information
    """

    uri = "telephony/config/people"
    path = "agent/callerId"


class UserCallBridge(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Call Bridge Warning Tone Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/read-call-bridge-settings-for-a-person
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-call-bridge-settings-for-a-person
    """

    uri = "telephony/config/people"
    path = "features/callBridge"


class UserMsTeams(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update MS Teams Settings for a User

    https://developer.webex.com/docs/api/v1/user-call-settings/retrieve-a-person's-ms-teams-settings
    https://developer.webex.com/docs/api/v1/user-call-settings/configure-a-person's-ms-teams-setting
    """

    uri = "telephony/config/people"
    path = "settings/msTeams"


class UserCompression(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update Compression Settings for a User

    https://developer.webex.com/docs/api/v1/device-call-settings/get-device-settings-for-a-person
    https://developer.webex.com/docs/api/v1/device-call-settings/update-device-settings-for-a-person
    """

    uri = "telephony/config/people"
    path = "devices/settings"


class UserEmergencyCallbackNumber(Endpoint, GetEndpointMixin, UpdateEndpointMixin):
    """
    Get or Update the Emergency Callback settings for a User

    https://developer.webex.com/docs/api/v1/emergency-services-settings/get-a-person's-emergency-callback-number
    https://developer.webex.com/docs/api/v1/emergency-services-settings/update-a-person's-emergency-callback-number
    """

    uri = "telephony/config/people"
    path = "emergencyCallbackNumber"


class UserEmergencyCallbackNumberDependencies(Endpoint, GetEndpointMixin):
    """
    Get the emergency callback number dependencies for a specific User

    https://developer.webex.com/docs/api/v1/emergency-services-settings/get-dependencies-for-a-virtual-line-emergency-callback-number
    """

    uri = "telephony/config/people"
    path = "emergencyCallbackNumber/dependencies"


class UserECBNAvailableNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    List PSTN numbers that are available to be assigned as a person's emergency callback number

    https://developer.webex.com/docs/api/v1/user-call-settings/get-person-ecbn-available-phone-numbers
    """

    uri = "telephony/config/people"
    path = "emergencyCallbackNumber/availableNumbers"
    list_key = "phoneNumbers"


class UserAvailablePrimaryPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get PSTN numbers that are available to be assigned as a person's primary phone number

    https://developer.webex.com/docs/api/v1/user-call-settings/get-person-primary-available-phone-numbers
    """

    uri = "telephony/config/people/primary/availableNumbers"
    list_key = "phoneNumbers"


class UserAvailableSecondaryPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get PSTN numbers that are available to be assigned as a person's secondary phone number

    https://developer.webex.com/docs/api/v1/user-call-settings/get-person-secondary-available-phone-numbers
    """

    uri = "telephony/config/people"
    path = "secondary/availableNumbers"
    list_key = "phoneNumbers"


class UserAvailableFaxPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get PSTN numbers that are available to be assigned as a person's FAX message number

    https://developer.webex.com/docs/api/v1/user-call-settings/get-person-fax-message-available-phone-numbers
    """

    uri = "telephony/config/people"
    path = "faxMessage/availableNumbers"
    list_key = "phoneNumbers"


class UserAvailableCallForwardPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get numbers that are available to be assigned as a person's call forward number

    https://developer.webex.com/docs/api/v1/user-call-settings/get-person-call-forward-available-phone-numbers
    """

    uri = "telephony/config/people"
    path = "callForwarding/availableNumbers"
    list_key = "phoneNumbers"


class UserAvailableInterceptPhoneNumbers(Endpoint, GetEndpointMixin, ListEndpointMixin):
    """
    Get numbers that are available to be assigned as a person's call intercept number

    https://developer.webex.com/docs/api/v1/user-call-settings/get-person-call-intercept-available-phone-numbers
    """

    uri = "telephony/config/people"
    path = "callIntercept/availableNumbers"
    list_key = "phoneNumbers"


class HuntGroups(Endpoint):
    list_key = "huntGroups"

    def list(self, **params) -> Iterator[dict]:
        uri = "telephony/config/huntGroups"
        url = self.url(uri=uri)
        yield from self._paged_get(url, self.list_key, params)

    def get(self, location_id, huntgroup_id, **params):
        uri = f"telephony/config/locations/{location_id}/huntGroups/{huntgroup_id}"
        return self._get(self.url(uri=uri), params=params)

    def create(self, location_id, payload: dict, **params) -> dict:
        uri = f"telephony/config/locations/{location_id}/huntGroups"
        resp = self.session.post(self.url(uri), json=payload, params=params)
        return resp.json()

    def update(self, location_id, huntgroup_id, payload, **params):
        uri = f"telephony/config/locations/{location_id}/huntGroups/{huntgroup_id}"
        self.session.put(self.url(uri), json=payload, params=params)

    def delete(self, location_id, huntgroup_id, **params):
        uri = f"telephony/config/locations/{location_id}/huntGroups/{huntgroup_id}"
        self.session.delete(self.url(uri), params=params)


class Numbers(Endpoint):
    def list(self, phoneNumber=None, extension=None, **params):
        params = dict(phoneNumber=phoneNumber, extension=extension, **params)
        uri = "telephony/config/numbers"
        url = self.url(uri=uri)
        yield from self._paged_get(url, "phoneNumbers", params)
