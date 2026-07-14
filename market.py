# market.py - Updated with Gemini fallback and source tracking

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os
import requests
import json
import re
from dotenv import load_dotenv

from database import get_db
from models import Farm, MarketCache

from market_cache import (
    get_cached_market_data,
    get_cache_status,
    get_ai_crop_name,
    CROP_MAPPING,
    call_market_api,
    clean_record
)

load_dotenv()

router = APIRouter(
    prefix="/api/market",
    tags=["Market Prices"]
)

# ==========================================================
# GEMINI API CONFIGURATION
# ==========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
gemini_model = None

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini API configured for market price estimation")
    except Exception as e:
        print(f"⚠️ Gemini configuration error: {e}")
else:
    print("⚠️ GEMINI_API_KEY not found in .env")

# ==========================================================
# DATA.GOV CONFIGURATION
# ==========================================================

API_KEY = os.getenv("DATA_GOV_API_KEY")
if API_KEY is None:
    raise Exception("DATA_GOV_API_KEY not found in .env file")

BASE_URL = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"

# ==========================================================
# GEMINI PRICE ESTIMATION
# ==========================================================

def get_gemini_market_prices(crop: str, state: str, district: str):
    """
    Use Gemini to estimate market prices when government API is down
    """
    if gemini_model is None:
        return None
    
    prompt = f"""
You are an agricultural market expert. Provide estimated current market prices for {crop} in {district}, {state}, India.

Based on your knowledge of Indian agricultural markets, provide:
1. Estimated modal price (₹ per quintal)
2. Estimated minimum price
3. Estimated maximum price
4. A brief market trend analysis (2-3 sentences)

Format the response as JSON:
{{
    "commodity": "{crop}",
    "state": "{state}",
    "district": "{district}",
    "modal_price": 2425,
    "minimum_price": 2350,
    "maximum_price": 2500,
    "trend": "Prices are stable with slight upward movement due to seasonal demand.",
    "source": "Gemini AI (estimated)"
}}

Return ONLY valid JSON, no other text.
"""
    
    try:
        response = gemini_model.generate_content(prompt)
        response_text = response.text
        
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            result = json.loads(json_str)
            return result
        else:
            return None
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return None

# ==========================================================
# MOCK DATA FOR SPECIFIC CROP (Last Resort)
# ==========================================================

def get_mock_data_for_crop(crop: str, state: str, district: str):
    crop_prices = {
        "Wheat": {"modal": 2425, "min": 2350, "max": 2500},
        "Rice": {"modal": 1850, "min": 1800, "max": 1950},
        "Maize": {"modal": 1962, "min": 1900, "max": 2050},
        "Millet": {"modal": 1950, "min": 1800, "max": 2100},
        "Potato": {"modal": 1000, "min": 800, "max": 1200},
        "Tomato": {"modal": 2000, "min": 1500, "max": 2500},
        "Onion": {"modal": 1500, "min": 1200, "max": 1800},
        "Mustard": {"modal": 5450, "min": 5200, "max": 5600},
        "Cotton": {"modal": 6200, "min": 6000, "max": 6500},
        "Sugarcane": {"modal": 3050, "min": 3000, "max": 3200},
        "Chickpea": {"modal": 4800, "min": 4500, "max": 5200},
        "Soybean": {"modal": 4300, "min": 4000, "max": 4500},
        "Groundnut": {"modal": 5500, "min": 5000, "max": 5800}
    }
    
    if crop not in crop_prices:
        for key in crop_prices:
            if key.lower() in crop.lower() or crop.lower() in key.lower():
                crop = key
                break
        else:
            return None
    
    prices = crop_prices.get(crop)
    if not prices:
        return None
    
    return {
        "commodity": crop,
        "variety": "Local",
        "market": f"{district} Mandi",
        "district": district,
        "state": state,
        "arrival_date": datetime.now().strftime("%d/%m/%Y"),
        "minimum_price": prices["min"],
        "maximum_price": prices["max"],
        "modal_price": prices["modal"],
        "source": "mock_data",
        "trend": "Estimated price based on national averages"
    }

