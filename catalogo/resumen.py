"""Totales de repuestos por estado para el filtro de marca del catálogo."""

from pathlib import Path

from catalogo.database import DEFAULT_DB_PATH, get_connection


def totales_por_marca(marca_id=None, db_path: str | Path = DEFAULT_DB_PATH):
    if marca_id == -1:
        where, params = " WHERE marca_id IS NULL", ()
    elif marca_id is None:
        where, params = "", ()
    else:
        where, params = " WHERE marca_id = ?", (marca_id,)
    with get_connection(db_path, autocommit=True) as connection:
        row = connection.execute("""SELECT
            COUNT(*) AS repuestos,
            COALESCE(SUM(CASE WHEN estado_gestion = 'propuesto' THEN 1 ELSE 0 END), 0) AS propuestos,
            COALESCE(SUM(CASE WHEN estado_gestion IN ('en_cotizacion', 'pendiente_aprobacion', 'aprobado')
                THEN 1 ELSE 0 END), 0) AS procesando,
            COALESCE(SUM(CASE WHEN estado_gestion = 'rechazado' THEN 1 ELSE 0 END), 0) AS rechazados,
            COALESCE(SUM(CASE WHEN estado_gestion = 'pedido' THEN 1 ELSE 0 END), 0) AS pedido,
            COALESCE(SUM(CASE WHEN estado_gestion = 'en_sap' THEN 1 ELSE 0 END), 0) AS en_sap
            FROM repuestos""" + where, params).fetchone()
    return dict(row)
