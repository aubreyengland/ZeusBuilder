import re
import logging
from zeus import registry as reg
from .shared import WxccBulkSvc
from zeus.wxcc import wxcc_models as wm
from zeus.services import BrowseSvc, ExportSvc, DetailSvc, UploadTask, RowLoadResp

log = logging.getLogger(__name__)


class WxccQueuePayload:
    """Mixin class for CREATE and UPDATE queue services."""

    model, lookup = None, None

    def build_payload(self):
        exclude = {"music_in_queue_file", "callDistributionGroups"}
        payload = self.model.to_payload(exclude=exclude, drop_unset=True)

        if self.model.music_in_queue_file:
            audio_file = self.lookup.audio_file(self.model.music_in_queue_file)
            payload["defaultMusicInQueueMediaFileId"] = audio_file["id"]

        payload["callDistributionGroups"] = self.build_call_distribution_groups()

        return payload

    def build_call_distribution_groups(self):
        """
        Create the `callDistributionGroups` payload value by combining the
        `agentGroup`, `duration`, and `order` fields in the request.

        Each of these fields is a comma/semicolon separated value. These are
        combined based on index.

        Examples:

          One group with one team:
            request.agentGroup = 'TeamA'
            request.duration = 0
            request.order = 1
         Output:
           [
            {
                'agentGroups': [{'teamId': '123'}],
                'duration': 0,
                'order': 1,
            }
           ]
          One group with two teams:
            request.agentGroup = 'TeamA;TeamB'
            request.duration = 0
            request.order = 1
         Output:
           [
            {
                'agentGroups': [{'teamId': '1'}, {'teamId': '2'}],
                'duration': 0,
                'order': 1,
            }
           ]
        Two groups with one team each:
            request.agentGroup = 'TeamA;TeamB'
            request.duration = 0;60
            request.order = 1;2
         Output:
           [
            {
                'agentGroups': [{'teamId': '1'}],
                'duration': 0,
                'order': 1,
            },
            {
                'agentGroups': [{'teamId': '2'}],
                'duration': 60,
                'order': 2,
            }
           ]
        Two groups. The first with one team, the second with two teams:
            request.agentGroup = 'TeamA;TeamB;TeamC'
            request.duration = 0;60
            request.order = 1;2
         Output:
           [
            {
                'agentGroups': [{'teamId': '1'}, {'teamId': '2'}],
                'duration': 0,
                'order': 1,
            },
            {
                'agentGroups': [{'teamId': '3'}],
                'duration': 60,
                'order': 2,
            }
           ]
        """
        payload = []
        for group in self.model.callDistributionGroups:

            agent_groups = [
                {"teamId": self.lookup.team(name)["id"]} for name in group.agentGroups
            ]

            payload.append(
                {
                    "order": group.order,
                    "duration": group.duration,
                    "agentGroups": agent_groups,
                }
            )

        return payload


@reg.bulk_service("wxcc", "queues", "CREATE")
class WxccQueueCreateSvc(WxccBulkSvc, WxccQueuePayload):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.queues.create(payload=payload)


@reg.bulk_service("wxcc", "queues", "UPDATE")
class WxccQueueUpdateSvc(WxccBulkSvc, WxccQueuePayload):

    def run(self):
        self.current = self.lookup.queue(self.model.name)

        payload = self.build_payload()
        payload["id"] = self.current["id"]
        # This is a workaround for a bug in the WxCC API. It will be removed when the bug is fixed.
        payload["ccOneQueue"] = True

        self.client.queues.update(self.current["id"], payload)


@reg.bulk_service("wxcc", "queues", "DELETE")
class WxccQueueDeleteSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.queue(self.model.name)
        self.client.queues.delete(self.current["id"])


