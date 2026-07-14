# market_cache.py - Background cache manager for market prices

import os
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db
from models import MarketCache, Farm

load_dotenv()

# ==========================================================
# GOVERNMENT API CONFIGURATION
# ==========================================================

API_KEY = os.getenv("DATA_GOV_API_KEY")

if API_KEY is None:
    raise Exception("DATA_GOV_API_KEY not found in .env file")

BASE_URL = (
    "https://api.data.gov.in/resource/"
    "35985678-0d79-46b4-9ed6-6f13308a1d24"
)

DEFAULT_LIMIT = 500

# ==========================================================
# CROP NAME MAPPING (AI Names → API Names)
# ==========================================================

CROP_MAPPING = {
    "Wheat": ["Wheat", "Gehun", "Wheat (Gehun)"],
    "Rice": ["Rice", "Paddy", "Paddy(Dhan)", "Rice (Paddy)"],
    "Maize": ["Maize", "Corn", "Maize/Corn"],
    "Corn": ["Maize", "Corn", "Maize/Corn"],
    "Mustard": ["Mustard", "Sarson", "Mustard (Sarson)"],
    "Chickpea": ["Chickpea", "Gram", "Chana", "Bengal Gram"],
    "Potato": ["Potato", "Aloo"],
    "Sugarcane": ["Sugarcane", "Ganna"],
    "Soybean": ["Soybean"],
    "Cotton": ["Cotton", "Kapas"],
    "Tomato": ["Tomato", "Tamatar"],
    "Onion": ["Onion", "Pyaz"],
    "Groundnut": ["Groundnut", "Moongfali"],
    "Paddy": ["Paddy", "Dhan"],
    "Gram": ["Gram", "Chana"],
    "Millet": ["Millet", "Bajra"],
}

API_TO_AI_MAPPING = {}
for ai_name, api_names in CROP_MAPPING.items():
    for api_name in api_names:
        API_TO_AI_MAPPING[api_name.lower()] = ai_name

def get_ai_crop_name(api_name: str) -> str:
    if not api_name:
        return api_name
    return API_TO_AI_MAPPING.get(api_name.lower(), api_name)

# ==========================================================
# API CALL FUNCTION
# ==========================================================

def call_market_api(
    commodity: str = None,
    state: str = None,
    district: str = None,
    limit: int = DEFAULT_LIMIT
):
    params = {
        "api-key": API_KEY,
        "format": "json",
        "limit": limit
    }

    if commodity:
        params["filters[Commodity]"] = commodity
    if state:
        params["filters[State]"] = state
    if district:
        params["filters[District]"] = district

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=60
        )
        if response.status_code != 200:
            print(f"⚠️ API Error: {response.status_code}")
            return None
        return response.json()
    except requests.exceptions.Timeout:
        print(f"⚠️ API Timeout")
        return None
    except Exception as e:
        print(f"⚠️ API Error: {e}")
        return None

# ==========================================================
# CLEAN RECORD
# ==========================================================

def clean_record(record):
    try:
        return {
            "commodity": record.get("Commodity", "").strip(),
            "variety": record.get("Variety", "").strip(),
            "market": record.get("Market", "").strip(),
            "district": record.get("District", "").strip(),
            "state": record.get("State", "").strip(),
            "arrival_date": record.get("Arrival_Date", "").strip(),
            "minimum_price": float(record.get("Min_Price", 0) or 0),
            "maximum_price": float(record.get("Max_Price", 0) or 0),
            "modal_price": float(record.get("Modal_Price", 0) or 0),
        }
    except Exception as e:
        print(f"⚠️ Error cleaning record: {e}")
        return None

# ==========================================================
# FETCH ALL CROPS FOR CACHE (with fallback)
# ==========================================================

