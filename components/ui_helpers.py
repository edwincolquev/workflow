import streamlit as st

class UIHelpers:
    @staticmethod
    def apply_custom_css():
        """Applies premium global CSS styling to the Streamlit app."""
        custom_css = """
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        
        <style>
            /* Apply custom font */
            html, body, [class*="css"], .stMarkdown {
                font-family: 'Outfit', sans-serif !important;
            }

            /* Main background styling */
            .main {
                background: linear-gradient(135deg, #f4f6fa 0%, #eef1f6 100%);
            }
            
            /* Reduce top space of the block container */
            .block-container {
                padding-top: 1.5rem !important;
                padding-bottom: 2.0rem !important;
            }
            
            /* Glassmorphic Cards */
            .glass-card {
                background: rgba(255, 255, 255, 0.7);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 20px;
                border: 1px solid rgba(255, 255, 255, 0.5);
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.04);
                transition: all 0.3s ease-in-out;
                margin-bottom: 20px;
            }
            
            .glass-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.8);
            }

            /* Metric styling */
            .kpi-title {
                font-size: 0.9rem;
                font-weight: 500;
                color: #6c757d;
                text-transform: uppercase;
                margin-bottom: 4px;
            }
            .kpi-value {
                font-size: 1.8rem;
                font-weight: 700;
                color: #1a202c;
                margin-bottom: 8px;
            }
            
            /* Badges & Semaphores */
            .badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
                text-align: center;
                text-transform: uppercase;
            }
            .badge-green {
                background-color: #d1fae5;
                color: #065f46;
                border: 1px solid #a7f3d0;
            }
            .badge-yellow {
                background-color: #fef3c7;
                color: #92400e;
                border: 1px solid #fde68a;
            }
            .badge-red {
                background-color: #fee2e2;
                color: #991b1b;
                border: 1px solid #fca5a5;
            }
            .badge-blue {
                background-color: #dbeafe;
                color: #1e40af;
                border: 1px solid #bfdbfe;
            }
            .badge-gray {
                background-color: #f3f4f6;
                color: #374151;
                border: 1px solid #e5e7eb;
            }

            /* Table Header Style */
            thead tr th {
                background-color: #1e293b !important;
                color: white !important;
                font-weight: 600 !important;
            }

            /* Sidebar custom styling */
            .css-1d391tw {
                background-color: #0f172a !important;
            }
            
            /* Custom headers */
            .main-header {
                font-size: 2.2rem;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 8px;
            }
            .section-header {
                font-size: 1.3rem;
                font-weight: 600;
                color: #334155;
                margin-top: 15px;
                margin-bottom: 15px;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 5px;
            }
        </style>
        """
        st.markdown(custom_css, unsafe_allow_html=True)

    @staticmethod
    def render_kpi_card(title: str, value: str, status: str = 'gray', trend: str = None):
        """Renders a single KPI card with custom premium look."""
        status_classes = {
            'green': 'border-left: 5px solid #10b981;',
            'yellow': 'border-left: 5px solid #f59e0b;',
            'red': 'border-left: 5px solid #ef4444;',
            'blue': 'border-left: 5px solid #3b82f6;',
            'gray': 'border-left: 5px solid #6b7280;'
        }
        
        border_style = status_classes.get(status, status_classes['gray'])
        
        trend_html = ""
        if trend:
            if trend.startswith('+'):
                trend_html = f"<span style='color: #10b981; font-weight: 600; font-size: 0.85rem;'>▲ {trend}</span>"
            elif trend.startswith('-'):
                trend_html = f"<span style='color: #ef4444; font-weight: 600; font-size: 0.85rem;'>▼ {trend}</span>"
            else:
                trend_html = f"<span style='color: #6b7280; font-size: 0.85rem;'>{trend}</span>"

        card_html = f"""
        <div class="glass-card" style="{border_style} padding: 15px 20px;">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div>{trend_html}</div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

    @staticmethod
    def get_badge_html(text: str, badge_type: str = 'gray') -> str:
        """Returns a string containing the HTML code for a styled badge."""
        classes = {
            'green': 'badge-green',
            'yellow': 'badge-yellow',
            'red': 'badge-red',
            'blue': 'badge-blue',
            'gray': 'badge-gray'
        }
        badge_class = classes.get(badge_type, 'badge-gray')
        return f'<span class="badge {badge_class}">{text}</span>'

    @staticmethod
    def render_interactive_mermaid(nodes, transitions, height=600):
        """Renders a Mermaid workflow diagram with interactive node hover popups and zoom controls."""
        if not nodes:
            st.info("Agregue nodos y transiciones para visualizar el diagrama.")
            return

        import json

        # 1. Build Mermaid Definition String & Node Metadata Dictionary
        lines = ["graph TD", "    %% Styles"]
        lines.append("    classDef startNode fill:#d1fae5,stroke:#065f46,stroke-width:2px,color:#065f46;")
        lines.append("    classDef taskNode fill:#dbeafe,stroke:#1e40af,stroke-width:2px,color:#1e40af;")
        lines.append("    classDef decisionNode fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#92400e;")
        lines.append("    classDef gatewayNode fill:#e2e8f0,stroke:#475569,stroke-width:2px,color:#475569;")
        lines.append("    classDef notificationNode fill:#fae8ff,stroke:#86198f,stroke-width:2px,color:#86198f;")
        lines.append("    classDef endNode fill:#fee2e2,stroke:#991b1b,stroke-width:2px,color:#991b1b;")

        node_details = {}

        for n in nodes:
            clean_name = n.name.replace('"', '\\"')
            style_class = "taskNode"
            if n.type == "START":
                style_class = "startNode"
            elif n.type == "DECISION":
                style_class = "decisionNode"
            elif n.type == "GATEWAY":
                style_class = "gatewayNode"
            elif n.type == "NOTIFICATION":
                style_class = "notificationNode"
            elif n.type == "END":
                style_class = "endNode"
            lines.append(f'    N{n.id}["{clean_name} ({n.type})"]:::{style_class}')

            # Outgoing transitions from n
            outgoing = []
            for t in transitions:
                if t.source_node_id == n.id:
                    t_target_name = t.target_node.name if t.target_node else f"Nodo #{t.target_node_id}"
                    t_role_name = t.source_node.role.name if (t.source_node and t.source_node.role) else "Cualquiera"
                    outgoing.append({
                        "action": t.action_name,
                        "target": t_target_name,
                        "role": t_role_name
                    })

            role_str = n.role.name if n.role else "Sin Rol Asignado"
            sla_str = f"{n.sla_hours} Horas" if n.sla_hours else "Sin SLA registrado"
            
            erp_str = None
            if hasattr(n, 'erp_query') and n.erp_query:
                erp_str = getattr(n.erp_query, 'query_name', None) or getattr(n.erp_query, 'name', None)

            node_details[str(n.id)] = {
                "id": n.id,
                "name": n.name,
                "type": n.type,
                "description": n.description or "Sin descripción registrada.",
                "role": role_str,
                "sla": sla_str,
                "erp_query": erp_str,
                "template": n.template_file_name if n.template_file_name else None,
                "outgoing": outgoing
            }

        for t in transitions:
            clean_action = t.action_name.replace('"', '\\"')
            role_name = t.source_node.role.name if (t.source_node and t.source_node.role) else "Cualquiera"
            lines.append(f'    N{t.source_node_id} -->|"{clean_action} ({role_name})"| N{t.target_node_id}')

        mermaid_code = "\n".join(lines)
        node_data_json = json.dumps(node_details)

        html_code = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
if (typeof mermaid === 'undefined') {{
    document.write('<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.0/mermaid.min.js"><\\/script>');
}}
</script>
<style>
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        padding: 0;
        font-family: 'Outfit', sans-serif;
        background: #f8fafc;
        user-select: none;
        overflow: hidden;
    }}
    .toolbar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        padding: 8px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        position: sticky;
        top: 0;
        z-index: 100;
    }}
    .btn-group {{
        display: flex;
        gap: 6px;
        align-items: center;
    }}
    .btn {{
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #334155;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s ease;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }}
    .btn:hover {{
        background: #e2e8f0;
        color: #0f172a;
    }}
    .zoom-indicator {{
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
        min-width: 45px;
        text-align: center;
    }}
    .info-text {{
        font-size: 12px;
        color: #64748b;
        display: flex;
        align-items: center;
        gap: 4px;
    }}
    .canvas-container {{
        width: 100%;
        height: calc(100vh - 45px);
        overflow: auto;
        position: relative;
        cursor: grab;
        background-color: #f8fafc;
        background-image: radial-gradient(#cbd5e1 1px, transparent 1px);
        background-size: 16px 16px;
    }}
    .canvas-container:active {{
        cursor: grabbing;
    }}
    #svg-wrapper {{
        transform-origin: 0 0;
        display: inline-block;
        padding: 20px;
        transition: transform 0.05s ease-out;
    }}
    
    /* TOOLTIP POPUP CARD */
    #node-popup {{
        display: none;
        position: fixed;
        z-index: 999999;
        width: 340px;
        max-width: 85vw;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 10px;
        padding: 14px;
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
        pointer-events: none;
        font-size: 13px;
        color: #1e293b;
    }}
    .popup-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 2px solid #f1f5f9;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }}
    .popup-title {{
        font-weight: 700;
        font-size: 15px;
        color: #0f172a;
        line-height: 1.2;
    }}
    .popup-badge {{
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        white-space: nowrap;
    }}
    .badge-START {{ background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }}
    .badge-TASK {{ background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }}
    .badge-DECISION {{ background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }}
    .badge-GATEWAY {{ background: #e2e8f0; color: #475569; border: 1px solid #cbd5e1; }}
    .badge-NOTIFICATION {{ background: #fae8ff; color: #86198f; border: 1px solid #f5d0fe; }}
    .badge-END {{ background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }}

    .popup-row {{
        margin-bottom: 6px;
        display: flex;
        align-items: flex-start;
        gap: 6px;
    }}
    .popup-label {{
        font-weight: 600;
        color: #475569;
        min-width: 90px;
    }}
    .popup-val {{
        color: #0f172a;
        word-break: break-word;
    }}
    .popup-desc-box {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 12px;
        color: #475569;
        line-height: 1.4;
        margin-top: 4px;
    }}
    .popup-transitions-title {{
        font-weight: 600;
        font-size: 12px;
        color: #334155;
        margin-top: 8px;
        margin-bottom: 4px;
        border-top: 1px solid #f1f5f9;
        padding-top: 6px;
    }}
    .popup-trans-list {{
        margin: 0;
        padding-left: 16px;
        font-size: 12px;
    }}
    .popup-trans-item {{
        margin-bottom: 3px;
        color: #334155;
    }}
</style>
</head>
<body>
<div class="toolbar">
    <div class="btn-group">
        <button class="btn" onclick="zoomIn()">🔍 +</button>
        <button class="btn" onclick="zoomOut()">🔍 -</button>
        <span class="zoom-indicator" id="zoom-val">100%</span>
        <button class="btn" onclick="resetZoom()">🔄 Restablecer</button>
    </div>
    <div class="info-text">
        💡 <span>Pase el cursor sobre cualquier nodo para ver sus detalles ampliados</span>
    </div>
</div>

<div class="canvas-container" id="container">
    <div id="svg-wrapper">
        <pre class="mermaid" id="mermaid-src">
{mermaid_code}
        </pre>
    </div>
</div>

<div id="node-popup">
    <div class="popup-header">
        <span class="popup-title" id="p-title"></span>
        <span class="popup-badge" id="p-badge"></span>
    </div>
    <div id="p-content">
        <div class="popup-row">
            <span class="popup-label">👤 Rol:</span>
            <span class="popup-val" id="p-role" style="font-weight:600; color:#0284c7;"></span>
        </div>
        <div class="popup-row">
            <span class="popup-label">⏱️ SLA:</span>
            <span class="popup-val" id="p-sla"></span>
        </div>
        <div id="p-extra"></div>
        <div>
            <span class="popup-label">📝 Descripción:</span>
            <div class="popup-desc-box" id="p-desc"></div>
        </div>
        <div id="p-trans-container">
            <div class="popup-transitions-title">🔀 Acciones / Salidas disponibles:</div>
            <ul class="popup-trans-list" id="p-trans-list"></ul>
        </div>
    </div>
</div>

<script>
const nodeData = {node_data_json};

let scale = 1.0;
let isPanning = false;
let startX = 0, startY = 0;
let translateX = 0, translateY = 0;

const container = document.getElementById('container');
const svgWrapper = document.getElementById('svg-wrapper');
const popup = document.getElementById('node-popup');

function updateTransform() {{
    svgWrapper.style.transform = `translate(${{translateX}}px, ${{translateY}}px) scale(${{scale}})`;
    document.getElementById('zoom-val').textContent = Math.round(scale * 100) + '%';
}}

function zoomIn() {{
    scale = Math.min(2.5, scale + 0.15);
    updateTransform();
}}

function zoomOut() {{
    scale = Math.max(0.3, scale - 0.15);
    updateTransform();
}}

function resetZoom() {{
    scale = 1.0;
    translateX = 0;
    translateY = 0;
    updateTransform();
}}

// Pan logic
container.addEventListener('mousedown', (e) => {{
    if (e.target.closest('#node-popup')) return;
    isPanning = true;
    startX = e.clientX - translateX;
    startY = e.clientY - translateY;
}});

window.addEventListener('mousemove', (e) => {{
    if (isPanning) {{
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;
        updateTransform();
    }}
    if (popup.style.display === 'block') {{
        movePopup(e);
    }}
}});

window.addEventListener('mouseup', () => {{
    isPanning = false;
}});

// Wheel zoom
container.addEventListener('wheel', (e) => {{
    e.preventDefault();
    if (e.deltaY < 0) {{
        scale = Math.min(2.5, scale + 0.08);
    }} else {{
        scale = Math.max(0.3, scale - 0.08);
    }}
    updateTransform();
}}, {{ passive: false }});

function movePopup(e) {{
    const pad = 15;
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    
    const pw = popup.offsetWidth || 340;
    const ph = popup.offsetHeight || 220;
    const ww = window.innerWidth;
    const wh = window.innerHeight;
    
    if (x + pw > ww - 10) {{
        x = e.clientX - pw - pad;
    }}
    if (y + ph > wh - 10) {{
        y = e.clientY - ph - pad;
    }}
    popup.style.left = Math.max(10, x) + 'px';
    popup.style.top = Math.max(10, y) + 'px';
}}

function showNodePopup(nodeId, e) {{
    const data = nodeData[nodeId];
    if (!data) return;
    
    document.getElementById('p-title').textContent = data.name + ' (#' + data.id + ')';
    const badge = document.getElementById('p-badge');
    badge.textContent = data.type;
    badge.className = 'popup-badge badge-' + data.type;
    
    document.getElementById('p-role').textContent = data.role;
    document.getElementById('p-sla').textContent = data.sla;
    document.getElementById('p-desc').textContent = data.description;
    
    let extraHtml = '';
    if (data.erp_query) {{
        extraHtml += `<div class="popup-row"><span class="popup-label">🔍 Consulta ERP:</span><span class="popup-val">${{data.erp_query}}</span></div>`;
    }}
    if (data.template) {{
        extraHtml += `<div class="popup-row"><span class="popup-label">📄 Plantilla:</span><span class="popup-val">${{data.template}}</span></div>`;
    }}
    document.getElementById('p-extra').innerHTML = extraHtml;
    
    const transList = document.getElementById('p-trans-list');
    transList.innerHTML = '';
    if (data.outgoing && data.outgoing.length > 0) {{
        data.outgoing.forEach(t => {{
            const li = document.createElement('li');
            li.className = 'popup-trans-item';
            li.innerHTML = `<strong>${{t.action}}</strong> ➔ <em>${{t.target}}</em> <small style="color:#64748b;">(${{t.role}})</small>`;
            transList.appendChild(li);
        }});
        document.getElementById('p-trans-container').style.display = 'block';
    }} else {{
        document.getElementById('p-trans-container').style.display = 'none';
    }}
    
    popup.style.display = 'block';
    movePopup(e);
}}

function hideNodePopup() {{
    popup.style.display = 'none';
}}

function bindNodeEvents() {{
    const nodes = document.querySelectorAll('g.node, g[id*="flowchart-N"], g[id^="N"]');
    nodes.forEach(nodeElem => {{
        const idAttr = nodeElem.id || '';
        let match = idAttr.match(/N(\\d+)/);
        if (!match) {{
            const txt = nodeElem.textContent || '';
            match = txt.match(/N(\\d+)/);
        }}
        if (match) {{
            const numId = match[1];
            if (nodeData[numId]) {{
                nodeElem.style.cursor = 'pointer';
                nodeElem.addEventListener('mouseenter', (e) => showNodePopup(numId, e));
                nodeElem.addEventListener('mouseleave', () => hideNodePopup());
            }}
        }}
    }});
}}

function initDiagram() {{
    if (typeof mermaid !== 'undefined') {{
        mermaid.initialize({{
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'default',
            flowchart: {{ useMaxWidth: false, htmlLabels: true }}
        }});
        
        if (mermaid.run) {{
            mermaid.run({{ querySelector: '.mermaid' }})
                .then(() => setTimeout(bindNodeEvents, 200))
                .catch(() => setTimeout(bindNodeEvents, 500));
        }} else if (mermaid.init) {{
            mermaid.init(undefined, '.mermaid');
            setTimeout(bindNodeEvents, 500);
        }} else {{
            setTimeout(bindNodeEvents, 800);
        }}
    }}
}}

if (document.readyState === 'complete' || document.readyState === 'interactive') {{
    setTimeout(initDiagram, 100);
}} else {{
    document.addEventListener('DOMContentLoaded', initDiagram);
}}
</script>
</body>
</html>
"""
        st.components.v1.html(html_code, height=height, scrolling=False)

