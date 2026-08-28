from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import select, and_

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
# DURUMLAR / RENKLER
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
        padding-top: 1.3rem;
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

        return db.execute(
            select(Location).order_by(
                Location.row_no,
                Location.col_no
            )
        ).scalars().all()


def get_location(code):

    with SessionLocal() as db:

        return db.execute(
            select(Location).where(
                Location.code == code
            )
        ).scalar_one()


# ============================================================
# TEK LOKASYON HAREKET KAYDI
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


        # ----------------------------------------------------
        # BOŞ DURUM
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # LOKASYON GÜNCELLE
        # ----------------------------------------------------

        location.status = status
        location.product = clean_product
        location.lot = clean_lot
        location.quantity_kg = quantity
        location.updated_at = datetime.now()


        # ----------------------------------------------------
        # HAREKET KAYDI
        # ----------------------------------------------------

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

            note=(
                note.strip()
                if note
                else None
            ),

            changed_by=(
                changed_by.strip()
                if changed_by
                else None
            ),

            created_at=datetime.now()
        )


        db.add(movement)

        db.commit()


# ============================================================
# TOPLU LOKASYON KAYDI
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


    # Toplam miktarı seçilen lokasyonlara böl
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

    for x in locations

    if x.status != "Boş"

)


empty_locations = (
    total_locations
    - filled_locations
)


blocked_locations = sum(

    1

    for x in locations

    if x.status == "Bloke"

)


reserved_locations = sum(

    1

    for x in locations

    if x.status == "Rezerve"

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
# ANA SEKMELER
# ============================================================

tab_map, tab_report = st.tabs(

    [
        "🗺️ Canlı Depo Haritası",
        "📊 Hareket Raporu"
    ]

)


# ============================================================
# CANLI HARİTA
# ============================================================

with tab_map:


    locations_by_code = {

        location.code:
            location

        for location
        in locations

    }


    # ========================================================
    # SEÇİM BİLGİSİ
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
                for location in locations
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

    for row_number in range(10):


        columns = st.columns(
            10,
            gap="small"
        )


        for column_number in range(10):


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


            # -------------------------------------------------
            # KUTU İÇERİĞİ
            # -------------------------------------------------

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


            # -------------------------------------------------
            # SEÇİLİ ÇERÇEVE
            # -------------------------------------------------

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


            # -------------------------------------------------
            # KUTU
            # -------------------------------------------------

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
    # TOPLU İŞLEM ALANI
    # ========================================================

    st.divider()


    selected_codes = (
        st.session_state.selected_locations
    )


    if not selected_codes:

        st.warning(
            "Lokasyon işlemi yapmak için haritadan en az bir lokasyon seç."
        )


    else:


        st.subheader(
            "📦 Toplu Lokasyon İşlemi"
        )


        st.caption(
            f"{len(selected_codes)} lokasyon üzerinde işlem yapılacak."
        )


        # ====================================================
        # FORM
        # ====================================================

        left, middle, right = st.columns(
            [1.2, 1.2, 1]
        )


        with left:


            selected_status = st.selectbox(

                "Durum",

                list(
                    STATUS_COLORS.keys()
                ),

                index=1

            )


            selected_product = st.text_input(

                "Ürün",

                placeholder=(
                    "Örn: GS840"
                )

            )


            selected_lot = st.text_input(

                "Lot",

                placeholder=(
                    "Örn: 2608B021"
                )

            )


        with middle:


            total_quantity = st.number_input(

                "TOPLAM Miktar (kg)",

                min_value=0.0,

                value=0.0,

                step=100.0

            )


            selected_movement_type = st.selectbox(

                "Hareket Tipi",

                MOVEMENT_TYPES

            )


            changed_by = st.text_input(

                "İşlemi Yapan",

                placeholder=(
                    "Ad Soyad / Kullanıcı"
                )

            )


        with right:


            movement_note = st.text_area(

                "Hareket Açıklaması",

                placeholder=(
                    "Örn: Üretimden depoya toplu giriş."
                ),

                height=108

            )


        # ====================================================
        # MİKTAR DAĞILIMI
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

                    location_codes=(
                        selected_codes
                    ),

                    status=(
                        selected_status
                    ),

                    product=(
                        selected_product
                    ),

                    lot=(
                        selected_lot
                    ),

                    total_quantity=(
                        total_quantity
                    ),

                    movement_type=(
                        selected_movement_type
                    ),

                    note=(
                        movement_note
                    ),

                    changed_by=(
                        changed_by
                    )

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


    filter1, filter2, filter3, filter4 = (
        st.columns(
            4
        )
    )


    with filter1:

        start_date = st.date_input(

            "Başlangıç Tarihi",

            value=(
                datetime.now().date()
                - timedelta(days=30)
            )

        )


    with filter2:

        end_date = st.date_input(

            "Bitiş Tarihi",

            value=datetime.now().date()

        )


    with filter3:

        location_filter = st.text_input(

            "Lokasyon",

            placeholder="Örn: J-04"

        )


    with filter4:

        movement_filter = st.selectbox(

            "Hareket Tipi",

            [
                "Tümü"
            ]
            + MOVEMENT_TYPES

        )


    filter5, filter6 = st.columns(
        2
    )


    with filter5:

        product_filter = st.text_input(

            "Ürün Filtresi",

            placeholder="Örn: GS840"

        )


    with filter6:

        lot_filter = st.text_input(

            "Lot Filtresi",

            placeholder="Örn: 2608B021"

        )


    report = movement_report(

        start_date=start_date,

        end_date=end_date,

        location=location_filter,

        product=product_filter,

        lot=lot_filter,

        movement_type=movement_filter

    )


    # ========================================================
    # RAPOR
    # ========================================================

    if report.empty:


        st.info(
            "Seçilen filtrelere uygun hareket kaydı bulunamadı."
        )


    else:


        total_positive = report.loc[

            report["Fark (kg)"] > 0,

            "Fark (kg)"

        ].sum()


        total_negative = -report.loc[

            report["Fark (kg)"] < 0,

            "Fark (kg)"

        ].sum()


        report_kpi1, report_kpi2, report_kpi3 = (
            st.columns(
                3
            )
        )


        report_kpi1.metric(

            "Toplam Hareket",

            len(report)

        )


        report_kpi2.metric(

            "Toplam Artış",

            f"{total_positive:,.0f} kg"

        )


        report_kpi3.metric(

            "Toplam Azalış",

            f"{total_negative:,.0f} kg"

        )


        st.dataframe(

            report,

            use_container_width=True,

            hide_index=True

        )


        csv_data = report.to_csv(
            index=False
        ).encode(
            "utf-8-sig"
        )


        st.download_button(

            "⬇ CSV Hareket Raporunu İndir",

            data=csv_data,

            file_name=(

                f"depo_hareket_raporu_"
                f"{start_date}_"
                f"{end_date}.csv"

            ),

            mime="text/csv",

            use_container_width=True

        )
