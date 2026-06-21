import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="ASTraM | Event-Driven Optimizer",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DYNAMIC DATA EXTRACTION ---
@st.cache_data
def load_summary_data():
    """Reads raw data dynamically so the dashboard works out-of-the-box."""
    data_path = Path("data/raw/astram_data.csv")
    if data_path.exists():
        df = pd.read_csv(data_path)
        
        # Filter to unplanned operational events
        df = df[df['event_type'] == 'unplanned'].copy()
        
        # Dynamically extract the hour of the day
        df['start_datetime'] = pd.to_datetime(df['start_datetime'], errors='coerce')
        df['hour_of_day'] = df['start_datetime'].dt.hour
        
        # Clean up vehicle types for the chart
        df['veh_type'] = df['veh_type'].fillna('Unknown').str.replace('_', ' ').str.title()
        
        return df
    return pd.DataFrame()

# --- Main UI ---
st.title("🚦 ASTraM: Event-Driven Congestion Optimizer")
st.markdown("""
**A proactive decision-support system for Bengaluru Traffic Police.** Most systems attempt to predict traffic flow. We predict **Event Impact** and prescribe the optimal deployment of finite police resources.
""")

st.divider()

df = load_summary_data()

if not df.empty:
    st.subheader("The Insight that Changes the Strategy")
    st.markdown("""
    When optimizing for unplanned congestion, traditional rush-hour logic fails. 
    Our analysis reveals that unplanned traffic events **peak at 2:00 AM**, completely inverted from passenger rush hours. 
    *Why?* Heavy freight and truck movement is restricted during the day, leading to massive nocturnal breakdown spikes on key arterials like Tumkur Road.
    """)
    
    # Group by hour and vehicle type
    hourly_counts = df.groupby(['hour_of_day', 'veh_type']).size().reset_index(name='incident_count')
    
    # Plotly Bar Chart
    fig = px.bar(
        hourly_counts, 
        x='hour_of_day', 
        y='incident_count', 
        color='veh_type',
        title="Dynamic Incident Analysis: Unplanned Events by Hour & Vehicle Type",
        labels={'hour_of_day': 'Hour of Day (24H)', 'incident_count': 'Total Incidents Logged', 'veh_type': 'Vehicle Type'},
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig.update_layout(xaxis=dict(tickmode='linear', dtick=1))
    
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Raw data not found. Please ensure 'data/raw/astram_data.csv' exists in your project folder.")

st.info("👈 **Use the sidebar to navigate to the Live Risk Map and the Event Simulator.**")