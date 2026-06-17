from sqlalchemy.orm import Session
from models import WorkflowNode, WorkflowTransition, WorkflowInstance, WorkflowTask

class WorkflowValidatorService:
    @staticmethod
    def is_node_in_use(db: Session, node_id: int) -> tuple[bool, str]:
        """Checks if a node is currently in use by active instances or active tasks."""
        # Check active instances
        active_instances = db.query(WorkflowInstance).filter(
            WorkflowInstance.current_node_id == node_id,
            WorkflowInstance.status == 'ACTIVE'
        ).all()
        if active_instances:
            names = ", ".join([inst.title for inst in active_instances[:3]])
            count = len(active_instances)
            suffix = "..." if count > 3 else ""
            return True, f"El nodo está siendo ocupado actualmente por {count} instancia(s) activa(s) (ej: {names}{suffix})."

        # Check pending tasks
        pending_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.node_id == node_id,
            WorkflowTask.status == 'PENDING'
        ).all()
        if pending_tasks:
            return True, f"Existen {len(pending_tasks)} tarea(s) pendiente(s) asociadas a este nodo."

        # Check transitions
        transitions = db.query(WorkflowTransition).filter(
            (WorkflowTransition.source_node_id == node_id) | 
            (WorkflowTransition.target_node_id == node_id)
        ).all()
        if transitions:
            return True, f"El nodo está asociado a {len(transitions)} regla(s) de transición activa(s). Elimine o modifique las transiciones primero."

        return False, ""

    @staticmethod
    def is_process_in_use(db: Session, process_id: int) -> tuple[bool, str]:
        """Checks if a process has active instances."""
        active_instances = db.query(WorkflowInstance).filter(
            WorkflowInstance.process_id == process_id,
            WorkflowInstance.status == 'ACTIVE'
        ).all()
        if active_instances:
            return True, f"El proceso tiene {len(active_instances)} instancia(s) activa(s) en curso."
        return False, ""

    @staticmethod
    def validate_process(db: Session, process_id: int) -> dict:
        """Validates the logical structure of a workflow process."""
        nodes = db.query(WorkflowNode).filter(WorkflowNode.process_id == process_id).all()
        transitions = db.query(WorkflowTransition).filter(WorkflowTransition.process_id == process_id).all()
        
        errors = []
        warnings = []
        
        if not nodes:
            return {"valid": False, "errors": ["El proceso no tiene ningún nodo configurado."], "warnings": []}

        # 1. Check START and END nodes count
        start_nodes = [n for n in nodes if n.type == 'START']
        end_nodes = [n for n in nodes if n.type == 'END']
        
        if len(start_nodes) != 1:
            errors.append(f"El proceso debe tener exactamente 1 nodo de tipo START (actualmente tiene {len(start_nodes)}).")
        
        if len(end_nodes) < 1:
            errors.append("El proceso debe tener al menos 1 nodo de tipo END.")

        # If we don't have exactly one start, we can't perform reachability checks properly
        if len(start_nodes) != 1:
            return {"valid": False, "errors": errors, "warnings": warnings}

        start_node = start_nodes[0]
        
        # Build adjacency list
        adj = {n.id: [] for n in nodes}
        rev_adj = {n.id: [] for n in nodes}
        for t in transitions:
            if t.source_node_id in adj:
                adj[t.source_node_id].append(t.target_node_id)
            if t.target_node_id in rev_adj:
                rev_adj[t.target_node_id].append(t.source_node_id)

        # 2. Check reachability from START (forward BFS)
        visited_forward = set()
        queue = [start_node.id]
        visited_forward.add(start_node.id)
        
        while queue:
            curr = queue.pop(0)
            for neighbor in adj[curr]:
                if neighbor not in visited_forward:
                    visited_forward.add(neighbor)
                    queue.append(neighbor)
                    
        # Find orphaned nodes (not reachable from start)
        nodes_dict = {n.id: n for n in nodes}
        orphaned = [nodes_dict[nid].name for nid in nodes_dict if nid not in visited_forward]
        if orphaned:
            errors.append(f"Los siguientes nodos no son alcanzables desde el Inicio (nodos huérfanos): {', '.join(orphaned)}.")

        # 3. Check co-reachability (each node should be able to reach at least one END node)
        # We run a backward BFS starting from all END nodes simultaneously
        visited_backward = set()
        queue = [n.id for n in end_nodes]
        for nid in queue:
            visited_backward.add(nid)
            
        while queue:
            curr = queue.pop(0)
            for parent in rev_adj[curr]:
                if parent not in visited_backward:
                    visited_backward.add(parent)
                    queue.append(parent)

        cannot_reach_end = [nodes_dict[nid].name for nid in nodes_dict if nid not in visited_backward]
        # Filter nodes that are already orphaned (since they are already errors, don't duplicate confusion)
        cannot_reach_end = [name for name in cannot_reach_end if name not in orphaned]
        if cannot_reach_end:
            errors.append(f"Los siguientes nodos están en un callejón sin salida (no pueden llegar a ningún nodo END): {', '.join(cannot_reach_end)}.")

        # 4. Check that TASK and DECISION nodes have outgoing transitions
        for n in nodes:
            if n.type in ['TASK', 'DECISION'] and n.id in visited_forward:
                if not adj[n.id]:
                    errors.append(f"El nodo '{n.name}' ({n.type}) no tiene transiciones salientes definidas.")

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }
