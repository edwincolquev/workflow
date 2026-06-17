import streamlit as st
import pandas as pd
from database import get_db
from models import WorkflowTask, WorkflowInstance, WorkflowUser, WorkflowRole
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS

# 1. Access Control
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

user_role = st.session_state.user['role']
if not ROLE_ACCESS.get(user_role, {}).get('bandeja', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>📥 Bandeja de Entrada de Workflow</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Gestione sus tareas pendientes y realice el seguimiento de procesos activos y cerrados.</p>", unsafe_allow_html=True)

# Tabs Definition
t_tasks, t_active, t_completed = st.tabs([
    "📥 Mis Tareas Pendientes", "📋 Procesos Activos (Todos)", "✅ Procesos Finalizados"
])

# Get user from DB
with get_db() as db:
    user = db.query(WorkflowUser).filter(WorkflowUser.id == st.session_state.user['id']).first()
    user_role_ids = [role.id for role in user.roles] if user else []

    # ==========================================
    # TAB 1: MIS TAREAS PENDIENTES
    # ==========================================
    with t_tasks:
        if not user_role_ids:
            st.warning("El usuario no tiene roles asignados.")
        else:
            # Fetch pending tasks for the user's roles
            pending_tasks = db.query(WorkflowTask).filter(
                WorkflowTask.status == 'PENDING',
                WorkflowTask.assigned_role_id.in_(user_role_ids)
            ).order_by(WorkflowTask.created_at.desc()).all()

            if not pending_tasks:
                st.info("🎉 ¡Excelente! No tienes tareas pendientes en tu bandeja de entrada.")
            else:
                st.markdown(f"Tienes **{len(pending_tasks)}** tareas que requieren tu atención.")
                
                # Render list of pending tasks as clean cards
                for task in pending_tasks:
                    inst = task.instance
                    proc_name = inst.process.name
                    task_created = task.created_at.strftime("%Y-%m-%d %H:%M")
                    
                    st.markdown(f"""
                    <div style="background-color: white; border-radius: 10px; padding: 15px; border-left: 5px solid #3b82f6; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-weight: 600; color: #1e293b; font-size: 1.05rem;">{inst.title}</span>
                            <span class="badge badge-blue">{proc_name}</span>
                        </div>
                        <div style="margin-top: 5px; font-size: 0.9rem; color: #64748b;">
                            <span>Etapa Actual: <b>{task.node.name}</b></span> | 
                            <span>Asignado a: <b>{task.assigned_role.name}</b></span> |
                            <span>Recibido: <i>{task_created}</i></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Button to inspect and execute transition
                    if st.button("Revisar & Avanzar Tarea", key=f"rev_btn_{task.id}"):
                        st.session_state.selected_workflow_instance_id = inst.id
                        st.success(f"Cargando instancia #{inst.id}. Por favor, haz clic en la página '08 Detalle Workflow' en el sidebar.")
                        st.rerun()

    # ==========================================
    # TAB 2: PROCESOS ACTIVOS (TODOS)
    # ==========================================
    with t_active:
        active_instances = db.query(WorkflowInstance).filter(
            WorkflowInstance.status == 'ACTIVE'
        ).order_by(WorkflowInstance.updated_at.desc()).all()

        if not active_instances:
            st.info("No hay procesos activos en ejecución en este momento.")
        else:
            data_active = []
            for inst in active_instances:
                # Find active task assignment
                active_task = db.query(WorkflowTask).filter(
                    WorkflowTask.instance_id == inst.id,
                    WorkflowTask.status == 'PENDING'
                ).first()
                assigned_to = active_task.assigned_role.name if (active_task and active_task.assigned_role) else "Ninguno"
                
                data_active.append({
                    'ID': inst.id,
                    'Proceso': inst.process.name,
                    'Título de Instancia': inst.title,
                    'Etapa Actual': inst.current_node.name if inst.current_node else "Inicio",
                    'Rol Responsable': assigned_to,
                    'Última Actualización': inst.updated_at
                })
            
            df_active = pd.DataFrame(data_active)
            st.dataframe(df_active, use_container_width=True, hide_index=True)
            
            # Allow jumping to an instance from here
            inst_to_inspect = st.selectbox(
                "Seleccione una instancia para ver detalles:", 
                [None] + [inst.id for inst in active_instances],
                format_func=lambda x: f"Instancia #{x}" if x else "Seleccionar..."
            )
            if inst_to_inspect:
                if st.button("Ir a Detalles", key="go_to_active_details"):
                    st.session_state.selected_workflow_instance_id = inst_to_inspect
                    st.success("Instancia cargada. Por favor, abre '08 Detalle Workflow' en el sidebar.")
                    st.rerun()

    # ==========================================
    # TAB 3: PROCESOS FINALIZADOS
    # ==========================================
    with t_completed:
        closed_instances = db.query(WorkflowInstance).filter(
            WorkflowInstance.status.in_(['COMPLETED', 'CANCELLED'])
        ).order_by(WorkflowInstance.updated_at.desc()).all()

        if not closed_instances:
            st.info("No hay procesos finalizados o cancelados.")
        else:
            data_closed = []
            for inst in closed_instances:
                data_closed.append({
                    'ID': inst.id,
                    'Proceso': inst.process.name,
                    'Título de Instancia': inst.title,
                    'Resultado': inst.status,
                    'Creado Por': inst.created_by.full_name if inst.created_by else "Sistema",
                    'Finalizado el': inst.updated_at
                })
            
            df_closed = pd.DataFrame(data_closed)
            st.dataframe(df_closed, use_container_width=True, hide_index=True)
            
            # Allow jumping to a closed instance
            closed_to_inspect = st.selectbox(
                "Seleccione un proceso finalizado para auditar:", 
                [None] + [inst.id for inst in closed_instances],
                format_func=lambda x: f"Instancia #{x}" if x else "Seleccionar..."
            )
            if closed_to_inspect:
                if st.button("Ver Historial de Instancia", key="go_to_closed_details"):
                    st.session_state.selected_workflow_instance_id = closed_to_inspect
                    st.success("Instancia cargada para auditoría. Abre '08 Detalle Workflow' en el sidebar.")
                    st.rerun()
