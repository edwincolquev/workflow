import streamlit as st
from database import get_db
from models import WorkflowInstance, WorkflowTask, WorkflowUser, WorkflowHistory, WorkflowTransition
from engine import WorkflowEngine
from components.ui_helpers import UIHelpers
from components.comments import CommentsComponent
from components.attachments import AttachmentsComponent

# 1. Session check
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>📋 Ejecución & Detalle del Workflow</h1>", unsafe_allow_html=True)

# 2. Check selected instance
instance_id = st.session_state.get("selected_workflow_instance_id")
if not instance_id:
    st.info("💡 No se ha seleccionado ninguna instancia de workflow.\n\nPor favor, ve a **Bandeja de Entrada (Bandeja)** o a los módulos de análisis (**Tránsitos** o **Productos Nuevos**) y selecciona una tarea/registro para interactuar.")
    st.stop()

with get_db() as db:
    # Fetch instance
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance:
        st.error(f"La instancia de workflow #{instance_id} no existe.")
        st.stop()
        
    user = db.query(WorkflowUser).filter(WorkflowUser.id == st.session_state.user['id']).first()
    
    # 3. Render General Information Card
    status_colors = {
        'ACTIVE': 'blue',
        'COMPLETED': 'green',
        'CANCELLED': 'red'
    }
    status_badge = UIHelpers.get_badge_html(instance.status, status_colors.get(instance.status, 'gray'))
    stage_badge = UIHelpers.get_badge_html(instance.current_node.name if instance.current_node else "N/A", 'yellow')
    
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
            <div><b>Referencia ERP:</b> {instance.external_ref or 'Ninguna'}</div>
            <div><b>Creado Por:</b> {instance.created_by.full_name}</div>
            <div><b>Creado el:</b> {instance.created_at.strftime('%Y-%m-%d %H:%M')}</div>
            <div><b>Última Actividad:</b> {instance.updated_at.strftime('%Y-%m-%d %H:%M')}</div>
            <div><b>ID de Instancia:</b> #{instance.id}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Email Status Report Expander
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
                        # Fetch history and convert to DataFrame
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
        
        # Fetch active tasks for this instance
        active_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.instance_id == instance.id,
            WorkflowTask.status == 'PENDING'
        ).all()
        
        # Filter active tasks that the user has authorization for
        user_role_ids = [role.id for role in user.roles]
        user_active_tasks = [at for at in active_tasks if at.assigned_role_id in user_role_ids]
        
        if not active_tasks:
            st.warning("El flujo está activo pero no tiene tareas pendientes configuradas.")
        elif not user_active_tasks:
            st.warning("🔒 No tienes acciones disponibles en esta etapa. El flujo está esperando la resolución del rol responsable.")
            # Show current pending assignments
            roles_pending = ", ".join(list(set([at.assigned_role.name for at in active_tasks])))
            st.info(f"Tareas actualmente asignadas a los roles: **{roles_pending}**")
        else:
            # Render execution box for each assigned active task
            for at in user_active_tasks:
                st.markdown(f"<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                st.markdown(f"##### Etapa Activa: **{at.node.name}**")
                st.write(f"Asignado al Rol: **{at.assigned_role.name}**")
                
                # Fetch transitions originating from this specific node for this user's role
                node_transitions = db.query(WorkflowTransition).filter(
                    WorkflowTransition.process_id == instance.process_id,
                    WorkflowTransition.source_node_id == at.node_id,
                    WorkflowTransition.role_id == at.assigned_role_id
                ).all()
                
                # Render a text area for an optional comment before transition
                comment_input = st.text_area(
                    "Comentario / Justificación (Opcional):", 
                    placeholder="Ingresa detalles sobre este avance...", 
                    key=f"comment_{at.id}"
                )
                
                is_task_node = (at.node.type == 'TASK')
                if is_task_node:
                    # TASK node: show a single confirmation button
                    btn_label = "Confirmar y Continuar" if len(node_transitions) > 1 else (node_transitions[0].action_name if node_transitions else "Completar Tarea")
                    if st.button(f"➡️ {btn_label}", key=f"action_btn_confirm_{at.id}", use_container_width=True):
                        if node_transitions:
                            try:
                                WorkflowEngine.execute_transition(
                                    db=db,
                                    instance_id=instance.id,
                                    transition_id=node_transitions[0].id,
                                    user_id=user.id,
                                    comment_text=comment_input
                                )
                                st.success(f"Etapa '{at.node.name}' completada con éxito.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        else:
                            st.error("No hay transiciones salientes configuradas para este nodo.")
                else:
                    # DECISION node: show all transition buttons
                    if not node_transitions:
                        st.warning("No hay caminos de decisión configurados para esta etapa.")
                    else:
                        cols = st.columns(len(node_transitions))
                        for idx, trans in enumerate(node_transitions):
                            with cols[idx]:
                                if st.button(f"➡️ {trans.action_name}", key=f"action_btn_{trans.id}", use_container_width=True):
                                    try:
                                        WorkflowEngine.execute_transition(
                                            db=db,
                                            instance_id=instance.id,
                                            transition_id=trans.id,
                                            user_id=user.id,
                                            comment_text=comment_input
                                        )
                                        st.success(f"Acción '{trans.action_name}' completada con éxito.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                st.markdown("</div>", unsafe_allow_html=True)

        # Administrator / Manager override action: Cancel Workflow
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

    # 5. Finished Workflow View (Completed or Cancelled)
    else:
        st.markdown("<div class='section-header'>🏁 Estado Final del Flujo</div>", unsafe_allow_html=True)
        if instance.status == 'COMPLETED':
            st.success("Este proceso ha finalizado correctamente. Toda la mercadería o items han sido ingresados / habilitados en el sistema.")
        elif instance.status == 'CANCELLED':
            st.error("Este proceso fue CANCELADO.")
            
        # Reopen option for Admin/Gerencia
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

    # 6. Render Full Workflow History Timeline
    st.markdown("<div class='section-header'>📜 Historial y Auditoría del Proceso</div>", unsafe_allow_html=True)
    history = db.query(WorkflowHistory).filter(
        WorkflowHistory.instance_id == instance.id
    ).order_by(WorkflowHistory.timestamp.asc()).all()

    if not history:
        st.info("No hay historial disponible.")
    else:
        for entry in history:
            time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            user_roles = ", ".join([role.name for role in entry.user.roles]) if entry.user.roles else "Sin Rol"
            action_desc = entry.action
            
            # Nicer labels for action
            if entry.action == 'CREATE':
                action_lbl = "🆕 Creación del Workflow"
                color = "#0ea5e9"
            elif entry.action == 'TRANSITION':
                target_name = entry.target_node.name if entry.target_node else "Avance de Etapa"
                action_lbl = f"🔀 Etapa: {target_name}"
                color = "#10b981"
            elif entry.action == 'CANCEL':
                action_lbl = "❌ Cancelación"
                color = "#ef4444"
            elif entry.action == 'REOPEN':
                action_lbl = "🔄 Reapertura"
                color = "#f59e0b"
            elif entry.action == 'COMPLETE':
                action_lbl = "🏁 Cierre de Proceso"
                color = "#8b5cf6"
            else:
                action_lbl = entry.action
                color = "#6b7280"

            st.markdown(f"""
            <div style="padding-left: 10px; border-left: 3px solid {color}; margin-bottom: 15px;">
                <div style="font-size: 0.8rem; color: #64748b;">
                    <b>{time_str}</b> | Usuario: <b>{entry.user.full_name}</b> ({user_roles})
                </div>
                <div style="font-weight: 500; font-size: 0.95rem; color: #1e293b; margin-top: 2px;">
                    {action_lbl}
                </div>
                <div style="font-size: 0.9rem; color: #475569; font-style: italic; margin-top: 3px;">
                    {entry.comment or ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 7. Render Comments and Attachments
    CommentsComponent.render_comments_section(db, instance.id, user.id)
    AttachmentsComponent.render_attachments_section(db, instance.id, user.id)
