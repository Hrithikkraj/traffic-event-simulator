import streamlit as st
import pandas as pd
import random
import pydeck as pdk
import sys
from pathlib import Path

# Add project root to sys.path so we can import our custom module
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.optimization.resource_allocator import optimize_deployment

st.set_page_config(page_title="Event Simulator", page_icon="🚨", layout="wide")

st.title("🚨 Live Event Injection & Deployment Simulator")
st.markdown("Inject a planned or unplanned event into the network. Watch the system dynamically calculate the Impact Score (EIS) and re-route finite police resources.")

# --- 1. Generate an "Active City State" (Background noise) ---
# In a real app, this queries the live database. Here, we mock 5 active background events.
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

# --- 2. The Input Form ---
with st.sidebar.form("simulator_form"):
    st.header("Inject New Event")
    sim_cause = st.selectbox("Event Cause", ["public_event / VIP", "protest", "heavy_vehicle_breakdown", "construction"])
    sim_location = st.selectbox("Corridor/Location", ["MG Road (Central)", "Tumkur Road (West)", "Hosur Road (South)"])
    
    # Map locations to approximate coordinates
    loc_coords = {
        "MG Road (Central)": (12.9750, 77.6000),
        "Tumkur Road (West)": (13.0450, 77.5200),
        "Hosur Road (South)": (12.9250, 77.6200)
    }
    lat, lon = loc_coords[sim_location]
    
    submitted = st.form_submit_button("Simulate Impact & Deploy")

# --- 3. Run the Simulation ---
if submitted:
    # Estimate EIS based on user inputs (Simulating the ML output)
    sim_tier = 'Critical' if sim_cause in ["public_event / VIP", "protest"] else 'High'
    sim_eis = random.uniform(85.0, 99.0) if sim_tier == 'Critical' else random.uniform(70.0, 84.0)
    
    new_event = pd.DataFrame([{
        'id': 'SIM_1',
        'event_cause': sim_cause,
        'latitude': lat,
        'longitude': lon,
        'eis_normalized': sim_eis,
        'eis_tier': sim_tier,
        'is_simulated': True
    }])
    
    # Combine background noise with the new simulated event
    current_events_df = pd.concat([city_state_df, new_event], ignore_index=True)
    
    st.success(f"**Event Injected!** Calculated Event Impact Score: **{sim_eis:.1f} ({sim_tier})**")
    
    # --- 4. RUN THE OPTIMIZER ---
    # We strictly limit the city to 20 officers. 
    # The solver will be forced to choose who gets them.
    optimized_df = optimize_deployment(current_events_df, total_officers=20, total_barricades=30)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("City-Wide Optimization Plan")
        st.markdown("*Note: With only 20 officers available, the ILP solver prioritizes the highest EIS events.*")
        
        # Highlight the simulated row in the table
        def highlight_sim(row):
            # Look up the 'is_simulated' flag from the original full dataframe using the row index
            is_sim = optimized_df.loc[row.name, 'is_simulated']
            return ['background-color: #ff4b4b; color: white'] * len(row) if is_sim else [''] * len(row)
            
        display_cols = ['event_cause', 'eis_tier', 'eis_normalized', 'assigned_officers', 'assigned_barricades']
        st.dataframe(optimized_df[display_cols].style.apply(highlight_sim, axis=1), use_container_width=True)

    with col2:
        st.subheader("Live Map")
        
        # 1. Calculate the color inside Pandas based on the simulation flag
        optimized_df['map_color'] = optimized_df['is_simulated'].apply(
            lambda x: [200, 30, 0, 160] if x else [0, 150, 200, 160]
        )
        
        # 2. Pass the new 'map_color' column to Pydeck (and use get_fill_color)
        layer = pdk.Layer(
            "ScatterplotLayer",
            optimized_df,
            get_position='[longitude, latitude]',
            get_fill_color="map_color", 
            get_radius="eis_normalized * 10",
            pickable=True
        )
        
        view_state = pdk.ViewState(latitude=12.9716, longitude=77.5946, zoom=10.5)
        st.pydeck_chart(pdk.Deck(
            layers=[layer], 
            initial_view_state=view_state, 
            tooltip={"text": "{event_cause}\nOfficers: {assigned_officers}"}
        ))

else:
    st.info("Use the sidebar to inject a new event into the city network.")