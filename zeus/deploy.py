import logging
from os import getenv
from pathlib import Path
from flask import current_app
from datetime import datetime
from flask_security import hash_password
from sqlalchemy import text, create_engine
from sqlalchemy.exc import OperationalError
from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)


def get_env():
    """
    Read the environment variables relevant to database setup and return as a dictionary.
    """
    return dict(
        uri=getenv("DB_URI", ""),
        user=getenv("DB_USER", ""),
        host=getenv("DB_HOST", ""),
        port=getenv("DB_PORT", ""),
        password=getenv("DB_PASSWORD", ""),
        name=getenv("DB_NAME", ""),
        engine=getenv("DB_ENGINE", ""),
        admin=getenv("POSTGRES_USER", ""),
        admin_pw=getenv("POSTGRES_PASSWORD", ""),
    )


def sqla_uri(**kwargs):
    uri = kwargs.get("uri")

    if not uri:
        user = kwargs.get("user")
        host = kwargs.get("host")
        port = kwargs.get("port")
        password = kwargs.get("password")
        name = kwargs.get("name")
        engine = kwargs.get("engine")

        if engine.lower() == "postgresql":
            uri = f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif engine.lower() == "sqlite":
            uri = f"sqlite:///{name}.sqlite"
        else:
            raise ValueError(f"Database engine {engine} not recognized")

    return uri


def create_db(postgres_user, postgres_password, echo=False):
    """
    Create the owner account and database in the postgres database
    if they do not already exist.

    Args:
        postgres_user (str): Postgres admin user
        postgres_password (str): Postgres admin password
        echo (bool): echo sqlalchemy engine commands to stdout
    """
    dbenv = get_env()
    if dbenv["engine"] == "postgresql":
        log.info(f"Checking if postgresql DB {dbenv['name']} exists...")

        db_uri = sqla_uri(
            engine="postgresql",
            user=postgres_user,
            password=postgres_password,
            name="postgres",
            host=dbenv["host"],
            port=dbenv["port"],
        )
        engine = create_engine(db_uri, isolation_level="AUTOCOMMIT", echo=echo)

        pg_create_owner(engine, dbenv["user"], dbenv["password"])
        pg_create_db(engine, dbenv["name"], dbenv["user"])

    elif dbenv["engine"] == "sqlite":
        pass
    else:
        raise NotImplementedError(
            f"Create scripts for {dbenv['engine']} not implemented"
        )


def pg_create_owner(engine, user, password):
    """
    Create an owner role in the postgres database.

    Args:
        engine (Sqlalchemy.Engine): Engine with connection to database
        user (str): Database owner
        password (str): Database owner password
    """
    exists_stmt = text("SELECT FROM pg_catalog.pg_roles WHERE rolname = :user")
    create_stmt = f"CREATE ROLE {user} LOGIN PASSWORD '{password}'"
    if not _exists(engine, exists_stmt, user=user):
        with engine.begin() as conn:
            conn.execute(create_stmt)
            log.info(f"DB owner account {user} created")


def pg_create_db(engine, name, user):
    """
    Create a database of the provided name using the provided engine and make
    the provided user the owner.

    Args:
        engine (Sqlalchemy.Engine): Engine with connection to database
        name (str): Database name
        user (str): Database owner
    """
    exists_stmt = text("SELECT FROM pg_catalog.pg_database WHERE datname= :name")
    create_stmt = f"CREATE DATABASE {name} WITH OWNER {user} ENCODING 'UTF8';"
    if not _exists(engine, exists_stmt, name=name):

        with engine.begin() as conn:
            conn.execute(create_stmt)
            log.info(f"Database {name} with owner {user} created")
    else:
        log.info(f"Database {name} with owner {user} already exists")


def set_db_owner(engine, name, user):
    """
    Set the owner on an existing or newly-created database.

    Args:
        engine (Sqlalchemy.Engine): Engine with connection to database
        name (str): Database name
        user (str): Database owner
    """
    stmt = f"ALTER DATABASE :name OWNER TO {user}"
    with engine.begin() as conn:
        conn.execute(stmt)
    log.info(f"DB {name} owner set to {user}")


def fix_org_type_id_auto_increment():
    """
    Fix auto incrementing of the org_type table id column that was broke
    by setting static IDs in a previous migration.

    This is done by setting the next value in the 'org_type_id_seq' table to the next available
    integer based on the current org_type table.

    """
    dbenv = get_env()
    engine = create_engine(sqla_uri(**dbenv))

    stmt = """select setval('org_type_id_seq', coalesce((select max(id)+1 from org_type), 1), false);"""
    with engine.begin() as conn:
        res = conn.execute(stmt)
    log.warning(f"DB table 'org_type'id sequence reset to {res.scalar()}")


