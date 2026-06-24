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
if not ROLE_ACCESS.get(user_role, {}).get('discontinuados', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>🚫 Discontinuados</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Análisis de capital inmovilizado en artículos en proceso de discontinuación.</p>", unsafe_allow_html=True)

# KPIs
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Capital en Discontinuados", "$180,000 USD", "-2% vs mes anterior")
with c2:
    st.metric("Cantidad de SKUs", "62 SKUs", "-4 SKUs")
with c3:
    st.metric("Meses sin Venta Promedio", "14.2 meses", "+0.8 meses")
with c4:
    st.metric("% del Inventario Total", "7.3%", "-0.5%")

st.markdown("---")

col_table, col_pie = st.columns([1.2, 0.8])

with col_table:
    st.markdown("##### Detalle de Artículos Discontinuados")
    df_discontinuados = pd.DataFrame({
        'ItemCode': ['SKF-6302-C3', 'BOS-WR7DC', 'VAL-821098', 'BRE-098485', 'DEN-KJ20CRL'],
        'Nombre': ['Rodamiento Cónico SKF', 'Bujía Súper Bosch', 'Kit Embrague Valeo Especial', 'Disco Freno Brembo Ventilado', 'Bujía Denso Iridium'],
        'Marca': ['SKF', 'Bosch', 'Valeo', 'Brembo', 'Denso'],
        'Stock': [300, 1200, 80, 110, 400],
        'Capital Inmovilizado USD': [4500, 7200, 18000, 11000, 8400],
        'Meses sin Venta': [18, 14, 11, 13, 22],
        'Estado': ['Discontinuado', 'Riesgo', 'Activo en Liquidación', 'Riesgo', 'Discontinuado']
    })
    
    st.dataframe(
        df_discontinuados.style.format({
            'Capital Inmovilizado USD': '${:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )

with col_pie:
    st.markdown("##### Distribución del Capital Inmovilizado")
    fig = px.pie(
        df_discontinuados, 
        names='Marca', 
        values='Capital Inmovilizado USD',
        color_discrete_sequence=px.colors.qualitative.Prism
    )
    st.plotly_chart(fig, use_container_width=True)
