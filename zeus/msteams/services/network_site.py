import logging
import re
from zeus import registry as reg
from .shared import (
    MsTeamsBulkSvc,
    MsTeamsNetworkRegionCreateTask,
    MsTeamsNetworkSiteCreateTask,
    MsTeamsNetworkSiteUpdateTask,
    MsTeamsNetworkSiteSubnetCreateTask,
    MsTeamsNetworkSiteSubnetUpdateTask,
    MsTeamsNetworkSiteSubnetDeleteTask,
)
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc, UploadTask, RowLoadResp
from ..msteams_models import MsTeamsNetworkSite, MsTeamsNetworkSiteSubnet
from ..msteams_simple import MsTeamsSimpleClient

log = logging.getLogger(__name__)


class MsTeamsNetworkSiteRequestBuilder:
    """
    Shared request builder class for MS Teams Network Site Create and Update services.
    """

    def build_request(self, model: MsTeamsNetworkSite) -> tuple[dict, dict, list[dict]]:
        """
        Builds and validates the request payload. Nulls empty strings on optional fields.

        Args:
            model (MsTeamsNetworkSite): The model containing the data to be validated.

        Raises:
            ZeusBulkOpFailed: If any required fields are missing or if they are not in the correct format.

        Returns:
            tuple: A tuple containing the network site payload, network region payload, and network site subnets payload.
        """
        network_site_payload = model.to_payload()
        network_region_payload = {
            "Identity": model.NetworkRegionID if model.NetworkRegionID else None
        }
        network_site_subnets_payload = network_site_payload.pop("Subnets")

        for subnet in network_site_subnets_payload:
            subnet["NetworkSiteID"] = model.Identity
            subnet["Identity"] = subnet["SubnetID"]

        # Validate required fields
        if len(network_site_payload["Identity"]) < 1:
            raise ZeusBulkOpFailed("Name is required")

        # Default OptYN to False
        if network_site_payload["EnableLocationBasedRouting"] is None:
            network_site_payload["EnableLocationBasedRouting"] = False

        # Rewrite default policy to None
        network_site_payload["NetworkRoamingPolicy"] = (
            self.convert_model_default_policy_to_req(
                network_site_payload["NetworkRoamingPolicy"]
            )
        )
        network_site_payload["EmergencyCallingPolicy"] = (
            self.convert_model_default_policy_to_req(
                network_site_payload["EmergencyCallingPolicy"]
            )
        )
        network_site_payload["EmergencyCallRoutingPolicy"] = (
            self.convert_model_default_policy_to_req(
                network_site_payload["EmergencyCallRoutingPolicy"]
            )
        )

        # None the optional fields if they are empty strings
        for key in network_site_payload:
            if network_site_payload[key] == "":
                network_site_payload[key] = None

        return network_site_payload, network_region_payload, network_site_subnets_payload

    @staticmethod
    def convert_model_default_policy_to_req(policy: str | None) -> str:
        return None if policy == "Global (Org-wide default)" else policy


@reg.bulk_service("msteams", "network_sites", "CREATE")
class MsTeamsNetworkSiteCreateSvc(MsTeamsBulkSvc, MsTeamsNetworkSiteRequestBuilder):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.network_site_payload = {}
        self.network_region_payload = {}
        self.network_site_subnets_payload = []

    def run(self):
        (
            self.network_site_payload,
            self.network_region_payload,
            self.network_site_subnets_payload,
        ) = self.build_request(self.model)

        self.lookup_or_create_network_region()

        self.create_network_site()

        self.create_network_site_subnets()

    def lookup_or_create_network_region(self):
        if self.network_region_payload["Identity"]:
            try:
                self.lookup.network_region(self.network_region_payload["Identity"])
            except ZeusBulkOpFailed:
                self.create_network_region()

    def create_network_region(self):
        task = MsTeamsNetworkRegionCreateTask(self, self.network_region_payload)
        task.run()
        self.rollback_tasks.append(task)

    def create_network_site(self):
        task = MsTeamsNetworkSiteCreateTask(self, self.network_site_payload)
        task.run()
        self.rollback_tasks.append(task)

    def create_network_site_subnets(self):
        for subnet in self.network_site_subnets_payload:
            task = MsTeamsNetworkSiteSubnetCreateTask(self, subnet)
            task.run()
            self.rollback_tasks.append(task)


