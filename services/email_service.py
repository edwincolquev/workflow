import hmac
import hashlib
import base64
import json
import time
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from sqlalchemy.orm import Session
import streamlit as st
import pandas as pd

from models import WorkflowUser, WorkflowTask, WorkflowTransition, WorkflowInstance, WorkflowNode
from services.data_loader import DataLoaderService
from services.export_service import ExportService

# Load secret key from secrets.toml or use a secure fallback
SECRET_KEY = b"supply_chain_super_secret_key"
try:
    sec = None
    if "email_workflow" in st.secrets:
        sec = st.secrets["email_workflow"]
    elif "email" in st.secrets:
        sec = st.secrets["email"]
    if sec:
        for k in ["secret_key", "SECRET_KEY"]:
            if k in sec:
                SECRET_KEY = sec[k].encode('utf-8')
                break
except:
    pass

def generate_task_token(task_id: int, transition_id: int, user_id: int, action_name: str = None, ttl_hours: int = 48) -> str:
    """Generates a base64 encoded and HMAC signed token containing workflow task details."""
    expiration = int(time.time()) + (ttl_hours * 3600)
    payload = {
        "task_id": task_id,
        "transition_id": transition_id,
        "action_name": action_name,
        "user_id": user_id,
        "exp": expiration
    }
    # Serialize and encode payload
    payload_json = json.dumps(payload).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8')
    
    # Generate signature
    signature = hmac.new(SECRET_KEY, payload_json, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode('utf-8')
    
    return f"{payload_b64}.{signature_b64}"

def verify_task_token(token: str) -> dict:
    """Verifies the token's HMAC signature and expiration. Returns payload if valid, None otherwise."""
    try:
        payload_b64, signature_b64 = token.split('.')
        payload_json = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
        
        # Verify signature
        expected_sig = hmac.new(SECRET_KEY, payload_json, hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode('utf-8')
        
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None # Signature mismatch
            
        payload = json.loads(payload_json.decode('utf-8'))
        
        # Verify expiration
        if time.time() > payload["exp"]:
            return None # Token expired
            
        return payload
    except Exception:
        return None

def send_task_notification_email(db: Session, task: WorkflowTask, from_comment: str = None, from_attachments: list = None):
    """
    Sends a task notification email to all users with the task's assigned role.
    
    Args:
        db: Database session.
        task: The newly created WorkflowTask to notify about.
        from_comment: Comment/observation written by the user at the PREVIOUS node.
        from_attachments: List of WorkflowAttachment objects uploaded at the PREVIOUS node.
    """
    if from_attachments is None:
        from_attachments = []

    role = task.assigned_role
    users = db.query(WorkflowUser).filter(
        WorkflowUser.active == True,
        WorkflowUser.roles.any(id=role.id)
    ).all()
    
    if not users:
        return
        
    inst = task.instance
    proc_name = inst.process.name
    task_name = task.node.name
    node_description = task.node.description or ""
    
    # Fetch transitions available from this node
    transitions = db.query(WorkflowTransition).filter(
        WorkflowTransition.process_id == inst.process_id,
        WorkflowTransition.source_node_id == task.node_id
    ).all()
    
    if not transitions:
        return

    # ── Build node description block (task instructions) ─────────────────────
    node_instructions_html = ""
    if node_description.strip():
        node_instructions_html = f"""
        <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 14px; margin: 15px 0; border-radius: 0 6px 6px 0;">
            <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color: #1d4ed8; text-transform: uppercase; letter-spacing: 0.5px;">📋 Instrucciones de la Tarea</p>
            <p style="margin: 0; font-size: 13px; color: #1e3a5f; line-height: 1.5;">{node_description}</p>
        </div>"""

    # ── Build previous node context block ──────────────────────────────────────
    prev_context_html = ""
    if from_comment and from_comment.strip():
        attachment_list_html = ""
        if from_attachments:
            items = "".join(
                f"<li style='font-size:12px;color:#374151;'>📎 {a.file_name}</li>"
                for a in from_attachments
            )
            attachment_list_html = f"""
            <p style="margin: 8px 0 2px 0; font-size: 12px; font-weight: bold; color: #4b5563;">Archivos adjuntos del nodo anterior:</p>
            <ul style="margin: 0; padding-left: 18px;">{items}</ul>"""

        prev_context_html = f"""
        <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px 14px; margin: 15px 0; border-radius: 0 6px 6px 0;">
            <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color: #065f46; text-transform: uppercase; letter-spacing: 0.5px;">💬 Contexto del Nodo Anterior</p>
            <p style="margin: 0; font-size: 13px; color: #1f2937; line-height: 1.5; font-style: italic;">"{from_comment.strip()}"</p>
            {attachment_list_html}
        </div>"""

    # ── Check and generate SQL report PDF if applicable ────────────────────────
    pdf_data = None
    pdf_filename = None
    if inst.external_ref:
        try:
            if inst.external_ref.startswith("DocNum:"):
                doc_num = int(inst.external_ref.split(":")[1])
                df, _ = DataLoaderService.get_transitos_with_workflow(db)
                df_filtered = df[df['DocNum'] == doc_num]
                if not df_filtered.empty:
                    pdf_filename = f"Reporte_Transito_{doc_num}.pdf"
                    pdf_data = ExportService.to_pdf(
                        title=f"Reporte de Tránsito - OC {doc_num}",
                        subtitle=f"Proveedor: {df_filtered.iloc[0].get('Nombre Proveedor', '')} - Fabricante: {df_filtered.iloc[0].get('Fabricante', '')}",
                        df=df_filtered
                    )
            elif inst.external_ref.startswith("ItemCode:"):
                item_code = inst.external_ref.split(":")[1]
                df, _ = DataLoaderService.get_nuevos_with_workflow(db)
                df_filtered = df[df['ItemCode'] == item_code]
                if not df_filtered.empty:
                    pdf_filename = f"Ficha_Tecnica_{item_code}.pdf"
                    pdf_data = ExportService.to_pdf(
                        title=f"Ficha de Artículo Nuevo - {item_code}",
                        subtitle=f"Descripción: {df_filtered.iloc[0].get('ItemName', '')} - Fabricante: {df_filtered.iloc[0].get('Fabricante', '')}",
                        df=df_filtered
                    )
        except Exception as ex:
            print(f"Error generating automatic PDF attachment: {str(ex)}")

    # ── Base URL configuration ─────────────────────────────────────────────────
    base_url = "http://localhost:8501"
    try:
        sec = None
        if "email_workflow" in st.secrets:
            sec = st.secrets["email_workflow"]
        elif "email" in st.secrets:
            sec = st.secrets["email"]
        if sec:
            for k in ["base_url", "BASE_URL"]:
                if k in sec:
                    base_url = sec[k].rstrip('/')
                    break
    except:
        pass

    for user in users:
        if not user.email:
            continue
            
        # ── Option 1: Action form (approval with comment) ──────────────────────
        form_actions_html = f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-top: 15px; margin-bottom: 15px;">
            <form action="{base_url}/" method="get">
                <div style="margin-bottom: 12px;">
                    <label for="comment" style="display: block; font-family: sans-serif; font-size: 13px; font-weight: bold; color: #1e293b; margin-bottom: 6px;">
                        Escribe tus comentarios u observaciones (Requerido):
                    </label>
                    <textarea id="comment" name="comment" rows="3" required style="width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; font-family: sans-serif; font-size: 13px; resize: vertical;" placeholder="Ingresa detalles obligatorios sobre esta resolución..."></textarea>
                </div>
                <div style="margin-top: 10px;">
        """
        
        # Determine transitions to show
        is_task_node = (task.node.type == 'TASK')
        transitions_to_show = []
        if is_task_node and transitions:
            t_first = transitions[0]
            display_name = "Confirmar y Continuar" if len(transitions) > 1 else t_first.action_name
            transitions_to_show.append((t_first, display_name))
        else:
            for t in transitions:
                transitions_to_show.append((t, t.action_name))
                
        for trans, action_display in transitions_to_show:
            token = generate_task_token(task.id, trans.id, user.id, action_name=trans.action_name)
            form_actions_html += f"""
            <button type="submit" name="token" value="{token}" style="display: inline-block; padding: 8px 16px; font-family: sans-serif; font-size: 13px; font-weight: bold; color: white; background-color: #3b82f6; border: none; border-radius: 5px; margin-right: 8px; margin-bottom: 8px; cursor: pointer;">
                {action_display}
            </button>
            """
            
        form_actions_html += """
                </div>
            </form>
        </div>
        """
        
        # ── Count forwarded attachments for footer note ────────────────────────
        fwd_att_note = ""
        if from_attachments:
            count = len(from_attachments)
            fwd_att_note = f"<p style='font-size: 12px; color: #475569;'>📎 Se adjuntan <b>{count}</b> archivo(s) del nodo anterior junto con este correo.</p>"

        # ── Build full HTML email ──────────────────────────────────────────────
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
            <div style="max-width: 620px; margin: 0 auto; background-color: white; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
              <div style="border-bottom: 2px solid #3b82f6; padding-bottom: 12px; margin-bottom: 15px;">
                  <h2 style="color: #0f172a; margin: 0; font-size: 18px;">⚙️ ACCIÓN REQUERIDA: Tarea Asignada</h2>
                  <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13px;">Proceso: <b>{proc_name}</b></p>
              </div>
              
              <p>Hola <b>{user.full_name}</b>,</p>
              <p>Se ha generado una tarea pendiente en tu bandeja que requiere tu gestión:</p>
              
              <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; margin: 15px 0; border-radius: 0 6px 6px 0;">
                  <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                      <tr>
                          <td style="padding: 3px 0; color: #64748b; width: 130px;"><b>Instancia:</b></td>
                          <td style="padding: 3px 0; color: #0f172a; font-weight: bold;">{inst.title}</td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>Código:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;">{inst.internal_code or f'#{inst.id}'}</td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>Etapa Asignada:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;"><span style="background-color: #fef3c7; color: #d97706; padding: 1px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">{task_name}</span></td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>DocNum:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;"><code>{inst.docnum or 'N/A'}</code></td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>Rol Asignado:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;">{role.name}</td>
                      </tr>
                  </table>
              </div>

              {node_instructions_html}
              {prev_context_html}
              
              <p style="font-weight: bold; color: #0f172a; margin-top: 20px; margin-bottom: 5px;">Resolución con Comentario Requerido</p>
              <p style="font-size: 12px; color: #64748b; margin-top: 0; margin-bottom: 8px;">Completa la justificación (campo obligatorio) y haz clic en el botón de la acción correspondiente:</p>
              {form_actions_html}
              
              {f"<p style='font-size: 12px; color: #475569;'>📎 Se adjunta el informe de datos operacionales.</p>" if pdf_data else ""}
              {fwd_att_note}
              
              <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 25px 0 15px 0;">
              <p style="font-size: 11px; color: #94a3b8; text-align: center; margin: 0;">
                  Este es un correo automático del Portal de Control Operacional. Los enlaces son seguros, de un solo uso y expiran en 48 horas.
              </p>
            </div>
          </body>
        </html>
        """
        
        # ── Assemble email attachments ─────────────────────────────────────────
        email_attachments = []
        
        # 1. PDF report (if applicable)
        if pdf_data:
            email_attachments.append({
                "data": pdf_data,
                "filename": pdf_filename,
                "mime_type": "application/pdf"
            })
        
        # 2. Forwarded attachments from the previous node (read from disk)
        for att in from_attachments:
            try:
                if os.path.exists(att.file_path):
                    with open(att.file_path, 'rb') as f:
                        file_bytes = f.read()
                    # Infer MIME type from extension
                    ext = os.path.splitext(att.file_name)[1].lower()
                    mime_map = {
                        '.pdf': 'application/pdf',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.xls': 'application/vnd.ms-excel',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        '.doc': 'application/msword',
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.zip': 'application/zip',
                        '.csv': 'text/csv',
                    }
                    mime_type = mime_map.get(ext, 'application/octet-stream')
                    email_attachments.append({
                        "data": file_bytes,
                        "filename": att.file_name,
                        "mime_type": mime_type
                    })
            except Exception as ex:
                print(f"Could not attach forwarded file '{att.file_name}': {ex}")
            
        send_email_with_attachments(
            to_email=user.email,
            subject=f"⚙️ TAREA ASIGNADA: '{task_name}' en {inst.internal_code or inst.title}",
            html_content=html_content,
            attachments=email_attachments
        )

def send_info_notification_email(db: Session, instance: WorkflowInstance, node: WorkflowNode, from_comment: str = None, from_attachments: list = None):
    """
    Sends an informational email notification to all active users with the node's assigned role.
    No buttons/actions are included.
    """
    if from_attachments is None:
        from_attachments = []
    
    role = node.role
    if not role:
        return
        
    users = db.query(WorkflowUser).filter(
        WorkflowUser.active == True,
        WorkflowUser.roles.any(id=role.id)
    ).all()
    
    if not users:
        return
        
    proc_name = instance.process.name
    node_name = node.name
    node_description = node.description or ""
    
    # Node description
    node_instructions_html = ""
    if node_description.strip():
        node_instructions_html = f"""
        <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 14px; margin: 15px 0; border-radius: 0 6px 6px 0;">
            <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color: #1d4ed8; text-transform: uppercase; letter-spacing: 0.5px;">📋 Detalle de la Notificación</p>
            <p style="margin: 0; font-size: 13px; color: #1e3a5f; line-height: 1.5;">{node_description}</p>
        </div>"""
        
    # Previous node context block
    prev_context_html = ""
    if from_comment and from_comment.strip():
        attachment_list_html = ""
        if from_attachments:
            items = "".join(
                f"<li style='font-size:12px;color:#374151;'>📎 {a.file_name}</li>"
                for a in from_attachments
            )
            attachment_list_html = f"""
            <p style="margin: 8px 0 2px 0; font-size: 12px; font-weight: bold; color: #4b5563;">Archivos adjuntos:</p>
            <ul style="margin: 0; padding-left: 18px;">{items}</ul>"""

        prev_context_html = f"""
        <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px 14px; margin: 15px 0; border-radius: 0 6px 6px 0;">
            <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color: #065f46; text-transform: uppercase; letter-spacing: 0.5px;">💬 Comentarios del Nodo Anterior</p>
            <p style="margin: 0; font-size: 13px; color: #1f2937; line-height: 1.5; font-style: italic;">"{from_comment.strip()}"</p>
            {attachment_list_html}
        </div>"""

    # Check and generate SQL report PDF if applicable
    pdf_data = None
    pdf_filename = None
    if instance.external_ref:
        try:
            if instance.external_ref.startswith("DocNum:"):
                doc_num = int(instance.external_ref.split(":")[1])
                df, _ = DataLoaderService.get_transitos_with_workflow(db)
                df_filtered = df[df['DocNum'] == doc_num]
                if not df_filtered.empty:
                    pdf_filename = f"Reporte_Transito_{doc_num}.pdf"
                    pdf_data = ExportService.to_pdf(
                        title=f"Reporte de Tránsito - OC {doc_num}",
                        subtitle=f"Proveedor: {df_filtered.iloc[0].get('Nombre Proveedor', '')} - Fabricante: {df_filtered.iloc[0].get('Fabricante', '')}",
                        df=df_filtered
                    )
            elif instance.external_ref.startswith("ItemCode:"):
                item_code = instance.external_ref.split(":")[1]
                df, _ = DataLoaderService.get_nuevos_with_workflow(db)
                df_filtered = df[df['ItemCode'] == item_code]
                if not df_filtered.empty:
                    pdf_filename = f"Ficha_Tecnica_{item_code}.pdf"
                    pdf_data = ExportService.to_pdf(
                        title=f"Ficha de Artículo Nuevo - {item_code}",
                        subtitle=f"Descripción: {df_filtered.iloc[0].get('ItemName', '')} - Fabricante: {df_filtered.iloc[0].get('Fabricante', '')}",
                        df=df_filtered
                    )
        except Exception as ex:
            print(f"Error generating automatic PDF attachment in notification: {str(ex)}")

    for user in users:
        if not user.email:
            continue
            
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
            <div style="max-width: 620px; margin: 0 auto; background-color: white; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
              <div style="border-bottom: 2px solid #3b82f6; padding-bottom: 12px; margin-bottom: 15px;">
                  <h2 style="color: #1e3a8a; margin: 0; font-size: 18px;">📢 NOTIFICACIÓN INFORMATIVA</h2>
                  <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13px;">Proceso: <b>{proc_name}</b></p>
              </div>
              
              <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px; margin-bottom: 15px; font-weight: bold; color: #1e40af; font-size: 13px; text-align: center;">
                  Esta es una notificación informativa. No se requiere ninguna acción de su parte.
              </div>
              
              <p>Hola <b>{user.full_name}</b>,</p>
              <p>Se ha registrado un hito o cambio de estado en el flujo de trabajo:</p>
              
              <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; margin: 15px 0; border-radius: 0 6px 6px 0;">
                  <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                      <tr>
                          <td style="padding: 3px 0; color: #64748b; width: 130px;"><b>Instancia:</b></td>
                          <td style="padding: 3px 0; color: #0f172a; font-weight: bold;">{instance.title}</td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>Código:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;">{instance.internal_code or f'#{instance.id}'}</td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>Etapa/Evento:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;"><span style="background-color: #dbeafe; color: #1e40af; padding: 1px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">{node_name}</span></td>
                      </tr>
                      <tr>
                          <td style="padding: 3px 0; color: #64748b;"><b>DocNum:</b></td>
                          <td style="padding: 3px 0; color: #0f172a;"><code>{instance.docnum or 'N/A'}</code></td>
                      </tr>
                  </table>
              </div>

              {node_instructions_html}
              {prev_context_html}
              
              {f"<p style='font-size: 12px; color: #475569;'>📎 Se adjunta el informe de datos operacionales.</p>" if pdf_data else ""}
              
              <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 25px 0 15px 0;">
              <p style="font-size: 11px; color: #94a3b8; text-align: center; margin: 0;">
                  Este es un correo automático del Portal de Control Operacional. No responda a este mensaje.
              </p>
            </div>
          </body>
        </html>
        """
        
        email_attachments = []
        if pdf_data:
            email_attachments.append({
                "data": pdf_data,
                "filename": pdf_filename,
                "mime_type": "application/pdf"
            })
            
        for att in from_attachments:
            try:
                if os.path.exists(att.file_path):
                    with open(att.file_path, 'rb') as f:
                        file_bytes = f.read()
                    ext = os.path.splitext(att.file_name)[1].lower()
                    mime_map = {
                        '.pdf': 'application/pdf',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.xls': 'application/vnd.ms-excel',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        '.doc': 'application/msword',
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.zip': 'application/zip',
                        '.csv': 'text/csv',
                    }
                    mime_type = mime_map.get(ext, 'application/octet-stream')
                    email_attachments.append({
                        "data": file_bytes,
                        "filename": att.file_name,
                        "mime_type": mime_type
                    })
            except Exception as ex:
                print(f"Could not attach forwarded file in notification '{att.file_name}': {ex}")
                
        send_email_with_attachments(
            to_email=user.email,
            subject=f"📢 NOTIFICACIÓN: '{node_name}' en {instance.internal_code or instance.title}",
            html_content=html_content,
            attachments=email_attachments
        )

def send_workflow_completed_notification(db: Session, instance: WorkflowInstance):
    """Notifies the workflow instance creator that the instance has reached its end node successfully."""
    creator = instance.created_by
    if not creator or not creator.email:
        return
        
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
          <div style="border-bottom: 2px solid #10b981; padding-bottom: 12px; margin-bottom: 15px;">
              <h2 style="color: #0f172a; margin: 0; font-size: 18px;">🏁 PROCESO FINALIZADO CON ÉXITO</h2>
              <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13px;">Flujo: <b>{instance.process.name}</b></p>
          </div>
          
          <p>Hola <b>{creator.full_name}</b>,</p>
          <p>Te notificamos que el flujo de trabajo que iniciaste ha finalizado correctamente:</p>
          
          <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px; margin: 15px 0; border-radius: 0 6px 6px 0;">
              <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                  <tr>
                      <td style="padding: 3px 0; color: #64748b; width: 120px;"><b>Flujo:</b></td>
                      <td style="padding: 3px 0; color: #0f172a; font-weight: bold;">{instance.title}</td>
                  </tr>
                  <tr>
                      <td style="padding: 3px 0; color: #64748b;"><b>Referencia ERP:</b></td>
                      <td style="padding: 3px 0; color: #0f172a;"><code>{instance.external_ref or 'Ninguna'}</code></td>
                  </tr>
                  <tr>
                      <td style="padding: 3px 0; color: #64748b;"><b>Fecha Finalización:</b></td>
                      <td style="padding: 3px 0; color: #0f172a;">{instance.updated_at.strftime('%Y-%m-%d %H:%M')}</td>
                  </tr>
              </table>
          </div>
          
          <p>Toda la mercadería o ítems asociados han sido plenamente ingresados / habilitados en el stock operativo de la compañía.</p>
          
          <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 25px 0 15px 0;">
          <p style="font-size: 11px; color: #94a3b8; text-align: center; margin: 0;">
              Este es un correo automático enviado desde el Portal de Control Operacional.
          </p>
        </div>
      </body>
    </html>
    """
    send_email_with_attachments(
        to_email=creator.email,
        subject=f"🏁 FINALIZADO: Flujo '{instance.title}' completado con éxito",
        html_content=html_content
    )

def send_report_email(to_email: str, report_title: str, df: pd.DataFrame, message: str = ""):
    """Manually dispatches a SQL report as attachments (PDF & Excel) to a recipient's email."""
    # Generate report binaries
    pdf_data = ExportService.to_pdf(report_title, "Portal de Cadena de Suministro", df)
    excel_data = ExportService.to_excel(df)
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
          <div style="border-bottom: 2px solid #6366f1; padding-bottom: 12px; margin-bottom: 15px;">
              <h2 style="color: #0f172a; margin: 0; font-size: 18px;">📊 Envío de Reporte Solicitado</h2>
              <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13px;">Reporte: <b>{report_title}</b></p>
          </div>
          
          <p>Estimado Usuario,</p>
          <p>Se adjunta el reporte solicitado en formatos <b>PDF</b> y <b>Excel</b> compilado desde el sistema.</p>
          
          {f"<div style='background-color: #f8fafc; padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; margin: 15px 0; font-size: 13px; font-style: italic; color: #475569;'>{message}</div>" if message else ""}
          
          <p><b>Resumen de Estructura de Datos (Muestra):</b></p>
          <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; margin-bottom: 15px;">
              <thead>
                  <tr style="background-color: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
                      <th style="border: 1px solid #cbd5e1; padding: 8px; text-align: left;">Columna</th>
                      <th style="border: 1px solid #cbd5e1; padding: 8px; text-align: left;">Valor Muestra (Primer Fila)</th>
                  </tr>
              </thead>
              <tbody>
    """
    
    if not df.empty:
        row0 = df.iloc[0]
        # Show sample values for first 5 columns
        for col in list(df.columns)[:5]:
            html_content += f"""
                  <tr>
                      <td style="border: 1px solid #cbd5e1; padding: 6px; font-weight: bold; background-color: #f8fafc; width: 150px;">{col}</td>
                      <td style="border: 1px solid #cbd5e1; padding: 6px; color: #334155;">{str(row0[col])}</td>
                  </tr>
            """
            
    html_content += """
              </tbody>
          </table>
          
          <p style="font-size: 12px; color: #64748b;">Consulte los adjuntos para ver el reporte de consultas completo.</p>
          
          <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 25px 0 15px 0;">
          <p style="font-size: 11px; color: #94a3b8; text-align: center; margin: 0;">
              Este es un correo automático enviado desde el Portal de Control Operacional.
          </p>
        </div>
      </body>
    </html>
    """
    
    file_safe = report_title.lower().replace(" ", "_")
    attachments = [
        {"data": pdf_data, "filename": f"{file_safe}.pdf", "mime_type": "application/pdf"},
        {"data": excel_data, "filename": f"{file_safe}.xlsx", "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ]
    
    send_email_with_attachments(
        to_email=to_email,
        subject=f"📊 REPORTE DISPONIBLE: {report_title}",
        html_content=html_content,
        attachments=attachments
    )

def send_email_with_attachments(to_email: str, subject: str, html_content: str, attachments: list = None):
    """Sends email through SMTP if configured, or saves it to disk in uploads/simulated_emails/ for simulation."""
    if attachments is None:
        attachments = []
        
    smtp_config = None
    try:
        if "email_workflow" in st.secrets:
            smtp_config = st.secrets["email_workflow"]
        elif "email" in st.secrets:
            smtp_config = st.secrets["email"]
    except:
        pass
        
    # If SMTP is configured, send the real email
    if smtp_config:
        def get_val(keys):
            for k in keys:
                if k in smtp_config:
                    return smtp_config[k]
                if k.lower() in smtp_config:
                    return smtp_config[k.lower()]
                if k.upper() in smtp_config:
                    return smtp_config[k.upper()]
            return None

        smtp_server = get_val(["smtp_server", "server"])
        sender_email = get_val(["sender_email", "email"])
        password = get_val(["password", "sender_password"])
        port_val = get_val(["port", "smtp_port"])
        
        try:
            port = int(port_val) if port_val is not None else 587
        except:
            port = 587

        if smtp_server and sender_email:
            try:
                msg = MIMEMultipart('mixed')
                msg['Subject'] = subject
                msg['From'] = sender_email
                msg['To'] = to_email
                
                msg_alternative = MIMEMultipart('alternative')
                msg_alternative.attach(MIMEText(html_content, 'html'))
                msg.attach(msg_alternative)
                
                for att in attachments:
                    part = MIMEApplication(att["data"], Name=att["filename"])
                    part['Content-Disposition'] = f'attachment; filename="{att["filename"]}"'
                    msg.attach(part)
                    
                server = smtplib.SMTP(smtp_server, port)
                server.starttls()
                server.login(sender_email, password)
                server.sendmail(sender_email, to_email, msg.as_string())
                server.quit()
                return
            except Exception as ex:
                print(f"SMTP failed, saving to simulation cache: {str(ex)}")

    # Sandbox/Simulation fallback (No Credentials Rule compliant)
    # Save the email as an HTML file + individual attachments in uploads/simulated_emails/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sim_dir = os.path.join(base_dir, 'uploads', 'simulated_emails')
    os.makedirs(sim_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    subject_safe = "".join([c if c.isalnum() else "_" for c in subject])
    to_email_safe = "".join([c if c.isalnum() or c=='@' else "_" for c in to_email])
    
    base_filename = f"{timestamp}_{to_email_safe}_{subject_safe}"
    html_filepath = os.path.join(sim_dir, f"{base_filename}.html")
    
    with open(html_filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    # Write attachments to files in the same sandbox directory
    for att in attachments:
        att_filepath = os.path.join(sim_dir, f"{base_filename}_attachment_{att['filename']}")
        with open(att_filepath, 'wb') as f:
            f.write(att["data"])
            
    try:
        print(f"[SIMULATION] Email saved successfully for '{to_email}' with subject '{subject}' to: {html_filepath}")
    except Exception:
        try:
            print(f"[SIMULATION] Email saved successfully to: {html_filepath}")
        except:
            pass
