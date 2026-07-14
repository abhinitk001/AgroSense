from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import requests

from database import get_db
from models import Farm

router = APIRouter(
    prefix="/api/weather",
    tags=["Weather"]
)

# ==========================================================
# OpenWeather Configuration
# ==========================================================

import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
COUNTRY = "IN"

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# ==========================================================
# Helper: Get City from Database
# ==========================================================

def get_city_from_db(farm_id: int, db: Session) -> str:
    """Fetch city/district from the farm database"""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    
    # Use district as the city name
    city = farm.district
    if not city:
        # Fallback to state if district is empty
        city = farm.state
    
    if not city:
        # Ultimate fallback
        city = "Patna"
    
    return city


# ==========================================================
# CURRENT WEATHER (With Farm ID)
# ==========================================================

@router.get("/{farm_id}")
def current_weather(
    farm_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current weather for the farm's location
    """
    city = get_city_from_db(farm_id, db)
    
    params = {
        "q": f"{city},{COUNTRY}",
        "appid": API_KEY,
        "units": "metric"
    }

    response = requests.get(CURRENT_URL, params=params, timeout=10)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Unable to fetch weather for {city}. Please check the city name."
        )

    data = response.json()

    rain = 0
    if "rain" in data:
        rain = data["rain"].get("1h", 0)

    return {
        "farm_id": farm_id,
        "location": data["name"],
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "temp_min": data["main"]["temp_min"],
        "temp_max": data["main"]["temp_max"],
        "wind": data["wind"]["speed"],
        "clouds": data["clouds"]["all"],
        "visibility": data.get("visibility", 0),
        "condition": data["weather"][0]["main"],
        "description": data["weather"][0]["description"],
        "icon": data["weather"][0]["icon"],
        "rain": rain
    }


# ==========================================================
# 5 DAY FORECAST (With Farm ID)
# ==========================================================

@router.get("/forecast/{farm_id}")
def weather_forecast(
    farm_id: int,
    db: Session = Depends(get_db)
):
    """
    Get 5-day weather forecast for the farm's location
    """
    city = get_city_from_db(farm_id, db)

    params = {
        "q": f"{city},{COUNTRY}",
        "appid": API_KEY,
        "units": "metric"
    }

    response = requests.get(FORECAST_URL, params=params, timeout=10)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Unable to fetch forecast for {city}. Please check the city name."
        )

    data = response.json()

    forecast = []

    # One reading every 24 hours (8 × 3-hour intervals)
    for item in data["list"][::8]:
        forecast.append({
            "date": item["dt_txt"],
            "temperature": item["main"]["temp"],
            "temp_min": item["main"]["temp_min"],
            "temp_max": item["main"]["temp_max"],
            "humidity": item["main"]["humidity"],
            "condition": item["weather"][0]["main"],
            "description": item["weather"][0]["description"],
            "icon": item["weather"][0]["icon"],
            "wind": item["wind"]["speed"],
            "rain_chance": int(item.get("pop", 0) * 100)
        })

    return {
        "farm_id": farm_id,
        "location": city,
        "forecast": forecast
    }


# ==========================================================
# DEFAULT WEATHER (Fallback - No Farm ID Required)
# ==========================================================

@router.get("")
def default_weather():
    """
    Get current weather for default city (Patna)
    Used when farm_id is not provided
    """
    params = {
        "q": f"Patna,{COUNTRY}",
        "appid": API_KEY,
        "units": "metric"
    }

    response = requests.get(CURRENT_URL, params=params, timeout=10)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Unable to fetch weather for default city."
        )

    data = response.json()

    rain = 0
    if "rain" in data:
        rain = data["rain"].get("1h", 0)

    return {
        "location": data["name"],
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "temp_min": data["main"]["temp_min"],
        "temp_max": data["main"]["temp_max"],
        "wind": data["wind"]["speed"],
        "clouds": data["clouds"]["all"],
        "visibility": data.get("visibility", 0),
        "condition": data["weather"][0]["main"],
        "description": data["weather"][0]["description"],
        "icon": data["weather"][0]["icon"],
        "rain": rain
    }


# ==========================================================
# DEFAULT FORECAST (Fallback)
# ==========================================================

@router.get("/forecast")
def default_forecast():
    """
    Get 5-day weather forecast for default city (Patna)
    Used when farm_id is not provided
    """
    params = {
        "q": f"Patna,{COUNTRY}",
        "appid": API_KEY,
        "units": "metric"
    }

    response = requests.get(FORECAST_URL, params=params, timeout=10)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Unable to fetch forecast for default city."
        )

    data = response.json()

    forecast = []

    for item in data["list"][::8]:
        forecast.append({
            "date": item["dt_txt"],
            "temperature": item["main"]["temp"],
            "temp_min": item["main"]["temp_min"],
            "temp_max": item["main"]["temp_max"],
            "humidity": item["main"]["humidity"],
            "condition": item["weather"][0]["main"],
            "description": item["weather"][0]["description"],
            "icon": item["weather"][0]["icon"],
            "wind": item["wind"]["speed"],
            "rain_chance": int(item.get("pop", 0) * 100)
        })

    return forecast