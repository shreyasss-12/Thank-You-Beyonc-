import requests
import json
import webbrowser
import os
import urllib.parse
import subprocess
import time

# Function to get latitude & longitude from an address
def get_coordinates(address):
 
    encoded_address = urllib.parse.quote(address)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json"
    headers = {"User-Agent": "YourApp/1.0"}  # Required by Nominatim API
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  

        data = response.json()
        if data:
            return data[0]["lat"], data[0]["lon"]
        else:
            print(f"❌ Location not found: {address}")
            exit()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching coordinates: {e}")
        exit()

# Function to format time
def format_time(time_in_ms):
    total_minutes = time_in_ms / 60000  # Convert ms to minutes
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    
    if hours > 0:
        return f"{hours} hr {minutes} min"
    else:
        return f"{minutes} min"

# Function to format distance
def format_distance(distance_in_meters):
    if distance_in_meters >= 1000:
        distance_in_km = distance_in_meters / 1000
        return f"{distance_in_km:.1f} km"
    else:
        return f"{int(distance_in_meters)} m"

# Get user input for source & destination
source_address = input("Enter source location: ").strip()
destination_address = input("Enter destination location: ").strip()

# Get optional via points
via_points = []
while True:
    via_prompt = "Enter a via point (or press Enter to continue): "
    via_address = input(via_prompt).strip()
    if not via_address:
        break
    via_points.append(via_address)

print(f"✅ Planning route with {len(via_points)} intermediate stops")

# Convert addresses to coordinates
source_lat, source_lon = get_coordinates(source_address)
dest_lat, dest_lon = get_coordinates(destination_address)

# Process via points
via_coords = []
via_addresses = []
if via_points:
    for i, via_address in enumerate(via_points):
        via_lat, via_lon = get_coordinates(via_address)
        via_coords.append((via_lat, via_lon))
        via_addresses.append(via_address)
        print(f" Via point {i+1}: {via_address} → {via_lat}, {via_lon}")

print(f" Source: {source_address} → {source_lat}, {source_lon}")
print(f" Destination: {destination_address} → {dest_lat}, {dest_lon}")

# api
GRAPHHOPPER_API_KEY = "90014c1a-114f-4819-a650-e68fae62d385"

# Build the GraphHopper URL with all points
url_parts = [f"https://graphhopper.com/api/1/route?point={source_lat},{source_lon}"]

# Add all via points to the URL
for via_lat, via_lon in via_coords:
    url_parts.append(f"&point={via_lat},{via_lon}")

# Add the destination
url_parts.append(f"&point={dest_lat},{dest_lon}")

url_parts.append("&profile=car&locale=en&calc_points=true&points_encoded=false")
url_parts.append(f"&key={GRAPHHOPPER_API_KEY}")

# Join all parts
GRAPHHOPPER_URL = "".join(url_parts)

# Send GET request to GraphHopper
try:
    response = requests.get(GRAPHHOPPER_URL)
    response.raise_for_status() 
    route_data = response.json()

    # Extract route path (list of lat/lon points)
    points = route_data["paths"][0]["points"]["coordinates"]
    
    # Extract distance (in meters) and time (in milliseconds)
    distance = route_data["paths"][0]["distance"]
    time_ms = route_data["paths"][0]["time"]
    
    # Format distance and time for display
    formatted_distance = format_distance(distance)
    formatted_time = format_time(time_ms)
    
    print(f" Total Distance: {formatted_distance}")
    print(f" Total Estimated travel time: {formatted_time}")

    # Extract segment information
    segments = []
    
    # Check if there are instructions (turn-by-turn) that we can use to extract segments
    if "instructions" in route_data["paths"][0]:
        instructions = route_data["paths"][0]["instructions"]
        # Process segments
        current_segment = {"type": "segment", "start_index": 0}
        
        for i, instruction in enumerate(instructions):
            if instruction.get("sign") == 4:  #  indicates arrival at via point
                current_segment["end_index"] = instruction["interval"][0]
                segments.append(current_segment)
                current_segment = {"type": "segment", "start_index": instruction["interval"][0]}
        
        if current_segment:
            current_segment["end_index"] = len(points) - 1
            segments.append(current_segment)
    
    # Convert to Leaflet-friendly format ([lat, lon] instead of [lon, lat])
    leaflet_points = [[point[1], point[0]] for point in points]

    # Get the current script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Save the route data
    route_path = os.path.join(script_dir, "route.json")
    with open(route_path, "w") as file:
        json.dump(leaflet_points, file)
    
    # Prepare waypoints for the JSON file
    waypoints = [
        {
            "type": "source",
            "address": source_address,
            "coordinates": [float(source_lat), float(source_lon)]
        }
    ]
    
    # Add via points
    for i, (address, coords) in enumerate(zip(via_addresses, via_coords)):
        waypoints.append({
            "type": "via",
            "address": address,
            "coordinates": [float(coords[0]), float(coords[1])]
        })
    
    # Add destination
    waypoints.append({
        "type": "destination",
        "address": destination_address,
        "coordinates": [float(dest_lat), float(dest_lon)]
    })
    
    # Save the location and route info data
    locations_data = {
        "source": {
            "address": source_address,
            "coordinates": [float(source_lat), float(source_lon)]
        },
        "destination": {
            "address": destination_address,
            "coordinates": [float(dest_lat), float(dest_lon)]
        },
        "via_points": [
            {
                "address": address,
                "coordinates": [float(coords[0]), float(coords[1])]
            } for address, coords in zip(via_addresses, via_coords)
        ],
        "waypoints": waypoints,
        "route_info": {
            "distance": distance,
            "distance_text": formatted_distance,
            "time": time_ms,
            "time_text": formatted_time,
            "segments": segments
        }
    }
    
    locations_path = os.path.join(script_dir, "locations.json")
    with open(locations_path, "w") as file:
        json.dump(locations_data, file)

    print(" Route data saved successfully!")

    # Start the server
    server_script = os.path.join(script_dir, "server.py")
    
    # Check if the server script exists
    if os.path.exists(server_script):
        print(" Starting web server...")

        subprocess.Popen(["python", server_script])
    else:
        print(" Server script not found. Opening HTML file directly.")
        maps_path = os.path.join(script_dir, "maps.html")
        if os.path.exists(maps_path):
            webbrowser.open(f"file://{maps_path}")
        else:
            print(f" Warning: Could not find {maps_path}")
            print("Please ensure 'maps.html' exists in the same folder as this script.")
            webbrowser.open("maps.html")

except requests.exceptions.RequestException as e:
    print(f" Error fetching route: {e}")
    exit()
except KeyError as e:
    print(f" Error processing route data: {e}")
    print("This may indicate an issue with the GraphHopper API response.")
    exit()
except Exception as e:
    print(f" Unexpected error: {e}")
    exit()