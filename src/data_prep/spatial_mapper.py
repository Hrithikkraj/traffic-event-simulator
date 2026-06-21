import pandas as pd
import h3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def add_h3_indices(df: pd.DataFrame, resolution: int = 8) -> pd.DataFrame:
    """Converts latitude and longitude into H3 hexagonal bins."""
    logging.info(f"Mapping coordinates to H3 hex bins at resolution {resolution}...")
    
    def get_hex(row):
        # Check for valid lat/lon before converting
        if pd.notna(row['latitude']) and pd.notna(row['longitude']):
            return h3.geo_to_h3(row['latitude'], row['longitude'], resolution)
        return None

    df['hex_id'] = df.apply(get_hex, axis=1)
    
    missing_coords = df['hex_id'].isna().sum()
    if missing_coords > 0:
        logging.warning(f"Failed to map {missing_coords} rows due to missing coordinates.")
        
    return df

if __name__ == "__main__":
    PROCESSED_DIR = Path("data/processed")
    
    for event_type in ['planned', 'unplanned']:
        file_path = PROCESSED_DIR / f"{event_type}_events_scored.csv"
        
        if file_path.exists():
            df = pd.read_csv(file_path)
            df_spatial = add_h3_indices(df, resolution=8)
            
            # Overwrite the file with the new spatial column
            df_spatial.to_csv(file_path, index=False)
            logging.info(f"Added spatial hex bins to {event_type} events.")
        else:
            logging.error(f"Could not find {file_path}. Run build_eis.py first.")