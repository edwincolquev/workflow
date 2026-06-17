import sys
import os

# Adjust path to find modules in workspace
sys.path.append('c:/supply_chain')

from database import get_db
from models import WorkflowProcess, WorkflowNode, WorkflowTransition, WorkflowRole, WorkflowUser
from services.workflow_validator import WorkflowValidatorService

def run_test():
    print("Iniciando pruebas del Validador de Workflows...")
    
    with get_db() as db:
        # Fetch a role to use
        role = db.query(WorkflowRole).first()
        if not role:
            print("Error: No hay roles en la base de datos.")
            return
            
        try:
            # 1. Create a dummy process
            print("\n1. Creando proceso de prueba...")
            proc = WorkflowProcess(name="Proceso Test Validador", description="Para pruebas unitarias", active=False)
            db.add(proc)
            db.flush()
            
            # Test empty process validation
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (Empty):", val)
            assert val["valid"] == False
            assert "El proceso no tiene ningún nodo configurado." in val["errors"]
            
            # 2. Add START node only
            print("\n2. Agregando solo nodo START...")
            node_start = WorkflowNode(process_id=proc.id, name="Inicio", type="START")
            db.add(node_start)
            db.flush()
            
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (Only START):", val)
            assert val["valid"] == False
            assert "El proceso debe tener al menos 1 nodo de tipo END." in val["errors"]
            
            # 3. Add END node
            print("\n3. Agregando nodo END...")
            node_end = WorkflowNode(process_id=proc.id, name="Fin", type="END")
            db.add(node_end)
            db.flush()
            
            # No transitions yet - nodes are orphaned (Fin is not reachable from Inicio, etc.)
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (START + END, no transitions):", val)
            assert val["valid"] == False
            assert any("huérfanos" in err for err in val["errors"])
            
            # 4. Connect START -> END
            print("\n4. Conectando START -> END...")
            t1 = WorkflowTransition(
                process_id=proc.id,
                source_node_id=node_start.id,
                role_id=role.id,
                action_name="Terminar",
                target_node_id=node_end.id
            )
            db.add(t1)
            db.flush()
            
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (Connected START -> END):", val)
            assert val["valid"] == True
            
            # 5. Add a TASK node without incoming/outgoing transitions (orphaned)
            print("\n5. Agregando nodo TASK huérfano...")
            node_task = WorkflowNode(process_id=proc.id, name="Tarea Pendiente", type="TASK")
            db.add(node_task)
            db.flush()
            
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (With orphaned TASK):", val)
            assert val["valid"] == False
            assert any("huérfanos" in err for err in val["errors"])
            
            # Connect it to incoming but no outgoing
            print("\n6. Conectando entrada de TASK pero sin salida...")
            t2 = WorkflowTransition(
                process_id=proc.id,
                source_node_id=node_start.id,
                role_id=role.id,
                action_name="Ir a Tarea",
                target_node_id=node_task.id
            )
            db.add(t2)
            db.flush()
            
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (TASK has entry but no exit):", val)
            assert val["valid"] == False
            # Check for dead end
            assert any("no tiene transiciones salientes definidas" in err or "callejón sin salida" in err for err in val["errors"])
            
            # Connect TASK -> END
            print("\n7. Conectando TASK -> END...")
            t3 = WorkflowTransition(
                process_id=proc.id,
                source_node_id=node_task.id,
                role_id=role.id,
                action_name="Completar Tarea",
                target_node_id=node_end.id
            )
            db.add(t3)
            db.flush()
            
            val = WorkflowValidatorService.validate_process(db, proc.id)
            print("Result (Fully connected flow):", val)
            assert val["valid"] == True
            
            # 8. Test node in-use logic
            print("\n8. Probando lógica de uso de nodos...")
            in_use, msg = WorkflowValidatorService.is_node_in_use(db, node_task.id)
            print(f"Node task in-use? {in_use} - Message: {msg}")
            # Should be True because of the transition dependencies we just added
            assert in_use == True
            assert "regla(s) de transición activa(s)" in msg
            
            print("\n¡Todas las pruebas unitarias pasaron con éxito!")
            
        except Exception as e:
            print(f"\n❌ Falla de aserción o ejecución en la prueba: {str(e)}")
            raise e
        finally:
            # Always rollback transaction to prevent polluting the database
            print("\nDeshaciendo cambios temporales en base de datos...")
            db.rollback()

if __name__ == "__main__":
    run_test()