@reg.upload_task("wxcc", "queues")
class WxccQueueUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            row["callDistributionGroups"] = self.build_call_distribution_groups(row)
        except Exception as exc:
            resp = RowLoadResp(index=idx, error=str(exc))
        return super().validate_row(idx, row)

    @staticmethod
    def build_call_distribution_groups(row):
        """
        Convert multiple call distribution group values into a single list value.
        Row will have one or more keys 'Call Distribution Group X Teams', 'Call Distribution Group X Duration'
        where 'X' is an integer.

        'Call Distribution Group X Teams' holds a comma/semicolon-separated string of team names
        'Call Distribution Group X Duration' holds an integer

        Turn these into a list of dictionaries.

        Example:
            row = {
                "Call Distribution Group 1 Teams": "TeamA;TeamB",
                "Call Distribution Group 1 Duration": 0,
                "Call Distribution Group 2 Teams": "TeamC",
                "Call Distribution Group 2 Duration": 10,
            }
        Returns:
            [
                {
                    "agentGroups":["TeamA", "TeamB"],
                    "duration": 0,
                    "order": 1,
                },
                {
                    "agentGroups":["TeamC"],
                    "duration": 10,
                    "order": 2,
                },
            ]
        """
        groups = []
        for key in row:
            if m := re.search(r"Call\sDistribution\sGroup\s(\d+)\sTeams", key):

                if not row[key]:
                    continue

                order = m.group(1)
                team_names = re.split(r"\s*[,|;]\s*", row[key])

                duration_key = f"Call Distribution Group {order} Duration"
                if duration_key not in row:
                    raise ValueError(f"{duration_key} not found")

                groups.append(
                    dict(agentGroups=team_names, order=order, duration=row[duration_key])
                )

        return groups


@reg.browse_service("wxcc", "queues")
class WxccQueueBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WxccQueueModelBuilder(self.client)

        for resp in self.client.queues.list():
            model = builder.build_model(resp)
            row = model.dict()
            row["detail_id"] = resp["id"]
            row["call_distribution_groups_count"] = len(resp.get("callDistributionGroups", []))
            rows.append(row)

        return rows


@reg.detail_service("wxcc", "queues")
class WxccQueueDetailSvc(DetailSvc):

    def run(self):
        builder = WxccQueueModelBuilder(self.client)
        resp = self.client.queues.get(self.browse_row["detail_id"])
        return builder.build_detailed_model(resp)


@reg.export_service("wxcc", "queues")
class WxccQueueExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = wm.WxccQueue.schema()["data_type"]
        builder = WxccQueueModelBuilder(self.client)

        for resp in self.client.queues.list():
            try:
                model = builder.build_detailed_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WxccQueueModelBuilder:
    def __init__(self, client):
        self.client = client
        self.team_map = {}
        self.audiofile_map = {}

    @staticmethod
    def build_model(resp: dict):
        summary_data = {k: v for k, v in resp.items() if k != "callDistributionGroups"}
        return wm.WxccQueue.safe_build(**summary_data, callDistributionGroups=[])

    def build_detailed_model(self, resp: dict):
        groups = self.build_call_distribution_groups(
            resp.pop("callDistributionGroups", [])
        )
        music_in_queue_file = self.get_audiofile_name(
            resp.get("defaultMusicInQueueMediaFileId")
        )
        return wm.WxccQueue.safe_build(
                callDistributionGroups=groups,
                music_in_queue_file=music_in_queue_file,
                **resp,
        )

    def build_call_distribution_groups(self, resp_groups):
        groups = []

        for item in resp_groups:
            team_names = [self.get_team_name(a["teamId"]) for a in item["agentGroups"]]
            groups.append(
                wm.WxccCallDistributionGroup(
                    agentGroups=team_names,
                    order=item["order"],
                    duration=item["duration"],
                )
            )

        return groups

    def get_team_name(self, team_id):
        if team_id not in self.team_map:

            self.team_map = {team["id"]: team for team in self.client.teams.list()}

        match = self.team_map.get(team_id, {})
        return match.get("name", "NOTFOUND")

    def get_audiofile_name(self, audiofile_id):
        if not audiofile_id:
            return ""

        if audiofile_id not in self.audiofile_map:

            self.audiofile_map = {
                file["id"]: file for file in self.client.audio_files.list()
            }

        match = self.audiofile_map.get(audiofile_id, {})
        return match.get("name", "NOTFOUND")
