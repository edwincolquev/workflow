import streamlit as st
import pandas as pd
from database import get_db
from models import WorkflowProcess
from engine import WorkflowEngine
from services.data_loader import DataLoaderService
from services.export_service import ExportService
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS

# 1. Access Control
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

user_role = st.session_state.user['role']
if not ROLE_ACCESS.get(user_role, {}).get('transitos', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>🚢 Módulo de Tránsitos</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Seguimiento analítico y operacional de importaciones en tránsito.</p>", unsafe_allow_html=True)

# 2. Fetch Data from Data Loader (combines SAP & SQLite)
with get_db() as db:
    df_raw, is_mock = DataLoaderService.get_transitos_with_workflow(db)

if df_raw.empty:
    st.warning("No se encontraron registros de tránsitos.")
    st.stop()

if is_mock:
    st.sidebar.info("🤖 Usando datos simulados (SQL Server no configurado).")

# 3. Sidebar Filters
st.sidebar.markdown("### Filtros de Tránsito")

# Provider Filter
providers = sorted(df_raw['Nombre Proveedor'].unique())
selected_prov = st.sidebar.multiselect("Proveedor", providers, default=providers)

# Manufacturer Filter
manufacturers = sorted(df_raw['Fabricante'].unique())
selected_mfg = st.sidebar.multiselect("Fabricante/Marca", manufacturers, default=manufacturers)

# Stage Filter
stages = sorted(df_raw['Etapa'].unique())
selected_stage = st.sidebar.multiselect("Etapa Comercial", stages, default=stages)

# Apply filters
df_filtered = df_raw[
    df_raw['Nombre Proveedor'].isin(selected_prov) &
    df_raw['Fabricante'].isin(selected_mfg) &
    df_raw['Etapa'].isin(selected_stage)
]

# Tabs Definition
tab_resumen, tab_detalle, tab_completados = st.tabs(["📊 Resumen Ejecutivo", "📋 Detalle Activo", "✅ Ingresados"])

# ==========================================
# TAB 1: RESUMEN
# ==========================================
with tab_resumen:
    # Segment active vs completed
    df_active = df_filtered[df_filtered['EstadoFlujo'] == 'Pendiente']
    
    # KPI metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        total_transit_usd = df_active['Monto Pendiente Ofertado USD'].sum()
        st.metric("Monto en Tránsito Activo", f"${total_transit_usd:,.2f} USD")
    with c2:
        active_imports_count = df_active['DocNum'].nunique()
        st.metric("Importaciones Activas", active_imports_count)
    with c3:
        retrasadas_count = df_active[df_active['EstadoRetraso'] == 'Retrasado']['DocNum'].nunique()
        st.metric("Importaciones Retrasadas", retrasadas_count)
    with c4:
        avg_lt = df_active['Lead Time Calc.'].mean()
        st.metric("Lead Time Promedio", f"{avg_lt:.1f} días" if not pd.isna(avg_lt) else "0.0 días")

    st.markdown("---")
    
    # Graphic analysis
    if not df_active.empty:
        st.markdown("##### Distribución de Montos por Etapa Comercial")
        stage_df = df_active.groupby('Etapa', as_index=False)['Monto Pendiente Ofertado USD'].sum()
        import plotly.express as px
        fig = px.bar(
            stage_df, 
            x='Etapa', 
            y='Monto Pendiente Ofertado USD',
            labels={'Monto Pendiente Ofertado USD': 'Monto USD'},
            color='Etapa',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay tránsitos activos para mostrar en el gráfico.")

# ==========================================
# TAB 2: DETALLE ACTIVO
# ==========================================
with tab_detalle:
    df_active = df_filtered[df_filtered['EstadoFlujo'] == 'Pendiente'].copy()
    
    # Search / select tool to initiate/view workflow
    col_sel, col_act = st.columns([1.5, 1])
    
    with col_sel:
        doc_nums = sorted(df_active['DocNum'].unique())
        selected_doc = st.selectbox("Seleccione un número de importación (DocNum):", doc_nums)
        
    with col_act:
        if selected_doc:
            row_data = df_active[df_active['DocNum'] == selected_doc].iloc[0]
            instance_id = row_data.get('wf_instance_id')
            
            st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
            if pd.isna(instance_id) or instance_id is None:
                # Button to start workflow
                if st.button("🚀 Iniciar Workflow Operacional"):
                    with get_db() as db:
                        proc = db.query(WorkflowProcess).filter(WorkflowProcess.name == "Importaciones").first()
                        if proc:
                            try:
                                WorkflowEngine.create_instance(
                                    db=db,
                                    process_id=proc.id,
                                    title=f"Importación OC {selected_doc} - {row_data['Nombre Proveedor']}",
                                    creator_id=st.session_state.user['id'],
                                    external_ref=f"DocNum:{selected_doc}"
                                )
                                st.success(f"¡Workflow iniciado para DocNum {selected_doc}!")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error al crear workflow: {str(ex)}")
                        else:
                            st.error("Proceso 'Importaciones' no está configurado en el motor.")
            else:
                # Button to go to details
                if st.button("🔗 Ver Detalle de Tarea & Avance"):
                    st.session_state.selected_workflow_instance_id = int(instance_id)
                    # Redirect dynamically in Streamlit.
                    # Since Streamlit doesn't support easy page redirects without queries or reload,
                    # we can set the state and instruct the user or let the page do a mock redirection.
                    # Alternatively, since pages are native, the user can click on "Mi Bandeja" or we display a direct instructions box.
                    st.success(f"Instancia #{int(instance_id)} cargada en memoria. Por favor, ve a la pestaña '08 Detalle Workflow' en el sidebar.")

    st.markdown("---")

    # Display grid
    if not df_active.empty:
        # Display formatted columns
        display_df = df_active[[
            'DocNum', 'Nombre Proveedor', 'Fabricante', 'Fecha Oferta Compra', 
            'Fecha Estimada de Llegada', 'Monto Pendiente Ofertado USD', 'Etapa', 'wf_estado', 'wf_rol_asignado'
        ]].copy()
        
        display_df.columns = [
            'DocNum', 'Proveedor', 'Fabricante', 'Fecha Emisión', 
            'Fecha Est. Llegada', 'Monto USD', 'Etapa SAP', 'Estado Workflow', 'Rol Responsable'
        ]
        
        st.dataframe(
            display_df.style.format({
                'Monto USD': '${:,.2f}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Export Actions
        st.markdown("##### 📥 Exportar Tránsitos Activos")
        ex_col1, ex_col2, ex_col3 = st.columns(3)
        with ex_col1:
            csv_bytes = ExportService.to_csv(df_active)
            st.download_button("Exportar a CSV", csv_bytes, "transitos_activos.csv", "text/csv")
        with ex_col2:
            xls_bytes = ExportService.to_excel(df_active)
            st.download_button("Exportar a Excel", xls_bytes, "transitos_activos.xlsx")
        with ex_col3:
            pdf_bytes = ExportService.to_pdf("Tránsitos Activos", "Portal de Cadena de Suministro", df_active)
            st.download_button("Exportar a PDF", pdf_bytes, "transitos_activos.pdf")

        # Email dispatch action
        st.markdown("##### ✉️ Enviar Reporte por Correo")
        with st.form(key="email_report_form_transitos"):
            dest_email = st.text_input("Correo Destinatario:", placeholder="ej. usuario@empresa.com")
            message = st.text_area("Mensaje adicional (Opcional):", placeholder="Adjunto reporte de tránsitos activos...")
            send_btn = st.form_submit_button("Enviar Reporte")
            if send_btn:
                if not dest_email.strip():
                    st.error("Por favor, ingrese un correo destinatario.")
                else:
                    try:
                        from services.email_service import send_report_email
                        send_report_email(
                            to_email=dest_email.strip(),
                            report_title="Tránsitos Activos",
                            df=df_active,
                            message=message.strip()
                        )
                        st.success(f"Reporte enviado con éxito a {dest_email}.")
                    except Exception as e:
                        st.error(f"Error al enviar correo: {str(e)}")
    else:
        st.info("No hay tránsitos activos para mostrar.")

# ==========================================
# TAB 3: COMPLETADOS
# ==========================================
with tab_completados:
    df_comp = df_filtered[df_filtered['EstadoFlujo'] == 'Completado']
    
    if not df_comp.empty:
        st.markdown("##### Historial de Importaciones Completadas e Ingresadas")
        display_comp = df_comp[[
            'DocNum', 'Nombre Proveedor', 'Fabricante', 'Fecha Ingreso', 'Monto Facturado'
        ]].copy()
        
        display_comp.columns = [
            'DocNum', 'Proveedor', 'Fabricante', 'Fecha Ingreso Real', 'Monto Facturado USD'
        ]
        
        st.dataframe(
            display_comp.style.format({
                'Monto Facturado USD': '${:,.2f}'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No se registran importaciones completadas bajo los filtros seleccionados.")
