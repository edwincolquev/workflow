import sys
import os

# Adjust path to find modules in workspace
sys.path.append('c:/supply_chain')

from database import get_db
from models import WorkflowProcess, WorkflowNode, WorkflowTransition, WorkflowRole, WorkflowUser, WorkflowInstance, WorkflowTask
from engine import WorkflowEngine

def run_test():
    print("Iniciando pruebas de flujo TASK (Paralelo) y DECISION (XOR)...")
    
    with get_db() as db:
        # Fetch resources
        role = db.query(WorkflowRole).first()
        admin = db.query(WorkflowUser).filter(WorkflowUser.username == 'admin').first()
        
        try:
            # 1. Create a process
            proc = WorkflowProcess(name="Test Splits", description="Prueba de paralelismo y decision", active=True)
            db.add(proc)
            db.flush()
            
            # Nodes
            # START -> TASK_1 (leads to TASK_2 and TASK_3 in parallel) -> END
            n_start = WorkflowNode(process_id=proc.id, name="Inicio", type="START")
            n_task1 = WorkflowNode(process_id=proc.id, name="Etapa Tarea 1", type="TASK")
            n_task2 = WorkflowNode(process_id=proc.id, name="Sub-Tarea A", type="TASK")
            n_task3 = WorkflowNode(process_id=proc.id, name="Sub-Tarea B", type="TASK")
            n_end = WorkflowNode(process_id=proc.id, name="Fin", type="END")
            
            db.add_all([n_start, n_task1, n_task2, n_task3, n_end])
            db.flush()
            
            # Transitions
            # START -> TASK_1
            t_start = WorkflowTransition(
                process_id=proc.id, source_node_id=n_start.id, role_id=role.id,
                action_name="Auto-Iniciar", target_node_id=n_task1.id, target_role_id=role.id
            )
            # TASK_1 -> TASK_2
            t_1_to_2 = WorkflowTransition(
                process_id=proc.id, source_node_id=n_task1.id, role_id=role.id,
                action_name="Avanzar A", target_node_id=n_task2.id, target_role_id=role.id
            )
            # TASK_1 -> TASK_3
            t_1_to_3 = WorkflowTransition(
                process_id=proc.id, source_node_id=n_task1.id, role_id=role.id,
                action_name="Avanzar B", target_node_id=n_task3.id, target_role_id=role.id
            )
            # TASK_2 -> END
            t_2_to_end = WorkflowTransition(
                process_id=proc.id, source_node_id=n_task2.id, role_id=role.id,
                action_name="Completar A", target_node_id=n_end.id, target_role_id=role.id
            )
            # TASK_3 -> END
            t_3_to_end = WorkflowTransition(
                process_id=proc.id, source_node_id=n_task3.id, role_id=role.id,
                action_name="Completar B", target_node_id=n_end.id, target_role_id=role.id
            )
            
            db.add_all([t_start, t_1_to_2, t_1_to_3, t_2_to_end, t_3_to_end])
            db.flush()
            
            # Create instance
            print("\n1. Creando instancia de flujo...")
            inst = WorkflowEngine.create_instance(db, proc.id, "Instancia Paralela Test", admin.id)
            print(f"Instancia creada ID={inst.id}, Estado={inst.status}, Nodo actual={inst.current_node.name}")
            
            # Verify active task is 'Etapa Tarea 1'
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas:", [t.node.name for t in tasks])
            assert len(tasks) == 1
            assert tasks[0].node_id == n_task1.id
            
            # Execute transition for TASK_1 (type TASK).
            # Passing t_1_to_2.id. The engine should automatically execute BOTH t_1_to_2 and t_1_to_3!
            print("\n2. Completando 'Etapa Tarea 1' (tipo TASK)...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_1_to_2.id, admin.id, "Completando Tarea 1")
            
            # Verify that BOTH Sub-Tarea A and Sub-Tarea B tasks are pending!
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas ahora (esperado: A y B):", [t.node.name for t in tasks])
            assert len(tasks) == 2
            task_nodes = set(t.node_id for t in tasks)
            assert n_task2.id in task_nodes
            assert n_task3.id in task_nodes
            
            # Execute t_2_to_end. Completing Sub-Tarea A.
            print("\n3. Completando 'Sub-Tarea A'...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_2_to_end.id, admin.id, "Completando A")
            
            # Verify that instance remains ACTIVE because Sub-Tarea B is still pending
            print(f"Estado de la Instancia: {inst.status} (esperado: ACTIVE)")
            assert inst.status == 'ACTIVE'
            
            # Verify that only Sub-Tarea B is pending now
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas ahora (esperado: solo B):", [t.node.name for t in tasks])
            assert len(tasks) == 1
            assert tasks[0].node_id == n_task3.id
            
            # Execute t_3_to_end. Completing Sub-Tarea B.
            print("\n4. Completando 'Sub-Tarea B'...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_3_to_end.id, admin.id, "Completando B")
            
            # Verify that instance is now COMPLETED
            print(f"Estado de la Instancia al final: {inst.status} (esperado: COMPLETED)")
            assert inst.status == 'COMPLETED'
            
            # Verify there are 0 active tasks left
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas al final:", len(tasks))
            assert len(tasks) == 0
            
            print("\n¡Pruebas lógicas de flujo de control paralelas pasaron exitosamente!")
            
        except Exception as e:
            print(f"\n❌ Error durante las pruebas: {str(e)}")
            raise e
        finally:
            db.rollback()
            print("\nDeshaciendo cambios temporales en base de datos.")

if __name__ == "__main__":
    run_test()
