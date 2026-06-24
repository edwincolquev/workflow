import os
import pandas as pd
from datetime import datetime
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

    @staticmethod
    def get_sap_document_details(db: Session, doc_num: str) -> pd.DataFrame:
        """
        Queries SAP B1 for lines of a document matching DocNum (PO or PQ).
        Returns a DataFrame with document lines, falling back to mock lines if no SAP database.
        """
        try:
            doc_num_val = int(str(doc_num).strip())
        except ValueError:
            return pd.DataFrame()

        # Try Purchase Orders first
        po_query = f"""
        SELECT 
            T0.DocNum AS [Número SAP],
            T0.CardCode AS [Código Proveedor],
            T0.CardName AS [Nombre Proveedor],
            T0.TaxDate AS [Fecha Contabilización],
            T0.DocStatus AS [Estado Documento],
            T0.DocTotal AS [Monto Total USD],
            T1.ItemCode AS [Código Artículo],
            T1.Dscription AS [Descripción],
            T1.Quantity AS [Cantidad Solicitada],
            T1.OpenQty AS [Cantidad Pendiente],
            T1.Price AS [Precio Unitario]
        FROM OPOR T0
        INNER JOIN POR1 T1 ON T0.DocEntry = T1.DocEntry
        WHERE T0.DocNum = {doc_num_val}
        """
        
        df_sap, is_mock = execute_sap_query(query_path="", query_text=po_query)
        
        # If real DB returned nothing, try Purchase Quotations
        if not is_mock and df_sap.empty:
            pq_query = f"""
            SELECT 
                T0.DocNum AS [Número SAP],
                T0.CardCode AS [Código Proveedor],
                T0.CardName AS [Nombre Proveedor],
                T0.TaxDate AS [Fecha Contabilización],
                T0.DocStatus AS [Estado Documento],
                T0.DocTotal AS [Monto Total USD],
                T1.ItemCode AS [Código Artículo],
                T1.Dscription AS [Descripción],
                T1.Quantity AS [Cantidad Solicitada],
                T1.OpenQty AS [Cantidad Pendiente],
                T1.Price AS [Precio Unitario]
            FROM OPQT T0
            INNER JOIN PQT1 T1 ON T0.DocEntry = T1.DocEntry
            WHERE T0.DocNum = {doc_num_val}
            """
            df_sap, is_mock = execute_sap_query(query_path="", query_text=pq_query)

        # If it's a mock result, generate specific mock document detail lines for that DocNum
        if is_mock or df_sap.empty:
            # Let's generate nice mock data
            # Determine mock provider/fabricante based on doc_num to match the dashboard/transit mocks
            np_seed = doc_num_val % 5
            providers = [
                ('PROV-001', 'Valeo Automotive Spain', 'Valeo'),
                ('PROV-002', 'SKF Bearings Europe', 'SKF'),
                ('PROV-003', 'Bosch Global Parts', 'Bosch'),
                ('PROV-004', 'Brembo Italy', 'Brembo'),
                ('PROV-005', 'Denso Japan', 'Denso')
            ]
            prov_code, prov_name, fab = providers[np_seed]
            
            # Generate 3 items
            descriptions = {
                'Valeo': ['Kit de Embrague Completo', 'Pastillas de Freno Delanteras', 'Disco de Freno Ventilado'],
                'SKF': ['Rodamiento de Rueda Delantera', 'Cojinete de Empuje', 'Retén de Cigüeñal'],
                'Bosch': ['Filtro de Aceite Premium', 'Bujía de Encendido Iridium', 'Filtro de Aire Motor'],
                'Brembo': ['Calipers de Freno Sport', 'Disco de Freno Cerámico', 'Líquido de Freno DOT 4'],
                'Denso': ['Alternador de Alta Capacidad', 'Bujía Incandescente Diésel', 'Compresor Aire Acondicionado']
            }
            
            node_items = descriptions.get(fab, ['Repuesto Genérico A', 'Repuesto Genérico B', 'Repuesto Genérico C'])
            prices = [120.50, 45.90, 85.00]
            quantities = [100.0, 250.0, 150.0]
            
            doc_total = sum(q * p for q, p in zip(quantities, prices))
            
            mock_lines = []
            for idx, item_desc in enumerate(node_items):
                mock_lines.append({
                    'Número SAP': doc_num_val,
                    'Código Proveedor': prov_code,
                    'Nombre Proveedor': prov_name,
                    'Fecha Contabilización': datetime.now().date(),
                    'Estado Documento': 'O' if idx % 2 == 0 else 'C', # Open / Closed
                    'Monto Total USD': doc_total,
                    'Código Artículo': f"ART-{fab[:3].upper()}-{100 + idx}",
                    'Descripción': item_desc,
                    'Cantidad Solicitada': quantities[idx],
                    'Cantidad Pendiente': quantities[idx] if idx % 2 == 0 else 0.0,
                    'Precio Unitario': prices[idx]
                })
            df_sap = pd.DataFrame(mock_lines)
            
        return df_sap
