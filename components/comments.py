import streamlit as st
from datetime import datetime
from sqlalchemy.orm import Session
from models import WorkflowComment, WorkflowHistory, WorkflowUser

class CommentsComponent:
    @staticmethod
    def render_comments_section(db: Session, instance_id: int, user_id: int):
        """
        Renders the comment log for a workflow instance and handles adding new comments.
        """
        st.markdown("<div class='section-header'>💬 Comentarios y Observaciones</div>", unsafe_allow_html=True)
        
        # 1. Fetch existing comments for this instance
        comments = db.query(WorkflowComment).filter(
            WorkflowComment.instance_id == instance_id
        ).order_by(WorkflowComment.created_at.desc()).all()

        # 2. Form to add a new comment
        with st.form(key=f"comment_form_{instance_id}", clear_on_submit=True):
            comment_text = st.text_area(
                "Escribe un nuevo comentario...", 
                height=80, 
                placeholder="Ej. Proveedor confirmó embarque para el 15 de julio."
            )
            submit_btn = st.form_submit_button("Registrar Comentario")
            
            if submit_btn and comment_text.strip():
                # Add to DB
                new_comment = WorkflowComment(
                    instance_id=instance_id,
                    user_id=user_id,
                    comment_text=comment_text.strip(),
                    created_at=datetime.utcnow()
                )
                db.add(new_comment)
                db.flush()
                
                # Log in history
                history = WorkflowHistory(
                    instance_id=instance_id,
                    task_id=None,
                    source_node_id=None,
                    target_node_id=None,
                    user_id=user_id,
                    action='COMMENT',
                    comment=f"Comentario registrado: '{comment_text.strip()[:60]}...'",
                    timestamp=datetime.utcnow()
                )
                db.add(history)
                db.commit()
                
                st.success("Comentario registrado con éxito.")
                st.rerun()

        # 3. Display existing comments list
        if not comments:
            st.info("No hay comentarios registrados para este flujo.")
        else:
            for comment in comments:
                user_roles = ", ".join([role.name for role in comment.user.roles])
                formatted_time = comment.created_at.strftime("%Y-%m-%d %H:%M")
                
                comment_html = f"""
                <div style="background-color: white; border-radius: 8px; padding: 12px 15px; margin-bottom: 10px; border: 1px solid #e2e8f0;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-weight: 600; color: #1e293b; font-size: 0.9rem;">
                            {comment.user.full_name} <span style="font-weight: 400; color: #64748b; font-size: 0.8rem;">({user_roles})</span>
                        </span>
                        <span style="color: #64748b; font-size: 0.8rem;">{formatted_time}</span>
                    </div>
                    <div style="color: #334155; font-size: 0.9rem; white-space: pre-wrap;">{comment.comment_text}</div>
                </div>
                """
                st.markdown(comment_html, unsafe_allow_html=True)
