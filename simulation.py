import requests
import random
import time
import threading
import json
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:5000/api"
NUM_DRIVERS = 20
NUM_RIDERS = 50
SIMULATION_DURATION = 60 * 5  # 5 minutes
GRID_SIZE = 1.0  # Normalized grid from 0 to 1.0

# For storing simulation data
active_drivers = []
active_riders = []
completed_rides = []

def random_location():
    """Generate random location within grid"""
    return [random.random(), random.random()]

def get_simulation_stats():
    """Get current simulation statistics"""
    try:
        response = requests.get(f"{BASE_URL}/simulation/status")
        return response.json()
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {}

def register_driver(driver_id):
    """Register a new driver"""
    try:
        location = random_location()
        data = {
            "driver_id": driver_id,
            "location": location
        }
        response = requests.post(f"{BASE_URL}/driver/register", json=data)
        if response.status_code == 200:
            active_drivers.append({"id": driver_id, "location": location})
            print(f"Driver {driver_id} registered at {location}")
        else:
            print(f"Failed to register driver {driver_id}: {response.text}")
    except Exception as e:
        print(f"Error registering driver: {e}")

def update_driver_location(driver_id):
    """Update driver location with small random movement"""
    try:
        # Find driver in active drivers
        for driver in active_drivers:
            if driver["id"] == driver_id:
                # Move slightly in random direction
                new_location = [
                    max(0, min(1, driver["location"][0] + random.uniform(-0.05, 0.05))),
                    max(0, min(1, driver["location"][1] + random.uniform(-0.05, 0.05)))
                ]
                
                data = {
                    "driver_id": driver_id,
                    "location": new_location
                }
                response = requests.post(f"{BASE_URL}/driver/update-location", json=data)
                if response.status_code == 200:
                    driver["location"] = new_location
                    print(f"Driver {driver_id} moved to {new_location}")
                break
    except Exception as e:
        print(f"Error updating driver location: {e}")

def request_ride(rider_id):
    """Request a new ride"""
    try:
        pickup = random_location()
        # Generate destination that's somewhat far from pickup
        dest_offset = [random.uniform(0.1, 0.3), random.uniform(0.1, 0.3)]
        if random.random() > 0.5:
            dest_offset[0] *= -1
        if random.random() > 0.5:
            dest_offset[1] *= -1
            
        destination = [
            max(0, min(1, pickup[0] + dest_offset[0])),
            max(0, min(1, pickup[1] + dest_offset[1]))
        ]
        
        data = {
            "rider_id": rider_id,
            "pickup": pickup,
            "destination": destination
        }
        
        response = requests.post(f"{BASE_URL}/rider/request-ride", json=data)
        if response.status_code == 200:
            result = response.json()
            active_riders.append({
                "id": rider_id,
                "pickup": pickup,
                "destination": destination,
                "available_drivers": result.get("available_drivers", []),
                "potential_shares": result.get("potential_shares", [])
            })
            print(f"Rider {rider_id} requested ride from {pickup} to {destination}")
            
            # Try to accept a potential share
            if result["potential_shares"]:
                share_with = random.choice(result["potential_shares"])
                if random.random() > 0.3:  # 70% chance to accept share
                    accept_share(rider_id, share_with)
            
            # Try to match with a driver
            if result["available_drivers"]:
                driver_id = random.choice(result["available_drivers"])
                # Wait a bit before driver accepts
                time.sleep(random.uniform(1, 5))
                driver_accept_ride(driver_id, rider_id)
        else:
            print(f"Failed to request ride for {rider_id}: {response.text}")
    except Exception as e:
        print(f"Error requesting ride: {e}")

