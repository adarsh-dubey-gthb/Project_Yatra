import joblib
import pandas as pd
import numpy as np
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from math import radians, asin, sqrt, cos, sin
import sys
import traceback
import os

# --- Master Cleaner Function to handle NaN for JSON ---
def replace_nan_with_none(obj):
    if isinstance(obj, dict): return {k: replace_nan_with_none(v) for k, v in obj.items()}
    if isinstance(obj, list): return [replace_nan_with_none(elem) for elem in obj]
    if isinstance(obj, (float, np.floating)) and np.isnan(obj): return None
    return obj

# --- Configuration ---
LIVE_API_URL = "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=A0wBZOxsEVxb2KpmPzEZckmfjtvybBTh"

# --- Initialize the Flask App ---
app = Flask(__name__)

# --- Load Models and Static Data ONCE ---
print("Loading all necessary data...")
try:
    model = joblib.load('bus_eta_model.pkl')
    stops_df = pd.read_csv('stops.csv')
    trips_df = pd.read_csv('trips.csv')
    stop_times_df = pd.read_csv('stop_times.csv')
    routes_df = pd.read_csv('routes.csv')
    route_map = pd.merge(pd.merge(stop_times_df, trips_df, on='trip_id'), stops_df, on='stop_id')
    print("Model and map data loaded successfully!")
except FileNotFoundError as e:
    print(f"FATAL ERROR: Could not load necessary file: {e}. The API will not function correctly.")
    model, stops_df, trips_df, stop_times_df, routes_df, route_map = (None,)*6

# --- Core Helper Functions ---
def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2]); dlon = lon2 - lon1; dlat = lat2 - lat1; a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2; c = 2 * asin(sqrt(a)); r = 6371; return c * r

def find_stops_near_vectorized(coords, radius_km=0.5):
    if stops_df is None: return pd.DataFrame()
    stops_lat_rad = np.radians(stops_df['stop_lat'].values); stops_lon_rad = np.radians(stops_df['stop_lon'].values)
    user_lat_rad = np.radians(coords['lat']); user_lon_rad = np.radians(coords['lon'])
    dlon = stops_lon_rad - user_lon_rad; dlat = stops_lat_rad - user_lat_rad
    a = np.sin(dlat / 2)**2 + np.cos(user_lat_rad) * np.cos(stops_lat_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a)); distances_km = 6371 * c
    return stops_df[distances_km <= radius_km]

def fetch_live_bus_data():
    try:
        sys.path.append(os.path.dirname(os.path.realpath(__file__))); import gtfs_realtime_pb2
        response = requests.get(LIVE_API_URL, timeout=15); response.raise_for_status(); feed = gtfs_realtime_pb2.FeedMessage(); feed.ParseFromString(response.content)
        data = [{'vehicle_id': e.vehicle.vehicle.id, 'trip_id': e.vehicle.trip.trip_id if e.vehicle.HasField('trip') else None, 'latitude': e.vehicle.position.latitude, 'longitude': e.vehicle.position.longitude} for e in feed.entity if e.HasField('vehicle')]
        return pd.DataFrame(data) if data else None
    except Exception as e:
        print(f"An error occurred while fetching live data: {e}", file=sys.stderr); return None

def get_current_segment(live_lat, live_lon, trip_id):
    if route_map is None: return None, None
    stops_on_trip = route_map[route_map['trip_id'] == trip_id].sort_values('stop_sequence')
    if stops_on_trip.empty: return None, None
    stops_on_trip['distance_to_bus'] = stops_on_trip.apply(lambda row: haversine(live_lat, live_lon, row['stop_lat'], row['stop_lon']), axis=1)
    closest_stop = stops_on_trip.loc[stops_on_trip['distance_to_bus'].idxmin()]
    last_stop_df = stops_on_trip[stops_on_trip['stop_sequence'] < closest_stop['stop_sequence']]
    last_stop = closest_stop if last_stop_df.empty else last_stop_df.iloc[-1]
    next_stop_df = stops_on_trip[stops_on_trip['stop_sequence'] > last_stop['stop_sequence']]
    next_stop = None if next_stop_df.empty else next_stop_df.iloc[0]
    return last_stop, next_stop


