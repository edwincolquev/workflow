import os
import pandas as pd
from sqlalchemy.orm import Session
from config.database_sap import execute_sap_query
from models import WorkflowInstance, WorkflowNode, WorkflowTask
from database import get_db

class DataLoaderService:
    @staticmethod
    def get_transitos_with_workflow(db: Session) -> tuple[pd.DataFrame, bool]:
        """
        Loads transit data from SAP B1 (or mocks) and joins it with the active
        workflow instances stored in the local SQLite database.
        Returns:
            df: DataFrame containing combined data.
            is_mock: Boolean indicating if it loaded simulated data.
        """
        # 1. Load data from SAP SQL / Mock
        query_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'queries', 'transitos.sql')
        df_sap, is_mock = execute_sap_query(query_path)
        
        if df_sap.empty:
            return df_sap, is_mock

        # 2. Query active/completed workflow instances in SQLite for 'Importaciones'
        instances = db.query(WorkflowInstance).all()
        
        # Build mapping of DocNum to (instance_id, node_name, status, task_role_id)
        wf_mapping = {}
        for inst in instances:
            if inst.external_ref and inst.external_ref.startswith("DocNum:"):
                try:
                    doc_num = int(inst.external_ref.split(":")[1])
                    current_node_name = inst.current_node.name if inst.current_node else "Desconocido"
                    
                    # Find active task assignment
                    active_task = db.query(WorkflowTask).filter(
                        WorkflowTask.instance_id == inst.id,
                        WorkflowTask.status == 'PENDING'
                    ).first()
                    assigned_role_name = active_task.assigned_role.name if (active_task and active_task.assigned_role) else "Ninguno"
                    
                    wf_mapping[doc_num] = {
                        'instance_id': inst.id,
                        'wf_node': current_node_name,
                        'wf_status': inst.status,
                        'wf_assigned_role': assigned_role_name
                    }
                except ValueError:
                    pass

        # 3. Inject workflow columns into the SAP DataFrame
        df_sap['wf_instance_id'] = df_sap['DocNum'].map(lambda x: wf_mapping[x]['instance_id'] if x in wf_mapping else None)
        df_sap['wf_estado'] = df_sap['DocNum'].map(lambda x: wf_mapping[x]['wf_node'] if x in wf_mapping else "No Iniciado")
        df_sap['wf_status'] = df_sap['DocNum'].map(lambda x: wf_mapping[x]['wf_status'] if x in wf_mapping else None)
        df_sap['wf_rol_asignado'] = df_sap['DocNum'].map(lambda x: wf_mapping[x]['wf_assigned_role'] if x in wf_mapping else "Ninguno")

        return df_sap, is_mock

    @staticmethod
    def get_nuevos_with_workflow(db: Session) -> tuple[pd.DataFrame, bool]:
        """
        Loads new products data from SAP (or mocks) and joins it with the active
        workflow instances in SQLite.
        """
        query_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'queries', 'nuevos.sql')
        df_sap, is_mock = execute_sap_query(query_path)

        if df_sap.empty:
            return df_sap, is_mock

        # Query workflow instances for 'Items Nuevos'
        instances = db.query(WorkflowInstance).all()
        
        wf_mapping = {}
        for inst in instances:
            if inst.external_ref and inst.external_ref.startswith("ItemCode:"):
                item_code = inst.external_ref.split(":")[1]
                current_node_name = inst.current_node.name if inst.current_node else "Desconocido"
                
                active_task = db.query(WorkflowTask).filter(
                    WorkflowTask.instance_id == inst.id,
                    WorkflowTask.status == 'PENDING'
                ).first()
                assigned_role_name = active_task.assigned_role.name if (active_task and active_task.assigned_role) else "Ninguno"
                
                wf_mapping[item_code] = {
                    'instance_id': inst.id,
                    'wf_node': current_node_name,
                    'wf_status': inst.status,
                    'wf_assigned_role': assigned_role_name
                }

        df_sap['wf_instance_id'] = df_sap['ItemCode'].map(lambda x: wf_mapping[x]['instance_id'] if x in wf_mapping else None)
        df_sap['wf_estado'] = df_sap['ItemCode'].map(lambda x: wf_mapping[x]['wf_node'] if x in wf_mapping else "No Iniciado")
        df_sap['wf_status'] = df_sap['ItemCode'].map(lambda x: wf_mapping[x]['wf_status'] if x in wf_mapping else None)
        df_sap['wf_rol_asignado'] = df_sap['ItemCode'].map(lambda x: wf_mapping[x]['wf_assigned_role'] if x in wf_mapping else "Ninguno")

        return df_sap, is_mock
