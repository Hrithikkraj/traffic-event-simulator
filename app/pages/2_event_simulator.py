import streamlit as st
import pandas as pd
import numpy as np
import random
import pydeck as pdk
import sys
from pathlib import Path

# Connect our ML Pipeline tools
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "astram_data.csv"
sys.path.append(str(PROJECT_ROOT))
from src.optimization.resource_allocator import optimize_deployment
from src.optimization.route_diversion import get_diversion_route

st.set_page_config(page_title="Event Simulator", page_icon="🚨", layout="wide")

# --- PASTE YOUR MAPMYINDIA STATIC KEY HERE ---
MAPMYINDIA_API_KEY = "qjcehglokmufbwcnxomavzejpkgmhleqeitu"

st.title("🚨 Live Event Injection & Deployment Simulator")
st.markdown("""
This screen lets you test a **what-if traffic emergency** before it happens.
Choose an incident type and a road corridor from the sidebar, then the app estimates how serious the disruption could be and suggests how limited traffic resources should be assigned.

Use this as a quick answer to: **If this event happens now, where should officers and barricades go first?**
""")

# --- DYNAMIC DATA EXTRACTION ---
@st.cache_data
def load_dynamic_options():
    """Reads the raw ASTraM dataset to extract all unique causes and corridor coordinates."""
    # Read the dataset you uploaded
    df = pd.read_csv(RAW_DATA_PATH)
    
    # Clean text
    df['event_cause'] = df['event_cause'].str.lower().str.strip()
    
    # 1. Get all unique causes
    causes = df['event_cause'].dropna().unique().tolist()
    
    # 2. Get all unique corridors and their approximate center points
    # We group by corridor and take the median lat/lon to find the center of that road
    corridor_data = df.groupby('corridor').agg({
        'latitude': 'median',
        'longitude': 'median'
    }).reset_index()
    
    # Drop any corridors that have missing coordinates
    corridor_data = corridor_data.dropna(subset=['corridor', 'latitude', 'longitude'])
    
    return sorted(causes), corridor_data

# Load the dynamic data
all_causes, corridor_df = load_dynamic_options()
all_corridors = sorted(corridor_df['corridor'].tolist())

# --- BACKGROUND CITY STATE ---
@st.cache_data
def get_background_events():
    return pd.DataFrame({
        'id': ['B1', 'B2', 'B3', 'B4', 'B5'],
        'event_cause': ['vehicle_breakdown', 'accident', 'water_logging', 'tree_fall', 'vehicle_breakdown'],
        'latitude': [12.9716, 12.9218, 13.0400, 12.9556, 12.9350],
        'longitude': [77.5946, 77.6451, 77.5180, 77.5857, 77.6150],
        'eis_normalized': [45.0, 75.0, 20.0, 60.0, 30.0],
        'eis_tier': ['Medium', 'High', 'Low', 'Medium', 'Low'],
        'is_simulated': [False] * 5
    })

city_state_df = get_background_events()

# --- SIMULATOR UI ---
with st.sidebar.form("simulator_form"):
    st.header("Inject New Event")
    st.markdown("""
    Pick the kind of incident and where it happens.
    The simulator will add it to a small live city snapshot and recalculate the response plan.
    """)
    
    # Dynamic Dropdowns populated from your CSV
    sim_cause = st.selectbox("Incident Type", all_causes)
    sim_location = st.selectbox("Road or Corridor", all_corridors)
    
    submitted = st.form_submit_button("Simulate Impact & Deploy")

