"""
API Services Module
==================
Contains all service functions: route, optimization, fuel, utilities.
"""

import requests
import polyline
from django.conf import settings
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
import csv
import pandas as pd


# ============================================================================
# Utility Functions (route_utils)
# ============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in miles between two lat/lon points"""
    R = 3958.8  # Earth radius in miles
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def sample_route_points(route_points, max_points=120):
    """Reduce route points for performance"""
    if len(route_points) <= max_points:
        return route_points

    step = max(1, len(route_points) // max_points)
    sampled = route_points[::step]

    if sampled[0] != route_points[0]:
        sampled.insert(0, route_points[0])
    if sampled[-1] != route_points[-1]:
        sampled.append(route_points[-1])

    return sampled


def get_bounding_box(route_points, padding=0.5):
    """Return min/max lat/lon with padding for fast pre-filter"""
    lats = [p[0] for p in route_points]
    lons = [p[1] for p in route_points]

    return {
        'min_lat': min(lats) - padding,
        'max_lat': max(lats) + padding,
        'min_lon': min(lons) - padding,
        'max_lon': max(lons) + padding,
    }


# ============================================================================
# City Coordinates Functions
# ============================================================================

CITY_COORDINATES = {}

def load_city_coordinates():
    global CITY_COORDINATES
    if CITY_COORDINATES:
        return

    csv_path = Path(__file__).parent.parent / "data" / "uscities.csv"
    
    if csv_path.exists():
        for encoding in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
            try:
                with open(csv_path, 'r', encoding=encoding, errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        city = row.get('city', '').strip().title()
                        state = row.get('state_id', '').strip().upper()
                        try:
                            lat = float(row.get('lat', 0))
                            lng = float(row.get('lng', 0))
                            if city and lat and lng and lat != 0 and lng != 0:
                                CITY_COORDINATES[city] = (lat, lng)
                                CITY_COORDINATES[f"{city}, {state}"] = (lat, lng)
                        except:
                            continue
                print(f"✅ Loaded city coordinates from uscities.csv using {encoding}")
                return
            except:
                continue

    manual_map = {
        "Big Cabin": (36.5340, -95.2210),
        "Tomah": (43.9841, -90.5040),
        "Gila Bend": (32.9478, -112.7247),
        "Fort Smith": (35.3859, -94.3985),
        "Columbia": (40.8875, -74.0460),
    }
    CITY_COORDINATES.update(manual_map)
    print("✅ Loaded manual city coordinates")


def get_city_coords(city: str, state: str = None):
    """Get coordinates for a city - no API calls"""
    load_city_coordinates()
    if not city:
        return None

    city_clean = city.strip().title()

    if state:
        key = f"{city_clean}, {state.strip().upper()}"
        if key in CITY_COORDINATES:
            return CITY_COORDINATES[key]

    if city_clean in CITY_COORDINATES:
        return CITY_COORDINATES[city_clean]

    return None


# ============================================================================
# Route Service Functions
# ============================================================================

def geocode_location(location: str):
    """
    Convert location string to (lon, lat) coordinates using Nominatim (free).
    Returns (lon, lat) tuple or None if not found.
    """
    location = location.strip()
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": location,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "FuelOptimizer/1.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]['lon']), float(data[0]['lat'])
    except Exception:
        pass
    
    return None


def get_route_coordinates(start: str, end: str):
    """
    Returns list of (latitude, longitude) tuples along the route.
    Uses geocoding to convert location names to coordinates.
    """
    start_coords = geocode_location(start)
    end_coords = geocode_location(end)

    location_map = {
        "New York, NY": (-74.0060, 40.7128),
        "Chicago, IL": (-87.6298, 41.8781),
        "Texas": (-99.9018, 31.9686),
        "California": (-119.4179, 36.7783),
    }
    
    if not start_coords:
        start_coords = location_map.get(start)
    if not end_coords:
        end_coords = location_map.get(end)

    if not start_coords or not end_coords:
        raise ValueError(f"Invalid locations: {start} or {end}")

    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [start_coords, end_coords],
        "instructions": False,
        "geometry": True,
        "geometry_simplify": "false",
        "units": "mi"
    }

    response = requests.post(url, json=body, headers=headers, timeout=15)

    if response.status_code != 200:
        raise Exception(f"Routing API failed: {response.status_code} - {response.text}")

    data = response.json()

    if "routes" not in data or not data["routes"]:
        raise Exception("No route found")

    geometry = data["routes"][0]["geometry"]
    route_points = polyline.decode(geometry)

    return route_points


# ============================================================================
# Fuel Data
# ============================================================================

df = pd.read_csv(str(Path(__file__).parent.parent / "data" / "fuel_prices.csv"))


# ============================================================================
# Optimizer Functions
# ============================================================================

from api.models import FuelStation

