import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_db
from models import (
    WorkflowTask, WorkflowInstance, WorkflowUser, WorkflowRole, WorkflowProcess, 
    WorkflowNode, WorkflowHistory, WorkflowTransition, WorkflowComment, WorkflowAttachment,
    WorkflowErpQuery, WorkflowInstanceQueryDocNum
)
from components.ui_helpers import UIHelpers
from components.comments import CommentsComponent
from components.attachments import AttachmentsComponent
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
t_tasks, t_active, t_new, t_completed = st.tabs([
    "📥 Mis Tareas Pendientes", "📋 Procesos Activos (Todos)", "➕ Nuevo Proceso", "✅ Procesos Finalizados"
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
            all_pending = db.query(WorkflowTask).filter(WorkflowTask.status == 'PENDING').all()
            pending_tasks = [
                t for t in all_pending
                if (t.node.role_id if t.node.role_id is not None else t.assigned_role_id) in user_role_ids
            ]
            pending_tasks.sort(key=lambda x: x.created_at, reverse=True)

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
                        remaining_h = (task.sla_hours * 24.0) - elapsed_h
                        if remaining_h < 0:
                            sla_color = "#ef4444"
                            sla_badge_html = f"<span style='background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:600;margin-left:6px;'>⚠️ SLA vencido ({abs(remaining_h/24.0):.1f}d tarde)</span>"
                        elif remaining_h < (task.sla_hours * 24.0) * 0.2:
                            sla_color = "#f59e0b"
                            sla_badge_html = f"<span style='background:#fef3c7;color:#b45309;padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:600;margin-left:6px;'>⏳ SLA próximo ({remaining_h/24.0:.1f}d restantes)</span>"

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

                    if st.button("Revisar & Avanzar Tarea", key=f"rev_btn_{task.id}", type="primary"):
                        st.session_state.selected_workflow_instance_id = inst.id
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
                        # Check process instance title uniqueness
                        existing_inst = db.query(WorkflowInstance).filter(
                            WorkflowInstance.title == process_title.strip()
                        ).first()
                        if existing_inst:
                            st.error("❌ El título del proceso ya existe. Por favor, elige un nombre único y diferente.")
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
                                st.rerun()
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
                total_sla_hours = sum(node.sla_hours for node in inst.process.nodes if node.type in ['TASK', 'DECISION'] and node.sla_hours) * 24
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
                        if pt_elapsed_h > pt.sla_hours * 24:
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
            st.caption("💡 Selecciona una fila haciendo clic para desplegar los detalles del proceso abajo.")
            event_active = st.dataframe(
                df_active,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="active_instances_df"
            )

            if event_active.selection["rows"]:
                selected_row_idx = event_active.selection["rows"][0]
                selected_inst_id = active_instances[selected_row_idx].id
                if st.session_state.get("selected_workflow_instance_id") != selected_inst_id:
                    st.session_state.selected_workflow_instance_id = selected_inst_id
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
                        if task_dur_h > task.sla_hours * 24:
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
            st.caption("💡 Selecciona una fila haciendo clic para desplegar el historial y auditoría abajo.")
            event_closed = st.dataframe(
                df_closed,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="closed_instances_df"
            )

            if event_closed.selection["rows"]:
                selected_row_idx = event_closed.selection["rows"][0]
                selected_inst_id = closed_instances[selected_row_idx].id
                if st.session_state.get("selected_workflow_instance_id") != selected_inst_id:
                    st.session_state.selected_workflow_instance_id = selected_inst_id
                    st.rerun()

    # ==========================================
    # DETAIL VIEW (MERGED FROM PAGE 03)
    # ==========================================
    def save_task_attachment(db, instance_id, task_id, user_id, uploaded_file):
        if uploaded_file is not None:
            import os
            from components.attachments import UPLOAD_DIR
            timestamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S")
            safe_filename = f"{timestamp_prefix}_{uploaded_file.name.replace(' ', '_')}"
            dest_path = os.path.join(UPLOAD_DIR, safe_filename)
            
            with open(dest_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            new_attach = WorkflowAttachment(
                instance_id=instance_id,
                task_id=task_id,
                user_id=user_id,
                file_name=uploaded_file.name,
                file_path=dest_path,
                file_size=uploaded_file.size,
                created_at=datetime.utcnow()
            )
            db.add(new_attach)
            db.flush()
            
            # Log in history
            history = WorkflowHistory(
                instance_id=instance_id,
                task_id=task_id,
                source_node_id=None,
                target_node_id=None,
                user_id=user_id,
                action='ATTACHMENT',
                comment=f"Archivo cargado en etapa: '{uploaded_file.name}'",
                timestamp=datetime.utcnow()
            )
            db.add(history)
            db.flush()

    instance_id = st.session_state.get("selected_workflow_instance_id")
    if instance_id:
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance:
            st.error(f"La instancia de workflow #{instance_id} no existe.")
        else:
            def log_debug(msg):
                try:
                    import os
                    from datetime import datetime
                    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'localdb')
                    os.makedirs(log_dir, exist_ok=True)
                    log_file = os.path.join(log_dir, 'debug.log')
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"{datetime.now()}: {msg}\n")
                except Exception as e:
                    print(f"LOGGER ERROR: {e}")

            log_debug(f"[DETAIL VIEW] Selected Instance ID: {instance.id}, Title: {instance.title}, Current Node ID: {instance.current_node_id} ({instance.current_node.name if instance.current_node else 'N/A'})")
            st.markdown("---")
            
            col_title, col_close = st.columns([5, 1])
            with col_title:
                st.markdown("<h2 class='section-header' style='margin-top: 0;'>📋 Detalle del Workflow Seleccionado</h2>", unsafe_allow_html=True)
            with col_close:
                if st.button("❌ Cerrar Detalle", key="close_workflow_detail", use_container_width=True):
                    st.session_state.selected_workflow_instance_id = None
                    st.rerun()

            status_colors = {
                'ACTIVE': 'blue',
                'COMPLETED': 'green',
                'CANCELLED': 'red'
            }
            status_badge = UIHelpers.get_badge_html(instance.status, status_colors.get(instance.status, 'gray'))
            stage_badge = UIHelpers.get_badge_html(instance.current_node.name if instance.current_node else "N/A", 'yellow')

            # SLA check for current active task
            sla_alert_html = ""
            active_task_for_sla = db.query(WorkflowTask).filter(
                WorkflowTask.instance_id == instance.id,
                WorkflowTask.status == 'PENDING'
            ).first()

            if active_task_for_sla and active_task_for_sla.sla_hours and active_task_for_sla.created_at:
                elapsed_h = (datetime.utcnow() - active_task_for_sla.created_at).total_seconds() / 3600
                remaining_h = (active_task_for_sla.sla_hours * 24.0) - elapsed_h
                if remaining_h < 0:
                    sla_alert_html = f"""
                    <div style="background:#fee2e2;border-left:4px solid #ef4444;padding:10px 14px;border-radius:6px;margin-top:10px;">
                        ⚠️ <b style="color:#b91c1c;">SLA VENCIDO:</b> <span style="color:#7f1d1d;">Esta etapa lleva {abs(remaining_h/24.0):.1f}d de retraso sobre el SLA de {active_task_for_sla.sla_hours}d configurado.</span>
                    </div>"""
                elif remaining_h < (active_task_for_sla.sla_hours * 24.0) * 0.25:
                    sla_alert_html = f"""
                    <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:6px;margin-top:10px;">
                        ⏳ <b style="color:#b45309;">SLA PRÓXIMO A VENCER:</b> <span style="color:#78350f;">Quedan {remaining_h/24.0:.1f}d de las {active_task_for_sla.sla_hours}d del SLA.</span>
                    </div>"""

            code_display = instance.internal_code or f"#{instance.id}"

            st.markdown(f"""
            <div class="glass-card" style="padding: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: #0f172a;">{instance.title}</h3>
                    <div>
                        {status_badge}
                        {stage_badge}
                    </div>
                </div>
                <hr style="margin: 12px 0; border: 0; border-top: 1px solid #e2e8f0;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; font-size: 0.9rem; color: #475569;">
                    <div><b>Proceso:</b> {instance.process.name}</div>
                    <div><b>Código Interno:</b> {code_display}</div>
                    <div><b>DocNum:</b> {instance.docnum or '—'}</div>
                    <div><b>Creado Por:</b> {instance.created_by.full_name}</div>
                    <div><b>Creado el:</b> {instance.created_at.strftime('%Y-%m-%d %H:%M')}</div>
                    <div><b>Última Actividad:</b> {instance.updated_at.strftime('%Y-%m-%d %H:%M')}</div>
                </div>
                {sla_alert_html}
            </div>
            """, unsafe_allow_html=True)

            # ─── SAP ERP Data (visible if DocNum or custom_query is present) ─────────────
            custom_query = instance.current_node.erp_query if (instance.current_node and instance.current_node.erp_query) else None
            
            def log_debug(msg):
                try:
                    with open("c:\\supply_chain\\localdb\\debug.log", "a", encoding="utf-8") as f:
                        f.write(f"{datetime.now()}: {msg}\n")
                except Exception:
                    pass

            if instance.docnum or custom_query:
                with st.expander("📦 Detalle de Documento ERP (SAP B1)", expanded=True):
                    from services.data_loader import DataLoaderService
                    
                    if custom_query:
                        log_debug(f"[ERP EXPANDER] Instance ID: {instance.id}, Custom Query ID: {custom_query.id}, Name: {custom_query.name}")
                        st.markdown(f"🧬 **Consulta ERP Personalizada: {custom_query.name}**")
                        if custom_query.description:
                            st.caption(custom_query.description)
                        
                        # 1. Fetch query-specific DocNum from DB
                        q_docnum_record = db.query(WorkflowInstanceQueryDocNum).filter(
                            WorkflowInstanceQueryDocNum.instance_id == instance.id,
                            WorkflowInstanceQueryDocNum.query_id == custom_query.id
                        ).first()
                        
                        active_docnum = q_docnum_record.docnum if q_docnum_record else ""
                        log_debug(f"[ERP EXPANDER] Loaded active_docnum from DB: '{active_docnum}'")
                        
                        # 2. Check if user is authorized to edit the DocNum for this stage
                        is_editable = (instance.status == 'ACTIVE') and (
                            st.session_state.user['role'] in ['Administrador', 'Gerencia'] or
                            any((t.node.role_id if t.node.role_id is not None else t.assigned_role_id) in user_role_ids 
                                for t in db.query(WorkflowTask).filter(
                                    WorkflowTask.instance_id == instance.id,
                                    WorkflowTask.status == 'PENDING'
                                ).all())
                        )
                        log_debug(f"[ERP EXPANDER] is_editable: {is_editable}, User Role: {st.session_state.user['role']}")
                        
                        # 3. Render inline editor for query-specific DocNum if editable
                        if is_editable:
                            col_qdoc1, col_qdoc2 = st.columns([3, 1])
                            with col_qdoc1:
                                input_qdocnum = st.text_input(
                                    f"Ingresar DocNum para la consulta '{custom_query.name}':",
                                    value=active_docnum,
                                    placeholder="Ej. 10045",
                                    key=f"qdocnum_input_{instance.id}_{custom_query.id}"
                                )
                                log_debug(f"[ERP EXPANDER] st.text_input output (input_qdocnum): '{input_qdocnum}'")
                            with col_qdoc2:
                                st.write("") # spacing
                                st.write("")
                                button_clicked = st.button("💾 Guardar DocNum", key=f"save_qdocnum_{instance.id}_{custom_query.id}", use_container_width=True)
                                log_debug(f"[ERP EXPANDER] Button '💾 Guardar DocNum' clicked state: {button_clicked}")
                                if button_clicked:
                                    log_debug(f"[ERP EXPANDER] Processing button click. Input DocNum: '{input_qdocnum}'")
                                    if not input_qdocnum.strip():
                                        st.error("El DocNum no puede estar vacío.")
                                    else:
                                        if not q_docnum_record:
                                            log_debug("[ERP EXPANDER] No existing record. Creating new WorkflowInstanceQueryDocNum")
                                            q_docnum_record = WorkflowInstanceQueryDocNum(
                                                instance_id=instance.id,
                                                query_id=custom_query.id,
                                                docnum=input_qdocnum.strip()
                                            )
                                            db.add(q_docnum_record)
                                        else:
                                            log_debug(f"[ERP EXPANDER] Existing record found. Updating docnum to '{input_qdocnum.strip()}'")
                                            q_docnum_record.docnum = input_qdocnum.strip()
                                        
                                        # If global DocNum is not set, set it as default
                                        if not instance.docnum:
                                            instance.docnum = input_qdocnum.strip()
                                            instance.external_ref = f"DocNum:{input_qdocnum.strip()}"
                                            
                                        log_debug("[ERP EXPANDER] Calling db.commit()...")
                                        db.commit()
                                        log_debug("[ERP EXPANDER] db.commit() completed successfully. Calling st.rerun()...")
                                        st.success("✅ DocNum de la consulta guardado con éxito.")
                                        st.rerun()
                            active_docnum = input_qdocnum.strip()
                        else:
                            if active_docnum:
                                st.info(f"📋 Ejecutando consulta con DocNum: **{active_docnum}**")
                        
                        # 4. Execute query using active_docnum
                        if active_docnum:
                            sql_lower = custom_query.sql_query.lower()
                            has_sap_tables = any(t in sql_lower for t in ['opor', 'por1', 'opqt', 'pqt1'])
                            
                            from config.database_sap import get_sap_connection
                            sap_conn = None
                            try:
                                sap_conn = get_sap_connection()
                            except Exception:
                                pass
                                
                            df_erp = pd.DataFrame()
                            if has_sap_tables and not sap_conn:
                                df_erp = DataLoaderService.get_sap_document_details(db, active_docnum)
                            else:
                                if sap_conn:
                                    try:
                                        query_to_run = custom_query.sql_query
                                        params = []
                                        if ":docnum" in query_to_run:
                                            query_to_run = query_to_run.replace(":docnum", "?")
                                            params.append(active_docnum)
                                        df_erp = pd.read_sql(query_to_run, sap_conn, params=params)
                                    except Exception as e:
                                        sap_conn = None
                                
                                if not sap_conn or df_erp.empty:
                                    from sqlalchemy import text
                                    try:
                                        res = db.execute(text(custom_query.sql_query), {"docnum": active_docnum})
                                        cols = res.keys()
                                        rows = res.fetchall()
                                        if rows:
                                            df_erp = pd.DataFrame(rows, columns=cols)
                                    except Exception as ex:
                                        st.error(f"❌ Error al ejecutar la consulta SQL: {str(ex)}")
                            
                            if not df_erp.empty:
                                st.dataframe(df_erp, use_container_width=True, hide_index=True)
                            else:
                                st.info(f"La consulta no retornó resultados para el DocNum {active_docnum}.")
                        else:
                            if not is_editable:
                                st.warning("⚠️ No se ha configurado un DocNum para esta etapa.")
                            else:
                                st.info("💡 Por favor, configure y guarde el DocNum para visualizar los datos del ERP.")
                    else:
                        df_erp = DataLoaderService.get_sap_document_details(db, instance.docnum)
                        if not df_erp.empty:
                            # General fields in columns
                            c_erp1, c_erp2, c_erp3 = st.columns(3)
                            with c_erp1:
                                st.metric("Número SAP B1", df_erp.iloc[0]['Número SAP'])
                            with c_erp2:
                                st.metric("Proveedor", df_erp.iloc[0]['Nombre Proveedor'])
                            with c_erp3:
                                st.metric("Total Documento", f"${df_erp.iloc[0]['Monto Total USD']:,} USD")
                            
                            # Items table
                            st.markdown("**Detalle de Partidas:**")
                            st.dataframe(
                                df_erp[['Código Artículo', 'Descripción', 'Cantidad Solicitada', 'Cantidad Pendiente', 'Precio Unitario']],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info(f"No se encontraron partidas activas en el ERP para el documento #{instance.docnum}. Verifique si está completado o cancelado en SAP.")

            # ─── DocNum Editor (always visible for active instances and admins) ───────────
            if instance.status == 'ACTIVE' or st.session_state.user['role'] in ['Administrador', 'Gerencia']:
                with st.expander("🔢 Actualizar DocNum (Número de Documento ERP)", expanded=False):
                    with st.form(key="docnum_update_form"):
                        new_docnum = st.text_input(
                            "DocNum:",
                            value=instance.docnum or "",
                            placeholder="Ej. 10045"
                        )
                        docnum_comment = st.text_area(
                            "Motivo de la actualización *",
                            placeholder="Ej. Se recibió confirmación del número SAP..."
                        )
                        save_docnum = st.form_submit_button("💾 Guardar DocNum", use_container_width=True)
                        if save_docnum:
                            if not docnum_comment.strip():
                                st.error("El comentario es obligatorio para registrar el cambio.")
                            elif not new_docnum.strip():
                                st.error("Ingresa un DocNum válido.")
                            else:
                                try:
                                    instance.docnum = new_docnum.strip()
                                    instance.external_ref = f"DocNum:{new_docnum.strip()}"
                                    instance.updated_at = datetime.utcnow()
                                    
                                    # Sync with active custom query if it exists
                                    active_query = instance.current_node.erp_query if (instance.current_node and instance.current_node.erp_query) else None
                                    if active_query:
                                        q_docnum_record = db.query(WorkflowInstanceQueryDocNum).filter(
                                            WorkflowInstanceQueryDocNum.instance_id == instance.id,
                                            WorkflowInstanceQueryDocNum.query_id == active_query.id
                                        ).first()
                                        if not q_docnum_record:
                                            q_docnum_record = WorkflowInstanceQueryDocNum(
                                                instance_id=instance.id,
                                                query_id=active_query.id,
                                                docnum=new_docnum.strip()
                                            )
                                            db.add(q_docnum_record)
                                        else:
                                            q_docnum_record.docnum = new_docnum.strip()
                                            
                                    db.add(WorkflowHistory(
                                        instance_id=instance.id,
                                        source_node_id=instance.current_node_id,
                                        target_node_id=instance.current_node_id,
                                        user_id=user.id,
                                        action='UPDATE_DOCNUM',
                                        comment=f"DocNum actualizado a '{new_docnum.strip()}'. {docnum_comment.strip()}",
                                        timestamp=datetime.utcnow()
                                    ))
                                    db.add(WorkflowComment(
                                        instance_id=instance.id,
                                        user_id=user.id,
                                        comment_text=f"[DocNum actualizado: {new_docnum.strip()}] {docnum_comment.strip()}",
                                        created_at=datetime.utcnow()
                                    ))
                                    db.commit()
                                    st.success(f"DocNum actualizado a **{new_docnum.strip()}** con éxito.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al guardar DocNum: {str(e)}")

            # ─── Email History Expander ────────────────────────────────────────────────
            with st.expander("✉️ Enviar Historial del Workflow por Correo"):
                with st.form(key="email_workflow_report_form"):
                    dest_email = st.text_input("Correo Destinatario:", placeholder="ej. gerente@empresa.com")
                    message = st.text_area("Mensaje adicional (Opcional):", placeholder="Adjunto el historial del workflow solicitado...")
                    send_btn = st.form_submit_button("Enviar Historial")
                    if send_btn:
                        if not dest_email.strip():
                            st.error("Por favor, ingrese un correo destinatario.")
                        else:
                            try:
                                history_list = db.query(WorkflowHistory).filter(
                                    WorkflowHistory.instance_id == instance.id
                                ).order_by(WorkflowHistory.timestamp.asc()).all()

                                hist_data = []
                                for h in history_list:
                                    hist_data.append({
                                        "Fecha/Hora": h.timestamp.strftime("%Y-%m-%d %H:%M"),
                                        "Usuario": h.user.full_name,
                                        "Acción": h.action,
                                        "Comentario": h.comment or ""
                                    })
                                df_hist = pd.DataFrame(hist_data)

                                from services.email_service import send_report_email
                                send_report_email(
                                    to_email=dest_email.strip(),
                                    report_title=f"Historial de Workflow - {instance.title}",
                                    df=df_hist,
                                    message=message.strip()
                                )
                                st.success(f"Historial enviado con éxito a {dest_email}.")
                            except Exception as e:
                                st.error(f"Error al enviar historial: {str(e)}")

            # 4. Render Action Execution Block
            if instance.status == 'ACTIVE':
                st.markdown("<div class='section-header'>⚡ Acciones Operativas de la Etapa</div>", unsafe_allow_html=True)

                active_tasks = db.query(WorkflowTask).filter(
                    WorkflowTask.instance_id == instance.id,
                    WorkflowTask.status == 'PENDING'
                ).all()

                user_active_tasks = [at for at in active_tasks if (at.node.role_id if at.node.role_id is not None else at.assigned_role_id) in user_role_ids]

                if not active_tasks:
                    st.warning("El flujo está activo pero no tiene tareas pendientes configuradas.")
                elif not user_active_tasks:
                    st.warning("🔒 No tienes acciones disponibles en esta etapa. El flujo está esperando la resolución del rol responsable.")
                    roles_pending = ", ".join(list(set([at.node.role.name if at.node.role else at.assigned_role.name for at in active_tasks])))
                    st.info(f"Tareas actualmente asignadas a los roles: **{roles_pending}**")
                else:
                    for at in user_active_tasks:
                        # SLA elapsed for this task
                        sla_info_html = ""
                        if at.sla_hours and at.created_at:
                            elapsed_h = (datetime.utcnow() - at.created_at).total_seconds() / 3600
                            elapsed_days = elapsed_h / 24
                            sla_days = at.sla_hours
                            bar_pct = min(100.0, (elapsed_h / (at.sla_hours * 24.0)) * 100.0)
                            bar_color = "#ef4444" if elapsed_h > (at.sla_hours * 24.0) else ("#f59e0b" if bar_pct > 75 else "#10b981")
                            sla_info_html = f"""
                            <div style='margin-top:8px; padding: 10px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;'>
                                <div style='display: flex; justify-content: space-between; font-size: 0.82rem; color: #475569;'>
                                    <span><b>Progreso de SLA:</b> {elapsed_days:.1f}d / {sla_days:.1f}d días ({elapsed_h:.1f}h / {at.sla_hours * 24.0:.1f}h usadas)</span>
                                    <span style='font-weight: bold; color: {bar_color};'>{bar_pct:.1f}%</span>
                                </div>
                                <div style='background:#e2e8f0;border-radius:4px;height:12px;margin-top:6px;overflow:hidden;'>
                                    <div style='width:{bar_pct:.1f}%;background:{bar_color};height:12px;border-radius:4px;'></div>
                                </div>
                            </div>"""
                        elif not at.sla_hours:
                            sla_info_html = "<div style='margin-top:6px;font-size:0.8rem;color:#94a3b8;'>⏱ Sin tiempo definido para esta etapa.</div>"

                        st.markdown(f"<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                        st.markdown(f"##### Etapa Activa: **{at.node.name}**")
                        current_assigned_role_name = at.node.role.name if at.node.role else at.assigned_role.name
                        st.write(f"Asignado al Rol: **{current_assigned_role_name}**")
                        st.markdown(sla_info_html, unsafe_allow_html=True)


                        node_transitions = db.query(WorkflowTransition).filter(
                            WorkflowTransition.process_id == instance.process_id,
                            WorkflowTransition.source_node_id == at.node_id
                        ).all()

                        comment_input = st.text_area(
                            "Comentario / Observación (Obligatorio):",
                            placeholder="Ingresa detalles sobre este avance...",
                            key=f"comment_{at.id}"
                        )

                        # DocNum inline update option
                        docnum_inline = st.text_input(
                            "Actualizar DocNum al avanzar (Opcional):",
                            value=instance.docnum or "",
                            placeholder="Ej. 10045",
                            key=f"docnum_inline_{at.id}"
                        )

                        # File uploader option
                        uploaded_file = st.file_uploader(
                            "Adjuntar archivo a esta etapa (Opcional):",
                            key=f"task_upload_{at.id}"
                        )

                        is_task_node = (at.node.type == 'TASK')
                        if is_task_node:
                            btn_label = "Confirmar y Continuar" if len(node_transitions) > 1 else (node_transitions[0].action_name if node_transitions else "Completar Tarea")
                            if st.button(f"➡️ {btn_label}", key=f"action_btn_confirm_{at.id}", use_container_width=True):
                                if not comment_input.strip():
                                    st.error("⚠️ Debes ingresar un comentario u observación para avanzar.")
                                elif node_transitions:
                                    try:
                                        if uploaded_file is not None:
                                            save_task_attachment(db, instance.id, at.id, user.id, uploaded_file)
                                        WorkflowEngine.execute_transition(
                                            db=db,
                                            instance_id=instance.id,
                                            transition_id=node_transitions[0].id,
                                            user_id=user.id,
                                            comment_text=comment_input,
                                            docnum_value=docnum_inline if docnum_inline.strip() != (instance.docnum or "") else None
                                        )
                                        st.success(f"Etapa '{at.node.name}' completada con éxito.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                                else:
                                    st.error("No hay transiciones salientes configuradas para este nodo.")
                        else:
                            if not node_transitions:
                                st.warning("No hay caminos de decisión configurados para esta etapa.")
                            else:
                                cols = st.columns(len(node_transitions))
                                for idx, trans in enumerate(node_transitions):
                                    with cols[idx]:
                                        if st.button(f"➡️ {trans.action_name}", key=f"action_btn_{trans.id}", use_container_width=True):
                                            if not comment_input.strip():
                                                st.error("⚠️ Debes ingresar un comentario u observación para avanzar.")
                                            else:
                                                try:
                                                    if uploaded_file is not None:
                                                        save_task_attachment(db, instance.id, at.id, user.id, uploaded_file)
                                                    WorkflowEngine.execute_transition(
                                                        db=db,
                                                        instance_id=instance.id,
                                                        transition_id=trans.id,
                                                        user_id=user.id,
                                                        comment_text=comment_input,
                                                        docnum_value=docnum_inline if docnum_inline.strip() != (instance.docnum or "") else None
                                                    )
                                                    st.success(f"Acción '{trans.action_name}' completada con éxito.")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error: {str(e)}")
                        st.markdown("</div>", unsafe_allow_html=True)

                # Admin / Manager: Cancel Workflow
                if st.session_state.user['role'] in ['Administrador', 'Gerencia']:
                    with st.expander("⚠️ Opciones Avanzadas (Administración)"):
                        st.markdown("<p style='color: #ef4444;'><b>Cancelar Instancia de Workflow</b></p>", unsafe_allow_html=True)
                        cancel_reason = st.text_input("Motivo de cancelación (Requerido):", placeholder="Ej. Orden de compra cancelada en SAP.")
                        if st.button("Confirmar Cancelación", type="primary"):
                            if not cancel_reason.strip():
                                st.error("Debes ingresar el motivo de cancelación.")
                            else:
                                try:
                                    WorkflowEngine.cancel_instance(db, instance.id, user.id, cancel_reason.strip())
                                    st.success("Flujo cancelado con éxito.")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(str(ex))

            # 5. Finished Workflow View
            else:
                st.markdown("<div class='section-header'>🏁 Estado Final del Flujo</div>", unsafe_allow_html=True)
                if instance.status == 'COMPLETED':
                    st.success("Este proceso ha finalizado correctamente.")
                elif instance.status == 'CANCELLED':
                    st.error("Este proceso fue CANCELADO.")

                if st.session_state.user['role'] in ['Administrador', 'Gerencia']:
                    with st.expander("🛠️ Reabrir Proceso Cerrado"):
                        reopen_reason = st.text_area("Motivo de la reapertura (Requerido):", placeholder="Detalla por qué es necesario reabrir este flujo...")
                        if st.button("Confirmar Reapertura", key="reopen_confirm"):
                            if not reopen_reason.strip():
                                st.error("Por favor, ingresa un motivo para reabrir el flujo.")
                            else:
                                try:
                                    WorkflowEngine.reopen_instance(db, instance.id, user.id, reopen_reason.strip())
                                    st.success("El flujo ha sido reabierto con éxito.")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(str(ex))

            # ─────────────────────────────────────────────────────────────
            # 6. Historial y Auditoría del Proceso — con duración de nodos
            # ─────────────────────────────────────────────────────────────
            st.markdown("<div class='section-header'>📜 Historial y Auditoría del Proceso</div>", unsafe_allow_html=True)

            history = db.query(WorkflowHistory).filter(
                WorkflowHistory.instance_id == instance.id
            ).order_by(WorkflowHistory.timestamp.asc()).all()

            # Filter out attachment and comment logs to show only stages/transitions
            filtered_history = [e for e in history if e.action not in ['ATTACHMENT', 'COMMENT']]

            if not filtered_history:
                st.info("No hay historial de etapas disponible.")
            else:
                import os
                from components.attachments import UPLOAD_DIR
                
                for i, entry in enumerate(filtered_history):
                    time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M")
                    user_roles = ", ".join([role.name for role in entry.user.roles]) if entry.user.roles else "Sin Rol"

                    # Determine label and color
                    is_completed_task = False
                    if entry.action == 'CREATE':
                        action_lbl = "🆕 Creación del Workflow"
                        color = "#0ea5e9"
                    elif entry.action == 'TRANSITION':
                        source_name = entry.source_node.name if entry.source_node else "Inicio"
                        action_lbl = f"✅ Etapa Completada: {source_name}"
                        color = "#10b981"
                        is_completed_task = True
                    elif entry.action == 'CANCEL':
                        action_lbl = "❌ Cancelación"
                        color = "#ef4444"
                    elif entry.action == 'REOPEN':
                        action_lbl = "🔄 Reapertura"
                        color = "#f59e0b"
                    elif entry.action == 'COMPLETE':
                        action_lbl = "🏁 Cierre de Proceso"
                        color = "#8b5cf6"
                    elif entry.action == 'UPDATE_DOCNUM':
                        action_lbl = "🔢 Actualización DocNum"
                        color = "#06b6d4"
                    else:
                        action_lbl = entry.action
                        color = "#6b7280"

                    # Calculate duration: time from this entry to next entry (or now if last)
                    duration_html = ""
                    next_ts = None
                    if i + 1 < len(filtered_history):
                        next_ts = filtered_history[i + 1].timestamp
                    elif instance.status == 'ACTIVE':
                        next_ts = datetime.utcnow()
                    elif i == len(filtered_history) - 1 and instance.status in ['COMPLETED', 'CANCELLED']:
                        next_ts = entry.timestamp  # zero duration for last entry

                    if next_ts and next_ts != entry.timestamp:
                        delta_secs = (next_ts - entry.timestamp).total_seconds()
                        if delta_secs < 60:
                            dur_str = f"{delta_secs:.0f}s"
                        elif delta_secs < 3600:
                            dur_str = f"{delta_secs / 60:.1f} min"
                        elif delta_secs < 86400:
                            dur_str = f"{delta_secs / 3600:.1f} h"
                        else:
                            dur_str = f"{delta_secs / 86400:.1f} días"

                        # Compare vs SLA if source node has sla_hours
                        sla_warn = ""
                        if entry.source_node_id:
                            src_node = db.query(WorkflowNode).filter(WorkflowNode.id == entry.source_node_id).first()
                            if src_node and src_node.sla_hours:
                                sla_secs = src_node.sla_hours * 24 * 3600
                                if delta_secs > sla_secs:
                                    sla_warn = f" <span style='color:#ef4444;font-weight:600;'>(⚠️ excedió SLA de {src_node.sla_hours}d)</span>"

                        duration_html = f"<span style='display:inline-block;background:#f1f5f9;color:#475569;padding:1px 8px;border-radius:10px;font-size:0.78rem;font-weight:500;margin-left:8px;'>⏱ {dur_str}{sla_warn}</span>"

                    # Fetch comments and attachments for this task entry
                    task_comments = []
                    task_attachments = []
                    if entry.task_id:
                        task_comments = db.query(WorkflowComment).filter(WorkflowComment.task_id == entry.task_id).all()
                        task_attachments = db.query(WorkflowAttachment).filter(WorkflowAttachment.task_id == entry.task_id).all()

                    # Clean the transition comment if it contains generic boilerplate
                    comment_disp = entry.comment or ""
                    if " Comentario: " in comment_disp:
                        comment_disp = comment_disp.split(" Comentario: ", 1)[1]
                    elif comment_disp.startswith("Acción ejecutada: "):
                        comment_disp = ""

                    # Gather all unique comments for this step
                    all_comments = []
                    if comment_disp:
                        all_comments.append(comment_disp)
                    for tc in task_comments:
                        if tc.comment_text not in all_comments and tc.comment_text != comment_disp:
                            all_comments.append(tc.comment_text)

                    comments_html = ""
                    if all_comments:
                        comments_joined = "<br>".join([f"💬 {c}" for c in all_comments])
                        comments_html = f"<div style='color: #475569; font-size: 0.9rem; margin-top: 3px; font-style: italic;'>{comments_joined}</div>"

                    # Gather all task attachments as clean download links
                    attachments_html = ""
                    if task_attachments:
                        import base64
                        links = []
                        for ta in task_attachments:
                            file_full_path = ta.file_path if os.path.isabs(ta.file_path) else os.path.join(UPLOAD_DIR, ta.file_path)
                            if os.path.exists(file_full_path):
                                try:
                                    with open(file_full_path, "rb") as f:
                                        b64 = base64.b64encode(f.read()).decode()
                                    links.append(f'<a href="data:application/octet-stream;base64,{b64}" download="{ta.file_name}" style="color: #0284c7; text-decoration: none; font-weight: 500; font-size: 0.85rem; margin-right: 15px;">📎 {ta.file_name} ({ta.file_size / 1024:.1f} KB)</a>')
                                except Exception:
                                    links.append(f'<span style="color: #94a3b8; font-size: 0.85rem; margin-right: 15px;">⚠️ {ta.file_name} (error)</span>')
                            else:
                                links.append(f'<span style="color: #ef4444; font-size: 0.85rem; margin-right: 15px;">⚠️ {ta.file_name} (no disponible)</span>')
                        attachments_html = f"<div style='margin-top: 5px; display: flex; flex-wrap: wrap;'>{''.join(links)}</div>"

                    st.markdown(f"""
                    <div style="padding-left: 10px; border-left: 3px solid {color}; margin-bottom: 12px;">
                        <div style="font-size: 0.8rem; color: #64748b;">
                            <b>{time_str}</b> | Usuario: <b>{entry.user.full_name}</b> ({user_roles}){duration_html}
                        </div>
                        <div style="font-weight: 600; font-size: 0.95rem; color: #1e293b; margin-top: 2px;">
                            {action_lbl}
                        </div>
                        {comments_html}
                        {attachments_html}
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("")

                # Render tasks in progress at the end
                if instance.status == 'ACTIVE':
                    pending_tasks = db.query(WorkflowTask).filter(
                        WorkflowTask.instance_id == instance.id,
                        WorkflowTask.status == 'PENDING'
                    ).all()

                    for pt in pending_tasks:
                        elapsed_h = (datetime.utcnow() - pt.created_at).total_seconds() / 3600
                        sla_info = ""
                        if pt.sla_hours:
                            if elapsed_h > pt.sla_hours * 24:
                                sla_info = f" (⚠️ Retrasado por {(elapsed_h/24.0 - pt.sla_hours):.1f}d)"
                            else:
                                sla_info = f" ({pt.sla_hours - elapsed_h/24.0:.1f}d restantes de SLA)"

                        st.markdown(f"""
                        <div style="padding-left: 10px; border-left: 3px dashed #f59e0b; margin-bottom: 15px; background: #fffbeb; padding-top: 5px; padding-bottom: 5px; border-radius: 0 8px 8px 0;">
                            <div style="font-size: 0.8rem; color: #b45309;">
                                <b>En Proceso</b> desde {pt.created_at.strftime("%Y-%m-%d %H:%M")}{sla_info}
                            </div>
                            <div style="font-weight: 600; font-size: 0.95rem; color: #b45309; margin-top: 2px;">
                                ⏳ Etapa Activa: {pt.node.name}
                            </div>
                            <div style="font-size: 0.9rem; color: #78350f; margin-top: 2px;">
                                Asignado al Rol: <b>{pt.assigned_role.name}</b>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)


