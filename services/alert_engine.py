"""
==========================================================
AgroSense Smart Alert Engine
==========================================================

This file contains all business logic for generating
AI-powered smart alerts.

Priority Levels

100 = Critical
80  = High
60  = Medium
40  = Low
20  = Information

Only Top 3 alerts are returned.

==========================================================
"""

from datetime import datetime


# ==========================================================
# Alert Priorities
# ==========================================================

CRITICAL = 100
HIGH = 80
MEDIUM = 60
LOW = 40
INFO = 20


# ==========================================================
# Alert Levels
# ==========================================================

LEVEL_CRITICAL = "critical"
LEVEL_WARNING = "warning"
LEVEL_INFO = "info"
LEVEL_SUCCESS = "success"


# ==========================================================
# Alert Icons
# ==========================================================

ICONS = {

    "moisture": "💧",

    "nitrogen": "🌿",

    "phosphorus": "🧪",

    "potassium": "🍃",

    "temperature": "🌡️",

    "humidity": "☁️",

    "ph": "⚗️",

    "weather": "🌧️",

    "crop": "🌾",

    "fertilizer": "🧴",

    "market": "📈",

    "healthy": "✅"

}


# ==========================================================
# Smart Alert Class
# ==========================================================

class SmartAlert:

    def __init__(

        self,

        priority,

        level,

        icon,

        title,

        message,

        recommendation

    ):

        self.priority = priority

        self.level = level

        self.icon = icon

        self.title = title

        self.message = message

        self.recommendation = recommendation

        self.time = datetime.now().strftime("%I:%M %p")

    def to_dict(self):

        return {

            "priority": self.priority,

            "level": self.level,

            "icon": self.icon,

            "title": self.title,

            "message": self.message,

            "recommendation": self.recommendation,

            "time": self.time

        }


# ==========================================================
# Alert Engine
# ==========================================================

class AlertEngine:

    def __init__(

        self,

        sensor,

        weather=None,

        crop=None,

        fertilizer=None,

        market=None

    ):

        self.sensor = sensor

        self.weather = weather

        self.crop = crop

        self.fertilizer = fertilizer

        self.market = market

        self.alerts = []


# ==========================================================
# Helper
# ==========================================================

    def add(

        self,

        priority,

        level,

        icon,

        title,

        message,

        recommendation

    ):

        self.alerts.append(

            SmartAlert(

                priority,

                level,

                icon,

                title,

                message,

                recommendation

            )

        )


# ==========================================================
# Soil Moisture Rules
# ==========================================================

    def check_soil_moisture(self):

        moisture = self.sensor.soil_moisture

        if moisture < 25:

            self.add(

                CRITICAL,

                LEVEL_CRITICAL,

                ICONS["moisture"],

                "Critical Soil Moisture",

                f"Soil moisture is only {moisture}%",

                "Start irrigation immediately."

            )

        elif moisture < 40:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["moisture"],

                "Low Soil Moisture",

                f"Soil moisture is {moisture}%",

                "Plan irrigation within 12 hours."

            )

        elif moisture > 90:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["moisture"],

                "Water Logging Risk",

                f"Soil moisture is {moisture}%",

                "Reduce irrigation and improve drainage."

            )


# ==========================================================
# Nitrogen Rules
# ==========================================================

    def check_nitrogen(self):

        n = self.sensor.nitrogen

        if n < 30:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["nitrogen"],

                "Nitrogen Deficiency",

                f"Nitrogen = {n}",

                "Apply Urea fertilizer."

            )

        elif n > 120:

            self.add(

                MEDIUM,

                LEVEL_WARNING,

                ICONS["nitrogen"],

                "High Nitrogen",

                f"Nitrogen = {n}",

                "Avoid additional nitrogen fertilizer."

            )


# ==========================================================
# Phosphorus Rules
# ==========================================================

    def check_phosphorus(self):

        p = self.sensor.phosphorus

        if p < 25:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["phosphorus"],

                "Phosphorus Deficiency",

                f"Phosphorus = {p}",

                "Apply DAP fertilizer."

            )

        elif p > 80:

            self.add(

                LOW,

                LEVEL_INFO,

                ICONS["phosphorus"],

                "High Phosphorus",

                f"Phosphorus = {p}",

                "Avoid additional phosphorus fertilizer."

            )


# ==========================================================
# Potassium Rules
# ==========================================================

    def check_potassium(self):

        k = self.sensor.potassium

        if k < 35:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["potassium"],

                "Potassium Deficiency",

                f"Potassium = {k}",

                "Apply MOP fertilizer."

            )

        elif k > 150:

            self.add(

                LOW,

                LEVEL_INFO,

                ICONS["potassium"],

                "High Potassium",

                f"Potassium = {k}",

                "Reduce potassium fertilizer."

            )


