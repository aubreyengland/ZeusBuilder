import logging
from . import emergency
from . import network
from .base import MsTeamsSession

log = logging.getLogger(__name__)


class MsTeamsSimpleClient:

    def __init__(
        self,
        access_token,
        base_url="https://api.interfaces.records.teams.microsoft.com",
        verify=True,
    ):
        session = MsTeamsSession(access_token, base_url, verify)
        self.emergency_addresses = emergency.Addresses(session)
        self.emergency_locations = emergency.Locations(session)
        self.emergency_calling_policies = emergency.CallingPolicies(session)
        self.emergency_call_routing_policies = emergency.CallRoutingPolicies(session)
        self.subnets = network.Subnets(session)
        self.switches = network.Switches(session)
        self.ports = network.Ports(session)
        self.waps = network.WirelessAccessPoints(session)
        self.trusted_ips = network.TrustedIPs(session)
        self.network_regions = network.Regions(session)
        self.network_sites = network.Sites(session)
        self.network_site_subnets = network.SiteSubnets(session)
        self.network_roaming_policies = network.RoamingPolicies(session)
