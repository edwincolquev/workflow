import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import WorkflowProcess, WorkflowNode, WorkflowTransition, WorkflowInstance, WorkflowTask, WorkflowHistory

with get_db() as db:
    print("=== WORKFLOW PROCESSES ===")
    processes = db.query(WorkflowProcess).all()
    for p in processes:
        print(f"Process ID: {p.id}, Name: {p.name}, Active: {p.active}")
        print("  Nodes:")
        nodes = db.query(WorkflowNode).filter(WorkflowNode.process_id == p.id).all()
        for n in nodes:
            print(f"    - Node ID: {n.id}, Name: {n.name}, Type: {n.type}, Role ID: {n.role_id}")
        print("  Transitions:")
        transitions = db.query(WorkflowTransition).filter(WorkflowTransition.process_id == p.id).all()
        for t in transitions:
            print(f"    - Transition ID: {t.id}, {t.source_node.name} ({t.source_node_id}) -> {t.target_node.name} ({t.target_node_id}) [Action: '{t.action_name}']")
        print("-" * 50)
        
    print("\n=== INSTANCES WITH 'NUEVOS' or '28' ===")
    instances = db.query(WorkflowInstance).filter(
        (WorkflowInstance.title.like("%NUEVOS%")) | 
        (WorkflowInstance.title.like("%28%")) |
        (WorkflowInstance.title.like("%MARILIA 28%"))
    ).all()
    for inst in instances:
        print(f"Instance ID: {inst.id}, Title: {inst.title}, Status: {inst.status}, Current Node: {inst.current_node.name if inst.current_node else 'None'} ({inst.current_node_id})")
        print("  Tasks:")
        tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id).order_by(WorkflowTask.id).all()
        for t in tasks:
            print(f"    - Task ID: {t.id}, Node: {t.node.name} ({t.node_id}), Status: {t.status}, Assigned User: {t.assigned_user_id}, Completed By: {t.completed_by_id}")
        print("  History:")
        history = db.query(WorkflowHistory).filter(WorkflowHistory.instance_id == inst.id).order_by(WorkflowHistory.timestamp).all()
        for h in history:
            print(f"    - History ID: {h.id}, Source Node: {h.source_node_id}, Target Node: {h.target_node_id}, User: {h.user_id}, Action: {h.action}, Comment: {h.comment}")
        print("=" * 60)
