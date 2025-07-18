import logging
from rq.queue import Queue
from rq.job import Job, JobStatus
from rq.utils import import_attribute
from rq.timeouts import JobTimeoutException
from rq.defaults import DEFAULT_RESULT_TTL, DEFAULT_FAILURE_TTL

log = logging.getLogger(__name__)


def handle_exc(job, exc_type, exc_value, traceback):
    """
    Rq worker exception handler to make a useful
    error message available for the alert in the response.
    Check the for a 'message' attribute (as will be present
    on any Zeus custom exceptions) and add this to the job's
    meta dictionary as the error_message. Otherwise, use the
    exception string rep as the error_message value.

    Return True to prevent additional exception handling by the
    worker.
    """
    message = ""

    if isinstance(exc_value, JobTimeoutException):
        message = str(exc_value)
    else:
        message = getattr(exc_value, "message", f"Unhandled Error: {exc_value}")

    job.meta["error_message"] = message
    job.save_meta()

    return True


class ZeusJob(Job):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dependencies = []
        self.progress_key = "progress_id"

    @property
    def status(self) -> str:
        if any([self.is_failed, self.is_stopped, self.is_canceled]):
            return "failed"
        return self.get_status()

    @property
    def progress(self) -> dict:
        """
        Return dependent job status as a dictionary
        keyed by a value from `job.meta` to allow individual progress indications in the view

        Keys are the `job.get_meta()[self.progress_key]`
        Values are a tuple of (status, message)

        The value is determined by:
        - If job is not finished, use `job.get_status()`, ""
        - If job is finished AND job return_value is a Successful SvcResponse, use `job.get_status()`, ""
        - if job is finished AND job return_value is a Failure SvcResponse, use 'failure', `SvcResponse.message`

        Skip jobs that do not include the progress_key in the meta attribute
        """
        progress = {}
        for job in self.dependencies():
            key = job.get_meta().get(self.progress_key)
            if not key:
                continue
            progress[key] = self._progress_for_dependent_job(job)
        return progress

    def dependencies(self):
        if self._dependency_ids:
            if not self._dependencies:
                self._dependencies = [
                    self.fetch(
                        dep_id, connection=self.connection, serializer=self.serializer
                    )
                    for dep_id in self._dependency_ids
                ]
        return self._dependencies

    @staticmethod
    def _progress_for_dependent_job(job) -> tuple:
        if job.is_finished:
            rv = job.return_value()
            # duck-type SvcResponse
            if rv and hasattr(rv, "ok"):
                if not rv.ok:
                    return JobStatus.FAILED.value, rv.message
        return job.get_status(), ""


class ZeusQueue(Queue):
    job_class = ZeusJob


