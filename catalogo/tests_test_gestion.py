from contextlib import closing
import json
import sqlite3

import pandas as pd

from catalogo.database import SCHEMA_PATH, get_connection, initialize_database
from catalogo.gestion import guardar_repuesto
from catalogo.importer import confirm_batch, stage_dataframe
from catalogo.tests_test_migration import _legacy_database


def test_management_migration_preserves_brand_and_initializes_states(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    _legacy_database(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE parts SET brand_name = 'FRASLE' WHERE id = 17")
        connection.execute("INSERT INTO parts (supplier_code, brand_name) VALUES ('P-002', 'FRASLE')")
        connection.commit()
    initialize_database(path)
    initialize_database(path)
    assert len(list(tmp_path.glob("*.pre_gestion_comercial*.sqlite3"))) == 1
    with get_connection(path) as connection:
        rows = connection.execute("SELECT nombre_marca, estado_gestion, precio_compra FROM vista_repuestos ORDER BY id").fetchall()
        assert [tuple(row) for row in rows] == [("FRASLE", "en_sap", None), ("FRASLE", "propuesto", None)]
        assert connection.execute("SELECT count(*) FROM marcas_repuestos").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM historial_estados").fetchone()[0] == 2
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_master_import_ignores_commercial_fields_and_keeps_classification(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    initialize_database(path)
    data = pd.DataFrame([{
        "repuestos.codigo_proveedor": "N-001", "unidades_medida.nombre": "Metro",
        "marcas_repuestos.nombre": "FRASLE", "categorias_repuestos.nombre": "Frenos",
        "repuestos.minimo_compra": "10,5", "repuestos.precio_compra": "2,25",
        "repuestos.precio_venta": "3.75", "repuestos.cantidad_compra": "12.5",
    }])
    assert confirm_batch(stage_dataframe(data, "gestion.csv", db_path=path), db_path=path) == (1, 0)
    assert confirm_batch(stage_dataframe(data, "gestion.csv", db_path=path), db_path=path) == (0, 0)
    with get_connection(path) as connection:
        part_id = connection.execute("SELECT id FROM repuestos WHERE codigo_proveedor = 'N-001'").fetchone()[0]
        guardar_repuesto(connection, {"precio_compra": 5, "estado_gestion": "Aprobado"}, part_id)
    update = pd.DataFrame([{"codigo_proveedor": "N-001", "precio_compra": "0", "precio_venta": ""}])
    assert confirm_batch(stage_dataframe(update, "actualizar.csv", db_path=path), db_path=path) == (0, 0)
    with get_connection(path) as connection:
        row = connection.execute("SELECT * FROM vista_repuestos").fetchone()
        assert (row["unidad"], row["nombre_marca"], row["categoria"]) == ("Metro", "FRASLE", "Frenos")
        assert (row["minimo_compra"], row["precio_compra"], row["precio_venta"], row["cantidad_compra"]) == (None, 5, None, None)
        assert row["estado_gestion"] == "aprobado"
        assert connection.execute("SELECT count(*) FROM categorias_repuestos").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM historial_estados").fetchone()[0] == 2
    old_file = pd.DataFrame([{"codigo_proveedor": "N-002", "estado_gestion": "En SAP",
                              "precio_compra": "-2", "cantidad_compra": "nan"}])
    batch = stage_dataframe(old_file, "antiguo.csv", db_path=path)
    with get_connection(path) as connection:
        assert connection.execute("SELECT filas_error FROM lotes_importacion WHERE id = ?", (batch,)).fetchone()[0] == 0
    assert confirm_batch(batch, db_path=path) == (1, 0)
    with get_connection(path) as connection:
        row = connection.execute("SELECT estado_gestion, precio_compra FROM repuestos WHERE codigo_proveedor = 'N-002'").fetchone()
        assert tuple(row) == ("propuesto", None)


def test_category_must_belong_to_brand(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    initialize_database(path)
    with get_connection(path) as connection:
        first, _ = guardar_repuesto(connection, dict(codigo_proveedor="A", nombre_marca="MARCA A", categoria="FRENOS"))
        second, _ = guardar_repuesto(connection, dict(codigo_proveedor="B", nombre_marca="MARCA B", categoria="FRENOS"))
        other_category = connection.execute("SELECT categoria_id FROM repuestos WHERE id = ?", (second,)).fetchone()[0]
        try:
            connection.execute("UPDATE repuestos SET categoria_id = ? WHERE id = ?", (other_category, first))
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Se permitió una categoría de otra marca")
        guardar_repuesto(connection, dict(nombre_marca="MARCA B"), first)
        assert connection.execute("SELECT categoria_id FROM repuestos WHERE id = ?", (first,)).fetchone()[0] is None
        assert connection.execute("SELECT count(*) FROM categorias_repuestos").fetchone()[0] == 2


def test_free_states_record_history_and_screen_closes_commercial_at_sap(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    initialize_database(path)
    with get_connection(path) as connection:
        part_id, _ = guardar_repuesto(connection, dict(codigo_proveedor="A", precio_compra="12.5"))
    with get_connection(path) as connection:
        guardar_repuesto(connection, dict(estado_gestion="Aprobado"), part_id)
        guardar_repuesto(connection, dict(estado_gestion="En SAP"), part_id)
        assert guardar_repuesto(connection, dict(estado_gestion="En SAP"), part_id) == (part_id, False)
        assert connection.execute("SELECT count(*) FROM historial_estados").fetchone()[0] == 3
        last = connection.execute("SELECT fecha_cambio FROM historial_estados WHERE repuesto_id = ? ORDER BY id DESC LIMIT 1",
                                  (part_id,)).fetchone()[0]
        assert connection.execute("SELECT fecha_actualizacion_estado FROM vista_repuestos WHERE id = ?",
                                  (part_id,)).fetchone()[0] == last
        guardar_repuesto(connection, dict(descripcion="Descripción técnica actualizada"), part_id)
        assert connection.execute("SELECT fecha_actualizacion_estado FROM repuestos WHERE id = ?",
                                  (part_id,)).fetchone()[0] == last
    with get_connection(path) as connection:
        guardar_repuesto(connection, dict(estado_gestion="Propuesto"), part_id)
        assert connection.execute("SELECT count(*) FROM historial_estados").fetchone()[0] == 4
        guardar_repuesto(connection, dict(estado_gestion="En SAP"), part_id)
    try:
        with get_connection(path) as connection:
            guardar_repuesto(connection, dict(precio_compra="20"), part_id)
    except ValueError as error:
        assert "cerrado" in str(error)
    else:
        raise AssertionError("Se modificó la gestión comercial cerrada")


def test_master_import_preserves_managed_states(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    initialize_database(path)
    with get_connection(path) as connection:
        guardar_repuesto(connection, dict(codigo_proveedor="A", estado_gestion="Aprobado"))
        guardar_repuesto(connection, dict(codigo_proveedor="B", estado_gestion="En SAP"))
    data = pd.DataFrame([{"codigo_proveedor": "A", "estado_gestion": "En cotización"},
                         {"codigo_proveedor": "B", "estado_gestion": "Pedido"}])
    batch = stage_dataframe(data, "estados.csv", db_path=path)
    with get_connection(path) as connection:
        staged = connection.execute("SELECT id, datos_normalizados FROM filas_importacion WHERE lote_id = ? LIMIT 1",
                                    (batch,)).fetchone()
        old_data = json.loads(staged["datos_normalizados"])
        old_data.update(estado_gestion="Pedido", precio_compra="99")
        connection.execute("UPDATE filas_importacion SET datos_normalizados = ? WHERE id = ?",
                           (json.dumps(old_data), staged["id"]))
    assert confirm_batch(batch, db_path=path) == (0, 0)
    with get_connection(path) as connection:
        assert connection.execute("SELECT count(*) FROM historial_estados").fetchone()[0] == 2
        assert [row[0] for row in connection.execute("SELECT estado_gestion FROM repuestos ORDER BY codigo_proveedor")] == [
            "aprobado", "en_sap"]
        assert connection.execute("SELECT estado FROM lotes_importacion WHERE id = ?", (batch,)).fetchone()[0] == "confirmed"


def test_old_sqlite_sap_check_migrates_without_losing_relations(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    schema = SCHEMA_PATH.read_text(encoding="utf-8").replace(
        "CHECK (estado_gestion IN ('propuesto', 'en_cotizacion', 'pendiente_aprobacion', 'aprobado', 'rechazado', 'pedido', 'en_sap'))",
        "CHECK (estado_gestion IN ('propuesto', 'en_cotizacion', 'pendiente_aprobacion', 'aprobado', 'rechazado', 'pedido', 'en_sap')) "
        "CHECK (estado_gestion <> 'en_sap' OR trim(coalesce(codigo_sap, '')) <> '')",
    )
    assert "CHECK (estado_gestion <> 'en_sap'" in schema
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(schema)
        connection.executescript(SCHEMA_PATH.with_name("schema_gestion.sql").read_text(encoding="utf-8"))
        connection.execute("INSERT INTO repuestos (id, codigo_proveedor) VALUES (7, 'ANTIGUO')")
        connection.execute("INSERT INTO codigos_oem (repuesto_id, codigo_oem) VALUES (7, 'OEM-7')")
        connection.commit()
    initialize_database(path)
    with get_connection(path) as connection:
        guardar_repuesto(connection, {"estado_gestion": "En SAP"}, 7)
        assert connection.execute("SELECT codigo_oem FROM codigos_oem WHERE repuesto_id = 7").fetchone()[0] == "OEM-7"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT fecha_actualizacion_estado FROM vista_repuestos WHERE id = 7").fetchone()[0]
