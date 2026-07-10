import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import WorkflowInstance, WorkflowProcess

with get_db() as db:
    instances = db.query(WorkflowInstance).order_by(WorkflowInstance.id.desc()).limit(15).all()
    for inst in instances:
        print(f"ID: {inst.id}, Title: {inst.title}, Process: {inst.process.name} (ID: {inst.process_id}), Current Node: {inst.current_node.name if inst.current_node else 'None'}")
