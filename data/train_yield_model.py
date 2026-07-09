import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb
import joblib
import json

# --- Load Data ---
df = pd.read_csv("data/yield_training_data.csv")
print(f"Loaded {len(df)} samples")

# --- Encode Categorical Features ---
encoders = {}
categorical_cols = ["crop_type", "region", "soil_type"]

for col in categorical_cols:
    le = LabelEncoder()
    df[f"{col}_encoded"] = le.fit_transform(df[col])
    encoders[col] = le

# --- Feature Set ---
feature_cols = [
    "crop_type_encoded",
    "farm_size_hectares",
    "region_encoded",
    "soil_type_encoded",
    "rainfall_mm",
    "temperature_celsius",
    "fertilizer_used"
]

X = df[feature_cols]
y = df["yield_kg"]

# --- Train/Test Split ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- Train XGBoost Model ---
model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42
)

model.fit(X_train, y_train)

# --- Evaluate ---
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"\n--- Model Performance ---")
print(f"MAE: {mae:.2f} kg")
print(f"R² Score: {r2:.4f}")

# --- Feature Importance ---
importance = dict(zip(feature_cols, model.feature_importances_))
print(f"\n--- Feature Importance ---")
for feat, imp in sorted(importance.items(), key=lambda x: -x[1]):
    print(f"{feat}: {imp:.4f}")

# --- Save Model + Encoders ---
joblib.dump(model, "app/models/ml/yield_model.pkl")
joblib.dump(encoders, "app/models/ml/yield_encoders.pkl")

# Save category lists so the API knows what valid inputs look like
categories = {col: list(encoders[col].classes_) for col in categorical_cols}
with open("app/models/ml/yield_categories.json", "w") as f:
    json.dump(categories, f, indent=2)

print(f"\nModel saved to app/models/ml/yield_model.pkl")
print(f"Encoders saved to app/models/ml/yield_encoders.pkl")