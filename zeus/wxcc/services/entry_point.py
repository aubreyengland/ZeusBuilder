from zeus import registry as reg
from .shared import WxccBulkSvc
from zeus.wxcc import wxcc_models as wm
from zeus.services import BrowseSvc, ExportSvc
from zeus.wxcc.wxcc_models import WxccEntryPoint


@reg.bulk_service("wxcc", "entry_points", "CREATE")
class WxccEntryPointCreateSvc(WxccBulkSvc):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.entry_points.create(payload)

    def build_payload(self):
        payload = self.model.to_payload(drop_unset=True)
        if self.model.moh_name:
            moh = self.lookup.audio_file(name=self.model.moh_name)
            payload["musicOnHoldId"] = moh["id"]
        if self.model.queue_name:
            queue = self.lookup.queue(name=self.model.queue_name)
            payload["outdialQueueId"] = queue["id"]
        return payload


@reg.bulk_service("wxcc", "entry_points", "UPDATE")
class WxccEntryPointUpdateSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.entry_point(self.model.name)
        payload = self.build_payload()
        self.client.entry_points.update(self.current["id"], payload)

    def build_payload(self):
        exclude = {}
        if self.model.channelType != "SOCIAL_CHANNEL":
            exclude = {"socialChannelType", "assetId", "imiOrgType"}

        payload = self.model.to_payload(exclude=exclude)
        payload["id"] = self.current["id"]
        if self.model.moh_name:
            moh = self.lookup.audio_file(name=self.model.moh_name)
            payload["musicOnHoldId"] = moh["id"]
        if self.model.queue_name:
            queue = self.lookup.queue(name=self.model.queue_name)
            payload["outdialQueueId"] = queue["id"]
        return payload


@reg.bulk_service("wxcc", "entry_points", "DELETE")
class WxccEntryPointDeleteSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.entry_point(self.model.name)
        self.client.entry_points.delete(self.current["id"])


@reg.browse_service("wxcc", "entry_points")
class WxccEntryPointBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WxccEntryPointModelBuilder(self.client)

        for resp in self.client.entry_points.list():
            model = builder.build_model(resp)
            rows.append(model.dict())

        return rows


@reg.export_service("wxcc", "entry_points")
class WxccEntryPointExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = wm.WxccEntryPoint.schema()["data_type"]
        builder = WxccEntryPointModelBuilder(self.client)

        for resp in self.client.entry_points.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WxccEntryPointModelBuilder:
    """
    Collect Webex Contact Center entry point details and create
    models for browse/export operations.

    The LIST request only provides MOH id and Queue id so API requests
    for each entry point is required to get the names.
    """

    def __init__(self, client):
        self.client = client
        self._moh_map: dict | None = None
        self._queue_map: dict | None = None

    def build_model(self, resp: dict):
        summary_data = {k: v for k, v in resp.items()}
        moh = {}
        queue = {}
        try:
            moh = self.moh_map[resp["musicOnHoldId"]]
        except Exception:
            pass  # Ignore missing MOH
        # Out Dial Queue is only for 'OUTBOUND' entry points
        if str(resp["entryPointType"]).lower() == 'outbound':
            try:
                queue = self.queue_map[resp["outdialQueueId"]]
            except Exception:
                pass  # Ignore missing Queue
        return WxccEntryPoint.safe_build(moh_name=moh.get("name", ""),
                                         queue_name=queue.get("name", ""),
                                         **summary_data)

    @property
    def moh_map(self) -> dict:
        """
        Upon first call, perform an audio_file LIST request to
        create a mapping for audio file IDs to audio file objects then
        return the audio object matching the provided audio file ID.
        """
        if self._moh_map is None:
            self._moh_map = {moh["id"]: moh for moh in self.client.audio_files.list()}

        return self._moh_map

    @property
    def queue_map(self) -> dict:
        """
        Upon first call, perform a queue LIST request to
        create a mapping for queue IDs to queue objects then
        return the queue object matching the provided queue ID.
        """
        if self._queue_map is None:
            self._queue_map = {q["id"]: q for q in self.client.queues.list()}

        return self._queue_map









