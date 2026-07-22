import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import contextmanager

# Ensure directory localdb exists
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'localdb')
os.makedirs(DB_DIR, exist_ok=True)

# Ensure directory uploads exists
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, 'workflow.db')

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "DATABASE_URL" in st.secrets:
                DATABASE_URL = st.secrets["DATABASE_URL"]
            elif "email" in st.secrets and "DATABASE_URL" in st.secrets["email"]:
                DATABASE_URL = st.secrets["email"]["DATABASE_URL"]
    except Exception:
        pass

if not DATABASE_URL:
    secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.streamlit', 'secrets.toml')
    if os.path.exists(secrets_path):
        try:
            import tomllib
            with open(secrets_path, "rb") as f:
                secrets_data = tomllib.load(f)
                if "DATABASE_URL" in secrets_data:
                    DATABASE_URL = secrets_data["DATABASE_URL"]
                elif "email" in secrets_data and "DATABASE_URL" in secrets_data["email"]:
                    DATABASE_URL = secrets_data["email"]["DATABASE_URL"]
        except Exception:
            pass

if not DATABASE_URL:
    secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.streamlit', 'secrets.toml')
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL") and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            DATABASE_URL = val
                            break
        except Exception:
            pass

if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{DB_PATH}"

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
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    db = SessionLocal()
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
    
    # Auto-migrations for DB columns
    from sqlalchemy import text
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
