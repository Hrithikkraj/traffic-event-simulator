import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

st.set_page_config(
    page_title="ASTraM | Event-Driven Optimizer",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DYNAMIC DATA EXTRACTION ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "astram_data.csv"


@st.cache_data
def load_summary_data():
    """Reads raw data dynamically so the dashboard works out-of-the-box."""
    data_path = RAW_DATA_PATH
    if data_path.exists():
        df = pd.read_csv(data_path)
        
        # Filter to unplanned operational events
        df = df[df['event_type'] == 'unplanned'].copy()
        
        # Dynamically extract the hour of the day
        df['start_datetime'] = pd.to_datetime(
            df['start_datetime'],
            errors='coerce',
            format='mixed',
            utc=True,
        ).dt.tz_convert('Asia/Kolkata')
        df['hour_of_day'] = df['start_datetime'].dt.hour
        invalid_datetime_count = df['hour_of_day'].isna().sum()
        df = df.dropna(subset=['hour_of_day'])
        df['hour_of_day'] = df['hour_of_day'].astype(int)
        
        # Clean up vehicle types for the chart
        df['veh_type'] = df['veh_type'].fillna('Unknown').astype(str).str.strip()
        df.loc[df['veh_type'].eq(''), 'veh_type'] = 'Unknown'
        df['veh_type'] = df['veh_type'].str.replace('_', ' ', regex=False).str.title()
        
        return df, invalid_datetime_count
    return pd.DataFrame(), 0

# --- Main UI ---
st.title("🚦 ASTraM: Event-Driven Congestion Optimizer")
st.markdown("""
**A proactive decision-support system for Bengaluru Traffic Police.** Most systems attempt to predict traffic flow. ASTraM focuses on a more practical question: when an incident happens, how badly will it affect the city and where should limited police resources go first?

The app uses historical unplanned traffic events to reveal when and where disruptions usually happen, then helps test response plans for new incidents. It is designed for quick operational decisions, not just data exploration.
""")

st.markdown("""
**How to use this dashboard**

- Start here to understand the main city-wide pattern.
- Open **Live Risk Map** to see where hotspots appear at a selected hour.
- Open **Event Simulator** to test a new incident and see a suggested deployment plan.
""")

st.divider()

df, invalid_datetime_count = load_summary_data()

if not df.empty:
    st.subheader("The Insight that Changes the Strategy")
    st.markdown("""
    When optimizing for unplanned congestion, traditional rush-hour logic fails. 
    Our analysis reveals that unplanned traffic events **peak at 2:00 AM**, completely inverted from passenger rush hours. 
    *Why?* Heavy freight and truck movement is restricted during the day, leading to massive nocturnal breakdown spikes on key arterials like Tumkur Road.

    For a common viewer, this means the riskiest response window is not always the busiest passenger travel window. Night-time preparedness can matter as much as morning and evening rush-hour planning.
    """)
    
    # Group by hour and vehicle type
    hourly_counts = df.groupby(['hour_of_day', 'veh_type']).size().reset_index(name='incident_count')
    total_by_hour = df.groupby('hour_of_day').size().reset_index(name='incident_count')

    if invalid_datetime_count:
        st.caption(f"Skipped {invalid_datetime_count} records with missing or invalid start times.")

    if not hourly_counts.empty:
        peak = total_by_hour.loc[total_by_hour['incident_count'].idxmax()]
        col1, col2, col3 = st.columns(3)
        col1.metric("Unplanned Events Loaded", f"{len(df):,}")
        col2.metric("Peak Local Hour", f"{int(peak['hour_of_day']):02d}:00")
        col3.metric("Peak Hour Incidents", f"{int(peak['incident_count']):,}")

        st.markdown("""
        **How to read the chart below:** each bar shows how many unplanned incidents were recorded at that hour of the day.
        The colors split those incidents by vehicle type, so you can see whether the pattern is driven by buses, trucks, cars, or unknown vehicle reports.
        """)

        chart = (
            alt.Chart(hourly_counts)
            .mark_bar()
            .encode(
                x=alt.X(
                    'hour_of_day:O',
                    title='Hour of Day (24H, Bengaluru Local Time)',
                    sort=list(range(24)),
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y('sum(incident_count):Q', title='Total Incidents Logged'),
                color=alt.Color('veh_type:N', title='Vehicle Type'),
                tooltip=[
                    alt.Tooltip('hour_of_day:O', title='Hour'),
                    alt.Tooltip('veh_type:N', title='Vehicle Type'),
                    alt.Tooltip('incident_count:Q', title='Incidents'),
                ],
            )
            .properties(
                title='Dynamic Incident Analysis: Unplanned Events by Hour & Vehicle Type',
                height=420,
            )
        )
        st.altair_chart(chart, use_container_width=True)

        st.info(
            "Operational takeaway: if the city only plans around commuter rush hours, it may miss a major overnight risk pattern. "
            "ASTraM highlights these hidden windows so patrols, barricades, and response teams can be positioned earlier."
        )
    else:
        st.warning("No valid incident timestamps were available for the hourly analysis.")

else:
    st.error("Raw data not found. Please ensure 'data/raw/astram_data.csv' exists in your project folder.")

st.info("👈 **Use the sidebar to navigate to the Live Risk Map and the Event Simulator.**")
