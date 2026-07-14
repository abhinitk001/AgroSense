from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import SensorData

# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(
    prefix="/api/fertilizer",
    tags=["AI Fertilizer Recommendation"]
)

# ==========================================================
# OPTIMUM NPK RANGES
# (General values suitable for most crops)
# ==========================================================

N_MIN = 50
N_MAX = 100

P_MIN = 30
P_MAX = 60

K_MIN = 40
K_MAX = 80

# ==========================================================
# STATUS FUNCTIONS
# ==========================================================

def get_status(value, minimum, maximum):

    if value is None:
        return "Unknown"

    if value < minimum:
        return "Low"

    elif value > maximum:
        return "High"

    return "Optimal"


# ==========================================================
# NITROGEN RULES
# ==========================================================

def nitrogen_rule(value):

    status = get_status(value, N_MIN, N_MAX)

    if status == "Low":

        return {

            "status":"Low",

            "fertilizer":"Urea",

            "dose":"50 kg/hectare",

            "reason":"Nitrogen level is below the optimum range."

        }

    elif status == "High":

        return {

            "status":"High",

            "fertilizer":"Do Not Apply",

            "dose":"0 kg/hectare",

            "reason":"Nitrogen level is already high."

        }

    return {

        "status":"Optimal",

        "fertilizer":"None",

        "dose":"0 kg/hectare",

        "reason":"Nitrogen level is optimal."

    }


# ==========================================================
# PHOSPHORUS RULES
# ==========================================================

def phosphorus_rule(value):

    status = get_status(value, P_MIN, P_MAX)

    if status == "Low":

        return {

            "status":"Low",

            "fertilizer":"DAP",

            "dose":"40 kg/hectare",

            "reason":"Phosphorus deficiency detected."

        }

    elif status == "High":

        return {

            "status":"High",

            "fertilizer":"Do Not Apply",

            "dose":"0 kg/hectare",

            "reason":"Phosphorus level is already high."

        }

    return {

        "status":"Optimal",

        "fertilizer":"None",

        "dose":"0 kg/hectare",

        "reason":"Phosphorus level is optimal."

    }


# ==========================================================
# POTASSIUM RULES
# ==========================================================

def potassium_rule(value):

    status = get_status(value, K_MIN, K_MAX)

    if status == "Low":

        return {

            "status":"Low",

            "fertilizer":"MOP (Muriate of Potash)",

            "dose":"30 kg/hectare",

            "reason":"Potassium level is below optimum."

        }

    elif status == "High":

        return {

            "status":"High",

            "fertilizer":"Do Not Apply",

            "dose":"0 kg/hectare",

            "reason":"Potassium level is already high."

        }

    return {

        "status":"Optimal",

        "fertilizer":"None",

        "dose":"0 kg/hectare",

        "reason":"Potassium level is optimal."

    }
# ==========================================================
# LOAD CROP AI
# ==========================================================

from ai.crop_ai import (
    model,
    encoders,
    get_weather,
    get_current_season,
    encode_soil,
    encode_irrigation,
    encode_season,
    decode_crop
)

from models import Farm
import pandas as pd


# ==========================================================
# GET FERTILIZER RECOMMENDATION
# ==========================================================

@router.get("/{farm_id}")
def fertilizer_recommendation(
    farm_id: int,
    db: Session = Depends(get_db)
):

    # ------------------------------------------------------
    # Farm Details
    # ------------------------------------------------------

    farm = (
        db.query(Farm)
        .filter(Farm.id == farm_id)
        .first()
    )

    if farm is None:

        raise HTTPException(
            status_code=404,
            detail="Farm not found."
        )

    # ------------------------------------------------------
    # Latest Sensor Reading
    # ------------------------------------------------------

    sensor = (
        db.query(SensorData)
        .filter(SensorData.farm_id == farm_id)
        .order_by(SensorData.created_at.desc())
        .first()
    )

    if sensor is None:

        raise HTTPException(
            status_code=404,
            detail="No sensor data found."
        )

    # ------------------------------------------------------
    # Weather
    # ------------------------------------------------------

    weather = get_weather(farm.district)

    # ------------------------------------------------------
    # Encode Farm Details
    # ------------------------------------------------------

    SOIL_MAPPING = {

        "Sandy (बलुई)": "Sandy",
        "Clay (चिकनी)": "Clay",
        "Loamy (दोमट)": "Loamy",
        "Silt (गाद)": "Silt"

    }

    IRRIGATION_MAPPING = {

        "canal": "Canal",
        "drip": "Drip",
        "rainfed": "Rainfed",
        "bore": "Drip"

    }

    soil = encode_soil(

        SOIL_MAPPING.get(
            farm.soil_type,
            farm.soil_type
        )

    )

    irrigation = encode_irrigation(

        IRRIGATION_MAPPING.get(
            farm.irrigation.lower(),
            farm.irrigation
        )

    )

    season = encode_season(
        get_current_season()
    )

    # ------------------------------------------------------
    # Create Feature Vector
    # ------------------------------------------------------

    features = pd.DataFrame([{

        "N": sensor.nitrogen or 0,

        "P": sensor.phosphorus or 0,

        "K": sensor.potassium or 0,

        "Soil_pH": sensor.ph or 7,

        "Soil_Moisture":
            sensor.soil_moisture or 0,

        "Soil_Type":
            soil,

        "Temperature":
            weather["temperature"],

        "Humidity":
            weather["humidity"],

        "Rainfall":
            weather["rainfall"],

        "Season":
            season,

        "Irrigation_Type":
            irrigation

    }])

    # ------------------------------------------------------
    # Crop Prediction
    # ------------------------------------------------------

    prediction = model.predict(features)[0]

    crop = decode_crop(prediction)

    confidence = round(
        max(model.predict_proba(features)[0]) * 100,
        2
    )

    # ------------------------------------------------------
    # Fertilizer Rules
    # ------------------------------------------------------

    nitrogen = nitrogen_rule(sensor.nitrogen)

    phosphorus = phosphorus_rule(sensor.phosphorus)

    potassium = potassium_rule(sensor.potassium)
    # ------------------------------------------------------
    # Final Response
    # ------------------------------------------------------

    return {

        "farm_name": farm.farm_name,

        "district": farm.district,

        "recommended_crop": crop,

        "confidence": confidence,

        "sensor_values": {

            "nitrogen": sensor.nitrogen,

            "phosphorus": sensor.phosphorus,

            "potassium": sensor.potassium,

            "soil_ph": sensor.ph,

            "soil_moisture": sensor.soil_moisture

        },

        "fertilizer": {

            "nitrogen": nitrogen,

            "phosphorus": phosphorus,

            "potassium": potassium

        }

    }