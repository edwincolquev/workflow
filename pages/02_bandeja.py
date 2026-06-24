import streamlit as st
import pandas as pd
from database import get_db
from models import WorkflowTask, WorkflowInstance, WorkflowUser, WorkflowRole, WorkflowProcess, WorkflowNode
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS
from engine import WorkflowEngine

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
st.markdown("<p style='color: #64748b;'>Gestione sus tareas pendientes, inicie nuevos procesos y realice el seguimiento de procesos activos y cerrados.</p>", unsafe_allow_html=True)

# Tabs Definition
t_tasks, t_new, t_active, t_completed = st.tabs([
    "📥 Mis Tareas Pendientes", "➕ Nuevo Proceso", "📋 Procesos Activos (Todos)", "✅ Procesos Finalizados"
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
            pending_tasks = db.query(WorkflowTask).filter(
                WorkflowTask.status == 'PENDING',
                WorkflowTask.assigned_role_id.in_(user_role_ids)
            ).order_by(WorkflowTask.created_at.desc()).all()

            if not pending_tasks:
                st.info("🎉 ¡Excelente! No tienes tareas pendientes en tu bandeja de entrada.")
            else:
                st.markdown(f"Tienes **{len(pending_tasks)}** tareas que requieren tu atención.")

                for task in pending_tasks:
                    inst = task.instance
                    proc_name = inst.process.name
                    task_created = task.created_at.strftime("%Y-%m-%d %H:%M")

                    # SLA alert color
                    from datetime import datetime, timezone
                    sla_color = "#3b82f6"
                    sla_badge_html = ""
                    if task.sla_hours and task.created_at:
                        now_utc = datetime.utcnow()
                        elapsed_h = (now_utc - task.created_at).total_seconds() / 3600
                        remaining_h = task.sla_hours - elapsed_h
                        if remaining_h < 0:
                            sla_color = "#ef4444"
                            sla_badge_html = f"<span style='background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:600;margin-left:6px;'>⚠️ SLA vencido ({abs(remaining_h):.1f}h tarde)</span>"
                        elif remaining_h < task.sla_hours * 0.2:
                            sla_color = "#f59e0b"
                            sla_badge_html = f"<span style='background:#fef3c7;color:#b45309;padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:600;margin-left:6px;'>⏳ SLA próximo ({remaining_h:.1f}h restantes)</span>"

                    code_badge = f"<span style='background:#f1f5f9;color:#475569;padding:2px 8px;border-radius:10px;font-size:0.78rem;font-weight:600;'>{inst.internal_code or f'#{inst.id}'}</span>"
                    docnum_info = f" | DocNum: <b>{inst.docnum}</b>" if inst.docnum else ""

                    st.markdown(f"""
                    <div style="background-color: white; border-radius: 10px; padding: 15px; border-left: 5px solid {sla_color}; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 600; color: #1e293b; font-size: 1.05rem;">{inst.title} {code_badge}</span>
                            <span class="badge badge-blue">{proc_name}</span>
                        </div>
                        <div style="margin-top: 5px; font-size: 0.9rem; color: #64748b;">
                            <span>Etapa Actual: <b>{task.node.name}</b></span> | 
                            <span>Asignado a: <b>{task.assigned_role.name}</b></span> |
                            <span>Recibido: <i>{task_created}</i></span>{docnum_info}
                        </div>
                        {sla_badge_html}
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("Revisar & Avanzar Tarea", key=f"rev_btn_{task.id}"):
                        st.session_state.selected_workflow_instance_id = inst.id
                        st.success(f"Cargando instancia {inst.internal_code or f'#{inst.id}'}. Por favor, haz clic en la página '03 Detalle Workflow' en el sidebar.")
                        st.rerun()

    # ==========================================
    # TAB 2: NUEVO PROCESO
    # ==========================================
    with t_new:
        st.markdown("#### Iniciar un Nuevo Proceso de Workflow")
        st.markdown("<p style='color: #64748b; font-size: 0.9rem;'>Crea una instancia genérica de proceso. El número de documento (DocNum) es opcional y puede ser asignado en cualquier etapa posterior.</p>", unsafe_allow_html=True)

        # Fetch active processes
        active_processes = db.query(WorkflowProcess).filter(WorkflowProcess.active == True).order_by(WorkflowProcess.name).all()

        if not active_processes:
            st.warning("No hay procesos configurados y activos. Contacta al administrador.")
        else:
            with st.form(key="new_process_form"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    selected_proc_id = st.selectbox(
                        "Tipo de Proceso *",
                        options=[p.id for p in active_processes],
                        format_func=lambda x: next((p.name for p in active_processes if p.id == x), str(x))
                    )
                    process_title = st.text_input(
                        "Título del Proceso *",
                        placeholder="Ej. Importación Proveedor ABC - Junio 2025"
                    )
                with col2:
                    docnum_input = st.text_input(
                        "DocNum (Opcional)",
                        placeholder="Ej. 10045"
                    )
                    st.markdown("<p style='font-size:0.8rem;color:#94a3b8;margin-top:-10px;'>Puede completarse después desde el detalle del proceso.</p>", unsafe_allow_html=True)

                # Show process description if available
                selected_proc = next((p for p in active_processes if p.id == selected_proc_id), None)
                if selected_proc and selected_proc.description:
                    st.info(f"**{selected_proc.name}**: {selected_proc.description}")

                submitted = st.form_submit_button("🚀 Crear Proceso", use_container_width=True, type="primary")

                if submitted:
                    if not process_title.strip():
                        st.error("El título del proceso es obligatorio.")
                    else:
                        try:
                            external_ref = None
                            if docnum_input.strip():
                                external_ref = f"DocNum:{docnum_input.strip()}"

                            new_instance = WorkflowEngine.create_instance(
                                db=db,
                                process_id=selected_proc_id,
                                title=process_title.strip(),
                                creator_id=st.session_state.user['id'],
                                external_ref=external_ref
                            )
                            st.success(f"✅ Proceso **{new_instance.internal_code}** creado con éxito: *{process_title.strip()}*")
                            st.session_state.selected_workflow_instance_id = new_instance.id
                            st.info("💡 Haz clic en **03 Detalle Workflow** en el sidebar para ver y gestionar el proceso recién creado.")
                        except Exception as e:
                            st.error(f"Error al crear el proceso: {str(e)}")

    # ==========================================
    # TAB 3: PROCESOS ACTIVOS (TODOS)
    # ==========================================
    with t_active:
        active_instances = db.query(WorkflowInstance).filter(
            WorkflowInstance.status == 'ACTIVE'
        ).order_by(WorkflowInstance.updated_at.desc()).all()

        if not active_instances:
            st.info("No hay procesos activos en ejecución en este momento.")
        else:
            from datetime import datetime
            data_active = []
            for inst in active_instances:
                active_task = db.query(WorkflowTask).filter(
                    WorkflowTask.instance_id == inst.id,
                    WorkflowTask.status == 'PENDING'
                ).first()
                assigned_to = active_task.assigned_role.name if (active_task and active_task.assigned_role) else "Ninguno"

                # Calculate completed and total nodes
                total_nodes = db.query(WorkflowNode).filter(
                    WorkflowNode.process_id == inst.process_id,
                    WorkflowNode.type.in_(['TASK', 'DECISION'])
                ).count()

                completed_nodes = db.query(WorkflowTask).filter(
                    WorkflowTask.instance_id == inst.id,
                    WorkflowTask.status == 'COMPLETED'
                ).count()

                pct_val = min(100, int((completed_nodes / total_nodes) * 100)) if total_nodes > 0 else 0
                pct_str = f"{pct_val}%"

                # SLA status (overall process check)
                total_sla_hours = sum(node.sla_hours for node in inst.process.nodes if node.type in ['TASK', 'DECISION'] and node.sla_hours)
                process_elapsed_h = (datetime.utcnow() - inst.created_at).total_seconds() / 3600

                # Check if any pending tasks are currently delayed
                active_tasks_delayed = False
                pending_tasks = db.query(WorkflowTask).filter(
                    WorkflowTask.instance_id == inst.id,
                    WorkflowTask.status == 'PENDING'
                ).all()
                for pt in pending_tasks:
                    if pt.sla_hours and pt.created_at:
                        pt_elapsed_h = (datetime.utcnow() - pt.created_at).total_seconds() / 3600
                        if pt_elapsed_h > pt.sla_hours:
                            active_tasks_delayed = True
                            break

                if total_sla_hours > 0:
                    if process_elapsed_h > total_sla_hours or active_tasks_delayed:
                        sla_status = "⚠️ Retrasado"
                    else:
                        sla_status = "✅ En tiempo"
                else:
                    sla_status = "Sin SLA"

                data_active.append({
                    'Código': inst.internal_code or f'#{inst.id}',
                    'DocNum': inst.docnum or '–',
                    'Proceso': inst.process.name,
                    'Título': inst.title,
                    '% Avance': pct_str,
                    'Etapa Actual': inst.current_node.name if inst.current_node else "Inicio",
                    'Rol Responsable': assigned_to,
                    'Estado SLA': sla_status,
                    'Última Actualización': inst.updated_at.strftime("%Y-%m-%d %H:%M") if inst.updated_at else "–"
                })

            df_active = pd.DataFrame(data_active)
            st.dataframe(df_active, use_container_width=True, hide_index=True)

            inst_to_inspect = st.selectbox(
                "Seleccione una instancia para ver detalles:",
                [None] + [inst.id for inst in active_instances],
                format_func=lambda x: f"{next((i.internal_code or f'#{i.id}' for i in active_instances if i.id == x), str(x))} — {next((i.title for i in active_instances if i.id == x), '')}" if x else "Seleccionar..."
            )
            if inst_to_inspect:
                if st.button("Ir a Detalles", key="go_to_active_details"):
                    st.session_state.selected_workflow_instance_id = inst_to_inspect
                    st.success("Instancia cargada. Por favor, abre '03 Detalle Workflow' en el sidebar.")
                    st.rerun()

    # ==========================================
    # TAB 4: PROCESOS FINALIZADOS
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
                # Calculate total SLA
                total_sla_hours = sum(node.sla_hours for node in inst.process.nodes if node.type in ['TASK', 'DECISION'] and node.sla_hours)
                
                # Total duration
                duration = inst.updated_at - inst.created_at
                duration_hours = duration.total_seconds() / 3600
                
                # Format duration string:
                days = duration.days
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60
                if days > 0:
                    duration_str = f"{days}d {hours}h"
                elif hours > 0:
                    duration_str = f"{hours}h {minutes}m"
                else:
                    duration_str = f"{minutes}m"

                # Check if any task of this completed process took longer than its SLA
                any_task_delayed = False
                all_tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id).all()
                for task in all_tasks:
                    if task.completed_at and task.created_at and task.sla_hours:
                        task_dur_h = (task.completed_at - task.created_at).total_seconds() / 3600
                        if task_dur_h > task.sla_hours:
                            any_task_delayed = True
                            break

                if total_sla_hours > 0:
                    if duration_hours > total_sla_hours or any_task_delayed:
                        sla_result = "⚠️ Retrasado"
                    else:
                        sla_result = "✅ En tiempo"
                else:
                    sla_result = "Sin SLA"

                data_closed.append({
                    'Código': inst.internal_code or f'#{inst.id}',
                    'DocNum': inst.docnum or '–',
                    'Proceso': inst.process.name,
                    'Título': inst.title,
                    'Resultado': inst.status,
                    'Creado Por': inst.created_by.full_name if inst.created_by else "Sistema",
                    'Tiempo Usado': duration_str,
                    'Resultado SLA': sla_result,
                    'Finalizado el': inst.updated_at.strftime("%Y-%m-%d %H:%M") if inst.updated_at else "–"
                })

            df_closed = pd.DataFrame(data_closed)
            st.dataframe(df_closed, use_container_width=True, hide_index=True)

            closed_to_inspect = st.selectbox(
                "Seleccione un proceso finalizado para auditar:",
                [None] + [inst.id for inst in closed_instances],
                format_func=lambda x: f"{next((i.internal_code or f'#{i.id}' for i in closed_instances if i.id == x), str(x))} — {next((i.title for i in closed_instances if i.id == x), '')}" if x else "Seleccionar..."
            )
            if closed_to_inspect:
                if st.button("Ver Historial de Instancia", key="go_to_closed_details"):
                    st.session_state.selected_workflow_instance_id = closed_to_inspect
                    st.success("Instancia cargada para auditoría. Abre '03 Detalle Workflow' en el sidebar.")
                    st.rerun()
