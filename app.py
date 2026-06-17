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
    from models import WorkflowTask, WorkflowInstance, WorkflowHistory
    from engine import WorkflowEngine
    
    payload = verify_task_token(token)
    
    if not payload:
        st.error("❌ Enlace no válido, expirado o firma corrupta. Por favor, ingresa al portal de forma manual para resolver la tarea.")
        st.stop()
        
    task_id = payload["task_id"]
    transition_id = payload["transition_id"]
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
                
            # 2. If task is pending, execute the transition
            from models import WorkflowUser
            user = db.query(WorkflowUser).filter(WorkflowUser.id == user_id).first()
            if not user:
                st.error("❌ El usuario firmante del token no existe.")
                st.stop()
                
            user_role_ids = [r.id for r in user.roles]
            if task.assigned_role_id not in user_role_ids:
                st.error("❌ No tienes el rol requerido para procesar esta transición.")
                st.stop()
                
            # Process transition
            comment_text = comment_param.strip()
            if not comment_text:
                comment_text = "Completado directamente vía correo electrónico (Outlook)."
            else:
                comment_text = f"{comment_text} (Enviado vía correo electrónico)."
                
            WorkflowEngine.execute_transition(
                db=db,
                instance_id=task.instance_id,
                transition_id=transition_id,
                user_id=user.id,
                comment_text=comment_text
            )
            
            st.balloons()
            st.success(f"🎉 ¡Tarea procesada con éxito! La importación/ítem ha avanzado en el flujo operacional.")
            st.info(f"""
            **Resumen de la Transición:**
            * **Flujo:** {task.instance.title}
            * **Etapa Completada:** {task.node.name}
            * **Comentario registrado:** "{comment_text}"
            * **Ejecutado por:** {user.full_name}
            """)
            
            if st.button("Ir al Portal"):
                st.query_params.clear()
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
    st.markdown("### Bienvenido al Sistema Integrado de Análisis y Workflow")
    
    st.write(
        "Utilice la barra lateral para navegar a través de los diferentes módulos analíticos "
        "y bandejas de workflow operacional según sus permisos."
    )

    st.markdown("---")

    # Fast access cards based on roles
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="glass-card" style="min-height: 180px;">
            <h4 style="color:#0f172a; margin-top:0;">📊 Sección de Análisis (Dashboards)</h4>
            <p style="color:#475569; font-size:0.9rem;">Consulte KPIs ejecutivos, estados de tránsito SAP B1, cobertura de stock, excesos, discontinuados y quiebres de artículos.</p>
            <p style="font-size: 0.8rem; color:#64748b;"><i>Mapeado directamente con SQL Server / SAP B1.</i></p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
        <div class="glass-card" style="min-height: 180px;">
            <h4 style="color:#0f172a; margin-top:0;">🚢 Sección de Operación (Workflow Engine)</h4>
            <p style="color:#475569; font-size:0.9rem;">Acceda a su bandeja personal de tareas pendientes, verifique comentarios, suba documentos y avance los tránsitos o items nuevos por la matriz de transición.</p>
            <p style="font-size: 0.8rem; color:#64748b;"><i>Orquestador de procesos autónomo en SQLite.</i></p>
        </div>
        """, unsafe_allow_html=True)