def _exists(engine, stmt, **bind_params):
    """
    Execute the provided statement using the provided engine.
    Return True if rows are returned or False if not.

    Args:
        engine (Sqlalchemy.Engine): Engine with connection to database
        stmt (str, Sqlalchemy.TextClause): String or TextClause to execute
        **bind_params: optional params for Text Clause

    Returns:
        (bool): True if row returned False if not
    """
    with engine.begin() as conn:
        res = conn.execute(stmt, **bind_params)
        count = res.rowcount
        return True if count else False


def auth_setup(admin_email, admin_pw, admin_roles, all_roles):
    """
    Create a row in the role table for each role name in the all_roles list.
    Create the default admin user account using the arguments provided.
    Args:
        admin_email (str): Admin account email address
        admin_pw (str): Admin account password
        admin_roles (list): List of roles to assign to the admin account
        all_roles (list): List of roles to create.
    """
    datastore = current_app.extensions["security"].datastore
    roles = {}
    for role_name in all_roles:
        roles[role_name] = datastore.find_or_create_role(role_name)

    if not datastore.find_user(email=admin_email):
        log.info(f"Creating default admin user {admin_email}.")
        datastore.create_user(
            email=admin_email,
            first_name="Zeus",
            last_name="Admin",
            password=hash_password(admin_pw),
            confirmed_at=datetime.utcnow(),
            roles=[roles[k] for k in roles if k in admin_roles],
            active=True,
        )
    else:
        log.info(f"Default admin user {admin_email} already exists")


def populate_table(session, rows, model):
    """
    Populate the table represented by the Sqlalchemy model with a row
    from the dictionaries in the rows iterator.

    Args:
        session (Sqlalchemy.Session): session with connection to database
        rows (Iterator): Iterator of dictionaries formatted for insert
        model (Sqlalchemy.DeclarativeMeta) Sqlalchemy model
    """
    table_name = model.__tablename__
    for row in rows:
        try:
            session.merge(model(**row))
        except Exception as ex:
            log.error(f"{table_name} insert failed: {ex}")
            session.rollback()
            return
        finally:
            session.commit()
    log.info(f"{table_name} populated with {session.query(model).count()} rows")


def sqlite_enable_wal(engine):
    """Enables write-ahead logging to avoid DB locks on long operations"""
    stmt = "PRAGMA journal_mode=WAL;"
    failed = False
    try:
        with engine.connect() as connection:
            if not connection.in_transaction():
                connection.execute(stmt)
                log.info("WAL mode enabled")
            else:
                failed = True
    except OperationalError:
        failed = True
    if failed:
        log.info("Cannot enable WAL mode, operating in DELETE mode")


def build_help_docs(help_docs_path):
    """
    Extract help doc-related information from the model schemas
    and provide this, along with the template and output file location
    to the render function.

    Args:
        help_docs_path (Path): Location of mkdocs structure
    """
    from zeus import registry
    from zeus.shared.data_type_models import DataTypeDoc

    default_template_file = "data_type.jinja2"

    for tool in ["five9", "zoom", "wbxc", "wxcc", "zoomcc", "msteams"]:
        for data_type, model in registry.get_data_types(tool, "help_doc").items():
            doc: DataTypeDoc = model.model_doc()
            schema = model.schema()

            template_file = doc.doc_template or default_template_file
            output_file = help_docs_path / tool / f"{data_type}.md"

            render_help_doc(
                template_path=help_docs_path,
                template_file=template_file,
                output_file=output_file,
                title=doc.title,
                description=doc.description,
                table_fields=doc.doc_fields,
                actions=doc.bulk_actions,
                tool=tool,
                **doc.doc_extra
            )


def render_help_doc(template_path: Path, template_file: str, output_file: Path, **render_kw):
    """
    Create config output text file using Jinja2 templates

    Args:
        template_path (Path): Parent directory of template file
        template_file (str): name of template in template_path
        output_file (Path): Full path of file to create with rendered template
    """
    loader = FileSystemLoader(template_path)

    env = Environment(
        loader=loader,
        trim_blocks=True,
        keep_trailing_newline=True,
    )

    template = env.get_template(template_file)
    rendered = template.render(**render_kw)

    with open(output_file, 'w') as fh:
        fh.write(rendered)
