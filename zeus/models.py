import datetime
from .app import db
from os import getenv
from uuid import uuid4
from sqlalchemy.sql import func
from .exceptions import ZeusCmdError
from sqlalchemy.types import VARCHAR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import CheckConstraint, Index
from flask_security import UserMixin, RoleMixin
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy_utils import ScalarListType, StringEncryptedType
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method


def aes_encrypt_key():
    # Use Flask Secret Key for Encrypted Type
    return getenv("SECRET_KEY")


class RolesUsers(db.Model):
    __tablename__ = "roles_users"
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column("user_id", db.Integer(), db.ForeignKey("user.id"))
    role_id = db.Column("role_id", db.Integer(), db.ForeignKey("role.id"))


class Role(db.Model, RoleMixin):
    __tablename__ = "role"
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    # A comma separated list of strings
    permissions = db.Column(db.UnicodeText, nullable=True)
    update_datetime = db.Column(
        type_=db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=datetime.datetime.utcnow,
    )
    users = db.relationship(
        "User", secondary="roles_users", back_populates="roles"
    )


class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    # Username is optional
    username = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean(), nullable=False)
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False)
    confirmed_at = db.Column(db.DateTime())
    last_login_at = db.Column(db.DateTime())
    current_login_at = db.Column(db.DateTime())
    last_login_ip = db.Column(db.String(64))
    current_login_ip = db.Column(db.String(64))
    login_count = db.Column(db.Integer)
    create_datetime = db.Column(type_=db.DateTime, nullable=False, server_default=func.now())
    update_datetime = db.Column(
        type_=db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=datetime.datetime.utcnow,
    )

    orgs = db.relationship("ProvisioningOrg", back_populates="user")
    oauth_apps = db.relationship("OAuthApp", back_populates="user")
    events = db.relationship("Event", back_populates="user")
    job_data = db.relationship("JobData", back_populates="user")
    roles = db.relationship("Role", secondary="roles_users", back_populates="users")

    @hybrid_property
    def display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email

    def add_event(
            self,
            job_id: str,
            org_id: int,
            result: str,
            action: str,
            data_type: str,
            entity: str,
            error: str = "",
    ):
        event = Event(
            job_id=job_id,
            org_id=org_id,
            action=action,
            data_type=data_type,
            entity=entity,
            result=result,
            error=error,
            user=self,
        )
        db.session.add(event)
        db.session.commit()

    @property
    def is_admin(self):
        return 'Admin' in [r.name for r in self.roles]

    @property
    def create_timestamp(self):
        if self.create_datetime:
            return self.create_datetime.timestamp()

    @property
    def current_login_timestamp(self):
        if self.current_login_at:
            return self.current_login_at.timestamp()

    @hybrid_method
    def events_for_job(self, job_id: str):
        return Event.query.filter_by(user_id=self.id).filter_by(job_id=job_id)

    @hybrid_method
    def active_org(self, org_type: str, org_id: str):
        active_org = next(
            (org for org in self.orgs_of_type(org_type)
             if str(org.id) == str(org_id)),
            None,
        )
        if not active_org:
            raise ZeusCmdError(f"{org_type} Org Not Found")

        return active_org

    @hybrid_method
    def orgs_of_type(self, org_type):
        """
        Convenience method to return ProvisioningOrg instances of the provided
        type owned by the current user
        """
        return (
            ProvisioningOrg.orgs_of_type(org_type)
            .filter(ProvisioningOrg.user_id == self.id)
        )

    @hybrid_method
    def available_oauth_apps(self, org_type: str, include_global = True) -> list["OAuthApp"]:
        """
        Return OAuthApp records that should be available
        to the user when creating/editing an organization
        for the org_type.

        These include records related to the current user and, optionally,
        those flagged as global.

        Returns:
            (list) List of OAuthApp records with user apps listed first
        """
        user_apps = (
            OAuthApp.query.join(OrgType)
            .filter(OrgType.name == org_type)
            .filter(OAuthApp.user_id == self.id)
            .order_by(OAuthApp.name)
        )
        global_apps = (
            OAuthApp.query.join(OrgType)
            .filter(OrgType.name == org_type)
            .filter(OAuthApp.is_global == True)
            .order_by(OAuthApp.name)
        )
        available_apps = [record for record in user_apps]
        if include_global:
            available_apps.extend([record for record in global_apps])

        return available_apps


# Generate random string for state value on update
def oauth_state():
    return uuid4().hex


# Use db-specific functions to generate random value for
# state field when record created.
class PerEngineRandomState(FunctionElement):
    name = "random_state"
    type = VARCHAR()


@compiles(PerEngineRandomState)
def postgres_state(element, compiler, **kwargs):
    return "substr(md5(random()::text), 0, 16)"


@compiles(PerEngineRandomState, "sqlite")
def sqlite_state(element, compiler, **kwargs):
    return "lower(hex(randomblob(16)))"


ORG_TYPES = [
    {"name": "five9", "abbr": "Five9", "title": "Five9", "is_oauth": False},
    {"name": "wxcc", "abbr": "WxCC", "title": "Webex Contact Center", "is_oauth": True},
    {"name": "zoom", "abbr": "Zoom", "title": "Zoom Phone", "is_oauth": True},
    {"name": "zoomcc", "abbr": "ZoomCC", "title": "Zoom Contact Center", "is_oauth": True},
    {"name": "msteams", "abbr": "MsTeams", "title": "MS Teams", "is_oauth": True},
    {"name": "wbxc", "abbr": "Wbxc", "title": "Webex Calling", "is_oauth": True},
    # {"name": "rc", "abbr": "Rc", "title": "Ring Central", "is_oauth": False},
]


