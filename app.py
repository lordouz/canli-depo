from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
from sqlalchemy import select, and_

from openpyxl import Workbook
from openpyxl.styles import (
    Font,
    PatternFill,
    Border,
    Side,
    Alignment
)
from openpyxl.utils import get_column_letter

from database import SessionLocal, Location, Movement, init_db


# ============================================================
# SAYFA AYARLARI
# ============================================================

st.set_page_config(
    page_title="Canlı Depo Haritası",
    page_icon="🏭",
    layout="wide"
)

init_db()


# ============================================================
# DURUM / RENK TANIMLARI
# ============================================================

STATUS_COLORS = {
    "Boş": "#E5E7EB",
    "PET": "#60A5FA",
    "rPET": "#4ADE80",
    "Hammadde": "#FACC15",
    "Bloke": "#F87171",
    "Rezerve": "#A78BFA",
}


MOVEMENT_TYPES = [
    "Giriş",
    "Çıkış",
    "Transfer",
    "Sayım Düzeltme",
    "Bloke",
    "Bloke Kaldırma",
    "Rezervasyon",
    "Ürün Değişimi",
    "Lot Değişimi",
    "Diğer",
]


# ============================================================
# SESSION STATE
# ============================================================

if "selected_locations" not in st.session_state:

    st.session_state.selected_locations = []


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    div[data-testid="stButton"] button {
        min-height: 38px;
        border-radius: 7px;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# VERİTABANI FONKSİYONLARI
# ============================================================

def get_locations():

    with SessionLocal() as db:

        locations = db.execute(
            select(Location).order_by(
                Location.row_no,
                Location.col_no
            )
        ).scalars().all()

        return locations


def get_location(code):

    with SessionLocal() as db:

        location = db.execute(
            select(Location).where(
                Location.code == code
            )
        ).scalar_one()

        return location


# ============================================================
# TEK LOKASYON KAYDET
# ============================================================

def save_location(
    code,
    status,
    product,
    lot,
    quantity,
    movement_type,
    note,
    changed_by
):

    with SessionLocal() as db:

        location = db.execute(
            select(Location).where(
                Location.code == code
            )
        ).scalar_one()


        old_status = location.status

        old_product = location.product

        old_lot = location.lot

        old_quantity = float(
            location.quantity_kg or 0
        )


        if status == "Boş":

            product = None
            lot = None
            quantity = 0


        quantity = float(
            quantity or 0
        )


        clean_product = (
            product.strip()
            if product
            else None
        )

        clean_lot = (
            lot.strip()
            if lot
            else None
        )

        clean_note = (
            note.strip()
            if note
            else None
        )

        clean_user = (
            changed_by.strip()
            if changed_by
            else None
        )


        location.status = status

        location.product = clean_product

        location.lot = clean_lot

        location.quantity_kg = quantity

        location.updated_at = datetime.now()


        movement = Movement(

            location_id=location.id,

            location_code=location.code,

            movement_type=movement_type,

            old_status=old_status,

            new_status=status,

            old_product=old_product,

            new_product=clean_product,

            old_lot=old_lot,

            new_lot=clean_lot,

            old_quantity_kg=old_quantity,

            new_quantity_kg=quantity,

            quantity_delta_kg=(
                quantity - old_quantity
            ),

            note=clean_note,

            changed_by=clean_user,

            created_at=datetime.now()
        )


        db.add(
            movement
        )

        db.commit()


# ============================================================
# TOPLU LOKASYON KAYDET
# ============================================================

def save_multiple_locations(
    location_codes,
    status,
    product,
    lot,
    total_quantity,
    movement_type,
    note,
    changed_by
):

    if not location_codes:
        return


    location_count = len(
        location_codes
    )


    quantity_per_location = (
        float(total_quantity)
        / location_count
    )


    for code in location_codes:

        save_location(

            code=code,

            status=status,

            product=product,

            lot=lot,

            quantity=quantity_per_location,

            movement_type=movement_type,

            note=note,

            changed_by=changed_by

        )


# ============================================================
# HAREKET RAPORU
# ============================================================

def movement_report(
    start_date,
    end_date,
    location,
    product,
    lot,
    movement_type
):

    with SessionLocal() as db:

        stmt = select(
            Movement
        ).where(

            and_(

                Movement.created_at >=
                datetime.combine(
                    start_date,
                    datetime.min.time()
                ),

                Movement.created_at <=
                datetime.combine(
                    end_date,
                    datetime.max.time()
                )

            )

        ).order_by(
            Movement.created_at.desc()
        )


        if location:

            stmt = stmt.where(
                Movement.location_code.contains(
                    location
                )
            )


        if product:

            stmt = stmt.where(
                Movement.new_product.contains(
                    product
                )
            )


        if lot:

            stmt = stmt.where(
                Movement.new_lot.contains(
                    lot
                )
            )


        if movement_type != "Tümü":

            stmt = stmt.where(
                Movement.movement_type
                == movement_type
            )


        rows = db.execute(
            stmt
        ).scalars().all()


    data = []


    for row in rows:

        data.append({

            "Tarih / Saat":
                row.created_at,

            "Lokasyon":
                row.location_code,

            "Hareket Tipi":
                row.movement_type,

            "Eski Durum":
                row.old_status,

            "Yeni Durum":
                row.new_status,

            "Eski Ürün":
                row.old_product,

            "Yeni Ürün":
                row.new_product,

            "Eski Lot":
                row.old_lot,

            "Yeni Lot":
                row.new_lot,

            "Eski Miktar (kg)":
                row.old_quantity_kg,

            "Yeni Miktar (kg)":
                row.new_quantity_kg,

            "Fark (kg)":
                row.quantity_delta_kg,

            "Not":
                row.note,

            "Değiştiren":
                row.changed_by

        })


    return pd.DataFrame(
        data
    )


# ============================================================
# PROFESYONEL EXCEL RAPORU
# ============================================================

def create_professional_excel_report(
    report,
    start_date,
    end_date,
    location_filter,
    product_filter,
    lot_filter,
    movement_filter
):

    output = BytesIO()

    workbook = Workbook()

    ws = workbook.active

    ws.title = "Hareketler"

    summary_ws = workbook.create_sheet(
        "Özet"
    )


    # ========================================================
    # RENKLER
    # ========================================================

    dark_blue = "1F4E78"

    medium_blue = "5B9BD5"

    light_blue = "D9EAF7"

    light_green = "E2F0D9"

    light_red = "FCE4D6"

    light_gray = "E7E6E6"

    white = "FFFFFF"

    border_color = "B7B7B7"


    thin_border = Border(

        left=Side(
            style="thin",
            color=border_color
        ),

        right=Side(
            style="thin",
            color=border_color
        ),

        top=Side(
            style="thin",
            color=border_color
        ),

        bottom=Side(
            style="thin",
            color=border_color
        )

    )


    # ========================================================
    # HAREKETLER SAYFASI - BAŞLIK
    # ========================================================

    ws.merge_cells(
        "A1:N2"
    )

    ws["A1"] = (
        "DEPO HAREKET RAPORU"
    )

    ws["A1"].font = Font(
        size=18,
        bold=True,
        color=white
    )

    ws["A1"].fill = PatternFill(
        "solid",
        fgColor=dark_blue
    )

    ws["A1"].alignment = Alignment(
        horizontal="center",
        vertical="center"
    )


    # ========================================================
    # RAPOR BİLGİLERİ
    # ========================================================

    ws["A4"] = "Rapor Tarihi"

    ws["B4"] = datetime.now().strftime(
        "%d.%m.%Y %H:%M"
    )


    ws["D4"] = "Başlangıç"

    ws["E4"] = start_date.strftime(
        "%d.%m.%Y"
    )


    ws["G4"] = "Bitiş"

    ws["H4"] = end_date.strftime(
        "%d.%m.%Y"
    )


    for cell in [
        "A4",
        "D4",
        "G4"
    ]:

        ws[cell].font = Font(
            bold=True,
            color=white
        )

        ws[cell].fill = PatternFill(
            "solid",
            fgColor=medium_blue
        )

        ws[cell].border = thin_border


    # ========================================================
    # FİLTRELER
    # ========================================================

    ws["A6"] = "Lokasyon"

    ws["B6"] = (
        location_filter
        or "Tümü"
    )


    ws["D6"] = "Ürün"

    ws["E6"] = (
        product_filter
        or "Tümü"
    )


    ws["G6"] = "Lot"

    ws["H6"] = (
        lot_filter
        or "Tümü"
    )


    ws["J6"] = "Hareket Tipi"

    ws["K6"] = (
        movement_filter
    )


    for cell in [
        "A6",
        "D6",
        "G6",
        "J6"
    ]:

        ws[cell].font = Font(
            bold=True
        )

        ws[cell].fill = PatternFill(
            "solid",
            fgColor=light_gray
        )

        ws[cell].border = thin_border


    # ========================================================
    # KPI HESAPLARI
    # ========================================================

    total_positive = report.loc[
        report["Fark (kg)"] > 0,
        "Fark (kg)"
    ].sum()


    total_negative = -report.loc[
        report["Fark (kg)"] < 0,
        "Fark (kg)"
    ].sum()


    ws["A8"] = "Toplam Hareket"

    ws["B8"] = len(
        report
    )


    ws["D8"] = "Toplam Giriş / Artış"

    ws["E8"] = total_positive


    ws["G8"] = "Toplam Çıkış / Azalış"

    ws["H8"] = total_negative


    ws["A8"].fill = PatternFill(
        "solid",
        fgColor=light_blue
    )

    ws["D8"].fill = PatternFill(
        "solid",
        fgColor=light_green
    )

    ws["G8"].fill = PatternFill(
        "solid",
        fgColor=light_red
    )


    for cell in [
        "A8",
        "D8",
        "G8"
    ]:

        ws[cell].font = Font(
            bold=True
        )

        ws[cell].border = thin_border


    ws["B8"].border = thin_border

    ws["E8"].border = thin_border

    ws["H8"].border = thin_border


    ws["E8"].number_format = (
        '#,##0.00 "kg"'
    )

    ws["H8"].number_format = (
        '#,##0.00 "kg"'
    )


    # ========================================================
    # TABLO BAŞLIKLARI
    # ========================================================

    table_start_row = 11

    headers = list(
        report.columns
    )


    for column_index, header in enumerate(
        headers,
        start=1
    ):

        cell = ws.cell(
            row=table_start_row,
            column=column_index
        )

        cell.value = header

        cell.font = Font(
            bold=True,
            color=white
        )

        cell.fill = PatternFill(
            "solid",
            fgColor=dark_blue
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

        cell.border = thin_border


    # ========================================================
    # TABLO VERİLERİ
    # ========================================================

    for row_index, row in enumerate(
        report.itertuples(
            index=False
        ),
        start=table_start_row + 1
    ):

        for column_index, value in enumerate(
            row,
            start=1
        ):

            cell = ws.cell(
                row=row_index,
                column=column_index
            )

            cell.value = value

            cell.border = thin_border

            cell.alignment = Alignment(
                vertical="center"
            )


            header_name = headers[
                column_index - 1
            ]


            if header_name == "Tarih / Saat":

                cell.number_format = (
                    "dd.mm.yyyy hh:mm"
                )


            if header_name in [
                "Eski Miktar (kg)",
                "Yeni Miktar (kg)",
                "Fark (kg)"
            ]:

                cell.number_format = (
                    '#,##0.00'
                )


            if header_name == "Fark (kg)":

                try:

                    numeric_value = float(
                        value or 0
                    )

                except Exception:

                    numeric_value = 0


                if numeric_value > 0:

                    cell.fill = PatternFill(
                        "solid",
                        fgColor=light_green
                    )


                elif numeric_value < 0:

                    cell.fill = PatternFill(
                        "solid",
                        fgColor=light_red
                    )


    # ========================================================
    # OTOMATİK FİLTRE
    # ========================================================

    last_row = (
        table_start_row
        + len(report)
    )

    last_column = len(
        headers
    )


    if last_row >= table_start_row:

        ws.auto_filter.ref = (

            f"A{table_start_row}:"
            f"{get_column_letter(last_column)}"
            f"{last_row}"

        )


    # ========================================================
    # SABİTLEME
    # ========================================================

    ws.freeze_panes = (
        f"A{table_start_row + 1}"
    )


    # ========================================================
    # KOLON GENİŞLİKLERİ
    # ========================================================

    widths = {

        "A": 20,

        "B": 14,

        "C": 20,

        "D": 16,

        "E": 16,

        "F": 22,

        "G": 22,

        "H": 20,

        "I": 20,

        "J": 18,

        "K": 18,

        "L": 16,

        "M": 38,

        "N": 22

    }


    for column_letter, width in (
        widths.items()
    ):

        ws.column_dimensions[
            column_letter
        ].width = width


    ws.row_dimensions[1].height = 28

    ws.sheet_view.showGridLines = False


    # ========================================================
    # ÖZET SAYFASI
    # ========================================================

    summary_ws.merge_cells(
        "A1:D2"
    )


    summary_ws["A1"] = (
        "DEPO HAREKET RAPORU - ÖZET"
    )


    summary_ws["A1"].font = Font(
        size=18,
        bold=True,
        color=white
    )


    summary_ws["A1"].fill = PatternFill(
        "solid",
        fgColor=dark_blue
    )


    summary_ws["A1"].alignment = Alignment(
        horizontal="center",
        vertical="center"
    )


    # ========================================================
    # ÖZET RAPOR BİLGİLERİ
    # ========================================================

    summary_ws["A4"] = (
        "Rapor Tarihi"
    )

    summary_ws["B4"] = (
        datetime.now().strftime(
            "%d.%m.%Y %H:%M"
        )
    )


    summary_ws["A5"] = (
        "Rapor Dönemi"
    )

    summary_ws["B5"] = (
        f"{start_date.strftime('%d.%m.%Y')} "
        f"- "
        f"{end_date.strftime('%d.%m.%Y')}"
    )


    summary_ws["A7"] = (
        "Toplam Hareket"
    )

    summary_ws["B7"] = len(
        report
    )


    summary_ws["A8"] = (
        "Toplam Giriş / Artış"
    )

    summary_ws["B8"] = (
        total_positive
    )


    summary_ws["A9"] = (
        "Toplam Çıkış / Azalış"
    )

    summary_ws["B9"] = (
        total_negative
    )


    summary_ws["B8"].number_format = (
        '#,##0.00 "kg"'
    )

    summary_ws["B9"].number_format = (
        '#,##0.00 "kg"'
    )


    for row in [
        4,
        5,
        7,
        8,
        9
    ]:

        summary_ws[
            f"A{row}"
        ].font = Font(
            bold=True
        )

        summary_ws[
            f"A{row}"
        ].fill = PatternFill(
            "solid",
            fgColor=light_blue
        )

        summary_ws[
            f"A{row}"
        ].border = thin_border

        summary_ws[
            f"B{row}"
        ].border = thin_border


    # ========================================================
    # HAREKET TİPİ ÖZETİ
    # ========================================================

    summary_ws["A12"] = (
        "Hareket Tipi"
    )

    summary_ws["B12"] = (
        "Adet"
    )


    for cell_name in [
        "A12",
        "B12"
    ]:

        summary_ws[
            cell_name
        ].font = Font(
            bold=True,
            color=white
        )

        summary_ws[
            cell_name
        ].fill = PatternFill(
            "solid",
            fgColor=dark_blue
        )

        summary_ws[
            cell_name
        ].border = thin_border


    movement_counts = (

        report[
            "Hareket Tipi"
        ]
        .fillna(
            "Belirsiz"
        )
        .value_counts()

    )


    summary_row = 13


    for movement_name, count in (
        movement_counts.items()
    ):

        summary_ws.cell(
            row=summary_row,
            column=1,
            value=movement_name
        )

        summary_ws.cell(
            row=summary_row,
            column=2,
            value=count
        )


        summary_ws.cell(
            row=summary_row,
            column=1
        ).border = thin_border


        summary_ws.cell(
            row=summary_row,
            column=2
        ).border = thin_border


        summary_row += 1


    # ========================================================
    # ÜRÜN BAZLI ÖZET
    # ========================================================

    summary_ws["D12"] = (
        "Ürün"
    )

    summary_ws["E12"] = (
        "Hareket Adedi"
    )


    for cell_name in [
        "D12",
        "E12"
    ]:

        summary_ws[
            cell_name
        ].font = Font(
            bold=True,
            color=white
        )

        summary_ws[
            cell_name
        ].fill = PatternFill(
            "solid",
            fgColor=dark_blue
        )

        summary_ws[
            cell_name
        ].border = thin_border


    product_counts = (

        report[
            "Yeni Ürün"
        ]
        .fillna(
            "Boş"
        )
        .value_counts()

    )


    product_row = 13


    for product_name, count in (
        product_counts.items()
    ):

        summary_ws.cell(
            row=product_row,
            column=4,
            value=product_name
        )

        summary_ws.cell(
            row=product_row,
            column=5,
            value=count
        )


        summary_ws.cell(
            row=product_row,
            column=4
        ).border = thin_border


        summary_ws.cell(
            row=product_row,
            column=5
        ).border = thin_border


        product_row += 1


    summary_ws.column_dimensions[
        "A"
    ].width = 28

    summary_ws.column_dimensions[
        "B"
    ].width = 22

    summary_ws.column_dimensions[
        "C"
    ].width = 6

    summary_ws.column_dimensions[
        "D"
    ].width = 28

    summary_ws.column_dimensions[
        "E"
    ].width = 18


    summary_ws.sheet_view.showGridLines = False


    # ========================================================
    # DOSYAYI KAYDET
    # ========================================================

    workbook.save(
        output
    )

    output.seek(
        0
    )

    return output


# ============================================================
# BAŞLIK
# ============================================================

st.title(
    "🏭 Canlı Depo Haritası"
)

st.caption(
    "Lokasyon, ürün, lot ve depo hareket takip sistemi"
)


# ============================================================
# VERİLER
# ============================================================

locations = get_locations()


total_locations = len(
    locations
)


filled_locations = sum(

    1

    for location in locations

    if location.status != "Boş"

)


empty_locations = (
    total_locations
    - filled_locations
)


blocked_locations = sum(

    1

    for location in locations

    if location.status == "Bloke"

)


reserved_locations = sum(

    1

    for location in locations

    if location.status == "Rezerve"

)


if total_locations:

    occupancy_rate = (

        filled_locations
        / total_locations
        * 100

    )

else:

    occupancy_rate = 0


# ============================================================
# KPI
# ============================================================

k1, k2, k3, k4 = st.columns(
    4
)


k1.metric(
    "Toplam Lokasyon",
    total_locations
)


k2.metric(
    "Dolu Lokasyon",
    filled_locations
)


k3.metric(
    "Boş Lokasyon",
    empty_locations
)


k4.metric(
    "Doluluk Oranı",
    f"%{occupancy_rate:.1f}"
)


st.caption(

    f"🔴 Bloke: {blocked_locations}"
    f"   •   "
    f"🟣 Rezerve: {reserved_locations}"

)


# ============================================================
# RENK AÇIKLAMASI
# ============================================================

legend_columns = st.columns(
    len(STATUS_COLORS)
)


for index, (
    status_name,
    status_color
) in enumerate(
    STATUS_COLORS.items()
):

    with legend_columns[index]:

        st.html(

            f"""
            <div style="
                background-color:{status_color};
                border:1px solid #9CA3AF;
                padding:8px;
                border-radius:7px;
                text-align:center;
                font-weight:700;
                color:#111827;
                margin-bottom:8px;
            ">
                {status_name}
            </div>
            """

        )


# ============================================================
# SEKME
# ============================================================

tab_map, tab_report = st.tabs(

    [
        "🗺️ Canlı Depo Haritası",
        "📊 Hareket Raporu"
    ]

)


# ============================================================
# CANLI DEPO HARİTASI
# ============================================================

with tab_map:


    locations_by_code = {

        location.code:
            location

        for location in locations

    }


    # ========================================================
    # ÜST BİLGİ / SEÇİMLER
    # ========================================================

    top1, top2, top3 = st.columns(
        [2, 1, 1]
    )


    with top1:

        st.subheader(
            "Depo Yerleşimi"
        )


        selected_count = len(
            st.session_state.selected_locations
        )


        if selected_count == 0:

            st.info(
                "İşlem yapmak istediğin lokasyonları seç."
            )

        else:

            st.success(

                f"{selected_count} lokasyon seçildi: "
                + ", ".join(
                    st.session_state.selected_locations
                )

            )


    with top2:

        if st.button(
            "✅ Tümünü Seç",
            use_container_width=True
        ):

            st.session_state.selected_locations = [

                location.code

                for location
                in locations

            ]

            st.rerun()


    with top3:

        if st.button(
            "❌ Seçimi Temizle",
            use_container_width=True
        ):

            st.session_state.selected_locations = []

            st.rerun()


    # ========================================================
    # HARİTA
    # ========================================================

    for row_number in range(
        10
    ):


        columns = st.columns(
            10,
            gap="small"
        )


        for column_number in range(
            10
        ):


            code = (

                f"{chr(65 + row_number)}-"
                f"{column_number + 1:02d}"

            )


            location = (
                locations_by_code[
                    code
                ]
            )


            status = (
                location.status
                or "Boş"
            )


            color = STATUS_COLORS.get(
                status,
                "#E5E7EB"
            )


            is_selected = (
                code
                in st.session_state.selected_locations
            )


            if status == "Boş":

                product_text = "BOŞ"

                lot_text = ""

                quantity_text = ""

            else:

                product_text = (
                    location.product
                    or status
                )

                lot_text = (
                    location.lot
                    or "-"
                )

                quantity_text = (
                    f"{float(location.quantity_kg or 0):,.0f} kg"
                )


            if is_selected:

                border = (
                    "4px solid #111827"
                )

                selected_text = (
                    "✓ SEÇİLDİ"
                )

            else:

                border = (
                    "1px solid #6B7280"
                )

                selected_text = ""


            with columns[
                column_number
            ]:


                st.html(

                    f"""
                    <div style="
                        background-color:{color};
                        border:{border};
                        border-radius:9px;
                        height:112px;
                        padding:7px 4px;
                        text-align:center;
                        color:#111827;
                        display:flex;
                        flex-direction:column;
                        justify-content:center;
                        align-items:center;
                        overflow:hidden;
                    ">

                        <div style="
                            font-size:16px;
                            font-weight:900;
                            line-height:1.15;
                        ">
                            {code}
                        </div>

                        <div style="
                            font-size:12px;
                            font-weight:800;
                            width:100%;
                            overflow:hidden;
                            white-space:nowrap;
                            text-overflow:ellipsis;
                            margin-top:3px;
                        ">
                            {product_text}
                        </div>

                        <div style="
                            font-size:10px;
                            width:100%;
                            overflow:hidden;
                            white-space:nowrap;
                            text-overflow:ellipsis;
                            margin-top:2px;
                        ">
                            {lot_text}
                        </div>

                        <div style="
                            font-size:11px;
                            font-weight:700;
                            margin-top:3px;
                        ">
                            {quantity_text}
                        </div>

                        <div style="
                            font-size:9px;
                            font-weight:900;
                            margin-top:4px;
                        ">
                            {selected_text}
                        </div>

                    </div>
                    """

                )


                button_text = (
                    "ÇIKAR"
                    if is_selected
                    else "SEÇ"
                )


                if st.button(

                    button_text,

                    key=f"select_{code}",

                    use_container_width=True

                ):


                    if is_selected:

                        st.session_state.selected_locations.remove(
                            code
                        )

                    else:

                        st.session_state.selected_locations.append(
                            code
                        )


                    st.rerun()


    # ========================================================
    # TOPLU İŞLEM
    # ========================================================

    st.divider()


    selected_codes = (
        st.session_state.selected_locations
    )


    if not selected_codes:

        st.warning(
            "Toplu işlem yapmak için en az bir lokasyon seç."
        )


    else:


        st.subheader(
            "📦 Toplu Lokasyon İşlemi"
        )


        st.caption(

            f"{len(selected_codes)} lokasyon "
            f"üzerinde işlem yapılacak."

        )


        left, middle, right = st.columns(
            [1.2, 1.2, 1]
        )


        with left:


            selected_status = st.selectbox(

                "Durum",

                list(
                    STATUS_COLORS.keys()
                ),

                index=1,

                key="bulk_status"

            )


            selected_product = st.text_input(

                "Ürün",

                placeholder="Örn: GS840",

                key="bulk_product"

            )


            selected_lot = st.text_input(

                "Lot",

                placeholder="Örn: 2608B021",

                key="bulk_lot"

            )


        with middle:


            total_quantity = st.number_input(

                "TOPLAM Miktar (kg)",

                min_value=0.0,

                value=0.0,

                step=100.0,

                key="bulk_quantity"

            )


            selected_movement_type = st.selectbox(

                "Hareket Tipi",

                MOVEMENT_TYPES,

                key="bulk_movement_type"

            )


            changed_by = st.text_input(

                "İşlemi Yapan",

                placeholder=(
                    "Ad Soyad / Kullanıcı"
                ),

                key="bulk_changed_by"

            )


        with right:


            movement_note = st.text_area(

                "Hareket Açıklaması",

                placeholder=(
                    "Örn: Üretimden depoya toplu giriş."
                ),

                height=108,

                key="bulk_note"

            )


        # ====================================================
        # DAĞILIM HESABI
        # ====================================================

        location_count = len(
            selected_codes
        )


        if location_count > 0:

            quantity_per_location = (

                total_quantity
                / location_count

            )

        else:

            quantity_per_location = 0


        # ====================================================
        # ÖN İZLEME
        # ====================================================

        st.markdown(
            "### 📋 Dağılım Ön İzleme"
        )


        p1, p2, p3 = st.columns(
            3
        )


        p1.metric(
            "Seçilen Lokasyon",
            location_count
        )


        p2.metric(
            "Toplam Miktar",
            f"{total_quantity:,.2f} kg"
        )


        p3.metric(
            "Lokasyon Başına",
            f"{quantity_per_location:,.2f} kg"
        )


        preview_data = []


        for code in selected_codes:

            preview_data.append({

                "Lokasyon":
                    code,

                "Durum":
                    selected_status,

                "Ürün":
                    selected_product,

                "Lot":
                    selected_lot,

                "Miktar (kg)":
                    round(
                        quantity_per_location,
                        2
                    )

            })


        preview_df = pd.DataFrame(
            preview_data
        )


        st.dataframe(

            preview_df,

            use_container_width=True,

            hide_index=True

        )


        # ====================================================
        # KAYDET
        # ====================================================

        if st.button(

            "💾 TOPLU HAREKETİ KAYDET",

            type="primary",

            use_container_width=True

        ):


            if (
                selected_status != "Boş"
                and not selected_product.strip()
            ):

                st.error(
                    "Ürün bilgisini gir."
                )


            elif (
                selected_status != "Boş"
                and not selected_lot.strip()
            ):

                st.error(
                    "Lot bilgisini gir."
                )


            elif (
                selected_status != "Boş"
                and total_quantity <= 0
            ):

                st.error(
                    "Toplam miktar 0'dan büyük olmalıdır."
                )


            else:


                save_multiple_locations(

                    location_codes=selected_codes,

                    status=selected_status,

                    product=selected_product,

                    lot=selected_lot,

                    total_quantity=total_quantity,

                    movement_type=selected_movement_type,

                    note=movement_note,

                    changed_by=changed_by

                )


                st.session_state.selected_locations = []


                st.success(

                    f"{location_count} lokasyona "
                    f"toplam {total_quantity:,.2f} kg "
                    f"başarıyla dağıtıldı."

                )


                st.rerun()


# ============================================================
# HAREKET RAPORU
# ============================================================

with tab_report:


    st.subheader(
        "📊 Depo Hareket Raporu"
    )


    filter1, filter2, filter3, filter4 = st.columns(
        4
    )


    with filter1:

        start_date = st.date_input(

            "Başlangıç Tarihi",

            value=(
                datetime.now().date()
                - timedelta(days=30)
            ),

            key="report_start_date"

        )


    with filter2:

        end_date = st.date_input(

            "Bitiş Tarihi",

            value=datetime.now().date(),

            key="report_end_date"

        )


    with filter3:

        location_filter = st.text_input(

            "Lokasyon",

            placeholder="Örn: J-04",

            key="report_location"

        )


    with filter4:

        movement_filter = st.selectbox(

            "Hareket Tipi",

            [
                "Tümü"
            ]
            + MOVEMENT_TYPES,

            key="report_movement"

        )


    filter5, filter6 = st.columns(
        2
    )


    with filter5:

        product_filter = st.text_input(

            "Ürün Filtresi",

            placeholder="Örn: GS840",

            key="report_product"

        )


    with filter6:

        lot_filter = st.text_input(

            "Lot Filtresi",

            placeholder="Örn: 2608B021",

            key="report_lot"

        )


    # ========================================================
    # RAPORU GETİR
    # ========================================================

    report = movement_report(

        start_date=start_date,

        end_date=end_date,

        location=location_filter,

        product=product_filter,

        lot=lot_filter,

        movement_type=movement_filter

    )


    # ========================================================
    # RAPOR SONUÇ
    # ========================================================

    if report.empty:


        st.info(
            "Seçilen filtrelere uygun hareket kaydı bulunamadı."
        )


    else:


        total_positive = report.loc[

            report[
                "Fark (kg)"
            ] > 0,

            "Fark (kg)"

        ].sum()


        total_negative = -report.loc[

            report[
                "Fark (kg)"
            ] < 0,

            "Fark (kg)"

        ].sum()


        r1, r2, r3 = st.columns(
            3
        )


        r1.metric(

            "Toplam Hareket",

            len(
                report
            )

        )


        r2.metric(

            "Toplam Giriş / Artış",

            f"{total_positive:,.2f} kg"

        )


        r3.metric(

            "Toplam Çıkış / Azalış",

            f"{total_negative:,.2f} kg"

        )


        st.dataframe(

            report,

            use_container_width=True,

            hide_index=True

        )


        # ====================================================
        # PROFESYONEL EXCEL RAPORU
        # ====================================================

        excel_report = create_professional_excel_report(

            report=report,

            start_date=start_date,

            end_date=end_date,

            location_filter=location_filter,

            product_filter=product_filter,

            lot_filter=lot_filter,

            movement_filter=movement_filter

        )


        st.download_button(

            "📊 PROFESYONEL EXCEL HAREKET RAPORUNU İNDİR",

            data=excel_report,

            file_name=(

                f"Depo_Hareket_Raporu_"
                f"{start_date}_"
                f"{end_date}.xlsx"

            ),

            mime=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),

            type="primary",

            use_container_width=True

        )
