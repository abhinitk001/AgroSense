# disease.py - Plant.id API (FIXED PARSING)

import os
import json
import base64
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(
    prefix="/api/disease",
    tags=["Plant Disease Detection"]
)

# ==========================================================
# Plant.id API Configuration
# ==========================================================

PLANT_API_KEY = os.getenv("PLANT_API_KEY", "")
PLANT_URL = "https://plant.id/api/v3/health_assessment"

# ==========================================================
# Load Treatments
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TREATMENT_PATH = os.path.join(BASE_DIR, "ml", "disease_treatments.json")

try:
    with open(TREATMENT_PATH, "r") as f:
        TREATMENTS = json.load(f)
    print(f"✅ Loaded {len(TREATMENTS)} treatment records")
except:
    TREATMENTS = {}
    print("⚠️ Treatments not loaded")

# ==========================================================
# Helper Functions
# ==========================================================

def get_treatment(disease_name):
    if not disease_name:
        return {"medicine": "Consult local agricultural officer", "severity": "Unknown", "prevention": "Maintain proper care"}
    
    for key in TREATMENTS:
        if disease_name.lower() in key.lower() or key.lower() in disease_name.lower():
            return TREATMENTS[key]
    
    return {"medicine": "Consult local agricultural officer", "severity": "Medium", "prevention": "Maintain proper care"}

def get_confidence_level(confidence):
    if confidence >= 90: return "Excellent"
    elif confidence >= 80: return "High"
    elif confidence >= 65: return "Medium"
    else: return "Low"

def format_disease_name(name):
    return name.replace("_", " ").title()

def get_crop_name(disease):
    if "_" in disease:
        return disease.split("_")[0]
    return "Unknown"

# ==========================================================
# Main Predict Endpoint - Plant.id API
# ==========================================================

@router.post("/predict")
async def predict(file: UploadFile = File(...)):
    """
    Upload a leaf image and predict diseases using Plant.id API.
    """
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Please upload a valid image.")

        image_bytes = await file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        print(f"📸 Image uploaded: {file.filename}, size: {len(image_bytes)} bytes")

        if not PLANT_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Plant.id API key not configured. Please set PLANT_API_KEY in .env file."
            )

        headers = {
            "Content-Type": "application/json",
            "Api-Key": PLANT_API_KEY
        }
        
        data = {
            "images": [image_base64],
            "health": "only"
        }

        print(f"📡 Calling Plant.id API: {PLANT_URL}")
        
        response = requests.post(PLANT_URL, headers=headers, json=data, timeout=30)

        print(f"📡 Plant.id API response status: {response.status_code}")

        if response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Invalid Plant.id API key. Please check your PLANT_API_KEY in .env"
            )
        elif response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Plant.id API rate limit exceeded. You have used all free credits."
            )
        elif response.status_code != 200 and response.status_code != 201:
            error_msg = "Unknown error"
            try:
                error_data = response.json()
                error_msg = error_data.get("message", error_data.get("error", str(response.text)))
            except:
                error_msg = response.text[:200] if response.text else "Unknown error"
            
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Plant.id API error: {error_msg}"
            )

        result = response.json()
        print(f"✅ Plant.id API response received")

        # ==========================================================
        # FIXED: Parse the response correctly
        # ==========================================================
        
        # Get disease suggestions
        disease_data = result.get("result", {}).get("disease", {})
        suggestions = disease_data.get("suggestions", [])
        
        # Get health status
        is_healthy = result.get("result", {}).get("is_healthy", {})
        is_healthy_binary = is_healthy.get("binary", False)
        health_probability = is_healthy.get("probability", 0)
        
        # Get plant detection
        is_plant = result.get("result", {}).get("is_plant", {})
        is_plant_probability = is_plant.get("probability", 0)

        print(f"🌿 Is Plant: {is_plant_probability * 100:.2f}%")
        print(f"🌿 Is Healthy: {is_healthy_binary} ({health_probability * 100:.2f}%)")
        print(f"🌿 Suggestions found: {len(suggestions)}")

        # If no diseases detected or plant is healthy
        if not suggestions or is_healthy_binary:
            return JSONResponse({
                "success": True,
                "message": "No diseases detected. Plant appears healthy.",
                "method": "Plant.id API",
                "prediction": {
                    "crop": "Unknown",
                    "disease": "Healthy Plant",
                    "confidence": round(health_probability * 100, 2) if health_probability else 100.0,
                    "confidence_level": "Excellent",
                    "health_status": "Healthy",
                    "medicine": "None",
                    "severity": "None",
                    "prevention": "Continue regular care",
                    "is_plant_confidence": round(is_plant_probability * 100, 2),
                    "top_predictions": []
                }
            })

        # Build top predictions list
        top_predictions = []
        for suggestion in suggestions[:5]:
            top_predictions.append({
                "class": suggestion.get("name", "Unknown"),
                "confidence": round(suggestion.get("probability", 0) * 100, 2)
            })

        # Get top disease suggestion
        top_disease = suggestions[0]
        disease_name = top_disease.get("name", "Unknown Disease")
        probability = top_disease.get("probability", 0) * 100
        
        # Try to get details - they might be in a separate call
        # For now, use local treatment data
        local_treatment = get_treatment(disease_name)

        # Extract crop name from disease
        crop = get_crop_name(disease_name)
        
        # If crop is unknown, try to find from disease name
        if crop == "Unknown":
            # Common crop names to check
            common_crops = ["Tomato", "Potato", "Corn", "Wheat", "Rice", "Sugarcane", "Soybean", "Cotton"]
            for c in common_crops:
                if c.lower() in disease_name.lower():
                    crop = c
                    break

        print(f"🔍 Final Prediction: {disease_name} ({probability:.2f}%)")
        print(f"   Crop: {crop}")
        print(f"   Health Status: {'Diseased' if not is_healthy_binary else 'Healthy'}")

        return JSONResponse({
            "success": True,
            "message": "Prediction completed successfully",
            "method": "Plant.id API",
            "prediction": {
                "crop": crop,
                "disease": disease_name,
                "confidence": round(probability, 2),
                "confidence_level": get_confidence_level(probability),
                "health_status": "Diseased" if not is_healthy_binary else "Healthy",
                "medicine": local_treatment.get("medicine", "Consult local agricultural officer"),
                "severity": local_treatment.get("severity", "Medium"),
                "prevention": local_treatment.get("prevention", "Maintain proper crop care practices"),
                "is_plant_confidence": round(is_plant_probability * 100, 2),
                "health_probability": round(health_probability * 100, 2),
                "top_predictions": top_predictions
            }
        })

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API request failed: {str(e)}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Prediction Error: {str(e)}")

# ==========================================================
# Check Credits
# ==========================================================

@router.get("/credits")
async def check_credits():
    if not PLANT_API_KEY:
        return {"error": "Plant.id API key not configured"}
    
    headers = {"Api-Key": PLANT_API_KEY}
    url = "https://plant.id/api/v3/usage_info"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "credits_remaining": data.get("credits", "Unknown"),
                "plan": data.get("plan", "Unknown")
            }
        else:
            return {"success": False, "error": f"Failed to check credits: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==========================================================
# Health Check
# ==========================================================

@router.get("/")
def disease_status():
    return {
        "service": "AgriSense Disease Detection",
        "status": "Running",
        "provider": "Plant.id API",
        "api_url": PLANT_URL,
        "api_key_configured": bool(PLANT_API_KEY)
    }

@router.get("/test")
def test():
    return {
        "message": "Disease Detection API is working",
        "status": "OK",
        "api_url": PLANT_URL,
        "api_key_configured": bool(PLANT_API_KEY)
    }