"""
SQLAlchemy models and database initialization for the Mercado Público fraud detection platform.
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer, DateTime,
    Text, ForeignKey, Index, JSON, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "mercado_publico.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Procurement(Base):
    __tablename__ = "procurements"
    ocid = Column(String, primary_key=True)
    buyer_rut = Column(String, index=True)
    buyer_name = Column(String)
    region = Column(String, index=True)
    title = Column(String)
    description = Column(Text)
    method = Column(String, index=True)       # open, selective, limited, direct
    method_details = Column(String)            # LE25, LP25, LQ25, etc.
    tender_start = Column(DateTime)
    tender_end = Column(DateTime)
    award_date = Column(DateTime)
    status = Column(String, index=True)
    total_amount = Column(Float)
    currency = Column(String, default="CLP")
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    raw_file = Column(String)                  # Source JSON filename
    ingested_at = Column(DateTime, default=datetime.utcnow)

    bids = relationship("Bid", back_populates="procurement")
    awards = relationship("Award", back_populates="procurement")
    items = relationship("Item", back_populates="procurement")
    alerts = relationship("Alert", back_populates="procurement")
    parties = relationship("ProcurementParty", back_populates="procurement")


class Party(Base):
    __tablename__ = "parties"
    rut = Column(String, primary_key=True)
    name = Column(String, index=True)
    legal_name = Column(String)
    address = Column(String)
    region = Column(String)
    phone = Column(String)
    contact_name = Column(String)
    email = Column(String)
    party_type = Column(String)                # natural / juridica
    external_data_updated = Column(DateTime)
    sii_start_date = Column(DateTime)          # Fecha inicio actividades SII
    sii_activity_code = Column(String)         # Giro SII
    sii_status = Column(String)                # Activo/Inactivo
    is_public_employee = Column(Boolean, default=False)
    public_employee_org = Column(String)

    procurements = relationship("ProcurementParty", back_populates="party")


class ProcurementParty(Base):
    __tablename__ = "procurement_parties"
    id = Column(Integer, primary_key=True, autoincrement=True)
    procurement_ocid = Column(String, ForeignKey("procurements.ocid"), index=True)
    party_rut = Column(String, ForeignKey("parties.rut"), index=True)
    role = Column(String)                      # buyer, supplier, tenderer

    procurement = relationship("Procurement", back_populates="parties")
    party = relationship("Party", back_populates="procurements")


class Bid(Base):
    __tablename__ = "bids"
    id = Column(String, primary_key=True)
    ocid = Column(String, ForeignKey("procurements.ocid"), index=True)
    supplier_rut = Column(String, index=True)
    supplier_name = Column(String)
    amount = Column(Float)
    currency = Column(String, default="CLP")
    date = Column(DateTime)
    status = Column(String)                    # valid, rejected, withdrawn

    procurement = relationship("Procurement", back_populates="bids")


class Award(Base):
    __tablename__ = "awards"
    id = Column(String, primary_key=True)
    ocid = Column(String, ForeignKey("procurements.ocid"), index=True)
    supplier_rut = Column(String, index=True)
    supplier_name = Column(String)
    amount = Column(Float)
    currency = Column(String, default="CLP")
    date = Column(DateTime)
    status = Column(String)

    procurement = relationship("Procurement", back_populates="awards")
    items = relationship("Item", back_populates="award")


class Item(Base):
    __tablename__ = "items"
    id = Column(String, primary_key=True)
    ocid = Column(String, ForeignKey("procurements.ocid"), index=True)
    award_id = Column(String, ForeignKey("awards.id"), nullable=True)
    unspsc_code = Column(String, index=True)
    unspsc_prefix = Column(String, index=True)  # First 4 digits for grouping
    description = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    unit_price = Column(Float)
    total_price = Column(Float)

    procurement = relationship("Procurement", back_populates="items")
    award = relationship("Award", back_populates="items")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ocid = Column(String, ForeignKey("procurements.ocid"), nullable=True, index=True)
    alert_type = Column(String, index=True)    # FRAC, CONC, COLU, PLAZ, RELA, PREC, NUEV, TRAT, DTDR, CONF
    severity = Column(String, index=True)      # alta, media, baja
    title = Column(String)
    description = Column(Text)
    evidence = Column(JSON)                    # Raw evidence dict with source ocids, amounts, etc.
    buyer_rut = Column(String, index=True)
    buyer_name = Column(String)
    supplier_rut = Column(String, index=True)
    supplier_name = Column(String)
    region = Column(String, index=True)
    amount_involved = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="open")    # open, reviewed, dismissed, confirmed

    procurement = relationship("Procurement", back_populates="alerts")


class ExternalData(Base):
    __tablename__ = "external_data"
    rut = Column(String, primary_key=True)
    source = Column(String, primary_key=True)  # sii, transparencia, contraloria, cmf, mercadopublico
    raw_data = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


# Indexes for performance
Index("idx_bids_supplier_ocid", Bid.supplier_rut, Bid.ocid)
Index("idx_awards_supplier", Award.supplier_rut, Award.date)
Index("idx_items_unspsc_price", Item.unspsc_prefix, Item.unit_price)
Index("idx_alerts_type_severity", Alert.alert_type, Alert.severity)
Index("idx_procurement_buyer_date", Procurement.buyer_rut, Procurement.tender_start)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
