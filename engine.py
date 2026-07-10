from datetime import datetime
from sqlalchemy.orm import Session
from models import (
    WorkflowProcess, WorkflowNode, WorkflowTransition, WorkflowInstance, 
    WorkflowTask, WorkflowHistory, WorkflowComment, WorkflowAttachment, 
    WorkflowRole, WorkflowUser
)

class WorkflowEngine:
    @staticmethod
    def create_instance(db: Session, process_id: int, title: str, creator_id: int, external_ref: str = None) -> WorkflowInstance:
        """
        Creates a new workflow instance for a process, sets it at the START node,
        and automatically advances it to the first task if a transition exists.
        """
        # 1. Verify process and START node
        process = db.query(WorkflowProcess).filter(WorkflowProcess.id == process_id, WorkflowProcess.active == True).first()
        if not process:
            raise ValueError("El proceso no existe o está inactivo.")
            
        start_node = db.query(WorkflowNode).filter(
            WorkflowNode.process_id == process_id, 
            WorkflowNode.type == 'START'
        ).first()
        if not start_node:
            raise ValueError("El proceso no tiene un nodo inicial (START).")

        # 2. Create instance
        docnum_val = None
        if external_ref and external_ref.startswith("DocNum:"):
            docnum_val = external_ref.split(":")[1]

        instance = WorkflowInstance(
            process_id=process_id,
            title=title,
            status='ACTIVE',
            current_node_id=start_node.id,
            external_ref=external_ref,
            docnum=docnum_val,
            created_by_id=creator_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(instance)
        db.flush()  # Generate instance ID
        
        # Auto-generate internal code (WF-XXXX)
        instance.internal_code = f"WF-{instance.id:04d}"

        # 3. Log creation in history
        history = WorkflowHistory(
            instance_id=instance.id,
            source_node_id=None,
            target_node_id=start_node.id,
            user_id=creator_id,
            action='CREATE',
            comment="Instancia de flujo creada.",
            timestamp=datetime.utcnow()
        )
        db.add(history)

        # 4. Auto-advance from START node using a queue (BFS) to resolve any GATEWAY or NOTIFICATION nodes
        start_transition = db.query(WorkflowTransition).filter(
            WorkflowTransition.process_id == process_id,
            WorkflowTransition.source_node_id == start_node.id
        ).first()

        new_tasks = []
        if start_transition:
            # Queue elements: (curr_target, action_name, source_node_id)
            queue = [(start_transition.target_node, start_transition.action_name, start_node.id)]
            last_target_node_id = None

            while queue:
                curr_target, action, src_id = queue.pop(0)
                last_target_node_id = curr_target.id

                # Log transition in history
                history_comment = f"Transición automática inicial: '{action}'."
                if curr_target.type == 'GATEWAY':
                    history_comment = f"Avance automático a compuerta: '{curr_target.name}'."
                elif curr_target.type == 'NOTIFICATION':
                    history_comment = f"Avance automático a etapa de notificación: '{curr_target.name}'."

                history_trans = WorkflowHistory(
                    instance_id=instance.id,
                    source_node_id=src_id,
                    target_node_id=curr_target.id,
                    user_id=creator_id,
                    action='TRANSITION',
                    comment=history_comment,
                    timestamp=datetime.utcnow()
                )
                db.add(history_trans)

                # Check target node type
                if curr_target.type in ['TASK', 'DECISION']:
                    task = WorkflowTask(
                        instance_id=instance.id,
                        node_id=curr_target.id,
                        assigned_role_id=curr_target.role_id,
                        status='PENDING',
                        sla_hours=curr_target.sla_hours, # Inherited from node config
                        docnum=docnum_val,
                        created_at=datetime.utcnow()
                    )
                    db.add(task)
                    new_tasks.append(task)
                elif curr_target.type == 'GATEWAY':
                    # Automatically execute all transitions originating from this GATEWAY
                    gateway_transitions = db.query(WorkflowTransition).filter(
                        WorkflowTransition.process_id == process_id,
                        WorkflowTransition.source_node_id == curr_target.id
                    ).all()
                    for gt in gateway_transitions:
                        queue.append((gt.target_node, gt.action_name, curr_target.id))
                elif curr_target.type == 'NOTIFICATION':
                    # Trigger info email notification for the role assigned to this notification node
                    try:
                        from services.email_service import send_info_notification_email
                        send_info_notification_email(db, instance, curr_target)
                    except Exception as e:
                        print(f"Error sending info notification: {str(e)}")
                    # Automatically execute all transitions originating from this NOTIFICATION node
                    notif_transitions = db.query(WorkflowTransition).filter(
                        WorkflowTransition.process_id == process_id,
                        WorkflowTransition.source_node_id == curr_target.id
                    ).all()
                    for nt in notif_transitions:
                        queue.append((nt.target_node, nt.action_name, curr_target.id))

            if last_target_node_id:
                instance.current_node_id = last_target_node_id

        db.commit()

        # Trigger email notification for any newly created tasks
        if new_tasks:
            try:
                from services.email_service import send_task_notification_email
                for task in new_tasks:
                    db.refresh(task)
                    send_task_notification_email(db, task)
            except Exception as e:
                print(f"Error sending task notification: {str(e)}")
                
        return instance

    @staticmethod
    def get_available_transitions(db: Session, instance_id: int, user: WorkflowUser) -> list[WorkflowTransition]:
        """
        Retrieves transitions that the current user can execute based on the active tasks of the instance and user roles.
        """
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance or instance.status != 'ACTIVE':
            return []

        # Find all active tasks for this instance
        active_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.instance_id == instance_id,
            WorkflowTask.status == 'PENDING'
        ).all()

        if not active_tasks:
            return []

        # Collect node IDs from active tasks
        active_node_ids = [task.node_id for task in active_tasks]

        # Find transitions originating from any of the active task nodes
        transitions = db.query(WorkflowTransition).filter(
            WorkflowTransition.process_id == instance.process_id,
            WorkflowTransition.source_node_id.in_(active_node_ids)
        ).all()

        # Filter transitions by user's roles matching the source node's role
        user_role_ids = [role.id for role in user.roles]
        available = []
        for t in transitions:
            if not t.source_node.role_id or t.source_node.role_id in user_role_ids:
                available.append(t)
                
        return available

    @staticmethod
    def execute_transition(db: Session, instance_id: int, transition_id: int, user_id: int, comment_text: str = None, docnum_value: str = None) -> WorkflowInstance:
        """
        Advances the workflow along a transition, completing the current task
        and creating the next task(s) or finalizing the workflow.
        For TASK nodes, it completes the task and automatically executes ALL outgoing transitions.
        For DECISION nodes, it executes only the selected transition.
        """
        # Enforce comment requirement
        if not comment_text or not comment_text.strip():
            raise ValueError("El comentario u observación es obligatorio para realizar esta acción.")

        # 1. Load objects
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance:
            raise ValueError("La instancia no existe.")
        if instance.status != 'ACTIVE':
            raise ValueError("La instancia no está activa.")

        # 1.5 Load transition and current task
        transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).first()
        if not transition or transition.process_id != instance.process_id:
            raise ValueError("Transición no válida para el estado actual de la instancia.")

        user = db.query(WorkflowUser).filter(WorkflowUser.id == user_id).first()
        if not user:
            raise ValueError("Usuario no existe.")
            
        source_node = transition.source_node
        if source_node.role_id:
            user_role_ids = [role.id for role in user.roles]
            if source_node.role_id not in user_role_ids:
                raise ValueError("El usuario no tiene el rol requerido para esta acción.")

        current_task = db.query(WorkflowTask).filter(
            WorkflowTask.instance_id == instance_id,
            WorkflowTask.node_id == source_node.id,
            WorkflowTask.status == 'PENDING'
        ).first()

        # Update docnum on current task and instance if provided
        active_docnum = None
        if current_task:
            active_docnum = current_task.docnum

        if docnum_value:
            docnum_clean = docnum_value.strip()
            if docnum_clean:
                active_docnum = docnum_clean
                if current_task:
                    current_task.docnum = docnum_clean
                    if current_task.node.erp_query_id is not None:
                        other_tasks = db.query(WorkflowTask).join(WorkflowTask.node).filter(
                            WorkflowTask.instance_id == instance_id,
                            WorkflowNode.erp_query_id == current_task.node.erp_query_id
                        ).all()
                        for ot in other_tasks:
                            ot.docnum = docnum_clean

        if active_docnum:
            instance.docnum = active_docnum
            instance.external_ref = f"DocNum:{active_docnum}"

        # 2. Complete the current pending task for this node
        if current_task:
            current_task.status = 'COMPLETED'
            current_task.completed_at = datetime.utcnow()
            current_task.completed_by_id = user_id
            db.add(current_task)

        # 3. Add optional comment
        comment_id = None
        if comment_text and comment_text.strip():
            comment = WorkflowComment(
                instance_id=instance_id,
                task_id=current_task.id if current_task else None,
                user_id=user_id,
                comment_text=comment_text,
                created_at=datetime.utcnow()
            )
            db.add(comment)
            db.flush()
            comment_id = comment.id

        # 4. Determine transitions to execute
        # If source node is TASK, we execute ALL transitions starting from this node.
        # If DECISION, we only execute the selected transition.
        if source_node.type == 'TASK':
            transitions_to_execute = db.query(WorkflowTransition).filter(
                WorkflowTransition.process_id == instance.process_id,
                WorkflowTransition.source_node_id == source_node.id
            ).all()
        else:
            transitions_to_execute = [transition]

        # Collect attachments from the completed source task to forward to next node
        from models import WorkflowAttachment
        forwarded_attachments = []
        if current_task:
            forwarded_attachments = db.query(WorkflowAttachment).filter(
                WorkflowAttachment.task_id == current_task.id
            ).all()

        # Queue elements: (curr_target, action_name, source_node_id)
        queue = []
        for t in transitions_to_execute:
            queue.append((t.target_node, t.action_name, t.source_node_id))

        # Keep track of tasks created for notifications
        new_tasks = []
        completed_workflow = False
        last_target_node_id = None

        while queue:
            curr_target, action, src_id = queue.pop(0)
            last_target_node_id = curr_target.id

            # Log history
            # Only append user comment to the direct transitions originating from user interaction (first level)
            is_first_level = (src_id == source_node.id)
            if is_first_level:
                history_comment = f"Acción ejecutada: '{action}'." + (f" Comentario: {comment_text}" if comment_text else "")
            else:
                if curr_target.type == 'GATEWAY':
                    history_comment = f"Avance automático a compuerta: '{curr_target.name}'."
                elif curr_target.type == 'NOTIFICATION':
                    history_comment = f"Avance automático a etapa de notificación: '{curr_target.name}'."
                else:
                    history_comment = f"Transición automática a través de compuerta: '{action}'."

            history = WorkflowHistory(
                instance_id=instance_id,
                task_id=current_task.id if current_task else None,
                source_node_id=src_id,
                target_node_id=curr_target.id,
                user_id=user_id,
                action='TRANSITION',
                comment=history_comment,
                timestamp=datetime.utcnow()
            )
            db.add(history)

            # Check target node type
            if curr_target.type == 'END':
                completed_workflow = True
            elif curr_target.type in ['TASK', 'DECISION']:
                # Determine initial docnum for the target node based on shared custom query
                target_docnum = None
                if curr_target.erp_query_id is not None:
                    existing_docnum_task = db.query(WorkflowTask).join(WorkflowTask.node).filter(
                        WorkflowTask.instance_id == instance_id,
                        WorkflowNode.erp_query_id == curr_target.erp_query_id,
                        WorkflowTask.docnum != None,
                        WorkflowTask.docnum != ""
                    ).first()
                    if existing_docnum_task:
                        target_docnum = existing_docnum_task.docnum
                
                # Create a new pending task for the destination role
                new_task = WorkflowTask(
                    instance_id=instance_id,
                    node_id=curr_target.id,
                    assigned_role_id=curr_target.role_id,
                    status='PENDING',
                    sla_hours=curr_target.sla_hours, # Inherited from node config
                    docnum=target_docnum,
                    created_at=datetime.utcnow()
                )
                db.add(new_task)
                new_tasks.append(new_task)
            elif curr_target.type == 'GATEWAY':
                # Automatically execute all transitions originating from this GATEWAY
                gateway_transitions = db.query(WorkflowTransition).filter(
                    WorkflowTransition.process_id == instance.process_id,
                    WorkflowTransition.source_node_id == curr_target.id
                ).all()
                for gt in gateway_transitions:
                    queue.append((gt.target_node, gt.action_name, curr_target.id))
            elif curr_target.type == 'NOTIFICATION':
                # Send info notification immediately
                try:
                    from services.email_service import send_info_notification_email
                    send_info_notification_email(
                        db, instance, curr_target,
                        from_comment=comment_text,
                        from_attachments=forwarded_attachments
                    )
                except Exception as e:
                    print(f"Error sending info notification: {str(e)}")
                # Automatically execute all transitions originating from this NOTIFICATION node
                notif_transitions = db.query(WorkflowTransition).filter(
                    WorkflowTransition.process_id == instance.process_id,
                    WorkflowTransition.source_node_id == curr_target.id
                ).all()
                for nt in notif_transitions:
                    queue.append((nt.target_node, nt.action_name, curr_target.id))

        # Update instance state to the last processed target node
        if last_target_node_id:
            instance.current_node_id = last_target_node_id

        # Count remaining active tasks
        db.flush()
        remaining_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.instance_id == instance_id,
            WorkflowTask.status == 'PENDING'
        ).count()
            
        if completed_workflow and remaining_tasks == 0:
            instance.status = 'COMPLETED'
            history_end = WorkflowHistory(
                instance_id=instance_id,
                source_node_id=last_target_node_id,
                target_node_id=None,
                user_id=user_id,
                action='COMPLETE',
                comment="Workflow finalizado.",
                timestamp=datetime.utcnow()
            )
            db.add(history_end)

        instance.updated_at = datetime.utcnow()
        db.commit()
        
        forwarded_attachments = []
        if current_task:
            forwarded_attachments = db.query(WorkflowAttachment).filter(
                WorkflowAttachment.task_id == current_task.id
            ).all()

        # Trigger email notifications
        try:
            from services.email_service import (
                send_task_notification_email, 
                send_workflow_completed_notification, 
                send_task_completion_email
            )
            
            # Send completion receipt email for the resolved task
            if current_task:
                send_task_completion_email(
                    db=db,
                    task=current_task,
                    action_name=transition.action_name,
                    comment_text=comment_text,
                    attachments=forwarded_attachments
                )
                
            if instance.status == 'COMPLETED':
                send_workflow_completed_notification(
                    db=db,
                    instance=instance,
                    from_comment=comment_text,
                    from_attachments=forwarded_attachments
                )
            
            for nt in new_tasks:
                db.refresh(nt)
                send_task_notification_email(
                    db, nt,
                    from_comment=comment_text,
                    from_attachments=forwarded_attachments
                )
        except Exception as e:
            print(f"Error sending transition notifications: {str(e)}")
            
        return instance

    @staticmethod
    def cancel_instance(db: Session, instance_id: int, user_id: int, comment_text: str) -> WorkflowInstance:
        """
        Cancels the active workflow instance.
        """
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance:
            raise ValueError("La instancia no existe.")
        if instance.status != 'ACTIVE':
            raise ValueError("Solo se pueden cancelar instancias activas.")

        # Cancel any pending task
        pending_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.instance_id == instance_id,
            WorkflowTask.status == 'PENDING'
        ).all()
        for pt in pending_tasks:
            pt.status = 'CANCELLED'
            pt.completed_at = datetime.utcnow()
            pt.completed_by_id = user_id
            db.add(pt)

        instance.status = 'CANCELLED'
        instance.updated_at = datetime.utcnow()

        if comment_text and comment_text.strip():
            comment = WorkflowComment(
                instance_id=instance_id,
                user_id=user_id,
                comment_text=f"[Cancelación] {comment_text}",
                created_at=datetime.utcnow()
            )
            db.add(comment)

        history = WorkflowHistory(
            instance_id=instance_id,
            source_node_id=instance.current_node_id,
            target_node_id=None,
            user_id=user_id,
            action='CANCEL',
            comment=f"Instancia cancelada. Motivo: {comment_text}",
            timestamp=datetime.utcnow()
        )
        db.add(history)
        db.commit()
        return instance

    @staticmethod
    def reopen_instance(db: Session, instance_id: int, user_id: int, comment_text: str) -> WorkflowInstance:
        """
        Reopens a completed or cancelled workflow instance and returns it to the first non-start task.
        """
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance:
            raise ValueError("La instancia no existe.")
        if instance.status == 'ACTIVE':
            raise ValueError("La instancia ya está activa.")

        # Find the first TASK node in the process configuration
        first_task_node = db.query(WorkflowNode).filter(
            WorkflowNode.process_id == instance.process_id,
            WorkflowNode.type == 'TASK'
        ).first()

        if not first_task_node:
            raise ValueError("No se encontró un nodo tipo TASK para reabrir el proceso.")

        assigned_role_id = first_task_node.role_id if first_task_node.role_id else db.query(WorkflowRole).first().id

        old_status = instance.status
        instance.status = 'ACTIVE'
        instance.current_node_id = first_task_node.id
        instance.updated_at = datetime.utcnow()

        # Create a new pending task
        new_task = WorkflowTask(
            instance_id=instance_id,
            node_id=first_task_node.id,
            assigned_role_id=assigned_role_id,
            status='PENDING',
            created_at=datetime.utcnow()
        )
        db.add(new_task)

        if comment_text and comment_text.strip():
            comment = WorkflowComment(
                instance_id=instance_id,
                user_id=user_id,
                comment_text=f"[Reapertura] {comment_text}",
                created_at=datetime.utcnow()
            )
            db.add(comment)

        history = WorkflowHistory(
            instance_id=instance_id,
            source_node_id=None,
            target_node_id=first_task_node.id,
            user_id=user_id,
            action='REOPEN',
            comment=f"Instancia reabierta desde estado {old_status}. Motivo: {comment_text}",
            timestamp=datetime.utcnow()
        )
        db.add(history)
        db.commit()
        
        # Trigger email notification for reopened task
        try:
            db.refresh(new_task)
            from services.email_service import send_task_notification_email
            send_task_notification_email(db, new_task)
        except Exception as e:
            print(f"Error sending reopen notification: {str(e)}")
            
        return instance
