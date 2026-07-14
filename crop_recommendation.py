import os
import json
import joblib
import numpy as np
import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import re
import requests
import pandas as pd

from database import get_db
from models import Farm, SensorData

load_dotenv()

router = APIRouter(
    prefix="/api/crop",
    tags=["Crop Recommendation"]
)

# ==========================================================
# Configure Gemini
# ==========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini API configured for crop recommendations")
    except Exception as e:
        print(f"⚠️ Gemini configuration error: {e}")
        gemini_model = None
else:
    print("⚠️ GEMINI_API_KEY not found. Using fallback data.")
    gemini_model = None

# ==========================================================
# Load ML Model from crop_ai.py
# ==========================================================

try:
    from ai.crop_ai import model as ml_model, encoders, get_weather, get_current_season
    print("✅ ML Model loaded from crop_ai.py")
except Exception as e:
    print(f"⚠️ Could not load from crop_ai.py: {e}")
    # Fallback: load directly
    ml_model = joblib.load("ml_models/crop_model.pkl")
    encoders = joblib.load("ml_models/crop_label_encoders.pkl")
    print("✅ ML Model loaded directly")

# ==========================================================
# Crop Emojis and Colors for Display
# ==========================================================

CROP_INFO = {
    "Wheat": {"emoji": "🌾", "color": "#2E7D32"},
    "Rice": {"emoji": "🍚", "color": "#1565C0"},
    "Maize": {"emoji": "🌽", "color": "#F9A825"},
    "Corn": {"emoji": "🌽", "color": "#F9A825"},
    "Mustard": {"emoji": "🌻", "color": "#F9A825"},
    "Chickpea": {"emoji": "🫘", "color": "#795548"},
    "Potato": {"emoji": "🥔", "color": "#7B1FA2"},
    "Sugarcane": {"emoji": "🎋", "color": "#4CAF50"},
    "Soybean": {"emoji": "🌱", "color": "#4CAF50"},
    "Cotton": {"emoji": "🌿", "color": "#795548"},
    "Tomato": {"emoji": "🍅", "color": "#D32F2F"},
    "Onion": {"emoji": "🧅", "color": "#D32F2F"},
    "Groundnut": {"emoji": "🥜", "color": "#F9A825"},
    "Paddy": {"emoji": "🍚", "color": "#1565C0"},
    "Gram": {"emoji": "🫘", "color": "#795548"},
    "Barley": {"emoji": "🌾", "color": "#8D6E63"},
    "Millet": {"emoji": "🌾", "color": "#A1887F"},
    "Pulses": {"emoji": "🫘", "color": "#795548"},
}

def get_crop_info(crop_name):
    for key in CROP_INFO:
        if key.lower() in crop_name.lower() or crop_name.lower() in key.lower():
            return CROP_INFO[key]
    return {"emoji": "🌱", "color": "#2E7D32"}

# ==========================================================
# FIXED: Update Farm Parameters
# ==========================================================

