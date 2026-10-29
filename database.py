import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.sql.elements import TextClause
from contextlib import contextmanager

# Ensure directory localdb exists
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'localdb')
os.makedirs(DB_DIR, exist_ok=True)

# Ensure directory uploads exists
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, 'workflow.db')

from collections.abc import Mapping

def _extract_db_url():
    # 1. Environment variable
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    # 2. Streamlit secrets (safely handling AttrDict / Secrets objects)
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            sec = st.secrets
            # Top-level check
            try:
                if "DATABASE_URL" in sec:
                    return sec["DATABASE_URL"]
            except Exception:
                pass
            
            # Search inside all sections (e.g. [email], [database], etc.)
            try:
                for key in sec:
                    try:
                        section = sec[key]
                        if isinstance(section, (dict, Mapping)) or hasattr(section, "__getitem__"):
                            if "DATABASE_URL" in section:
                                return section["DATABASE_URL"]
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    # 3. Direct parsing of .streamlit/secrets.toml
    secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.streamlit', 'secrets.toml')
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL") and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    return None

DATABASE_URL = _extract_db_url() or f"sqlite:///{DB_PATH}"

# SQLAlchemy 2.1 defaults postgresql:// URLs to psycopg (v3), while this
# project installs psycopg2-binary. Select the installed driver explicitly.
if DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL.split("://", 1)[1]

if DATABASE_URL and "pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False, "timeout": 15}  # Needed for SQLite in multi-threaded Streamlit
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy import event

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:
            pass
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
        pool_pre_ping=True
    )

class PortalSession(Session):
    def flush(self, objects=None):
        if self.info.get("read_only") and (self.new or self.dirty or self.deleted):
            raise PermissionError("Su permiso es Lectura; no puede modificar datos.")
        return super().flush(objects)

    def execute(self, statement, *args, **kwargs):
        if self.info.get("read_only"):
            if isinstance(statement, (Insert, Update, Delete)):
                raise PermissionError("Su permiso es Lectura; no puede modificar datos.")
            if isinstance(statement, TextClause):
                sql = statement.text.lstrip().upper()
                if not sql.startswith(("SELECT", "SHOW", "EXPLAIN")):
                    raise PermissionError("Su permiso es Lectura; no puede modificar datos.")
        return super().execute(statement, *args, **kwargs)


@event.listens_for(PortalSession, "after_begin")
def set_read_only_transaction(session, transaction, connection):
    if session.info.get("read_only") and connection.dialect.name == "postgresql":
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=PortalSession)
Base = declarative_base()

@contextmanager
def get_db():
    db = SessionLocal()
    from permissions import can_write, current_user
    user = current_user()
    if user is not None and not can_write(user):
        db.info["read_only"] = True
    try:
        yield db
        db.commit()
    except BaseException as e:
        if e.__class__.__name__ in ["RerunException", "StopException"]:
            try:
                db.commit()
            except Exception:
                pass
            raise e
        db.rollback()
        raise e
    finally:
        db.close()

def init_db():
    # Dynamic imports of models to ensure they are registered in metadata
    import models
    Base.metadata.create_all(bind=engine)

    # Existing accounts retain write access; legacy administrators keep admin access.
    from sqlalchemy import inspect, text
    if "access_level" not in {column["name"] for column in inspect(engine).get_columns("wf_user")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE wf_user ADD COLUMN access_level VARCHAR(20) NOT NULL DEFAULT 'Escritura'"))
            conn.execute(text("""UPDATE wf_user SET access_level = 'Administrador'
                WHERE id IN (SELECT ur.user_id FROM wf_user_role ur
                             JOIN wf_role r ON r.id = ur.role_id
                             WHERE r.name = 'Administrador')"""))

    # Administrador is now a permission, not a user-assigned process role.
    # Keep the role itself because workflow nodes still reference it.
    with engine.begin() as conn:
        conn.execute(text("""UPDATE wf_user SET access_level = 'Administrador'
            WHERE access_level = 'Total' OR id IN (
                SELECT ur.user_id FROM wf_user_role ur
                JOIN wf_role r ON r.id = ur.role_id
                WHERE r.name = 'Administrador')"""))
        conn.execute(text("""DELETE FROM wf_user_role WHERE role_id IN (
            SELECT id FROM wf_role WHERE name = 'Administrador')"""))
    
    # Auto-migrations for DB columns
    migrations = [
        "ALTER TABLE wf_node ADD COLUMN sla_hours INTEGER;",
        "ALTER TABLE wf_node ADD COLUMN role_id INTEGER REFERENCES wf_role(id) ON DELETE SET NULL;",
        "ALTER TABLE wf_instance ADD COLUMN docnum VARCHAR(50);",
        "ALTER TABLE wf_instance ADD COLUMN internal_code VARCHAR(50);",
        "ALTER TABLE wf_node ADD COLUMN template_file_name VARCHAR(255);",
        "ALTER TABLE wf_node ADD COLUMN template_file_path VARCHAR(500);",
        "ALTER TABLE wf_node ADD COLUMN erp_query_id INTEGER REFERENCES wf_erp_query(id) ON DELETE SET NULL;",
        "ALTER TABLE wf_task ADD COLUMN docnum VARCHAR(50);",
        "ALTER TABLE wf_instance ADD COLUMN brand_id INTEGER REFERENCES wf_brand(id) ON DELETE SET NULL;"
    ]
    for stmt in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass

    # Purge any existing orphan transitions or tasks left from prior deletions
    with SessionLocal() as db_session:
        try:
            from models import WorkflowNode, WorkflowTransition, WorkflowTask, WorkflowInstance
            
            existing_node_ids = [n.id for n in db_session.query(WorkflowNode.id).all()]
            
            # 1. Purge transitions referencing deleted nodes
            orphan_transitions = db_session.query(WorkflowTransition).filter(
                (~WorkflowTransition.source_node_id.in_(existing_node_ids)) |
                (~WorkflowTransition.target_node_id.in_(existing_node_ids))
            ).all()
            if orphan_transitions:
                for t in orphan_transitions:
                    db_session.delete(t)
                db_session.commit()
                print(f"Purged {len(orphan_transitions)} orphan transitions from SQLite.")
                
            # 2. Purge tasks referencing deleted nodes
            orphan_tasks = db_session.query(WorkflowTask).filter(
                ~WorkflowTask.node_id.in_(existing_node_ids)
            ).all()
            if orphan_tasks:
                for tk in orphan_tasks:
                    db_session.delete(tk)
                db_session.commit()
                print(f"Purged {len(orphan_tasks)} orphan tasks from SQLite.")
        except Exception as e:
            print(f"Error purging orphan records: {str(e)}")
