import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from database import get_db
from models import WorkflowInstance, WorkflowTask, WorkflowNode, WorkflowRole, WorkflowProcess, WorkflowObjective, WorkflowBrand
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS

# 1. Access Control
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

user_role = st.session_state.user['role']
if not ROLE_ACCESS.get(user_role, {}).get('dashboard', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Render content inside database context
with get_db() as db:
    # Query live records
    instances = db.query(WorkflowInstance).all()
    tasks = db.query(WorkflowTask).all()
    roles = db.query(WorkflowRole).all()
    processes = db.query(WorkflowProcess).filter(WorkflowProcess.active == True).all()
    objectives = db.query(WorkflowObjective).all()
    
    # Check if we have active/completed instances in SQLite to decide if we show real or simulated stats
    has_real_data = len(instances) > 0 and any(i.status == 'COMPLETED' for i in instances)
    
    # Fetch active brands and BUs
    all_brands = db.query(WorkflowBrand).filter(WorkflowBrand.active == True).all()
    
    active_process_ids = {p.id for p in processes}
    
    # Prepare standard instances dataset
    instances_data = []
    
    if has_real_data:
        for inst in instances:
            if inst.process_id not in active_process_ids:
                continue
            instances_data.append({
                'id': inst.id,
                'internal_code': inst.internal_code or f'#{inst.id}',
                'title': inst.title,
                'status': inst.status,
                'created_at': inst.created_at,
                'updated_at': inst.updated_at,
                'process_id': inst.process_id,
                'process_name': inst.process.name if inst.process else "Desconocido",
                'brand_name': inst.brand.name if inst.brand else "Sin Clasificar",
                'u_negocio': inst.brand.u_negocio if inst.brand else "Sin Clasificar",
                'leadtime': inst.brand.leadtime if inst.brand else 0,
                'current_node_name': inst.current_node.name if inst.current_node else 'Finalizado'
            })
    else:
        # Fallback/Demo Simulated Data (Matching the layout/volumes/deviations from photo)
        import random
        random.seed(42)
        
        sim_brands = [
            {"name": "MITSUBOSHI", "u_negocio": "C-MOVIL", "leadtime": 252},
            {"name": "MARILIA", "u_negocio": "C-MOVIL", "leadtime": 90},
            {"name": "NGK", "u_negocio": "C-MOVIL", "leadtime": 150},
            {"name": "MRK", "u_negocio": "C-MOVIL", "leadtime": 210},
            {"name": "WEGA", "u_negocio": "C-MOVIL", "leadtime": 65},
            {"name": "FRASLE", "u_negocio": "NOVAPARTES", "leadtime": 120},
            {"name": "CTR", "u_negocio": "NOVAPARTES", "leadtime": 195},
            {"name": "3M", "u_negocio": "C-MOVIL", "leadtime": 28},
            {"name": "Sin Clasificar", "u_negocio": "Sin Clasificar", "leadtime": 0}
        ]
        
        brand_volumes = {
            "MITSUBOSHI": (7, 10), # (active, completed)
            "MARILIA": (5, 4),
            "Sin Clasificar": (3, 4),
            "NGK": (2, 2),
            "MRK": (1, 0),
            "WEGA": (0, 1),
            "3M": (4, 12),
            "FRASLE": (5, 15),
            "CTR": (2, 8)
        }
        
        inst_id = 1
        now = datetime.now()
        
        for brand_name, (act, comp) in brand_volumes.items():
            brand_info = next(b for b in sim_brands if b["name"] == brand_name)
            
            # Active instances
            for i in range(act):
                created_days_ago = random.randint(10, 150)
                created_at = now - timedelta(days=created_days_ago)
                instances_data.append({
                    'id': inst_id,
                    'internal_code': f'IMP-2026-{inst_id:03d}',
                    'title': f'Importación {brand_name} Lote {i+1}',
                    'status': 'ACTIVE',
                    'created_at': created_at,
                    'updated_at': now,
                    'process_id': 1,
                    'process_name': 'Importaciones',
                    'brand_name': brand_name,
                    'u_negocio': brand_info["u_negocio"],
                    'leadtime': brand_info["leadtime"],
                    'current_node_name': random.choice(['Viaje Marítimo', 'Aduana', 'Transporte Local'])
                })
                inst_id += 1
                
            # Completed instances
            for i in range(comp):
                ref_lt = brand_info["leadtime"] if brand_info["leadtime"] > 0 else 30
                if brand_name == "WEGA":
                    cycle_days = ref_lt + 3.2
                elif brand_name == "3M":
                    cycle_days = ref_lt - 3.5
                elif brand_name == "FRASLE":
                    cycle_days = ref_lt - 5.0
                else:
                    cycle_days = ref_lt + random.uniform(-10, 15)
                
                cycle_days = max(1.0, cycle_days)
                created_days_ago = random.randint(int(cycle_days) + 2, 200)
                created_at = now - timedelta(days=created_days_ago)
                completed_at = created_at + timedelta(days=cycle_days)
                
                instances_data.append({
                    'id': inst_id,
                    'internal_code': f'IMP-2026-{inst_id:03d}',
                    'title': f'Importación {brand_name} Lote {comp+i+1}',
                    'status': 'COMPLETED',
                    'created_at': created_at,
                    'updated_at': completed_at,
                    'process_id': 1,
                    'process_name': 'Importaciones',
                    'brand_name': brand_name,
                    'u_negocio': brand_info["u_negocio"],
                    'leadtime': brand_info["leadtime"],
                    'current_node_name': 'Ingresado'
                })
                inst_id += 1

    # Extract dynamic filters options
    filter_bu_list = sorted(list(set(i['u_negocio'] for i in instances_data if i['u_negocio'] != "Sin Clasificar")))
    
    # ─── 1ro. KPIs CONTENEDOR PRINCIPAL (RESERVADO AL TOPE) ───────────────────
    kpi_container = st.container()

    # ─── 2do. FILTROS OPERATIVOS ──────────────────────────────────────────────
    st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        process_names = sorted(list(set(i['process_name'] for i in instances_data)))
        process_options = ["Todos los Procesos"] + process_names
        selected_process_name = st.selectbox(
            "🔍 Proceso:", 
            process_options,
            index=0,
            key="dash_filter_process"
        )
        
    with col_f2:
        bu_options = ["Todas las Unidades"] + filter_bu_list
        selected_bu = st.selectbox(
            "🏢 Unidad de Negocio / Categoría:",
            bu_options,
            index=0,
            key="dash_filter_bu"
        )
        
    with col_f3:
        # Filter brands list based on selected BU
        if selected_bu != "Todas las Unidades":
            filtered_brands = sorted(list(set(i['brand_name'] for i in instances_data if i['u_negocio'] == selected_bu)))
        else:
            filtered_brands = sorted(list(set(i['brand_name'] for i in instances_data)))
        brand_options = ["Todas las Marcas"] + filtered_brands
        selected_brand_name = st.selectbox(
            "🏷️ Marca:",
            brand_options,
            index=0,
            key="dash_filter_brand"
        )

    # ─── FILTRAR DATASET SEGÚN FILTROS SELECCIONADOS ─────────────────────────
    instances_filtered = instances_data
    if selected_process_name != "Todos los Procesos":
        instances_filtered = [i for i in instances_filtered if i['process_name'] == selected_process_name]
    if selected_bu != "Todas las Unidades":
        instances_filtered = [i for i in instances_filtered if i['u_negocio'] == selected_bu]
    if selected_brand_name != "Todas las Marcas":
        instances_filtered = [i for i in instances_filtered if i['brand_name'] == selected_brand_name]

    # Calcular Métricas y KPIs
    active_count = sum(1 for i in instances_filtered if i['status'] == 'ACTIVE')
    completed_instances = [i for i in instances_filtered if i['status'] == 'COMPLETED']
    completed_count = len(completed_instances)
    
    # Ciclo promedio (días)
    durations_days = [(inst['updated_at'] - inst['created_at']).total_seconds() / 86400.0 for inst in completed_instances]
    avg_days = sum(durations_days) / len(durations_days) if durations_days else 0.0
    
    # Cumplimiento SLA
    if has_real_data:
        filtered_instance_ids = {i['id'] for i in instances_filtered}
        tasks_filtered = [t for t in tasks if t.instance_id in filtered_instance_ids]
        completed_tasks = [t for t in tasks_filtered if t.status == 'COMPLETED' and t.completed_at and t.created_at]
        tasks_with_sla = [t for t in completed_tasks if t.sla_hours]
        
        sla_compliant_count = 0
        for t in tasks_with_sla:
            task_duration = (t.completed_at - t.created_at).total_seconds() / 3600
            if task_duration <= t.sla_hours * 24:
                sla_compliant_count += 1
        sla_compliance_pct = (sla_compliant_count / len(tasks_with_sla) * 100) if tasks_with_sla else 100.0
    else:
        sla_compliance_pct = 91.8
        
    # Peor Desviación de Marca para Foco de Mejora Continua
    brand_perf = {}
    for inst in completed_instances:
        b_name = inst['brand_name']
        if b_name == "Sin Clasificar":
            continue
        if b_name not in brand_perf:
            brand_perf[b_name] = {
                'durations': [],
                'leadtime': inst['leadtime']
            }
        dur_days = (inst['updated_at'] - inst['created_at']).total_seconds() / 86400.0
        brand_perf[b_name]['durations'].append(dur_days)
        
    worst_brand = "N/A"
    worst_deviation = 0.0
    for b_name, data in brand_perf.items():
        avg_real = sum(data['durations']) / len(data['durations'])
        ref = data['leadtime']
        if ref > 0:
            diff = avg_real - ref
            if diff > worst_deviation:
                worst_deviation = diff
                worst_brand = b_name
                
    brand_foc_text = f"{worst_brand} (+{worst_deviation:.1f}d)" if worst_deviation > 0 else "Ninguna (En Tiempo)"

    # Renderizar KPIs al tope de la página
    with kpi_container:
        st.markdown("""
        <style>
            /* Eliminar márgenes excesivos en la parte superior */
            .element-container:has(div.kpi-container-mark) {
                margin-top: -30px !important;
            }
        </style>
        <div class="kpi-container-mark"></div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            UIHelpers.render_kpi_card(
                title="Flujos Activos", 
                value=f"{active_count} ítems", 
                status="blue" if active_count > 0 else "gray",
                trend="Monitoreo activo"
            )
        with c2:
            UIHelpers.render_kpi_card(
                title="Flujos Finalizados", 
                value=f"{completed_count} ítems", 
                status="green",
                trend=f"+{int(completed_count*0.12)} este mes"
            )
        with c3:
            UIHelpers.render_kpi_card(
                title="Ciclo Promedio", 
                value=f"{avg_days:.1f} días", 
                status="green" if avg_days < 90 else "yellow",
                trend="Inicio a Fin de flujo"
            )
        with c4:
            UIHelpers.render_kpi_card(
                title="Cumplimiento SLA", 
                value=f"{sla_compliance_pct:.1f}%", 
                status="green" if sla_compliance_pct >= 90 else "red",
                trend="Meta operativa 90%"
            )
        with c5:
            UIHelpers.render_kpi_card(
                title="Foco de Mejora", 
                value=brand_foc_text, 
                status="red" if worst_deviation > 0 else "green",
                trend="Peor desviación (Marca)"
            )

    # ─── 3ro. VOLÚMENES POR UNIDAD DE NEGOCIO Y TOP 10 MARCAS (APILADAS) ──────
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
    c_bu, c_brand = st.columns(2)
    
    with c_bu:
        st.markdown("<div class='section-header'>🏢 Volumen de Procesos por Unidad de Negocio</div>", unsafe_allow_html=True)
        bu_status_counts = {}
        for inst in instances_filtered:
            bu = inst['u_negocio']
            status = 'Abiertas' if inst['status'] == 'ACTIVE' else 'Completadas'
            if bu not in bu_status_counts:
                bu_status_counts[bu] = {'Abiertas': 0, 'Completadas': 0}
            bu_status_counts[bu][status] += 1
            
        if not bu_status_counts:
            st.info("No hay datos por Unidad de Negocio para este filtro.")
        else:
            bu_rows = []
            for bu, counts in bu_status_counts.items():
                bu_rows.append({'Unidad de Negocio': bu, 'Estado': 'Abiertas', 'Cantidad': counts['Abiertas']})
                bu_rows.append({'Unidad de Negocio': bu, 'Estado': 'Completadas', 'Cantidad': counts['Completadas']})
            df_bu = pd.DataFrame(bu_rows)
            
            fig_bu = px.bar(
                df_bu,
                x='Unidad de Negocio',
                y='Cantidad',
                color='Estado',
                barmode='stack',
                color_discrete_map={'Completadas': '#1e3a8a', 'Abiertas': '#bae6fd'},
                category_orders={"Estado": ["Completadas", "Abiertas"]}
            )
            fig_bu.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=25, b=20),
                height=320,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
            )
            # Add totals on top
            totals_bu = df_bu.groupby('Unidad de Negocio')['Cantidad'].sum().reset_index()
            for _, row in totals_bu.iterrows():
                fig_bu.add_annotation(
                    x=row['Unidad de Negocio'],
                    y=row['Cantidad'],
                    text=str(int(row['Cantidad'])),
                    showarrow=False,
                    yshift=10,
                    font=dict(size=11, color='#1e293b', family='Outfit', weight='bold')
                )
            st.plotly_chart(fig_bu, use_container_width=True)
            
    with c_brand:
        st.markdown("<div class='section-header'>🏷️ Top 10 Marcas por Volumen de Procesos</div>", unsafe_allow_html=True)
        brand_status_counts = {}
        for inst in instances_filtered:
            brand = inst['brand_name']
            status = 'Abiertas' if inst['status'] == 'ACTIVE' else 'Completadas'
            if brand not in brand_status_counts:
                brand_status_counts[brand] = {'Abiertas': 0, 'Completadas': 0, 'Total': 0}
            brand_status_counts[brand][status] += 1
            brand_status_counts[brand]['Total'] += 1
            
        if not brand_status_counts:
            st.info("No hay datos por Marca para este filtro.")
        else:
            sorted_brands = sorted(brand_status_counts.items(), key=lambda x: x[1]['Total'], reverse=True)[:10]
            brand_rows = []
            for brand, counts in sorted_brands:
                brand_rows.append({'Marca': brand, 'Estado': 'Abiertas', 'Cantidad': counts['Abiertas']})
                brand_rows.append({'Marca': brand, 'Estado': 'Completadas', 'Cantidad': counts['Completadas']})
            df_brand = pd.DataFrame(brand_rows)
            
            fig_brand = px.bar(
                df_brand,
                x='Marca',
                y='Cantidad',
                color='Estado',
                barmode='stack',
                color_discrete_map={'Completadas': '#1e3a8a', 'Abiertas': '#fed7aa'},
                category_orders={"Estado": ["Completadas", "Abiertas"]}
            )
            fig_brand.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=25, b=20),
                height=320,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
            )
            # Add totals on top
            totals_brand = df_brand.groupby('Marca')['Cantidad'].sum().reset_index()
            for _, row in totals_brand.iterrows():
                fig_brand.add_annotation(
                    x=row['Marca'],
                    y=row['Cantidad'],
                    text=str(int(row['Cantidad'])),
                    showarrow=False,
                    yshift=10,
                    font=dict(size=11, color='#1e293b', family='Outfit', weight='bold')
                )
            st.plotly_chart(fig_brand, use_container_width=True)

    # ─── 4to. COMPARATIVA DE TIEMPOS DE CICLO VS LEADTIME POR MARCA ───────────
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>⏱️ Comparativa de Tiempos de Ciclo vs Leadtime de Referencia por Marca</div>", unsafe_allow_html=True)
    
    brand_comparison = {}
    for inst in instances_filtered:
        b_name = inst['brand_name']
        if b_name not in brand_comparison:
            brand_comparison[b_name] = {
                "name": b_name,
                "u_negocio": inst["u_negocio"],
                "ref_leadtime": inst["leadtime"],
                "iniciados": 0,
                "abiertos": 0,
                "finalizados": 0,
                "durations": []
            }
        
        brand_comparison[b_name]["iniciados"] += 1
        if inst["status"] == "ACTIVE":
            brand_comparison[b_name]["abiertos"] += 1
        elif inst["status"] == "COMPLETED":
            brand_comparison[b_name]["finalizados"] += 1
            dur_days = (inst['updated_at'] - inst['created_at']).total_seconds() / 86400.0
            brand_comparison[b_name]["durations"].append(dur_days)
            
    comparison_rows = []
    for b_name, data in brand_comparison.items():
        avg_real = sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0.0
        ref = data["ref_leadtime"]
        diff = avg_real - ref if ref > 0 and avg_real > 0 else 0.0
        
        if ref == 0:
            status_str = "➖ N/A"
        elif diff > 0:
            status_str = f"⚠️ Excedido (+{diff:.1f}d)"
        else:
            status_str = f"✅ En Tiempo ({diff:.1f}d)"
            
        comparison_rows.append({
            "Marca": b_name,
            "Unidad de Negocio": data["u_negocio"],
            "Iniciados": data["iniciados"],
            "Finalizados": data["finalizados"],
            "Abiertos": data["abiertos"],
            "Ciclo Promedio Real (Días)": round(avg_real, 1) if avg_real > 0 else 0.0,
            "Leadtime de Referencia (Días)": ref,
            "Desviación (Días)": round(diff, 1) if ref > 0 and avg_real > 0 else 0.0,
            "Estado": status_str
        })
        
    if not comparison_rows:
        st.info("No hay flujos con marcas asociadas para mostrar la comparación de leadtime.")
    else:
        df_comparison = pd.DataFrame(comparison_rows)
        df_comparison = df_comparison.sort_values(by="Desviación (Días)", ascending=False)
        st.dataframe(
            df_comparison.style.format({
                "Ciclo Promedio Real (Días)": "{:.1f}",
                "Desviación (Días)": "{:.1f}"
            }).set_properties(**{
                'background-color': 'white',
                'color': '#334155',
                'border-color': '#e2e8f0'
            }),
            use_container_width=True,
            hide_index=True
        )

    # ─── 5to. FLUJOS ACTIVOS CON RETRASO CRÍTICO (VENCIMIENTO DE SLA) ──────────
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>🚨 Flujos Activos con Retraso Crítico (Vencimiento de SLA)</div>", unsafe_allow_html=True)
    
    if has_real_data:
        delayed_instances_list = []
        active_instances = [i for i in instances_filtered if i['status'] == 'ACTIVE']
        for inst_data in active_instances:
            inst = db.query(WorkflowInstance).filter(WorkflowInstance.id == inst_data['id']).first()
            if not inst:
                continue
            elapsed_h = (datetime.utcnow() - inst.created_at).total_seconds() / 3600
            total_sla_hours = sum(n.sla_hours for n in inst.process.nodes if n.type in ['TASK', 'DECISION'] and n.sla_hours) * 24
            
            ptasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id == inst.id, WorkflowTask.status == 'PENDING').all()
            any_task_delayed = False
            max_task_delay = 0.0
            delayed_stage_name = ""
            assigned_role_name = ""
            
            for pt in ptasks:
                if pt.sla_hours and pt.created_at:
                    pt_elapsed = (datetime.utcnow() - pt.created_at).total_seconds() / 3600
                    if pt_elapsed > pt.sla_hours * 24:
                        any_task_delayed = True
                        task_delay = pt_elapsed - (pt.sla_hours * 24.0)
                        if task_delay > max_task_delay:
                            max_task_delay = task_delay
                            delayed_stage_name = pt.node.name
                            assigned_role_name = pt.assigned_role.name if pt.assigned_role else "Sin Rol"
            
            is_overdue = False
            delay_h = 0.0
            reason = ""
            
            if total_sla_hours > 0 and elapsed_h > total_sla_hours:
                is_overdue = True
                delay_h = elapsed_h - total_sla_hours
                reason = "Proceso completo fuera de SLA"
                
            if any_task_delayed:
                is_overdue = True
                if max_task_delay > delay_h:
                    delay_h = max_task_delay
                    reason = f"Etapa '{delayed_stage_name}' vencida"
            
            if is_overdue:
                delayed_instances_list.append({
                    'Código': inst.internal_code or f'#{inst.id}',
                    'Título': inst.title,
                    'Proceso': inst.process.name,
                    'Etapa Actual': inst.current_node.name if inst.current_node else 'N/A',
                    'Rol Asignado': assigned_role_name or (inst.current_node.role.name if inst.current_node and inst.current_node.role else 'Sin Rol'),
                    'Días Transcurridos': round(elapsed_h / 24.0, 1),
                    'Retraso (Días)': round(delay_h / 24.0, 1),
                    'Detalle': reason,
                    'Marca': inst_data['brand_name'],
                    'u_negocio': inst_data['u_negocio']
                })
        df_delayed_instances = pd.DataFrame(delayed_instances_list)
        if not df_delayed_instances.empty:
            df_delayed_instances = df_delayed_instances.drop(columns=['Marca', 'u_negocio'])
    else:
        sim_delayed = [
            {'Código': 'IMP-2026-004', 'Título': 'Importación Hyundai Repuestos', 'Proceso': 'Importaciones', 'Etapa Actual': 'Aduana', 'Rol Asignado': 'Logística', 'Días Transcurridos': 4.0, 'Retraso (Días)': 2.0, 'Detalle': 'Etapa Aduana excedió SLA de 48h', 'Marca': 'MITSUBOSHI', 'u_negocio': 'C-MOVIL'},
            {'Código': 'ITM-2026-012', 'Título': 'Homologación Neumáticos Premium', 'Proceso': 'Items Nuevos', 'Etapa Actual': 'Homologación', 'Rol Asignado': 'Logística', 'Días Transcurridos': 3.0, 'Retraso (Días)': 1.5, 'Detalle': 'Etapa Homologación excedió SLA de 36h', 'Marca': 'MARILIA', 'u_negocio': 'C-MOVIL'},
            {'Código': 'IMP-2026-009', 'Título': 'Tránsito Filtros de Aire', 'Proceso': 'Importaciones', 'Etapa Actual': 'Viaje Marítimo', 'Rol Asignado': 'Importaciones', 'Días Transcurridos': 6.7, 'Retraso (Días)': 1.7, 'Detalle': 'Viaje excedió SLA total', 'Marca': 'WEGA', 'u_negocio': 'C-MOVIL'}
        ]
        if selected_process_name != "Todos los Procesos":
            sim_delayed = [s for s in sim_delayed if s['Proceso'] == selected_process_name]
        if selected_bu != "Todas las Unidades":
            sim_delayed = [s for s in sim_delayed if s['u_negocio'] == selected_bu]
        if selected_brand_name != "Todas las Marcas":
            sim_delayed = [s for s in sim_delayed if s['Marca'] == selected_brand_name]
            
        df_delayed_instances = pd.DataFrame(sim_delayed)
        if not df_delayed_instances.empty:
            df_delayed_instances = df_delayed_instances.drop(columns=['Marca', 'u_negocio'])
            
    if df_delayed_instances.empty:
        st.success("🎉 ¡Excelente! No se registran flujos activos con retrasos ni SLA vencidos para esta selección.")
    else:
        st.dataframe(
            df_delayed_instances.style.set_properties(**{
                'background-color': '#fff5f5',
                'color': '#742a2a',
                'border-color': '#fed7d7'
            }),
            use_container_width=True,
            hide_index=True
        )

    # ─── 6to. SEMÁFORO DE TAREAS ACTIVAS Y TIEMPOS DE CICLO POR ETAPA ──────────
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
    c_bottleneck_left, c_bottleneck_right = st.columns([1.2, 0.8])
    
    if has_real_data:
        filtered_instance_ids = {i['id'] for i in instances_filtered}
        active_tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id.in_(filtered_instance_ids), WorkflowTask.status == 'PENDING').all()
        on_time_active = 0
        delayed_active = 0
        for at in active_tasks:
            elapsed_h = (datetime.utcnow() - at.created_at).total_seconds() / 3600
            if at.sla_hours and elapsed_h > at.sla_hours * 24:
                delayed_active += 1
            else:
                on_time_active += 1
                
        completed_tasks = db.query(WorkflowTask).filter(WorkflowTask.instance_id.in_(filtered_instance_ids), WorkflowTask.status == 'COMPLETED').all()
        node_durations = {}
        node_counts = {}
        for t in completed_tasks:
            if t.completed_at and t.created_at:
                node_name = t.node.name
                task_duration = (t.completed_at - t.created_at).total_seconds() / 3600
                node_durations[node_name] = node_durations.get(node_name, 0.0) + task_duration
                node_counts[node_name] = node_counts.get(node_name, 0) + 1
                
        node_cycle_times = []
        for name in node_durations:
            node_cycle_times.append({
                'Etapa': name,
                'Horas Promedio': round(node_durations[name] / node_counts[name], 1)
            })
        df_bottlenecks = pd.DataFrame(node_cycle_times) if node_cycle_times else pd.DataFrame(columns=['Etapa', 'Horas Promedio'])
    else:
        on_time_active = 19
        delayed_active = 3
        df_bottlenecks = pd.DataFrame({
            'Etapa': ['Validación de Stock', 'Emisión de OC SAP', 'Aduana & Tránsito', 'Inspección de Calidad', 'Homologación de Ficha', 'Preparación Catálogo'],
            'Horas Promedio': [12.4, 24.8, 72.2, 18.5, 36.1, 8.4]
        })
        
    with c_bottleneck_left:
        st.markdown("<div class='section-header'>⏱️ Tiempos de Ciclo por Etapa (Cuellos de Botella)</div>", unsafe_allow_html=True)
        if df_bottlenecks.empty:
            st.info("No hay datos de tiempo de ciclo disponibles.")
        else:
            df_bottlenecks_sorted = df_bottlenecks.sort_values(by='Horas Promedio', ascending=True)
            fig_bottlenecks = px.bar(
                df_bottlenecks_sorted,
                x='Horas Promedio',
                y='Etapa',
                orientation='h',
                color='Horas Promedio',
                color_continuous_scale=px.colors.sequential.Oranges,
                text='Horas Promedio',
                labels={'Horas Promedio': 'Horas Promedio'}
            )
            fig_bottlenecks.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=10, b=20),
                coloraxis_showscale=False,
                height=300
            )
            fig_bottlenecks.update_traces(textposition='outside')
            st.plotly_chart(fig_bottlenecks, use_container_width=True)
            
    with c_bottleneck_right:
        st.markdown("<div class='section-header'>🚨 Semáforo de Tareas Activas</div>", unsafe_allow_html=True)
        total_active_tasks = on_time_active + delayed_active
        if total_active_tasks == 0:
            st.info("No hay tareas activas ejecutándose.")
        else:
            df_status = pd.DataFrame({
                'Estado': ['En Tiempo', 'SLA Vencido'],
                'Cantidad': [on_time_active, delayed_active]
            })
            fig_status = px.pie(
                df_status,
                names='Estado',
                values='Cantidad',
                color='Estado',
                color_discrete_map={'En Tiempo': '#10b981', 'SLA Vencido': '#ef4444'},
                hole=0.4
            )
            fig_status.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=10, b=20),
                height=250,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_status, use_container_width=True)

    # ─── 7mo. RENDIMIENTO Y SLAS POR TIPO DE PROCESO ──────────────────────────
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
    if selected_process_name == "Todos los Procesos":
        st.markdown("<div class='section-header'>📋 Rendimiento y SLAs por Tipo de Proceso</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='section-header'>📋 Desglose de SLAs por Etapa: {selected_process_name}</div>", unsafe_allow_html=True)
        
    if has_real_data:
        if selected_process_name == "Todos los Procesos":
            proc_perf = []
            for proc in processes:
                proc_insts = [i for i in instances_filtered if i['process_id'] == proc.id]
                total_run = len(proc_insts)
                proc_completed = [i for i in proc_insts if i['status'] == 'COMPLETED']
                
                proc_durs = [(i['updated_at'] - i['created_at']).total_seconds() / 3600 for i in proc_completed]
                proc_avg_h = sum(proc_durs) / len(proc_durs) if proc_durs else 0.0
                
                proc_task_records = [t for t in tasks if t.instance.process_id == proc.id and t.status == 'COMPLETED' and t.completed_at and t.created_at and t.sla_hours]
                proc_compliant = sum(1 for t in proc_task_records if ((t.completed_at - t.created_at).total_seconds() / 3600) <= t.sla_hours * 24)
                proc_sla_pct = (proc_compliant / len(proc_task_records) * 100) if proc_task_records else 100.0
                
                proc_perf.append({
                    'Proceso': proc.name,
                    'Iniciados': total_run,
                    'Finalizados': len(proc_completed),
                    'Duración Prom. (días)': round(proc_avg_h / 24, 1) if proc_avg_h > 0 else 0.0,
                    'Cumplimiento SLA': f"{proc_sla_pct:.1f}%"
                })
            df_proc_perf = pd.DataFrame(proc_perf)
        else:
            selected_proc = next((p for p in processes if p.name == selected_process_name), None)
            stage_perf = []
            if selected_proc:
                proc_nodes = [n for n in selected_proc.nodes if n.type not in ['START', 'END']]
                for node in proc_nodes:
                    node_tasks = [t for t in tasks if t.node_id == node.id and t.status == 'COMPLETED' and t.completed_at and t.created_at]
                    node_compliant = sum(1 for t in node_tasks if t.sla_hours and ((t.completed_at - t.completed_at).total_seconds() / 3600) <= t.sla_hours * 24)
                    node_sla_pct = (node_compliant / len(node_tasks) * 100) if node_tasks else 100.0
                    
                    stage_perf.append({
                        'Etapa': node.name,
                        'Rol Asignado': node.role.name if node.role else 'Sin Rol',
                        'Tareas Completadas': len(node_tasks),
                        'SLA Configurado (días)': f"{node.sla_hours}d" if node.sla_hours else "Sin SLA",
                        'Cumplimiento SLA': f"{node_sla_pct:.1f}%" if node.sla_hours else "N/A"
                    })
            df_proc_perf = pd.DataFrame(stage_perf)
    else:
        if selected_process_name == "Todos los Procesos":
            df_proc_perf = pd.DataFrame([
                {'Proceso': 'Importaciones', 'Iniciados': 65, 'Finalizados': 52, 'Duración Prom. (días)': 4.8, 'Cumplimiento SLA': '89.5%'},
                {'Proceso': 'Items Nuevos', 'Iniciados': 38, 'Finalizados': 35, 'Duración Prom. (días)': 3.1, 'Cumplimiento SLA': '95.2%'}
            ])
        else:
            df_proc_perf = pd.DataFrame([
                {'Etapa': 'OC Emitida', 'Rol Asignado': 'Compras', 'Tareas Completadas': 52, 'SLA Configurado (días)': '1d', 'Cumplimiento SLA': '92.0%'},
                {'Etapa': 'Viaje Marítimo', 'Rol Asignado': 'Importaciones', 'Tareas Completadas': 48, 'SLA Configurado (días)': '5d', 'Cumplimiento SLA': '82.5%'},
                {'Etapa': 'Aduana', 'Rol Asignado': 'Logística', 'Tareas Completadas': 45, 'SLA Configurado (días)': '2d', 'Cumplimiento SLA': '78.3%'},
                {'Etapa': 'Transporte Local', 'Rol Asignado': 'Logística', 'Tareas Completadas': 44, 'SLA Configurado (días)': '1d', 'Cumplimiento SLA': '95.0%'},
                {'Etapa': 'Almacén', 'Rol Asignado': 'Logística', 'Tareas Completadas': 42, 'SLA Configurado (días)': '1d', 'Cumplimiento SLA': '91.2%'}
            ])
            
    if df_proc_perf.empty:
        st.info("No hay información de rendimiento disponible.")
    else:
        st.dataframe(
            df_proc_perf.style.set_properties(**{
                'background-color': 'white',
                'color': '#334155',
                'border-color': '#e2e8f0'
            }),
            use_container_width=True,
            hide_index=True
        )

    # ─── 8vo. ALINEACIÓN CON OBJETIVOS ESTRATÉGICOS DE NEGOCIO ──────────────────
    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>🎯 Alineación con Objetivos Estratégicos de Negocio (Supply Chain)</div>", unsafe_allow_html=True)
    
    if not objectives:
        objectives_list = [
            {'metric_name': 'Reducir sobrestock global', 'current_value': 4.2, 'target_value': 10.0, 'description': 'Reducción del capital inmovilizado en exceso de inventario'},
            {'metric_name': 'Incrementar Índice de Calidad de Inventario (ICI)', 'current_value': 74.5, 'target_value': 75.0, 'description': 'Asegurar que el stock corresponda con artículos de alta rotación'},
            {'metric_name': 'Reducir quiebres de stock críticos', 'current_value': 8.5, 'target_value': 20.0, 'description': 'Disminuir la venta perdida por quiebre de items top 100'}
        ]
    else:
        objectives_list = [
            {'metric_name': obj.metric_name, 'current_value': obj.current_value, 'target_value': obj.target_value, 'description': obj.description}
            for obj in objectives
        ]
        
    cols = st.columns(len(objectives_list))
    for idx, obj in enumerate(objectives_list):
        with cols[idx]:
            val = obj['current_value']
            tgt = obj['target_value']
            prog_pct = min(100.0, (val / tgt * 100.0)) if tgt > 0 else 0.0
            
            st.markdown(f"""
            <div class="glass-card" style="padding: 18px; min-height: 180px; margin-bottom: 5px;">
                <div style="font-size: 0.82rem; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">{obj['metric_name']}</div>
                <div style="font-size: 1.7rem; font-weight: 700; color: #0f172a; margin-top: 10px; margin-bottom: 2px;">
                    {val:.1f}% <span style="font-size: 0.85rem; color: #64748b; font-weight: 400;">/ Meta: {tgt:.1f}%</span>
                </div>
                <div style="font-size: 0.78rem; color: #64748b; margin-top: 4px; line-height: 1.3;">{obj['description']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(prog_pct / 100.0)