@router.put("/update-farm/{farm_id}")
async def update_farm_parameters(
    farm_id: int,
    district: str = None,
    farm_size: float = None,
    season: str = None,
    irrigation: str = None,
    db: Session = Depends(get_db)
):
    try:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        
        if not farm:
            raise HTTPException(status_code=404, detail="Farm not found")
        
        # Update fields if provided
        if district is not None and district != "":
            farm.district = district
        
        if farm_size is not None and farm_size > 0:
            farm.farm_size = farm_size
        
        if irrigation is not None and irrigation != "":
            farm.irrigation = irrigation
        
        # Handle season - check if column exists
        if season is not None and season != "":
            try:
                # Try to set season if column exists
                if hasattr(farm, 'season'):
                    farm.season = season
                else:
                    print(f"⚠️ 'season' column does not exist in farms table")
            except Exception as e:
                print(f"⚠️ Could not set season: {e}")
        
        db.commit()
        db.refresh(farm)
        
        return {
            "success": True,
            "message": "Farm parameters updated successfully",
            "farm": {
                "id": farm.id,
                "farm_name": farm.farm_name,
                "district": farm.district,
                "farm_size": farm.farm_size,
                "season": farm.season if hasattr(farm, 'season') else "Rabi",
                "irrigation": farm.irrigation
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Update error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update farm: {str(e)}"
        )

# ==========================================================
# Get Farm Parameters
# ==========================================================

@router.get("/farm-params/{farm_id}")
async def get_farm_parameters(
    farm_id: int,
    db: Session = Depends(get_db)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    
    return {
        "success": True,
        "farm": {
            "id": farm.id,
            "farm_name": farm.farm_name,
            "district": farm.district,
            "state": farm.state,
            "farm_size": farm.farm_size,
            "soil_type": farm.soil_type,
            "irrigation": farm.irrigation,
            "season": farm.season if hasattr(farm, 'season') else "Rabi",
            "crops": farm.crops
        }
    }

# ==========================================================
# ML Model Prediction
# ==========================================================

def predict_with_ml(farm_id: int, db: Session):
    """Use the ML model to predict crop"""
    
    try:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        if not farm:
            return None
        
        sensor = db.query(SensorData).filter(
            SensorData.farm_id == farm_id
        ).order_by(SensorData.created_at.desc()).first()
        
        if not sensor:
            return None
        
        # Get weather
        try:
            weather = get_weather(farm.district)
        except:
            weather = {"temperature": 28, "humidity": 65, "rainfall": 0}
        
        season = get_current_season()
        
        # Encode values
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
            "bore": "Drip"
        }
        irrigation_name = IRRIGATION_MAPPING.get(farm.irrigation.lower(), farm.irrigation)
        
        # Encode using encoders
        try:
            from ai.crop_ai import encode_soil, encode_irrigation, encode_season, decode_crop
            soil_encoded = encode_soil(soil_name)
            irrigation_encoded = encode_irrigation(irrigation_name)
            season_encoded = encode_season(season)
        except:
            # Fallback direct encoding
            soil_encoded = encoders["Soil_Type"].transform([soil_name])[0]
            irrigation_encoded = encoders["Irrigation_Type"].transform([irrigation_name])[0]
            season_encoded = encoders["Season"].transform([season])[0]
            decode_crop = lambda x: encoders["Recommended_Crop"].inverse_transform([x])[0]
        
        features = pd.DataFrame([{
            "N": sensor.nitrogen or 0,
            "P": sensor.phosphorus or 0,
            "K": sensor.potassium or 0,
            "Soil_pH": sensor.ph or 7,
            "Soil_Moisture": sensor.soil_moisture or 0,
            "Soil_Type": soil_encoded,
            "Temperature": weather["temperature"],
            "Humidity": weather["humidity"],
            "Rainfall": weather["rainfall"],
            "Season": season_encoded,
            "Irrigation_Type": irrigation_encoded
        }])
        
        prediction = ml_model.predict(features)[0]
        probabilities = ml_model.predict_proba(features)[0]
        
        crop_names = encoders["Recommended_Crop"].classes_
        crop = crop_names[prediction]
        confidence = round(max(probabilities) * 100, 2)
        
        top3_indices = np.argsort(probabilities)[-3:][::-1]
        top3 = []
        for idx in top3_indices:
            top3.append({
                "crop": crop_names[idx],
                "confidence": round(probabilities[idx] * 100, 2)
            })
        
        return {
            "crop": crop,
            "confidence": confidence,
            "top_3": top3,
            "crop_info": get_crop_info(crop)
        }
        
    except Exception as e:
        print(f"⚠️ ML Prediction error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==========================================================
# Gemini Recommendations
# ==========================================================

def get_gemini_recommendations(soil_data, farm_data, weather_data):
    if gemini_model is None:
        return None
    
    def clean_value(val):
        if val is None or val == "Unknown" or val == "":
            return "Not available"
        return val
    
    prompt = f"""
You are an expert agricultural advisor. Based on this data, recommend TOP 4 crops:

Location: {clean_value(farm_data.get('district', 'Unknown'))}
Season: {clean_value(farm_data.get('season', 'Rabi'))}
Soil: {clean_value(soil_data.get('soil_type', 'Unknown'))}
NPK: N={clean_value(soil_data.get('nitrogen', 'Unknown'))}, P={clean_value(soil_data.get('phosphorus', 'Unknown'))}, K={clean_value(soil_data.get('potassium', 'Unknown'))}
pH: {clean_value(soil_data.get('ph', 'Unknown'))}
Temp: {clean_value(weather_data.get('temperature', 'Unknown'))}°C

Return JSON: recommendations (rank, crop, suitability, season, water, yield, price, reason, sow, harvest, n, p, k, emoji, color), planting_calendar, soil_health_assessment (score, summary, recommendations). Return ONLY valid JSON.
"""
    
    try:
        response = gemini_model.generate_content(prompt)
        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return None

# ==========================================================
# Main Endpoint
# ==========================================================

@router.get("/recommend/{farm_id}")
async def get_crop_recommendations(
    farm_id: int,
    db: Session = Depends(get_db)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    
    sensor = db.query(SensorData).filter(
        SensorData.farm_id == farm_id
    ).order_by(SensorData.created_at.desc()).first()
    
    try:
        weather_data = get_weather(farm.district)
    except:
        weather_data = {"temperature": 28, "humidity": 65, "rainfall": 0}
    
    soil_data = {
        "nitrogen": sensor.nitrogen if sensor else "Unknown",
        "phosphorus": sensor.phosphorus if sensor else "Unknown",
        "potassium": sensor.potassium if sensor else "Unknown",
        "ph": sensor.ph if sensor else "Unknown",
        "soil_type": farm.soil_type or "Unknown"
    }
    
    farm_data = {
        "farm_name": farm.farm_name,
        "district": farm.district,
        "state": farm.state,
        "farm_size": farm.farm_size,
        "irrigation": farm.irrigation,
        "season": farm.season if hasattr(farm, 'season') else "Rabi",
        "soil_type": farm.soil_type or "Unknown"
    }
    
    ml_prediction = predict_with_ml(farm_id, db)
    gemini_result = get_gemini_recommendations(soil_data, farm_data, weather_data)
    
    response = {
        "success": True,
        "farm_id": farm_id,
        "farm_name": farm.farm_name,
        "ml_prediction": ml_prediction,
        "gemini_recommendations": gemini_result,
        "soil_data": soil_data,
        "weather_data": weather_data
    }
    
    if gemini_result is None:
        response["gemini_recommendations"] = get_fallback_recommendations()
        response["note"] = "Using fallback recommendations."
    
    return response

# ==========================================================
# Fallback Recommendations
# ==========================================================

def get_fallback_recommendations():
    return {
        "recommendations": [
            {"rank": 1, "crop": "Wheat", "suitability": 85, "season": "Rabi (Oct–Apr)", 
             "water": "Low", "yield": "40-50 q/acre", "price": "₹2,425/q", 
             "reason": "Recommended based on your soil conditions.", 
             "sow": "Oct 15 – Nov 15", "harvest": "Mar – Apr",
             "n": "120 kg/ha", "p": "60 kg/ha", "k": "40 kg/ha",
             "emoji": "🌾", "color": "#2E7D32"},
            {"rank": 2, "crop": "Mustard", "suitability": 78, "season": "Rabi (Oct–Feb)", 
             "water": "Low", "yield": "8-10 q/acre", "price": "₹5,200/q", 
             "reason": "Good alternative crop.", "sow": "Oct 1 – Oct 20", "harvest": "Jan – Feb",
             "n": "80 kg/ha", "p": "40 kg/ha", "k": "40 kg/ha",
             "emoji": "🌻", "color": "#F9A825"},
            {"rank": 3, "crop": "Chickpea", "suitability": 72, "season": "Rabi (Oct–Mar)", 
             "water": "Very Low", "yield": "6-8 q/acre", "price": "₹4,800/q", 
             "reason": "Fixes nitrogen in soil.", "sow": "Oct 25 – Nov 10", "harvest": "Mar",
             "n": "20 kg/ha", "p": "60 kg/ha", "k": "20 kg/ha",
             "emoji": "🫘", "color": "#795548"},
            {"rank": 4, "crop": "Potato", "suitability": 65, "season": "Rabi (Oct–Jan)", 
             "water": "Medium", "yield": "100-120 q/acre", "price": "₹1,200/q", 
             "reason": "High value cash crop.", "sow": "Oct 10 – Nov 5", "harvest": "Jan – Feb",
             "n": "150 kg/ha", "p": "100 kg/ha", "k": "120 kg/ha",
             "emoji": "🥔", "color": "#7B1FA2"}
        ],
        "planting_calendar": [
            {"crop": "Wheat", "sow": "Oct 15 – Nov 15", "harvest": "Mar – Apr", "emoji": "🌾", "color": "#2E7D32"},
            {"crop": "Mustard", "sow": "Oct 1 – Oct 20", "harvest": "Jan – Feb", "emoji": "🌻", "color": "#F9A825"},
            {"crop": "Chickpea", "sow": "Oct 25 – Nov 10", "harvest": "Mar", "emoji": "🫘", "color": "#795548"},
            {"crop": "Potato", "sow": "Oct 10 – Nov 5", "harvest": "Jan – Feb", "emoji": "🥔", "color": "#7B1FA2"}
        ],
        "soil_health_assessment": {
            "score": 75,
            "summary": "Your soil conditions are generally favorable.",
            "recommendations": "Maintain regular soil testing."
        }
    }