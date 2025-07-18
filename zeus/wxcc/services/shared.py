import logging
from ..wxcc_simple import WxccSimpleClient
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BulkSvc, BulkTask, SvcClient

log = logging.getLogger(__name__)


class WxccBulkSvc(BulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.client: WxccSimpleClient = client
        self.lookup = WxccLookup(client)


class WxccBulkTask(BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WxccBulkSvc = svc


class WxccSvcClient(SvcClient):
    tool = "wxcc"
    client_cls = WxccSimpleClient


class WxccLookup:
    def __init__(self, client):
        self.client: WxccSimpleClient = client
        self.current: dict = {}

    def skill(self, name: str) -> dict:
        params = dict(filter=f"name=='{name}'")
        match = next(self.client.skills.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"Skill: {name} does not exist.")

        return match

    def skill_profile(self, name: str) -> dict:
        """API does not support filter by name"""
        existing = self.client.skill_profiles.list()
        match = next(
            (item for item in existing if item["name"] == name), None
        )

        if not match:
            raise ZeusBulkOpFailed(f"Skill Profile: {name} does not exist.")

        return match

    def team(self, name: str) -> dict:
        params = dict(filter=f"name=='{name}'")
        match = next(self.client.teams.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"Team: {name} does not exist.")

        return match

    def entry_point(self, name: str) -> dict:
        """API does not support filter by name"""
        existing = self.client.entry_points.list()
        match = next(
            (item for item in existing if item["name"] == name), None
        )

        if not match:
            raise ZeusBulkOpFailed(f"Entry Point: {name} does not exist.")

        return match

    def queue(self, name: str) -> dict:
        params = dict(filter=f"name=='{name}'")
        match = next(self.client.queues.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"Queue: {name} does not exist.")

        return match

    def site(self, name: str) -> dict:
        params = dict(filter=f"name=='{name}'")
        match = next(self.client.sites.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"Site: {name} does not exist.")

        return match

    def user(self, email: str) -> dict:
        params = dict(filter=f"email=='{email}'")
        match = next(self.client.users.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"User: {email} does not exist.")

        return match

    def user_profile(self, name: str) -> dict:
        """API does not support filter by name"""
        for resp in self.client.user_profiles.list():
            if resp["name"] == name:
                return resp

        raise ZeusBulkOpFailed(f"User Profile: {name} does not exist.")

    def multimedia_profile(self, name: str) -> dict:
        """API does not support filter by name"""
        for resp in self.client.user_profiles.list():
            if resp["name"] == name:
                return resp

        raise ZeusBulkOpFailed(f"Multimedia profile: {name} does not exist.")

    def desktop_layout(self, name: str) -> dict:
        params = dict(filter=f"name=='{name}'")
        match = next(self.client.desktop_layouts.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"Desktop layout: {name} does not exist.")

        return match

    def audio_file(self, name: str) -> dict:
        params = dict(filter=f"name=='{name}'")
        match = next(self.client.audio_files.list(**params), None)

        if not match:
            raise ZeusBulkOpFailed(f"Audio file: {name} does not exist.")

        return match
