#!/usr/bin/env python
import os
import click
import flask_migrate
from . import models
from pathlib import Path
from .app import db, create_app
from flask.cli import AppGroup


ADMIN_ROLES = ["Admin"]
ALL_ROLES = ["Admin"]


cfg_name = os.getenv("FLASK_ENV") or "default"
app = create_app(cfg_name)

setup_cli = AppGroup("setup", short_help="Zeus Database Setup")


@setup_cli.command("all")
@click.option("--postgres-user", default=None, envvar="POSTGRES_USER", help="Postgres admin user")
@click.option("--postgres-password", default=None, envvar="POSTGRES_PASSWORD", help="Postgres admin password")
@click.option("--zeus-admin-email", default=None, envvar="ZEUS_ADMIN_EMAIL", help="Default Zeus admin email")
@click.option("--zeus-admin-password", default=None, envvar="ZEUS_ADMIN_PASSWORD", help="Default Zeus admin password")
def setup_all(postgres_user, postgres_password, zeus_admin_email, zeus_admin_password):
    """
    Create zeus database and create default admin account and roles.
    """
    _setup_postgres(postgres_user, postgres_password)
    _setup_auth(zeus_admin_email, zeus_admin_password)
    _setup_orgs()


@setup_cli.command("postgres")
@click.option("--postgres-user", default=None, envvar="POSTGRES_USER", help="Postgres admin user")
@click.option("--postgres-password", default=None, envvar="POSTGRES_PASSWORD", help="Postgres admin password")
def setup_postgres(postgres_user, postgres_password):
    """
    Create owner account and database based on environment variables.
    """
    _setup_postgres(postgres_user, postgres_password)


def _setup_postgres(postgres_user, postgres_password):
    from .deploy import create_db, fix_org_type_id_auto_increment
    if postgres_user and postgres_password:
        create_db(postgres_user, postgres_password)
    flask_migrate.upgrade()
    fix_org_type_id_auto_increment()
    click.echo(f"Zeus Postgres Setup Complete")


@setup_cli.command("auth")
@click.option("--zeus-admin-email", default=None, envvar="ZEUS_ADMIN_EMAIL", help="Default Zeus admin email")
@click.option("--zeus-admin-password", default=None, envvar="ZEUS_ADMIN_PASSWORD", help="Default Zeus admin password")
def setup_auth(zeus_admin_email, zeus_admin_password):
    """
    Create default admin login and default roles.
    """
    _setup_auth(zeus_admin_email, zeus_admin_password)


def _setup_auth(zeus_admin_email, zeus_admin_password):
    from .deploy import auth_setup
    db.create_all()
    if zeus_admin_email and zeus_admin_password:
        auth_setup(zeus_admin_email, zeus_admin_password, ADMIN_ROLES, ALL_ROLES)
        db.session.commit()
        click.echo("Zeus Auth Setup Complete")
    else:
        click.echo("Zeus Auth Setup Skipped")


@setup_cli.command("orgs")
def setup_orgs():
    """
    Populate org_type table
    if found in env
    """
    _setup_orgs()


def _setup_orgs():
    db.create_all()
    models.OrgType.populate()
    db.session.commit()
    click.echo("Zeus Orgs Setup Complete")


def get_token(org_name):
    return models.ProvisioningOrg.query.filter_by(name=org_name).first().access_token


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "models": models,
        "User": models.User,
        "Role": models.Role,
        "ProvisioningOrg": models.ProvisioningOrg,
        "Org": models.ProvisioningOrg,
        "get_token": get_token,
    }


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "models": models,
        "User": models.User,
        "Role": models.Role,
        "ProvisioningOrg": models.ProvisioningOrg,
    }


@setup_cli.command("help_docs")
def setup_help_docs():
    from .deploy import build_help_docs
    help_docs_path = Path("help_docs/docs")
    build_help_docs(help_docs_path)


app.cli.add_command(setup_cli)
