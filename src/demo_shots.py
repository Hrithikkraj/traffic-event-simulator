"""Capture clean, high-res screenshots of each dashboard state for the demo video.

Prereq: app running at http://localhost:8501
Run:    /opt/anaconda3/bin/python src/demo_shots.py  -> outputs/demo/shots/*.png
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
OUT = Path("outputs/demo/shots"); OUT.mkdir(parents=True, exist_ok=True)


def shot(pg, name):
    pg.screenshot(path=str(OUT / name))
    print("shot:", name)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.goto(URL, wait_until="domcontentloaded")
        pg.wait_for_selector("text=Gridlock", timeout=120000)
        time.sleep(8)
        tabs = pg.get_by_role("tab")

        # 1-2) Simulator — inject a VIP movement (Critical)
        tabs.nth(0).click(); time.sleep(2)
        try:
            pg.locator('[data-testid="stSelectbox"]').first.click(); time.sleep(1)
            pg.get_by_text("vip_movement", exact=True).click(); time.sleep(5)
        except Exception as e:
            print("sim select skipped:", str(e)[:80])
        pg.evaluate("window.scrollTo(0,0)"); time.sleep(1); shot(pg, "1_sim.png")
        pg.evaluate("window.scrollTo(0,560)"); time.sleep(2); shot(pg, "2_simmap.png")

        # 3) City Risk Map
        tabs.nth(1).click(); time.sleep(4); pg.evaluate("window.scrollTo(0,170)"); time.sleep(3)
        shot(pg, "3_riskmap.png")

        # 4) Surge-Day Replay
        tabs.nth(2).click(); time.sleep(4); pg.evaluate("window.scrollTo(0,140)"); time.sleep(2)
        shot(pg, "4_surge.png")

        # 5) Forecast & Hotspots
        tabs.nth(3).click(); time.sleep(4); pg.evaluate("window.scrollTo(0,150)"); time.sleep(2)
        shot(pg, "5_forecast.png")

        # 6) Learning Loop
        tabs.nth(4).click(); time.sleep(4); pg.evaluate("window.scrollTo(0,150)"); time.sleep(2)
        shot(pg, "6_learning.png")

        ctx.close(); b.close()
    print("done")


if __name__ == "__main__":
    main()