def accept_share(rider_id, share_with):
    """Accept ride sharing with another rider"""
    try:
        data = {
            "rider_id": rider_id,
            "share_with": share_with
        }
        response = requests.post(f"{BASE_URL}/rider/accept-share", json=data)
        if response.status_code == 200:
            print(f"Rider {rider_id} will share ride with {share_with}")
            return True
        else:
            print(f"Failed to accept share: {response.text}")
            return False
    except Exception as e:
        print(f"Error accepting share: {e}")
        return False

def driver_accept_ride(driver_id, rider_id):
    """Driver accepts a ride request"""
    try:
        data = {
            "driver_id": driver_id,
            "rider_id": rider_id
        }
        response = requests.post(f"{BASE_URL}/driver/accept-ride", json=data)
        if response.status_code == 200:
            result = response.json()
            ride_id = result.get("ride_id")
            print(f"Driver {driver_id} accepted ride for rider {rider_id}, ride_id: {ride_id}")
            
            # Simulate ride duration
            ride_duration = random.uniform(3, 10)  # 3-10 seconds for simulation
            threading.Timer(ride_duration, complete_ride, args=[ride_id]).start()
            
            return ride_id
        else:
            print(f"Failed to accept ride: {response.text}")
            return None
    except Exception as e:
        print(f"Error accepting ride: {e}")
        return None

def complete_ride(ride_id):
    """Complete a ride"""
    try:
        data = {
            "ride_id": ride_id
        }
        response = requests.post(f"{BASE_URL}/driver/complete-ride", json=data)
        if response.status_code == 200:
            result = response.json()
            points = result.get("points_earned", 0)
            level_up = result.get("level_up", False)
            completed_rides.append({
                "ride_id": ride_id,
                "points": points,
                "level_up": level_up,
                "time": datetime.now().isoformat()
            })
            
            level_msg = " and leveled up!" if level_up else ""
            print(f"Ride {ride_id} completed! Driver earned {points} points{level_msg}")
    except Exception as e:
        print(f"Error completing ride: {e}")

def run_simulation():
    """Run the full simulation"""
    start_time = time.time()
    
    # Register drivers
    for i in range(NUM_DRIVERS):
        register_driver(f"d{i+1}")
        time.sleep(0.1)
    
    # Main simulation loop
    rider_counter = 0
    
    try:
        while time.time() - start_time < SIMULATION_DURATION:
            current_stats = get_simulation_stats()
            print(f"\nCurrent simulation stats: {json.dumps(current_stats, indent=2)}\n")
            
            # Move some drivers
            for driver in random.sample(active_drivers, min(5, len(active_drivers))):
                update_driver_location(driver["id"])
            
            # Generate new riders
            new_riders_count = random.randint(1, 3)  # 1-3 new riders per cycle
            for _ in range(new_riders_count):
                rider_counter += 1
                request_ride(f"r{rider_counter}")
            
            # Sleep between simulation cycles
            time.sleep(3)
    except KeyboardInterrupt:
        print("Simulation stopped by user")
    
    # Print final stats
    final_stats = get_simulation_stats()
    print("\n=== SIMULATION COMPLETE ===")
    print(f"Final stats: {json.dumps(final_stats, indent=2)}")
    print(f"Total riders generated: {rider_counter}")
    print(f"Total rides completed: {len(completed_rides)}")
    
    # Calculate driver performance
    if completed_rides:
        total_points = sum(ride["points"] for ride in completed_rides)
        avg_points = total_points / len(completed_rides)
        level_ups = sum(1 for ride in completed_rides if ride["level_up"])
        
        print(f"Total points earned by all drivers: {total_points}")
        print(f"Average points per ride: {avg_points:.2f}")
        print(f"Total driver level-ups: {level_ups}")

if __name__ == "__main__":
    print("Starting ride-sharing simulation...")
    print(f"Simulating {NUM_DRIVERS} drivers and generating up to {NUM_RIDERS} riders")
    print(f"Simulation will run for {SIMULATION_DURATION/60:.1f} minutes")
    print("Press Ctrl+C to stop early")
    time.sleep(2)
    run_simulation()