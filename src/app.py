"""Gridlock — Event-Driven Congestion decision-support dashboard.

Launch:  bash run_app.sh        (sets libomp env + starts Streamlit)
or:      DYLD_LIBRARY_PATH=/opt/homebrew/opt/libomp/lib streamlit run src/app.py
"""
import numpy as np
import pandas as pd
import joblib
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pydeck as pdk

import config as C
import inference as I
import prescribe as P

st.set_page_config(page_title="Gridlock — Event Congestion", layout="wide", page_icon="🚦")

TIER_COLOR = {"Low": [39, 174, 96], "Medium": [243, 156, 18],
              "High": [230, 126, 34], "Critical": [192, 57, 43]}
TIER_HEX = {"Low": "#27ae60", "Medium": "#f39c12", "High": "#e67e22", "Critical": "#c0392b"}


@st.cache_data
def load():
    df = pd.read_pickle(C.DATA_DIR / "scored.pkl")
    df["date"] = pd.to_datetime(df["event_time"]).dt.tz_localize(None).dt.date
    hot = pd.read_csv(C.PRED_DIR / "hotspot_corridor_hour.csv")
    hawkes = joblib.load(C.MODEL_DIR / "hawkes_accident.pkl")
    art = joblib.load(C.MODEL_DIR / "eis_artifacts.pkl")
    pb = pd.read_csv(C.PRED_DIR / "learning_playbook.csv")
    pb_cause = pd.read_csv(C.PRED_DIR / "learning_playbook_by_cause.csv")
    return df, hot, hawkes, art, pb, pb_cause


df, HOT, HAWKES, ART, PB, PB_CAUSE = load()
CORRIDORS = sorted([c for c in ART["corridor_centroid"].keys() if c not in ("unknown",)])
CAUSES = ["vehicle_breakdown", "accident", "congestion", "tree_fall", "water_logging",
          "pot_holes", "construction", "public_event", "procession", "vip_movement",
          "protest", "road_conditions", "others"]
VEH = ["unknown", "bmtc_bus", "heavy_vehicle", "lcv", "truck", "private_car",
       "private_bus", "ksrtc_bus", "taxi", "auto"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

st.title("🚦 Gridlock — Event-Driven Congestion Intelligence")
st.caption("Forecast → Quantify Impact → Prescribe deployment → Learn.  Bengaluru ASTraM data, 8,173 events.")

t1, t2, t3, t4, t5 = st.tabs(["🎯 Event Simulator", "🗺️ City Risk Map",
                              "📅 Surge-Day Replay", "📈 Forecast & Hotspots",
                              "🔁 Learning Loop"])

# ============================================================ Simulator
with t1:
    st.subheader("Score a hypothetical event and get a deployment plan")
    c = st.columns(4)
    cause = c[0].selectbox("Event cause", CAUSES)
    corridor = c[1].selectbox("Corridor", CORRIDORS,
                              index=CORRIDORS.index("Hosur Road") if "Hosur Road" in CORRIDORS else 0)
    hour = c[2].slider("Hour of day", 0, 23, 9)
    dow = c[3].selectbox("Day", range(7), format_func=lambda i: DOW[i], index=4)
    c2 = st.columns(4)
    veh = c2[0].selectbox("Vehicle type", VEH)
    planned = c2[1].checkbox("Planned event (known schedule)")
    pdur = c2[2].number_input("Planned duration (h)", 0.5, 24.0, 4.0) if planned else None

    s = I.score_event(cause, corridor, hour, dow, veh_type=veh, planned_duration_h=pdur)
    rec = P.recommend(cause, corridor, s["EIS"], s["tier"], s["closure_prob"],
                      s["duration_used_h"], "planned" if planned else "unplanned")

    left, right = st.columns([1, 1])
    with left:
        g = go.Figure(go.Indicator(
            mode="gauge+number", value=s["EIS"],
            title={"text": f"Event Impact Score — <b>{s['tier']}</b>"},
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": TIER_HEX[s["tier"]]},
                   "steps": [{"range": [0, 50], "color": "#eafaf1"},
                             {"range": [50, 80], "color": "#fef9e7"},
                             {"range": [80, 95], "color": "#fdebd0"},
                             {"range": [95, 100], "color": "#f9ebea"}]}))
        g.update_layout(height=280, margin=dict(t=50, b=10))
        st.plotly_chart(g, use_container_width=True)
        m = st.columns(3)
        m[0].metric("Clearance P50", f"{s['clearance_p50_h']} h")
        m[1].metric("Clearance P90 (worst)", f"{s['clearance_p90_h']} h")
        m[2].metric("Road-closure prob", f"{s['closure_prob']*100:.0f}%")
    with right:
        st.markdown(f"### 📋 Recommended deployment")
        st.metric("Officers", rec["officers_needed"])
        cc = st.columns(2)
        cc[0].metric("Barricade units", rec["barricades"])
        cc[1].metric("Diversion", "YES" if rec["diversion"] else "no")
        for a in rec["actions"]:
            st.markdown(f"- {a}")

        if rec["diversion"]:
            dv = P.diversion_route(corridor)
            c0 = ART["corridor_centroid"].get(corridor, {"latitude": 12.97, "longitude": 77.59})
            layers = [pdk.Layer("ScatterplotLayer",
                                data=pd.DataFrame([{"lon": c0["longitude"], "lat": c0["latitude"]}]),
                                get_position=["lon", "lat"], get_fill_color=[192, 57, 43],
                                get_radius=250)]
            if dv["route_coords"]:
                layers.append(pdk.Layer("PathLayer",
                                        data=pd.DataFrame([{"path": dv["route_coords"]}]),
                                        get_path="path", get_color=[255, 200, 0],
                                        width_min_pixels=5))
                st.caption(f"🛣️ Live diversion → {dv['target']} · "
                           f"{dv['distance_km']:.1f} km · {dv['duration_min']:.0f} min")
            else:
                st.caption(f"🛣️ Suggested diversion → {dv['target']} "
                           "(live road route unavailable offline)")
            st.pydeck_chart(pdk.Deck(map_style=None, layers=layers,
                                     initial_view_state=pdk.ViewState(
                                         latitude=c0["latitude"], longitude=c0["longitude"], zoom=12)))

