import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Avoid exposing credentials in codebase (respecting Rule Global: No Exfiltration of Credentials)
# We look for secrets in Streamlit configurations
def get_sap_connection():
    try:
        import streamlit as st
        if "sap_db" in st.secrets:
            import pyodbc
            conn_str = (
                f"DRIVER={st.secrets.sap_db.get('driver', '{ODBC Driver 17 for SQL Server}')};"
                f"SERVER={st.secrets.sap_db.get('server')};"
                f"DATABASE={st.secrets.sap_db.get('database')};"
                f"UID={st.secrets.sap_db.get('username')};"
                f"PWD={st.secrets.sap_db.get('password')};"
                f"Timeout={st.secrets.sap_db.get('timeout', 5)}"
            )
            return pyodbc.connect(conn_str)
    except Exception as e:
        # Silently log error or handle it gracefully
        pass
    return None

def execute_sap_query(query_path, query_text=None):
    """
    Executes a query against SAP SQL Server. 
    If the connection fails or isn't configured, returns simulated mock data.
    """
    conn = get_sap_connection()
    if conn:
        try:
            if not query_text and os.path.exists(query_path):
                with open(query_path, 'r', encoding='utf-8') as f:
                    query_text = f.read()
            if query_text:
                df = pd.read_sql(query_text, conn)
                conn.close()
                return df, False  # df, is_mock
        except Exception as e:
            # Fallback to mock if SQL Server query fails
            pass
        finally:
            try:
                conn.close()
            except:
                pass
                
    # If connection fails or doesn't exist, generate mock data
    return generate_mock_sap_data(query_path), True

def generate_mock_sap_data(query_path):
    # Determine what mock data to generate based on filename
    basename = os.path.basename(query_path)
    
    if "transitos" in basename:
        return generate_mock_transitos()
    elif "nuevos" in basename:
        return generate_mock_nuevos()
    elif "dashboard" in basename:
        return generate_mock_dashboard()
    else:
        return pd.DataFrame()

def generate_mock_transitos():
    """Generates mock data resembling the output of the transitos.sql query"""
    np.random.seed(42)
    n_records = 30
    
    providers = [
        ('PROV-001', 'Valeo Automotive Spain'),
        ('PROV-002', 'SKF Bearings Europe'),
        ('PROV-003', 'Bosch Global Parts'),
        ('PROV-004', 'Brembo Italy'),
        ('PROV-005', 'Denso Japan')
    ]
    
    fab_map = {
        'PROV-001': 'Valeo',
        'PROV-002': 'SKF',
        'PROV-003': 'Bosch',
        'PROV-004': 'Brembo',
        'PROV-005': 'Denso'
    }
    
    groups = ['Frenos', 'Rodamientos', 'Filtros', 'Encendido', 'Embragues']
    
    data = []
    today = datetime.now().date()
    
    for i in range(n_records):
        prov_code, prov_name = providers[i % len(providers)]
        fab = fab_map[prov_code]
        grp = groups[i % len(groups)]
        doc_num = 10000 + i
        import_name = f"IMP-2026-{i+1:03d}"
        item_code = f"ART-{fab[:3].upper()}-{100 + i}"
        
        # Date math
        tax_date = today - timedelta(days=int(np.random.randint(40, 100)))
        
        # Decide milestones status
        has_oc = i % 10 != 9  # 90% have OC
        has_fact = has_oc and (i % 5 != 4)  # 80% of OCs have invoice
        has_ing = has_fact and (i % 4 == 0) # 25% of fact have ingresado (Completed)
        
        fecha_oc = tax_date + timedelta(days=5) if has_oc else None
        fecha_fact = (fecha_oc + timedelta(days=15)) if (fecha_oc and has_fact) else None
        fecha_ing = (fecha_fact + timedelta(days=20)) if (fecha_fact and has_ing) else None
        
        lead_time_oferta = int(np.random.randint(30, 60))
        lead_time_calc = int(np.random.randint(35, 65))
        
        cant_ofertada = float(np.random.randint(50, 500))
        cant_pendiente_ofertada = 0.0 if has_ing else (cant_ofertada if not has_oc else 0.0)
        
        cant_ordenada = cant_ofertada if has_oc else 0.0
        pendiente_oc = 0.0 if (has_fact or has_ing) else cant_ordenada
        
        cant_facturada = cant_ordenada if has_fact else 0.0
        pendiente_fact = 0.0 if (has_ing or not has_fact) else cant_facturada
        
        cant_ingresada = cant_facturada if has_ing else 0.0
        
        # En transito calculations
        en_transito = cant_pendiente_ofertada + pendiente_oc + pendiente_fact
        price = round(float(np.random.uniform(5.0, 120.0)), 2)
        
        monto_ofertado = round(cant_ofertada * price, 2)
        monto_pendiente_ofertado = round(cant_pendiente_ofertada * price, 2)
        monto_facturado = round(cant_facturada * price, 2)
        
        # Base ETA
        if fecha_oc:
            fecha_est_base = fecha_oc + timedelta(days=lead_time_calc)
        else:
            fecha_est_base = tax_date + timedelta(days=lead_time_oferta)
            
        # Delay calculation
        dias_retraso = (today - fecha_est_base).days
        
        # Estado Flujo & Retraso
        if cant_pendiente_ofertada <= 0 and pendiente_oc <= 0 and pendiente_fact <= 0:
            estado_flujo = 'Completado'
            estado_retraso = 'Completado'
            fecha_est_llegada = fecha_ing
            dias_retraso = 0
        else:
            estado_flujo = 'Pendiente'
            if dias_retraso > 0:
                estado_retraso = 'Retrasado'
                if fecha_oc:
                    fecha_est_llegada = today + timedelta(days=10)
                else:
                    fecha_est_llegada = today + timedelta(days=lead_time_calc)
            else:
                estado_retraso = 'En Tiempo'
                fecha_est_llegada = fecha_est_base
                
        # Etapa funcional
        if estado_flujo == 'Completado':
            etapa = 'Completado'
        elif not has_oc:
            etapa = 'Pendiente OC'
        elif not has_fact:
            etapa = 'En Producción'
        elif has_fact and (pendiente_fact > 0 or en_transito > 0) and (today > fecha_est_base):
            etapa = 'En Tránsito Retrasado'
        elif has_fact and (pendiente_fact > 0 or en_transito > 0):
            etapa = 'En Tránsito'
        else:
            etapa = 'Revisar'
            
        data.append({
            'Código Proveedor': prov_code,
            'Nombre Proveedor': prov_name,
            'Fabricante': fab,
            'Grupo Artículo': grp,
            'DocNum': doc_num,
            'Nombre Importacion (Oferta)': import_name,
            'ItemCode': item_code,
            'Fecha Oferta Compra': tax_date,
            'Fecha Orden Compra': fecha_oc,
            'Fecha Factura': fecha_fact,
            'Fecha Ingreso': fecha_ing,
            'Lead Time Oferta': lead_time_oferta,
            'Lead Time Calc.': lead_time_calc,
            'Cantidad Ofertada': cant_ofertada,
            'Cantidad Pendiente Ofertada': cant_pendiente_ofertada,
            'Cantidad Ordenada': cant_ordenada,
            'Pendiente OC': pendiente_oc,
            'Cantidad Facturada': cant_facturada,
            'Pendiente FACT': pendiente_fact,
            'Cantidad Ingresada': cant_ingresada,
            'En Transito': en_transito,
            'Monto Ofertado USD': monto_ofertado,
            'Monto Pendiente Ofertado USD': monto_pendiente_ofertado,
            'Monto Facturado': monto_facturado,
            'FechaEstimadaBase': fecha_est_base,
            'DiasRetraso': dias_retraso,
            'EstadoFlujo': estado_flujo,
            'EstadoRetraso': estado_retraso,
            'Fecha Estimada de Llegada': fecha_est_llegada,
            'Etapa': etapa
        })
        
    df = pd.DataFrame(data)
    # Sort like in SQL
    df = df.sort_values(by=['Nombre Proveedor', 'Fabricante', 'Fecha Oferta Compra']).reset_index(drop=True)
    return df

