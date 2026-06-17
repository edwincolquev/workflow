import streamlit as st
import pandas as pd
import plotly.express as px
from database import get_db
from models import WorkflowObjective
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

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>📊 Dashboard Ejecutivo</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Visión consolidada de la cadena de suministro y cumplimiento de metas.</p>", unsafe_allow_html=True)

# 2. Main KPI Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    UIHelpers.render_kpi_card("Inventario Total", "$2.45M USD", "red", "+8% vs mes anterior")
with col2:
    UIHelpers.render_kpi_card("Índice Calidad Inv (ICI)", "74.5%", "yellow", "-1.2% vs objetivo")
with col3:
    UIHelpers.render_kpi_card("Monto en Tránsito", "$850K USD", "green", "+15% vs promedio")
with col4:
    UIHelpers.render_kpi_card("Items Quebrados", "145 SKUs", "red", "Pérdida est: $25K")

st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

# 3. Semaphores Section
st.markdown("<div class='section-header'>🚨 Semáforos de Alerta Operacional</div>", unsafe_allow_html=True)
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(f"**Inventario:** {UIHelpers.get_badge_html('Crítico (Exceso)', 'red')}", unsafe_allow_html=True)
with s2:
    st.markdown(f"**Tránsitos:** {UIHelpers.get_badge_html('En Rango', 'green')}", unsafe_allow_html=True)
with s3:
    st.markdown(f"**Quiebres:** {UIHelpers.get_badge_html('Alto Riesgo', 'red')}", unsafe_allow_html=True)
with s4:
    st.markdown(f"**Discontinuados:** {UIHelpers.get_badge_html('Atención', 'yellow')}", unsafe_allow_html=True)

st.markdown("---")

# 4. Top Brands & Problems
c_left, c_right = st.columns([1.2, 0.8])

with c_left:
    st.markdown("<div class='section-header'>🏆 Top 5 Marcas por Participación</div>", unsafe_allow_html=True)
    top_brands = pd.DataFrame({
        'Marca': ['SKF', 'Bosch', 'Valeo', 'Brembo', 'Denso'],
        'Part. %': [24.0, 18.0, 15.0, 12.0, 10.0],
        'Inventario USD': [500000, 450000, 300000, 250000, 200000],
        'Quiebres SKUs': [12, 45, 10, 5, 15],
        'ICI %': [82, 65, 78, 88, 72]
    })
    
    # Render styled table
    st.dataframe(
        top_brands.style.format({
            'Part. %': '{:.1f}%',
            'Inventario USD': '${:,.0f}',
            'ICI %': '{:.0f}%'
        }),
        use_container_width=True,
        hide_index=True
    )

with c_right:
    st.markdown("<div class='section-header'>⚠️ Problemas Críticos Detectados</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background-color: #fff; border-radius: 8px; padding: 15px; border: 1px solid #e2e8f0; height: 100%;">
        <ul style="padding-left: 15px; margin: 0; color: #475569; font-size: 0.9rem; line-height: 1.6;">
            <li>⚡ <b>SKF</b> incrementó 15% su sobrestock en la línea de rodamientos.</li>
            <li>⚡ <b>Bosch</b> presenta 45 items quebrados críticos de alta demanda.</li>
            <li>⚡ <b>Valeo</b> presenta retrasos superiores a 20 días en 4 importaciones marítimas activas.</li>
            <li>⚡ <b>Discontinuados</b> representan el 7.5% de capital inmovilizado ($180K USD).</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# 5. Objectives & Monthly Goals Progress (From SQLite)
st.markdown("---")
st.markdown("<div class='section-header'>🎯 Objetivos Mensuales del Negocio</div>", unsafe_allow_html=True)

with get_db() as db:
    objectives = db.query(WorkflowObjective).filter(WorkflowObjective.month_period == '2026-06').all()
    
    if not objectives:
        st.info("No se han configurado objetivos para el mes de Junio 2026.")
    else:
        for obj in objectives:
            col_meta, col_progress = st.columns([0.4, 0.6])
            
            with col_meta:
                st.markdown(f"**{obj.metric_name}**")
                st.caption(f"Meta: {obj.target_value}% | Actual: {obj.current_value}%")
            
            with col_progress:
                # Progress calculation
                progress = min(1.0, max(0.0, obj.current_value / obj.target_value))
                st.progress(progress)