@reg.bulk_service("msteams", "network_sites", "UPDATE")
class MsTeamsNetworkSiteUpdateSvc(MsTeamsBulkSvc, MsTeamsNetworkSiteRequestBuilder):

    def run(self):
        (
            self.network_site_payload,
            self.network_region_payload,
            self.network_site_subnets_payload,
        ) = self.build_request(self.model)

        self.current = self.lookup.network_site(self.model.Identity)

        self.lookup_or_create_network_region()

        self.update_network_site()

        self.update_network_site_subnets()

    def lookup_or_create_network_region(self):
        if (
            self.network_region_payload["Identity"] is not None
            and self.network_region_payload["Identity"] != self.current["NetworkRegionID"]
        ):
            try:
                self.lookup.network_region(self.network_region_payload["Identity"])
            except ZeusBulkOpFailed:
                self.create_network_region()

    def create_network_region(self):
        task = MsTeamsNetworkRegionCreateTask(self, self.network_region_payload)
        task.run()
        self.rollback_tasks.append(task)

    def update_network_site(self):
        task = MsTeamsNetworkSiteUpdateTask(self, self.network_site_payload)
        task.run()
        self.rollback_tasks.append(task)

    def update_network_site_subnets(self):
        # Compare current subnets to new subnets
        current_subnets = {s["SubnetID"]: s for s in self.current["Subnets"]}
        new_subnets = {s["SubnetID"]: s for s in self.network_site_subnets_payload}

        # Delete subnets that are in current but not in new
        for current_subnet in current_subnets:
            if current_subnet not in new_subnets:
                task = MsTeamsNetworkSiteSubnetDeleteTask(
                    self, current_subnets[current_subnet]
                )
                task.run()
                self.rollback_tasks.append(task)

        # Update subnets where the MaskBits or Description have changed
        for new_subnet in new_subnets:
            if new_subnet in current_subnets:
                if (
                    int(new_subnets[new_subnet]["MaskBits"])
                    != int(current_subnets[new_subnet]["MaskBits"])
                    or new_subnets[new_subnet]["Description"]
                    != current_subnets[new_subnet]["Description"]
                ):
                    task = MsTeamsNetworkSiteSubnetUpdateTask(
                        self, current_subnets[new_subnet], new_subnets[new_subnet]
                    )
                    task.run()
                    self.rollback_tasks.append(task)

        # Create subnets that are in new but not in current
        for new_subnet in new_subnets:
            if new_subnet not in current_subnets:
                task = MsTeamsNetworkSiteSubnetCreateTask(self, new_subnets[new_subnet])
                task.run()
                self.rollback_tasks.append(task)


@reg.bulk_service("msteams", "network_sites", "DELETE")
class MsTeamsNetworkSiteDeleteSvc(MsTeamsBulkSvc):

    def run(self):
        self.current = self.lookup.network_site(self.model.Identity)

        self.delete_network_site_subnets()
        self.delete_network_site()

    def delete_network_site_subnets(self):
        for subnet in self.current["Subnets"]:
            task = MsTeamsNetworkSiteSubnetDeleteTask(self, subnet)
            task.run()
            self.rollback_tasks.append(task)

    def delete_network_site(self):
        self.client.network_sites.delete(self.current["Identity"])


