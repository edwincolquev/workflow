import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import WorkflowErpQuery, WorkflowNode, WorkflowInstance, WorkflowInstanceQueryDocNum, WorkflowTask

with get_db() as db:
    print("--- ERP QUERIES ---")
    queries = db.query(WorkflowErpQuery).all()
    for q in queries:
        print(f"ID: {q.id}, Name: {q.name}, SQL: {q.sql_query}")
        
    print("\n--- NODES WITH ERP QUERY ID ---")
    nodes = db.query(WorkflowNode).filter(WorkflowNode.erp_query_id != None).all()
    for n in nodes:
        print(f"ID: {n.id}, Name: {n.name}, Process ID: {n.process_id}, Query ID: {n.erp_query_id}")

    print("\n--- INSTANCES ---")
    instances = db.query(WorkflowInstance).all()
    for inst in instances:
        print(f"ID: {inst.id}, Title: {inst.title}, DocNum: {inst.docnum}, Node ID: {inst.current_node_id}")

    print("\n--- INSTANCE QUERY DOCNUM ---")
    docnums = db.query(WorkflowInstanceQueryDocNum).all()
    for d in docnums:
        print(f"ID: {d.id}, Instance ID: {d.instance_id}, Query ID: {d.query_id}, DocNum: {d.docnum}")

    print("\n--- PENDING TASKS ---")
    tasks = db.query(WorkflowTask).filter(WorkflowTask.status == 'PENDING').all()
    for t in tasks:
        print(f"ID: {t.id}, Instance ID: {t.instance_id}, Node ID: {t.node_id}, Node Name: {t.node.name}, Assigned Role: {t.assigned_role.name}")
