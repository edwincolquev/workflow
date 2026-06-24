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
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Needed for SQLite in multi-threaded Streamlit
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    # Dynamic imports of models to ensure they are registered in metadata
    import models
    Base.metadata.create_all(bind=engine)
    
    # Auto-migrations for SQLite to avoid dropping data
    from sqlalchemy import text
    with engine.connect() as conn:
        # 1. Add sla_hours to wf_node
        try:
            conn.execute(text("ALTER TABLE wf_node ADD COLUMN sla_hours INTEGER;"))
        except Exception:
            pass
            
        # 1b. Add role_id to wf_node
        try:
            conn.execute(text("ALTER TABLE wf_node ADD COLUMN role_id INTEGER REFERENCES wf_role(id) ON DELETE SET NULL;"))
        except Exception:
            pass
            
        # 2. Add docnum to wf_instance
        try:
            conn.execute(text("ALTER TABLE wf_instance ADD COLUMN docnum VARCHAR(50);"))
        except Exception:
            pass
            
        # 3. Add internal_code to wf_instance
        try:
            conn.execute(text("ALTER TABLE wf_instance ADD COLUMN internal_code VARCHAR(50);"))
        except Exception:
            pass

        # 4. Add template_file_name to wf_node
        try:
            conn.execute(text("ALTER TABLE wf_node ADD COLUMN template_file_name VARCHAR(255);"))
        except Exception:
            pass

        # 5. Add template_file_path to wf_node
        try:
            conn.execute(text("ALTER TABLE wf_node ADD COLUMN template_file_path VARCHAR(500);"))
        except Exception:
            pass
        
        # In SQLAlchemy 2.x, commit connection context to persist ALTER TABLE
        try:
            conn.commit()
        except Exception:
            pass
