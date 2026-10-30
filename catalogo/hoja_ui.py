"""Hoja editable con selección y repetición de celdas en Streamlit."""

from copy import deepcopy

import pandas as pd
import streamlit as st
from permissions import can_write

from catalogo.database import fetch_all
from catalogo.gestion import ESTADOS, NUMERICOS
from catalogo.hoja_trabajo import (
    CAMPOS_EDITABLES, LABELS, aplicar_edicion, cambios_hoja, filas_para_editor,
    guardar_cambios_hoja, valor_celda,
)
from catalogo.plantilla_hoja import importar_plantilla_hoja, plantilla_hoja_bytes, revisar_plantilla_hoja

STATE_KEY = "hoja_trabajo"
def hay_cambios_hoja():
    state = st.session_state.get(STATE_KEY)
    return bool(state and cambios_hoja(state["originales"], state["borrador"]))


def _renovar_editor(state):
    version = st.session_state.get("hoja_version", 0) + 1
    st.session_state["hoja_version"] = version
    state["editor_key"] = f"hoja_editor_{version}"
    state["entrada"] = deepcopy(state["borrador"])


def _seleccionar_todas():
    selected = st.session_state["hoja_seleccionar_todas"]
    state = st.session_state[STATE_KEY]
    for row in state["borrador"]:
        row["seleccionar"] = selected
    _renovar_editor(state)


def _al_editar(editor_key):
    state = st.session_state[STATE_KEY]
    if editor_key != state["editor_key"]:
        return
    proposal = deepcopy(state["entrada"])
    edits = st.session_state[editor_key]["edited_rows"]
    for position, changes in edits.items():
        if 0 <= int(position) < len(proposal):
            for field, value in changes.items():
                if field in (*CAMPOS_EDITABLES, "seleccionar"):
                    proposal[int(position)][field] = valor_celda(value)
    draft, notices = aplicar_edicion(state["borrador"], proposal, repetir=True)
    state["borrador"] = draft
    state["avisos"] = notices
    if draft != proposal:
        _renovar_editor(state)