if submitted:
    # Get the dynamic coordinates for the chosen corridor
    selected_corridor_row = corridor_df[corridor_df['corridor'] == sim_location].iloc[0]
    lat = selected_corridor_row['latitude']
    lon = selected_corridor_row['longitude']
    
    # Dynamically assign severity based on typical impact (Heuristics for the simulator)
    critical_causes = ['protest', 'public_event', 'vip_movement', 'procession', 'tree_fall', 'water_logging']
    high_causes = ['accident', 'heavy_vehicle', 'bmtc_bus', 'fire']
    
    if any(c in sim_cause for c in critical_causes):
        sim_tier = 'Critical'
        sim_eis = random.uniform(85.0, 99.0)
    elif any(c in sim_cause for c in high_causes):
        sim_tier = 'High'
        sim_eis = random.uniform(70.0, 84.0)
    else:
        sim_tier = 'Medium'
        sim_eis = random.uniform(40.0, 69.0)
    
    new_event = pd.DataFrame([{
        'id': 'SIM_1', 'event_cause': sim_cause, 'latitude': lat, 'longitude': lon,
        'eis_normalized': sim_eis, 'eis_tier': sim_tier, 'is_simulated': True
    }])
    
    current_events_df = pd.concat([city_state_df, new_event], ignore_index=True)
    st.success(f"Event added at **{sim_location}**. Estimated traffic impact score: **{sim_eis:.1f}/100 ({sim_tier})**")
    st.markdown("""
    The impact score is a simple severity estimate. A higher score means the event is more likely to create serious congestion,
    need faster police attention, or require more physical control such as barricades.
    """)
    
    # Run the ILP Optimizer
    optimized_df = optimize_deployment(current_events_df, total_officers=20, total_barricades=30)
    
    # Calculate a Mappls Diversion Route (Routing traffic AWAY from the injected event towards a safe hub)
    SAFE_HUB_LAT, SAFE_HUB_LON = 12.9781, 77.5695 
    route_coords, duration, distance = get_diversion_route(lat, lon, SAFE_HUB_LAT, SAFE_HUB_LON)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("City-Wide Optimization Plan")
        st.markdown("""
        This table compares the simulated incident with other active city events and shows how available officers and barricades should be distributed.
        The highlighted row is the new incident you just injected. Higher-impact events receive more resources first.
        """)
        
        def highlight_sim(row):
            is_sim = optimized_df.loc[row.name, 'is_simulated']
            return ['background-color: #ff4b4b; color: white'] * len(row) if is_sim else [''] * len(row)
            
        display_cols = ['event_cause', 'eis_tier', 'eis_normalized', 'assigned_officers', 'assigned_barricades']
        st.dataframe(optimized_df[display_cols].style.apply(highlight_sim, axis=1), use_container_width=True)
        
        if route_coords:
            st.info(
                f"Suggested diversion route: about {distance:.1f} km, "
                f"estimated {duration:.1f} minutes to bypass the affected area."
            )
        else:
            st.warning("No diversion route was returned for this location. The deployment plan is still shown above.")

    with col2:
        st.subheader("Live Map")
        st.markdown("""
        The red point is the simulated incident. Blue points are the background city events already being managed.
        If a diversion is available, the yellow line shows a possible route away from the incident area.
        """)
        layers_to_render = []
        
        # 1. Mappls Base Map
        MAPPLES_TILE_URL = f"https://apis.mappls.com/advancedmaps/v1/{MAPMYINDIA_API_KEY}/retina_map/{{z}}/{{x}}/{{y}}.png"
        layers_to_render.append(pdk.Layer(
            "TileLayer", data=MAPPLES_TILE_URL, min_zoom=0, max_zoom=19
        ))
        
        # 2. Diversion Path Layer (If Mappls found a route)
        if route_coords:
            route_data = pd.DataFrame([{"path": route_coords}])
            layers_to_render.append(pdk.Layer(
                "PathLayer",
                route_data,
                get_path="path",
                get_color=[255, 200, 0, 200], # Bright Yellow Diversion Line
                width_scale=20,
                width_min_pixels=5
            ))
        
        # 3. Incident Dots
        optimized_df['map_color'] = optimized_df['is_simulated'].apply(lambda x: [200, 30, 0, 160] if x else [0, 150, 200, 160])
        layers_to_render.append(pdk.Layer(
            "ScatterplotLayer",
            optimized_df,
            get_position='[longitude, latitude]',
            get_fill_color="map_color", 
            get_radius="eis_normalized * 10",
            pickable=True
        ))
        
        view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=11.5)
        st.pydeck_chart(pdk.Deck(
            map_style=None, 
            layers=layers_to_render, 
            initial_view_state=view_state, 
            tooltip={"text": "Incident: {event_cause}\nAssigned officers: {assigned_officers}\nAssigned barricades: {assigned_barricades}"}
        ))
else:
    st.info(
        "Start by choosing an incident type and road corridor in the sidebar. "
        "After simulation, this page will show the expected impact, the resource allocation plan, and the map view."
    )
