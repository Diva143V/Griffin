import os
from fpdf import FPDF
import pandas as pd

class ScientificReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Griffin Bio - Scientific Synthesis & Consensus Report", 0, 1, "R")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u03b2": "beta",
        "\u03b1": "alpha",
        "\u03bc": "mu",
        "\u2019": "'",
        "\u201d": '"',
        "\u201c": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "*",
        "\u2192": "->",
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.encode("latin-1", errors="replace").decode("latin-1")

def generate_synthesis_pdf(
    query: str,
    consensus_text: str,
    protocol_text: str,
    top_papers_df: pd.DataFrame | None,
    output_path: str
) -> str:
    pdf = ScientificReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Title Section
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(15, 23, 42) # Slate-900
    pdf.multi_cell(0, 12, clean_pdf_text("Scientific Consensus Report"))
    pdf.ln(5)
    
    # Query Section
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(79, 70, 229) # Indigo-600
    pdf.cell(0, 6, "RESEARCH QUERY:", 0, 1)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(30, 41, 59) # Slate-800
    pdf.multi_cell(0, 6, clean_pdf_text(query))
    pdf.ln(8)
    
    # Consensus Report
    if consensus_text:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "1. Executive Consensus & Synthesis", 0, 1)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
        pdf.ln(4)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85) # Slate-700
        pdf.multi_cell(0, 5, clean_pdf_text(consensus_text))
        pdf.ln(10)
        
    # Protocol Section
    if protocol_text:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "2. Laboratory Protocol Draft", 0, 1)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
        pdf.ln(4)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 5, clean_pdf_text(protocol_text))
        pdf.ln(10)
        
    # Cited Papers Section
    if top_papers_df is not None and not top_papers_df.empty:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "3. Cited Evidence & Methodological Quality", 0, 1)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
        pdf.ln(4)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        
        # Display top 5 papers
        for idx, (_, r) in enumerate(top_papers_df.head(5).iterrows(), 1):
            title = r.get("title", "")
            score = r.get("evidence_score", 0.0)
            design = r.get("study_design", "Undetermined")
            sample_val = r.get("sample_size", 0)
            sample_size = str(int(sample_val)) if (pd.notna(sample_val) and sample_val > 0) else "N/A"
            year = r.get("year", "N/A")
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 5, clean_pdf_text(f"[{idx}] {title}"))
            
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 116, 139) # Slate-500
            pdf.cell(0, 5, clean_pdf_text(f"Score: {score:.1f}/10 | Design: {design} | N: {sample_size} | Year: {year}"), 0, 1)
            pdf.ln(3)
            pdf.set_text_color(51, 65, 85)
            
    pdf.output(output_path)
    return output_path
