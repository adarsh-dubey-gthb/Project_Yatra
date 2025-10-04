# find_active_routes.py

import pandas as pd
# Make sure to copy your fetch_live_bus_data function into this file
from live_predictor import fetch_live_bus_data 

print("Finding all currently active routes...")

# Load the trips file to map trip_id to route_id
trips_df = pd.read_csv('trips.csv')

# Get all live bus data
live_buses_df = fetch_live_bus_data()

if live_buses_df is not None and not live_buses_df.empty:
    # Merge with trips to find the route for each bus
    live_buses_with_routes = pd.merge(live_buses_df.dropna(subset=['trip_id']), trips_df, on='trip_id')
    
    # Get a list of unique, active route IDs
    active_routes = live_buses_with_routes['route_id'].unique()
    
    print("\n--- ✅ Found the following active routes ---")
    print(sorted(active_routes))
else:
    print("Could not retrieve any live data at the moment.")