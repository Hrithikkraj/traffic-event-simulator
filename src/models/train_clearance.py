import pandas as pd
import lightgbm as lgb
import logging
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
import joblib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_clearance_model(data_path: Path, model_dir: Path):
    logging.info("Loading spatially mapped unplanned events...")
    df = pd.read_csv(data_path)
    
    # Drop rows where target is missing
    df = df.dropna(subset=['clearance_duration_hrs'])
    
    # Sort chronologically for a strict temporal split
    df['start_datetime'] = pd.to_datetime(df['start_datetime'])
    df = df.sort_values('start_datetime').reset_index(drop=True)
    
    # Define features and target
    target = 'clearance_duration_hrs'
    features = [
        'hour_of_day', 'day_of_week', 'is_weekend', 
        'event_cause', 'veh_type', 'corridor', 'hex_id', 'priority'
    ]
    
    # Convert string columns to categorical type for LightGBM
    cat_cols = ['event_cause', 'veh_type', 'corridor', 'hex_id', 'priority']
    for col in cat_cols:
        df[col] = df[col].astype('category')
        
    # Temporal Split: First 80% for training, last 20% for testing (no future leakage)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    X_train, y_train = train_df[features], train_df[target]
    X_test, y_test = test_df[features], test_df[target]
    
    logging.info(f"Training on {len(X_train)} events, testing on {len(X_test)} events.")
    
    # Initialize and train LightGBM Regressor
    model = lgb.LGBMRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=7,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=20)]
    )
    
    # Evaluate
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    
    logging.info(f"Model Performance -> MAE: {mae:.2f} hrs | RMSE: {rmse:.2f} hrs")
    
    # Save the model
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "lgb_clearance_model.pkl"
    joblib.dump(model, model_path)
    logging.info(f"Model saved to {model_path}")

if __name__ == "__main__":
    DATA_PATH = Path("data/processed/unplanned_events_scored.csv")
    MODEL_DIR = Path("models_saved")
    
    if DATA_PATH.exists():
        train_clearance_model(DATA_PATH, MODEL_DIR)
    else:
        logging.error("Data missing. Run pipeline steps 1-4 first.")