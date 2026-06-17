import streamlit as st
import pandas as pd
import plotly.express as px
from components.ui_helpers import UIHelpers
from config.settings import ROLE_ACCESS

# 1. Access Control
if not st.session_state.get("authenticated", False):
    st.warning("Debe iniciar sesión en la página principal primero.")
    st.stop()

user_role = st.session_state.user['role']
if not ROLE_ACCESS.get(user_role, {}).get('quebrados', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>⚠️ Items Quebrados</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Monitoreo de quiebres de stock y estimación de venta perdida.</p>", unsafe_allow_html=True)

# KPIs
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Items Quebrados", "85 SKUs", "+4 vs mes anterior")
with c2:
    st.metric("Venta Perdida Estimada", "$25,000 USD", "+8% vs prom. trim.")
with c3:
    st.metric("Marcas Afectadas", "5 Marcas", "Principal: Bosch")
with c4:
    st.metric("Tiempo Promedio Quiebre", "19.8 días", "-2.2 días")

st.markdown("---")

col_table, col_pie = st.columns([1.2, 0.8])

with col_table:
    st.markdown("##### Detalle de Quiebres por SKU")
    df_quebrados = pd.DataFrame({
        'ItemCode': ['BOS-FR7DP', 'SKF-6203-2RS', 'VAL-826356', 'BRE-P83085', 'DEN-W20EPR'],
        'Nombre': ['Bujía Bosch Platino', 'Rodamiento Rígido SKF', 'Kit Embrague Valeo', 'Pastilla Freno Brembo', 'Bujía Denso Standard'],
        'Marca': ['Bosch', 'SKF', 'Valeo', 'Brembo', 'Denso'],
        'Días en Quiebre': [24, 15, 12, 18, 30],
        'Demanda Mensual': [500, 300, 45, 120, 250],
        'Venta Perdida Est. USD': [8500, 3200, 2900, 4200, 6100]
    })
    
    st.dataframe(
        df_quebrados.style.format({
            'Venta Perdida Est. USD': '${:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )

with col_pie:
    st.markdown("##### Ventas Perdidas por Marca")
    fig = px.pie(
        df_quebrados, 
        names='Marca', 
        values='Venta Perdida Est. USD',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    st.plotly_chart(fig, use_container_width=True)
