from catalogo.database import get_connection, initialize_database
from catalogo.gestion import guardar_repuesto
from catalogo.resumen import totales_por_marca


def test_totales_follow_brand_and_group_processing_states(tmp_path):
    path = tmp_path / "catalogo.sqlite3"
    initialize_database(path)
    with get_connection(path) as connection:
        entries = [
            ("A", "propuesto"), ("A", "en_cotizacion"), ("A", "pendiente_aprobacion"),
            ("A", "aprobado"), ("A", "rechazado"), ("A", "pedido"), ("A", "en_sap"),
            ("B", "propuesto"), ("B", "pedido"), (None, "rechazado"),
        ]
        for number, (brand, state) in enumerate(entries):
            guardar_repuesto(connection, {"codigo_proveedor": f"P-{number}",
                                         "nombre_marca": brand, "estado_gestion": state})
        brand_a = connection.execute("SELECT id FROM marcas_repuestos WHERE nombre = 'A'").fetchone()[0]
        brand_b = connection.execute("SELECT id FROM marcas_repuestos WHERE nombre = 'B'").fetchone()[0]

    assert totales_por_marca(None, path) == dict(repuestos=10, propuestos=2, procesando=3,
                                               rechazados=2, pedido=2, en_sap=1)
    assert totales_por_marca(brand_a, path) == dict(repuestos=7, propuestos=1, procesando=3,
                                                  rechazados=1, pedido=1, en_sap=1)
    assert totales_por_marca(brand_b, path) == dict(repuestos=2, propuestos=1, procesando=0,
                                                  rechazados=0, pedido=1, en_sap=0)
    assert totales_por_marca(-1, path) == dict(repuestos=1, propuestos=0, procesando=0,
                                            rechazados=1, pedido=0, en_sap=0)
