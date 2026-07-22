import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import hashlib
from database import get_db
from models import (
    WorkflowProcess, WorkflowNode, WorkflowTransition, 
    WorkflowUser, WorkflowRole, WorkflowInstance, WorkflowTask,
    WorkflowEmailLog, WorkflowErpQuery, WorkflowInstanceQueryDocNum, WorkflowBrand
)
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS
from services.workflow_validator import WorkflowValidatorService

# 1. Access Control
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

user_role = st.session_state.user['role']
if not ROLE_ACCESS.get(user_role, {}).get('admin', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>⚙️ Configuración & Administración</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Configure el motor de workflow, valide la estructura lógica de los procesos, gestione la matriz de transiciones y cuentas de usuario.</p>", unsafe_allow_html=True)

# Tabs
t_transitions, t_processes, t_users, t_queries, t_email_audit, t_brands = st.tabs([
    "🔀 Matriz de Transiciones", "📋 Procesos y Nodos", "👥 Usuarios y Roles", "🔍 Consultas ERP", "✉️ Auditoría de Correos", "🏷️ Categorías de Marcas"
])

def generate_mermaid(nodes, transitions):
    if not nodes:
        return ""
    lines = ["graph TD", "    %% Styles"]
    lines.append("    classDef startNode fill:#d1fae5,stroke:#065f46,stroke-width:2px,color:#065f46;")
    lines.append("    classDef taskNode fill:#dbeafe,stroke:#1e40af,stroke-width:2px,color:#1e40af;")
    lines.append("    classDef decisionNode fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#92400e;")
    lines.append("    classDef gatewayNode fill:#e2e8f0,stroke:#475569,stroke-width:2px,color:#475569;")
    lines.append("    classDef notificationNode fill:#fae8ff,stroke:#86198f,stroke-width:2px,color:#86198f;")
    lines.append("    classDef endNode fill:#fee2e2,stroke:#991b1b,stroke-width:2px,color:#991b1b;")
    
    # Node declarations
    for n in nodes:
        clean_name = n.name.replace('"', '\\"')
        style_class = "taskNode"
        if n.type == "START":
            style_class = "startNode"
        elif n.type == "DECISION":
            style_class = "decisionNode"
        elif n.type == "GATEWAY":
            style_class = "gatewayNode"
        elif n.type == "NOTIFICATION":
            style_class = "notificationNode"
        elif n.type == "END":
            style_class = "endNode"
        lines.append(f'    N{n.id}["{clean_name} ({n.type})"]:::{style_class}')
        
    # Transitions
    for t in transitions:
        clean_action = t.action_name.replace('"', '\\"')
        role_name = t.source_node.role.name if t.source_node.role else "Cualquiera"
        lines.append(f'    N{t.source_node_id} -->|"{clean_action} ({role_name})"| N{t.target_node_id}')
        
    return "\n".join(lines)

with get_db() as db:
    all_processes = db.query(WorkflowProcess).all()
    all_roles = db.query(WorkflowRole).all()
    all_users = db.query(WorkflowUser).all()
    
    role_map = {r.id: r.name for r in all_roles}

    # ==========================================
    # TAB 1: MATRIZ DE TRANSICIONES
    # ==========================================
    with t_transitions:
        st.markdown("<div class='section-header'>Matriz de Reglas de Transición</div>", unsafe_allow_html=True)
        
        # Select Process (ID-based to avoid selectbox freeze)
        proc_map = {p.id: p.name for p in all_processes}
        selected_proc_id = st.selectbox(
            "Seleccione Proceso a Configurar:", 
            options=list(proc_map.keys()),
            format_func=lambda x: proc_map[x],
            key="trans_proc_select"
        )
        
        selected_proc = db.query(WorkflowProcess).filter(WorkflowProcess.id == selected_proc_id).first() if selected_proc_id else None
        
        if selected_proc:
            # Query transitions and nodes
            transitions = db.query(WorkflowTransition).filter(
                WorkflowTransition.process_id == selected_proc.id
            ).all()
            nodes = db.query(WorkflowNode).filter(WorkflowNode.process_id == selected_proc.id).all()
            node_map = {n.id: f"{n.name} ({n.type})" for n in nodes}
            
            # Display current transitions
            if not transitions:
                st.info("No hay transiciones configuradas para este proceso.")
            else:
                trans_data = []
                for t in transitions:
                    trans_data.append({
                        'ID': t.id,
                        'Etapa Origen': t.source_node.name,
                        'Tipo': t.source_node.type,
                        'Rol que Ejecuta': t.source_node.role.name if t.source_node.role else "Cualquiera",
                        'Acción (Nombre Botón)': t.action_name,
                        'Etapa Destino': t.target_node.name
                    })
                
                df_trans = pd.DataFrame(trans_data)
                st.dataframe(df_trans, use_container_width=True, hide_index=True)
                
                # Delete transitions
                st.markdown("##### 🗑️ Eliminar Regla de Transición")
                col_del_1, col_del_2 = st.columns([3, 1])
                with col_del_1:
                    delete_id = st.selectbox(
                        "Seleccionar Transición para Eliminar:", 
                        [None] + [t.id for t in transitions],
                        format_func=lambda x: f"ID {x} - " + next(f"{t.source_node.name} -> {t.target_node.name} ({t.action_name})" for t in transitions if t.id == x) if x else "Seleccione una regla..."
                    )
                with col_del_2:
                    st.write("") 
                    st.write("")
                    if st.button("Eliminar Regla", key="delete_rule_btn", disabled=not delete_id, use_container_width=True):
                        t_del = db.query(WorkflowTransition).filter(WorkflowTransition.id == delete_id).first()
                        if t_del:
                            try:
                                db.delete(t_del)
                                db.commit()
                                st.success(f"Regla de transición ID {delete_id} eliminada.")
                                st.rerun()
                            except Exception as ex:
                                db.rollback()
                                st.error(f"❌ Error al eliminar la transición: {str(ex)}")

            st.markdown("---")
            st.markdown("##### ➕ Agregar Regla de Transición")
            
            if not nodes:
                st.warning("Debe crear nodos para este proceso antes de agregar transiciones.")
            else:
                # Node-centric simple transition layout
                col1, col2 = st.columns(2)
                with col1:
                    source_node_id = st.selectbox("Nodo Origen", options=list(node_map.keys()), format_func=lambda x: node_map[x], key="new_source_node")
                    action_name = st.text_input("Nombre de la Acción (Texto en Botón)", placeholder="Enviar a Viaje Marítimo", key="new_action_name")
                with col2:
                    target_node_id = st.selectbox("Nodo Destino", options=list(node_map.keys()), format_func=lambda x: node_map[x], key="new_target_node")
                
                submit_btn = st.button("Guardar Regla", key="save_rule_btn_new")
                if submit_btn:
                    if not action_name.strip():
                        st.error("Debes ingresar el nombre de la acción.")
                    else:
                        new_t = WorkflowTransition(
                            process_id=selected_proc.id,
                            source_node_id=source_node_id,
                            action_name=action_name.strip(),
                            target_node_id=target_node_id
                        )
                        try:
                            db.add(new_t)
                            db.commit()
                            st.success("¡Transición agregada con éxito!")
                            st.rerun()
                        except Exception as ex:
                            db.rollback()
                            st.error(f"❌ Error al guardar la transición: {str(ex)}")

            st.markdown("---")
            st.markdown("### 🔍 Visualización del Flujo (Mermaid)")
            mermaid_code = generate_mermaid(nodes, transitions)
            if mermaid_code:
                st.markdown(f"```mermaid\n{mermaid_code}\n```")
            else:
                st.info("Agregue nodos y transiciones para visualizar el diagrama.")

    # ==========================================
    # TAB 2: PROCESOS Y NODOS
    # ==========================================
    with t_processes:
        st.markdown("<div class='section-header'>Gestión de Procesos y Estructura del Workflow</div>", unsafe_allow_html=True)
        
        proc_options_p = [0] + list(proc_map.keys())
        def format_p(val):
            if val == 0:
                return "--- Crear nuevo proceso ---"
            return proc_map.get(val, "Desconocido")
            
        selected_proc_p_id = st.selectbox(
            "Seleccione Proceso a Configurar / Visualizar:", 
            options=proc_options_p, 
            format_func=format_p,
            key="proc_p_select"
        )
        
        selected_proc_p = db.query(WorkflowProcess).filter(WorkflowProcess.id == selected_proc_p_id).first() if selected_proc_p_id != 0 else None
        
        if selected_proc_p:
            # 1. LIVE WORKFLOW VISUALIZATION
            st.markdown("### 🔍 Visualización del Flujo (Mermaid)")
            p_nodes = db.query(WorkflowNode).filter(WorkflowNode.process_id == selected_proc_p.id).all()
            p_transitions = db.query(WorkflowTransition).filter(WorkflowTransition.process_id == selected_proc_p.id).all()
            
            mermaid_code = generate_mermaid(p_nodes, p_transitions)
            if mermaid_code:
                st.markdown(f"```mermaid\n{mermaid_code}\n```")
            else:
                st.info("Agregue nodos y transiciones para visualizar el diagrama.")
                
            # 2. STRUCTURAL INTEGRITY VALIDATION
            validation = WorkflowValidatorService.validate_process(db, selected_proc_p.id)
            if validation["valid"]:
                st.success("✅ Estructura del Workflow Válida: El flujo es consistente y no contiene callejones sin salida.")
            else:
                st.error("⚠️ Errores de Estructura detectados:")
                for err in validation["errors"]:
                    st.write(f"- {err}")
            
            st.markdown("---")
            
            # 3. GESTION DE PROCESO
            st.markdown("### 📋 Configuración del Proceso")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown("##### Editar Metadatos del Proceso")
                p_name = st.text_input("Nombre del Proceso", value=selected_proc_p.name)
                p_desc = st.text_area("Descripción", value=selected_proc_p.description or "", height=100)
                p_active = st.checkbox("Activo / Habilitado", value=selected_proc_p.active)
                
                if st.button("Guardar Cambios de Proceso"):
                    if not p_name.strip():
                        st.error("El nombre del proceso no puede estar vacío.")
                    else:
                        selected_proc_p.name = p_name.strip()
                        selected_proc_p.description = p_desc.strip()
                        selected_proc_p.active = p_active
                        db.commit()
                        st.success("Proceso actualizado con éxito.")
                        st.rerun()
            with col_p2:
                st.markdown("##### 🗑️ Eliminar Proceso Completo")
                st.warning("Advertencia: Eliminar un proceso eliminará todos sus nodos, transiciones e instancias asociadas permanentemente.")
                in_use, use_msg = WorkflowValidatorService.is_process_in_use(db, selected_proc_p.id)
                if in_use:
                    st.error(f"No se puede eliminar: {use_msg}")
                else:
                    confirm_delete = st.checkbox("Confirmar que deseo eliminar este proceso y todos sus componentes.")
                    if st.button("Eliminar Proceso", disabled=not confirm_delete, type="primary"):
                        db.delete(selected_proc_p)
                        db.commit()
                        st.success("Proceso eliminado con éxito.")
                        st.rerun()

            st.markdown("---")
            
            # 4. GESTION DE NODOS
            st.markdown("### 📍 Gestión de Nodos / Etapas")
            
            # List current nodes
            if p_nodes:
                nodes_df_list = []
                for n in p_nodes:
                    nodes_df_list.append({
                        'ID': n.id,
                        'Nombre Etapa': n.name,
                        'Tipo': n.type,
                        'Rol Responsable': n.role.name if n.role else "Ninguno",
                        'SLA (Días)': f"{n.sla_hours} días" if n.sla_hours else "Sin SLA",
                        'Plantilla Base': n.template_file_name or "Sin plantilla",
                        'Descripción': n.description or "Sin descripción"
                    })
                st.dataframe(pd.DataFrame(nodes_df_list), use_container_width=True, hide_index=True)
            
            # Form tabs for Node Actions
            t_add_n, t_edit_n, t_del_n = st.tabs(["➕ Agregar Nodo", "✏️ Editar Nodo", "🗑️ Eliminar Nodo"])
            
            with t_add_n:
                with st.form("add_node_form"):
                    n_name = st.text_input("Nombre del Nodo", placeholder="Aduana")
                    n_type = st.selectbox("Tipo de Nodo", ['START', 'TASK', 'DECISION', 'GATEWAY', 'NOTIFICATION', 'END'])
                    n_role = st.selectbox("Rol Responsable (Obligatorio para TASK, DECISION y NOTIFICATION)", options=[0] + list(role_map.keys()), format_func=lambda x: role_map[x] if x != 0 else "Ninguno")
                    n_desc = st.text_area("Instrucciones detalladas de la tarea (se enviarán por correo)", height=120)
                    n_sla = st.number_input("SLA en Días (Tiempo estimado de ejecución, 0 = Sin SLA)", min_value=0, value=0, step=1)
                    n_template = st.file_uploader("Subir Plantilla Base (Ej. Excel vacío para completar)", key="add_node_template_upload")
                    
                    # Load ERP queries
                    all_erp_queries = db.query(WorkflowErpQuery).all()
                    query_map = {q.id: q.name for q in all_erp_queries}
                    n_query = st.selectbox("Consulta ERP Asociada (Opcional)", options=[0] + list(query_map.keys()), format_func=lambda x: query_map[x] if x != 0 else "Ninguna")

                    if st.form_submit_button("Guardar Nuevo Nodo"):
                        if not n_name.strip():
                            st.error("El nombre del nodo es requerido.")
                        elif n_type in ['TASK', 'DECISION', 'NOTIFICATION'] and n_role == 0:
                            st.error(f"El nodo tipo '{n_type}' requiere obligatoriamente un Rol Responsable.")
                        else:
                            import os
                            from datetime import datetime
                            
                            t_name = None
                            t_path = None
                            if n_template is not None:
                                from services.storage_service import StorageService
                                file_bytes = n_template.getbuffer().tobytes()
                                t_path = StorageService.upload_file(file_bytes, n_template.name, folder="node_templates")
                                t_name = n_template.name

                            sla_val = n_sla if n_sla > 0 else None
                            new_node = WorkflowNode(
                                process_id=selected_proc_p.id,
                                name=n_name.strip(),
                                type=n_type,
                                role_id=n_role if n_role != 0 else None,
                                description=n_desc.strip(),
                                sla_hours=sla_val,
                                template_file_name=t_name,
                                template_file_path=t_path,
                                erp_query_id=n_query if n_query != 0 else None
                            )
                            try:
                                db.add(new_node)
                                db.commit()
                                st.success(f"Nodo '{n_name}' creado exitosamente.")
                                st.rerun()
                            except Exception as ex:
                                db.rollback()
                                st.error(f"❌ Error al crear el nodo: {str(ex)}")
                            
            with t_edit_n:
                if not p_nodes:
                    st.info("No hay nodos para editar.")
                else:
                    node_options_edit = {n.id: f"{n.name} ({n.type})" for n in p_nodes}
                    edit_node_id = st.selectbox(
                        "Seleccione Nodo a Editar:", 
                        options=list(node_options_edit.keys()), 
                        format_func=lambda x: node_options_edit[x], 
                        key="select_node_edit"
                    )
                    edit_node = db.query(WorkflowNode).filter(WorkflowNode.id == edit_node_id).first() if edit_node_id else None
                    
                    if edit_node:
                        if edit_node.template_file_name:
                            st.info(f"📎 **Plantilla cargada actual:** `{edit_node.template_file_name}`")
                            from services.storage_service import StorageService
                            template_bytes = StorageService.get_file_bytes(edit_node.template_file_path)
                            if template_bytes:
                                st.download_button(
                                    label="⬇️ Descargar plantilla actual",
                                    data=template_bytes,
                                    file_name=edit_node.template_file_name,
                                    key=f"dl_template_{edit_node.id}"
                                )
                                    
                        with st.form(f"edit_node_form_{edit_node.id}"):
                            en_name = st.text_input("Nombre del Nodo", value=edit_node.name)
                            en_types = ['START', 'TASK', 'DECISION', 'GATEWAY', 'NOTIFICATION', 'END']
                            en_type_idx = en_types.index(edit_node.type) if edit_node.type in en_types else 0
                            en_type = st.selectbox("Tipo de Nodo", en_types, index=en_type_idx)
                            en_role = st.selectbox(
                                "Rol Responsable (Obligatorio para TASK, DECISION y NOTIFICATION)",
                                options=[0] + list(role_map.keys()),
                                format_func=lambda x: role_map[x] if x != 0 else "Ninguno",
                                index=0 if not edit_node.role_id else list(role_map.keys()).index(edit_node.role_id) + 1
                            )
                            en_desc = st.text_area("Instrucciones detalladas de la tarea (se enviarán por correo)", value=edit_node.description or "", height=120)
                            en_sla = st.number_input("SLA en Días (Tiempo estimado de ejecución, 0 = Sin SLA)", min_value=0, value=edit_node.sla_hours or 0, step=1)
                            
                            en_template = st.file_uploader("Reemplazar Plantilla Base (Opcional)", key=f"edit_template_{edit_node.id}")
                            
                            # Load ERP queries
                            all_erp_queries = db.query(WorkflowErpQuery).all()
                            query_map = {q.id: q.name for q in all_erp_queries}
                            en_query = st.selectbox(
                                "Consulta ERP Asociada (Opcional)",
                                options=[0] + list(query_map.keys()),
                                format_func=lambda x: query_map[x] if x != 0 else "Ninguna",
                                index=0 if not edit_node.erp_query_id else list(query_map.keys()).index(edit_node.erp_query_id) + 1
                            )
                            
                            remove_template = False
                            if edit_node.template_file_name:
                                remove_template = st.checkbox("Eliminar plantilla actual")
                                
                            if st.form_submit_button("Actualizar Nodo"):
                                if not en_name.strip():
                                    st.error("El nombre no puede estar vacío.")
                                elif en_type in ['TASK', 'DECISION', 'NOTIFICATION'] and en_role == 0:
                                    st.error(f"El nodo tipo '{en_type}' requiere obligatoriamente un Rol Responsable.")
                                else:
                                    from datetime import datetime
                                    edit_node.name = en_name.strip()
                                    edit_node.type = en_type
                                    edit_node.role_id = en_role if en_role != 0 else None
                                    edit_node.description = en_desc.strip()
                                    edit_node.sla_hours = en_sla if en_sla > 0 else None
                                    edit_node.erp_query_id = en_query if en_query != 0 else None
                                    
                                    if remove_template:
                                        if edit_node.template_file_path and os.path.exists(edit_node.template_file_path):
                                            try:
                                                os.remove(edit_node.template_file_path)
                                            except:
                                                pass
                                        edit_node.template_file_name = None
                                        edit_node.template_file_path = None
                                        
                                    if en_template is not None:
                                        from services.storage_service import StorageService
                                        file_bytes = en_template.getbuffer().tobytes()
                                        edit_node.template_file_path = StorageService.upload_file(file_bytes, en_template.name, folder="node_templates")
                                        edit_node.template_file_name = en_template.name
                                        
                                    try:
                                        db.commit()
                                        st.success(f"Nodo '{en_name}' actualizado.")
                                        st.rerun()
                                    except Exception as ex:
                                        db.rollback()
                                        st.error(f"❌ Error al actualizar el nodo: {str(ex)}")
                                    
            with t_del_n:
                if not p_nodes:
                    st.info("No hay nodos para eliminar.")
                else:
                    node_options_del = {n.id: f"{n.name} ({n.type})" for n in p_nodes}
                    del_node_id = st.selectbox(
                        "Seleccione Nodo a Eliminar:", 
                        options=list(node_options_del.keys()), 
                        format_func=lambda x: node_options_del[x], 
                        key="select_node_del"
                    )
                    del_node = db.query(WorkflowNode).filter(WorkflowNode.id == del_node_id).first() if del_node_id else None
                    
                    if del_node:
                        in_use, use_msg = WorkflowValidatorService.is_node_in_use(db, del_node.id)
                        if in_use:
                            st.error(f"No se puede eliminar: {use_msg}")
                        else:
                            st.warning(f"¿Está seguro de que desea eliminar el nodo '{del_node.name}'?")
                            if st.button("Eliminar Nodo Seleccionado", type="primary"):
                                db.delete(del_node)
                                db.commit()
                                st.success(f"Nodo '{del_node.name}' eliminado correctamente.")
                                st.rerun()
        else:
            # CREATE NEW PROCESS
            st.markdown("### ➕ Crear Nuevo Proceso de Negocio")
            with st.form("create_process_form"):
                new_p_name = st.text_input("Nombre del Proceso", placeholder="ej. Aprobaciones de Inventario Especial")
                new_p_desc = st.text_area("Descripción", placeholder="Detalles sobre el propósito del flujo...")
                
                if st.form_submit_button("Crear Proceso"):
                    if not new_p_name.strip():
                        st.error("El nombre del proceso es requerido.")
                    else:
                        new_proc = WorkflowProcess(
                            name=new_p_name.strip(),
                            description=new_p_desc.strip(),
                            active=False # Starts deactivated until validated
                        )
                        db.add(new_proc)
                        db.flush()
                        
                        # Automatically seed start/end nodes to help the user
                        start_node = WorkflowNode(process_id=new_proc.id, name="Inicio", type="START", description="Punto de partida")
                        end_node = WorkflowNode(process_id=new_proc.id, name="Fin", type="END", description="Punto final")
                        db.add(start_node)
                        db.add(end_node)
                        
                        db.commit()
                        st.success(f"Proceso '{new_p_name}' creado con éxito. Se agregaron automáticamente los nodos 'Inicio' y 'Fin'.")
                        st.rerun()

    # ==========================================
    # TAB 3: USUARIOS Y ROLES
    # ==========================================
    with t_users:
        st.markdown("<div class='section-header'>Usuarios Registrados</div>", unsafe_allow_html=True)
        
        users_list = []
        for u in all_users:
            roles_str = ", ".join([role.name for role in u.roles])
            users_list.append({
                'ID': u.id,
                'Usuario': u.username,
                'Nombre Completo': u.full_name,
                'Correo Electrónico': u.email or "Sin correo",
                'Roles Asignados': roles_str,
                'Estado': "Activo" if u.active else "Inactivo"
            })
            
        st.dataframe(pd.DataFrame(users_list), use_container_width=True, hide_index=True)
        
        # User Action sub-tabs
        t_add_u, t_edit_u, t_pwd_u, t_roles_desc = st.tabs([
            "➕ Crear Usuario", "✏️ Editar Usuario", "🔑 Restablecer Contraseña", "💼 Descripciones de Roles"
        ])
        
        with t_add_u:
            with st.form("new_user_form"):
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    new_username = st.text_input("Usuario (Login)", placeholder="ej. logistico2")
                    new_fullname = st.text_input("Nombre Completo", placeholder="Juan Pérez")
                    new_email = st.text_input("Correo Electrónico", placeholder="juan.perez@empresa.com")
                with col_u2:
                    new_pass = st.text_input("Contraseña", type="password", placeholder="Contraseña segura")
                    selected_role_ids = st.multiselect("Roles Asignados", options=list(role_map.keys()), format_func=lambda x: role_map[x], key="new_user_roles_sel")
                
                user_submit = st.form_submit_button("Crear Usuario")
                if user_submit:
                    if not new_username.strip() or not new_fullname.strip() or not new_pass.strip() or not selected_role_ids:
                        st.error("El nombre de usuario, nombre completo, contraseña y al menos un rol son requeridos.")
                    else:
                        existing = db.query(WorkflowUser).filter(WorkflowUser.username == new_username.strip()).first()
                        if existing:
                            st.error("El nombre de usuario ya está registrado.")
                        else:
                            pwd_hash = hashlib.sha256(new_pass.encode('utf-8')).hexdigest()
                            new_u = WorkflowUser(
                                username=new_username.strip(),
                                email=new_email.strip() if new_email.strip() else None,
                                full_name=new_fullname.strip(),
                                password_hash=pwd_hash,
                                active=True
                            )
                            roles_to_assign = db.query(WorkflowRole).filter(WorkflowRole.id.in_(selected_role_ids)).all()
                            for r in roles_to_assign:
                                new_u.roles.append(r)
                            db.add(new_u)
                            db.commit()
                            st.success("Usuario creado con éxito.")
                            st.rerun()
                            
        with t_edit_u:
            user_map = {u.id: f"{u.full_name} ({u.username})" for u in all_users}
            edit_user_id = st.selectbox(
                "Seleccione Usuario a Editar:", 
                options=list(user_map.keys()), 
                format_func=lambda x: user_map[x],
                key="select_user_edit"
            )
            edit_user = db.query(WorkflowUser).filter(WorkflowUser.id == edit_user_id).first() if edit_user_id else None
            
            if edit_user:
                with st.form("edit_user_form"):
                    col_ue1, col_ue2 = st.columns(2)
                    with col_ue1:
                        eu_fullname = st.text_input("Nombre Completo", value=edit_user.full_name)
                        eu_email = st.text_input("Correo Electrónico", value=edit_user.email or "")
                        eu_active = st.checkbox("Usuario Activo", value=edit_user.active)
                    with col_ue2:
                        current_role_ids = [r.id for r in edit_user.roles]
                        eu_role_ids = st.multiselect(
                            "Roles Asignados", 
                            options=list(role_map.keys()), 
                            default=current_role_ids,
                            format_func=lambda x: role_map[x],
                            key=f"edit_roles_{edit_user.id}"
                        )
                        
                    if st.form_submit_button("Actualizar Usuario"):
                        if not eu_fullname.strip() or not eu_role_ids:
                            st.error("El nombre completo y al menos un rol son requeridos.")
                        else:
                            edit_user.full_name = eu_fullname.strip()
                            edit_user.email = eu_email.strip() if eu_email.strip() else None
                            edit_user.active = eu_active
                            
                            # Update roles association
                            roles_to_assign = db.query(WorkflowRole).filter(WorkflowRole.id.in_(eu_role_ids)).all()
                            edit_user.roles = []
                            for r in roles_to_assign:
                                edit_user.roles.append(r)
                                
                            db.commit()
                            st.success("Usuario actualizado correctamente.")
                            st.rerun()
                            
        with t_pwd_u:
            pwd_user_id = st.selectbox(
                "Restablecer Contraseña para:", 
                options=list(user_map.keys()), 
                format_func=lambda x: user_map[x], 
                key="pwd_user_select"
            )
            pwd_user = db.query(WorkflowUser).filter(WorkflowUser.id == pwd_user_id).first() if pwd_user_id else None
            
            if pwd_user:
                with st.form("reset_password_form"):
                    new_pwd1 = st.text_input("Nueva Contraseña", type="password")
                    new_pwd2 = st.text_input("Confirmar Contraseña", type="password")
                    
                    if st.form_submit_button("Cambiar Contraseña"):
                        if not new_pwd1.strip():
                            st.error("La contraseña no puede estar vacía.")
                        elif new_pwd1 != new_pwd2:
                            st.error("Las contraseñas no coinciden.")
                        else:
                            new_hash = hashlib.sha256(new_pwd1.encode('utf-8')).hexdigest()
                            pwd_user.password_hash = new_hash
                            db.commit()
                            st.success(f"Contraseña de '{pwd_user.username}' cambiada exitosamente.")
                            st.rerun()

        with t_roles_desc:
            st.markdown("##### Gestión de Descripciones de Roles")
            role_map_desc = {r.id: r.name for r in all_roles}
            edit_role_id = st.selectbox(
                "Seleccione Rol:", 
                options=list(role_map_desc.keys()), 
                format_func=lambda x: role_map_desc[x],
                key="select_role_desc"
            )
            edit_role = db.query(WorkflowRole).filter(WorkflowRole.id == edit_role_id).first() if edit_role_id else None
            
            if edit_role:
                with st.form("edit_role_desc_form"):
                    role_desc = st.text_area("Descripción del Rol", value=edit_role.description or "", height=100)
                    if st.form_submit_button("Actualizar Descripción"):
                        edit_role.description = role_desc.strip()
                        db.commit()
                        st.success(f"Descripción del rol '{edit_role.name}' actualizada.")
                        st.rerun()

    # ==========================================
    # TAB: GESTION DE CONSULTAS ERP
    # ==========================================
    with t_queries:
        st.markdown("<div class='section-header'>🔍 Gestión de Consultas ERP SAP B1</div>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b;'>Configure las consultas SQL que se ejecutarán en las etapas del workflow usando la variable <code>:docnum</code>.</p>", unsafe_allow_html=True)

        all_queries = db.query(WorkflowErpQuery).all()
        if all_queries:
            q_data = []
            for q in all_queries:
                q_data.append({
                    'ID': q.id,
                    'Nombre Consulta': q.name,
                    'Descripción': q.description or 'Sin descripción',
                    'Consulta SQL': q.sql_query
                })
            st.dataframe(pd.DataFrame(q_data), use_container_width=True, hide_index=True)
        else:
            st.info("No hay consultas ERP configuradas en este momento.")

        t_add_q, t_edit_q, t_del_q = st.tabs(["➕ Agregar Consulta", "✏️ Editar Consulta", "🗑️ Eliminar Consulta"])

        with t_add_q:
            with st.form("add_query_form"):
                q_name = st.text_input("Nombre de la Consulta", placeholder="ej. Consulta Oferta de Compra")
                q_desc = st.text_area("Descripción", placeholder="ej. Muestra información detallada de la oferta de compra desde SAP")
                q_sql = st.text_area("Consulta SQL (Debe contener :docnum)", placeholder="SELECT DocNum, CardCode, CardName, DocDate, DocTotal FROM OQUT WHERE DocNum = :docnum", height=150)
                
                if st.form_submit_button("Guardar Consulta"):
                    if not q_name.strip() or not q_sql.strip():
                        st.error("El nombre de la consulta y el código SQL son requeridos.")
                    elif ":docnum" not in q_sql.lower():
                        st.error("El código SQL debe contener el placeholder ':docnum' para parametrizar la consulta.")
                    else:
                        # Check name uniqueness
                        existing_q = db.query(WorkflowErpQuery).filter(WorkflowErpQuery.name == q_name.strip()).first()
                        if existing_q:
                            st.error("❌ Ya existe una consulta registrada con este nombre.")
                        else:
                            new_q = WorkflowErpQuery(
                                name=q_name.strip(),
                                description=q_desc.strip(),
                                sql_query=q_sql.strip()
                            )
                            db.add(new_q)
                            db.commit()
                            st.success(f"Consulta '{q_name}' guardada correctamente.")
                            st.rerun()

        with t_edit_q:
            if not all_queries:
                st.info("No hay consultas configuradas para editar.")
            else:
                q_options_edit = {q.id: q.name for q in all_queries}
                edit_q_id = st.selectbox(
                    "Seleccione Consulta a Editar:",
                    options=list(q_options_edit.keys()),
                    format_func=lambda x: q_options_edit[x],
                    key="select_query_edit"
                )
                edit_q = db.query(WorkflowErpQuery).filter(WorkflowErpQuery.id == edit_q_id).first() if edit_q_id else None
                if edit_q:
                    with st.form(f"edit_query_form_{edit_q.id}"):
                        eq_name = st.text_input("Nombre de la Consulta", value=edit_q.name)
                        eq_desc = st.text_area("Descripción", value=edit_q.description or "")
                        eq_sql = st.text_area("Consulta SQL (Debe contener :docnum)", value=edit_q.sql_query, height=150)

                        if st.form_submit_button("Actualizar Consulta"):
                            if not eq_name.strip() or not eq_sql.strip():
                                st.error("El nombre de la consulta y el código SQL no pueden estar vacíos.")
                            elif ":docnum" not in eq_sql.lower():
                                st.error("El código SQL debe contener el placeholder ':docnum' para parametrizar la consulta.")
                            else:
                                # Check name uniqueness
                                existing_q = db.query(WorkflowErpQuery).filter(
                                    WorkflowErpQuery.name == eq_name.strip(),
                                    WorkflowErpQuery.id != edit_q.id
                                ).first()
                                if existing_q:
                                    st.error("❌ Ya existe otra consulta registrada con este nombre.")
                                else:
                                    edit_q.name = eq_name.strip()
                                    edit_q.description = eq_desc.strip()
                                    edit_q.sql_query = eq_sql.strip()
                                    db.commit()
                                    st.success(f"Consulta '{eq_name}' actualizada.")
                                    st.rerun()

        with t_del_q:
            if not all_queries:
                st.info("No hay consultas configuradas para eliminar.")
            else:
                q_options_del = {q.id: q.name for q in all_queries}
                del_q_id = st.selectbox(
                    "Seleccione Consulta a Eliminar:",
                    options=list(q_options_del.keys()),
                    format_func=lambda x: q_options_del[x],
                    key="select_query_del"
                )
                del_q = db.query(WorkflowErpQuery).filter(WorkflowErpQuery.id == del_q_id).first() if del_q_id else None
                if del_q:
                    # Check if node is currently using it
                    nodes_using = db.query(WorkflowNode).filter(WorkflowNode.erp_query_id == del_q.id).all()
                    if nodes_using:
                        node_names = ", ".join([f"'{n.name}'" for n in nodes_using])
                        st.error(f"No se puede eliminar la consulta porque está asignada a las etapas: {node_names}. Desasócielas primero.")
                    else:
                        st.warning(f"¿Está seguro de que desea eliminar la consulta '{del_q.name}'?")
                        if st.button("Eliminar Consulta", type="primary", key="del_query_btn"):
                            db.delete(del_q)
                            db.commit()
                            st.success("Consulta eliminada correctamente.")
                            st.rerun()

    # ==========================================
    # TAB 4: AUDITORÍA DE CORREOS
    # ==========================================
    with t_email_audit:
        st.markdown("<div class='section-header'>✉️ Registro de Auditoría de Correos Electrónicos</div>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b;'>Visualice y audite todos los correos electrónicos generados por el motor de workflow, incluyendo notificaciones de asignación y comprobantes de resolución.</p>", unsafe_allow_html=True)

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            f_code = st.text_input("Filtrar por Código o Título de Instancia (ej. WF-0005):", key="email_audit_code_filter")
        with col_f2:
            f_recipient = st.text_input("Filtrar por Destinatario (Email):", key="email_audit_recipient_filter")
        with col_f3:
            f_status = st.selectbox("Filtrar por Estado:", ["Todos", "SENT", "SIMULATED", "FAILED"], key="email_audit_status_filter")

        query = db.query(WorkflowEmailLog).join(WorkflowEmailLog.instance)

        if f_code.strip():
            code_clean = f_code.strip()
            query = query.filter(
                (WorkflowInstance.internal_code.like(f"%{code_clean}%")) |
                (WorkflowInstance.title.like(f"%{code_clean}%"))
            )

        if f_recipient.strip():
            query = query.filter(WorkflowEmailLog.recipient.like(f"%{f_recipient.strip()}%"))

        if f_status != "Todos":
            query = query.filter(WorkflowEmailLog.status == f_status)

        logs = query.order_by(WorkflowEmailLog.sent_at.desc()).all()

        if not logs:
            st.info("No se encontraron registros de correos que coincidan con los filtros.")
        else:
            # Prepare dataframe for display
            log_data = []
            for log in logs:
                log_data.append({
                    "ID": log.id,
                    "Instancia": f"{log.instance.internal_code or 'N/A'} - {log.instance.title}",
                    "Fecha/Hora": log.sent_at.strftime("%Y-%m-%d %H:%M"),
                    "Destinatario": log.recipient,
                    "Asunto": log.subject,
                    "Estado": log.status,
                    "Detalles": (log.error_message or "—")[:60] + ("..." if log.error_message and len(log.error_message) > 60 else "")
                })
            df_logs = pd.DataFrame(log_data)
            st.dataframe(df_logs, use_container_width=True, hide_index=True)

            st.markdown("##### 🔍 Seleccione un Correo para Inspección de Contenido")
            selected_log_id = st.selectbox(
                "Seleccione Correo por ID / Asunto:",
                options=[l.id for l in logs],
                format_func=lambda x: f"ID {x} | {next(f'{l.recipient} - {l.subject}' for l in logs if l.id == x)}",
                key="email_audit_selected_id"
            )

            selected_log = db.query(WorkflowEmailLog).filter(WorkflowEmailLog.id == selected_log_id).first() if selected_log_id else None

            if selected_log:
                st.markdown("---")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.markdown(f"**De:** `{selected_log.sender}`")
                    st.markdown(f"**Para:** `{selected_log.recipient}`")
                    st.markdown(f"**Fecha:** {selected_log.sent_at.strftime('%Y-%m-%d %H:%M:%S')}")
                with col_d2:
                    st.markdown(f"**Asunto:** `{selected_log.subject}`")
                    status_color = {"SENT": "green", "SIMULATED": "blue", "FAILED": "red"}.get(selected_log.status, "grey")
                    st.markdown(f"**Estado:** :{status_color}[{selected_log.status}]")
                    if selected_log.error_message:
                        st.markdown(f"**Detalles Técnicos / Ruta:** `{selected_log.error_message}`")

                # Show attachments if any
                if selected_log.attachments_json:
                    import json
                    try:
                        atts = json.loads(selected_log.attachments_json)
                        if atts:
                            st.markdown("**📎 Archivos Adjuntos Enviados:**")
                            for a in atts:
                                st.markdown(f"- 📄 `{a.get('filename')}` ({a.get('size', 0) / 1024:.1f} KB)")
                    except Exception:
                        pass

                st.markdown("---")
                st.markdown("**Visualización del Correo (Formato HTML):**")
                
                # Recalculate SLA progress bar dynamically using current date
                html_content = selected_log.body_html
                if 'class="sla-progress-container"' in html_content:
                    import re
                    from datetime import datetime, timedelta
                    
                    pattern = r'<div class="sla-progress-container"\s+data-created-at="([^"]+)"\s+data-sla-hours="(\d+)"[^>]*>.*?<!-- END_SLA_PROGRESS_BAR -->'
                    match = re.search(pattern, html_content, re.DOTALL)
                    if match:
                        created_str = match.group(1)
                        sla_days = int(match.group(2))
                        try:
                            created_dt = datetime.strptime(created_str, '%Y-%m-%d %H:%M:%S')
                            now_utc = datetime.utcnow()
                            elapsed_h = (now_utc - created_dt).total_seconds() / 3600
                            progress_pct = min(100.0, (elapsed_h / (sla_days * 24.0) * 100.0))
                            elapsed_days = elapsed_h / 24
                            sla_days_disp = sla_days
                            bar_color = "#ef4444" if elapsed_h > (sla_days * 24.0) else ("#f59e0b" if progress_pct > 75 else "#10b981")
                            
                            c_str = created_dt.strftime('%Y-%m-%d')
                            d_str = (created_dt + timedelta(days=sla_days)).strftime('%Y-%m-%d')
                            
                            updated_progress_html = f"""<div class="sla-progress-container" 
                  data-created-at="{created_str}" 
                  data-sla-hours="{sla_days}" 
                  style="margin: 15px 0; padding: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; font-family: Arial, sans-serif;">
                 <div style="display: flex; justify-content: space-between; font-size: 12px; color: #475569; margin-bottom: 5px;">
                     <span><b>Progreso de SLA (Dinámico):</b> <span class="sla-days-text">{elapsed_days:.1f}d / {sla_days_disp:.1f}d días transcurridos</span></span>
                     <span class="sla-pct-text" style="font-weight: bold; color: {bar_color};">{progress_pct:.1f}%</span>
                 </div>
                 <div style="background-color: #e2e8f0; border-radius: 4px; height: 12px; width: 100%; overflow: hidden;">
                     <div class="sla-bar-fill" style="background-color: {bar_color}; height: 12px; width: {progress_pct:.1f}%; border-radius: 4px; transition: width 0.3s ease;"></div>
                 </div>
                 <div style="display: flex; justify-content: space-between; font-size: 10px; color: #94a3b8; margin-top: 4px;">
                     <span>Inicio: {c_str}</span>
                     <span>Límite (SLA): {d_str}</span>
                 </div>
             </div><!-- END_SLA_PROGRESS_BAR -->"""
                            html_content = re.sub(pattern, updated_progress_html, html_content, flags=re.DOTALL)
                        except Exception as ex:
                            pass
                
                st.components.v1.html(html_content, height=450, scrolling=True)

    # ==========================================
    # TAB 6: CATEGORÍAS DE MARCAS
    # ==========================================
    with t_brands:
        st.markdown("<div class='section-header'>🏷️ Administración de Marcas y Categorías</div>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; font-size: 0.9rem;'>Gestione la lista de marcas asociadas a los procesos de la cadena de suministro, su leadtime de referencia y la unidad de negocio a la que pertenecen.</p>", unsafe_allow_html=True)

        col_left, col_right = st.columns([1.2, 0.8])

        with col_left:
            st.markdown("##### 📋 Listado de Marcas")
            search_query = st.text_input("🔍 Buscar Marca o Unidad de Negocio:", placeholder="Ej. 3M, C-MOVIL...", key="brand_search_input")
            
            # Fetch all brands
            brands_query = db.query(WorkflowBrand)
            if search_query.strip():
                q = f"%{search_query.strip()}%"
                brands_query = brands_query.filter(
                    (WorkflowBrand.name.like(q)) | (WorkflowBrand.u_negocio.like(q))
                )
            
            all_brands = brands_query.order_by(WorkflowBrand.name).all()

            if not all_brands:
                st.info("No se encontraron marcas configuradas.")
            else:
                brands_list = []
                for b in all_brands:
                    brands_list.append({
                        "ID": b.id,
                        "Marca": b.name,
                        "Unidad de Negocio": b.u_negocio,
                        "Leadtime Ref. (Días)": b.leadtime,
                        "Estado": "Activa" if b.active else "Inactiva"
                    })
                df_brands = pd.DataFrame(brands_list)
                st.dataframe(df_brands, use_container_width=True, hide_index=True)

        with col_right:
            # Action tabs inside sidebar/right column
            brand_action = st.radio("Acción:", ["Agregar Nueva Marca", "Editar/Desactivar Marca"], horizontal=True, key="brand_action_radio")

            if brand_action == "Agregar Nueva Marca":
                st.markdown("##### ➕ Nueva Marca")
                with st.form("add_brand_form"):
                    b_name = st.text_input("Nombre de la Marca *", placeholder="Ej. 3M, MICHELIN")
                    b_un = st.selectbox(
                        "Unidad de Negocio *", 
                        options=["C-MOVIL", "NOVAPARTES", "PROLINE", "Otro"],
                        key="add_brand_un_select"
                    )
                    b_un_custom = st.text_input("Escriba la Unidad de Negocio * (Si seleccionó 'Otro')", placeholder="Ej. RETAIL")

                    b_lt = st.number_input("Leadtime de Referencia (Días) *", min_value=0, max_value=365, value=30, step=1)
                    b_active = st.checkbox("Activa", value=True)

                    btn_add = st.form_submit_button("Guardar Marca", type="primary", use_container_width=True)

                    if btn_add:
                        final_un = b_un_custom.strip().upper() if b_un == "Otro" else b_un
                        if not b_name.strip():
                            st.error("El nombre de la marca es obligatorio.")
                        elif b_un == "Otro" and not b_un_custom.strip():
                            st.error("Debe especificar la unidad de negocio.")
                        else:
                            # Check uniqueness
                            existing = db.query(WorkflowBrand).filter(WorkflowBrand.name == b_name.strip().upper()).first()
                            if existing:
                                st.error(f"Ya existe una marca llamada '{b_name.strip().upper()}'.")
                            else:
                                new_b = WorkflowBrand(
                                    name=b_name.strip().upper(),
                                    u_negocio=final_un,
                                    leadtime=int(b_lt),
                                    active=b_active
                                )
                                db.add(new_b)
                                db.commit()
                                st.success(f"¡Marca '{b_name.strip().upper()}' creada con éxito!")
                                st.rerun()

            else:
                st.markdown("##### ✏️ Editar Marca")
                # Reload active/inactive brands for selectbox
                all_select_brands = db.query(WorkflowBrand).order_by(WorkflowBrand.name).all()
                if not all_select_brands:
                    st.info("No hay marcas disponibles para editar.")
                else:
                    selected_b_id = st.selectbox(
                        "Seleccione Marca a Editar:",
                        options=[b.id for b in all_select_brands],
                        format_func=lambda x: next(f"{b.name} ({b.u_negocio})" for b in all_select_brands if b.id == x),
                        key="edit_brand_select"
                    )
                    
                    selected_brand = db.query(WorkflowBrand).filter(WorkflowBrand.id == selected_b_id).first()
                    
                    if selected_brand:
                        with st.form("edit_brand_form"):
                            eb_name = st.text_input("Nombre de la Marca", value=selected_brand.name)
                            # Match index for selectbox
                            un_options = ["C-MOVIL", "NOVAPARTES", "PROLINE", "Otro"]
                            default_idx = un_options.index(selected_brand.u_negocio) if selected_brand.u_negocio in un_options else 3
                            
                            eb_un = st.selectbox("Unidad de Negocio", options=un_options, index=default_idx, key="edit_brand_un_select")
                            eb_un_custom = st.text_input("Escriba la Unidad de Negocio * (Si seleccionó 'Otro')", value=selected_brand.u_negocio)

                            eb_lt = st.number_input("Leadtime de Referencia (Días)", min_value=0, max_value=365, value=selected_brand.leadtime, step=1)
                            eb_active = st.checkbox("Activa", value=selected_brand.active)

                            btn_save = st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True)

                            if btn_save:
                                final_un = eb_un_custom.strip().upper() if eb_un == "Otro" else eb_un
                                if not eb_name.strip():
                                    st.error("El nombre de la marca es obligatorio.")
                                elif eb_un == "Otro" and not eb_un_custom.strip():
                                    st.error("Debe especificar la unidad de negocio.")
                                else:
                                    # Check uniqueness if name changed
                                    name_changed = eb_name.strip().upper() != selected_brand.name
                                    if name_changed and db.query(WorkflowBrand).filter(WorkflowBrand.name == eb_name.strip().upper()).first():
                                        st.error(f"Ya existe otra marca llamada '{eb_name.strip().upper()}'.")
                                    else:
                                        selected_brand.name = eb_name.strip().upper()
                                        selected_brand.u_negocio = final_un
                                        selected_brand.leadtime = int(eb_lt)
                                        selected_brand.active = eb_active
                                        db.commit()
                                        st.success("¡Cambios guardados con éxito!")
                                        st.rerun()