@reg.upload_task("msteams", "network_sites")
class MsTeamsNetworkSiteUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            row["Subnets"] = self.build_subnets(row)
        except Exception as exc:
            _ = RowLoadResp(index=idx, error=str(exc))
        return super().validate_row(idx, row)

    @staticmethod
    def build_subnets(row):
        """
        Convert multiple subnet values into a single list value.
        Row will have one or more keys 'Subnet X', 'Subnet X Network Range'.

        Turn these into a list of dictionaries.

        Example:
            row = {
                "Subnet 1": "10.0.1.0",
                "Subnet 1 Network Range": "24",
                "Subnet 1 Description": "Subnet 1",
                "Subnet 2": "10.0.2.0",
                "Subnet 2 Network Range": "24",
                "Subnet 2 Description": "Subnet 2",
            }
        Returns:
            [
                {
                    "idx": 1,
                    "SubnetID": "10.0.1.0",
                    "MaskBits": "24",
                    "Description": "Subnet 1",
                },
                {
                    "idx": 2,
                    "SubnetID": "10.0.2.0",
                    "MaskBits": "24",
                    "Description": "Subnet 2",
                },
            ]
        """
        subnets = []
        for key in row:
            if m := re.search(r"Subnet\s(\d+)$", key):

                if not row[key]:
                    continue

                order = m.group(1)

                network_range_key = f"Subnet {order} Network Range"
                description_key = f"Subnet {order} Description"

                subnets.append(
                    dict(
                        idx=order,
                        SubnetID=row[key],
                        MaskBits=row.get(network_range_key),
                        Description=row.get(description_key),
                    )
                )

        return subnets


@reg.browse_service("msteams", "network_sites")
class MsTeamsNetworkSiteBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = MsTeamsNetworkSiteModelBuilder(self.client)
        for resp in self.client.network_sites.list(include_subnets=True):
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = model.Identity
            row["SubnetsCount"] = len(builder.build_subnets(resp))
            rows.append(row)
        return rows


@reg.export_service("msteams", "network_sites")
class MsTeamsNetworkSiteExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsNetworkSite.schema()["data_type"]
        builder = MsTeamsNetworkSiteModelBuilder(self.client)

        for resp in self.client.network_sites.list(include_subnets=True):
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("Identity", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class MsTeamsNetworkSiteModelBuilder:
    """
    Shared model builder class for MS Teams Network Sites
    Browse and Export services.
    """

    def __init__(self, client):
        self.client: MsTeamsSimpleClient = client

    def build_model(self, resp: dict) -> MsTeamsNetworkSite:
        summary_data = {k: v for k, v in resp.items() if k != "Subnets"}
        return MsTeamsNetworkSite.safe_build(
            NetworkRoamingPolicy=self.default_policy(
                summary_data.pop("NetworkRoamingPolicy")
            ),
            EmergencyCallingPolicy=self.default_policy(
                summary_data.pop("EmergencyCallingPolicy")
            ),
            EmergencyCallRoutingPolicy=self.default_policy(
                summary_data.pop("EmergencyCallRoutingPolicy")
            ),
            Subnets=[],
            **summary_data,
        )

    def build_detailed_model(self, resp: dict) -> MsTeamsNetworkSite:
        subnets = self.build_subnets(resp)
        return MsTeamsNetworkSite.safe_build(
            NetworkRoamingPolicy=self.default_policy(resp.pop("NetworkRoamingPolicy")),
            EmergencyCallingPolicy=self.default_policy(resp.pop("EmergencyCallingPolicy")),
            EmergencyCallRoutingPolicy=self.default_policy(
                resp.pop("EmergencyCallRoutingPolicy")
            ),
            Subnets=subnets,
            **resp,
        )

    def build_subnets(self, resp: dict) -> list[dict]:
        subnets = []

        for idx, subnet in enumerate(resp.pop("Subnets", []), start=len(subnets) + 1):
            subnets.append(
                MsTeamsNetworkSiteSubnet(
                    idx=idx,
                    **subnet,
                )
            )
        return subnets

    def default_policy(self, policy: str | None) -> str:
        return "Global (Org-wide default)" if policy == "" or policy is None else policy
