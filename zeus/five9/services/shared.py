import logging
from ..five9_client import Five9
from zeus.services import BulkSvc, BulkTask, SvcClient

log = logging.getLogger(__name__)


class Five9BulkSvc(BulkSvc):
    client: Five9


class Five9BulkTask(BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: Five9BulkSvc = svc


class Five9SvcClient(SvcClient):
    tool = "five9"
    client_cls = Five9
