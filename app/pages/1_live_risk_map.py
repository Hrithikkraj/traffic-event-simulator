import streamlit as st
import pandas as pd
import pydeck as pdk
import h3
from pathlib import Path

st.set_page_config(page_title="Live Risk Map", page_icon="🗺️", layout="wide")

# --- PASTE YOUR MAPMYINDIA STATIC KEY HERE ---
MAPMYINDIA_API_KEY = "qjcehglokmufbwcnxomavzejpkgmhleqeitu"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "astram_data.csv"

st.title("🗺️ Spatiotemporal Hotspot Risk Map")
st.markdown("""
This screen shows where Bengaluru has historically seen unplanned traffic disruptions at a selected hour of the day.
Each raised hexagon represents a small area of the city. Taller hexagons mean more incidents were recorded there, and warmer colors mean the incidents are likely to have a stronger traffic impact.

Use this as a quick answer to: **Where should traffic teams pay attention at this time of day?**
""")

# --- DYNAMIC DATA EXTRACTION & SPATIAL MAPPING ---
@st.cache_data
def load_spatial_data():
    """Reads raw data, maps coords to H3 Hexagons, and estimates impact dynamically."""
    data_path = RAW_DATA_PATH
    if not data_path.exists():
        return pd.DataFrame()
        
    df = pd.read_csv(data_path)
    df = df[df['event_type'] == 'unplanned'].copy()
    
    # Time extraction
    df['start_datetime'] = pd.to_datetime(
        df['start_datetime'],
        errors='coerce',
        format='mixed',
        utc=True,
    ).dt.tz_convert('Asia/Kolkata')
    df['hour_of_day'] = df['start_datetime'].dt.hour
    df = df.dropna(subset=['hour_of_day'])
    df['hour_of_day'] = df['hour_of_day'].astype(int)
    
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
    st.sidebar.markdown("""
    Choose an hour to see which parts of the city usually become risky around that time.
    The app uses Bengaluru local time.
    """)
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
            tooltip={"text": "Historical incidents in this area: {incident_count}\nAverage traffic impact score: {avg_eis}"}
        )

        st.subheader(f"Risk hotspots around {selected_hour:02d}:00")
        st.markdown("""
        Look for the tallest columns first: those areas have had the most repeated incidents at this hour.
        Among columns of similar height, the warmer color points to the area where an incident is expected to hurt traffic more.
        """)
        
        st.pydeck_chart(r)
        
        # Metrics below the map
        col1, col2, col3 = st.columns(3)
        col1.metric("Risk Areas Found", len(hex_agg), help="Number of city zones with at least one recorded incident at the selected hour.")
        col2.metric("Incidents at This Hour", int(hex_agg['incident_count'].sum()), help="Total historical unplanned incidents recorded during this hour.")
        col3.metric("Highest Impact Score", f"{hex_agg['avg_eis'].max():.1f}/100", help="Higher scores suggest incidents that can slow traffic more severely.")

        st.info(
            "How to read this map: a tall column means repeated trouble in that area. "
            "A high impact score means an incident there is more likely to cause serious congestion, "
            "so it may deserve earlier monitoring or faster response."
        )
        
    else:
        st.info(f"No recorded incidents were found around {selected_hour:02d}:00 in the available data.")
else:
    st.error("Data missing. Please ensure 'data/raw/astram_data.csv' exists.")
