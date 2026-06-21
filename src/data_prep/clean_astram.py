import pandas as pd
import numpy as np
import logging
from pathlib import Path

# Set up logging to track data drops
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_and_clean_data(file_path: str) -> pd.DataFrame:
    """Loads raw ASTraM data, drops useless columns, and formats datetimes."""
    logging.info(f"Loading data from {file_path}")
    df = pd.read_csv(file_path)
    
    # 1. Drop practically empty or useless columns (identified in your EDA)
    cols_to_drop = ['direction', 'map_file', 'comment', 'meta_data', 'kgid']
    df = df.drop(columns=[col for col in cols_to_drop if col in df.columns], errors='ignore')
    
    # 2. Fix Text Casings (e.g., Debris vs debris)
    if 'event_cause' in df.columns:
        df['event_cause'] = df['event_cause'].str.lower().str.strip()
        
    # 3. Convert time columns to proper datetime objects (handling UTC timezone)
    time_cols = ['start_datetime', 'end_datetime', 'modified_datetime', 'closed_datetime', 'resolved_datetime']
    for col in time_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
    # 4. Extract Base Temporal Features from start_datetime
    df['hour_of_day'] = df['start_datetime'].dt.hour
    df['day_of_week'] = df['start_datetime'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    return df

def process_clearance_time(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates clearance time and drops illogical negative durations."""
    # Clearance time is the difference between closed and start
    df['clearance_duration_hrs'] = (df['closed_datetime'] - df['start_datetime']).dt.total_seconds() / 3600
    
    # Filter out the negative durations you found in EDA
    initial_len = len(df)
    df = df[(df['clearance_duration_hrs'] >= 0) | (df['clearance_duration_hrs'].isna())]
    dropped = initial_len - len(df)
    
    if dropped > 0:
        logging.warning(f"Dropped {dropped} rows with negative clearance durations.")
        
    # Cap infrastructure tickets (e.g., open > 30 days) so they don't skew ML models
    # We cap at 72 hours for "operational" incident modeling
    df['clearance_duration_hrs'] = df['clearance_duration_hrs'].clip(upper=72.0)
    
    return df

def split_pipelines(df: pd.DataFrame):
    """Splits the dataframe into Planned and Unplanned based on problem statement."""
    planned_df = df[df['event_type'] == 'planned'].copy()
    unplanned_df = df[df['event_type'] == 'unplanned'].copy()
    
    logging.info(f"Split completed: {len(planned_df)} Planned, {len(unplanned_df)} Unplanned events.")
    return planned_df, unplanned_df

if __name__ == "__main__":
    # Define paths (assuming you run this from the project root)
    RAW_DATA_PATH = "data/raw/astram_data.csv"
    PROCESSED_DIR = Path("data/processed")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run the pipeline
    df_cleaned = load_and_clean_data(RAW_DATA_PATH)
    df_processed = process_clearance_time(df_cleaned)
    df_planned, df_unplanned = split_pipelines(df_processed)
    
    # Save the foundational datasets
    df_planned.to_csv(PROCESSED_DIR / "planned_events_clean.csv", index=False)
    df_unplanned.to_csv(PROCESSED_DIR / "unplanned_events_clean.csv", index=False)
    logging.info("Foundation data successfully saved to data/processed/")