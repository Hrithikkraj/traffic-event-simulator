import requests
import polyline
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- PASTE YOUR MAPMYINDIA STATIC KEY HERE ---
MAPMYINDIA_API_KEY = "qjcehglokmufbwcnxomavzejpkgmhleqeitu"

def get_diversion_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    """
    Calls Mappls Routing API to get the optimal driving route.
    """
    logging.info(f"Calculating diversion route via Mappls: ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
    
    # Mappls uses Longitude,Latitude format in the URL
    url = f"https://apis.mappls.com/advancedmaps/v1/{MAPMYINDIA_API_KEY}/route_adv/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('routes') and len(data['routes']) > 0:
            # Decode the polyline into coordinates
            encoded_geometry = data['routes'][0]['geometry']
            decoded_coordinates = polyline.decode(encoded_geometry)
            
            # Pydeck requires [longitude, latitude] for drawing lines
            route_coords = [[lon, lat] for lat, lon in decoded_coordinates]
            
            duration_min = data['routes'][0]['duration'] / 60
            distance_km = data['routes'][0]['distance'] / 1000
            
            logging.info(f"Route found: {distance_km:.1f} km, {duration_min:.1f} mins")
            return route_coords, duration_min, distance_km
    else:
        logging.error(f"Mappls API Failed. Status: {response.status_code}, Response: {response.text}")
        
    return None, 0, 0