from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    TIMESTAMP,
    Text,
    text
)

from sqlalchemy.orm import relationship

from database import Base


# ==========================================================
# USER TABLE
# ==========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    email = Column(String(150), unique=True, nullable=False, index=True)

    phone = Column(String(20), unique=True, nullable=False)

    password = Column(String(255), nullable=False)

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # One User -> One Farm
    farm = relationship(
        "Farm",
        back_populates="owner",
        uselist=False,
        cascade="all, delete"
    )


# ==========================================================
# FARM TABLE
# ==========================================================

class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    farm_name = Column(String(150), nullable=False)

    state = Column(String(100), nullable=False)

    district = Column(String(100), nullable=False)

    farm_size = Column(Float, nullable=False)

    soil_type = Column(String(100), nullable=False)

    irrigation = Column(String(100), nullable=False)

    crops = Column(Text, nullable=False)

    iot_nodes = Column(Integer, default=0)

    # ==========================================================
    # FIXED: Add season field INSIDE the Farm class
    # ==========================================================
    season = Column(String(50), nullable=True, default="Rabi")

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )

    owner = relationship(
        "User",
        back_populates="farm"
    )
    sensor_data = relationship(
        "SensorData",
        back_populates="farm",
        cascade="all, delete-orphan"
    )


# ==========================================================
# SENSOR DATA TABLE
# ==========================================================

class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)

    farm_id = Column(
        Integer,
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False
    )

    # ---------- Soil Sensors ----------

    nitrogen = Column(Float, nullable=True)

    phosphorus = Column(Float, nullable=True)

    potassium = Column(Float, nullable=True)

    ph = Column(Float, nullable=True)

    tds = Column(Float, nullable=True)

    soil_moisture = Column(Float, nullable=True)

    # ---------- Weather Sensors ----------

    temperature = Column(Float, nullable=True)

    humidity = Column(Float, nullable=True)

    # ---------- ESP32 Information ----------

    node_id = Column(
        String(50),
        nullable=False,
        default="ESP32_01"
    )

    signal_strength = Column(
        String(30),
        nullable=True
    )

    battery_voltage = Column(
        Float,
        nullable=True
    )

    # ---------- Timestamp ----------

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # ---------- Relationship ----------

    farm = relationship(
        "Farm",
        back_populates="sensor_data"
    )

from sqlalchemy import Index

class MarketCache(Base):
    __tablename__ = "market_cache"

    id = Column(Integer, primary_key=True, index=True)
    
    # Crop information
    commodity = Column(String(100), nullable=False, index=True)
    variety = Column(String(100), nullable=True)
    
    # Location
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    market = Column(String(100), nullable=False)
    
    # Prices
    modal_price = Column(Float, nullable=False)
    minimum_price = Column(Float, nullable=False)
    maximum_price = Column(Float, nullable=False)
    
    # Dates
    arrival_date = Column(String(50), nullable=False)
    cached_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    
    # Indexes for faster queries
    __table_args__ = (
        Index('idx_commodity_state_district', 'commodity', 'state', 'district'),
        Index('idx_cached_at', 'cached_at'),
    )