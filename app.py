from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import select, and_

from database import SessionLocal, Location, Movement, init_db


st.set_page_config(
    page_title="Canlı Depo Haritası",
    layout="wide"
)

init_db()


STATUS_COLORS = {
    "Boş": "#E5E7EB",
    "PET": "#60A5FA",
    "rPET": "#4ADE80",
    "Hammadde": "#FACC15",
    "Bloke": "#F87171",
    "Rezerve": "#A78BFA",
}


def get_locations():
    with SessionLocal() as db:
        return db.execute(
            select(Location).order_by(
                Location.row_no,
                Location.col_no
            )
        ).scalars().all()


def get_location(code: str):
    with SessionLocal() as db:
        return db.execute(
            select(Location).where(
                Location.code == code
            )
        ).scalar_one()


def save_location(
    code,
    status,
    product,
    lot,
    qty,
    note,
    changed_by
):
    with SessionLocal() as db:

        loc = db.execute(
            select(Location).where(
                Location.code == code
            )
        ).scalar_one()

        old = {
            "status": loc.status,
            "product": loc.product,
            "lot": loc.lot,
            "quantity": float(loc.quantity_kg or 0),
        }

        if status == "Boş":
            product = None
            lot = None
            qty = 0.0

        qty = float(qty or 0)

        movement_type = "Güncelleme"

        if old["status"] == "Boş" and status != "Boş":
            movement_type = "Giriş"

        elif old["status"] != "Boş" and status == "Boş":
            movement_type = "Çıkış"

        elif old["quantity"] != qty:
            movement_type = "Miktar Değişimi"

        elif (
            old["lot"] != lot
            or old["product"] != product
        ):
            movement_type = "Lot/Ürün Değişimi"

        elif old["status"] != status:
            movement_type = "Durum Değişimi"

        loc.status = status
        loc.product = product or None
        loc.lot = lot or None
        loc.quantity_kg = qty
        loc.updated_at = datetime.now()

        movement = Movement(
            location_id=loc.id,
            location_code=loc.code,
            movement_type=movement_type,

            old_status=old["status"],
            new_status=status,

            old_product=old["product"],
            new_product=product or None,

            old_lot=old["lot"],
            new_lot=lot or None,

            old_quantity_kg=old["quantity"],
            new_quantity_kg=qty,

            quantity_delta_kg=qty - old["quantity"],

            note=note or None,
            changed_by=changed_by or None,
        )

        db.add(movement)
        db.commit()


def movement_report(
    start_date,
    end_date,
    location,
    product,
    lot,
    movement_type
):

    with SessionLocal() as db:

        stmt = select(Movement).where(
            and_(
                Movement.created_at >= datetime.combine(
                    start_date,
                    datetime.min.time()
                ),
                Movement.created_at <= datetime.combine(
                    end_date,
                    datetime.max.time()
                ),
            )
        ).order_by(
            Movement.created_at.desc()
        )

        if location:
            stmt = stmt.where(
                Movement.location_code.contains(location)
            )

        if product:
            stmt = stmt.where(
                Movement.new_product.contains(product)
            )

        if lot:
            stmt = stmt.where(
                Movement.new_lot.contains(lot)
            )

        if movement_type != "Tümü":
            stmt = stmt.where(
                Movement.movement_type == movement_type
            )

        rows = db.execute(stmt).scalars().all()

    return pd.DataFrame(
        [
            {
                "Tarih/Saat": r.created_at,
                "Lokasyon": r.location_code,
                "Hareket Tipi": r.movement_type,
                "Eski Durum": r.old_status,
                "Yeni Durum": r.new_status,
                "Eski Ürün": r.old_product,
                "Yeni Ürün": r.new_product,
                "Eski Lot": r.old_lot,
                "Yeni Lot": r.new_lot,
                "Eski Miktar (kg)": r.old_quantity_kg,
                "Yeni Miktar (kg)": r.new_quantity_kg,
                "Fark (kg)": r.quantity_delta_kg,
                "Not": r.note,
                "Değiştiren": r.changed_by,
            }
            for r in rows
        ]
    )


st.title("🏭 Canlı Depo Haritası")

locations = get_locations()

filled = sum(
    1 for x in locations
    if x.status != "Boş"
)

blocked = sum(
    1 for x in locations
    if x.status == "Bloke"
)

reserved = sum(
    1 for x in locations
    if x.status == "Rezerve"
)


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Toplam Lokasyon",
    len(locations)
)

c2.metric(
    "Dolu Lokasyon",
    filled
)

c3.metric(
    "Boş Lokasyon",
    len(locations) - filled
)

if len(locations) > 0:
    doluluk = filled / len(locations) * 100
else:
    doluluk = 0

c4.metric(
    "Doluluk",
    f"%{doluluk:.1f}"
)

st.caption(
    f"🔴 Bloke: {blocked} • 🟣 Rezerve: {reserved}"
)


tab_map, tab_report = st.tabs(
    [
        "🗺️ Canlı Harita",
        "📊 Hareket Raporu"
    ]
)