def fetch_all_market_data():
    """Fetch market data from government API with fallback"""
    all_records = []
    batch_size = 100
    offset = 0
    max_records = 2000
    
    print(f"🔄 Fetching market data in batches of {batch_size}...")
    
    while len(all_records) < max_records:
        try:
            params = {
                "api-key": API_KEY,
                "format": "json",
                "limit": batch_size,
                "offset": offset
            }
            
            response = requests.get(
                BASE_URL,
                params=params,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"⚠️ API Error at offset {offset}: {response.status_code}")
                break
            
            data = response.json()
            records = data.get("records", [])
            
            if not records:
                break
            
            for record in records:
                cleaned = clean_record(record)
                if cleaned:
                    all_records.append(cleaned)
            
            print(f"   ✅ Batch {offset//batch_size + 1}: Fetched {len(records)} records (Total: {len(all_records)})")
            
            if len(records) < batch_size:
                break
                
            offset += batch_size
            
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout at offset {offset}, stopping fetch")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            break
    
    print(f"✅ Total records fetched: {len(all_records)}")
    return all_records

# ==========================================================
# STORE IN CACHE
# ==========================================================

def store_in_cache(db: Session, records: list):
    if not records:
        return 0
    
    db.query(MarketCache).delete()
    db.commit()
    
    count = 0
    for record in records:
        try:
            cache_entry = MarketCache(
                commodity=record["commodity"],
                variety=record["variety"],
                market=record["market"],
                district=record["district"],
                state=record["state"],
                arrival_date=record["arrival_date"],
                minimum_price=record["minimum_price"],
                maximum_price=record["maximum_price"],
                modal_price=record["modal_price"],
                cached_at=datetime.now()
            )
            db.add(cache_entry)
            count += 1
            
            if count % 100 == 0:
                db.commit()
                
        except Exception as e:
            print(f"⚠️ Error storing record: {e}")
            continue
    
    db.commit()
    print(f"✅ Successfully stored {count} records in cache")
    return count

# ==========================================================
# MOCK DATA (Fallback when API is down)
# ==========================================================

def get_mock_market_data():
    """Return mock market data for testing"""
    return [
        # Punjab Records
        {
            "commodity": "Wheat",
            "variety": "Local",
            "market": "Ludhiana Mandi",
            "district": "Ludhiana",
            "state": "Punjab",
            "arrival_date": "12/07/2026",
            "minimum_price": 2350,
            "maximum_price": 2500,
            "modal_price": 2425
        },
        {
            "commodity": "Rice",
            "variety": "Pusa-1121",
            "market": "Ludhiana Mandi",
            "district": "Ludhiana",
            "state": "Punjab",
            "arrival_date": "12/07/2026",
            "minimum_price": 1800,
            "maximum_price": 1950,
            "modal_price": 1850
        },
        {
            "commodity": "Millet",
            "variety": "Local",
            "market": "Ludhiana Mandi",
            "district": "Ludhiana",
            "state": "Punjab",
            "arrival_date": "12/07/2026",
            "minimum_price": 1800,
            "maximum_price": 2100,
            "modal_price": 1950
        },
        {
            "commodity": "Potato",
            "variety": "Local",
            "market": "Jalandhar Mandi",
            "district": "Jalandhar",
            "state": "Punjab",
            "arrival_date": "12/07/2026",
            "minimum_price": 800,
            "maximum_price": 1200,
            "modal_price": 1000
        },
        {
            "commodity": "Mustard",
            "variety": "Local",
            "market": "Bathinda Mandi",
            "district": "Bathinda",
            "state": "Punjab",
            "arrival_date": "12/07/2026",
            "minimum_price": 5200,
            "maximum_price": 5600,
            "modal_price": 5450
        },
        {
            "commodity": "Cotton",
            "variety": "Local",
            "market": "Bathinda Mandi",
            "district": "Bathinda",
            "state": "Punjab",
            "arrival_date": "12/07/2026",
            "minimum_price": 6000,
            "maximum_price": 6500,
            "modal_price": 6200
        },
        # Maharashtra Records (for your farm)
        {
            "commodity": "Millet",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 2000,
            "maximum_price": 2300,
            "modal_price": 2150
        },
        {
            "commodity": "Wheat",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 2500,
            "maximum_price": 2700,
            "modal_price": 2600
        },
        {
            "commodity": "Rice",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 2000,
            "maximum_price": 2200,
            "modal_price": 2100
        },
        {
            "commodity": "Potato",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 1200,
            "maximum_price": 1600,
            "modal_price": 1400
        },
        {
            "commodity": "Tomato",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 1800,
            "maximum_price": 2800,
            "modal_price": 2300
        },
        {
            "commodity": "Onion",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 1500,
            "maximum_price": 2000,
            "modal_price": 1750
        },
        {
            "commodity": "Soybean",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 4500,
            "maximum_price": 5000,
            "modal_price": 4800
        },
        {
            "commodity": "Groundnut",
            "variety": "Local",
            "market": "Mumbai Mandi",
            "district": "Mumbai",
            "state": "Maharashtra",
            "arrival_date": "12/07/2026",
            "minimum_price": 5800,
            "maximum_price": 6200,
            "modal_price": 6000
        }
    ]

