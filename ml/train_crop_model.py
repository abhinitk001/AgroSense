import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# ==========================================================
# Load Dataset
# ==========================================================

df = pd.read_csv("datasets/crop_recommendation.csv")

print("Dataset Loaded Successfully")
print(df.head())
print("\nColumns:")
print(df.columns.tolist())
# ==========================================================
# Encode Categorical Columns
# ==========================================================

encoders = {}

categorical_columns = [
    "Soil_Type",
    "Season",
    "Irrigation_Type",
]

for col in categorical_columns:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    encoders[col] = le

# Encode Target Column
crop_encoder = LabelEncoder()
df["Recommended_Crop"] = crop_encoder.fit_transform(df["Recommended_Crop"])

encoders["Recommended_Crop"] = crop_encoder

# ==========================================================
# Features and Target
# ==========================================================
X = df[
    [
        "N",
        "P",
        "K",
        "Soil_pH",
        "Soil_Moisture",
        "Soil_Type",
        "Temperature",
        "Humidity",
        "Rainfall",
        "Season",
        "Irrigation_Type",
    ]
]

y = df["Recommended_Crop"]

# ==========================================================
# Train Test Split
# ==========================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y,
)

# ==========================================================
# Train Random Forest
# ==========================================================

model = RandomForestClassifier(
    n_estimators=300,
    random_state=42,
    max_depth=18,
    n_jobs=-1,
)

model.fit(X_train, y_train)

# ==========================================================
# Evaluate
# ==========================================================

pred = model.predict(X_test)

accuracy = accuracy_score(y_test, pred)

print("\n==============================")
print("Model Accuracy")
print("==============================")

print(f"Accuracy : {accuracy*100:.2f}%")

print("\nClassification Report\n")

print(
    classification_report(
        y_test,
        pred,
        target_names=crop_encoder.classes_
    )
)

# ==========================================================
# Save Model
# ==========================================================

joblib.dump(model,"ml_models/crop_model.pkl")

joblib.dump(encoders,"ml_models/crop_label_encoders.pkl")

print("\n==============================")
print("Model Saved Successfully")
print("==============================")

print("crop_model.pkl")

print("label_encoders.pkl")