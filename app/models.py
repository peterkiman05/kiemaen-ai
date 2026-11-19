from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base

class LeadModel(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True, index=True)
    last_interaction = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="Active")

class TradeModel(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    pair = Column(String)
    setup_details = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class B2BModel(Base):
    __tablename__ = "b2b_pipeline"
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, unique=True)
    status = Column(String, default="Pending")
    timestamp = Column(DateTime, default=datetime.utcnow)
