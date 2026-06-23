"""Assemble a narrated, captioned guided-tour demo video from the dashboard shots.

Pipeline: compose branded 1080p scene frames (PIL) -> narrate (macOS `say`) ->
per-scene clips with fades + audio (ffmpeg/videotoolbox) -> concat -> Gridlock_Demo.mp4

Run: /opt/anaconda3/bin/python src/make_demo.py
"""
import subprocess, shlex
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "outputs/demo/shots"
WORK = ROOT / "outputs/demo/build"; WORK.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "Gridlock_Demo.mp4"
WIDTH, HEIGHT = 1920, 1080

BG = (14, 19, 32); CARD = (27, 36, 54); TXT = (242, 245, 250)
YEL = (255, 225, 27); ABLUE = (90, 160, 255); MUT = (154, 167, 184); LINE = (42, 53, 80)


def font(sz, bold=True):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def ctext(d, cx, y, s, fnt, fill):
    w = d.textbbox((0, 0), s, font=fnt)[2]
    d.text((cx - w / 2, y), s, font=fnt, fill=fill)


# scenes: (shot, title, caption, narration)
SCENES = [
    (None, "GRIDLOCK", "Event-Driven Congestion Intelligence — Live Dashboard Demo",
     "Gridlock turns event driven congestion into a decision. Forecast the event, "
     "quantify its impact, prescribe the response, and learn from it. Here is the live dashboard."),
    ("1_sim.png", "Event Simulator", "Score any event  →  instant deployment plan",
     "The event simulator scores any hypothetical incident. A VIP movement on a busy corridor "
     "scores high impact, and the system instantly recommends officers, barricades, and diversions."),
    ("3_riskmap.png", "City Risk Map", "8,173 events across Bengaluru, coloured by impact tier",
     "The city risk map plots every event, coloured by impact tier, surfacing the critical "
     "hotspots along Bengaluru's arterials."),
    ("4_surge.png", "Surge-Day Replay", "Allocate a finite force  ·  expose the deficit",
     "Replay any real day. On the March seventh surge, two hundred and fourteen events needed "
     "over a thousand officers. The optimizer triages a finite force and quantifies the shortfall."),
    ("5_forecast.png", "Forecast & Hotspots", "Where, when & why  —  2 AM is the peak, not rush hour",
     "Forecasting predicts where and when events strike. Notice the peak at two a.m., "
     "freight breakdowns, not rush hour, a signal most teams miss."),
    ("6_learning.png", "Learning Loop", "Predicted vs actual  ·  automatic drift detection",
     "After every event, the learning loop compares predictions with reality and flags where "
     "the model drifts, so the city keeps getting smarter."),
    (None, "From reaction to anticipation.", "Team TrafficSolvers  ·  Flipkart Gridlock Hackathon 2.0",
     "Gridlock. From reaction to anticipation. Built by Team Traffic Solvers for the "
     "Flipkart Gridlock Hackathon."),
]


def compose(shot, title, caption, idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, WIDTH, 6], fill=YEL)
    d.rectangle([0, HEIGHT - 6, WIDTH, HEIGHT], fill=ABLUE)
    d.text((70, 36), "GRIDLOCK · Live Dashboard Demo", font=font(26), fill=MUT)

    if shot is None:                                   # title / outro card
        ctext(d, WIDTH / 2, 420, title, font(96), TXT)
        ctext(d, WIDTH / 2, 560, caption, font(40, False), YEL)
        ctext(d, WIDTH / 2, 680, "Forecast → Quantify → Prescribe → Learn", font(32, False), MUT)
    else:
        ctext(d, WIDTH / 2, 86, title, font(60), TXT)
        im = Image.open(SHOTS / shot).convert("RGB")
        bw, bh = 1560, 760                              # screenshot box
        sc = min(bw / im.width, bh / im.height)
        nw, nh = int(im.width * sc), int(im.height * sc)
        im = im.resize((nw, nh), Image.LANCZOS)
        x, y = (WIDTH - nw) // 2, 180
        d.rectangle([x - 3, y - 3, x + nw + 3, y + nh + 3], outline=LINE, width=3)
        img.paste(im, (x, y))
        cy = 980
        d.rounded_rectangle([160, cy - 28, WIDTH - 160, cy + 40], radius=16, fill=CARD)
        ctext(d, WIDTH / 2, cy - 16, caption, font(36, True), TXT)
    p = WORK / f"scene_{idx}.png"; img.save(p)
    return p


def run(cmd):
    subprocess.run(shlex.split(cmd), check=True, capture_output=True)


def narrate(text, idx):
    aiff = WORK / f"v_{idx}.aiff"
    subprocess.run(["say", "-v", "Samantha", "-o", str(aiff), text], check=True)
    out = subprocess.run(["/opt/anaconda3/bin/ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "default=nw=1:nk=1", str(aiff)],
                         capture_output=True, text=True)
    return aiff, float(out.stdout.strip())


def main():
    clips = []
    for i, (shot, title, cap, narr) in enumerate(SCENES):
        png = compose(shot, title, cap, i)
        aiff, dur = narrate(narr, i)
        T = round(dur + 1.3, 2)                         # pad after speech
        mp4 = WORK / f"clip_{i}.mp4"
        vf = (f"scale={WIDTH}:{HEIGHT},fade=t=in:st=0:d=0.5,"
              f"fade=t=out:st={T-0.6:.2f}:d=0.6,format=yuv420p")
        run(f'/opt/anaconda3/bin/ffmpeg -y -loop 1 -i "{png}" -i "{aiff}" -t {T} '
            f'-filter_complex "[0:v]{vf}[v]" -map "[v]" -map 1:a '
            f'-c:v h264_videotoolbox -b:v 6M -c:a aac -b:a 192k -ar 44100 '
            f'-pix_fmt yuv420p "{mp4}"')
        clips.append(mp4); print(f"scene {i}: {T}s")

    lst = WORK / "list.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    run(f'/opt/anaconda3/bin/ffmpeg -y -f concat -safe 0 -i "{lst}" '
        f'-c:v h264_videotoolbox -b:v 6M -c:a aac -movflags +faststart "{OUT}"')
    print("SAVED:", OUT)


if __name__ == "__main__":
    main()
