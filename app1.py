from flask import Flask, request, jsonify
import numpy as np
import math
from datetime import datetime

app = Flask(__name__)

# Simple in-memory data storage
drivers = {}  # driver_id -> driver_info
riders = {}   # rider_id -> rider_info
active_rides = {}  # ride_id -> ride_info

# Grid size (city area divided into cells)
GRID_SIZE = 10  # 10x10 grid for simplicity
MAX_SHARING_RADIUS = 2  # km

# Track demand in each grid cell
demand_grid = np.zeros((GRID_SIZE, GRID_SIZE))
# Track high traffic areas
traffic_hotspots = np.zeros((GRID_SIZE, GRID_SIZE), dtype=bool)

def calculate_distance(pos1, pos2):
    """Calculate distance between two lat/lng points in km"""
    # Simple Euclidean distance for simulation
    # In production, use haversine formula for GPS coordinates
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def update_traffic_hotspots():
    """Identify high traffic areas based on demand"""
    global traffic_hotspots
    threshold = np.percentile(demand_grid, 80)  # Top 20% are hotspots
    traffic_hotspots = demand_grid > threshold

# Driver APIs
@app.route('/api/driver/register', methods=['POST'])
def register_driver():
    data = request.json
    driver_id = data.get('driver_id')
    current_location = data.get('location')  # [lat, lng]
    
    drivers[driver_id] = {
        'location': current_location,
        'status': 'available',
        'points': 0,
        'level': 1
    }
    
    return jsonify({'status': 'success'})

@app.route('/api/driver/update-location', methods=['POST'])
def update_driver_location():
    data = request.json
    driver_id = data.get('driver_id')
    new_location = data.get('location')
    
    if driver_id in drivers:
        drivers[driver_id]['location'] = new_location
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Driver not found'}), 404

# Rider APIs
@app.route('/api/rider/request-ride', methods=['POST'])
def request_ride():
    data = request.json
    rider_id = data.get('rider_id')
    pickup_location = data.get('pickup')
    destination = data.get('destination')
    
    # Create rider entry
    riders[rider_id] = {
        'pickup': pickup_location,
        'destination': destination,
        'status': 'waiting',
        'matched_riders': [],
        'driver_id': None
    }
    
    # Update demand in the grid
    grid_x = min(int(pickup_location[0] * GRID_SIZE), GRID_SIZE-1)
    grid_y = min(int(pickup_location[1] * GRID_SIZE), GRID_SIZE-1)
    demand_grid[grid_x, grid_y] += 1
    
    # Find nearby drivers
    available_drivers = []
    for d_id, driver in drivers.items():
        if driver['status'] == 'available':
            distance = calculate_distance(pickup_location, driver['location'])
            if distance < 5:  # Within 5km
                available_drivers.append((d_id, distance))
    
    # Find potential ride shares
    potential_shares = []
    for r_id, rider in riders.items():
        if r_id != rider_id and rider['status'] == 'waiting' and rider['driver_id'] is None:
            distance = calculate_distance(pickup_location, rider['pickup'])
            # Check if both pickups and destinations are reasonably close
            dest_distance = calculate_distance(destination, rider['destination'])
            if distance < MAX_SHARING_RADIUS and dest_distance < MAX_SHARING_RADIUS * 2:
                potential_shares.append(r_id)
    
    # Update hotspots
    update_traffic_hotspots()
    
    response = {
        'status': 'success',
        'request_id': rider_id,
        'available_drivers': [d for d, _ in sorted(available_drivers, key=lambda x: x[1])],
        'potential_shares': potential_shares
    }
    
    return jsonify(response)

@app.route('/api/rider/accept-share', methods=['POST'])
def accept_share():
    data = request.json
    rider_id = data.get('rider_id')
    share_with = data.get('share_with')
    
    if rider_id in riders and share_with in riders:
        # Link the two riders
        riders[rider_id]['matched_riders'].append(share_with)
        riders[share_with]['matched_riders'].append(rider_id)
        
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Rider not found'}), 404

@app.route('/api/driver/accept-ride', methods=['POST'])
def accept_ride():
    data = request.json
    driver_id = data.get('driver_id')
    rider_id = data.get('rider_id')
    
    if driver_id in drivers and rider_id in riders:
        drivers[driver_id]['status'] = 'busy'
        riders[rider_id]['driver_id'] = driver_id
        
        # Include any matched riders in this ride
        for shared_rider in riders[rider_id]['matched_riders']:
            if shared_rider in riders:
                riders[shared_rider]['driver_id'] = driver_id
        
        # Create ride entry
        ride_id = f"ride_{len(active_rides) + 1}"
        active_rides[ride_id] = {
            'driver_id': driver_id,
            'riders': [rider_id] + riders[rider_id]['matched_riders'],
            'status': 'in_progress',
            'start_time': datetime.now().isoformat()
        }
        
        return jsonify({'status': 'success', 'ride_id': ride_id})
    else:
        return jsonify({'status': 'error', 'message': 'Driver or rider not found'}), 404

@app.route('/api/driver/complete-ride', methods=['POST'])
def complete_ride():
    data = request.json
    ride_id = data.get('ride_id')
    
    if ride_id in active_rides:
        ride = active_rides[ride_id]
        driver_id = ride['driver_id']
        
        # Update ride status
        active_rides[ride_id]['status'] = 'completed'
        active_rides[ride_id]['end_time'] = datetime.now().isoformat()
        
        # Free up driver
        if driver_id in drivers:
            drivers[driver_id]['status'] = 'available'
            
            # Check if ride was in a high traffic area
            pickup_loc = riders[ride['riders'][0]]['pickup']
            grid_x = min(int(pickup_loc[0] * GRID_SIZE), GRID_SIZE-1)
            grid_y = min(int(pickup_loc[1] * GRID_SIZE), GRID_SIZE-1)
            
            # Award points if from high traffic area
            points_earned = 10  # Base points
            if traffic_hotspots[grid_x, grid_y]:
                points_earned += 25  # Bonus for high traffic area
            
            # Additional points for shared rides
            if len(ride['riders']) > 1:
                points_earned += 15 * (len(ride['riders']) - 1)
                
            drivers[driver_id]['points'] += points_earned
            
            # Check for level up
            current_level = drivers[driver_id]['level']
            points_threshold = current_level * 100  # Simple level progression
            
            if drivers[driver_id]['points'] >= points_threshold:
                drivers[driver_id]['level'] += 1
                level_up = True
            else:
                level_up = False
            
            # Clear rider statuses
            for rider_id in ride['riders']:
                if rider_id in riders:
                    riders[rider_id]['status'] = 'completed'
            
            return jsonify({
                'status': 'success',
                'points_earned': points_earned,
                'total_points': drivers[driver_id]['points'],
                'level_up': level_up,
                'current_level': drivers[driver_id]['level']
            })
    
    return jsonify({'status': 'error', 'message': 'Ride not found'}), 404

# Simulation endpoint for testing
@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    return jsonify({
        'drivers': len(drivers),
        'riders': len(riders),
        'active_rides': len([r for r in active_rides.values() if r['status'] == 'in_progress']),
        'high_demand_areas': np.count_nonzero(traffic_hotspots),
        'total_trips_completed': len([r for r in active_rides.values() if r['status'] == 'completed'])
    })

if __name__ == '__main__':
    app.run(debug=True)