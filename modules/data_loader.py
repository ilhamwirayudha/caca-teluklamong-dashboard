"""
Modul Pemuat Data & Export File
Terminal Teluk Lamong - Pelindo

Menyediakan fungsi pembacaan cepat file Excel/CSV dengan caching Streamlit,
serta generator file Excel hasil ekspor (data-only).
"""

from io import BytesIO
import pandas as pd
import streamlit as st
from openpyxl.styles import Font


@st.cache_data(show_spinner=False, max_entries=3, ttl=1800)
def baca_file(file_bytes: bytes, filename: str, sheet_name=None):
    """Membaca file data operasional (.xlsx, .xls, .csv) dengan cepat dan efisien."""
    if filename.lower().endswith(".csv"):
        return {"__csv__": pd.read_csv(BytesIO(file_bytes))}
    xls = pd.ExcelFile(BytesIO(file_bytes))
    if sheet_name is not None:
        return {sheet_name: xls.parse(sheet_name)}
    return {name: xls.parse(name) for name in xls.sheet_names}


def build_excel_data_only(out_df: pd.DataFrame) -> bytes:
    """
    Membangun file Excel hasil analisis (.xlsx) ringan dan cepat (hanya sheet Data),
    menggunakan openpyxl dengan header tebal dan freeze pane.
    """
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        out_df.to_excel(writer, index=False, sheet_name="Data")
        ws = writer.sheets["Data"]
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
    bio.seek(0)
    return bio.getvalue()