def mostrar_hoja(rows, scope, total):
    read_only = not can_write(st.session_state.get("user"))
    if read_only and hay_cambios_hoja():
        st.session_state.pop(STATE_KEY, None)
    rows = [dict(row) for row in rows]
    state = st.session_state.get(STATE_KEY)
    if state is None or (state["scope"] != scope and not hay_cambios_hoja()):
        state = dict(scope=scope, originales=rows, borrador=filas_para_editor(rows), avisos=[])
        st.session_state[STATE_KEY] = state
        _renovar_editor(state)
    elif not hay_cambios_hoja() and state["originales"] != rows:
        selected = {row["id"] for row in state["borrador"] if row["seleccionar"]}
        state["originales"] = rows
        state["borrador"] = filas_para_editor(rows, selected)
        _renovar_editor(state)
    flash = st.session_state.pop("hoja_mensaje", None)
    if flash:
        st.success(flash)
    st.subheader("Hoja de trabajo")
    st.caption(f"{len(state['borrador'])} de {total} repuestos mostrados con estos filtros.")
    with st.expander("Edición masiva con Excel"):
        st.write("La descarga respeta Filtrar por MARCA y Filtrar por estado; incluye todos los repuestos coincidentes, "
                 "aunque la hoja muestre menos filas. Edite las celdas y agregue filas al final con el ID vacío. "
                 "Mantenga los encabezados y los códigos como texto para conservar ceros iniciales. "
                 "La columna Imagen (URL) admite el enlace de la foto referencial. "
                 "Las filas omitidas no se eliminan; las filas sin cambios no se guardan.")
        st.caption("El estado puede cambiar libremente. 'Fecha cambio de estado' se actualiza automáticamente. "
                   "Los importes En SAP se pueden editar aquí, pero siguen bloqueados en pantalla.")
        export_scope = scope[:2]
        if st.button("Preparar plantilla Excel", key="hoja_preparar_excel"):
            st.session_state["hoja_plantilla_excel"] = {
                "filtros": export_scope,
                "datos": plantilla_hoja_bytes(marca_id=export_scope[0], estado=export_scope[1]),
            }
        prepared = st.session_state.get("hoja_plantilla_excel")
        if prepared and prepared["filtros"] == export_scope:
            st.download_button("Descargar plantilla Excel", data=prepared["datos"],
                               file_name="repuestos_hoja_trabajo.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="hoja_descargar_excel")
        uploaded = st.file_uploader("Importar plantilla editada", type=["xlsx"],
                                    disabled=read_only or hay_cambios_hoja(), key="hoja_importar_excel")
        if uploaded:
            content = uploaded.getvalue()
            try:
                updates, inserts = revisar_plantilla_hoja(content)
                st.info(f"Se prepararán {len(updates)} modificaciones y {len(inserts)} repuestos nuevos.")
                preview = [dict(fila=number, accion="Modificar", id=part_id,
                                codigo_proveedor=code,
                                campos=", ".join(LABELS[field] for field in fields))
                           for number, part_id, fields, code in updates]
                preview += [dict(fila=number, accion="Agregar", id=None,
                                 codigo_proveedor=data["codigo_proveedor"], campos="Nuevo repuesto")
                            for number, data in inserts]
                if preview:
                    st.dataframe(preview, hide_index=True, width="stretch")
                if st.button("Aplicar cambios del Excel", type="primary",
                             disabled=read_only or hay_cambios_hoja() or not preview):
                    modified, created = importar_plantilla_hoja(content)
                    st.session_state.pop(STATE_KEY, None)
                    st.session_state.pop("hoja_plantilla_excel", None)
                    st.session_state["hoja_mensaje"] = (
                        f"Plantilla importada: {modified} modificados y {created} nuevos."
                    )
                    st.rerun()
            except Exception as error:
                st.error(f"No se aplicó la plantilla: {error}")
        if hay_cambios_hoja():
            st.caption("Guarde o descarte los cambios pendientes de la hoja antes de importar Excel.")
    if not state["borrador"]:
        st.info("No hay repuestos para los filtros elegidos.")
        return []
    selected_count = sum(bool(row["seleccionar"]) for row in state["borrador"])
    st.session_state["hoja_seleccionar_todas"] = selected_count == len(state["borrador"])
    select_column, _ = st.columns([1, 11], gap="small")
    select_column.checkbox(
        "Seleccionar todas las filas mostradas",
        key="hoja_seleccionar_todas",
        label_visibility="collapsed",
        help="Marcar o quitar la selección de todas las filas mostradas",
        on_change=_seleccionar_todas,
    )
    data = pd.DataFrame(state["entrada"])
    data.insert(data.columns.get_loc("imagen"), "vista_imagen", data["imagen"].fillna(""))
    for field in NUMERICOS:
        data[field] = pd.to_numeric(data[field], errors="raise").astype(float)
    for field in CAMPOS_EDITABLES:
        if field not in (*NUMERICOS, "activo"):
            data[field] = data[field].astype("string")
    data["activo"] = data["activo"].astype(bool)
    data["seleccionar"] = data["seleccionar"].astype(bool)
    data.index = data["id"].tolist()
    config = {field: st.column_config.TextColumn(label) for field, label in LABELS.items()}
    config["codigo_proveedor"] = st.column_config.TextColumn("Código proveedor", required=True)
    config["seleccionar"] = st.column_config.CheckboxColumn(" ", default=False, pinned=True, width="small")
    config["id"] = st.column_config.NumberColumn("ID", disabled=True)
    config["activo"] = st.column_config.CheckboxColumn("Activo")
    config["estado_gestion"] = st.column_config.SelectboxColumn("Estado", options=list(ESTADOS.values()), required=True, width="medium")
    config["vista_imagen"] = st.column_config.ImageColumn("Vista", width="small", help="Foto referencial; haga doble clic en la miniatura para ampliarla.")
    config["imagen"] = st.column_config.LinkColumn("Imagen (URL)", width="medium", help="Enlace web de la foto referencial; se puede editar o abrir.")
    config["fecha_actualizacion"] = st.column_config.TextColumn("Última actualización", disabled=True, width="medium", help="Fecha y hora de la última modificación del repuesto o de su descripción, en hora de Bolivia.")
    config["fecha_actualizacion_estado"] = st.column_config.TextColumn("Último cambio de estado", disabled=True, width="medium", help="Fecha y hora en que cambió el estado de gestión por última vez, en hora de Bolivia.")
    for field in NUMERICOS:
        config[field] = st.column_config.NumberColumn(LABELS[field], min_value=0.0001 if field == "minimo_compra" else 0.0, format="%.4f")
    for field, table in (("unidad", "unidades_medida"), ("nombre_marca", "marcas_repuestos"), ("categoria", "categorias_repuestos")):
        options = {row["nombre"] for row in fetch_all(f"SELECT nombre FROM {table}")}
        options.update(row[field] for row in state["borrador"] if row[field])
        config[field] = st.column_config.SelectboxColumn(LABELS[field], options=sorted(options), width="medium")
    disabled = ["id", "vista_imagen", "fecha_actualizacion", "fecha_actualizacion_estado", "_index"]
    if read_only:
        disabled.extend(CAMPOS_EDITABLES)
    if all(row["estado_gestion"] == "en_sap" for row in state["originales"]):
        disabled += list(NUMERICOS)
    st.data_editor(data, hide_index=True, width="stretch", height=min(580, 38 + 35 * len(data)),
                   num_rows="fixed", column_config=config, disabled=disabled, key=state["editor_key"],
                   on_change=_al_editar, args=(state["editor_key"],))
    st.caption("Vista muestra la foto referencial y se amplía con doble clic. Las fechas se muestran como día/mes/año hora:minuto (Bolivia): Última actualización registra cambios del repuesto o su descripción; Último cambio de estado registra cuándo cambió el estado de gestión.")
    st.caption(f"{selected_count} filas seleccionadas. Edite una celda de una fila marcada para copiar su valor a las demás marcadas. Los códigos proveedor y SAP se editan individualmente.")
    for notice in state["avisos"]:
        st.warning(notice)
    st.caption("Las categorías deben pertenecer a la marca de cada fila. Al cambiar la marca se limpia su categoría. El estado puede cambiar libremente; los importes En SAP se corrigen mediante Excel.")
    changes = cambios_hoja(state["originales"], state["borrador"])
    st.caption(f"{len(changes)} repuestos con cambios pendientes. Guarde o descarte para volver a cambiar los filtros.")
    if changes:
        originals = {row["id"]: row for row in state["originales"]}
        with st.expander("Revisar cambios pendientes"):
            review = []
            for part_id, fields in changes.items():
                for field, value in fields.items():
                    previous = originals[part_id][field]
                    if field == "estado_gestion":
                        previous = ESTADOS[previous]
                    review.append(dict(codigo_proveedor=originals[part_id]["codigo_proveedor"], campo=LABELS[field],
                                       anterior="" if previous is None else str(previous), nuevo="" if value is None else str(value)))
            st.dataframe(review, hide_index=True, width="stretch")
    save, discard = st.columns(2)
    if save.button("Guardar cambios de la hoja", type="primary", disabled=read_only or not changes):
        try:
            count = guardar_cambios_hoja(state["originales"], changes)
            st.session_state.pop(STATE_KEY)
            st.session_state["hoja_mensaje"] = f"Hoja guardada: {count} repuestos actualizados."
            st.rerun()
        except Exception as error:
            st.error(f"No se guardó ninguna fila: {error}")
    if discard.button("Descartar cambios de la hoja", disabled=not changes):
        st.session_state.pop(STATE_KEY)
        st.rerun()
    return [row["id"] for row in state["borrador"] if row["seleccionar"]]
