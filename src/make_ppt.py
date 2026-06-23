"""Build the Gridlock pitch deck (.pptx) from the real results + figures.

Run: /opt/anaconda3/bin/python src/make_ppt.py  ->  Gridlock_Pitch_Deck.pptx
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image
import config as C

BLUE = RGBColor(0x28, 0x74, 0xF0)
INK = RGBColor(0x1A, 0x1A, 0x2E)
YEL = RGBColor(0xFF, 0xE1, 0x1B)
GREY = RGBColor(0x6B, 0x72, 0x80)
LIGHT = RGBColor(0xF4, 0xF6, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x27, 0xAE, 0x60)
RED = RGBColor(0xC0, 0x39, 0x2B)
AMBER = RGBColor(0xF3, 0x9C, 0x12)
FIG = C.FIG_DIR / "ppt"
FONT = "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
W, H = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def slide():
    return prs.slides.add_slide(BLANK)


def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    sp = s.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(1)
    sp.shadow.inherit = False
    return sp


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=4):
    """runs: list of paragraphs; each = list of (txt, size, color, bold) tuples."""
    tb = s.shapes.add_textbox(x, y, w, h); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space); p.space_before = Pt(0)
        for (txt, size, color, bold) in para:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold; r.font.name = FONT
    return tb


def header(s, kicker, title):
    rect(s, 0, 0, W, Inches(1.15), WHITE)
    rect(s, 0, 0, Inches(0.18), Inches(1.15), BLUE)
    text(s, Inches(0.5), Inches(0.12), Inches(12), Inches(0.35),
         [[(kicker, 12, BLUE, True)]])
    text(s, Inches(0.5), Inches(0.42), Inches(12.3), Inches(0.7),
         [[(title, 26, INK, True)]])
    rect(s, Inches(0.5), Inches(1.12), Inches(12.33), Pt(2), LIGHT)


def pic(s, name, x, y, w):
    p = FIG / name
    iw, ih = Image.open(p).size
    h = int(w * ih / iw)
    s.shapes.add_picture(str(p), x, y, width=w, height=Emu(h))
    return h


def card(s, x, y, w, h, accent, title, body):
    rect(s, x, y, w, h, LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    rect(s, x, y, w, Inches(0.10), accent, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.18), y + Inches(0.22), w - Inches(0.36), h - Inches(0.4),
         [[(title, 15, INK, True)]] + [[(body, 12.5, GREY, False)]], space=5)


# ----------------------------------------------------------------- 1 TITLE
s = slide(); rect(s, 0, 0, W, H, BLUE)
rect(s, 0, 0, W, Inches(0.25), YEL)
text(s, Inches(0.9), Inches(2.2), Inches(11.5), Inches(1.3),
     [[("🚦 GRIDLOCK", 54, WHITE, True)]])
text(s, Inches(0.95), Inches(3.5), Inches(11.5), Inches(0.7),
     [[("Event-Driven Congestion Intelligence for Bengaluru Traffic", 24, YEL, True)]])
text(s, Inches(0.95), Inches(4.3), Inches(11.5), Inches(0.6),
     [[("Forecast  →  Quantify Impact  →  Prescribe Deployment  →  Learn", 18, WHITE, False)]])
text(s, Inches(0.95), Inches(6.4), Inches(11.5), Inches(0.6),
     [[("Flipkart Gridlock Hackathon 2.0 · Round 2", 14, WHITE, True)],
      [("Built on the anonymized ASTraM incident dataset — 8,173 events × 46 fields", 12, LIGHT, False)]])

# ----------------------------------------------------------------- 2 PROBLEM
s = slide(); header(s, "THE OPERATIONAL CHALLENGE", "Events break the city — and we react blind")
text(s, Inches(0.5), Inches(1.35), Inches(12.3), Inches(0.8),
     [[("Rallies, festivals, sports, construction & sudden gatherings cause localized "
        "traffic breakdowns. Today the response is reactive and experience-driven.", 16, INK, False)]])
cy, cw, ch = Inches(2.5), Inches(3.95), Inches(3.4)
card(s, Inches(0.5), cy, cw, ch, RED, "① Impact is not quantified",
     "No way to know in advance how bad an event will be, how long it will tie up the road, "
     "or which junctions it threatens.")
card(s, Inches(4.69), cy, cw, ch, AMBER, "② Deployment is guesswork",
     "Officers, barricades and diversions are assigned from experience — not from data, "
     "and not optimized against a finite resource pool.")
card(s, Inches(8.88), cy, cw, ch, BLUE, "③ No post-event learning",
     "Every event is handled fresh. Mistakes are never fed back; the system never "
     "gets smarter after the fact.")

# ----------------------------------------------------------------- 3 HOOK
s = slide(); header(s, "DATA INSIGHT MOST TEAMS WILL MISS", "This is an incident log — not congestion data")
pic(s, "events_by_hour.png", Inches(0.5), Inches(1.5), Inches(7.6))
text(s, Inches(8.4), Inches(1.7), Inches(4.5), Inches(5),
     [[("There is NO speed / volume / delay field.", 15, RED, True)],
      [("So the target — “traffic impact” — does not exist in the data. "
        "It must be engineered.", 13.5, INK, False)],
      [("", 6, INK, False)],
      [("Events peak at 2 AM, not rush hour:", 15, BLUE, True)],
      [("60% are vehicle breakdowns, driven by night-time freight movement. "
        "Teams that assume normal rush-hour patterns will build the wrong model.", 13.5, INK, False)],
      [("", 6, INK, False)],
      [("We turn this gap into our centrepiece.", 14, INK, True)]])

# ----------------------------------------------------------------- 4 REFRAME
s = slide(); header(s, "OUR REFRAME", "Not prediction — a decision-support system")
text(s, Inches(0.5), Inches(1.35), Inches(12.3), Inches(0.6),
     [[("Most teams stop at “predict congestion.” We deliver the full operational loop:", 16, INK, False)]])
labels = [("FORECAST", "where / when / how many", BLUE),
          ("QUANTIFY", "Event Impact Score", GREEN),
          ("PRESCRIBE", "manpower · barricades · diversions", AMBER),
          ("LEARN", "post-event playbook", RED)]
x = Inches(0.6); bw = Inches(2.85); gap = Inches(0.25)
for i, (t1, t2, c) in enumerate(labels):
    rect(s, x, Inches(2.6), bw, Inches(1.9), c, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, Inches(2.95), bw, Inches(0.7), [[(t1, 20, WHITE, True)]], align=PP_ALIGN.CENTER)
    text(s, x + Inches(0.1), Inches(3.65), bw - Inches(0.2), Inches(0.8),
         [[(t2, 12.5, WHITE, False)]], align=PP_ALIGN.CENTER)
    if i < 3:
        text(s, x + bw, Inches(3.0), gap, Inches(1), [[("→", 24, INK, True)]], align=PP_ALIGN.CENTER)
    x = x + bw + gap
text(s, Inches(0.6), Inches(5.0), Inches(12), Inches(0.8),
     [[("Two pipelines — Planned (proactive scheduling) and Unplanned (real-time triage) — "
        "exactly matching the problem statement.", 14, GREY, False)]])

# ----------------------------------------------------------------- 5 ARCHITECTURE
s = slide(); header(s, "SYSTEM ARCHITECTURE", "Four layers on one data foundation")
rows = [("L0 · DATA FOUNDATION", "clean · leakage-safe features · H3 hex bins · EN+Kannada text", INK),
        ("L1 · FORECAST", "LightGBM-Poisson corridor counts · empirical-Bayes hotspots · Hawkes self-excitation", BLUE),
        ("L2 · IMPACT (EIS)", "clearance quantile regression + road-closure classifier → Event Impact Score", GREEN),
        ("L3 · PRESCRIBE", "manpower / barricades / diversions + city-wide officer optimization (ILP)", AMBER),
        ("L4 · LEARN", "predicted-vs-actual playbook · model-drift detection · retrain triggers", RED)]
y = Inches(1.45); rh = Inches(1.0)
for title, body, c in rows:
    rect(s, Inches(0.6), y, Inches(3.4), Inches(0.85), c, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(0.6), y + Inches(0.22), Inches(3.4), Inches(0.5), [[(title, 14, WHITE, True)]],
         align=PP_ALIGN.CENTER)
    rect(s, Inches(4.2), y, Inches(8.5), Inches(0.85), LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(4.45), y + Inches(0.18), Inches(8.1), Inches(0.6), [[(body, 13, INK, False)]],
         anchor=MSO_ANCHOR.MIDDLE)
    y = y + rh

# ----------------------------------------------------------------- 6 EIS
s = slide(); header(s, "L2 · THE SPINE", "Event Impact Score — engineering the missing target")
text(s, Inches(0.5), Inches(1.35), Inches(7.4), Inches(3),
     [[("Framed as expected vehicle-hours of delay:", 14, INK, True)],
      [("EIS ≈ Clearance × Spatial reach × Baseline flow × Closure severity",
        13, BLUE, True)],
      [("", 6, INK, False)],
      [("• Clearance time is predicted (leakage-safe), not observed", 13, INK, False)],
      [("• Robust percentile-rank scaling → Low / Medium / High / Critical", 13, INK, False)],
      [("• VALIDATED against observed severity:", 13, INK, True)],
      [("    Spearman 0.70 · AUC 0.89 flagging top-10% impact events", 13, GREEN, True)]])
pic(s, "eis_by_cause.png", Inches(8.0), Inches(1.45), Inches(4.9))

# ----------------------------------------------------------------- 7 ML RIGOR
s = slide(); header(s, "MODELLING RIGOUR (KAGGLE-GRADE)", "10-model zoo · k-fold CV · leakage hunt · Optuna")
pic(s, "closure_leaderboard.png", Inches(0.5), Inches(1.45), Inches(7.2))
text(s, Inches(8.0), Inches(1.6), Inches(4.9), Inches(5),
     [[("Headline results", 16, INK, True)],
      [("Clearance time   MAE 2.88 h (blended)", 13.5, INK, False)],
      [("Road closure     PR-AUC 0.471  ·  +469% over baseline", 13.5, INK, False)],
      [("EIS validity     Spearman 0.70 · AUC 0.89", 13.5, INK, False)],
      [("Event forecast   +16.7% over lag-7 baseline", 13.5, INK, False)],
      [("", 6, INK, False)],
      [("Discipline that wins:", 16, BLUE, True)],
      [("• Time-split CV + spatial holdout (no future leakage)", 12.5, GREY, False)],
      [("• Leakage hunt: dropped end-coords leaking at AUC 0.976", 12.5, GREY, False)],
      [("• Priority shown to be ~location-circular (we report it honestly)", 12.5, GREY, False)],
      [("• Stacked ensemble + Optuna tuning", 12.5, GREY, False)]])

# ----------------------------------------------------------------- 8 FORECAST
s = slide(); header(s, "L1 · FORECAST", "Where, when and how many events — ahead of time")
pic(s, "daily_volume.png", Inches(0.5), Inches(1.5), Inches(7.7))
text(s, Inches(8.4), Inches(1.7), Inches(4.5), Inches(5),
     [[("LightGBM-Poisson", 15, BLUE, True)],
      [("corridor × day event counts — 16.7% better than the lag-7 baseline.", 13, INK, False)],
      [("", 5, INK, False)],
      [("Empirical-Bayes hotspots", 15, BLUE, True)],
      [("recurring corridor × hour risk surface for pre-positioning.", 13, INK, False)],
      [("", 5, INK, False)],
      [("Hawkes self-excitation", 15, BLUE, True)],
      [("accidents cluster — branching ratio 0.31 — quantifying contagion.", 13, INK, False)]])

# ----------------------------------------------------------------- 9 PRESCRIBE
s = slide(); header(s, "L3 · PRESCRIBE + OPTIMIZE", "The deliverable most teams never reach")
text(s, Inches(0.5), Inches(1.35), Inches(6.1), Inches(5),
     [[("Per-event plan", 16, AMBER, True)],
      [("Officers, barricade units and a real road-network diversion (OSRM) — "
        "driven by the validated EIS tier + closure probability.", 13, INK, False)],
      [("", 6, INK, False)],
      [("City-wide optimization", 16, AMBER, True)],
      [("Finite officer pool allocated by ILP (PuLP) — two doctrines:", 13, INK, False)],
      [("• Priority — cover highest-impact first (triage)", 12.5, INK, False)],
      [("• Efficiency — maximize total mitigated impact", 12.5, INK, False)]])
rect(s, Inches(7.0), Inches(1.6), Inches(5.8), Inches(4.6), LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
rect(s, Inches(7.0), Inches(1.6), Inches(5.8), Inches(0.7), RED, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(7.2), Inches(1.72), Inches(5.4), Inches(0.5),
     [[("Surge day — 7 Mar 2024", 16, WHITE, True)]])
text(s, Inches(7.3), Inches(2.5), Inches(5.3), Inches(3.6),
     [[("214 events in one day", 22, INK, True)],
      [("≈ 1,096 officers needed", 18, RED, True)],
      [("vs ~120 available  →  a quantified deficit", 14, INK, False)],
      [("", 8, INK, False)],
      [("The system tells the commander exactly which events to staff first and how "
        "many more officers to escalate for — turning guesswork into math.", 13, GREY, False)]])

# ----------------------------------------------------------------- 10 LEARN
s = slide(); header(s, "L4 · LEARN", "The post-event loop the brief explicitly asks for")
pic(s, "learning_bias.png", Inches(0.5), Inches(1.5), Inches(7.6))
text(s, Inches(8.3), Inches(1.7), Inches(4.6), Inches(5),
     [[("After events close,", 15, RED, True)],
      [("we compare leak-free predictions with reality and build a playbook keyed by "
        "cause × H3 hex.", 13, INK, False)],
      [("", 6, INK, False)],
      [("It self-diagnoses:", 15, RED, True)],
      [("the model under-predicts infrastructure events — potholes by +8.0 h, "
        "water-logging +7.1 h — and flags those cells for retraining.", 13, INK, False)],
      [("", 6, INK, False)],
      [("Closes the “no post-event learning” gap most teams ignore.", 13, INK, True)]])

# ----------------------------------------------------------------- 11 DEMO
s = slide(); header(s, "THE PRODUCT", "A live decision-support dashboard")
tabs = [("🎯 Event Simulator", "score any what-if event → EIS, clearance P50/P90, full deployment plan"),
        ("🗺️ City Risk Map", "all 8,173 events on a Bengaluru map, coloured by impact tier"),
        ("📅 Surge-Day Replay", "replay a real day, set an officer budget → live allocation + deficit"),
        ("📈 Forecast & Hotspots", "corridor × hour risk heatmap, Hawkes, the 2-AM explainer"),
        ("🔁 Learning Loop", "predicted-vs-actual playbook + drift alerts")]
y = Inches(1.45)
for t1, t2 in tabs:
    rect(s, Inches(0.6), y, Inches(3.5), Inches(0.82), BLUE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(0.7), y + Inches(0.18), Inches(3.3), Inches(0.5), [[(t1, 13.5, WHITE, True)]])
    text(s, Inches(4.3), y + Inches(0.16), Inches(8.4), Inches(0.6), [[(t2, 13, INK, False)]],
         anchor=MSO_ANCHOR.MIDDLE)
    y = y + Inches(0.95)
text(s, Inches(0.6), Inches(6.35), Inches(12), Inches(0.8),
     [[("Live proof: the same breakdown scores EIS 17 at 2 AM vs 78 at 9 AM rush; "
        "a VIP movement scores 99.7 (Critical) with a real OSRM diversion drawn on the map.",
        13, GREY, False)]])

# ----------------------------------------------------------------- 12 WHY WIN
s = slide(); header(s, "WHY THIS WINS", "Seven things the field won't have together")
items = [("Correct reframe", "incident log, not congestion data"),
         ("Engineered + validated EIS", "Spearman 0.70 — the missing target, proven"),
         ("k-fold model zoo", "10 models, stacking, Optuna — not one model"),
         ("Prescription + ILP", "we allocate scarce officers; others only predict"),
         ("Post-event learning", "L4 playbook + drift — the 3rd gap, solved"),
         ("Real-ML simulator", "runs the trained models (not random numbers)"),
         ("Honesty & rigor", "leakage hunt, time-split CV, stated limits")]
xs = [Inches(0.6), Inches(4.85), Inches(9.1)]
for i, (t1, t2) in enumerate(items):
    col = i % 3; row = i // 3
    x = xs[col]; y = Inches(1.55) + row * Inches(1.75)
    card(s, x, y, Inches(3.95), Inches(1.55), [BLUE, GREEN, AMBER, RED, BLUE, GREEN, AMBER][i], t1, t2)

# ----------------------------------------------------------------- 13 IMPACT
s = slide(); header(s, "IMPACT, ROADMAP & HONESTY", "Operational value — and what we'd add next")
text(s, Inches(0.5), Inches(1.4), Inches(6.0), Inches(5),
     [[("Operational value", 16, GREEN, True)],
      [("• Quantified impact before the event, not after", 13, INK, False)],
      [("• Optimal, defensible resource deployment", 13, INK, False)],
      [("• Faster clearance via right-sized response", 13, INK, False)],
      [("• A city that gets smarter after every event", 13, INK, False)],
      [("", 8, INK, False)],
      [("Roadmap", 16, BLUE, True)],
      [("• Plug in live flow (Google/TomTom) to calibrate EIS", 13, INK, False)],
      [("• Spatio-temporal GNN forecasting · officer-shift scheduling", 13, INK, False)]])
text(s, Inches(6.9), Inches(1.4), Inches(5.9), Inches(5),
     [[("Honest limitations (we say so)", 16, RED, True)],
      [("• No ground-truth flow → EIS validated against proxies", 13, INK, False)],
      [("• Manpower data sparse (1.6%) → optimization + rules,", 13, INK, False)],
      [("   not over-claimed as learned", 13, INK, False)],
      [("• 5 months of data → calendar priors mitigate seasonality", 13, INK, False)],
      [("", 10, INK, False)],
      [("Stack", 16, BLUE, True)],
      [("Python · LightGBM/XGBoost/CatBoost · scikit-learn · Optuna ·", 12.5, GREY, False)],
      [("H3 · PuLP · OSRM · Streamlit + pydeck", 12.5, GREY, False)]])

# ----------------------------------------------------------------- 14 CLOSE
s = slide(); rect(s, 0, 0, W, H, INK)
rect(s, 0, Inches(7.25), W, Inches(0.25), YEL)
text(s, Inches(0.9), Inches(2.3), Inches(11.5), Inches(1.2),
     [[("From reaction to anticipation.", 40, WHITE, True)]])
text(s, Inches(0.95), Inches(3.6), Inches(11.5), Inches(1.4),
     [[("Forecast the event · quantify the impact · deploy the optimal response · "
        "learn from every outcome.", 18, YEL, False)]])
text(s, Inches(0.95), Inches(5.6), Inches(11.5), Inches(0.6),
     [[("GRIDLOCK — Event-Driven Congestion Intelligence", 16, WHITE, True)],
      [("Flipkart Gridlock Hackathon 2.0 · Round 2", 13, LIGHT, False)]])

out = C.ROOT / "Gridlock_Pitch_Deck.pptx"
prs.save(str(out))
print(f"Saved deck -> {out}  ({len(list(prs.slides))} slides)")
