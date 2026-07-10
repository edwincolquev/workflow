import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import WorkflowProcess, WorkflowNode, WorkflowTransition, WorkflowTask, WorkflowInstance, WorkflowHistory

with get_db() as db:
    print("=== INSPECTING FOR ORPHAN RECORDS ===")
    
    # 1. Transitions pointing to non-existent processes
    orphan_trans_proc = db.query(WorkflowTransition).filter(
        ~WorkflowTransition.process_id.in_(db.query(WorkflowProcess.id))
    ).all()
    print(f"Found {len(orphan_trans_proc)} transitions with non-existent process_id.")
    for t in orphan_trans_proc:
        print(f"  - Transition ID {t.id}: process_id={t.process_id}, action='{t.action_name}'")

    # 2. Transitions pointing to non-existent source nodes
    orphan_trans_src = db.query(WorkflowTransition).filter(
        ~WorkflowTransition.source_node_id.in_(db.query(WorkflowNode.id))
    ).all()
    print(f"Found {len(orphan_trans_src)} transitions with non-existent source_node_id.")
    for t in orphan_trans_src:
        print(f"  - Transition ID {t.id}: source_node_id={t.source_node_id}, action='{t.action_name}'")

    # 3. Transitions pointing to non-existent target nodes
    orphan_trans_tgt = db.query(WorkflowTransition).filter(
        ~WorkflowTransition.target_node_id.in_(db.query(WorkflowNode.id))
    ).all()
    print(f"Found {len(orphan_trans_tgt)} transitions with non-existent target_node_id.")
    for t in orphan_trans_tgt:
        print(f"  - Transition ID {t.id}: target_node_id={t.target_node_id}, action='{t.action_name}'")

    # 4. Nodes pointing to non-existent processes
    orphan_nodes_proc = db.query(WorkflowNode).filter(
        ~WorkflowNode.process_id.in_(db.query(WorkflowProcess.id))
    ).all()
    print(f"Found {len(orphan_nodes_proc)} nodes with non-existent process_id.")
    for n in orphan_nodes_proc:
        print(f"  - Node ID {n.id}: process_id={n.process_id}, name='{n.name}'")

    # 5. Tasks pointing to non-existent nodes
    orphan_tasks_node = db.query(WorkflowTask).filter(
        ~WorkflowTask.node_id.in_(db.query(WorkflowNode.id))
    ).all()
    print(f"Found {len(orphan_tasks_node)} tasks with non-existent node_id.")
    for tk in orphan_tasks_node:
        print(f"  - Task ID {tk.id}: node_id={tk.node_id}, status='{tk.status}'")

    # 6. Tasks pointing to non-existent instances
    orphan_tasks_inst = db.query(WorkflowTask).filter(
        ~WorkflowTask.instance_id.in_(db.query(WorkflowInstance.id))
    ).all()
    print(f"Found {len(orphan_tasks_inst)} tasks with non-existent instance_id.")

    # 7. Instances pointing to non-existent processes
    orphan_inst_proc = db.query(WorkflowInstance).filter(
        ~WorkflowInstance.process_id.in_(db.query(WorkflowProcess.id))
    ).all()
    print(f"Found {len(orphan_inst_proc)} instances with non-existent process_id.")
    for inst in orphan_inst_proc:
        print(f"  - Instance ID {inst.id}: process_id={inst.process_id}, title='{inst.title}'")

    # Let's perform cleanup if requested
    confirm = len(orphan_trans_proc) + len(orphan_trans_src) + len(orphan_trans_tgt) + len(orphan_nodes_proc) + len(orphan_tasks_node) + len(orphan_tasks_inst) + len(orphan_inst_proc)
    if confirm > 0:
        print("\nDeleting orphan records...")
        for t in orphan_trans_proc + orphan_trans_src + orphan_trans_tgt:
            db.delete(t)
        for n in orphan_nodes_proc:
            db.delete(n)
        for tk in orphan_tasks_node + orphan_tasks_inst:
            db.delete(tk)
        for inst in orphan_inst_proc:
            db.delete(inst)
        db.commit()
        print("Cleanup completed successfully!")
    else:
        print("\nNo orphan records found in this local database.")
