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
    "Diğer",
]


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.5rem;
    }

    /* HARİTA BUTONLARI */

    div[data-testid="stButton"] button {
        min-height: 78px;
        white-space: pre-line;
        font-weight: 700;
        border-radius: 8px;
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


def save_location(
    code,
    status,
    product,
    lot,
    qty,
    movement_type,
    note,
    changed_by
):

    with SessionLocal() as db:

        loc = db.execute(
            select(Location).where(
                Location.code == code
            )
        ).scalar_one()


        # ----------------------------------------------------
        # ESKİ DEĞERLER
        # ----------------------------------------------------

        old_status = loc.status
        old_product = loc.product
        old_lot = loc.lot
        old_qty = float(
            loc.quantity_kg or 0
        )


        # ----------------------------------------------------
        # BOŞ LOKASYON
        # ----------------------------------------------------

        if status == "Boş":

            product = None
            lot = None
            qty = 0


        qty = float(
            qty or 0
        )


        # ----------------------------------------------------
        # LOKASYONU GÜNCELLE
        # ----------------------------------------------------

        loc.status = status
        loc.product = (
            product or None
        )

        loc.lot = (
            lot or None
        )

        loc.quantity_kg = qty

        loc.updated_at = datetime.now()


        # ----------------------------------------------------
        # HAREKET KAYDI
        # ----------------------------------------------------

        movement = Movement(

            location_id=loc.id,

            location_code=loc.code,

            movement_type=movement_type,

            old_status=old_status,
            new_status=status,

            old_product=old_product,
            new_product=product or None,

            old_lot=old_lot,
            new_lot=lot or None,

            old_quantity_kg=old_qty,
            new_quantity_kg=qty,

            quantity_delta_kg=(
                qty - old_qty
            ),

            note=note or None,

            changed_by=(
                changed_by or None
            ),

            created_at=datetime.now()
        )


        db.add(
            movement
        )

        db.commit()


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
                Movement.movement_type ==
                movement_type
            )


        rows = db.execute(
            stmt
        ).scalars().all()


    data = []


    for r in rows:

        data.append({

            "Tarih / Saat":
                r.created_at,

            "Lokasyon":
                r.location_code,

            "Hareket Tipi":
                r.movement_type,

            "Eski Durum":
                r.old_status,

            "Yeni Durum":
                r.new_status,

            "Eski Ürün":
                r.old_product,

            "Yeni Ürün":
                r.new_product,

            "Eski Lot":
                r.old_lot,

            "Yeni Lot":
                r.new_lot,

            "Eski Miktar (kg)":
                r.old_quantity_kg,

            "Yeni Miktar (kg)":
                r.new_quantity_kg,

            "Fark (kg)":
                r.quantity_delta_kg,

            "Not":
                r.note,

            "Değiştiren":
                r.changed_by

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
    "Lokasyon bazlı depo, ürün, lot ve hareket takip sistemi"
)


# ============================================================
# VERİLER
# ============================================================

locations = get_locations()


total_locations = len(
    locations
)


filled = sum(

    1

    for x in locations

    if x.status != "Boş"

)


empty = (
    total_locations
    - filled
)


blocked = sum(

    1

    for x in locations

    if x.status == "Bloke"

)


reserved = sum(

    1

    for x in locations

    if x.status == "Rezerve"

)


if total_locations:

    occupancy = (
        filled
        / total_locations
        * 100
    )

else:

    occupancy = 0


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
    filled
)


k3.metric(
    "Boş Lokasyon",
    empty
)


k4.metric(
    "Doluluk Oranı",
    f"%{occupancy:.1f}"
)


st.caption(

    f"🔴 Bloke: {blocked}   |   "
    f"🟣 Rezerve: {reserved}"

)


# ============================================================
# RENK AÇIKLAMASI
# ============================================================

legend_cols = st.columns(
    len(STATUS_COLORS)
)


