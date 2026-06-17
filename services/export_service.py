import io
import pandas as pd
from datetime import datetime

class ExportService:
    @staticmethod
    def to_csv(df: pd.DataFrame) -> bytes:
        """Converts a DataFrame to CSV bytes encoded in utf-8 with BOM for Excel compatibility."""
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue().encode('utf-8-sig')

    @staticmethod
    def to_excel(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
        """Converts a DataFrame to Excel bytes using openpyxl."""
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                max_len = max(len(str(val or '')) for val in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 10)
        return excel_buffer.getvalue()

    @staticmethod
    def to_pdf(title: str, subtitle: str, df: pd.DataFrame, max_rows: int = 50) -> bytes:
        """
        Generates a styled PDF report using fpdf2.
        Truncates data to max_rows to prevent extremely long PDFs.
        """
        try:
            from fpdf import FPDF
        except ImportError:
            # Fallback in case fpdf is missing
            fallback_text = f"{title}\n{subtitle}\nReport generated on {datetime.now()}\n\n"
            fallback_text += df.head(max_rows).to_string()
            return fallback_text.encode('utf-8')

        class StyledPDF(FPDF):
            def header(self):
                self.set_fill_color(24, 28, 36) # dark blue grey
                self.rect(0, 0, 210, 30, 'F')
                self.set_text_color(255, 255, 255)
                self.set_font('Helvetica', 'B', 16)
                self.cell(0, 10, title.upper(), 0, 1, 'C')
                self.set_font('Helvetica', 'I', 10)
                self.cell(0, 5, subtitle, 0, 1, 'C')
                self.ln(15)

            def footer(self):
                self.set_y(-15)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f"Página {self.page_no()}/{{nb}} - Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 0, 'C')

        pdf = StyledPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Body font
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(0, 0, 0)

        # Select a subset of important columns to fit on the standard A4 page (width: 190mm)
        cols_to_print = []
        col_widths = []
        
        # Check standard columns based on DataFrame type
        all_cols = list(df.columns)
        if 'DocNum' in all_cols: # Transitos-like
            cols_to_print = ['DocNum', 'Nombre Proveedor', 'Fabricante', 'Fecha Estimada de Llegada', 'En Transito', 'Etapa']
            col_widths = [18, 55, 30, 32, 25, 30]
        elif 'ItemCode' in all_cols: # Nuevos-like
            cols_to_print = ['ItemCode', 'ItemName', 'Fabricante', 'Stock Actual', 'Clasificacion']
            col_widths = [25, 65, 35, 25, 40]
        else: # Generic fallback
            cols_to_print = all_cols[:5]
            col_widths = [38] * len(cols_to_print)

        # Draw Table Header
        pdf.set_fill_color(220, 224, 230)
        pdf.set_font('Helvetica', 'B', 8)
        for col, width in zip(cols_to_print, col_widths):
            pdf.cell(width, 7, str(col), 1, 0, 'C', fill=True)
        pdf.ln()

        # Draw Table Rows
        pdf.set_font('Helvetica', '', 8)
        rows_printed = 0
        for _, row in df.iterrows():
            if rows_printed >= max_rows:
                break
            
            # Alternate row background
            fill = (rows_printed % 2 == 1)
            if fill:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)

            for col, width in zip(cols_to_print, col_widths):
                val = str(row.get(col, ''))
                # Handle numeric formatting for cash/quantity if needed
                if col in ['En Transito', 'Monto Facturado', 'Stock Actual']:
                    try:
                        val = f"{float(val):,.0f}"
                    except:
                        pass
                elif isinstance(row.get(col), datetime):
                    val = row.get(col).strftime('%Y-%m-%d')
                
                # Truncate text if too long
                if len(val) > 30 and width < 40:
                    val = val[:27] + "..."
                elif len(val) > 40:
                    val = val[:37] + "..."
                    
                pdf.cell(width, 6, val, 1, 0, 'L', fill=True)
            pdf.ln()
            rows_printed += 1

        if len(df) > max_rows:
            pdf.ln(5)
            pdf.set_font('Helvetica', 'I', 8)
            pdf.cell(0, 10, f"* Reporte limitado a los primeros {max_rows} registros de {len(df)} totales.", 0, 1, 'L')

        return pdf.output()
