from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ==========================================================
# STEP 1 : USER INFORMATION
# ==========================================================

class UserRegister(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)

    email: EmailStr

    phone: str = Field(..., min_length=10, max_length=15)

    password: str = Field(..., min_length=6)


# ==========================================================
# STEP 2 : FARM INFORMATION
# ==========================================================

class FarmRegister(BaseModel):

    farm_name: str

    state: str

    district: str

    farm_size: float

    soil_type: str

    irrigation: str

    crops: str

    iot_nodes: int


# ==========================================================
# COMPLETE REGISTRATION
# ==========================================================

class RegisterRequest(BaseModel):

    user: UserRegister

    farm: FarmRegister


# ==========================================================
# LOGIN
# ==========================================================

class LoginRequest(BaseModel):

    email: EmailStr

    password: str


# ==========================================================
# USER RESPONSE
# ==========================================================

class UserResponse(BaseModel):

    id: int

    first_name: str

    last_name: str

    email: EmailStr

    phone: str

    class Config:
        from_attributes = True


# ==========================================================
# FARM RESPONSE
# ==========================================================

class FarmResponse(BaseModel):

    id: int

    farm_name: str

    state: str

    district: str

    farm_size: float

    soil_type: str

    irrigation: str

    crops: str

    iot_nodes: int

    class Config:
        from_attributes = True

# ==========================================================
# SENSOR DATA (ESP32 → FASTAPI)
# ==========================================================

class SensorDataCreate(BaseModel):

    farm_id: int

    nitrogen: Optional[float] = None

    phosphorus: Optional[float] = None

    potassium: Optional[float] = None

    ph: Optional[float] = None

    tds: Optional[float] = None

    soil_moisture: Optional[float] = None

    temperature: Optional[float] = None

    humidity: Optional[float] = None

    node_id: str = "ESP32_01"

    signal_strength: Optional[str] = None

    battery_voltage: Optional[float] = None


# ==========================================================
# SENSOR RESPONSE
# ==========================================================

class SensorDataResponse(BaseModel):

    id: int

    farm_id: int

    nitrogen: Optional[float]

    phosphorus: Optional[float]

    potassium: Optional[float]

    ph: Optional[float]

    tds: Optional[float]

    soil_moisture: Optional[float]

    temperature: Optional[float]

    humidity: Optional[float]

    node_id: str

    signal_strength: Optional[str]

    battery_voltage: Optional[float]

    class Config:
        from_attributes = True


# ==========================================================
# LIVE DASHBOARD RESPONSE
# ==========================================================

class LiveSensorResponse(BaseModel):

    temperature: Optional[float]

    humidity: Optional[float]

    soil_moisture: Optional[float]

    ph: Optional[float]

    tds: Optional[float]

    nitrogen: Optional[float]

    phosphorus: Optional[float]

    potassium: Optional[float]

    node_id: str

    signal_strength: Optional[str]

# schemas.py - Add season to FarmRegister and FarmResponse

class FarmRegister(BaseModel):
    farm_name: str
    state: str
    district: str
    farm_size: float
    soil_type: str
    irrigation: str
    crops: str
    iot_nodes: int
    season: str = "Rabi"  # Add this


class FarmResponse(BaseModel):
    id: int
    farm_name: str
    state: str
    district: str
    farm_size: float
    soil_type: str
    irrigation: str
    crops: str
    iot_nodes: int
    season: str  # Add this

    class Config:
        from_attributes = True