def find_next_scheduled_departure(trip_id, start_stop_id):
    """Finds the next scheduled departure time for a specific trip and start stop."""
    try:
        now = datetime.now()
        current_time_in_seconds = now.hour * 3600 + now.minute * 60 + now.second
        
        # Find all scheduled stops for this specific trip
        trip_schedule = stop_times_df[stop_times_df['trip_id'] == trip_id]
        
        # Find the specific departure for the start stop on that trip
        departure_row = trip_schedule[trip_schedule['stop_id'] == start_stop_id]
        if departure_row.empty: return None

        for dep_time_str in sorted(departure_row['departure_time'].unique()):
            dep_h, dep_m, dep_s = map(int, dep_time_str.split(':'))
            departure_in_seconds = dep_h * 3600 + dep_m * 60 + dep_s
            if departure_in_seconds >= current_time_in_seconds:
                # Format the time back to a user-friendly string
                return (datetime.min + timedelta(seconds=departure_in_seconds)).strftime('%I:%M %p')
        return None # No more departures for today
    except Exception:
        return None

# --- Logic Functions (Cleaned Up) ---
def plan_trip_logic(start_coords, end_coords):
    nearby_start_stops = find_stops_near_vectorized(start_coords)
    nearby_end_stops = find_stops_near_vectorized(end_coords)
    if nearby_start_stops.empty or nearby_end_stops.empty: return []
    start_segments = route_map[route_map['stop_id'].isin(nearby_start_stops['stop_id'])]
    end_segments = route_map[route_map['stop_id'].isin(nearby_end_stops['stop_id'])]
    merged = pd.merge(start_segments, end_segments, on='trip_id', suffixes=('_start', '_end'))
    valid_trips = merged[merged['stop_sequence_start'] < merged['stop_sequence_end']]
    
    detailed_journeys = {}
    for index, trip in valid_trips.iterrows():
        route_id = trip['route_id_start']
        start_stop_id = trip['stop_id_start']
        end_stop_id = trip['stop_id_end']
        journey_key = f"{route_id}-{start_stop_id}-{end_stop_id}"
        if journey_key not in detailed_journeys:
            route_name_series = routes_df[routes_df['route_id'] == route_id]['route_short_name']
            route_name = route_name_series.iloc[0] if not route_name_series.empty else f"Route {int(route_id)}"
            next_departure = find_next_scheduled_departure(trip['trip_id'], start_stop_id)
            detailed_journeys[journey_key] = {
                'route_id': int(route_id), 'route_name': route_name,
                'start_stop': trip['stop_name_start'], 'end_stop': trip['stop_name_end'],
                'next_scheduled_departure': next_departure
            }
    return list(detailed_journeys.values())

