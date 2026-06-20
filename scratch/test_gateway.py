import sys
import os

# Adjust path to find modules in workspace
sys.path.append('c:/supply_chain')

from database import get_db
from models import WorkflowProcess, WorkflowNode, WorkflowTransition, WorkflowRole, WorkflowUser, WorkflowInstance, WorkflowTask, WorkflowHistory
from engine import WorkflowEngine

def run_gateway_test():
    print("Iniciando pruebas de compuerta automática GATEWAY...")
    
    with get_db() as db:
        # Fetch resources
        role = db.query(WorkflowRole).first()
        admin = db.query(WorkflowUser).filter(WorkflowUser.username == 'admin').first()
        
        if not role or not admin:
            print("[ERROR] No se encontraron roles o el usuario admin para la prueba. Asegure que la BD esté inicializada.")
            return

        try:
            # 1. Create a process
            proc = WorkflowProcess(name="Test Gateway Process", description="Proceso para validar compuertas GATEWAY", active=True)
            db.add(proc)
            db.flush()
            
            # Nodes
            n_start = WorkflowNode(process_id=proc.id, name="Inicio", type="START")
            n_task_aprob = WorkflowNode(process_id=proc.id, name="Solicitar Aprobación", type="TASK", role_id=role.id)
            n_decision = WorkflowNode(process_id=proc.id, name="Decidir Avance", type="DECISION", role_id=role.id)
            n_gateway = WorkflowNode(process_id=proc.id, name="Compuerta Aprobación", type="GATEWAY")
            n_para_a = WorkflowNode(process_id=proc.id, name="Tarea Paralela A", type="TASK", role_id=role.id)
            n_para_b = WorkflowNode(process_id=proc.id, name="Tarea Paralela B", type="TASK", role_id=role.id)
            n_end = WorkflowNode(process_id=proc.id, name="Fin", type="END")
            
            db.add_all([n_start, n_task_aprob, n_decision, n_gateway, n_para_a, n_para_b, n_end])
            db.flush()
            
            # Transitions
            # 1. START -> TASK_aprob
            t_start = WorkflowTransition(
                process_id=proc.id, source_node_id=n_start.id,
                action_name="Auto-Iniciar", target_node_id=n_task_aprob.id
            )
            # 2. TASK_aprob -> DECISION
            t_aprob_to_dec = WorkflowTransition(
                process_id=proc.id, source_node_id=n_task_aprob.id,
                action_name="Enviar a Decisión", target_node_id=n_decision.id
            )
            # 3. DECISION -> GATEWAY (Option "Aprobar")
            t_dec_aprobar = WorkflowTransition(
                process_id=proc.id, source_node_id=n_decision.id,
                action_name="Aprobar y Paralelizar", target_node_id=n_gateway.id
            )
            # 4. DECISION -> END (Option "Rechazar")
            t_dec_rechazar = WorkflowTransition(
                process_id=proc.id, source_node_id=n_decision.id,
                action_name="Rechazar", target_node_id=n_end.id
            )
            # 5. GATEWAY -> Tarea Paralela A
            t_gate_to_a = WorkflowTransition(
                process_id=proc.id, source_node_id=n_gateway.id,
                action_name="Ruta A", target_node_id=n_para_a.id
            )
            # 6. GATEWAY -> Tarea Paralela B
            t_gate_to_b = WorkflowTransition(
                process_id=proc.id, source_node_id=n_gateway.id,
                action_name="Ruta B", target_node_id=n_para_b.id
            )
            # 7. Tarea A -> END
            t_a_to_end = WorkflowTransition(
                process_id=proc.id, source_node_id=n_para_a.id,
                action_name="Terminar A", target_node_id=n_end.id
            )
            # 8. Tarea B -> END
            t_b_to_end = WorkflowTransition(
                process_id=proc.id, source_node_id=n_para_b.id,
                action_name="Terminar B", target_node_id=n_end.id
            )
            
            db.add_all([t_start, t_aprob_to_dec, t_dec_aprobar, t_dec_rechazar, t_gate_to_a, t_gate_to_b, t_a_to_end, t_b_to_end])
            db.flush()
            
            # --- START EXECUTION ---
            print("\n1. Creando instancia del flujo...")
            inst = WorkflowEngine.create_instance(db, proc.id, "Flujo Prueba GATEWAY", admin.id)
            print(f"Instancia creada: ID={inst.id}, Estado={inst.status}, Nodo actual={inst.current_node.name}")
            
            # Verify active task is 'Solicitar Aprobación'
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas:", [t.node.name for t in tasks])
            assert len(tasks) == 1
            assert tasks[0].node_id == n_task_aprob.id
            
            # Advance to Decision
            print("\n2. Completando 'Solicitar Aprobación' -> Moviendo a 'Decidir Avance'...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_aprob_to_dec.id, admin.id, "Avanzando a decisión")
            
            # Verify active task is 'Decidir Avance'
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas:", [t.node.name for t in tasks])
            assert len(tasks) == 1
            assert tasks[0].node_id == n_decision.id
            
            # Choose Option "Aprobar y Paralelizar" (targets the GATEWAY)
            # The engine must execute t_dec_aprobar, detect GATEWAY, automatically execute t_gate_to_a and t_gate_to_b,
            # and create TWO pending tasks: "Tarea Paralela A" and "Tarea Paralela B".
            print("\n3. Seleccionando 'Aprobar y Paralelizar' (Apuntando a compuerta GATEWAY)...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_dec_aprobar.id, admin.id, "Aprobando")
            
            # Verify that BOTH tasks are active
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas después de compuerta (esperado: A y B):", [t.node.name for t in tasks])
            assert len(tasks) == 2
            task_nodes = set(t.node_id for t in tasks)
            assert n_para_a.id in task_nodes
            assert n_para_b.id in task_nodes
            
            # Verify history contains the auto-advance entries
            history = db.query(WorkflowHistory).filter(WorkflowHistory.instance_id == inst.id).all()
            gateway_entries = [h for h in history if "compuerta" in h.comment.lower()]
            print("Registros de compuerta en historial:", [h.comment for h in gateway_entries])
            assert len(gateway_entries) > 0
            
            # Complete task A
            print("\n4. Completando 'Tarea Paralela A'...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_a_to_end.id, admin.id, "Finalizado A")
            
            # Verify workflow is still ACTIVE
            assert inst.status == 'ACTIVE'
            tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            print("Tareas activas ahora (esperado: solo B):", [t.node.name for t in tasks])
            assert len(tasks) == 1
            assert tasks[0].node_id == n_para_b.id
            
            # Complete task B
            print("\n5. Completando 'Tarea Paralela B'...")
            inst = WorkflowEngine.execute_transition(db, inst.id, t_b_to_end.id, admin.id, "Finalizado B")
            
            # Verify workflow is now COMPLETED
            print(f"Estado final del flujo: {inst.status} (esperado: COMPLETED)")
            assert inst.status == 'COMPLETED'
            
            print("\n[OK] ¡La prueba de GATEWAY (paralelización automática) finalizó exitosamente!")
            
        except Exception as e:
            print(f"\n[ERROR] Error durante la prueba: {str(e)}")
            raise e
        finally:
            db.rollback()
            print("\nTransacción revertida. Base de datos limpia.")

if __name__ == "__main__":
    run_gateway_test()
