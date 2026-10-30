from __future__ import annotations

import sqlite3
import os
import re
from contextlib import closing, contextmanager
from pathlib import Path

from catalogo.migrations import migrate_management, migrate_spanish_names

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = Path(os.environ.get("CATALOGO_DB_PATH") or BASE_DIR / "data" / "catalogo.sqlite3")
SCHEMA_PATH = BASE_DIR / "schema.sql"
_OLD_SAP_CHECK = re.compile(
    r"CHECK\s*\(\s*estado_gestion\s*<>\s*'en_sap'\s*OR\s*"
    r"trim\s*\(\s*coalesce\s*\(\s*codigo_sap\s*,\s*''\s*\)\s*\)\s*<>\s*''\s*\)",
    re.IGNORECASE,
)


def _migrate_free_states(path: Path) -> None:
    """Retira el CHECK antiguo de En SAP conservando IDs, relaciones e índices."""
    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'repuestos'"
        ).fetchone()
        if not row or not _OLD_SAP_CHECK.search(row[0]):
            return
        backup_path = path.with_name(path.stem + ".pre_estado_libre" + path.suffix)
        if not backup_path.exists():
            with closing(sqlite3.connect(backup_path)) as backup:
                connection.backup(backup)
        dependencies = [item[0] for item in connection.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name = 'repuestos' "
            "AND type IN ('index', 'trigger') AND sql IS NOT NULL"
        ).fetchall()]
        external_triggers = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND tbl_name <> 'repuestos' AND instr(lower(sql), 'repuestos') > 0"
        ).fetchall()
        old_sql = row[0]
        new_sql = _OLD_SAP_CHECK.sub("", old_sql, count=1)
        new_sql = re.sub(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?repuestos\b",
                         "CREATE TABLE repuestos_nuevo", new_sql, count=1, flags=re.IGNORECASE)
        columns = [item[1] for item in connection.execute("PRAGMA table_info(repuestos)")]
        names = ", ".join(f'"{name}"' for name in columns)
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("DROP VIEW IF EXISTS vista_repuestos")
            for name, _ in external_triggers:
                connection.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
            connection.execute(new_sql)
            connection.execute(f"INSERT INTO repuestos_nuevo ({names}) SELECT {names} FROM repuestos")
            connection.execute("DROP TABLE repuestos")
            connection.execute("ALTER TABLE repuestos_nuevo RENAME TO repuestos")
            for statement in dependencies:
                connection.execute(statement)
            for _, statement in external_triggers:
                connection.execute(statement)
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("La migración de estados dejó relaciones inválidas")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("La migración de estados no pasó integrity_check")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")