MAX_RANGE_MILES = 500
MPG = 10.0
THRESHOLD_MILES = 15.0
LOOKAHEAD_MILES = 150
MIN_FUEL_BUFFER = 50


def optimize_fuel_stops(start: str, end: str, route_points: list) -> dict:
    """
    Single-pass fuel optimization.
    
    Returns:
        dict with route_summary, fuel_stops, total_cost, remaining_fuel_at_destination
    """
    if not route_points or len(route_points) < 2:
        return _empty_result()
    
    sampled_points = sample_route_points(route_points, max_points=150)
    candidates = _get_candidate_stations(sampled_points)
    
    if not candidates:
        return _empty_result()
    
    total_distance = _calculate_total_distance(sampled_points)
    
    fuel_stops, total_cost, remaining_fuel = _run_simulation(
        sampled_points, candidates
    )
    
    fuel_stops_with_alts = _add_alternatives(fuel_stops, candidates)
    
    return {
        "route_summary": {
            "total_distance": round(total_distance, 2),
            "fuel_capacity": MAX_RANGE_MILES,
            "mpg": MPG,
            "fuel_required_total": round(total_distance / MPG, 2)
        },
        "fuel_stops": fuel_stops_with_alts,
        "total_cost": round(total_cost, 2),
        "remaining_fuel_at_destination": round(remaining_fuel, 2)
    }


def _add_alternatives(fuel_stops: list, candidates: list) -> list:
    """Add 2-3 nearby alternative stations for each fuel stop."""
    ALT_RADIUS_MILES = 15.0
    MAX_ALTERNATIVES = 3
    
    for stop in fuel_stops:
        stop_lat = stop["location"][0]
        stop_lon = stop["location"][1]
        stop_price = stop["price"]
        
        alternatives = []
        for cand in candidates:
            if cand['station'].retail_price == stop_price and cand['station'].name == stop["station_name"]:
                continue
            
            dist = haversine_distance(
                stop_lat, stop_lon,
                cand['station'].latitude, cand['station'].longitude
            )
            
            if dist <= ALT_RADIUS_MILES:
                alternatives.append({
                    "name": cand['station'].name,
                    "city": cand['station'].city,
                    "state": cand['station'].state,
                    "price": round(cand['station'].retail_price, 3),
                    "distance_from_stop": round(dist, 2)
                })
        
        alternatives.sort(key=lambda x: x["price"])
        stop["alternatives"] = alternatives[:MAX_ALTERNATIVES]
    
    return fuel_stops


def _empty_result() -> dict:
    return {
        "route_summary": {
            "total_distance": 0.0,
            "fuel_capacity": MAX_RANGE_MILES,
            "mpg": MPG,
            "fuel_required_total": 0.0
        },
        "fuel_stops": [],
        "total_cost": 0.0,
        "remaining_fuel_at_destination": 0.0
    }


