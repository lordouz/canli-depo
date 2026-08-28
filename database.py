from datetime import datetime

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


# ======================================================
# VERİTABANI AYARI
# ======================================================

DATABASE_URL = "sqlite:///warehouse.db"


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
    if DATABASE_URL.startswith("sqlite")
    else {},
    future=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# ======================================================
# BASE
# ======================================================

class Base(DeclarativeBase):
    pass


# ======================================================
# LOKASYON TABLOSU
# ======================================================

class Location(Base):

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True
    )

    row_no: Mapped[int] = mapped_column(
        Integer
    )

    col_no: Mapped[int] = mapped_column(
        Integer
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="Boş"
    )

    product: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    lot: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    quantity_kg: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    movements = relationship(
        "Movement",
        back_populates="location",
        cascade="all, delete-orphan"
    )


# ======================================================
# HAREKET TABLOSU
# ======================================================

class Movement(Base):

    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        index=True
    )

    location_code: Mapped[str] = mapped_column(
        String(20),
        index=True
    )

    movement_type: Mapped[str] = mapped_column(
        String(50),
        index=True
    )

    old_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    new_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    old_product: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    new_product: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    old_lot: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    new_lot: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True
    )

    old_quantity_kg: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    new_quantity_kg: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    quantity_delta_kg: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    note: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True
    )

    changed_by: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        index=True
    )

    location = relationship(
        "Location",
        back_populates="movements"
    )


# ======================================================
# İLK KURULUM
# ======================================================

def init_db():

    Base.metadata.create_all(
        bind=engine
    )

    with SessionLocal() as db:

        location_count = (
            db.query(Location)
            .count()
        )

        if location_count == 0:

            for r in range(10):

                for c in range(10):

                    code = (
                        f"{chr(65 + r)}-"
                        f"{c + 1:02d}"
                    )

                    location = Location(
                        code=code,
                        row_no=r,
                        col_no=c,
                        status="Boş",
                        product=None,
                        lot=None,
                        quantity_kg=0
                    )

                    db.add(location)

            db.commit()
