import os
import streamlit as st
from datetime import datetime
from sqlalchemy.orm import Session
from models import WorkflowAttachment, WorkflowHistory

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

class AttachmentsComponent:
    @staticmethod
    def render_attachments_section(db: Session, instance_id: int, user_id: int, task_id: int = None):
        """
        Renders the attachment section, handles file uploads, and provides download options.
        
        Args:
            task_id: If provided, newly uploaded attachments will be linked to this task (for forwarding).
        """
        st.markdown("<div class='section-header'>📎 Documentos Adjuntos</div>", unsafe_allow_html=True)
        
        # 1. Fetch existing attachments
        attachments = db.query(WorkflowAttachment).filter(
            WorkflowAttachment.instance_id == instance_id
        ).order_by(WorkflowAttachment.created_at.desc()).all()

        # 2. Form to upload new attachment
        uploaded_file = st.file_uploader(
            "Cargar documento (PDF, Excel, Imagen, etc.)", 
            key=f"uploader_{instance_id}"
        )
        
        if uploaded_file is not None:
            # Add upload button
            if st.button("Guardar Archivo Adjunto", key=f"save_file_btn_{instance_id}"):
                # Create a unique filename
                timestamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S")
                safe_filename = f"{timestamp_prefix}_{uploaded_file.name.replace(' ', '_')}"
                dest_path = os.path.join(UPLOAD_DIR, safe_filename)
                
                # Save file locally
                with open(dest_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Add record to DB (store absolute path for reliable retrieval)
                new_attach = WorkflowAttachment(
                    instance_id=instance_id,
                    task_id=task_id,  # Links to the active task node if provided
                    user_id=user_id,
                    file_name=uploaded_file.name,
                    file_path=dest_path,  # Full absolute path
                    file_size=uploaded_file.size,
                    created_at=datetime.utcnow()
                )
                db.add(new_attach)
                db.flush()
                
                # Log history
                history = WorkflowHistory(
                    instance_id=instance_id,
                    task_id=None,
                    source_node_id=None,
                    target_node_id=None,
                    user_id=user_id,
                    action='ATTACHMENT',
                    comment=f"Archivo cargado: '{uploaded_file.name}'",
                    timestamp=datetime.utcnow()
                )
                db.add(history)
                db.commit()
                
                st.success(f"Archivo '{uploaded_file.name}' cargado con éxito.")
                st.rerun()

        # 3. Display list of attachments
        if not attachments:
            st.info("No hay archivos adjuntos en este flujo.")
        else:
            for attach in attachments:
                # Support both absolute paths (new) and relative filenames (legacy)
                if os.path.isabs(attach.file_path):
                    file_full_path = attach.file_path
                else:
                    file_full_path = os.path.join(UPLOAD_DIR, attach.file_path)
                
                # Verify file exists on disk
                if not os.path.exists(file_full_path):
                    st.warning(f"El archivo '{attach.file_name}' no se encuentra físicamente.")
                    continue
                    
                # Read file for download button
                with open(file_full_path, "rb") as file_bytes:
                    btn = st.download_button(
                        label=f"⬇️ Descargar: {attach.file_name} ({attach.file_size / 1024:.1f} KB)",
                        data=file_bytes,
                        file_name=attach.file_name,
                        key=f"download_{attach.id}"
                    )
                
                user_roles = ", ".join([role.name for role in attach.user.roles])
                st.caption(f"Cargado por: {attach.user.full_name} ({user_roles}) el {attach.created_at.strftime('%Y-%m-%d %H:%M')}")
                st.markdown("<hr style='margin: 8px 0; border: 0; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)
        
        # Clean spacing
        st.write("")
