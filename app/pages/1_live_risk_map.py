import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path

st.set_page_config(page_title="Live Risk Map", page_icon="🗺️", layout="wide")

st.title("🗺️ Spatiotemporal Hotspot Risk Map")
st.markdown("Visualize the historical and forecasted density of high-impact events across Bengaluru using Uber's H3 Hexagonal Grid.")

@st.cache_data
def load_spatial_data():
    data_path = Path("data/processed/unplanned_events_scored.csv")
    if data_path.exists():
        df = pd.read_csv(data_path)
        # Drop rows without H3 hex mapping
        df = df.dropna(subset=['hex_id'])
        return df
    return pd.DataFrame()

df = load_spatial_data()

if not df.empty:
    # --- Sidebar Controls ---
    st.sidebar.header("Map Filters")
    selected_hour = st.sidebar.slider("Select Time of Day", min_value=0, max_value=23, value=14, step=1)
    
    # Filter data by the selected hour
    filtered_df = df[df['hour_of_day'] == selected_hour]
    
    if not filtered_df.empty:
        # Aggregate data by Hexagon for Pydeck
        hex_agg = filtered_df.groupby('hex_id').agg(
            incident_count=('hex_id', 'count'),
            avg_eis=('eis_normalized', 'mean')
        ).reset_index()
        
        # --- Pydeck 3D Map ---
        # Elevation = Number of incidents
        # Color = Average Event Impact Score (Red = Critical, Green = Low)
        
        layer = pdk.Layer(
            "H3HexagonLayer",
            hex_agg,
            pickable=True,
            stroked=True,
            filled=True,
            extruded=True,
            get_hexagon="hex_id",
            get_fill_color="[avg_eis * 2.5, 255 - (avg_eis * 2.5), 0, 180]", # Dynamic Green to Red
            get_elevation="incident_count",
            elevation_scale=50,
        )

        # Set the viewport over Bengaluru
        view_state = pdk.ViewState(
            latitude=12.9716, 
            longitude=77.5946, 
            zoom=10.5, 
            pitch=45, # Tilted to show 3D elevation
            bearing=0
        )

        # Render the map
        r = pdk.Deck(
            layers=[layer], 
            initial_view_state=view_state, 
            tooltip={"text": "Hex ID: {hex_id}\nIncidents: {incident_count}\nAvg Impact Score: {avg_eis}"}
        )
        
        st.pydeck_chart(r)
        
        # Breakdown metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Active Hotspots", len(hex_agg))
        col2.metric("Total Incidents", hex_agg['incident_count'].sum())
        col3.metric("Highest Regional Impact Score", f"{hex_agg['avg_eis'].max():.1f}/100")
        
    else:
        st.info("No recorded incidents for the selected hour.")
else:
    st.error("Data missing. Please ensure 'unplanned_events_scored.csv' exists.")