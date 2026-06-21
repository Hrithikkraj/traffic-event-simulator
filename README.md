# ASTraM: Event-Driven Congestion Optimizer

ASTraM is a Streamlit-based decision-support prototype for traffic incident response in Bengaluru. Instead of only predicting regular traffic flow, the project focuses on unplanned events: where they happen, when they peak, how severe they may become, and how limited field resources can be allocated.

The dashboard is designed for operational users as well as reviewers. It explains the key insight, maps historical risk hotspots, and lets users simulate a new traffic incident to see a suggested deployment plan.

## What the App Does

- Identifies hour-wise patterns in unplanned congestion events.
- Shows a live-style hotspot map using H3 hexagonal zones.
- Estimates a simple Event Impact Score for incidents.
- Simulates new events on selected corridors.
- Allocates finite officers and barricades using an optimization model.
- Attempts to generate diversion routes through Mappls routing.

## Main Pages

### 1. Main Dashboard

File: `app/main.py`

The main page introduces ASTraM and shows the central analytical insight: unplanned events in the available data peak around 2 AM Bengaluru local time. The chart groups incidents by hour and vehicle type so users can understand whether buses, trucks, cars, or unknown reports are driving the pattern.

### 2. Live Risk Map

File: `app/pages/1_live_risk_map.py`

This page shows historical incident hotspots for a selected hour of the day. Each raised hexagon represents a small area of Bengaluru:

- Taller columns mean more recorded incidents.
- Warmer colors mean higher expected traffic impact.
- The sidebar hour slider filters the map by Bengaluru local time.

This page is useful for deciding which areas may need earlier monitoring or faster response at a given time.

### 3. Event Simulator

File: `app/pages/2_event_simulator.py`

This page lets users inject a what-if incident by choosing an incident type and corridor. The app estimates the event severity, adds it to a small active-event city snapshot, and calculates a resource allocation plan.

The simulator shows:

- Estimated traffic impact score.
- Assigned officers and barricades.
- Highlighted simulated incident row.
- Map view of the simulated event and background events.
- Suggested diversion route when routing data is available.

## Project Structure

```text
round_2/
  app/
    main.py
    pages/
      1_live_risk_map.py
      2_event_simulator.py
  data/
    raw/
      astram_data.csv
    processed/
      planned_events_clean.csv
      planned_events_scored.csv
      unplanned_events_clean.csv
      unplanned_events_scored.csv
  models_saved/
    lgb_clearance_model.pkl
  src/
    data_prep/
      clean_astram.py
      spatial_mapper.py
    evaluation/
      metrics_logger.py
    features/
      build_eis.py
    models/
      train_clearance.py
    optimization/
      resource_allocator.py
      route_diversion.py
  requirements.txt
```

## Data Requirements

The Streamlit app expects this file to exist:

```text
data/raw/astram_data.csv
```

Important columns used by the app include:

- `event_type`
- `event_cause`
- `start_datetime`
- `latitude`
- `longitude`
- `veh_type`
- `corridor`

The app filters `event_type == "unplanned"` for the main dashboard and live risk map. Timestamps are parsed as UTC and converted to `Asia/Kolkata` before extracting the hour of day.

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If `pydeck==0.8.1B` fails to install, change it to a valid release such as:

```text
pydeck==0.8.1b0
```

or install pydeck separately:

```bash
pip install pydeck
```

## Run the App

From the project root, run:

```bash
streamlit run app/main.py
```

Then open the local Streamlit URL shown in the terminal, usually:

```text
http://localhost:8501
```

## Mappls Configuration

The app currently contains a Mappls API key directly in the Streamlit page files:

- `app/pages/1_live_risk_map.py`
- `app/pages/2_event_simulator.py`
- `src/optimization/route_diversion.py`

For production use, move this key into environment variables or Streamlit secrets instead of keeping it in source code.

Example Streamlit secrets approach:

```toml
MAPMYINDIA_API_KEY = "your-key-here"
```

Then read it in Python with:

```python
MAPMYINDIA_API_KEY = st.secrets["MAPMYINDIA_API_KEY"]
```

## Backend Modules

### Data Preparation

`src/data_prep/clean_astram.py` loads raw ASTraM data, cleans datetime fields, calculates clearance duration, and splits planned/unplanned events.

`src/data_prep/spatial_mapper.py` assigns H3 hex IDs to event coordinates.

### Feature Engineering

`src/features/build_eis.py` builds an Event Impact Score using spatial reach, baseline flow proxy, closure severity, and clearance duration.

### Model Training

`src/models/train_clearance.py` trains a LightGBM clearance-time model and saves it under `models_saved/`.

### Optimization

`src/optimization/resource_allocator.py` allocates officers and barricades to active events using linear programming.

`src/optimization/route_diversion.py` calls the Mappls routing API to estimate diversion routes.

### Evaluation

`src/evaluation/metrics_logger.py` updates playbook-style metrics by comparing predicted and actual clearance times.

## Suggested Workflow

1. Place the raw ASTraM CSV at `data/raw/astram_data.csv`.
2. Run the cleaning and feature scripts if processed datasets need to be regenerated.
3. Train or refresh the clearance model if needed.
4. Start the Streamlit app.
5. Use the main dashboard to understand the city-wide pattern.
6. Use the live risk map to inspect risk by hour.
7. Use the event simulator to test incident response decisions.

## Notes and Limitations

- Event Impact Score values in the Streamlit map are simplified proxies for demonstration.
- The simulator uses a small sample background city state rather than a live incident feed.
- Diversion routing depends on Mappls API availability and key validity.
- This project is a prototype and should be validated with operational stakeholders before real-world deployment.

## License

No license file is currently included. Add a license before distributing or reusing this project publicly.
