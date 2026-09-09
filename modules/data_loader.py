"""
Modul Pemuat Data & Export File
Terminal Teluk Lamong - Pelindo

Menyediakan fungsi pembacaan streaming file Excel/CSV dengan pelaporan progres riil,
hemat memori (read_only mode openpyxl), serta generator file Excel hasil ekspor.
"""

from io import BytesIO
import time
import openpyxl
from openpyxl.styles import Font
import pandas as pd
import streamlit as st


def baca_file(file_bytes: bytes, filename: str, progress_callback=None) -> dict[str, pd.DataFrame]:
    """
    Membaca file data operasional (.xlsx, .xls, .csv) dengan pelaporan progres riil
    dan efisiensi memori tingkat tinggi (streaming SAX parser).
    """
    fname_lower = filename.lower()

    # ------------------------------------------------------------
    # 1. Penanganan File CSV
    # ------------------------------------------------------------
    if fname_lower.endswith(".csv"):
        if progress_callback:
            progress_callback(10, "Membaca file CSV operasional...", "Menginisialisasi parser data...")

        total_bytes = len(file_bytes)
        # Jika CSV berukuran besar (> 8 MB), baca dalam batch/chunk
        if total_bytes > 8 * 1024 * 1024:
            bio = BytesIO(file_bytes)
            chunks = []
            chunk_size = 20000
            total_rows = 0
            last_time = time.time()

            for chunk in pd.read_csv(bio, chunksize=chunk_size):
                chunks.append(chunk)
                total_rows += len(chunk)
                now = time.time()
                if now - last_time > 0.18:
                    last_time = now
                    # Estimasi progres berbasis chunk
                    pct = min(94, 15 + int((total_rows * 120) / total_bytes * 75))
                    if progress_callback:
                        progress_callback(
                            pct,
                            f"Membaca data CSV ({total_rows:,} baris)...",
                            f"{total_rows:,} baris dimuat ke memori",
                        )

            df = pd.concat(chunks, ignore_index=True)
        else:
            if progress_callback:
                progress_callback(30, "Mengekstrak baris data CSV...", "Memproses tabel data...")
            df = pd.read_csv(BytesIO(file_bytes))

        if progress_callback:
            progress_callback(
                100,
                "File CSV operasional siap dianalisis!",
                f"{len(df):,} baris data berhasil dimuat",
            )
        return {"__csv__": df}

    # ------------------------------------------------------------
    # 2. Penanganan File Excel Modern (.xlsx, .xlsm) via openpyxl streaming
    # ------------------------------------------------------------
    if fname_lower.endswith((".xlsx", ".xlsm")):
        if progress_callback:
            progress_callback(5, "Menganalisis struktur workbook Excel...", "Membuka lembar kerja...")

        bio = BytesIO(file_bytes)
        wb = openpyxl.load_workbook(bio, read_only=True, data_only=True)
        sheet_names = wb.sheetnames
        num_sheets = len(sheet_names)

        sheets_dict = {}
        last_update = 0.0

        for s_idx, sname in enumerate(sheet_names):
            ws = wb[sname]
            max_row = ws.max_row  # Mendapatkan total baris lembar kerja
            base_pct = int(8 + (s_idx / num_sheets) * 88)
            sheet_weight = 88.0 / num_sheets

            if progress_callback:
                target_info = f"{max_row:,} total baris" if max_row else "memulai baris..."
                progress_callback(
                    base_pct,
                    f"Mengekstrak sheet '{sname}' ({s_idx + 1}/{num_sheets})...",
                    target_info,
                )

            rows_iter = ws.iter_rows(values_only=True)
            try:
                header = next(rows_iter)
            except StopIteration:
                sheets_dict[sname] = pd.DataFrame()
                continue

            # Bersihkan nama kolom header
            clean_headers = [
                str(c).strip() if c is not None and str(c).strip() != "" else f"Col_{i}"
                for i, c in enumerate(header)
            ]

            rows = []
            last_pct = base_pct
            for r_idx, row in enumerate(rows_iter):
                rows.append(row)
                now = time.time()
                # Batasi frekuensi callback agar stabil, mulus, dan tidak flickering
                if now - last_update > 0.20:
                    if max_row and max_row > 1:
                        sheet_prog = min(1.0, (r_idx + 1) / (max_row - 1))
                    else:
                        sheet_prog = min(0.95, (r_idx + 1) / 100000)

                    current_pct = int(base_pct + sheet_prog * sheet_weight)
                    current_pct = min(96, max(base_pct, current_pct))

                    if current_pct > last_pct:
                        last_update = now
                        last_pct = current_pct
                        if progress_callback:
                            row_info = f"Baris {r_idx + 1:,}" + (f" / {max_row:,}" if max_row else "")
                            progress_callback(
                                current_pct,
                                f"Mengekstrak '{sname}'...",
                                row_info,
                            )

            df = pd.DataFrame(rows, columns=clean_headers)
            sheets_dict[sname] = df

        wb.close()

        if progress_callback:
            total_all_rows = sum(len(df) for df in sheets_dict.values())
            progress_callback(
                100,
                "Data siap dianalisis!",
                f"{total_all_rows:,} baris siap",
            )
        return sheets_dict

    # ------------------------------------------------------------
    # 3. Penanganan File Excel Lama (.xls)
    # ------------------------------------------------------------
    if progress_callback:
        progress_callback(10, "Membaca file Excel (.xls)...", "Mengekstrak tabel...")
    xls = pd.ExcelFile(BytesIO(file_bytes))
    sheets_dict = {}
    sheet_names = xls.sheet_names
    num_sheets = len(sheet_names)

    for i, sname in enumerate(sheet_names):
        pct = min(95, int(15 + (i / num_sheets) * 80))
        if progress_callback:
            progress_callback(pct, f"Membaca sheet '{sname}'...", f"Sheet {i + 1} dari {num_sheets}")
        sheets_dict[sname] = xls.parse(sname)

    if progress_callback:
        total_rows = sum(len(d) for d in sheets_dict.values())
        progress_callback(100, "File Excel siap dianalisis!", f"{total_rows:,} baris berhasil dimuat")
    return sheets_dict


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
