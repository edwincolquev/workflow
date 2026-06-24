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
if not ROLE_ACCESS.get(user_role, {}).get('inventarios', False):
    st.error("Acceso denegado: Tu rol no tiene permisos para ver esta sección.")
    st.stop()

# Apply CSS
UIHelpers.apply_custom_css()

# Sidebar User Info
st.sidebar.markdown(f"**Usuario:** {st.session_state.user['full_name']}")
st.sidebar.markdown(f"**Rol:** {st.session_state.user['role']}")

st.markdown("<h1 class='main-header'>📦 Módulo de Inventarios</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b;'>Análisis y monitoreo de la calidad y cobertura del inventario.</p>", unsafe_allow_html=True)

# Tabs Definition
t_resumen, t_ici, t_cobertura, t_excesos, t_quiebres, t_evolucion = st.tabs([
    "📊 Resumen", "🎯 ICI", "📅 Cobertura", "📈 Excesos", "⚠️ Quiebres", "📉 Evolución"
])

# ==========================================
# TAB 1: RESUMEN
# ==========================================
with t_resumen:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Capital Inmovilizado", "$540,000 USD", "-5% vs mes anterior")
    with c2:
        st.metric("Índice de Calidad (ICI)", "74.5 / 100", "+2.1 pts vs mes ant.")
    with c3:
        st.metric("SKUs en Exceso", "214 SKUs", "-15 SKUs")
    with c4:
        st.metric("SKUs en Quiebre", "85 SKUs", "-8 SKUs")

    st.markdown("---")

    # Brand inventory weight
    st.markdown("##### Capital Inmovilizado por Marca")
    brand_inv = pd.DataFrame({
        'Marca': ['SKF', 'Bosch', 'Valeo', 'Brembo', 'Denso'],
        'Sobre-Stock USD': [180000, 150000, 90000, 70000, 50000],
        'SKUs Afectados': [45, 38, 22, 18, 12]
    })
    
    fig = px.bar(
        brand_inv, 
        x='Marca', 
        y='Sobre-Stock USD', 
        text_auto='.2s',
        color='Marca',
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 2: ICI (ÍNDICE CALIDAD INVENTARIO)
# ==========================================
with t_ici:
    st.markdown("#### Índice de Calidad de Inventario (ICI)")
    st.write("El ICI mide qué porcentaje de tu inventario corresponde a productos de alta rotación (Ventas Clase A) ponderado por el peso comercial de cada marca.")
    
    col_chart, col_details = st.columns([1.2, 0.8])
    with col_chart:
        ici_data = pd.DataFrame({
            'Línea de Negocio': ['Rodamientos', 'Frenos', 'Filtros', 'Encendido', 'Embragues'],
            'ICI': [82, 74, 68, 71, 79]
        })
        fig_ici = px.polar_bar(ici_data, r='ICI', theta='Línea de Negocio', color='Línea de Negocio', title="ICI por Línea")
        st.plotly_chart(fig_ici, use_container_width=True)
        
    with col_details:
        st.markdown("""
        **Ponderador de Importancia de Ventas:**
        * **SKF (Rodamientos)**: Peso 35% | ICI Actual: **82%**
        * **Bosch (Encendido)**: Peso 25% | ICI Actual: **71%**
        * **Valeo (Embragues)**: Peso 20% | ICI Actual: **79%**
        * **Brembo (Frenos)**: Peso 15% | ICI Actual: **74%**
        * **Denso (Filtros)**: Peso 5% | ICI Actual: **68%**
        """)

# ==========================================
# TAB 3: COBERTURA
# ==========================================
with t_cobertura:
    st.markdown("#### Análisis de Cobertura de Stock")
    st.caption("Cobertura = Inventario Actual / Venta Promedio Mensual")
    
    cob_df = pd.DataFrame({
        'Categoría Cobertura': ['Quiebre (0 meses)', 'Bajo (< 1.5 meses)', 'Óptimo (1.5 - 3 meses)', 'Alto (3 - 6 meses)', 'Exceso (> 6 meses)'],
        'Cantidad SKUs': [85, 120, 410, 180, 214],
        'Valor Inventario USD': [0, 80000, 950000, 600000, 540000]
    })
    
    st.dataframe(
        cob_df.style.format({
            'Valor Inventario USD': '${:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    fig_cob = px.pie(cob_df, names='Categoría Cobertura', values='Cantidad SKUs', title="Distribución de SKUs por Cobertura")
    st.plotly_chart(fig_cob, use_container_width=True)

# ==========================================
# TAB 4: EXCESOS
# ==========================================
with t_excesos:
    st.markdown("#### Detalle de Excesos y Capital Inmovilizado")
    st.write("SKUs con cobertura mayor a 6 meses de venta promedio mensual.")
    
    excesos_data = pd.DataFrame({
        'SKU': ['SKF-6203-2RS', 'BOS-FR7DP', 'VAL-826356', 'BRE-P83085', 'DEN-W20EPR'],
        'Marca': ['SKF', 'Bosch', 'Valeo', 'Brembo', 'Denso'],
        'Stock Actual': [1200, 3500, 450, 800, 2500],
        'Venta Mensual Prom': [50, 150, 20, 45, 110],
        'Cobertura (Meses)': [24.0, 23.3, 22.5, 17.8, 22.7],
        'Capital Exceso USD': [14400, 17500, 9000, 12800, 7500]
    })
    
    st.dataframe(
        excesos_data.style.format({
            'Capital Exceso USD': '${:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )

# ==========================================
# TAB 5: QUIEBRES
# ==========================================
with t_quiebres:
    st.markdown("#### Quiebres de Stock Detectados")
    st.write("Artículos con stock cero o por debajo de la demanda mensual de seguridad.")
    
    quiebres_data = pd.DataFrame({
        'SKU': ['SKF-30204-J', 'BOS-SP009', 'VAL-828002', 'BRE-09A721', 'DEN-IK20TT'],
        'Marca': ['SKF', 'Bosch', 'Valeo', 'Brembo', 'Denso'],
        'Venta Perdida Est. USD': [3200, 8500, 2900, 4200, 6100],
        'Días en Quiebre': [15, 24, 12, 18, 30]
    })
    
    st.dataframe(
        quiebres_data.style.format({
            'Venta Perdida Est. USD': '${:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )

# ==========================================
# TAB 6: EVOLUCIÓN
# ==========================================
with t_evolucion:
    st.markdown("#### Evolución Histórica de ICI e Inventario")
    
    evo_data = pd.DataFrame({
        'Mes': ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun'],
        'ICI (%)': [71.2, 72.0, 73.5, 73.0, 73.9, 74.5],
        'Exceso Inventario (k$):': [600, 580, 570, 560, 550, 540]
    })
    
    fig_line = px.line(evo_data, x='Mes', y='ICI (%)', title="Tendencia del ICI")
    st.plotly_chart(fig_line, use_container_width=True)
