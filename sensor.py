from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import SensorData, Farm
from schemas import SensorDataCreate, SensorDataResponse

router = APIRouter(tags=["Sensor API"])


# ==========================================================
# SAVE SENSOR DATA (ESP32)
# ==========================================================

@router.post(
    "/api/sensors",
    response_model=SensorDataResponse
   
)

def save_sensor_data(
    sensor: SensorDataCreate,
    db: Session = Depends(get_db)
):

    # Check Farm Exists

    farm = db.query(Farm).filter(
        Farm.id == sensor.farm_id
    ).first()

    if not farm:
        raise HTTPException(
            status_code=404,
            detail="Farm not found"
        )

    sensor_data = SensorData(

        farm_id=sensor.farm_id,

        nitrogen=sensor.nitrogen,
        phosphorus=sensor.phosphorus,
        potassium=sensor.potassium,

        ph=sensor.ph,

        tds=sensor.tds,

        soil_moisture=sensor.soil_moisture,

        temperature=sensor.temperature,
        humidity=sensor.humidity,

        node_id=sensor.node_id,

        signal_strength=sensor.signal_strength,

        battery_voltage=sensor.battery_voltage

    )

    db.add(sensor_data)
    db.commit()
    db.refresh(sensor_data)

    return sensor_data


# ==========================================================
# GET LATEST SENSOR DATA
# ==========================================================

@router.get(
    "/api/latest/{farm_id}",
    response_model=SensorDataResponse
)
def get_latest_sensor(
    farm_id: int,
    db: Session = Depends(get_db)
):

    latest = db.query(SensorData)\
        .filter(
            SensorData.farm_id == farm_id
        )\
        .order_by(
            SensorData.created_at.desc()
        )\
        .first()

    if not latest:
        raise HTTPException(
            status_code=404,
            detail="No Sensor Data Found"
        )

    return latest


# ==========================================================
# GET SENSOR HISTORY
# ==========================================================

@router.get("/api/history/{farm_id}")
def sensor_history(
    farm_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):

    history = db.query(SensorData)\
        .filter(
            SensorData.farm_id == farm_id
        )\
        .order_by(
            SensorData.created_at.desc()
        )\
        .limit(limit)\
        .all()

    return history


# ==========================================================
# DELETE SENSOR HISTORY
# ==========================================================

@router.delete("/api/history/{farm_id}")
def delete_sensor_history(
    farm_id: int,
    db: Session = Depends(get_db)
):

    readings = db.query(SensorData).filter(
        SensorData.farm_id == farm_id
    ).all()

    if not readings:
        raise HTTPException(
            status_code=404,
            detail="No Sensor Data Found"
        )

    for reading in readings:
        db.delete(reading)

    db.commit()

    return {
        "message": "Sensor history deleted successfully"
    }


# ==========================================================
# GET SENSOR COUNT
# ==========================================================

@router.get("/api/count/{farm_id}")
def sensor_count(
    farm_id: int,
    db: Session = Depends(get_db)
):

    count = db.query(SensorData)\
        .filter(
            SensorData.farm_id == farm_id
        )\
        .count()

    return {
        "farm_id": farm_id,
        "total_readings": count
    }