# ==========================================================
# pH Rules
# ==========================================================

    def check_ph(self):

        ph = self.sensor.ph

        if ph < 5.5:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["ph"],

                "Acidic Soil",

                f"Soil pH = {ph}",

                "Apply agricultural lime."

            )

        elif ph > 7.5:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["ph"],

                "Alkaline Soil",

                f"Soil pH = {ph}",

                "Apply gypsum or sulfur."

            )


# ==========================================================
# Run Sensor Checks
# ==========================================================

    def run_sensor_checks(self):

        self.check_soil_moisture()

        self.check_nitrogen()

        self.check_phosphorus()

        self.check_potassium()

        self.check_ph()
# ==========================================================
# Temperature Rules
# ==========================================================

    def check_temperature(self):

        temp = self.sensor.temperature

        if temp >= 40:

            self.add(

                CRITICAL,

                LEVEL_CRITICAL,

                ICONS["temperature"],

                "Extreme Heat",

                f"Temperature is {temp}°C.",

                "Increase irrigation immediately and avoid fertilizer application during peak heat."

            )

        elif temp >= 35:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["temperature"],

                "High Temperature",

                f"Temperature is {temp}°C.",

                "Monitor crops for heat stress and irrigate if needed."

            )

        elif temp <= 10:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["temperature"],

                "Low Temperature",

                f"Temperature is {temp}°C.",

                "Protect crops from cold stress."

            )


# ==========================================================
# Humidity Rules
# ==========================================================

    def check_humidity(self):

        humidity = self.sensor.humidity

        if humidity >= 90:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["humidity"],

                "Very High Humidity",

                f"Humidity is {humidity}%",

                "High fungal disease risk. Improve air circulation."

            )

        elif humidity >= 80:

            self.add(

                MEDIUM,

                LEVEL_WARNING,

                ICONS["humidity"],

                "High Humidity",

                f"Humidity is {humidity}%",

                "Monitor crops for fungal infections."

            )

        elif humidity <= 25:

            self.add(

                MEDIUM,

                LEVEL_WARNING,

                ICONS["humidity"],

                "Low Humidity",

                f"Humidity is {humidity}%",

                "Increase irrigation frequency if soil is dry."

            )


# ==========================================================
# Weather Rules
# ==========================================================

    def check_weather(self):

        if self.weather is None:
            return

        weather = self.weather

        condition = str(weather.get("condition", "")).lower()

        rainfall = float(weather.get("rainfall", 0))

        wind = float(weather.get("wind_speed", 0))

        # Rain Prediction

        if rainfall >= 20:

            self.add(

                HIGH,

                LEVEL_INFO,

                ICONS["weather"],

                "Heavy Rain Expected",

                "Heavy rainfall is expected.",

                "Delay irrigation and protect fertilizers from runoff."

            )

        elif rainfall > 0:

            self.add(

                MEDIUM,

                LEVEL_INFO,

                ICONS["weather"],

                "Rain Expected",

                "Rain is expected soon.",

                "Reduce irrigation today."

            )

        # Strong Wind

        if wind >= 35:

            self.add(

                HIGH,

                LEVEL_WARNING,

                ICONS["weather"],

                "Strong Wind Alert",

                f"Wind Speed: {wind} km/h",

                "Avoid pesticide spraying."

            )

        # Storm

        if "storm" in condition or "thunder" in condition:

            self.add(

                CRITICAL,

                LEVEL_CRITICAL,

                ICONS["weather"],

                "Thunderstorm Alert",

                "Severe weather approaching.",

                "Avoid field activities until weather improves."

            )


# ==========================================================
# Crop Recommendation Rules
# ==========================================================

    def check_crop(self):

        if self.crop is None:
            return

        crop_name = self.crop.get("recommended_crop", "Unknown")

        confidence = float(self.crop.get("confidence", 0))

        if confidence < 60:

            self.add(

                MEDIUM,

                LEVEL_WARNING,

                ICONS["crop"],

                "Low AI Confidence",

                f"Crop recommendation confidence is only {confidence:.1f}%",

                "Collect fresh sensor readings."

            )

        elif confidence >= 90:

            self.add(

                INFO,

                LEVEL_SUCCESS,

                ICONS["crop"],

                "Crop Recommendation Ready",

                f"Recommended Crop: {crop_name}",

                "Current farm conditions are highly suitable."

            )


# ==========================================================
# Fertilizer Recommendation Rules
# ==========================================================

    def check_fertilizer(self):

        if self.fertilizer is None:
            return

        fertilizer_name = self.fertilizer.get("recommended_fertilizer", "")

        if fertilizer_name:

            self.add(

                MEDIUM,

                LEVEL_INFO,

                ICONS["fertilizer"],

                "Fertilizer Recommendation",

                f"Recommended: {fertilizer_name}",

                "Apply the recommended fertilizer according to dosage."

            )