def get_prediction_for_bus(bus_series, destination_stop):
    try:
        bus_lat, bus_lon, bus_trip_id = bus_series['latitude'], bus_series['longitude'], bus_series['trip_id']
        stops_on_trip = route_map[route_map['trip_id'] == bus_trip_id].sort_values('stop_sequence')
        if stops_on_trip.empty: return None
        last_stop, next_stop = get_current_segment(bus_lat, bus_lon, bus_trip_id)
        if last_stop is None or next_stop is None: return None
        if destination_stop.iloc[0]['stop_sequence'] <= last_stop['stop_sequence']: return None
        now = datetime.now()
        base_features = {'route_id': int(bus_series['route_id']), 'hour_of_day': now.hour, 'monday': 1 if now.weekday() == 0 else 0, 'tuesday': 1 if now.weekday() == 1 else 0, 'wednesday': 1 if now.weekday() == 2 else 0, 'thursday': 1 if now.weekday() == 3 else 0, 'friday': 1 if now.weekday() == 4 else 0, 'saturday': 1 if now.weekday() == 5 else 0, 'sunday': 1 if now.weekday() == 6 else 0}
        
        current_features = base_features.copy()
        current_features['stop_id'] = int(last_stop['stop_id']); current_features['stop_sequence'] = int(last_stop['stop_sequence'])
        features_df = pd.DataFrame(current_features, index=[0]); features_df['route_id'] = features_df['route_id'].astype('category'); features_df['stop_id'] = features_df['stop_id'].astype('category')
        full_travel_time_prediction = model.predict(features_df)[0]
        
        total_segment_dist = haversine(last_stop['stop_lat'], last_stop['stop_lon'], next_stop['stop_lat'], next_stop['stop_lon'])
        dist_from_start = haversine(last_stop['stop_lat'], last_stop['stop_lon'], bus_lat, bus_lon)
        fraction_remaining = 1.0 - (dist_from_start / total_segment_dist) if total_segment_dist > 0 else 0
        if fraction_remaining < 0: fraction_remaining = 0
        remaining_time_for_current_segment = full_travel_time_prediction * fraction_remaining

        total_future_time = 0
        future_stops = stops_on_trip[(stops_on_trip['stop_sequence'] > last_stop['stop_sequence']) & (stops_on_trip['stop_sequence'] <= destination_stop.iloc[0]['stop_sequence'])]
        start_of_segment = last_stop
        for index, end_of_segment in future_stops.iterrows():
            future_features = base_features.copy()
            future_features['stop_id'] = int(start_of_segment['stop_id']); future_features['stop_sequence'] = int(start_of_segment['stop_sequence'])
            future_features_df = pd.DataFrame(future_features, index=[0]); future_features_df['route_id'] = future_features_df['route_id'].astype('category'); future_features_df['stop_id'] = future_features_df['stop_id'].astype('category')
            segment_prediction = model.predict(future_features_df)[0]
            total_future_time += segment_prediction
            start_of_segment = end_of_segment
            
        total_predicted_seconds = remaining_time_for_current_segment + total_future_time
        eta_time = datetime.now() + timedelta(seconds=total_predicted_seconds)
        
        return {"vehicle_id": bus_series['vehicle_id'], "from_stop": last_stop['stop_name'], "to_stop": next_stop['stop_name'], "final_destination_stop": destination_stop.iloc[0]['stop_name'], "final_eta": eta_time.strftime('%I:%M:%S %p')}
    except Exception:
        return None

def get_delay_for_bus_segment(bus_series):
    try:
        bus_lat, bus_lon, bus_trip_id = bus_series['latitude'], bus_series['longitude'], bus_series['trip_id']
        last_stop, next_stop = get_current_segment(bus_lat, bus_lon, bus_trip_id)
        if last_stop is None or next_stop is None: return None
        now = datetime.now()
        features = {'route_id': int(bus_series['route_id']), 'stop_id': int(last_stop['stop_id']),'stop_sequence': int(last_stop['stop_sequence']), 'hour_of_day': now.hour,'monday': 1 if now.weekday() == 0 else 0, 'tuesday': 1 if now.weekday() == 1 else 0,'wednesday': 1 if now.weekday() == 2 else 0, 'thursday': 1 if now.weekday() == 3 else 0,'friday': 1 if now.weekday() == 4 else 0, 'saturday': 1 if now.weekday() == 5 else 0,'sunday': 1 if now.weekday() == 6 else 0}
        features_df = pd.DataFrame(features, index=[0]); features_df['route_id'] = features_df['route_id'].astype('category'); features_df['stop_id'] = features_df['stop_id'].astype('category')
        full_travel_time_prediction = model.predict(features_df)[0]
        dep_h, dep_m, dep_s = map(int, last_stop['departure_time'].split(':')); arr_h, arr_m, arr_s = map(int, next_stop['arrival_time'].split(':'))
        departure_in_seconds = (dep_h * 3600) + (dep_m * 60) + dep_s; arrival_in_seconds = (arr_h * 3600) + (arr_m * 60) + arr_s
        if arrival_in_seconds < departure_in_seconds: arrival_in_seconds += 24 * 3600
        scheduled_travel_seconds = arrival_in_seconds - departure_in_seconds
        return full_travel_time_prediction - scheduled_travel_seconds
    except Exception:
        return None

