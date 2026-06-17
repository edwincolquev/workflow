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
        instance = WorkflowInstance(
            process_id=process_id,
            title=title,
            status='ACTIVE',
            current_node_id=start_node.id,
            external_ref=external_ref,
            created_by_id=creator_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(instance)
        db.flush()  # Generate instance ID

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

        # 4. Auto-advance from START node to the first TASK
        # We find transitions originating from START node
        start_transition = db.query(WorkflowTransition).filter(
            WorkflowTransition.process_id == process_id,
            WorkflowTransition.source_node_id == start_node.id
        ).first()

        if start_transition:
            # Advance to first target node automatically
            target_node = start_transition.target_node
            instance.current_node_id = target_node.id
            
            # Log transition in history
            history_trans = WorkflowHistory(
                instance_id=instance.id,
                source_node_id=start_node.id,
                target_node_id=target_node.id,
                user_id=creator_id,
                action='TRANSITION',
                comment="Transición automática inicial.",
                timestamp=datetime.utcnow()
            )
            db.add(history_trans)

            # If it's a TASK node, create a pending task
            if target_node.type == 'TASK':
                task = WorkflowTask(
                    instance_id=instance.id,
                    node_id=target_node.id,
                    assigned_role_id=start_transition.target_role_id,
                    status='PENDING',
                    created_at=datetime.utcnow()
                )
                db.add(task)
        
        db.commit()
        
        # Trigger email notification for the initial task
        if start_transition and target_node.type == 'TASK':
            try:
                db.refresh(task)
                from services.email_service import send_task_notification_email
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

        # Filter transitions by user's roles
        user_role_ids = [role.id for role in user.roles]
        available = []
        for t in transitions:
            if t.role_id in user_role_ids:
                available.append(t)
                
        return available

    @staticmethod
    def execute_transition(db: Session, instance_id: int, transition_id: int, user_id: int, comment_text: str = None) -> WorkflowInstance:
        """
        Advances the workflow along a transition, completing the current task
        and creating the next task(s) or finalizing the workflow.
        For TASK nodes, it completes the task and automatically executes ALL outgoing transitions.
        For DECISION nodes, it executes only the selected transition.
        """
        # 1. Load objects
        instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance:
            raise ValueError("La instancia no existe.")
        if instance.status != 'ACTIVE':
            raise ValueError("La instancia no está activa.")

        transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).first()
        if not transition or transition.process_id != instance.process_id:
            raise ValueError("Transición no válida para el estado actual de la instancia.")

        user = db.query(WorkflowUser).filter(WorkflowUser.id == user_id).first()
        if not user:
            raise ValueError("Usuario no existe.")
            
        user_role_ids = [role.id for role in user.roles]
        if transition.role_id not in user_role_ids:
            raise ValueError("El usuario no tiene el rol requerido para esta acción.")

        source_node = transition.source_node
        
        # 2. Complete the current pending task for this node
        current_task = db.query(WorkflowTask).filter(
            WorkflowTask.instance_id == instance_id,
            WorkflowTask.node_id == source_node.id,
            WorkflowTask.status == 'PENDING'
        ).first()

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

        # Keep track of tasks created for notifications
        new_tasks = []
        completed_workflow = False
        last_target_node_id = None

        for t in transitions_to_execute:
            target_node = t.target_node
            last_target_node_id = target_node.id
            
            # Log history
            history = WorkflowHistory(
                instance_id=instance_id,
                task_id=current_task.id if current_task else None,
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                user_id=user_id,
                action='TRANSITION',
                comment=f"Acción ejecutada: '{t.action_name}'." + (f" Comentario: {comment_text}" if comment_text else ""),
                timestamp=datetime.utcnow()
            )
            db.add(history)

            # Check target node type
            if target_node.type == 'END':
                completed_workflow = True
            elif target_node.type in ['TASK', 'DECISION']:
                # Create a new pending task for the destination role
                new_task = WorkflowTask(
                    instance_id=instance_id,
                    node_id=target_node.id,
                    assigned_role_id=t.target_role_id,
                    status='PENDING',
                    created_at=datetime.utcnow()
                )
                db.add(new_task)
                new_tasks.append(new_task)

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
        
        # Trigger email notifications
        try:
            from services.email_service import send_task_notification_email, send_workflow_completed_notification
            if instance.status == 'COMPLETED':
                send_workflow_completed_notification(db, instance)
            
            for nt in new_tasks:
                db.refresh(nt)
                send_task_notification_email(db, nt)
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

        # Find standard transition for this first task node to identify the default role
        transition = db.query(WorkflowTransition).filter(
            WorkflowTransition.process_id == instance.process_id,
            WorkflowTransition.target_node_id == first_task_node.id
        ).first()
        
        assigned_role_id = transition.target_role_id if transition else db.query(WorkflowRole).first().id

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