# ==========================================================
# ENDPOINTS
# ==========================================================

@router.get("/cache-status")
def cache_status(db: Session = Depends(get_db)):
    return get_cache_status(db)

@router.get("/recommended/{farm_id}")
def recommended_market_price(
    farm_id: int,
    db: Session = Depends(get_db)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Get recommended crop from AI
    try:
        response = requests.get(
            f"http://127.0.0.1:8000/api/recommendation/{farm_id}",
            timeout=10
        )
        if response.status_code != 200:
            recommended_crop = list(CROP_MAPPING.keys())[0] if CROP_MAPPING else "Wheat"
        else:
            data = response.json()
            recommended_crop = data.get("recommended_crop", "Wheat")
    except Exception as e:
        print(f"⚠️ Error fetching AI recommendation: {e}")
        recommended_crop = "Wheat"

    # === Try Cache First ===
    cached_data = get_cached_market_data(
        db=db,
        state=farm.state,
        district=farm.district,
        crop=recommended_crop,
        limit=20
    )

    if cached_data:
        modal_prices = [r["modal_price"] for r in cached_data if r["modal_price"] > 0]
        if modal_prices:
            highest = max(cached_data, key=lambda x: x["modal_price"])
            lowest = min(cached_data, key=lambda x: x["modal_price"])
            average = sum(modal_prices) / len(modal_prices)

            return {
                "recommended_crop": recommended_crop,
                "state": farm.state,
                "district": farm.district,
                "total_markets": len(cached_data),
                "average_price": round(average, 2),
                "highest_market": highest,
                "lowest_market": lowest,
                "markets": cached_data,
                "source": "government_api",
                "source_label": "📊 Government API (AGMARKNET)",
                "cached_at": cached_data[0]["cached_at"] if cached_data else None
            }

    # === Try Gemini API ===
    print(f"🔄 Cache empty. Trying Gemini for {recommended_crop} in {farm.district}...")
    gemini_data = get_gemini_market_prices(recommended_crop, farm.state, farm.district)

    if gemini_data:
        return {
            "recommended_crop": recommended_crop,
            "state": farm.state,
            "district": farm.district,
            "total_markets": 1,
            "average_price": gemini_data.get("modal_price", 0),
            "highest_market": gemini_data,
            "lowest_market": gemini_data,
            "markets": [gemini_data],
            "source": "gemini_ai",
            "source_label": "🤖 Gemini AI (Estimated)",
            "trend": gemini_data.get("trend", "No trend data available")
        }

    # === Fallback to Mock Data ===
    print(f"⚠️ Gemini failed. Using mock data for {recommended_crop}...")
    mock_data = get_mock_data_for_crop(recommended_crop, farm.state, farm.district)

    if mock_data:
        return {
            "recommended_crop": recommended_crop,
            "state": farm.state,
            "district": farm.district,
            "total_markets": 1,
            "average_price": mock_data["modal_price"],
            "highest_market": mock_data,
            "lowest_market": mock_data,
            "markets": [mock_data],
            "source": "mock_data",
            "source_label": "📋 Mock Data (Fallback)",
            "message": "Using estimated prices (government API unavailable)"
        }

    return {
        "recommended_crop": recommended_crop,
        "state": farm.state,
        "district": farm.district,
        "total_markets": 0,
        "average_price": 0,
        "highest_market": None,
        "lowest_market": None,
        "markets": [],
        "message": "Unable to fetch market data. Please try again later.",
        "source": "empty",
        "source_label": "❌ No Data Available"
    }

@router.get("/all/{farm_id}")
def all_crop_prices(
    farm_id: int,
    db: Session = Depends(get_db)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    cached_data = get_cached_market_data(
        db=db,
        state=farm.state,
        district=farm.district,
        limit=500
    )

    if not cached_data:
        return {
            "state": farm.state,
            "district": farm.district,
            "total_crops": 0,
            "crops": [],
            "message": "No market data available in cache",
            "source": "empty",
            "source_label": "❌ No Data Available"
        }

    crops_dict = {}
    for item in cached_data:
        ai_name = item.get("ai_crop", item["commodity"])
        if ai_name not in crops_dict:
            crops_dict[ai_name] = {
                "crop": ai_name,
                "price": item["modal_price"],
                "market": item["market"],
                "variety": item["variety"],
                "district": item["district"],
                "state": item["state"]
            }
        else:
            if item["modal_price"] > crops_dict[ai_name]["price"]:
                crops_dict[ai_name] = {
                    "crop": ai_name,
                    "price": item["modal_price"],
                    "market": item["market"],
                    "variety": item["variety"],
                    "district": item["district"],
                    "state": item["state"]
                }

    crops_list = sorted(crops_dict.values(), key=lambda x: x["price"], reverse=True)

    return {
        "state": farm.state,
        "district": farm.district,
        "total_crops": len(crops_list),
        "crops": crops_list,
        "source": "government_api",
        "source_label": "📊 Government API (AGMARKNET)",
        "cached_at": cached_data[0]["cached_at"] if cached_data else None
    }

@router.get("/search")
def search_crop(
    commodity: str,
    state: str = None,
    district: str = None,
    db: Session = Depends(get_db)
):
    cached_data = get_cached_market_data(
        db=db,
        state=state,
        district=district,
        crop=commodity,
        limit=50
    )

    if cached_data:
        return {
            "commodity": commodity,
            "count": len(cached_data),
            "records": cached_data,
            "source": "government_api",
            "source_label": "📊 Government API (AGMARKNET)"
        }

    try:
        data = call_market_api(
            commodity=commodity,
            state=state,
            district=district,
            limit=50
        )
        
        if data:
            records = data.get("records", [])
            result = []
            for item in records:
                cleaned = clean_record(item)
                if cleaned:
                    result.append(cleaned)
            
            return {
                "commodity": commodity,
                "count": len(result),
                "records": result,
                "source": "government_api",
                "source_label": "📊 Government API (AGMARKNET)"
            }
    except Exception as e:
        print(f"⚠️ Search fallback error: {e}")

    return {
        "commodity": commodity,
        "count": 0,
        "records": [],
        "source": "empty",
        "source_label": "❌ No Data Available",
        "message": "No data available. Please try again later."
    }

@router.get("/latest")
def latest_market_update(db: Session = Depends(get_db)):
    cached_data = get_cached_market_data(
        db=db,
        limit=20
    )

    if cached_data:
        return {
            "records": cached_data,
            "source": "government_api",
            "source_label": "📊 Government API (AGMARKNET)",
            "cached_at": cached_data[0]["cached_at"] if cached_data else None
        }

    try:
        data = call_market_api(limit=20)
        if data:
            records = data.get("records", [])
            result = []
            for item in records:
                cleaned = clean_record(item)
                if cleaned:
                    result.append(cleaned)
            
            return {
                "records": result,
                "source": "government_api",
                "source_label": "📊 Government API (AGMARKNET)"
            }
    except Exception as e:
        print(f"⚠️ Latest fallback error: {e}")

    return {
        "records": [],
        "source": "empty",
        "source_label": "❌ No Data Available",
        "message": "No data available"
    }

@router.get("/")
def market_status():
    return {
        "service": "AgriSense Market API",
        "status": "Running",
        "provider": "Government of India + Gemini AI",
        "dataset": "AGMARKNET",
        "cache_enabled": True,
        "gemini_enabled": bool(gemini_model),
        "crop_mappings": len(CROP_MAPPING)
    }

@router.post("/update-cache")
def trigger_cache_update():
    from market_cache import update_market_cache
    
    try:
        update_market_cache()
        return {
            "success": True,
            "message": "Cache update triggered successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Cache update failed: {str(e)}"
        }