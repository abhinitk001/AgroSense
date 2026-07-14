from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import SensorData, Farm

import joblib
import pandas as pd
import requests

from datetime import datetime

# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(
    prefix="/api/recommendation",
    tags=["AI Crop Recommendation"]
)

# ==========================================================
# LOAD MODEL
# ==========================================================

model = joblib.load(
    "ml_models/crop_model.pkl"
)

encoders = joblib.load(
    "ml_models/crop_label_encoders.pkl"
)

# ==========================================================
# WEATHER CONFIGURATION
# ==========================================================

API_KEY = "722762ea5a7f56de6f1f50fd46982e14"

COUNTRY = "IN"

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"

# ==========================================================
# GET CURRENT SEASON
# ==========================================================

def get_current_season():

    month = datetime.now().month

    if month in [6,7,8,9]:
        return "Kharif"

    elif month in [10,11,12,1]:
        return "Rabi"

    else:
        return "Zaid"

# ==========================================================
# FETCH WEATHER
# ==========================================================

def get_weather(city):

    params = {

        "q": f"{city},{COUNTRY}",

        "appid": API_KEY,

        "units":"metric"

    }

    response = requests.get(

        CURRENT_URL,

        params=params

    )

    if response.status_code != 200:

        raise HTTPException(

            status_code=500,

            detail="Weather API Error"

        )

    weather = response.json()

    rainfall = 0

    if "rain" in weather:

        rainfall = weather["rain"].get("1h",0)

    return {

        "temperature":weather["main"]["temp"],

        "humidity":weather["main"]["humidity"],

        "rainfall":rainfall

    }

# ==========================================================
# ENCODE VALUES
# ==========================================================

def encode_soil(soil):

    return encoders["Soil_Type"].transform([soil])[0]


def encode_irrigation(irrigation):

    return encoders["Irrigation_Type"].transform([irrigation])[0]


def encode_season(season):

    return encoders["Season"].transform([season])[0]


def decode_crop(prediction):

    return encoders["Recommended_Crop"].inverse_transform(
        [prediction]
    )[0]
# ==========================================================
# AI PREDICTION API
# ==========================================================

@router.get("/{farm_id}")
def crop_recommendation(
    farm_id: int,
    db: Session = Depends(get_db)
):

    # ---------------------------------------------
    # Get Farm Details
    # ---------------------------------------------

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

    # ---------------------------------------------
    # Get Latest Sensor Reading
    # ---------------------------------------------

    sensor = (
        db.query(SensorData)
        .filter(SensorData.farm_id == farm_id)
        .order_by(SensorData.created_at.desc())
        .first()
    )

    if sensor is None:

        raise HTTPException(
            status_code=404,
            detail="No sensor data available."
        )

    # ---------------------------------------------
    # Get Weather
    # ---------------------------------------------

    weather = get_weather(farm.district)

    # ---------------------------------------------
    # Encode Text Fields
    # ---------------------------------------------

    try:

        SOIL_MAPPING = {
        "Sandy (बलुई)": "Sandy",
        "Loamy (दोमट)": "Loamy",
        "Clay (चिकनी)": "Clay",
        "Silt (गाद)": "Silt"
        }
        soil_name = SOIL_MAPPING.get(farm.soil_type, farm.soil_type)
        IRRIGATION_MAPPING = {

        "canal": "Canal",
        "drip": "Drip",
        "rainfed": "Rainfed",

    # Borewell is not present in dataset.
    # Closest irrigation method:
        "bore": "Drip"

    }
        soil_name = SOIL_MAPPING.get(
        farm.soil_type,
        farm.soil_type
        )
        irrigation_name = IRRIGATION_MAPPING.get(
        farm.irrigation.lower(),
        farm.irrigation
    )
        
        soil = encode_soil(soil_name)
        irrigation = encode_irrigation(irrigation_name)
        season = encode_season(
            get_current_season()
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Encoding Error : {e}"
        )

    # ---------------------------------------------
    # Create Feature Vector
    # ---------------------------------------------

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

    # ---------------------------------------------
    # Predict
    # ---------------------------------------------

    prediction = model.predict(features)[0]

    crop = decode_crop(prediction)

    # ---------------------------------------------
    # Confidence
    # ---------------------------------------------

    confidence = max(
        model.predict_proba(features)[0]
    ) * 100

    # ---------------------------------------------
    # Response
    # ---------------------------------------------

    return {

        "farm_name": farm.farm_name,

        "district": farm.district,

        "recommended_crop": crop,

        "confidence": round(confidence,2),

        "sensor_values":{

            "nitrogen":sensor.nitrogen,

            "phosphorus":sensor.phosphorus,

            "potassium":sensor.potassium,

            "soil_ph":sensor.ph,

            "soil_moisture":
                sensor.soil_moisture

        },

        "weather":{

            "temperature":
                weather["temperature"],

            "humidity":
                weather["humidity"],

            "rainfall":
                weather["rainfall"]

        }

    }