class JobQueue(object):
    """
    Flask plugin to set up RQ and redis based on Flask config variables.
    """
    queued_ttl = None
    running_timeout = None
    result_ttl = DEFAULT_RESULT_TTL
    failure_ttl = DEFAULT_FAILURE_TTL
    result_ttl_browse = DEFAULT_RESULT_TTL
    result_ttl_export = DEFAULT_RESULT_TTL
    redis_url = "redis://localhost:6379"
    connection_class = "redis.StrictRedis"
    queue_names = ["default"]
    queue_class = "zeus.job_queue.ZeusQueue"
    worker_class = "rq.worker.Worker"
    job_class = "zeus.job_queue.ZeusJob"

    def __init__(self, app=None, **kwargs):
        self._is_async = None
        self._queue_instances = {}
        self._connection = None
        self.default_timeout = Queue.DEFAULT_TIMEOUT

        if app is not None:
            self.init_app(app)

    @property
    def connection(self):
        if self._connection is None:
            connection_class = import_attribute(self.connection_class)
            self._connection = connection_class.from_url(self.redis_url)  # noqa
        return self._connection

    @property
    def default_queue_name(self):
        if self.queue_names:
            return self.queue_names[0]
        return "default"

    def init_app(self, app):
        """
        Initialize the app, e.g. can be used if factory pattern is used.
        """
        self.redis_url = app.config.setdefault(
            "REDIS_URL",
            self.redis_url,
        )
        self.connection_class = app.config.setdefault(
            "RQ_CONNECTION_CLASS",
            self.connection_class,
        )
        self.queue_names = app.config.setdefault(
            "RQ_QUEUE_NAMES",
            self.queue_names,
        )
        self.queue_class = app.config.setdefault(
            "RQ_QUEUE_CLASS",
            self.queue_class,
        )
        self.worker_class = app.config.setdefault(
            "RQ_WORKER_CLASS",
            self.worker_class,
        )
        self.job_class = app.config.setdefault(
            "RQ_JOB_CLASS",
            self.job_class,
        )
        self.running_timeout = app.config.setdefault(
            "RQ_JOB_RUNNING_TIMEOUT",
            self.running_timeout,
        )
        self.queued_ttl = app.config.setdefault(
            "RQ_JOB_QUEUED_TTL",
            self.queued_ttl,
        )
        self.result_ttl_browse = app.config.setdefault(
            "RQ_JOB_RESULT_TTL_BROWSE",
            self.result_ttl_browse,
        )
        self.result_ttl_export = app.config.setdefault(
            "RQ_JOB_RESULT_TTL_EXPORT",
            self.result_ttl_export,
        )
        self.failure_ttl = app.config.setdefault("RQ_JOB_FAILURE_TTL", self.failure_ttl)
        _async = app.config.setdefault("RQ_ASYNC", True)
        if self._is_async is None:
            self._is_async = _async

        app.extensions = getattr(app, "extensions", {})
        app.extensions["job_queue"] = self

    def get_queue(self, name=None) -> ZeusQueue:
        """
        Returns an RQ queue instance with the given name,
        or the default_queue_name if a name is not provided.
        """
        if not name:
            name = self.default_queue_name

        queue = self._queue_instances.get(name)
        if queue is None:
            queue_cls = import_attribute(self.queue_class)

            queue = queue_cls(
                name=name,
                default_timeout=self.default_timeout,
                is_async=self._is_async,
                connection=self.connection,
                job_class=self.job_class,
            )

            self._queue_instances[name] = queue

        return queue

    def get_workers(self, *queue_names) -> list:
        """Return RQ worker instances for the given queue names"""
        workers = set()
        worker_cls = import_attribute(self.worker_class)

        if queue_names:
            queues = [self.get_queue(name) for name in queue_names]
            for queue in queues:
                for worker in worker_cls.all(queue=queue):  # noqa
                    workers.add(worker)
        else:
            for worker in worker_cls.all(connection=self.connection):  # noqa
                workers.add(worker)

        return list(workers)

    def get_job(self, job_id) -> ZeusJob:
        """
        Return the job matching the provided job_id or allow the
        JobNotFound exception to be raised.
        """
        job_cls = import_attribute(self.job_class)
        return job_cls.fetch(job_id, connection=self.connection)  # noqa

    def enqueue_job(self, f, queue_name=None, **kwargs) -> ZeusJob:
        """
        Place a new job on the queue for the provided queue_name
        using the provided function or callable, f, and the provided
        kwargs. Then return the job.

        The job will use the job timeout and TTLs from the Flask Config
        unless provided in the kwargs.
        """
        job_kw = self.job_timers()
        job_kw.update(kwargs)

        queue = self.get_queue(queue_name)
        return queue.enqueue(f=f, **job_kw)  # noqa

    def job_timers(self) -> dict:
        """
        Return a dictionary of RQ job timeout/TTL values from the Flask
        config.

        The keys match kwargs for the RQ Queue.enqueue method.
        """
        return {
            "ttl": self.queued_ttl,
            "result_ttl": self.result_ttl,
            "failure_ttl": self.failure_ttl,
            "job_timeout": self.running_timeout,
        }