# ==========================================================
# Market Rules
# ==========================================================

    def check_market(self):

        if self.market is None:
            return

        trend = float(self.market.get("weekly_change", 0))

        crop = self.market.get("crop", "")

        mandi = self.market.get("best_market", "")

        if trend >= 10:

            self.add(

                MEDIUM,

                LEVEL_INFO,

                ICONS["market"],

                "Excellent Market Opportunity",

                f"{crop} price increased by {trend:.1f}% this week.",

                f"Consider selling at {mandi}."

            )

        elif trend <= -10:

            self.add(

                LOW,

                LEVEL_INFO,

                ICONS["market"],

                "Market Price Down",

                f"{crop} price dropped by {abs(trend):.1f}% this week.",

                "Waiting for price recovery may be beneficial."

            )


# ==========================================================
# AI Decision Rules
# ==========================================================

    def run_ai_rules(self):

        if self.weather is None:
            return

        rainfall = float(self.weather.get("rainfall", 0))

        moisture = self.sensor.soil_moisture

        # Intelligent Irrigation Advice

        if moisture < 30 and rainfall > 10:

            self.add(

                CRITICAL,

                LEVEL_INFO,

                "🤖",

                "Smart Irrigation Advice",

                "Soil moisture is low but rainfall is expected.",

                "Delay irrigation until rainfall is complete."

            )

        elif moisture < 30 and rainfall == 0:

            self.add(

                CRITICAL,

                LEVEL_CRITICAL,

                "🤖",

                "Immediate Irrigation Required",

                "Low soil moisture with no expected rainfall.",

                "Start irrigation immediately."

            )


# ==========================================================
# Run All Advanced Checks
# ==========================================================

    def run_advanced_checks(self):

        self.check_temperature()

        self.check_humidity()

        self.check_weather()

        self.check_crop()

        self.check_fertilizer()

        self.check_market()

        self.run_ai_rules()
# ==========================================================
# Remove Duplicate Alerts
# ==========================================================

    def remove_duplicates(self):

        unique = {}

        for alert in self.alerts:

            key = (
                alert.title,
                alert.level
            )

            if key not in unique:

                unique[key] = alert

            else:

                if alert.priority > unique[key].priority:

                    unique[key] = alert

        self.alerts = list(unique.values())


# ==========================================================
# Sort Alerts
# ==========================================================

    def sort_alerts(self):

        self.alerts.sort(

            key=lambda x: x.priority,

            reverse=True

        )


# ==========================================================
# Keep Only Top 3 Alerts
# ==========================================================

    def top_alerts(self):

        self.alerts = self.alerts[:3]


# ==========================================================
# Calculate Dashboard Status
# ==========================================================

    def dashboard_status(self):

        critical = 0

        warning = 0

        info = 0

        success = 0

        for alert in self.alerts:

            if alert.level == LEVEL_CRITICAL:

                critical += 1

            elif alert.level == LEVEL_WARNING:

                warning += 1

            elif alert.level == LEVEL_INFO:

                info += 1

            elif alert.level == LEVEL_SUCCESS:

                success += 1

        if critical > 0:

            status = "Critical"

        elif warning > 0:

            status = "Needs Attention"

        else:

            status = "Healthy"

        return {

            "status": status,

            "critical_alerts": critical,

            "warning_alerts": warning,

            "info_alerts": info,

            "healthy_parameters": success

        }


# ==========================================================
# Generate Alerts
# ==========================================================

    def generate(self):

        # ----------------------------
        # Sensor Based Alerts
        # ----------------------------

        self.run_sensor_checks()

        # ----------------------------
        # AI Based Alerts
        # ----------------------------

        self.run_advanced_checks()

        # ----------------------------
        # Remove Duplicate Alerts
        # ----------------------------

        self.remove_duplicates()

        # ----------------------------
        # Sort by Priority
        # ----------------------------

        self.sort_alerts()

        # ----------------------------
        # Keep Top 3
        # ----------------------------

        self.top_alerts()

        # ----------------------------
        # Dashboard Status
        # ----------------------------

        summary = self.dashboard_status()

        return {

            "status": summary["status"],

            "critical_alerts": summary["critical_alerts"],

            "warning_alerts": summary["warning_alerts"],

            "info_alerts": summary["info_alerts"],

            "healthy_parameters": summary["healthy_parameters"],

            "total_alerts": len(self.alerts),

            "alerts": [

                alert.to_dict()

                for alert in self.alerts

            ]

        }


# ==========================================================
# Public Function
# ==========================================================

def generate_alerts(

    sensor,

    weather=None,

    crop=None,

    fertilizer=None,

    market=None

):

    engine = AlertEngine(

        sensor=sensor,

        weather=weather,

        crop=crop,

        fertilizer=fertilizer,

        market=market

    )

    return engine.generate()