class OrgType(db.Model):
    __tablename__ = "org_type"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True)
    abbr = db.Column(db.String(), unique=True)
    title = db.Column(db.String())
    is_oauth = db.Column(db.Boolean(), nullable=False)

    orgs = db.relationship("ProvisioningOrg", back_populates="org_type")
    oauth_apps = db.relationship("OAuthApp", back_populates="org_type")

    @classmethod
    def populate(cls):
        for item in ORG_TYPES:
            if not cls.query.filter_by(name=item["name"]).first():
                db.session.add(OrgType(**item))
        db.session.commit()


class OAuthApp(db.Model):
    __tablename__ = "oauth_app"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    client_id = db.Column(db.String)
    client_secret = db.Column(StringEncryptedType(db.String, key=aes_encrypt_key))
    redirect_uri = db.Column(db.String)
    scopes = db.Column(ScalarListType(), default="")
    api_endpoint = db.Column(db.String, default="")
    auth_endpoint = db.Column(db.String, default="")
    token_endpoint = db.Column(db.String, default="")
    is_global = db.Column(db.Boolean, default=False, nullable=False)

    org_type_id = db.Column(db.Integer, db.ForeignKey("org_type.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    org_type = db.relationship("OrgType", back_populates="oauth_apps")
    user = db.relationship("User", back_populates="oauth_apps")

    orgs = db.relationship("ProvisioningOrg", back_populates="oauth")

    # Need separate unique constraint for records with a user_id
    # and records without.
    __table_args__ = (
        Index(
            "uq_oauth_app_name_user_id",
            "name",
            "user_id",
            unique=True,
            postgresql_where=user_id.isnot(None)
        ),
        Index(
            "uq_oauth_app_name_global",
            "name",
            unique=True,
            postgresql_where=user_id.is_(None)
        ),
    )

    @classmethod
    def create(cls, name, org_type, **kwargs):
        """
        Convenience method to create an OAuth app with an org_type or OrgType instance.
        Object is added to session but not committed. It is up to the calling code to eventually
        call commit.
        """
        if isinstance(org_type, str):
            org_type = OrgType.query.filter_by(name=org_type).one()

        oauth = cls(name=name, org_type=org_type, **kwargs)
        db.session.add(oauth)
        return oauth


class ProvisioningOrg(db.Model):
    __tablename__ = "provisioning_org"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    api_user = db.Column(db.String(200))
    api_password = db.Column(StringEncryptedType(db.String, key=aes_encrypt_key))
    access_token = db.Column(StringEncryptedType(db.String, key=aes_encrypt_key))
    refresh_token = db.Column(StringEncryptedType(db.String, key=aes_encrypt_key))
    access_expires = db.Column(db.Float)
    refresh_expires = db.Column(db.Float)
    state = db.Column(db.String, server_default=PerEngineRandomState(), onupdate=oauth_state, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    org_type_id = db.Column(db.Integer, db.ForeignKey("org_type.id"), nullable=False)
    oauth_id = db.Column(db.Integer, db.ForeignKey("oauth_app.id"), nullable=True)

    user = db.relationship("User", back_populates="orgs")
    org_type = db.relationship("OrgType", back_populates="orgs")
    oauth = db.relationship("OAuthApp", back_populates="orgs")
    events = db.relationship("Event", back_populates="org")

    @classmethod
    def create(cls, name, org_type, **kwargs):
        """
        Convenience method to create a provisioning_org with an org_type or OrgType instance.
        Object is added to session but not committed. It is up to the calling code to eventually
        call commit.
        """
        if isinstance(org_type, str):
            org_type = OrgType.query.filter_by(name=org_type).one()

        org = ProvisioningOrg(name=name, org_type=org_type, **kwargs)
        db.session.add(org)
        return org

    @hybrid_method
    def orgs_of_type(self, org_type: str):
        """
        Convenience method to return ProvisioningOrg instances of the provided
        type.
        """
        return (
            ProvisioningOrg.query.join(ProvisioningOrg.org_type, aliased=True)
            .filter(OrgType.name.ilike(org_type))  # noqa
        )


def _timestamp():
    return datetime.datetime.utcnow().timestamp()


class Event(db.Model):
    __tablename__ = "event"
    id = db.Column(db.Integer, primary_key=True)
    # Identifies all events submitted at the same time
    job_id = db.Column(db.String, nullable=False, unique=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("provisioning_org.id"))
    result = db.Column("result", db.String)
    error = db.Column(db.String, nullable=True)
    # Get, Delete, Update, Create.
    action = db.Column(db.String, nullable=False)
    data_type = db.Column(db.String, nullable=False)
    # The user deleted, name of prompt updated, etc.
    entity = db.Column(db.String, nullable=True)
    timestamp = db.Column(db.Float, nullable=False, default=_timestamp)

    user = db.relationship("User", back_populates="events")
    org = db.relationship("ProvisioningOrg", back_populates="events")

    __table_args__ = (
        CheckConstraint(result.in_(["Success", "Fail", "Info"]), name="ck_event_result"),  # noqa
    )


class JobData(db.Model):
    __tablename__ = "job_data"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.Float, nullable=False, default=_timestamp)
    job_id = db.Column(db.String, nullable=False, unique=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    data_type = db.Column(db.String, nullable=False)
    data = db.Column(db.JSON, default={})

    user = db.relationship("User", back_populates="job_data")

    def __init__(self, job_id, user_id, data_type, data):
        """Prevents type checker warnings"""
        self.job_id = job_id
        self.user_id = user_id
        self.data_type = data_type
        self.data = data
