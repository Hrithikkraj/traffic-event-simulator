import pandas as pd
import numpy as np
import logging
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_spatial_reach(df: pd.DataFrame) -> pd.Series:
    """
    R_spatial: Multiplier based on physical footprint of the event.
    Heavy vehicles and multi-lane events get higher multipliers.
    """
    # Default multiplier is 1.0
    reach = pd.Series(1.0, index=df.index)
    
    # Vehicle type mapping (if available)
    if 'veh_type' in df.columns:
        heavy_vehs = ['heavy_vehicle', 'bmtc_bus', 'truck', 'tractor']
        reach = np.where(df['veh_type'].isin(heavy_vehs), 1.5, reach)
    
    # Cause mapping (e.g., a tree fall blocks more lanes than a broken down bike)
    if 'event_cause' in df.columns:
        wide_impact_causes = ['tree_fall', 'water_logging', 'protest', 'public_event']
        reach = np.where(df['event_cause'].isin(wide_impact_causes), 1.8, reach)
        
    return reach

def calculate_baseline_flow(df: pd.DataFrame) -> pd.Series:
    """
    F_base: Proxy for traffic volume based on time of day and corridor.
    """
    flow = pd.Series(1.0, index=df.index)
    
    # 1. Rush Hour Multiplier
    if 'hour_of_day' in df.columns:
        # Morning peak (8-11 AM) and Evening peak (5-8 PM)
        is_peak = df['hour_of_day'].isin([8, 9, 10, 17, 18, 19])
        # Night time (11 PM - 5 AM)
        is_night = df['hour_of_day'].isin([23, 0, 1, 2, 3, 4, 5])
        
        flow = np.where(is_peak, flow * 1.5, flow)
        flow = np.where(is_night, flow * 0.7, flow)
        
    # 2. Corridor Multiplier (Bengaluru's major arterials carry more baseline flow)
    if 'corridor' in df.columns:
        major_arterials = ['ORR East 1', 'ORR South', 'Tumkur Road', 'Hosur Road', 'Bellary Road']
        is_major = df['corridor'].isin(major_arterials)
        flow = np.where(is_major, flow * 1.3, flow)
        
    return flow

def calculate_closure_severity(df: pd.DataFrame) -> pd.Series:
    """
    S_closure: Multiplier for priority and actual road closures.
    """
    severity = pd.Series(1.0, index=df.index)
    
    if 'requires_road_closure' in df.columns:
        # If true, it severely bottlenecks flow
        severity = np.where(df['requires_road_closure'] == True, severity * 2.0, severity)
        
    if 'priority' in df.columns:
        severity = np.where(df['priority'] == 'High', severity * 1.3, severity)
        
    return severity

def build_event_impact_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combines components to calculate the final EIS.
    """
    logging.info("Calculating Event Impact Score (EIS) components...")
    
    # T_clear: We use the actual historical duration as the baseline truth for training
    # Fallback to 1 hour if duration is missing to avoid multiplying by NaN
    t_clear = df['clearance_duration_hrs'].fillna(1.0) 
    
    r_spatial = calculate_spatial_reach(df)
    f_base = calculate_baseline_flow(df)
    s_closure = calculate_closure_severity(df)
    
    # The Core Formula
    df['eis_raw'] = t_clear * r_spatial * f_base * s_closure
    
    # Normalize to 0-100 scale for business interpretability
    scaler = MinMaxScaler(feature_range=(0, 100))
    df['eis_normalized'] = scaler.fit_transform(df[['eis_raw']])
    
    # Create Operational Tiers based on percentiles
    # Bottom 50% = Low, 50-80% = Medium, 80-95% = High, Top 5% = Critical
    bins = [-1, 
            df['eis_normalized'].quantile(0.50), 
            df['eis_normalized'].quantile(0.80), 
            df['eis_normalized'].quantile(0.95), 
            101]
    labels = ['Low', 'Medium', 'High', 'Critical']
    
    df['eis_tier'] = pd.cut(df['eis_normalized'], bins=bins, labels=labels)
    
    logging.info("EIS calculation and tiering complete.")
    return df

if __name__ == "__main__":
    PROCESSED_DIR = Path("data/processed")
    
    for event_type in ['planned', 'unplanned']:
        file_path = PROCESSED_DIR / f"{event_type}_events_clean.csv"
        
        if file_path.exists():
            df = pd.read_csv(file_path)
            df_scored = build_event_impact_score(df)
            
            output_path = PROCESSED_DIR / f"{event_type}_events_scored.csv"
            df_scored.to_csv(output_path, index=False)
            logging.info(f"Saved scored dataset to {output_path}")
        else:
            logging.warning(f"File not found: {file_path}. Run clean_astram.py first.")