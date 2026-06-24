import streamlit as st
import hashlib
from database import get_db
from models import WorkflowUser
from components.ui_helpers import UIHelpers

# 1. Config page first
st.set_page_config(
    page_title="Portal de Cadena de Suministro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply global CSS styles
UIHelpers.apply_custom_css()

# 2. Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_login(username, password):
    with get_db() as db:
        user = db.query(WorkflowUser).filter(
            WorkflowUser.username == username, 
            WorkflowUser.active == True
        ).first()
        if user and user.password_hash == hash_password(password):
            role_name = user.roles[0].name if user.roles else "Sin Rol"
            return {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": role_name
            }
    return None

# Intercept token requests from email links
if "token" in st.query_params:
    token = st.query_params["token"]
    comment_param = st.query_params.get("comment", "")
    
    # Lazy imports to avoid circular dependency
    from services.email_service import verify_task_token
    from models import WorkflowTask, WorkflowInstance, WorkflowHistory, WorkflowAttachment
    from engine import WorkflowEngine
    import os
    from datetime import datetime
    
    payload = verify_task_token(token)
    
    if not payload:
        st.error("❌ Enlace no válido, expirado o firma corrupta. Por favor, ingresa al portal de forma manual para resolver la tarea.")
        st.stop()
        
    task_id = payload["task_id"]
    transition_id_token = payload.get("transition_id")
    action_name = payload.get("action_name")
    user_id = payload["user_id"]
    
    with get_db() as db:
        try:
            # 1. Fetch task and check state (Requirement 1: Already processed link check)
            task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
            
            if not task:
                st.error("❌ La tarea referenciada por este enlace no existe.")
                st.stop()
                
            # If task is not pending, or the instance is not active
            if task.status != 'PENDING' or task.instance.status != 'ACTIVE':
                completer_name = "un usuario del sistema"
                completed_at_str = "recientemente"
                
                if task.completed_by:
                    completer_name = task.completed_by.full_name
                if task.completed_at:
                    completed_at_str = task.completed_at.strftime('%Y-%m-%d %H:%M')
                else:
                    # Look up in history
                    hist = db.query(WorkflowHistory).filter(
                        WorkflowHistory.instance_id == task.instance_id,
                        WorkflowHistory.task_id == task.id,
                        WorkflowHistory.action == 'TRANSITION'
                    ).first()
                    if hist:
                        completer_name = hist.user.full_name
                        completed_at_str = hist.timestamp.strftime('%Y-%m-%d %H:%M')
                
                status_text = "COMPLETADA" if task.status == 'COMPLETED' else task.status
                instance_status = task.instance.status
                
                st.warning(f"⚠️ Esta tarea ya fue procesada anteriormente.")
                st.info(f"""
                **Detalles del Procesamiento:**
                * **Estado de la Tarea:** {status_text}
                * **Resuelta por:** {completer_name}
                * **Fecha/Hora:** {completed_at_str}
                * **Estado del Flujo General:** {instance_status}
                
                *Nota: No se puede volver a aplicar la acción de este enlace.*
                """)
                
                if st.button("Ir al Portal de Cadena de Suministro"):
                    st.query_params.clear()
                    st.rerun()
                st.stop()
                
            # 2. If task is pending, render landing page for confirmation
            from models import WorkflowUser, WorkflowTransition
            user = db.query(WorkflowUser).filter(WorkflowUser.id == user_id).first()
            if not user:
                st.error("❌ El usuario firmante del token no existe.")
                st.stop()
                
            user_role_ids = [r.id for r in user.roles]
            if task.assigned_role_id not in user_role_ids:
                st.error("❌ No tienes el rol requerido para procesar esta transición.")
                st.stop()
                
            # Dynamic Transition Resolution (Mid-flight Process Updates Resilience)
            transition = None
            if action_name:
                transition = db.query(WorkflowTransition).filter(
                    WorkflowTransition.process_id == task.instance.process_id,
                    WorkflowTransition.source_node_id == task.node_id,
                    WorkflowTransition.action_name == action_name
                ).first()
            
            if not transition and transition_id_token:
                transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id_token).first()
                if transition and transition.source_node_id != task.node_id:
                    transition = None
                    
            if not transition and task.node.type == 'TASK':
                transition = db.query(WorkflowTransition).filter(
                    WorkflowTransition.process_id == task.instance.process_id,
                    WorkflowTransition.source_node_id == task.node_id
                ).first()
                
            if not transition:
                st.error("❌ Transición no válida para el estado actual de la tarea. La configuración del proceso puede haber cambiado.")
                st.stop()
                
            # ── Page Header ─────────────────────────────────────────────────────────
            inst = task.instance
            UIHelpers.apply_custom_css()
            st.markdown("<h2 class='main-header'>⚡ Confirmación de Aprobación vía Email</h2>", unsafe_allow_html=True)
            
            # Instance summary card
            code_display = inst.internal_code or f"#{inst.id}"
            st.markdown(f"""
            <div class="glass-card" style="padding: 16px; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div style="font-size: 0.78rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px;">Instancia</div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: #0f172a; margin-top: 2px;">{inst.title}</div>
                        <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">
                            Proceso: <b>{inst.process.name}</b> &nbsp;|&nbsp; Código: <b>{code_display}</b>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 0.78rem; text-transform: uppercase; color: #94a3b8;">Etapa Actual</div>
                        <span style="background:#fef3c7;color:#b45309;padding:4px 10px;border-radius:5px;font-weight:700;font-size:0.9rem;">{task.node.name}</span>
                        <div style="font-size: 0.82rem; color: #64748b; margin-top: 4px;">👤 {user.full_name} ({user.roles[0].name if user.roles else 'Sin Rol'})</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Section 1: ERP Data & DocNum Editor ─────────────────────────────────
            st.markdown("<div class='section-header'>📦 Documento ERP (SAP B1)</div>", unsafe_allow_html=True)
            
            # Inline DocNum editor (outside form so it can submit independently)
            current_docnum = inst.docnum or ""
            col_dn1, col_dn2 = st.columns([3, 1])
            with col_dn1:
                new_docnum_input = st.text_input(
                    "DocNum (Número de Documento SAP B1):",
                    value=current_docnum,
                    placeholder="Ej. 10045",
                    key="landing_docnum_input"
                )
            with col_dn2:
                st.write("")
                st.write("")
                save_docnum_btn = st.button("💾 Guardar DocNum", key="landing_save_docnum", use_container_width=True)
            
            if save_docnum_btn:
                if new_docnum_input.strip() and new_docnum_input.strip() != current_docnum:
                    try:
                        inst.docnum = new_docnum_input.strip()
                        inst.external_ref = f"DocNum:{new_docnum_input.strip()}"
                        inst.updated_at = datetime.utcnow()
                        db.add(WorkflowHistory(
                            instance_id=inst.id,
                            source_node_id=inst.current_node_id,
                            target_node_id=inst.current_node_id,
                            user_id=user.id,
                            action='UPDATE_DOCNUM',
                            comment=f"DocNum actualizado a '{new_docnum_input.strip()}' vía email-landing.",
                            timestamp=datetime.utcnow()
                        ))
                        db.commit()
                        st.success(f"DocNum actualizado a **{new_docnum_input.strip()}**.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar DocNum: {str(e)}")
                elif not new_docnum_input.strip():
                    st.warning("Ingrese un valor de DocNum válido.")
                else:
                    st.info("El DocNum ingresado es igual al actual.")

            # ERP document detail panel
            active_docnum = inst.docnum
            if active_docnum:
                try:
                    from services.data_loader import DataLoaderService
                    df_erp = DataLoaderService.get_sap_document_details(db, active_docnum)
                    if not df_erp.empty:
                        first_row = df_erp.iloc[0]
                        c_e1, c_e2, c_e3 = st.columns(3)
                        with c_e1:
                            st.metric("Número SAP B1", str(first_row.get('Número SAP', active_docnum)))
                        with c_e2:
                            st.metric("Proveedor", str(first_row.get('Nombre Proveedor', '—')))
                        with c_e3:
                            monto = first_row.get('Monto Total USD', 0)
                            try:
                                st.metric("Total Documento", f"${float(monto):,.2f} USD")
                            except Exception:
                                st.metric("Total Documento", str(monto))
                        st.markdown("**Detalle de Partidas:**")
                        cols_to_show = [c for c in ['Código Artículo', 'Descripción', 'Cantidad Solicitada', 'Cantidad Pendiente', 'Precio Unitario'] if c in df_erp.columns]
                        st.dataframe(df_erp[cols_to_show], use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No se encontraron partidas activas en el ERP para el documento #{active_docnum}.")
                except Exception as erp_ex:
                    st.warning(f"No se pudo cargar la información del ERP: {str(erp_ex)}")
            else:
                st.info("💡 No hay DocNum registrado. Puede ingresarlo en el campo de arriba.")

            st.markdown("---")

            # ── Section 2: Node Instructions ────────────────────────────────────────
            node_desc = task.node.description or ""
            if node_desc.strip():
                st.markdown(f"""
                <div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:12px 14px;
                             border-radius:0 6px 6px 0;margin-bottom:16px;">
                    <p style="margin:0 0 4px 0;font-size:12px;font-weight:bold;color:#1d4ed8;
                               text-transform:uppercase;letter-spacing:0.5px;">📋 Instrucciones de la Etapa</p>
                    <p style="margin:0;font-size:13px;color:#1e3a5f;line-height:1.6;">
                        {node_desc.replace(chr(10), '<br>')}
                    </p>
                </div>
                """, unsafe_allow_html=True)

            # ── Section 3: Confirmation Form ─────────────────────────────────────────
            st.markdown("<div class='section-header'>✅ Confirmar Acción de la Tarea</div>", unsafe_allow_html=True)

            submitted_key = f"email_landing_submitted_{task.id}"

            if not st.session_state.get(submitted_key, False):
                with st.form(key="email_landing_confirmation_form"):
                    comment_input = st.text_area(
                        "Justificación / Comentario (Requerido):",
                        value=comment_param,
                        height=100,
                        placeholder="Escriba un comentario o justificación obligatorio para avanzar..."
                    )
                    uploaded_file = st.file_uploader("Adjuntar archivo / documento (Opcional):", key="email_approval_uploader")
                    submit_btn = st.form_submit_button(
                        f"✅ Confirmar: {transition.action_name}",
                        type="primary",
                        use_container_width=True
                    )

                if submit_btn:
                    if not comment_input.strip():
                        st.error("❌ El comentario o justificación es obligatorio para avanzar la tarea.")
                    else:
                        comment_text = comment_input.strip() + " (Resolución vía email)"
                        if uploaded_file is not None:
                            UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
                            timestamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S")
                            safe_filename = f"{timestamp_prefix}_{uploaded_file.name.replace(' ', '_')}"
                            dest_path = os.path.join(UPLOAD_DIR, safe_filename)
                            with open(dest_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            db.add(WorkflowAttachment(
                                instance_id=task.instance_id,
                                task_id=task.id,
                                user_id=user.id,
                                file_name=uploaded_file.name,
                                file_path=dest_path,
                                file_size=uploaded_file.size,
                                created_at=datetime.utcnow()
                            ))
                            db.add(WorkflowHistory(
                                instance_id=task.instance_id,
                                task_id=task.id,
                                source_node_id=None,
                                target_node_id=None,
                                user_id=user.id,
                                action='ATTACHMENT',
                                comment=f"Archivo cargado vía email-landing: '{uploaded_file.name}'",
                                timestamp=datetime.utcnow()
                            ))
                        WorkflowEngine.execute_transition(
                            db=db,
                            instance_id=task.instance_id,
                            transition_id=transition.id,
                            user_id=user.id,
                            comment_text=comment_text
                        )
                        st.session_state[submitted_key] = True
                        st.session_state[f"email_landing_completed_node_{task.id}"] = task.node.name
                        st.session_state[f"email_landing_comment_{task.id}"] = comment_text
                        st.session_state[f"email_landing_instance_id_{task.id}"] = task.instance_id
                        st.balloons()
                        st.rerun()
            else:
                # ── Post-confirmation: Success card + Full History Table ──────────────
                completed_node = st.session_state.get(f"email_landing_completed_node_{task.id}", "—")
                completed_comment = st.session_state.get(f"email_landing_comment_{task.id}", "—")
                completed_instance_id = st.session_state.get(f"email_landing_instance_id_{task.id}", task.instance_id)

                st.success(f"🎉 ¡Tarea **{completed_node}** confirmada y cerrada con éxito!")

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.markdown(f"""
                    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:14px;">
                        <div style="font-size:0.78rem;color:#16a34a;text-transform:uppercase;font-weight:700;">Etapa Cerrada</div>
                        <div style="font-size:1rem;font-weight:700;color:#15803d;margin-top:2px;">{completed_node}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_s2:
                    st.markdown(f"""
                    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:14px;">
                        <div style="font-size:0.78rem;color:#16a34a;text-transform:uppercase;font-weight:700;">Ejecutado por</div>
                        <div style="font-size:1rem;font-weight:700;color:#15803d;margin-top:2px;">{user.full_name}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown(f"""
                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-top:10px;">
                    <span style="font-size:0.82rem;color:#64748b;font-weight:600;">💬 Comentario registrado:</span>
                    <p style="margin:4px 0 0 0;color:#1e293b;font-style:italic;">"{completed_comment}"</p>
                </div>
                """, unsafe_allow_html=True)

                # ── Full Process History ──────────────────────────────────────────────
                st.markdown("---")
                st.markdown("<div class='section-header'>📜 Historial Completo del Proceso</div>", unsafe_allow_html=True)

                history_records = db.query(WorkflowHistory).filter(
                    WorkflowHistory.instance_id == completed_instance_id
                ).order_by(WorkflowHistory.timestamp.asc()).all()

                if history_records:
                    fresh_inst = db.query(WorkflowInstance).filter(WorkflowInstance.id == completed_instance_id).first()
                    if fresh_inst:
                        final_status = fresh_inst.status
                        status_color = {"ACTIVE": "#3b82f6", "COMPLETED": "#10b981", "CANCELLED": "#ef4444"}.get(final_status, "#94a3b8")
                        status_label = {"ACTIVE": "ACTIVO", "COMPLETED": "COMPLETADO", "CANCELLED": "CANCELADO"}.get(final_status, final_status)
                        next_stage = f"&nbsp; → Próxima etapa: <b>{fresh_inst.current_node.name}</b>" if fresh_inst.current_node and final_status == 'ACTIVE' else ""
                        st.markdown(f"""
                        <div style="margin-bottom:14px;">
                            Estado del flujo:
                            <span style="background:{status_color};color:white;padding:3px 10px;border-radius:12px;font-size:0.82rem;font-weight:700;">{status_label}</span>
                            {next_stage}
                        </div>
                        """, unsafe_allow_html=True)

                    action_labels = {
                        'CREATE': '🚀 Creación', 'TRANSITION': '▶ Transición',
                        'COMMENT': '💬 Comentario', 'ATTACHMENT': '📎 Adjunto',
                        'REOPEN': '🔄 Reapertura', 'CANCEL': '❌ Cancelación',
                        'UPDATE_DOCNUM': '🔢 DocNum',
                    }
                    import pandas as pd
                    hist_data = []
                    for h in history_records:
                        src = h.source_node.name if h.source_node else "—"
                        tgt = h.target_node.name if h.target_node else "—"
                        tr_str = f"{src} → {tgt}" if src != "—" and tgt != "—" and src != tgt else (src if src != "—" else "—")
                        hist_data.append({
                            "Fecha/Hora": h.timestamp.strftime("%Y-%m-%d %H:%M"),
                            "Usuario": h.user.full_name,
                            "Acción": action_labels.get(h.action, h.action),
                            "Transición": tr_str,
                            "Comentario": (h.comment or "")[:120] + ("…" if h.comment and len(h.comment) > 120 else "")
                        })
                    st.dataframe(pd.DataFrame(hist_data), use_container_width=True, hide_index=True)
                else:
                    st.info("No hay registros de historial disponibles.")

                st.markdown("---")
                if st.button("🏠 Ir al Portal de Control Operacional", use_container_width=True, type="primary"):
                    st.query_params.clear()
                    for k in [submitted_key, f"email_landing_completed_node_{task.id}",
                               f"email_landing_comment_{task.id}", f"email_landing_instance_id_{task.id}"]:
                        st.session_state.pop(k, None)
                    st.rerun()

        except Exception as ex:
            st.error(f"❌ Error al procesar la transición: {str(ex)}")
            
    st.stop()

# 3. Login Interface
if not st.session_state.authenticated:
    st.markdown("<div style='text-align: center; margin-top: 50px;'><h1 class='main-header'>🔐 Portal de Cadena de Suministro & Workflow</h1><p style='color:#64748b;'>Por favor ingrese sus credenciales para acceder</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form(key="login_form"):
            username = st.text_input("Usuario", placeholder="ej. importador")
            password = st.text_input("Contraseña", type="password", placeholder="******")
            login_btn = st.form_submit_button("Iniciar Sesión")
            
            if login_btn:
                user_info = check_login(username.strip(), password)
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.user = user_info
                    st.success("¡Inicio de sesión exitoso!")
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas o usuario inactivo.")
                    
        # Help details (using demo credentials)
        st.markdown("""
        <div style="background-color: rgba(255,255,255,0.5); padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; margin-top: 15px;">
            <p style="font-weight: 600; margin-bottom: 5px; color: #334155; font-size: 0.85rem;">Usuarios demo iniciales (Contraseñas: usuario123, ej: admin123):</p>
            <ul style="color: #64748b; font-size: 0.8rem; padding-left: 20px; margin: 0;">
                <li><b>admin</b> (Rol: Administrador)</li>
                <li><b>gerente</b> (Rol: Gerencia)</li>
                <li><b>comprador</b> (Rol: Compras)</li>
                <li><b>importador</b> (Rol: Importaciones)</li>
                <li><b>logistico</b> (Rol: Logística)</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

# 4. Welcoming Logged-in Interface
else:
    # Sidebar Info
    st.sidebar.markdown(f"""
    <div style="background-color: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; color: white; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1);">
        <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.7;">Usuario Conectado</div>
        <div style="font-weight: 600; font-size: 1.1rem; margin-top: 2px;">{st.session_state.user['full_name']}</div>
        <div style="font-size: 0.85rem; margin-top: 2px; color: #a5f3fc;">Rol: {st.session_state.user['role']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()

    # Welcome landing page
    st.markdown("<h1 class='main-header'>🏢 Portal de Control Operacional</h1>", unsafe_allow_html=True)
    st.markdown("### Bienvenido al Sistema Integrado de Gestión de Workflows")
    
    st.write(
        "Utilice la barra lateral para navegar a través de los diferentes módulos del motor "
        "de workflows operacionales y paneles de control según sus permisos."
    )

    st.markdown("---")

    # Fast access cards based on roles
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="glass-card" style="min-height: 180px;">
            <h4 style="color:#0f172a; margin-top:0;">📊 Analítica de Procesos (Dashboard)</h4>
            <p style="color:#475569; font-size:0.9rem;">Consulte KPIs operativos, tiempos promedio de ciclo por etapa, cumplimiento de SLAs y balance de carga de trabajo por rol.</p>
            <p style="font-size: 0.8rem; color:#64748b;"><i>Métricas automáticas basadas en el historial del motor.</i></p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
        <div class="glass-card" style="min-height: 180px;">
            <h4 style="color:#0f172a; margin-top:0;">🚢 Gestión y Operación de Tareas (Bandeja)</h4>
            <p style="color:#475569; font-size:0.9rem;">Acceda a su bandeja personal de tareas pendientes, inicie flujos de trabajo, asigne documentos y cargue soportes o plantillas para avanzar las transiciones.</p>
            <p style="font-size: 0.8rem; color:#64748b;"><i>Orquestador de procesos autónomo en SQLite y conexión ERP.</i></p>
        </div>
        """, unsafe_allow_html=True)
