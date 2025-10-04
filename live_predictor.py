# live_predictor.py (Final Corrected Version)

import requests
import pandas as pd
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import gtfs_realtime_pb2

# --- Configuration & Helper Functions ---
# (haversine and fetch_live_bus_data remain the same)
YOUR_ML_API_URL = "http://127.0.0.1:5000/predict"
LIVE_API_URL = "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=A0wBZOxsEVxb2KpmPzEZckmfjtvybBTh"
def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2]); dlon = lon2 - lon1; dlat = lat2 - lat1; a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2; c = 2 * asin(sqrt(a)); r = 6371; return c * r
def fetch_live_bus_data():
    try:
        response = requests.get(LIVE_API_URL, timeout=15); response.raise_for_status(); feed = gtfs_realtime_pb2.FeedMessage(); feed.ParseFromString(response.content)
        data = [{'vehicle_id': e.vehicle.vehicle.id, 'trip_id': e.vehicle.trip.trip_id if e.vehicle.HasField('trip') else None, 'latitude': e.vehicle.position.latitude, 'longitude': e.vehicle.position.longitude} for e in feed.entity if e.HasField('vehicle')]
        return pd.DataFrame(data) if data else None
    except Exception as e: print(f"An error occurred: {e}"); return None

# --- UPGRADED HELPER FUNCTION (THE FIX IS HERE) ---
def get_current_segment(live_lat, live_lon, trip_id, route_map_df):
    """Finds the last and next stop for a specific trip."""
    # This now filters by the specific trip_id, not the whole route_id
    stops_on_trip = route_map_df[route_map_df['trip_id'] == trip_id].sort_values('stop_sequence')
    if stops_on_trip.empty: return None, None
    
    stops_on_trip['distance_to_bus'] = stops_on_trip.apply(lambda row: haversine(live_lat, live_lon, row['stop_lat'], row['stop_lon']), axis=1)
    closest_stop = stops_on_trip.loc[stops_on_trip['distance_to_bus'].idxmin()]
    
    last_stop_df = stops_on_trip[stops_on_trip['stop_sequence'] < closest_stop['stop_sequence']]
    last_stop = closest_stop if last_stop_df.empty else last_stop_df.iloc[-1]
    
    next_stop_df = stops_on_trip[stops_on_trip['stop_sequence'] > last_stop['stop_sequence']]
    next_stop = None if next_stop_df.empty else next_stop_df.iloc[0]
    
    return last_stop, next_stop


# --- Main Application Logic (UPDATED) ---
if __name__ == "__main__":
    TARGET_ROUTE_ID = 30 # You can change this
    print(f"--- Searching for all active buses on Route {TARGET_ROUTE_ID} ---")
    
    print("Loading local GTFS map data...")
    trips_df = pd.read_csv('trips.csv')
    route_map = pd.merge(pd.merge(pd.read_csv('stop_times.csv'), trips_df, on='trip_id'), pd.read_csv('stops.csv'), on='stop_id')
    print("Map data loaded.")

    print("\nFetching live bus data from Delhi Transport API...")
    live_buses_df = fetch_live_bus_data()

    if live_buses_df is not None and not live_buses_df.empty:
        live_buses_with_routes = pd.merge(live_buses_df.dropna(subset=['trip_id']), trips_df, on='trip_id')
        buses_on_target_route = live_buses_with_routes[live_buses_with_routes['route_id'] == TARGET_ROUTE_ID]

        if buses_on_target_route.empty:
            print(f"\nNo active buses found on Route {TARGET_ROUTE_ID} right now.")
        else:
            print(f"\nFound {len(buses_on_target_route)} active bus(es) on Route {TARGET_ROUTE_ID}. Getting ETAs...")
            
            for index, bus_to_track in buses_on_target_route.iterrows():
                bus_lat, bus_lon, bus_trip_id = bus_to_track['latitude'], bus_to_track['longitude'], bus_to_track['trip_id']

                # this line inside  `for` loop, after you find the bus
                print(f"  Live Bus Coordinates: ({bus_lat:.6f}, {bus_lon:.6f})")
                
                # We now pass the specific trip_id to the helper
                last_stop, next_stop = get_current_segment(bus_lat, bus_lon, bus_trip_id, route_map)

                if last_stop is not None and next_stop is not None:
                    # (Feature assembly and prediction logic remains the same)
                    now = datetime.now()
                    features = {
                        'route_id': int(bus_to_track['route_id']), 'stop_id': int(last_stop['stop_id']),
                        'stop_sequence': int(last_stop['stop_sequence']), 'hour_of_day': now.hour,
                        'monday': 1 if now.weekday() == 0 else 0, 'tuesday': 1 if now.weekday() == 1 else 0,
                        'wednesday': 1 if now.weekday() == 2 else 0, 'thursday': 1 if now.weekday() == 3 else 0,
                        'friday': 1 if now.weekday() == 4 else 0, 'saturday': 1 if now.weekday() == 5 else 0,
                        'sunday': 1 if now.weekday() == 6 else 0,
                    }
                    prediction_response = requests.post(YOUR_ML_API_URL, json=features)
                    full_travel_time_prediction = prediction_response.json()['predicted_travel_time_seconds']

                    # The delay calculation will now be correct
                    dep_h, dep_m, dep_s = map(int, last_stop['departure_time'].split(':'))
                    arr_h, arr_m, arr_s = map(int, next_stop['arrival_time'].split(':'))
                    departure_in_seconds = (dep_h * 3600) + (dep_m * 60) + dep_s
                    arrival_in_seconds = (arr_h * 3600) + (arr_m * 60) + arr_s
                    if arrival_in_seconds < departure_in_seconds: arrival_in_seconds += 24 * 3600
                    scheduled_travel_seconds = arrival_in_seconds - departure_in_seconds
                    predicted_delay_seconds = full_travel_time_prediction - scheduled_travel_seconds
                    
                    # The ETA calculation is also the same
                    total_segment_dist = haversine(last_stop['stop_lat'], last_stop['stop_lon'], next_stop['stop_lat'], next_stop['stop_lon'])
                    dist_from_start = haversine(last_stop['stop_lat'], last_stop['stop_lon'], bus_lat, bus_lon)
                    fraction_remaining = 1.0 - (dist_from_start / total_segment_dist) if total_segment_dist > 0 else 0
                    if fraction_remaining < 0: fraction_remaining = 0
                    remaining_time_seconds = full_travel_time_prediction * fraction_remaining
                    eta_time = datetime.now() + timedelta(seconds=remaining_time_seconds)

                    # (The final display is the same)
                    print("\n--- ✅ Live ETA & Delay Prediction ---")
                    print(f"  Bus Vehicle ID:   {bus_to_track['vehicle_id']}")
                    print(f"  From:             {last_stop['stop_name']}")
                    print(f"  To:               {next_stop['stop_name']}")
                    print(f"  Predicted ETA:    {eta_time.strftime('%I:%M:%S %p')}")
                    print("------------------------------------------")
                    if predicted_delay_seconds > 60: print(f"  Status:             Running {predicted_delay_seconds / 60:.1f} minutes LATE")
                    elif predicted_delay_seconds < -60: print(f"  Status:             Running {-predicted_delay_seconds / 60:.1f} minutes EARLY")
                    else: print(f"  Status:             Running On Time")