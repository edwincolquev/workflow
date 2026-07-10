import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import WorkflowProcess, WorkflowInstance

with get_db() as db:
    print("Processes:")
    for p in db.query(WorkflowProcess).all():
        print(f"ID: {p.id}, Name: '{p.name}', Active: {p.active}")
    print("\nInstances:")
    for inst in db.query(WorkflowInstance).all():
        print(f"ID: {inst.id}, Title: '{inst.title}', Process ID: {inst.process_id}")
