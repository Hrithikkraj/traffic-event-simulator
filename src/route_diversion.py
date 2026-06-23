"""Real road-network diversion routing (merged from main, de-risked).

main hard-coded a Mappls API key in the repo. This version uses the keyless
public OSRM server, reads an override endpoint from env if provided, and
degrades gracefully to None (caller falls back to the corridor heuristic) so
the demo never breaks offline.

  export OSRM_URL=...   # optional self-hosted/alternate OSRM base
"""
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

OSRM_BASE = os.environ.get("OSRM_URL", "https://router.project-osrm.org")


def get_diversion_route(start_lat, start_lon, end_lat, end_lon, timeout=6):
    """Return (route_coords[[lon,lat],...], duration_min, distance_km) or (None,0,0)."""
    try:
        import requests
        url = (f"{OSRM_BASE}/route/v1/driving/"
               f"{start_lon},{start_lat};{end_lon},{end_lat}"
               f"?overview=full&geometries=geojson")
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if data.get("routes"):
                rt = data["routes"][0]
                coords = rt["geometry"]["coordinates"]          # already [lon,lat]
                return coords, rt["duration"] / 60.0, rt["distance"] / 1000.0
        logging.warning(f"OSRM returned {r.status_code}; falling back to heuristic.")
    except Exception as e:                                       # offline / blocked / timeout
        logging.warning(f"Routing unavailable ({type(e).__name__}); falling back to heuristic.")
    return None, 0.0, 0.0


if __name__ == "__main__":
    # KR Puram -> city centre (works only with network access)
    coords, mins, km = get_diversion_route(13.0100, 77.6950, 12.9781, 77.5695)
    print(f"route points: {len(coords) if coords else 0}, {km:.1f} km, {mins:.1f} min"
          if coords else "no route (offline) — caller uses corridor heuristic")
