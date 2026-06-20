import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_db
from models import WorkflowInstance, WorkflowTask, WorkflowUser, WorkflowHistory, WorkflowTransition, WorkflowComment, WorkflowAttachment
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

    # SLA check for current active task
    sla_alert_html = ""
    active_task_for_sla = db.query(WorkflowTask).filter(
        WorkflowTask.instance_id == instance.id,
        WorkflowTask.status == 'PENDING'
    ).first()

    if active_task_for_sla and active_task_for_sla.sla_hours and active_task_for_sla.created_at:
        elapsed_h = (datetime.utcnow() - active_task_for_sla.created_at).total_seconds() / 3600
        remaining_h = active_task_for_sla.sla_hours - elapsed_h
        if remaining_h < 0:
            sla_alert_html = f"""
            <div style="background:#fee2e2;border-left:4px solid #ef4444;padding:10px 14px;border-radius:6px;margin-top:10px;">
                ⚠️ <b style="color:#b91c1c;">SLA VENCIDO:</b> <span style="color:#7f1d1d;">Esta etapa lleva {abs(remaining_h):.1f}h de retraso sobre el SLA de {active_task_for_sla.sla_hours}h configurado.</span>
            </div>"""
        elif remaining_h < active_task_for_sla.sla_hours * 0.25:
            sla_alert_html = f"""
            <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:6px;margin-top:10px;">
                ⏳ <b style="color:#b45309;">SLA PRÓXIMO A VENCER:</b> <span style="color:#78350f;">Quedan {remaining_h:.1f}h de las {active_task_for_sla.sla_hours}h del SLA.</span>
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
                            from models import WorkflowHistory as WH, WorkflowComment as WC
                            db.add(WH(
                                instance_id=instance.id,
                                source_node_id=instance.current_node_id,
                                target_node_id=instance.current_node_id,
                                user_id=user.id,
                                action='UPDATE_DOCNUM',
                                comment=f"DocNum actualizado a '{new_docnum.strip()}'. {docnum_comment.strip()}",
                                timestamp=datetime.utcnow()
                            ))
                            db.add(WC(
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

        user_role_ids = [role.id for role in user.roles]
        user_active_tasks = [at for at in active_tasks if at.assigned_role_id in user_role_ids]

        if not active_tasks:
            st.warning("El flujo está activo pero no tiene tareas pendientes configuradas.")
        elif not user_active_tasks:
            st.warning("🔒 No tienes acciones disponibles en esta etapa. El flujo está esperando la resolución del rol responsable.")
            roles_pending = ", ".join(list(set([at.assigned_role.name for at in active_tasks])))
            st.info(f"Tareas actualmente asignadas a los roles: **{roles_pending}**")
        else:
            for at in user_active_tasks:
                # SLA elapsed for this task
                sla_info_html = ""
                if at.sla_hours and at.created_at:
                    elapsed_h = (datetime.utcnow() - at.created_at).total_seconds() / 3600
                    remaining_h = at.sla_hours - elapsed_h
                    bar_pct = min(100, (elapsed_h / at.sla_hours) * 100)
                    bar_color = "#ef4444" if remaining_h < 0 else ("#f59e0b" if bar_pct > 75 else "#10b981")
                    sla_info_html = f"""
                    <div style='margin-top:8px;'>
                        <span style='font-size:0.82rem;color:#64748b;'>SLA: {elapsed_h:.1f}h / {at.sla_hours}h usadas</span>
                        <div style='background:#e2e8f0;border-radius:4px;height:6px;margin-top:4px;'>
                            <div style='width:{bar_pct:.0f}%;background:{bar_color};height:6px;border-radius:4px;'></div>
                        </div>
                    </div>"""
                elif not at.sla_hours:
                    sla_info_html = "<div style='margin-top:6px;font-size:0.8rem;color:#94a3b8;'>⏱ Sin tiempo definido para esta etapa.</div>"

                st.markdown(f"<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                st.markdown(f"##### Etapa Activa: **{at.node.name}**")
                st.write(f"Asignado al Rol: **{at.assigned_role.name}**")
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

                is_task_node = (at.node.type == 'TASK')
                if is_task_node:
                    btn_label = "Confirmar y Continuar" if len(node_transitions) > 1 else (node_transitions[0].action_name if node_transitions else "Completar Tarea")
                    if st.button(f"➡️ {btn_label}", key=f"action_btn_confirm_{at.id}", use_container_width=True):
                        if not comment_input.strip():
                            st.error("⚠️ Debes ingresar un comentario u observación para avanzar.")
                        elif node_transitions:
                            try:
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
                    from models import WorkflowNode
                    src_node = db.query(WorkflowNode).filter(WorkflowNode.id == entry.source_node_id).first()
                    if src_node and src_node.sla_hours:
                        sla_secs = src_node.sla_hours * 3600
                        if delta_secs > sla_secs:
                            sla_warn = f" <span style='color:#ef4444;font-weight:600;'>(⚠️ excedió SLA de {src_node.sla_hours}h)</span>"

                duration_html = f"<span style='display:inline-block;background:#f1f5f9;color:#475569;padding:1px 8px;border-radius:10px;font-size:0.78rem;font-weight:500;margin-left:8px;'>⏱ {dur_str}{sla_warn}</span>"

            st.markdown(f"""
            <div style="padding-left: 10px; border-left: 3px solid {color}; margin-bottom: 5px;">
                <div style="font-size: 0.8rem; color: #64748b;">
                    <b>{time_str}</b> | Usuario: <b>{entry.user.full_name}</b> ({user_roles}){duration_html}
                </div>
                <div style="font-weight: 500; font-size: 0.95rem; color: #1e293b; margin-top: 2px;">
                    {action_lbl}
                </div>
                <div style="font-size: 0.9rem; color: #475569; font-style: italic; margin-top: 3px; margin-bottom: 5px;">
                    {entry.comment or ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Interactive popover for completed tasks
            if is_completed_task and entry.task_id:
                task_comments = db.query(WorkflowComment).filter(WorkflowComment.task_id == entry.task_id).all()
                task_attachments = db.query(WorkflowAttachment).filter(WorkflowAttachment.task_id == entry.task_id).all()

                if task_comments or task_attachments:
                    if hasattr(st, "popover"):
                        with st.popover("📂 Ver comentarios y adjuntos", key=f"pop_{entry.id}"):
                            if task_comments:
                                st.markdown("**💬 Comentarios registrados:**")
                                for tc in task_comments:
                                    st.markdown(f"- **{tc.user.full_name}**: {tc.comment_text}")
                            if task_attachments:
                                st.markdown("**📎 Archivos adjuntos:**")
                                for ta in task_attachments:
                                    file_full_path = ta.file_path if os.path.isabs(ta.file_path) else os.path.join(UPLOAD_DIR, ta.file_path)
                                    if os.path.exists(file_full_path):
                                        with open(file_full_path, "rb") as file_bytes:
                                            st.download_button(
                                                label=f"⬇️ Descargar: {ta.file_name} ({ta.file_size / 1024:.1f} KB)",
                                                data=file_bytes.read(),
                                                file_name=ta.file_name,
                                                key=f"dl_hist_{ta.id}_{entry.id}"
                                            )
                                    else:
                                        st.warning(f"⚠️ Archivo '{ta.file_name}' no disponible en el servidor.")
                            else:
                                st.info("No hay archivos adjuntos en esta tarea.")
                    else:
                        with st.expander("📂 Ver comentarios y adjuntos", expanded=False):
                            if task_comments:
                                st.markdown("**💬 Comentarios registrados:**")
                                for tc in task_comments:
                                    st.markdown(f"- **{tc.user.full_name}**: {tc.comment_text}")
                            if task_attachments:
                                st.markdown("**📎 Archivos adjuntos:**")
                                for ta in task_attachments:
                                    file_full_path = ta.file_path if os.path.isabs(ta.file_path) else os.path.join(UPLOAD_DIR, ta.file_path)
                                    if os.path.exists(file_full_path):
                                        with open(file_full_path, "rb") as file_bytes:
                                            st.download_button(
                                                label=f"⬇️ Descargar: {ta.file_name} ({ta.file_size / 1024:.1f} KB)",
                                                data=file_bytes.read(),
                                                file_name=ta.file_name,
                                                key=f"dl_hist_{ta.id}_{entry.id}"
                                            )
                                    else:
                                        st.warning(f"⚠️ Archivo '{ta.file_name}' no disponible en el servidor.")
                            else:
                                st.info("No hay archivos adjuntos en esta tarea.")
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
                    if elapsed_h > pt.sla_hours:
                        sla_info = f" (⚠️ Retrasado por {elapsed_h - pt.sla_hours:.1f}h)"
                    else:
                        sla_info = f" ({pt.sla_hours - elapsed_h:.1f}h restantes de SLA)"

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

    # 7. Render Comments and Attachments
    # Pass the active task_id so uploads get linked to the current node for forwarding
    active_task_for_attach = db.query(WorkflowTask).filter(
        WorkflowTask.instance_id == instance.id,
        WorkflowTask.status == 'PENDING',
        WorkflowTask.assigned_role_id.in_([role.id for role in user.roles])
    ).first()
    active_task_id = active_task_for_attach.id if active_task_for_attach else None

    CommentsComponent.render_comments_section(db, instance.id, user.id)
    AttachmentsComponent.render_attachments_section(db, instance.id, user.id, task_id=active_task_id)
