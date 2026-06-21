import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_playbook(closed_events_df: pd.DataFrame, playbook_path: Path):
    """
    Takes newly closed events, compares predictions vs. reality, 
    and updates the operational Playbook.
    """
    logging.info(f"Processing {len(closed_events_df)} newly closed events for the Learning Loop...")
    
    # Calculate Prediction Error
    closed_events_df['error_hrs'] = closed_events_df['actual_clearance_hrs'] - closed_events_df['predicted_clearance_hrs']
    closed_events_df['absolute_error_hrs'] = closed_events_df['error_hrs'].abs()
    
    # Load or initialize the Playbook
    if playbook_path.exists():
        playbook = pd.read_csv(playbook_path)
    else:
        # Initialize a new playbook
        playbook = pd.DataFrame(columns=[
            'event_cause', 'hex_id', 'historical_avg_hrs', 'model_bias_hrs', 'total_events_logged'
        ])
        
    # Aggregate new learnings by Cause and Location (hex_id)
    new_learnings = closed_events_df.groupby(['event_cause', 'hex_id']).agg(
        new_actual_avg=('actual_clearance_hrs', 'mean'),
        new_bias_avg=('error_hrs', 'mean'),
        event_count=('id', 'count')
    ).reset_index()
    
    # Merge and update existing playbook
    if not playbook.empty:
        merged = pd.merge(playbook, new_learnings, on=['event_cause', 'hex_id'], how='outer').fillna(0)
        
        # Weighted average update for historical times
        merged['historical_avg_hrs'] = (
            (merged['historical_avg_hrs'] * merged['total_events_logged']) + 
            (merged['new_actual_avg'] * merged['event_count'])
        ) / (merged['total_events_logged'] + merged['event_count'])
        
        # Weighted average update for model bias (Are we consistently underpredicting here?)
        merged['model_bias_hrs'] = (
            (merged['model_bias_hrs'] * merged['total_events_logged']) + 
            (merged['new_bias_avg'] * merged['event_count'])
        ) / (merged['total_events_logged'] + merged['event_count'])
        
        merged['total_events_logged'] += merged['event_count']
        
        # Clean up columns
        playbook = merged[['event_cause', 'hex_id', 'historical_avg_hrs', 'model_bias_hrs', 'total_events_logged']]
    else:
        # First time writing to playbook
        playbook = new_learnings.rename(columns={
            'new_actual_avg': 'historical_avg_hrs',
            'new_bias_avg': 'model_bias_hrs',
            'event_count': 'total_events_logged'
        })
        
    # Flag high-drift areas for model retraining
    drift_threshold = 1.0 # 1 hour of consistent error
    retrain_flags = playbook[playbook['model_bias_hrs'].abs() > drift_threshold]
    if not retrain_flags.empty:
        logging.warning(f"🚨 ALERT: High model drift detected in {len(retrain_flags)} zones. Retraining recommended.")
        
    # Save updated playbook
    playbook.to_csv(playbook_path, index=False)
    logging.info("Playbook successfully updated.")
    
    return playbook

# Quick test if run directly
if __name__ == "__main__":
    PLAYBOOK_PATH = Path("data/processed/cause_location_playbook.csv")
    PLAYBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Mock data simulating events that just closed today
    mock_closed_events = pd.DataFrame({
        'id': ['E1', 'E2', 'E3'],
        'event_cause': ['vehicle_breakdown', 'tree_fall', 'vehicle_breakdown'],
        'hex_id': ['8861892aaaaa03f', '8861892bbbbb03f', '8861892aaaaa03f'],
        'predicted_clearance_hrs': [1.5, 3.0, 1.2],
        'actual_clearance_hrs': [2.5, 3.1, 2.0] # Notice breakdowns took longer than predicted
    })
    
    updated_playbook = update_playbook(mock_closed_events, PLAYBOOK_PATH)
    print("\n--- Updated Operational Playbook ---")
    print(updated_playbook)
    
    