# ==========================================================
# MAIN CACHE UPDATE FUNCTION
# ==========================================================

def update_market_cache():
    print(f"\n🔄 Updating market cache at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    db = next(get_db())
    
    try:
        records = fetch_all_market_data()
        
        if not records:
            print("⚠️ No records from API, using mock data...")
            records = get_mock_market_data()
            
            if records:
                db.query(MarketCache).delete()
                db.commit()
                
                for record in records:
                    cache_entry = MarketCache(
                        commodity=record["commodity"],
                        variety=record.get("variety", "Local"),
                        market=record["market"],
                        district=record["district"],
                        state=record["state"],
                        arrival_date=record.get("arrival_date", datetime.now().strftime("%d/%m/%Y")),
                        minimum_price=record["minimum_price"],
                        maximum_price=record["maximum_price"],
                        modal_price=record["modal_price"],
                        cached_at=datetime.now()
                    )
                    db.add(cache_entry)
                
                db.commit()
                print(f"✅ Stored {len(records)} mock records in cache")
                return
        
        count = store_in_cache(db, records)
        print(f"✅ Market cache updated successfully: {count} records")
        
    except Exception as e:
        print(f"❌ Error updating market cache: {e}")
        db.rollback()
    finally:
        db.close()

# ==========================================================
# GET CACHED MARKET DATA
# ==========================================================

def get_cached_market_data(
    db: Session,
    state: str = None,
    district: str = None,
    crop: str = None,
    limit: int = 100
):
    query = db.query(MarketCache)
    
    if state:
        query = query.filter(MarketCache.state == state)
    
    if district:
        query = query.filter(MarketCache.district == district)
    
    if crop:
        crop_lower = crop.lower()
        if crop in CROP_MAPPING:
            api_names = CROP_MAPPING[crop]
            query = query.filter(MarketCache.commodity.in_(api_names))
        else:
            query = query.filter(MarketCache.commodity.like(f"%{crop}%"))
    
    results = query.order_by(
        MarketCache.cached_at.desc(),
        MarketCache.modal_price.desc()
    ).limit(limit).all()
    
    formatted_results = []
    for r in results:
        formatted_results.append({
            "commodity": r.commodity,
            "ai_crop": get_ai_crop_name(r.commodity),
            "variety": r.variety,
            "market": r.market,
            "district": r.district,
            "state": r.state,
            "arrival_date": r.arrival_date,
            "minimum_price": r.minimum_price,
            "maximum_price": r.maximum_price,
            "modal_price": r.modal_price,
            "cached_at": r.cached_at.strftime("%Y-%m-%d %H:%M:%S") if r.cached_at else None
        })
    
    return formatted_results

# ==========================================================
# GET CACHE STATUS
# ==========================================================

def get_cache_status(db: Session):
    total = db.query(MarketCache).count()
    
    if total == 0:
        return {
            "status": "empty",
            "records": 0,
            "last_updated": None,
            "message": "Cache is empty. Please run cache update."
        }
    
    latest = db.query(MarketCache).order_by(MarketCache.cached_at.desc()).first()
    states = db.query(MarketCache.state).distinct().count()
    districts = db.query(MarketCache.district).distinct().count()
    commodities = db.query(MarketCache.commodity).distinct().count()
    
    return {
        "status": "ready",
        "records": total,
        "states": states,
        "districts": districts,
        "commodities": commodities,
        "last_updated": latest.cached_at.strftime("%Y-%m-%d %H:%M:%S") if latest else None,
        "message": f"Cache contains {total} records for {commodities} commodities"
    }