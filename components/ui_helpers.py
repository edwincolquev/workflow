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