# ============================================================ Risk map
with t2:
    st.subheader("Where the impact is — all scored events")
    f = st.columns(3)
    tiers = f[0].multiselect("Tiers", list(TIER_COLOR), default=["High", "Critical"])
    hr = f[1].slider("Hour range", 0, 23, (0, 23))
    etype = f[2].selectbox("Event type", ["all", "unplanned", "planned"])
    d = df[df["EIS_tier"].isin(tiers) & df["hour"].between(*hr)]
    if etype != "all":
        d = d[d["event_type"] == etype]
    d = d.dropna(subset=["latitude", "longitude"]).copy()
    d["color"] = d["EIS_tier"].map(TIER_COLOR)

    k = st.columns(4)
    k[0].metric("Events shown", f"{len(d):,}")
    k[1].metric("Mean EIS", f"{d['EIS'].mean():.0f}" if len(d) else "—")
    k[2].metric("Critical", int((d.EIS_tier == "Critical").sum()))
    k[3].metric("Mean closure prob", f"{d['closure_prob'].mean()*100:.0f}%" if len(d) else "—")

    if len(d):
        st.pydeck_chart(pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(latitude=12.97, longitude=77.59, zoom=10.2),
            layers=[pdk.Layer("ScatterplotLayer", data=d,
                              get_position=["longitude", "latitude"],
                              get_fill_color="color", get_radius=120, opacity=0.6,
                              pickable=True)],
            tooltip={"text": "{event_cause}\n{corridor}\nEIS {EIS}"}))

