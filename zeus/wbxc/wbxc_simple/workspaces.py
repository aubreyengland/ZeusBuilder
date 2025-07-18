from .base import Endpoint, GetEndpointMixin

class WorkspaceNumbers(Endpoint, GetEndpointMixin):
    """
    https://developer.webex.com/docs/api/v1/workspace-call-settings/list-numbers-associated-with-a-specific-workspace

    List the PSTN phone numbers associated with a specific workspace, by ID, within the organization.
    Also shows the location and organization associated with the workspace.

    Retrieving this list requires a full or read-only administrator or location administrator auth token
    with a scope of spark-admin:workspaces_read.

    Only supports 'GET' operation
    """
    uri = "workspaces"
    path = "features/numbers"