# --- API Endpoints ---
@app.route('/get-system-stats', methods=['GET'])
def get_system_stats():
    if model is None: return jsonify({'error': 'Server not ready'}), 500
    try:
        live_buses_df = fetch_live_bus_data()
        if live_buses_df is None or live_buses_df.empty:
            return jsonify({'active_buses_count': 0, 'avg_delay_minutes': 'N/A', 'on_time_percentage': 'N/A', 'routes_covered_count': 0, 'last_updated': datetime.now().isoformat()})
        active_buses_count = len(live_buses_df)
        live_buses_with_routes = pd.merge(live_buses_df.dropna(subset=['trip_id']), trips_df, on='trip_id')
        routes_covered_count = live_buses_with_routes['route_id'].nunique()
        delay_list = [delay for bus in live_buses_with_routes.to_dict('records') if (delay := get_delay_for_bus_segment(bus)) is not None]
        avg_delay_minutes = np.mean(delay_list) / 60 if delay_list else 0
        on_time_percentage = (sum(1 for delay in delay_list if abs(delay) <= 300) / len(delay_list)) * 100 if delay_list else 100
        result = {'active_buses_count': active_buses_count, 'avg_delay_minutes': avg_delay_minutes, 'on_time_percentage': on_time_percentage, 'routes_covered_count': routes_covered_count, 'last_updated': datetime.now().isoformat()}
        return jsonify(replace_nan_with_none(result))
    except Exception as e:
        traceback.print_exc(); return jsonify({'error': str(e)}), 500

@app.route('/get-realtime-trip-plan', methods=['POST'])
def get_realtime_trip_plan():
    if model is None: return jsonify({'error': 'Server not ready'}), 500
    try:
        data = request.get_json(); start_coords = data['start_coords']; end_coords = data['end_coords']
        possible_routes_details = plan_trip_logic(start_coords, end_coords)
        live_buses_df = fetch_live_bus_data()
        if live_buses_df is None or live_buses_df.empty:
            return jsonify({ 'trip_summary': {'possible_routes': possible_routes_details, 'active_routes_in_city': []}, 'final_plan': {}, 'message': 'No buses are currently live.' })
        live_buses_with_routes = pd.merge(live_buses_df.dropna(subset=['trip_id']), trips_df, on='trip_id')
        active_route_ids = live_buses_with_routes['route_id'].unique()
        active_routes_details = routes_df[routes_df['route_id'].isin(active_route_ids)][['route_id', 'route_short_name']].to_dict('records')
        possible_route_ids = [r['route_id'] for r in possible_routes_details]
        final_route_ids = sorted(list(set(possible_route_ids) & set(active_route_ids)))
        
        nearby_end_stops = find_stops_near_vectorized(end_coords)
        if nearby_end_stops.empty: return jsonify({'message': 'Could not find any bus stops near your destination.'})
        destination_stop = nearby_end_stops.iloc[[0]]

        final_trip_plan = {}
        for route_id in final_route_ids:
            buses_on_this_route = live_buses_with_routes[live_buses_with_routes['route_id'] == route_id]
            bus_details_list = [details for bus in buses_on_this_route.to_dict('records') if (details := get_prediction_for_bus(bus, destination_stop)) is not None]
            final_trip_plan[f"route_{route_id}"] = bus_details_list
        final_response = {'trip_summary': {'possible_routes': possible_routes_details, 'active_routes_in_city': active_routes_details}, 'final_plan': final_trip_plan}
        return jsonify(replace_nan_with_none(final_response))
    except Exception as e:
        traceback.print_exc(); return jsonify({'error': str(e)}), 500

# --- Main execution block ---
if __name__ == '__main__':
    app.run(port=5000, debug=True)
