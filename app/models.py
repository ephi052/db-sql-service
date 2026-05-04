from sqlalchemy import Column, Integer, DateTime, String, JSON, func
from .db import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(String(200), nullable=True)
    payload = Column(JSON, nullable=False)


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
