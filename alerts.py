from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Farm, SensorData

# Smart Alert Engine
from services.alert_engine import generate_alerts

# Optional imports
# Uncomment these when your APIs are ready
#
# from weather import get_weather_data
# from recommendation import get_crop_recommendation
# from fertilizer import get_fertilizer_recommendation
# from market import get_market_recommendation


router = APIRouter(
    prefix="/api",
    tags=["Smart Alerts"]
)


# ==========================================================
# Smart Alerts
# ==========================================================

@router.get("/alerts/{farm_id}")
def smart_alerts(

    farm_id: int,

    db: Session = Depends(get_db)

):

    # ======================================================
    # Farm
    # ======================================================

    farm = (

        db.query(Farm)

        .filter(Farm.id == farm_id)

        .first()

    )

    if farm is None:

        raise HTTPException(

            status_code=404,

            detail="Farm not found"

        )

    # ======================================================
    # Latest Sensor Values
    # ======================================================

    sensor = (

        db.query(SensorData)

        .filter(SensorData.farm_id == farm_id)

        .order_by(SensorData.created_at.desc())

        .first()

    )

    if sensor is None:

        raise HTTPException(

            status_code=404,

            detail="No Sensor Data Found"

        )

    # ======================================================
    # Weather
    # ======================================================

    weather = None

    try:

        # Replace with your function

        # weather = get_weather_data(farm_id)

        pass

    except Exception:

        weather = None

    # ======================================================
    # Crop Recommendation
    # ======================================================

    crop = None

    try:

        # Replace with your function

        # crop = get_crop_recommendation(farm_id)

        pass

    except Exception:

        crop = None

    # ======================================================
    # Fertilizer Recommendation
    # ======================================================

    fertilizer = None

    try:

        # Replace with your function

        # fertilizer = get_fertilizer_recommendation(farm_id)

        pass

    except Exception:

        fertilizer = None

    # ======================================================
    # Market Recommendation
    # ======================================================

    market = None

    try:

        # Replace with your function

        # market = get_market_recommendation(farm_id)

        pass

    except Exception:

        market = None

    # ======================================================
    # Generate AI Alerts
    # ======================================================

    result = generate_alerts(

        sensor=sensor,

        weather=weather,

        crop=crop,

        fertilizer=fertilizer,

        market=market

    )

    # ======================================================
    # Final Response
    # ======================================================

    return {

        "farm_id": farm.id,

        "farm_name": farm.farm_name,

        "generated_at": sensor.created_at,

        **result

    }