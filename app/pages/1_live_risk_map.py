import streamlit as st
import pandas as pd
import pydeck as pdk
import h3
from pathlib import Path

st.set_page_config(page_title="Live Risk Map", page_icon="🗺️", layout="wide")

# --- PASTE YOUR MAPMYINDIA STATIC KEY HERE ---
MAPMYINDIA_API_KEY = "qjcehglokmufbwcnxomavzejpkgmhleqeitu"

st.title("🗺️ Spatiotemporal Hotspot Risk Map")
st.markdown("Visualize the historical and forecasted density of high-impact events across Bengaluru using Uber's H3 Hexagonal Grid mapped on Mappls.")

# --- DYNAMIC DATA EXTRACTION & SPATIAL MAPPING ---
@st.cache_data
def load_spatial_data():
    """Reads raw data, maps coords to H3 Hexagons, and estimates impact dynamically."""
    data_path = Path("data/raw/astram_data.csv")
    if not data_path.exists():
        return pd.DataFrame()
        
    df = pd.read_csv(data_path)
    df = df[df['event_type'] == 'unplanned'].copy()
    
    # Time extraction
    df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce')
    df['hour_of_day'] = df['start_datetime'].dt.hour
    
    # Drop rows without coordinates
    df = df.dropna(subset=['latitude', 'longitude'])
    
    # Map Coordinates to H3 Hexagons (Resolution 8)
    def get_hex(row):
        try:
            return h3.geo_to_h3(row['latitude'], row['longitude'], 8)
        except:
            return None
            
    df['hex_id'] = df.apply(get_hex, axis=1)
    df = df.dropna(subset=['hex_id'])
    
    # Dynamically assign a proxy Event Impact Score based on the cause
    def assign_mock_eis(cause):
        c = str(cause).lower()
        if any(x in c for x in ['protest', 'tree_fall', 'water_logging']): return 85.0
        elif any(x in c for x in ['accident', 'heavy_vehicle', 'fire']): return 70.0
        else: return 45.0
        
    df['eis_normalized'] = df['event_cause'].apply(assign_mock_eis)
    
    return df

df = load_spatial_data()

if not df.empty:
    st.sidebar.header("Map Filters")
    selected_hour = st.sidebar.slider("Select Time of Day", min_value=0, max_value=23, value=2, step=1)
    
    filtered_df = df[df['hour_of_day'] == selected_hour]
    
    if not filtered_df.empty:
        # Aggregate the data by Hexagon for Pydeck
        hex_agg = filtered_df.groupby('hex_id').agg(
            incident_count=('hex_id', 'count'),
            avg_eis=('eis_normalized', 'mean')
        ).reset_index()
        
        # 1. The 3D Hexagon Data Layer
        data_layer = pdk.Layer(
            "H3HexagonLayer",
            hex_agg,
            pickable=True,
            stroked=True,
            filled=True,
            extruded=True,
            get_hexagon="hex_id",
            get_fill_color="[avg_eis * 2.5, 255 - (avg_eis * 2.5), 0, 180]", 
            get_elevation="incident_count",
            elevation_scale=50,
        )

        # 2. The Mappls Base Map Layer (NO get_image bug here)
        MAPPLES_TILE_URL = f"https://apis.mappls.com/advancedmaps/v1/{MAPMYINDIA_API_KEY}/retina_map/{{z}}/{{x}}/{{y}}.png"
        tile_layer = pdk.Layer(
            "TileLayer",
            data=MAPPLES_TILE_URL,
            min_zoom=0, max_zoom=19
        )

        view_state = pdk.ViewState(latitude=13.0400, longitude=77.5180, zoom=10.5, pitch=45, bearing=0)

        # 3. Render Combined Map
        r = pdk.Deck(
            map_style=None, 
            layers=[tile_layer, data_layer], 
            initial_view_state=view_state, 
            tooltip={"text": "Hex ID: {hex_id}\nTotal Historical Incidents at {hour_of_day}:00: {incident_count}\nAvg Impact Score: {avg_eis}"}
        )
        
        st.pydeck_chart(r)
        
        # Metrics below the map
        col1, col2, col3 = st.columns(3)
        col1.metric("Active City Hotspots", len(hex_agg))
        col2.metric("Total Incidents in this Hour", hex_agg['incident_count'].sum())
        col3.metric("Highest Regional Impact Score", f"{hex_agg['avg_eis'].max():.1f}/100")
        
    else:
        st.info("No recorded incidents for the selected hour.")
else:
    st.error("Data missing. Please ensure 'data/raw/astram_data.csv' exists.")