with tab_map:

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            min-height: 78px;
            white-space: pre-line;
            font-weight: 700;
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    by_code = {
        x.code: x
        for x in locations
    }

    selected_code = st.session_state.get(
        "selected_code",
        "A-01"
    )


    for r in range(10):

        cols = st.columns(
            10,
            gap="small"
        )

        for c in range(10):

            code = (
                f"{chr(65 + r)}-"
                f"{c + 1:02d}"
            )

            loc = by_code[code]

            if loc.status != "Boş":
                label = (
                    f"{code}\n"
                    f"{loc.product or loc.status}\n"
                    f"{loc.quantity_kg:,.0f} kg"
                )
            else:
                label = (
                    f"{code}\n"
                    f"BOŞ"
                )

            color = STATUS_COLORS[
                loc.status
            ]

            with cols[c]:

                st.markdown(
                    f"""
                    <div
                    style="
                    height:7px;
                    background:{color};
                    border-radius:5px 5px 0 0;
                    ">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    label,
                    key=f"btn_{code}",
                    use_container_width=True
                ):

                    st.session_state[
                        "selected_code"
                    ] = code

                    selected_code = code


    st.divider()

    loc = get_location(
        selected_code
    )

    st.subheader(
        f"📦 Lokasyon Detayı — {loc.code}"
    )

    a, b = st.columns(
        [2, 1]
    )

    with a:

        status = st.selectbox(
            "Durum",
            list(
                STATUS_COLORS.keys()
            ),
            index=list(
                STATUS_COLORS.keys()
            ).index(
                loc.status
            ),
        )

        product = st.text_input(
            "Ürün",
            value=loc.product or ""
        )

        lot = st.text_input(
            "Lot",
            value=loc.lot or ""
        )

        qty = st.number_input(
            "Miktar (kg)",
            min_value=0.0,
            value=float(
                loc.quantity_kg or 0
            ),
            step=100.0,
        )


    with b:

        changed_by = st.text_input(
            "Değiştiren",
            placeholder="Kullanıcı adı"
        )

        note = st.text_area(
            "Hareket Notu",
            placeholder="İsteğe bağlı açıklama"
        )

        st.write(
            "Son güncelleme:"
        )

        st.write(
            loc.updated_at.strftime(
                "%d.%m.%Y %H:%M"
            )
        )

        if st.button(
            "💾 Lokasyonu Kaydet",
            type="primary",
            use_container_width=True
        ):

            save_location(
                loc.code,
                status,
                product,
                lot,
                qty,
                note,
                changed_by
            )

            st.success(
                "Lokasyon güncellendi ve hareket kaydı oluşturuldu."
            )

            st.rerun()


with tab_report:

    st.subheader(
        "📊 Depo Hareket Raporu"
    )

    f1, f2, f3, f4 = st.columns(4)

    with f1:

        start_date = st.date_input(
            "Başlangıç Tarihi",
            value=(
                datetime.now().date()
                - timedelta(days=30)
            ),
        )

    with f2:

        end_date = st.date_input(
            "Bitiş Tarihi",
            value=datetime.now().date()
        )

    with f3:

        location_filter = st.text_input(
            "Lokasyon",
            placeholder="Örn: A-01"
        )

    with f4:

        movement_type = st.selectbox(
            "Hareket Tipi",
            [
                "Tümü",
                "Giriş",
                "Çıkış",
                "Miktar Değişimi",
                "Lot/Ürün Değişimi",
                "Durum Değişimi",
                "Güncelleme",
            ],
        )

    f5, f6 = st.columns(2)

    with f5:

        product_filter = st.text_input(
            "Ürün Filtresi"
        )

    with f6:

        lot_filter = st.text_input(
            "Lot Filtresi"
        )

    report = movement_report(
        start_date,
        end_date,
        location_filter,
        product_filter,
        lot_filter,
        movement_type
    )

    if report.empty:

        st.info(
            "Seçilen filtrelerde hareket kaydı bulunamadı."
        )

    else:

        total_in = report.loc[
            report["Fark (kg)"] > 0,
            "Fark (kg)"
        ].sum()

        total_out = -report.loc[
            report["Fark (kg)"] < 0,
            "Fark (kg)"
        ].sum()

        r1, r2, r3 = st.columns(3)

        r1.metric(
            "Hareket Sayısı",
            len(report)
        )

        r2.metric(
            "Toplam Artış",
            f"{total_in:,.0f} kg"
        )

        r3.metric(
            "Toplam Azalış",
            f"{total_out:,.0f} kg"
        )

        st.dataframe(
            report,
            use_container_width=True,
            hide_index=True
        )

        csv = report.to_csv(
            index=False
        ).encode(
            "utf-8-sig"
        )

        st.download_button(
            "⬇ CSV Hareket Raporunu İndir",
            csv,
            file_name=(
                f"hareket_raporu_"
                f"{start_date}_"
                f"{end_date}.csv"
            ),
            mime="text/csv",
        )
