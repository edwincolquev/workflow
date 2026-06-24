import streamlit as st
import pandas as pd
from database import get_db
from models import WorkflowProcess
from engine import WorkflowEngine
from services.data_loader import DataLoaderService
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS

# 1. Access Control
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

user_role = st.session_state.user['role']
if not ROLE_ACCESS.get(user_role, {}).get('nuevos', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>🆕 Productos Nuevos</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Evaluación de desempeño y seguimiento del flujo de preparación para el mercado de nuevos SKUs.</p>", unsafe_allow_html=True)

# 2. Fetch Data from Data Loader (combines SAP & SQLite)
with get_db() as db:
    df_raw, is_mock = DataLoaderService.get_nuevos_with_workflow(db)

if df_raw.empty:
    st.warning("No se encontraron registros de productos nuevos.")
    st.stop()

if is_mock:
    st.sidebar.info("🤖 Usando datos simulados (SQL Server no configurado).")

# Filter by Manufacturer
manufacturers = sorted(df_raw['Fabricante'].unique())
selected_mfg = st.sidebar.multiselect("Fabricante", manufacturers, default=manufacturers)

df_filtered = df_raw[df_raw['Fabricante'].isin(selected_mfg)]

# 3. KPIs
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Nuevos SKUs Activos", len(df_filtered))
with c2:
    st.metric("Ventas Acumuladas USD", f"${df_filtered['Venta Acumulada USD'].sum():,.2f} USD")
with c3:
    st.metric("Stock Actual Unidades", f"{df_filtered['Stock Actual'].sum():,.0f}")
with c4:
    avg_cov = df_filtered['Cobertura'].mean()
    st.metric("Cobertura Promedio", f"{avg_cov:.1f} meses" if not pd.isna(avg_cov) else "0.0 meses")

st.markdown("---")

# 4. Initiate/View Workflow Container
col_sel, col_act = st.columns([1.5, 1])

with col_sel:
    item_codes = sorted(df_filtered['ItemCode'].unique())
    selected_item = st.selectbox("Seleccione un Código de Artículo (ItemCode):", item_codes)
    
with col_act:
    if selected_item:
        row_data = df_filtered[df_filtered['ItemCode'] == selected_item].iloc[0]
        instance_id = row_data.get('wf_instance_id')
        
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        if pd.isna(instance_id) or instance_id is None:
            # Button to start workflow
            if st.button("🚀 Iniciar Habilitación de Item"):
                with get_db() as db:
                    proc = db.query(WorkflowProcess).filter(WorkflowProcess.name == "Items Nuevos").first()
                    if proc:
                        try:
                            WorkflowEngine.create_instance(
                                db=db,
                                process_id=proc.id,
                                title=f"Habilitación SKU {selected_item} - {row_data['ItemName']}",
                                creator_id=st.session_state.user['id'],
                                external_ref=f"ItemCode:{selected_item}"
                            )
                            st.success(f"¡Flujo de habilitación iniciado para {selected_item}!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al iniciar flujo: {str(ex)}")
                    else:
                        st.error("Proceso 'Items Nuevos' no está configurado en el motor.")
        else:
            # Button to go to details
            if st.button("🔗 Ver Detalle de Tarea & Avance"):
                st.session_state.selected_workflow_instance_id = int(instance_id)
                st.success(f"Instancia #{int(instance_id)} cargada en memoria. Por favor, ve a la pestaña '08 Detalle Workflow' en el sidebar.")

st.markdown("---")

# 5. Display Table
if not df_filtered.empty:
    display_df = df_filtered[[
        'ItemCode', 'ItemName', 'Fabricante', 'Stock Actual', 
        'Venta Acumulada USD', 'Clasificacion', 'wf_estado', 'wf_rol_asignado'
    ]].copy()
    
    display_df.columns = [
        'Código SKU', 'Nombre Artículo', 'Fabricante', 'Stock Actual', 
        'Ventas USD', 'Desempeño', 'Estado Workflow', 'Rol Responsable'
    ]
    
    st.dataframe(
        display_df.style.format({
            'Ventas USD': '${:,.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    # Export and Email Actions
    st.markdown("##### 📥 Exportar Productos Nuevos")
    ex_col1, ex_col2, ex_col3 = st.columns(3)
    from services.export_service import ExportService
    with ex_col1:
        csv_bytes = ExportService.to_csv(df_filtered)
        st.download_button("Exportar a CSV", csv_bytes, "productos_nuevos.csv", "text/csv")
    with ex_col2:
        xls_bytes = ExportService.to_excel(df_filtered)
        st.download_button("Exportar a Excel", xls_bytes, "productos_nuevos.xlsx")
    with ex_col3:
        pdf_bytes = ExportService.to_pdf("Productos Nuevos", "Portal de Cadena de Suministro", df_filtered)
        st.download_button("Exportar a PDF", pdf_bytes, "productos_nuevos.pdf")
        
    st.markdown("##### ✉️ Enviar Reporte por Correo")
    with st.form(key="email_report_form_nuevos"):
        dest_email = st.text_input("Correo Destinatario:", placeholder="ej. usuario@empresa.com")
        message = st.text_area("Mensaje adicional (Opcional):", placeholder="Adjunto reporte de productos nuevos...")
        send_btn = st.form_submit_button("Enviar Reporte")
        if send_btn:
            if not dest_email.strip():
                st.error("Por favor, ingrese un correo destinatario.")
            else:
                try:
                    from services.email_service import send_report_email
                    send_report_email(
                        to_email=dest_email.strip(),
                        report_title="Productos Nuevos",
                        df=df_filtered,
                        message=message.strip()
                    )
                    st.success(f"Reporte enviado con éxito a {dest_email}.")
                except Exception as e:
                    st.error(f"Error al enviar correo: {str(e)}")
else:
    st.info("No hay productos nuevos para mostrar.")