def _get_candidate_stations(route_points: list) -> list:
    """Filter stations using bounding box + haversine."""
    bbox = get_bounding_box(route_points, padding=1.5)
    
    stations_qs = FuelStation.objects.filter(
        latitude__gte=bbox['min_lat'],
        latitude__lte=bbox['max_lat'],
        longitude__gte=bbox['min_lon'],
        longitude__lte=bbox['max_lon']
    ).order_by('retail_price')
    
    candidates = []
    step = max(1, len(route_points) // 30)
    
    for station in stations_qs:
        min_dist = float('inf')
        route_index = -1
        
        for idx in range(0, len(route_points), step):
            dist = haversine_distance(
                route_points[idx][0], route_points[idx][1],
                station.latitude, station.longitude
            )
            if dist < min_dist:
                min_dist = dist
                route_index = idx
        
        if min_dist <= THRESHOLD_MILES:
            candidates.append({
                'station': station,
                'route_index': route_index,
                'dist_to_route': min_dist
            })
    
    candidates.sort(key=lambda x: x['station'].retail_price)
    return candidates


def _calculate_total_distance(route_points: list) -> float:
    """Calculate total route distance."""
    total = 0.0
    for i in range(len(route_points) - 1):
        total += haversine_distance(
            route_points[i][0], route_points[i][1],
            route_points[i+1][0], route_points[i+1][1]
        )
    return total


def _run_simulation(route_points: list, candidates: list) -> tuple:
    """Single-pass simulation: track fuel, make refuel decisions, return results."""
    fuel_stops = []
    total_cost = 0.0
    
    current_fuel = MAX_RANGE_MILES
    distance_from_start = 0.0
    current_route_idx = 0
    
    for i in range(len(route_points) - 1):
        curr = route_points[i]
        next_p = route_points[i + 1]
        
        segment_dist = haversine_distance(curr[0], curr[1], next_p[0], next_p[1])
        current_fuel -= segment_dist
        distance_from_start += segment_dist
        
        need_refuel = (
            current_fuel <= MIN_FUEL_BUFFER or
            i >= len(route_points) - 3
        )
        
        if need_refuel:
            current_pos = (curr[0], curr[1])
            fuel_before = current_fuel
            
            reachable = _find_reachable_ahead(current_pos, current_fuel, candidates, current_route_idx)
            
            if not reachable:
                nearest = _find_nearest(current_pos, candidates)
                reachable = [nearest] if nearest else []
            
            if reachable:
                best = min(reachable, key=lambda x: x['station'].retail_price)
                best_price = best['station'].retail_price
                
                cheaper = _find_cheaper_ahead(
                    current_pos, current_fuel, candidates, 
                    current_route_idx, best_price
                )
                
                if cheaper and _can_reach(current_pos, current_fuel, cheaper):
                    continue
                else:
                    station = best['station']
                    gallons = (MAX_RANGE_MILES - current_fuel) / MPG
                    cost = gallons * station.retail_price
                    
                    fuel_stops.append({
                        "station_name": station.name,
                        "city": station.city,
                        "state": station.state,
                        "price": round(station.retail_price, 3),
                        "distance_from_start": round(distance_from_start, 2),
                        "fuel_left_before": round(fuel_before, 2),
                        "gallons_filled": round(gallons, 2),
                        "cost": round(cost, 2),
                        "location": [station.latitude, station.longitude],
                        "reason": _get_refuel_reason(cheaper, best_price)
                    })
                    
                    total_cost += cost
                    current_fuel = MAX_RANGE_MILES
                    current_route_idx = i
    
    total_distance = _calculate_total_distance(route_points)
    if not fuel_stops and total_distance > 0:
        cheapest = min(candidates, key=lambda x: x['station'].retail_price)
        station = cheapest['station']
        gallons = total_distance / MPG
        cost = gallons * station.retail_price
        
        fuel_stops.append({
            "station_name": station.name,
            "city": station.city,
            "state": station.state,
            "price": round(station.retail_price, 3),
            "distance_from_start": 0.0,
            "fuel_left_before": MAX_RANGE_MILES,
            "gallons_filled": round(gallons, 2),
            "cost": round(cost, 2),
            "location": [station.latitude, station.longitude],
            "reason": "Short trip - single refuel"
        })
        total_cost = cost
        current_fuel = 0.0
    
    return fuel_stops, total_cost, current_fuel


def _get_refuel_reason(cheaper_ahead: dict, current_price: float) -> str:
    """Generate human-readable reason for refuel decision."""
    if cheaper_ahead:
        return f"Cheapest reachable. Found cheaper station ahead but not reachable in time."
    return "Cheapest reachable station - no better option ahead"


def _find_reachable_ahead(current_pos: tuple, current_fuel: float,
                          candidates: list, current_idx: int) -> list:
    """Find stations reachable with current fuel that are ahead."""
    max_travel = max(0, current_fuel - MIN_FUEL_BUFFER)
    reachable = []
    
    for cand in candidates:
        if cand['route_index'] < current_idx - 5:
            continue
        
        dist = haversine_distance(
            current_pos[0], current_pos[1],
            cand['station'].latitude, cand['station'].longitude
        )
        
        if dist <= max_travel:
            reachable.append(cand)
    
    return reachable


def _find_cheaper_ahead(current_pos: tuple, current_fuel: float,
                         candidates: list, current_idx: int, 
                         current_price: float) -> dict:
    """Find cheapest station ahead within lookahead range."""
    max_search = current_fuel + LOOKAHEAD_MILES
    cheapest = None
    
    for cand in candidates:
        if cand['route_index'] <= current_idx:
            continue
        
        dist = haversine_distance(
            current_pos[0], current_pos[1],
            cand['station'].latitude, cand['station'].longitude
        )
        
        if dist > max_search:
            continue
        
        if cand['station'].retail_price < current_price:
            if cheapest is None or cand['station'].retail_price < cheapest['station'].retail_price:
                cheapest = cand
    
    return cheapest


def _can_reach(current_pos: tuple, current_fuel: float, 
               station_cand: dict) -> bool:
    """Check if station is reachable while maintaining safety buffer."""
    dist = haversine_distance(
        current_pos[0], current_pos[1],
        station_cand['station'].latitude, station_cand['station'].longitude
    )
    return dist <= (current_fuel - MIN_FUEL_BUFFER)


def _find_nearest(current_pos: tuple, candidates: list) -> dict:
    """Find nearest station for edge case."""
    if not candidates:
        return None
    
    nearest = None
    min_dist = float('inf')
    
    for cand in candidates:
        dist = haversine_distance(
            current_pos[0], current_pos[1],
            cand['station'].latitude, cand['station'].longitude
        )
        if dist < min_dist:
            min_dist = dist
            nearest = cand
    
    return nearest
