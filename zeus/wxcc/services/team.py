from zeus import registry as reg
from .shared import WxccBulkSvc
from zeus.wxcc import wxcc_models as wm
from zeus.services import BrowseSvc, ExportSvc


class WxccTeamPayload:
    """Mixin class for CREATE and UPDATE team services."""

    model, lookup = None, None

    def build_payload(self) -> dict:
        site = self.lookup.site(self.model.site_name)
        payload = self.model.to_payload(
            include={
                "name",
                "active",
                "teamStatus",
                "teamType",
                "dialedNumber",
                "capacity",
            },
            drop_unset=True,
        )
        payload["siteId"] = site["id"]

        if self.model.teamType == "AGENT":
            self.add_agent_type_ref_fields(payload)

        return payload

    def add_agent_type_ref_fields(self, payload: dict):
        """
        Add agent team optional reference fields to the payload.

        If the model has a value for each field, do a lookup on
        the name and add the referenced object's id.

        If the model does not have a value for a field, set the
        value to null to allow updates to remove a reference
        """
        payload.update({
            "desktopLayoutId": None,
            "multimediaProfileId": None,
            "skillProfileId": None,
            "userIds": [],
        })

        if self.model.desktop_layout_name:
            resp = self.lookup.desktop_layout(self.model.desktop_layout_name)
            payload["desktopLayoutId"] = resp["id"]

        if self.model.multimedia_profile_name:
            resp = self.lookup.multimedia_profile(self.model.multimedia_profile_name)
            payload["multimediaProfileId"] = resp["id"]

        if self.model.skill_profile_name:
            resp = self.lookup.skill_profile(self.model.skill_profile_name)
            payload["skillProfileId"] = resp["id"]

        for name in self.model.agent_list:
            agent = self.lookup.user(name)
            payload["userIds"].append(agent["id"])


@reg.bulk_service("wxcc", "teams", "CREATE")
class WxccTeamCreateSvc(WxccBulkSvc, WxccTeamPayload):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.teams.create(payload)


@reg.bulk_service("wxcc", "teams", "UPDATE")
class WxccTeamUpdateSvc(WxccBulkSvc, WxccTeamPayload):

    def run(self):
        self.current = self.lookup.team(self.model.name)
        payload = self.build_payload()
        payload["id"] = self.current["id"]

        self.client.teams.update(self.current["id"], payload)


@reg.bulk_service("wxcc", "teams", "DELETE")
class WxccTeamDeleteSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.team(self.model.name)
        self.client.teams.delete(self.current["id"])


@reg.browse_service("wxcc", "teams")
class WxccTeamBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WxccTeamModelBuilder(self.client)

        for resp in self.client.teams.list():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("wxcc", "teams")
class WxccTeamExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = wm.WxccTeam.schema()["data_type"]
        builder = WxccTeamModelBuilder(self.client)

        for resp in self.client.teams.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WxccTeamModelBuilder:
    def __init__(self, client):
        self.client = client
        self.obj_maps = {}

    def build_model(self, resp):

        model = wm.WxccTeam.safe_build(
            resp,
            agents=self.get_agent_names(resp),
            site_name=self.get_site_name(resp),
            skill_profile_name=self.get_skill_profile_name(resp),
            desktop_layout_name=self.get_desktop_layout_name(resp),
            multimedia_profile_name=self.get_multimedia_profile_name(resp),
        )

        return model

    def get_name_from_id(self, identifier: str, endpoint: str):
        """
        Get a referenced object's name using the provided object id by doing a
        LIST request for the object type and returning the response matching
        the provided id.

        Save the LIST responses to the obj_maps attribute, so the request is
        only made once per object type.

        Note: LIST requests are done instead of GETTING the ID to avoid
        Wxcc rate limiting.

        Args:
            identifier (str): Unique ID of the referenced object from the LIST team response
            endpoint (str): API endpoint to invoke

        """
        if endpoint not in self.obj_maps:

            self.obj_maps[endpoint] = {
                resp["id"]: resp for resp
                in getattr(self.client, endpoint).list()
            }

        return self.obj_maps[endpoint].get(identifier) or {}

    def get_site_name(self, resp):
        ref = self.get_name_from_id(resp["siteId"], "sites")
        return ref.get("name", "NOTFOUND")

    def get_skill_profile_name(self, resp):
        identifier = resp.get("skillProfileId")
        if identifier:
            ref = self.get_name_from_id(identifier, "skill_profiles")
            return ref.get("name", "NOTFOUND")
        return ""

    def get_desktop_layout_name(self, resp):
        identifier = resp.get("desktopLayoutId")
        if identifier:
            ref = self.get_name_from_id(identifier, "desktop_layouts")
            return ref.get("name", "NOTFOUND")
        return ""

    def get_multimedia_profile_name(self, resp):
        identifier = resp.get("multimediaProfileId")
        if identifier:
            ref = self.get_name_from_id(identifier, "multimedia_profiles")
            return ref.get("name", "NOTFOUND")
        return ""

    def get_agent_names(self, resp):
        agent_names = []
        for user_id in resp.get("userIds") or []:
            ref = self.get_name_from_id(user_id, "users")
            agent_names.append(ref.get("email", "NOTFOUND"))

        return ",".join(agent_names)