for index, (
    status_name,
    color
) in enumerate(
    STATUS_COLORS.items()
):

    with legend_cols[index]:

        st.markdown(

            f"""
            <div style="
                background:{color};
                padding:8px;
                border-radius:6px;
                text-align:center;
                font-weight:700;
                color:#111827;
                margin-bottom:10px;
            ">
            {status_name}
            </div>
            """,

            unsafe_allow_html=True

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
# CANLI HARİTA
# ============================================================

with tab_map:


    by_code = {

        location.code:
            location

        for location
        in locations

    }


    selected_code = (
        st.session_state.get(
            "selected_code",
            "A-01"
        )
    )


    st.subheader(
        "Depo Yerleşimi"
    )


    # ========================================================
    # RENKLİ HARİTA
    # ========================================================

    for row in range(10):


        columns = st.columns(
            10,
            gap="small"
        )


        for column in range(10):


            code = (

                f"{chr(65 + row)}-"
                f"{column + 1:02d}"

            )


            location = by_code[
                code
            ]


            status = (
                location.status
            )


            color = STATUS_COLORS.get(
                status,
                "#E5E7EB"
            )


            if status == "Boş":

                product_text = "BOŞ"

                quantity_text = ""


            else:

                product_text = (

                    location.product
                    or status

                )


                quantity_text = (

                    f"{location.quantity_kg:,.0f} kg"

                )


            # ----------------------------------------------
            # RENKLİ KUTU
            # ----------------------------------------------

            with columns[column]:


                st.markdown(

                    f"""
                    <div style="
                        background-color:{color};
                        border:2px solid #374151;
                        border-radius:8px;
                        min-height:78px;
                        padding:7px 3px;
                        text-align:center;
                        color:#111827;
                        margin-bottom:3px;
                    ">

                        <div style="
                            font-size:15px;
                            font-weight:800;
                        ">
                            {code}
                        </div>

                        <div style="
                            font-size:11px;
                            font-weight:700;
                            overflow:hidden;
                            white-space:nowrap;
                            text-overflow:ellipsis;
                        ">
                            {product_text}
                        </div>

                        <div style="
                            font-size:10px;
                        ">
                            {quantity_text}
                        </div>

                    </div>
                    """,

                    unsafe_allow_html=True

                )


                if st.button(

                    "Seç",

                    key=f"select_{code}",

                    use_container_width=True

                ):

                    st.session_state[
                        "selected_code"
                    ] = code

                    st.rerun()


    st.divider()


    # ========================================================
    # LOKASYON DETAYI
    # ========================================================

    selected_code = (
        st.session_state.get(
            "selected_code",
            "A-01"
        )
    )


    location = get_location(
        selected_code
    )


    st.subheader(
        f"📦 Lokasyon Detayı — {location.code}"
    )


    left, middle, right = st.columns(
        [1.2, 1.2, 1]
    )


    # ========================================================
    # SOL
    # ========================================================

    with left:


        status = st.selectbox(

            "Durum",

            list(
                STATUS_COLORS.keys()
            ),

            index=list(
                STATUS_COLORS.keys()
            ).index(
                location.status
            )

        )


        product = st.text_input(

            "Ürün",

            value=(
                location.product
                or ""
            )

        )


        lot = st.text_input(

            "Lot",

            value=(
                location.lot
                or ""
            )

        )


    # ========================================================
    # ORTA
    # ========================================================

    with middle:


        quantity = st.number_input(

            "Miktar (kg)",

            min_value=0.0,

            value=float(
                location.quantity_kg
                or 0
            ),

            step=100.0

        )


        movement_type = st.selectbox(

            "Hareket Tipi",

            MOVEMENT_TYPES,

            index=0

        )


        changed_by = st.text_input(

            "İşlemi Yapan",

            placeholder=(
                "Ad Soyad / Kullanıcı"
            )

        )


    # ========================================================
    # SAĞ
    # ========================================================

    with right:


        note = st.text_area(

            "Hareket Açıklaması",

            placeholder=(
                "Örn: Üretimden gelen "
                "10 palet depoya alındı."
            ),

            height=110

        )


        st.write(
            "**Son Güncelleme**"
        )


        st.write(

            location.updated_at.strftime(
                "%d.%m.%Y %H:%M:%S"
            )

        )


    # ========================================================
    # KAYDET
    # ========================================================

    if st.button(

        "💾 HAREKETİ KAYDET",

        type="primary",

        use_container_width=True

    ):


        save_location(

            location.code,

            status,

            product,

            lot,

            quantity,

            movement_type,

            note,

            changed_by

        )


        st.success(

            f"{location.code} lokasyonundaki "
            f"{movement_type} hareketi kaydedildi."

        )


        st.rerun()


# ============================================================
# HAREKET RAPORU
# ============================================================

with tab_report:


    st.subheader(
        "📊 Depo Hareket Raporu"
    )


    f1, f2, f3, f4 = st.columns(
        4
    )


    with f1:


        start_date = st.date_input(

            "Başlangıç Tarihi",

            value=(
                datetime.now().date()
                - timedelta(days=30)
            )

        )


    with f2:


        end_date = st.date_input(

            "Bitiş Tarihi",

            value=datetime.now().date()

        )


    with f3:


        location_filter = st.text_input(

            "Lokasyon Filtresi",

            placeholder="A-01"

        )


    with f4:


        movement_filter = st.selectbox(

            "Hareket Tipi Filtresi",

            [
                "Tümü"
            ]
            + MOVEMENT_TYPES

        )


    f5, f6 = st.columns(
        2
    )


    with f5:


        product_filter = st.text_input(

            "Ürün Filtresi",

            placeholder="PET"

        )


    with f6:


        lot_filter = st.text_input(

            "Lot Filtresi",

            placeholder="LOT-001"

        )


    report = movement_report(

        start_date,

        end_date,

        location_filter,

        product_filter,

        lot_filter,

        movement_filter

    )


    # ========================================================
    # RAPOR SONUÇLARI
    # ========================================================

    if report.empty:


        st.info(

            "Seçilen filtrelere uygun "
            "hareket bulunamadı."

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

            len(report)

        )


        r2.metric(

            "Toplam Giriş / Artış",

            f"{total_positive:,.0f} kg"

        )


        r3.metric(

            "Toplam Çıkış / Azalış",

            f"{total_negative:,.0f} kg"

        )


        st.dataframe(

            report,

            use_container_width=True,

            hide_index=True

        )


        # ====================================================
        # CSV
        # ====================================================

        csv = report.to_csv(
            index=False
        ).encode(
            "utf-8-sig"
        )


        st.download_button(

            "⬇ Hareket Raporunu İndir",

            data=csv,

            file_name=(

                f"depo_hareket_raporu_"
                f"{start_date}_"
                f"{end_date}.csv"

            ),

            mime="text/csv",

            use_container_width=True

        )