def _postgres_url(db_path: str | Path) -> str | None:
    if Path(db_path) != DEFAULT_DB_PATH:
        return None

    # Workflow and Cat?logo use different Supabase projects.
    url = os.environ.get("CATALOGO_DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("CATALOGO_DATABASE_URL")
        except Exception:
            pass
    if url and "[YOUR-PASSWORD]" in url:
        raise ValueError("Sustituya [YOUR-PASSWORD] en CATALOGO_DATABASE_URL")
    return url or None


def using_postgres() -> bool:
    return bool(_postgres_url(DEFAULT_DB_PATH))


@contextmanager
def get_connection(db_path: str | Path = DEFAULT_DB_PATH, *, autocommit: bool = False):
    postgres_url = _postgres_url(db_path)
    if postgres_url:
        from catalogo.postgres_database import PostgresConnection

        connection = PostgresConnection(postgres_url, autocommit=autocommit)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    if _postgres_url(db_path):
        with get_connection(db_path, autocommit=True) as connection:
            connection.execute("SELECT 1 FROM public.repuestos LIMIT 1")
        return
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptions_need_refresh = False
    # SQLite cannot remove NOT NULL from an existing column with ALTER TABLE.
    # Keep IDs intact so references from OEM, applications and staging remain valid.
    with closing(sqlite3.connect(path)) as connection:
        existing = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'parts'"
        ).fetchone()
        if existing:
            columns = {row[1]: row for row in connection.execute("PRAGMA table_info(parts)")}
            if columns["sap_code"][3] or columns["description"][3]:
                duplicate = connection.execute(
                    """SELECT upper(trim(supplier_code)), COUNT(*) FROM parts
                       WHERE supplier_code IS NOT NULL AND trim(supplier_code) <> ''
                       GROUP BY upper(trim(supplier_code)) HAVING COUNT(*) > 1 LIMIT 1"""
                ).fetchone()
                if duplicate:
                    raise ValueError(f"Hay códigos de proveedor duplicados: {duplicate[0]}")
                backup_path = path.with_name(path.stem + ".pre_supplier_migration" + path.suffix)
                if not backup_path.exists():
                    with closing(sqlite3.connect(backup_path)) as backup_connection:
                        connection.backup(backup_connection)
                connection.execute("PRAGMA foreign_keys = OFF")
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("""CREATE TABLE parts_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sap_code TEXT, supplier_code TEXT, description TEXT,
                        measure TEXT, brand_name TEXT, long_description TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )""")
                    connection.execute("""INSERT INTO parts_new
                        (id, sap_code, supplier_code, description, measure, brand_name,
                         long_description, is_active, created_at, updated_at)
                        SELECT id, sap_code, supplier_code, description, measure, brand_name,
                               long_description, is_active, created_at, updated_at FROM parts""")
                    connection.execute("DROP TABLE parts")
                    connection.execute("ALTER TABLE parts_new RENAME TO parts")
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.execute("PRAGMA foreign_keys = ON")
                violation = connection.execute("PRAGMA foreign_key_check").fetchone()
                if violation:
                    raise ValueError(f"La migración dejó una referencia inválida: {violation}")
                descriptions_need_refresh = True
        applications = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'part_applications'"
        ).fetchone()
        if applications:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(part_applications)")}
            if "application_text" not in columns:
                backup_path = path.with_name(path.stem + ".pre_application_text_migration" + path.suffix)
                if not backup_path.exists():
                    with closing(sqlite3.connect(backup_path)) as backup_connection:
                        connection.backup(backup_connection)
                connection.execute("PRAGMA foreign_keys = OFF")
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("""CREATE TABLE part_applications_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
                        brand_id INTEGER NOT NULL REFERENCES vehicle_brands(id) ON DELETE RESTRICT,
                        model_id INTEGER NOT NULL REFERENCES vehicle_models(id) ON DELETE RESTRICT,
                        engine_type_id INTEGER REFERENCES engine_types(id) ON DELETE RESTRICT,
                        displacement REAL CHECK (displacement IS NULL OR displacement > 0),
                        year_from INTEGER CHECK (year_from IS NULL OR year_from BETWEEN 1886 AND 2200),
                        year_to INTEGER CHECK (year_to IS NULL OR year_to BETWEEN 1886 AND 2200),
                        application_text TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CHECK (year_from IS NULL OR year_to IS NULL OR year_from <= year_to)
                    )""")
                    connection.execute("""INSERT INTO part_applications_new
                        (id, part_id, brand_id, model_id, engine_type_id, displacement,
                         year_from, year_to, created_at)
                        SELECT id, part_id, brand_id, model_id, engine_type_id, displacement,
                               year_from, year_to, created_at FROM part_applications""")
                    connection.execute("""DELETE FROM part_applications_new WHERE id NOT IN (
                        SELECT min(id) FROM part_applications_new
                        GROUP BY part_id, brand_id, model_id, coalesce(engine_type_id, 0),
                                 coalesce(displacement, 0), coalesce(year_from, 0), coalesce(year_to, 0)
                    )""")
                    connection.execute("DROP TABLE part_applications")
                    connection.execute("ALTER TABLE part_applications_new RENAME TO part_applications")
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.execute("PRAGMA foreign_keys = ON")
                violation = connection.execute("PRAGMA foreign_key_check").fetchone()
                if violation:
                    raise ValueError(f"La migración de aplicaciones dejó una referencia inválida: {violation}")
                descriptions_need_refresh = True
        migrate_spanish_names(connection, path)
        migrate_management(connection, path)
    _migrate_free_states(path)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(path) as connection:
        connection.executescript(schema)
        columns = {item[1] for item in connection.execute("PRAGMA table_info(repuestos)")}
        if "fecha_actualizacion_estado" not in columns:
            connection.execute("ALTER TABLE repuestos ADD COLUMN fecha_actualizacion_estado TEXT")
        if "imagen" not in columns:
            connection.execute("ALTER TABLE repuestos ADD COLUMN imagen TEXT")
        for name in ("repuestos_estado_inicial", "repuestos_transicion_estado", "repuestos_comercial_cerrado"):
            connection.execute(f"DROP TRIGGER IF EXISTS {name}")
        view = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'view' AND name = 'vista_repuestos'").fetchone()
        if view and ("r.fecha_actualizacion_estado" not in view[0] or "r.imagen" not in view[0]):
            connection.execute("DROP VIEW vista_repuestos")
        connection.executescript((BASE_DIR / "schema_gestion.sql").read_text(encoding="utf-8"))
        connection.execute("""UPDATE repuestos SET fecha_actualizacion_estado = coalesce((
            SELECT h.fecha_cambio FROM historial_estados h
            WHERE h.repuesto_id = repuestos.id ORDER BY h.id DESC LIMIT 1
        ), fecha_actualizacion, CURRENT_TIMESTAMP)
        WHERE fecha_actualizacion_estado IS NULL""")
        for unit in ("Pieza", "Juego", "Metro"):
            connection.execute("INSERT OR IGNORE INTO unidades_medida (nombre) VALUES (?)", (unit,))
        if descriptions_need_refresh:
            from catalogo.descriptions import refresh_long_description

            part_ids = [int(row[0]) for row in connection.execute("SELECT id FROM repuestos").fetchall()]
            for part_id in part_ids:
                refresh_long_description(connection, part_id)


def fetch_all(query: str, parameters: tuple = (), db_path: str | Path = DEFAULT_DB_PATH) -> list[sqlite3.Row]:
    with get_connection(db_path, autocommit=True) as connection:
        return connection.execute(query, parameters).fetchall()


def execute(query: str, parameters: tuple = (), db_path: str | Path = DEFAULT_DB_PATH) -> int:
    with get_connection(db_path) as connection:
        cursor = connection.execute(query, parameters)
        return cursor.lastrowid