# ============================================================ Surge replay
with t3:
    st.subheader("Replay a real day & allocate a finite officer pool")
    daily = df.groupby("date").size().sort_values(ascending=False)
    spike_dates = daily.index.tolist()
    day = st.selectbox("Pick a day (sorted by event volume)", spike_dates,
                       format_func=lambda x: f"{x}  ({daily[x]} events)")
    cc = st.columns(2)
    budget = cc[0].slider("Officers available", 10, 400, 120, step=10)
    mode = cc[1].radio("Doctrine", ["priority", "efficiency"], horizontal=True)

    dd = df[df["date"] == day].copy()
    # per-event officer need from the rule
    dd["officers_needed"] = [
        P.recommend(r.event_cause, r.corridor, r.EIS, r.EIS_tier, r.closure_prob,
                    r.pred_duration_h, r.event_type)["officers_needed"]
        for r in dd.itertuples()]
    alloc, summ = P.allocate(dd.assign(id=dd["id"])[["id", "EIS", "officers_needed"]],
                             budget=budget, mode=mode)

    k = st.columns(5)
    k[0].metric("Events", summ["events_total"])
    k[1].metric("Officers needed", summ["officers_needed_total"])
    k[2].metric("Deficit", summ["deficit"], delta=f"-{summ['deficit']}", delta_color="inverse")
    k[3].metric("Staffed", summ["events_staffed"])
    k[4].metric("Impact covered", f"{summ['impact_covered_pct']}%")

    cnt = dd["EIS_tier"].value_counts().reindex(["Low", "Medium", "High", "Critical"]).fillna(0)
    fig = px.bar(x=cnt.index, y=cnt.values, color=cnt.index, color_discrete_map=TIER_HEX,
                 labels={"x": "tier", "y": "events"}, title=f"{day}: {len(dd)} events by impact tier")
    st.plotly_chart(fig, use_container_width=True)
    if summ["unmet_high_impact"]:
        st.warning(f"⚠️ {len(summ['unmet_high_impact'])} high-impact events UNMET at this budget — "
                   f"escalate for ~{summ['deficit']} more officers.")

# ============================================================ Forecast
with t4:
    st.subheader("Forecast & recurring hotspots (L1)")
    cc = st.columns([2, 1])
    with cc[0]:
        piv = (HOT.pivot_table(index="corridor", columns="hr", values="rate_per_day", aggfunc="sum")
               .fillna(0))
        piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index].head(12)
        fig = px.imshow(piv, aspect="auto", color_continuous_scale="YlOrRd",
                        labels=dict(x="hour", y="corridor", color="events/day"),
                        title="Expected events — corridor × hour (empirical-Bayes)")
        st.plotly_chart(fig, use_container_width=True)
    with cc[1]:
        st.markdown("#### 🔁 Accident self-excitation (Hawkes)")
        st.metric("Branching ratio", f"{HAWKES['branching']:.2f}",
                  help="Share of accidents that trigger short-horizon follow-on incidents")
        st.metric("Excitation half-life", f"{HAWKES['half_life_h']*60:.0f} min")
        st.markdown("#### 🌙 Why nights, not rush hour?")
        st.write("60% of events are vehicle breakdowns, driven by night-time freight "
                 "movement — the impact model up-weights the rarer rush-hour events.")
        byhour = df.groupby("hour").size()
        st.plotly_chart(px.line(x=byhour.index, y=byhour.values,
                                labels={"x": "hour", "y": "events"}, title="Events by hour"),
                        use_container_width=True)

# ============================================================ Learning loop
with t5:
    st.subheader("Post-event learning — predicted vs. actual, model-drift detection")
    st.caption("After events close, the system compares leak-free out-of-fold predictions "
               "with reality and flags cause/locations where the model is systematically off.")
    drift = PB[PB["retrain_flag"] == 1]
    k = st.columns(4)
    k[0].metric("Playbook cells (cause × hex)", f"{len(PB):,}")
    k[1].metric("Cells with ≥5 events", int((PB["n"] >= 5).sum()))
    k[2].metric("Drift cells (retrain)", len(drift))
    worst = PB_CAUSE.reindex(PB_CAUSE["model_bias_hrs"].abs().sort_values(ascending=False).index).iloc[0]
    k[3].metric("Worst-calibrated cause", str(worst["event_cause"]),
                delta=f"{worst['model_bias_hrs']:+.1f} h bias")

    cc = st.columns([1, 1])
    with cc[0]:
        st.markdown("#### Model bias by cause (h, + = under-predicted)")
        fig = px.bar(PB_CAUSE.sort_values("model_bias_hrs"),
                     x="model_bias_hrs", y="event_cause", orientation="h",
                     color="model_bias_hrs", color_continuous_scale="RdBu_r",
                     labels={"model_bias_hrs": "actual − predicted (h)", "event_cause": ""})
        st.plotly_chart(fig, use_container_width=True)
    with cc[1]:
        st.markdown("#### 🚨 Cells flagged for retraining")
        if len(drift):
            st.dataframe(drift[["event_cause", "corridor", "n", "historical_avg_hrs",
                                "model_bias_hrs"]].round(2).reset_index(drop=True),
                         use_container_width=True, height=320)
        else:
            st.success("No drift cells above threshold — model is well-calibrated.")
    st.info("This closes the loop the brief calls out — *'no post-event learning system'* — "
            "feeding drift back into the next retrain.")