def generate_mock_nuevos():
    """Generates mock data for new products (resembling OITM)"""
    np.random.seed(99)
    n_records = 20
    
    brands = ['Valeo', 'SKF', 'Bosch', 'Brembo', 'Denso']
    groups = ['Frenos', 'Rodamientos', 'Filtros', 'Encendido', 'Embragues']
    
    data = []
    today = datetime.now().date()
    
    for i in range(n_records):
        brand = brands[i % len(brands)]
        grp = groups[i % len(groups)]
        item_code = f"NEW-{brand[:3].upper()}-{500 + i}"
        item_name = f"Repuesto Nuevo {brand} Gen-{i+1}"
        
        # Created in last 60 days
        created_date = today - timedelta(days=int(np.random.randint(5, 60)))
        
        # Sales and inventory metrics
        sales_qty = float(np.random.randint(0, 150))
        on_hand = float(np.random.randint(10, 200))
        price = round(float(np.random.uniform(10.0, 150.0)), 2)
        sales_usd = round(sales_qty * price, 2)
        
        # Coverage
        avg_monthly_sales = max(1.0, sales_qty / 2.0)
        coverage = round(on_hand / avg_monthly_sales, 1)
        
        # Classification
        if sales_qty == 0:
            classification = 'Sin movimiento'
        elif sales_qty > 100:
            classification = 'Exitoso'
        else:
            classification = 'Normal'
            
        data.append({
            'ItemCode': item_code,
            'ItemName': item_name,
            'Fabricante': brand,
            'Grupo Artículo': grp,
            'Fecha Creación': created_date,
            'Stock Actual': on_hand,
            'Venta Acumulada Qty': sales_qty,
            'Venta Acumulada USD': sales_usd,
            'Cobertura': coverage,
            'Clasificacion': classification
        })
        
    return pd.DataFrame(data)

def generate_mock_dashboard():
    """Generates high level aggregates for the Executive Dashboard"""
    # Simply returning dictionary-like data that our dashboard logic can use
    # We don't necessarily need a strict df for general dashboard KPIs
    return pd.DataFrame([{
        'Inventario Total': 2450000.00,
        'Capital Inmovilizado': 540000.00,
        'ICI': 74.5,
        'Monto en Transito': 850000.00,
        'Items Quebrados': 145,
        'Capital Discontinuados': 180000.00,
        'Productos Nuevos Activos': 20,
        'Fecha Actualizacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
