from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pymongo import MongoClient, GEOSPHERE
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import json
import math
from dotenv import load_dotenv
import uuid
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Ride-sharing app startup')

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JWT_EXPIRATION_DELTA'] = timedelta(hours=int(os.getenv('JWT_EXPIRATION_HOURS', 24)))
app.config['RIDE_MATCHING_RADIUS_KM'] = float(os.getenv('RIDE_MATCHING_RADIUS_KM', 5.0))

# MongoDB Atlas Connection
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client[os.getenv('DB_NAME', 'rideshare_sync_db')]

# Collections
users_collection = db.users
rides_collection = db.rides
ride_requests_collection = db.ride_requests
ratings_collection = db.ratings
payments_collection = db.payments

# Create indexes
users_collection.create_index([("email", 1)], unique=True)
rides_collection.create_index([("start_location", GEOSPHERE)])
rides_collection.create_index([("end_location", GEOSPHERE)])
ride_requests_collection.create_index([("pickup_location", GEOSPHERE)])
ride_requests_collection.create_index([("status", 1)])

# MongoDB JSON encoder
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check if token is in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'Authentication token is missing!'
            }), 401
        
        try:
            # Verify token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})
            if current_user is None:
                return jsonify({
                    'success': False,
                    'message': 'User not found!'
                }), 401
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'message': 'Token has expired!'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Invalid token!'
            }), 401
        
        # Add user to request context
        request.current_user = current_user
        return f(*args, **kwargs)
    
    return decorated

# Helper functions
def calculate_distance(point1, point2):
    """Calculate distance between two points in kilometers using Haversine formula"""
    # Convert coordinates from [lng, lat] to [lat, lng] for calculation
    lat1, lon1 = point1[1], point1[0]
    lat2, lon2 = point2[1], point2[0]
    
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Differences
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance

def calculate_price(distance_km, duration_minutes):
    """Calculate ride price based on distance and duration"""
    base_fare = 2.50
    price_per_km = 1.50
    price_per_minute = 0.25
    
    total_price = base_fare + (distance_km * price_per_km) + (duration_minutes * price_per_minute)
    return round(total_price, 2)

def find_nearby_rides(location, radius_km=5.0):
    """Find rides within a given radius of a location"""
    # MongoDB uses [longitude, latitude] format
    nearby_rides = rides_collection.find({
        'status': 'active',
        'start_location': {
            '$near': {
                '$geometry': {
                    'type': 'Point',
                    'coordinates': location
                },
                '$maxDistance': radius_km * 1000  # Convert km to meters
            }
        }
    })
    return list(nearby_rides)

def match_rides(ride_request):
    """Match a ride request with available rides"""
    pickup_location = ride_request['pickup_location']['coordinates']
    dropoff_location = ride_request['dropoff_location']['coordinates']
    
    # Find nearby rides
    nearby_rides = find_nearby_rides(pickup_location, app.config['RIDE_MATCHING_RADIUS_KM'])
    
    matches = []
    for ride in nearby_rides:
        ride_start = ride['start_location']['coordinates']
        ride_end = ride['end_location']['coordinates']
        
        # Calculate distances
        pickup_distance = calculate_distance(pickup_location, ride_start)
        dropoff_distance = calculate_distance(dropoff_location, ride_end)
        
        # Check if the ride is a good match
        if pickup_distance <= app.config['RIDE_MATCHING_RADIUS_KM'] and dropoff_distance <= app.config['RIDE_MATCHING_RADIUS_KM']:
            # Calculate score based on distance (lower is better)
            score = pickup_distance + dropoff_distance
            
            # Check driver rating
            driver = users_collection.find_one({'_id': ObjectId(ride['driver_id'])})
            driver_rating = driver.get('rating', 4.5)  # Default to 4.5 if not rated
            
            matches.append({
                'ride_id': str(ride['_id']),
                'driver_id': str(ride['driver_id']),
                'driver_name': driver.get('name', 'Unknown Driver'),
                'driver_rating': driver_rating,
                'pickup_distance': round(pickup_distance, 2),
                'dropoff_distance': round(dropoff_distance, 2),
                'score': score,
                'vehicle': ride.get('vehicle', 'Unknown Vehicle'),
                'estimated_price': calculate_price(
                    pickup_distance + dropoff_distance,
                    ((pickup_distance + dropoff_distance) / 30) * 60  # Rough estimate of duration
                )
            })
    
    # Sort matches by score (lower is better)
    matches.sort(key=lambda x: x['score'])
    return matches

# Routes
@app.route('/')
def home():
    return jsonify({
        "message": "Welcome to the Ride-Sharing API",
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    })

# Auth routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    required_fields = ['email', 'password', 'name', 'phone_number']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    # Check if email already exists
    existing_user = users_collection.find_one({'email': data['email']})
    if existing_user:
        return jsonify({
            'success': False,
            'message': 'User with this email already exists!'
        }), 409
    
    # Hash the password
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    
    # Create new user
    new_user = {
        'email': data['email'],
        'password': hashed_password,
        'name': data['name'],
        'phone_number': data['phone_number'],
        'profile_picture': data.get('profile_picture', ''),
        'user_type': data.get('user_type', 'rider'),  # Default to rider
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'rating': 5.0,  # Default rating
        'is_active': True
    }
    
    # Add driver-specific fields if applicable
    if data.get('user_type') == 'driver':
        required_driver_fields = ['license_number', 'vehicle_info']
        for field in required_driver_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required driver field: {field}'
                }), 400
        
        new_user.update({
            'license_number': data['license_number'],
            'vehicle_info': data['vehicle_info'],
            'is_verified': False,  # Driver needs verification
            'verification_documents': data.get('verification_documents', [])
        })
    
    # Insert user into database
    result = users_collection.insert_one(new_user)
    
    return jsonify({
        'success': True,
        'message': 'User registered successfully!',
        'user_id': str(result.inserted_id)
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({
            'success': False,
            'message': 'Missing required fields: email, password'
        }), 400
    
    # Find user by email
    user = users_collection.find_one({'email': data['email']})
    
    if not user or not check_password_hash(user['password'], data['password']):
        return jsonify({
            'success': False,
            'message': 'Invalid email or password!'
        }), 401
    
    # Check if user is active
    if not user.get('is_active', True):
        return jsonify({
            'success': False,
            'message': 'User account is inactive or suspended'
        }), 403
        
    # Generate token
    token_payload = {
        'user_id': str(user['_id']),
        'email': user['email'],
        'user_type': user.get('user_type', 'rider'),
        'exp': datetime.utcnow() + app.config['JWT_EXPIRATION_DELTA']
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        'success': True,
        'message': 'Login successful!',
        'token': token,
        'user': {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'phone_number': user['phone_number'],
            'user_type': user.get('user_type', 'rider'),
            'profile_picture': user.get('profile_picture', ''),
            'rating': user.get('rating', 5.0)
        }
    })

@app.route('/api/users/profile', methods=['GET'])
@token_required
def get_profile():
    user = request.current_user
    
    return jsonify({
        'success': True,
        'user': {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'phone_number': user['phone_number'],
            'profile_picture': user.get('profile_picture', ''),
            'user_type': user.get('user_type', 'rider'),
            'rating': user.get('rating', 5.0),
            'created_at': user['created_at'].isoformat(),
            'vehicle_info': user.get('vehicle_info', None) if user.get('user_type') == 'driver' else None
        }
    })

@app.route('/api/users/profile', methods=['PUT'])
@token_required
def update_profile():
    user = request.current_user
    data = request.get_json()
    
    # Fields that can be updated
    updatable_fields = ['name', 'phone_number', 'profile_picture']
    
    # Add driver-specific updatable fields
    if user.get('user_type') == 'driver':
        updatable_fields.extend(['vehicle_info'])
    
    # Update user data
    update_data = {
        'updated_at': datetime.now()
    }
    
    for field in updatable_fields:
        if field in data:
            update_data[field] = data[field]
    
    if update_data:
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': update_data}
        )
        
        # Get updated user
        updated_user = users_collection.find_one({'_id': user['_id']})
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': {
                'id': str(updated_user['_id']),
                'name': updated_user['name'],
                'email': updated_user['email'],
                'phone_number': updated_user['phone_number'],
                'profile_picture': updated_user.get('profile_picture', ''),
                'user_type': updated_user.get('user_type', 'rider'),
                'rating': updated_user.get('rating', 5.0),
                'vehicle_info': updated_user.get('vehicle_info', None) if updated_user.get('user_type') == 'driver' else None
            }
        })
    
    return jsonify({
        'success': False,
        'message': 'No fields to update'
    }), 400

# Ride routes
@app.route('/api/rides', methods=['POST'])
@token_required
def create_ride():
    user = request.current_user
    data = request.get_json()
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can create rides'
        }), 403
    
    # Check if driver is verified
    if not user.get('is_verified', False):
        return jsonify({
            'success': False,
            'message': 'Driver is not verified'
        }), 403
    
    # Validate required fields
    required_fields = ['start_location', 'end_location', 'departure_time', 'available_seats', 'price_per_seat']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    # Create new ride
    new_ride = {
        'driver_id': str(user['_id']),
        'start_location': {
            'type': 'Point',
            'coordinates': data['start_location']  # [longitude, latitude]
        },
        'end_location': {
            'type': 'Point',
            'coordinates': data['end_location']  # [longitude, latitude]
        },
        'departure_time': datetime.fromisoformat(data['departure_time']),
        'estimated_arrival_time': datetime.fromisoformat(data.get('estimated_arrival_time', '')),
        'available_seats': int(data['available_seats']),
        'price_per_seat': float(data['price_per_seat']),
        'status': 'active',  # active, in_progress, completed, cancelled
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'vehicle': user.get('vehicle_info', {}),
        'route_polyline': data.get('route_polyline', ''),
        'additional_info': data.get('additional_info', ''),
        'riders': []
    }
    
    # Insert ride into database
    result = rides_collection.insert_one(new_ride)
    
    # Return created ride
    new_ride['_id'] = result.inserted_id
    return json.dumps({
        'success': True,
        'message': 'Ride created successfully',
        'ride': new_ride
    }, cls=MongoJSONEncoder), 201, {'Content-Type': 'application/json'}

@app.route('/api/rides/<ride_id>', methods=['GET'])
@token_required
def get_ride(ride_id):
    try:
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Get driver details
        driver = users_collection.find_one({'_id': ObjectId(ride['driver_id'])})
        driver_details = {
            'id': str(driver['_id']),
            'name': driver['name'],
            'rating': driver.get('rating', 5.0),
            'phone_number': driver['phone_number']
        } if driver else {}
        
        # Add driver details to ride
        ride_data = json.loads(json.dumps(ride, cls=MongoJSONEncoder))
        ride_data['driver'] = driver_details
        
        return jsonify({
            'success': True,
            'ride': ride_data
        })
    except Exception as e:
        app.logger.error(f"Error getting ride: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Invalid ride ID or error: {str(e)}'
        }), 400

@app.route('/api/rides/<ride_id>', methods=['PUT'])
@token_required
def update_ride(ride_id):
    user = request.current_user
    data = request.get_json()
    
    try:
        # Check if ride exists
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Check if user is the driver
        if str(user['_id']) != ride['driver_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to update this ride'
            }), 403
        
        # Check if ride can be updated (not completed or cancelled)
        if ride['status'] in ['completed', 'cancelled']:
            return jsonify({
                'success': False,
                'message': f"Cannot update ride with status '{ride['status']}'"
            }), 400
        
        # Fields that can be updated
        updatable_fields = [
            'departure_time', 'estimated_arrival_time', 'available_seats',
            'price_per_seat', 'status', 'additional_info'
        ]
        
        # Update ride data
        update_data = {
            'updated_at': datetime.now()
        }
        
        for field in updatable_fields:
            if field in data:
                # Convert string dates to datetime objects
                if field in ['departure_time', 'estimated_arrival_time'] and data[field]:
                    update_data[field] = datetime.fromisoformat(data[field])
                else:
                    update_data[field] = data[field]
        
        if update_data:
            rides_collection.update_one(
                {'_id': ObjectId(ride_id)},
                {'$set': update_data}
            )
            
            # Get updated ride
            updated_ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
            
            return json.dumps({
                'success': True,
                'message': 'Ride updated successfully',
                'ride': updated_ride
            }, cls=MongoJSONEncoder), 200, {'Content-Type': 'application/json'}
        
        return jsonify({
            'success': False,
            'message': 'No fields to update'
        }), 400
    
    except Exception as e:
        app.logger.error(f"Error updating ride: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating ride: {str(e)}'
        }), 400

@app.route('/api/rides/<ride_id>', methods=['DELETE'])
@token_required
def cancel_ride(ride_id):
    user = request.current_user
    
    try:
        # Check if ride exists
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Check if user is the driver
        if str(user['_id']) != ride['driver_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to cancel this ride'
            }), 403
        
        # Check if ride can be cancelled (not completed)
        if ride['status'] == 'completed':
            return jsonify({
                'success': False,
                'message': 'Cannot cancel a completed ride'
            }), 400
        
        # Update ride status to cancelled
        rides_collection.update_one(
            {'_id': ObjectId(ride_id)},
            {'$set': {
                'status': 'cancelled',
                'updated_at': datetime.now()
            }}
        )
        
        # Notify riders about cancellation (in a real app, you'd implement notifications)
        
        return jsonify({
            'success': True,
            'message': 'Ride cancelled successfully'
        })
    
    except Exception as e:
        app.logger.error(f"Error cancelling ride: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error cancelling ride: {str(e)}'
        }), 400

@app.route('/api/rides/search', methods=['POST'])
@token_required
def search_rides():
    data = request.get_json()
    
    # Required fields
    if not data.get('pickup_location') or not data.get('dropoff_location'):
        return jsonify({
            'success': False,
            'message': 'Missing required fields: pickup_location, dropoff_location'
        }), 400
    
    pickup_location = data['pickup_location']  # [longitude, latitude]
    dropoff_location = data['dropoff_location']  # [longitude, latitude]
    
    # Optional parameters
    radius_km = float(data.get('radius_km', app.config['RIDE_MATCHING_RADIUS_KM']))
    departure_time = data.get('departure_time')
    if departure_time:
        departure_time = datetime.fromisoformat(departure_time)
    
    # Find nearby rides
    query = {
        'status': 'active',
        'available_seats': {'$gte': 1},
        'start_location': {
            '$near': {
                '$geometry': {
                    'type': 'Point',
                    'coordinates': pickup_location
                },
                '$maxDistance': radius_km * 1000  # Convert km to meters
            }
        }
    }
    
    # Add departure time filter if provided
    if departure_time:
        # Find rides departing within 2 hours of requested time
        time_window = 2
        query['departure_time'] = {
            '$gte': departure_time - timedelta(hours=time_window),
            '$lte': departure_time + timedelta(hours=time_window)
        }
    
    try:
        nearby_rides = list(rides_collection.find(query))
        
        # Process and filter rides based on dropoff location
        matching_rides = []
        for ride in nearby_rides:
            ride_end = ride['end_location']['coordinates']
            dropoff_distance = calculate_distance(dropoff_location, ride_end)
            
            # Check if the dropoff locations are close enough
            if dropoff_distance <= radius_km:
                # Get driver details
                driver = users_collection.find_one({'_id': ObjectId(ride['driver_id'])})
                
                # Calculate price estimate
                pickup_distance = calculate_distance(pickup_location, ride['start_location']['coordinates'])
                price_estimate = calculate_price(
                    pickup_distance + dropoff_distance,
                    ((pickup_distance + dropoff_distance) / 30) * 60  # Rough estimate of duration (30km/h)
                )
                
                # Convert ride to dict for JSON serialization
                ride_dict = json.loads(json.dumps(ride, cls=MongoJSONEncoder))
                
                # Add additional info
                ride_dict['driver'] = {
                    'id': str(driver['_id']),
                    'name': driver['name'],
                    'rating': driver.get('rating', 5.0),
                    'phone_number': driver['phone_number']
                } if driver else {}
                ride_dict['pickup_distance_km'] = round(pickup_distance, 2)
                ride_dict['dropoff_distance_km'] = round(dropoff_distance, 2)
                ride_dict['price_estimate'] = price_estimate
                
                matching_rides.append(ride_dict)
        
        # Sort by departure time
        matching_rides.sort(key=lambda x: x['departure_time'])
        
        return jsonify({
            'success': True,
            'count': len(matching_rides),
            'rides': matching_rides
        })
    
    except Exception as e:
        app.logger.error(f"Error searching rides: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error searching rides: {str(e)}'
        }), 400

# Ride requests (for passengers)
@app.route('/api/ride-requests', methods=['POST'])
@token_required
def create_ride_request():
    user = request.current_user
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['pickup_location', 'dropoff_location', 'requested_seats']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    # Create new ride request
    new_request = {
        'rider_id': str(user['_id']),
        'pickup_location': {
            'type': 'Point',
            'coordinates': data['pickup_location']  # [longitude, latitude]
        },
        'dropoff_location': {
            'type': 'Point',
            'coordinates': data['dropoff_location']  # [longitude, latitude]
        },
        'requested_pickup_time': datetime.fromisoformat(data.get('requested_pickup_time', datetime.now().isoformat())),
        'requested_seats': int(data['requested_seats']),
        'status': 'pending',  # pending, matching, matched, in_progress, completed, cancelled
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'matched_ride_id': None,
        'price': None,
        'payment_status': 'unpaid',
        'additional_info': data.get('additional_info', '')
    }
    
    # Insert ride request into database
    result = ride_requests_collection.insert_one(new_request)
    request_id = result.inserted_id
    
    # Find matching rides
    matches = []
    try:
        # Create a simplified request object for matching
        request_for_matching = {
            'pickup_location': new_request['pickup_location'],
            'dropoff_location': new_request['dropoff_location']
        }
        matches = match_rides(request_for_matching)
    except Exception as e:
        app.logger.error(f"Error matching rides: {str(e)}")
    
    # Update request with matches if found
    if matches:
        ride_requests_collection.update_one(
            {'_id': request_id},
            {'$set': {
                'status': 'matching',
                'potential_matches': matches[:5],  # Store top 5 matches
                'updated_at': datetime.now()
            }}
        )
    
    # Get the updated request
    created_request = ride_requests_collection.find_one({'_id': request_id})
    
    return json.dumps({
        'success': True,
        'message': 'Ride request created successfully',
        'request': created_request,
        'matches': matches[:5] if matches else []
    }, cls=MongoJSONEncoder), 201, {'Content-Type': 'application/json'}

@app.route('/api/ride-requests/<request_id>/accept-match', methods=['POST'])
@token_required
def accept_ride_match(request_id):
    user = request.current_user
    data = request.get_json()
    
    if not data.get('ride_id'):
        return jsonify({
            'success': False,
            'message': 'Missing required field: ride_id'
        }), 400
    
    try:
        # Get the ride request
        ride_request = ride_requests_collection.find_one({'_id': ObjectId(request_id)})
        if not ride_request:
            return jsonify({
                'success': False,
                'message': f'Ride request with id {request_id} not found'
            }), 404
        
        # Check if user owns this request
        if str(user['_id']) != ride_request['rider_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to accept this match'
            }), 403
        
        # Check if request is in a valid state
        if ride_request['status'] not in ['pending', 'matching']:
            return jsonify({
                'success': False,
                'message': f"Cannot accept match for request with status '{ride_request['status']}'"
            }), 400
        
        # Get the ride
        ride_id = data['ride_id']
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Check if ride is active and has seats
        if ride['status'] != 'active':
            return jsonify({
                'success': False,
                'message': f"Cannot join ride with status '{ride['status']}'"
            }), 400
        
        if ride['available_seats'] < ride_request['requested_seats']:
            return jsonify({
                'success': False,
                'message': 'Not enough available seats'
            }), 400
        
        # Calculate price based on distance and time
        pickup_location = ride_request['pickup_location']['coordinates']
        dropoff_location = ride_request['dropoff_location']['coordinates']
        ride_start = ride['start_location']['coordinates']
        ride_end = ride['end_location']['coordinates']
        
        pickup_distance = calculate_distance(pickup_location, ride_start)
        dropoff_distance = calculate_distance(dropoff_location, ride_end)
        
        # Calculate price
        price = calculate_price(
            pickup_distance + dropoff_distance,
            ((pickup_distance + dropoff_distance) / 30) * 60  # Rough estimate: 30km/h
        )
        
        # Update ride request
        ride_requests_collection.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {
                'status': 'matched',
                'matched_ride_id': ride_id,
                'price': price,
                'updated_at': datetime.now()
            }}
        )
        
        # Update ride's available seats and add rider
        rider_info = {
            'rider_id': str(user['_id']),
            'name': user['name'],
            'pickup_location': ride_request['pickup_location'],
            'dropoff_location': ride_request['dropoff_location'],
            'seats': ride_request['requested_seats'],
            'price': price,
            'status': 'confirmed'  # confirmed, picked_up, dropped_off
        }
        
        rides_collection.update_one(
            {'_id': ObjectId(ride_id)},
            {
                '$inc': {'available_seats': -ride_request['requested_seats']},
                '$push': {'riders': rider_info},
                '$set': {'updated_at': datetime.now()}
            }
        )
        
        # Get updated ride and request
        updated_ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        updated_request = ride_requests_collection.find_one({'_id': ObjectId(request_id)})
        
        return json.dumps({
            'success': True,
            'message': 'Ride match accepted successfully',
            'request': updated_request,
            'ride': updated_ride
        }, cls=MongoJSONEncoder), 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        app.logger.error(f"Error accepting ride match: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error accepting ride match: {str(e)}'
        }), 400

@app.route('/api/ride-requests/<request_id>/cancel', methods=['POST'])
@token_required
def cancel_ride_request(request_id):
    user = request.current_user
    
    try:
        # Get the ride request
        ride_request = ride_requests_collection.find_one({'_id': ObjectId(request_id)})
        if not ride_request:
            return jsonify({
                'success': False,
                'message': f'Ride request with id {request_id} not found'
            }), 404
        
        # Check if user owns this request
        if str(user['_id']) != ride_request['rider_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to cancel this request'
            }), 403
        
        # Check if request can be cancelled
        if ride_request['status'] in ['completed', 'cancelled']:
            return jsonify({
                'success': False,
                'message': f"Cannot cancel request with status '{ride_request['status']}'"
            }), 400
        
        # If request is matched with a ride, update the ride too
        if ride_request['status'] == 'matched' and ride_request.get('matched_ride_id'):
            matched_ride = rides_collection.find_one({'_id': ObjectId(ride_request['matched_ride_id'])})
            
            if matched_ride:
                # Return available seats
                rides_collection.update_one(
                    {'_id': ObjectId(ride_request['matched_ride_id'])},
                    {
                        '$inc': {'available_seats': ride_request['requested_seats']},
                        '$pull': {'riders': {'rider_id': str(user['_id'])}},
                        '$set': {'updated_at': datetime.now()}
                    }
                )
        
        # Update ride request status to cancelled
        ride_requests_collection.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {
                'status': 'cancelled',
                'cancelled_at': datetime.now(),
                'updated_at': datetime.now(),
                'cancellation_reason': 'User cancelled request'
            }}
        )
        
        return jsonify({
            'success': True,
            'message': 'Ride request cancelled successfully'
        })
    
    except Exception as e:
        app.logger.error(f"Error cancelling ride request: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error cancelling ride request: {str(e)}'
        }), 400

@app.route('/api/ride-requests/<request_id>', methods=['GET'])
@token_required
def get_ride_request(request_id):
    user = request.current_user
    
    try:
        # Get the ride request
        ride_request = ride_requests_collection.find_one({'_id': ObjectId(request_id)})
        if not ride_request:
            return jsonify({
                'success': False,
                'message': f'Ride request with id {request_id} not found'
            }), 404
        
        # Check if user is authorized (either rider or driver of matched ride)
        is_rider = str(user['_id']) == ride_request['rider_id']
        is_driver = False
        
        if ride_request.get('matched_ride_id'):
            matched_ride = rides_collection.find_one({'_id': ObjectId(ride_request['matched_ride_id'])})
            if matched_ride:
                is_driver = str(user['_id']) == matched_ride['driver_id']
        
        if not (is_rider or is_driver):
            return jsonify({
                'success': False,
                'message': 'You are not authorized to view this request'
            }), 403
        
        # Convert to dict for JSON serialization
        request_data = json.loads(json.dumps(ride_request, cls=MongoJSONEncoder))
        
        # Get matched ride details if available
        if ride_request.get('matched_ride_id'):
            matched_ride = rides_collection.find_one({'_id': ObjectId(ride_request['matched_ride_id'])})
            if matched_ride:
                # Get driver details
                driver = users_collection.find_one({'_id': ObjectId(matched_ride['driver_id'])})
                driver_details = {
                    'id': str(driver['_id']),
                    'name': driver['name'],
                    'rating': driver.get('rating', 5.0),
                    'phone_number': driver['phone_number'],
                    'profile_picture': driver.get('profile_picture', '')
                } if driver else {}
                
                # Add driver details to matched ride
                ride_data = json.loads(json.dumps(matched_ride, cls=MongoJSONEncoder))
                ride_data['driver'] = driver_details
                
                request_data['matched_ride'] = ride_data
        
        # Get rider details
        rider = users_collection.find_one({'_id': ObjectId(ride_request['rider_id'])})
        request_data['rider'] = {
            'id': str(rider['_id']),
            'name': rider['name'],
            'rating': rider.get('rating', 5.0),
            'phone_number': rider['phone_number'],
            'profile_picture': rider.get('profile_picture', '')
        } if rider else {}
        
        return jsonify({
            'success': True,
            'request': request_data
        })
    
    except Exception as e:
        app.logger.error(f"Error getting ride request: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting ride request: {str(e)}'
        }), 400

@app.route('/api/users/rides', methods=['GET'])
@token_required
def get_user_rides():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Query parameters
    status = request.args.get('status', '')  # Filter by status
    role = request.args.get('role', 'all')  # 'driver', 'rider', or 'all'
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    try:
        result = {
            'as_driver': [],
            'as_rider': [],
            'requests': []
        }
        
        # Get rides where user is the driver
        if role in ['driver', 'all'] and user.get('user_type') == 'driver':
            query = {'driver_id': user_id}
            if status:
                query['status'] = status
            
            driver_rides = list(rides_collection.find(query).sort('departure_time', -1).skip(offset).limit(limit))
            result['as_driver'] = json.loads(json.dumps(driver_rides, cls=MongoJSONEncoder))
        
        # Get rides where user is a rider
        if role in ['rider', 'all']:
            # First get ride requests
            request_query = {'rider_id': user_id}
            if status:
                request_query['status'] = status
            
            ride_requests = list(ride_requests_collection.find(request_query).sort('created_at', -1).skip(offset).limit(limit))
            result['requests'] = json.loads(json.dumps(ride_requests, cls=MongoJSONEncoder))
            
            # Get rides where user appears as a rider
            rider_rides_cursor = rides_collection.find({
                'riders.rider_id': user_id
            }).sort('departure_time', -1).skip(offset).limit(limit)
            
            rider_rides = []
            for ride in rider_rides_cursor:
                # Add driver info
                driver = users_collection.find_one({'_id': ObjectId(ride['driver_id'])})
                if driver:
                    ride_dict = json.loads(json.dumps(ride, cls=MongoJSONEncoder))
                    ride_dict['driver'] = {
                        'id': str(driver['_id']),
                        'name': driver['name'],
                        'rating': driver.get('rating', 5.0),
                        'phone_number': driver['phone_number']
                    }
                    rider_rides.append(ride_dict)
            
            result['as_rider'] = rider_rides
        
        return jsonify({
            'success': True,
            'rides': result
        })
    
    except Exception as e:
        app.logger.error(f"Error getting user rides: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting user rides: {str(e)}'
        }), 400

# Ride status updates
@app.route('/api/rides/<ride_id>/start', methods=['POST'])
@token_required
def start_ride(ride_id):
    user = request.current_user
    
    try:
        # Check if ride exists
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Check if user is the driver
        if str(user['_id']) != ride['driver_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to start this ride'
            }), 403
        
        # Check if ride can be started
        if ride['status'] != 'active':
            return jsonify({
                'success': False,
                'message': f"Cannot start ride with status '{ride['status']}'"
            }), 400
        
        # Update ride status to in_progress
        rides_collection.update_one(
            {'_id': ObjectId(ride_id)},
            {'$set': {
                'status': 'in_progress',
                'started_at': datetime.now(),
                'updated_at': datetime.now()
            }}
        )
        
        # Update all matched ride requests
        if ride.get('riders'):
            for rider in ride['riders']:
                # Find the corresponding ride request
                request = ride_requests_collection.find_one({
                    'rider_id': rider['rider_id'],
                    'matched_ride_id': ride_id,
                    'status': 'matched'
                })
                
                if request:
                    ride_requests_collection.update_one(
                        {'_id': request['_id']},
                        {'$set': {
                            'status': 'in_progress',
                            'updated_at': datetime.now()
                        }}
                    )
        
        return jsonify({
            'success': True,
            'message': 'Ride started successfully'
        })
    
    except Exception as e:
        app.logger.error(f"Error starting ride: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error starting ride: {str(e)}'
        }), 400

@app.route('/api/rides/<ride_id>/complete', methods=['POST'])
@token_required
def complete_ride(ride_id):
    user = request.current_user
    
    try:
        # Check if ride exists
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Check if user is the driver
        if str(user['_id']) != ride['driver_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to complete this ride'
            }), 403
        
        # Check if ride can be completed
        if ride['status'] != 'in_progress':
            return jsonify({
                'success': False,
                'message': f"Cannot complete ride with status '{ride['status']}'"
            }), 400
        
        # Update ride status to completed
        rides_collection.update_one(
            {'_id': ObjectId(ride_id)},
            {'$set': {
                'status': 'completed',
                'completed_at': datetime.now(),
                'updated_at': datetime.now()
            }}
        )
        
        # Update all matched ride requests
        if ride.get('riders'):
            for rider in ride['riders']:
                # Find the corresponding ride request
                request = ride_requests_collection.find_one({
                    'rider_id': rider['rider_id'],
                    'matched_ride_id': ride_id,
                    'status': 'in_progress'
                })
                
                if request:
                    ride_requests_collection.update_one(
                        {'_id': request['_id']},
                        {'$set': {
                            'status': 'completed',
                            'updated_at': datetime.now(),
                            'completed_at': datetime.now()
                        }}
                    )
        
        return jsonify({
            'success': True,
            'message': 'Ride completed successfully'
        })
    
    except Exception as e:
        app.logger.error(f"Error completing ride: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error completing ride: {str(e)}'
        }), 400

@app.route('/api/rides/<ride_id>/rider-status', methods=['POST'])
@token_required
def update_rider_status(ride_id):
    user = request.current_user
    data = request.get_json()
    
    if not data.get('rider_id') or not data.get('status'):
        return jsonify({
            'success': False,
            'message': 'Missing required fields: rider_id, status'
        }), 400
    
    # Validate status
    valid_statuses = ['confirmed', 'picked_up', 'dropped_off', 'no_show']
    if data['status'] not in valid_statuses:
        return jsonify({
            'success': False,
            'message': f"Invalid status: {data['status']}. Must be one of {valid_statuses}"
        }), 400
    
    try:
        # Check if ride exists
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {ride_id} not found'
            }), 404
        
        # Check if user is the driver
        if str(user['_id']) != ride['driver_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to update rider status'
            }), 403
        
        # Check if ride is active or in progress
        if ride['status'] not in ['active', 'in_progress']:
            return jsonify({
                'success': False,
                'message': f"Cannot update rider status for ride with status '{ride['status']}'"
            }), 400
        
        # Check if rider exists in the ride
        rider_found = False
        for i, rider in enumerate(ride.get('riders', [])):
            if rider['rider_id'] == data['rider_id']:
                rider_found = True
                break
        
        if not rider_found:
            return jsonify({
                'success': False,
                'message': f"Rider with id {data['rider_id']} not found in this ride"
            }), 404
        
        # Update rider status
        rides_collection.update_one(
            {
                '_id': ObjectId(ride_id),
                'riders.rider_id': data['rider_id']
            },
            {'$set': {
                'riders.$.status': data['status'],
                'riders.$.status_updated_at': datetime.now(),
                'updated_at': datetime.now()
            }}
        )
        
        # If rider is marked as no_show, adjust available seats
        if data['status'] == 'no_show':
            # Find the rider to get their seat count
            rider_seats = 0
            for rider in ride.get('riders', []):
                if rider['rider_id'] == data['rider_id']:
                    rider_seats = rider.get('seats', 1)
                    break
            
            # Adjust available seats
            if rider_seats > 0:
                rides_collection.update_one(
                    {'_id': ObjectId(ride_id)},
                    {'$inc': {'available_seats': rider_seats}}
                )
        
        return jsonify({
            'success': True,
            'message': f"Rider status updated to {data['status']}"
        })
    
    except Exception as e:
        app.logger.error(f"Error updating rider status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating rider status: {str(e)}'
        }), 400

# Rating routes
@app.route('/api/ratings', methods=['POST'])
@token_required
def submit_rating():
    user = request.current_user
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['rated_user_id', 'ride_id', 'rating']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    # Validate rating value
    try:
        rating_value = float(data['rating'])
        if rating_value < 1 or rating_value > 5:
            return jsonify({
                'success': False,
                'message': 'Rating must be between 1 and 5'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Rating must be a number'
        }), 400
    
    try:
        # Check if ride exists
        ride = rides_collection.find_one({'_id': ObjectId(data['ride_id'])})
        if not ride:
            return jsonify({
                'success': False,
                'message': f'Ride with id {data["ride_id"]} not found'
            }), 404
        
        # Verify user was part of the ride (either as driver or rider)
        user_id = str(user['_id'])
        rated_user_id = data['rated_user_id']
        
        if user_id == ride['driver_id']:
            # Driver rating a rider
            rider_found = False
            for rider in ride.get('riders', []):
                if rider['rider_id'] == rated_user_id:
                    rider_found = True
                    break
            
            if not rider_found:
                return jsonify({
                    'success': False,
                    'message': 'Rated user was not a rider in this ride'
                }), 400
        elif any(rider['rider_id'] == user_id for rider in ride.get('riders', [])):
            # Rider rating the driver
            if rated_user_id != ride['driver_id']:
                return jsonify({
                    'success': False,
                    'message': 'Rider can only rate the driver'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': 'You were not part of this ride'
            }), 403
        
        # Check if the ride is completed
        if ride['status'] != 'completed':
            return jsonify({
                'success': False,
                'message': 'Can only rate completed rides'
            }), 400
        
        # Check if user has already rated this user for this ride
        existing_rating = ratings_collection.find_one({
            'rater_id': user_id,
            'rated_user_id': rated_user_id,
            'ride_id': data['ride_id']
        })
        
        if existing_rating:
            return jsonify({
                'success': False,
                'message': 'You have already rated this user for this ride'
            }), 409
        
        # Create new rating
        new_rating = {
            'rater_id': user_id,
            'rated_user_id': rated_user_id,
            'ride_id': data['ride_id'],
            'rating': rating_value,
            'comment': data.get('comment', ''),
            'created_at': datetime.now()
        }
        
        ratings_collection.insert_one(new_rating)
        
        # Update user's average rating
        all_ratings = list(ratings_collection.find({'rated_user_id': rated_user_id}))
        avg_rating = sum(r['rating'] for r in all_ratings) / len(all_ratings)
        
        users_collection.update_one(
            {'_id': ObjectId(rated_user_id)},
            {'$set': {
                'rating': round(avg_rating, 1),
                'updated_at': datetime.now()
            }}
        )
        
        return jsonify({
            'success': True,
            'message': 'Rating submitted successfully',
            'average_rating': round(avg_rating, 1)
        })
    
    except Exception as e:
        app.logger.error(f"Error submitting rating: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error submitting rating: {str(e)}'
        }), 400

@app.route('/api/users/<user_id>/ratings', methods=['GET'])
@token_required
def get_user_ratings(user_id):
    try:
        # Check if user exists
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            return jsonify({
                'success': False,
                'message': f'User with id {user_id} not found'
            }), 404
        
        # Get all ratings for the user
        ratings = list(ratings_collection.find({'rated_user_id': user_id}).sort('created_at', -1))
        
        # Calculate average rating
        avg_rating = 0
        if ratings:
            avg_rating = sum(r['rating'] for r in ratings) / len(ratings)
        
        # Format ratings for response
        formatted_ratings = []
        for rating in ratings:
            # Get rater info
            rater = users_collection.find_one({'_id': ObjectId(rating['rater_id'])})
            rater_info = {
                'id': str(rater['_id']),
                'name': rater['name'],
                'profile_picture': rater.get('profile_picture', '')
            } if rater else {}
            
            # Add ride info
            ride = rides_collection.find_one({'_id': ObjectId(rating['ride_id'])})
            ride_info = {
                'id': str(ride['_id']),
                'date': ride['departure_time'].isoformat(),
                'from': ride['start_location'],
                'to': ride['end_location']
            } if ride else {}
            
            formatted_ratings.append({
                'id': str(rating['_id']),
                'rating': rating['rating'],
                'comment': rating.get('comment', ''),
                'created_at': rating['created_at'].isoformat(),
                'rater': rater_info,
                'ride': ride_info
            })
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'average_rating': round(avg_rating, 1),
            'total_ratings': len(ratings),
            'ratings': formatted_ratings
        })
    
    except Exception as e:
        app.logger.error(f"Error getting user ratings: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting user ratings: {str(e)}'
        }), 400

# Payment routes
@app.route('/api/payments', methods=['POST'])
@token_required
def create_payment():
    user = request.current_user
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['ride_request_id', 'payment_method', 'amount']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'message': f'Missing required field: {field}'
            }), 400
    
    try:
        # Get the ride request
        ride_request = ride_requests_collection.find_one({'_id': ObjectId(data['ride_request_id'])})
        if not ride_request:
            return jsonify({
                'success': False,
                'message': f'Ride request with id {data["ride_request_id"]} not found'
            }), 404
        
        # Check if user is the rider
        if str(user['_id']) != ride_request['rider_id']:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to make this payment'
            }), 403
        
        # Check if payment is already made
        if ride_request['payment_status'] == 'paid':
            return jsonify({
                'success': False,
                'message': 'Payment has already been made for this ride request'
            }), 409
        
        # Create new payment
        payment_id = str(uuid.uuid4())
        new_payment = {
            'payment_id': payment_id,
            'ride_request_id': data['ride_request_id'],
            'rider_id': str(user['_id']),
            'driver_id': None,  # Will be filled after getting ride details
            'ride_id': ride_request.get('matched_ride_id'),
            'amount': float(data['amount']),
            'payment_method': data['payment_method'],
            'payment_status': 'processing',  # processing, completed, failed
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'transaction_details': data.get('transaction_details', {})
        }
        
        # If ride_id exists, get driver_id
        if ride_request.get('matched_ride_id'):
            ride = rides_collection.find_one({'_id': ObjectId(ride_request['matched_ride_id'])})
            if ride:
                new_payment['driver_id'] = ride['driver_id']
        
        # Insert payment
        payments_collection.insert_one(new_payment)
        
# Simulate payment processing (in a real app, this would integrate with a payment gateway)
        # For demo purposes, we'll just mark it as successful
        payments_collection.update_one(
            {'payment_id': payment_id},
            {'$set': {
                'payment_status': 'completed',
                'completed_at': datetime.now(),
                'updated_at': datetime.now()
            }}
        )
        
        # Update ride request payment status
        ride_requests_collection.update_one(
            {'_id': ObjectId(data['ride_request_id'])},
            {'$set': {
                'payment_status': 'paid',
                'updated_at': datetime.now()
            }}
        )
        
        return jsonify({
            'success': True,
            'message': 'Payment processed successfully',
            'payment_id': payment_id,
            'payment_status': 'completed'
        })
    
    except Exception as e:
        app.logger.error(f"Error processing payment: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing payment: {str(e)}'
        }), 400

@app.route('/api/payments/<payment_id>', methods=['GET'])
@token_required
def get_payment(payment_id):
    user = request.current_user
    
    try:
        # Get the payment
        payment = payments_collection.find_one({'payment_id': payment_id})
        if not payment:
            return jsonify({
                'success': False,
                'message': f'Payment with id {payment_id} not found'
            }), 404
        
        # Check if user is authorized (either rider or driver)
        if str(user['_id']) != payment['rider_id'] and str(user['_id']) != payment.get('driver_id'):
            return jsonify({
                'success': False,
                'message': 'You are not authorized to view this payment'
            }), 403
        
        # Return payment details
        payment_data = json.loads(json.dumps(payment, cls=MongoJSONEncoder))
        
        return jsonify({
            'success': True,
            'payment': payment_data
        })
    
    except Exception as e:
        app.logger.error(f"Error getting payment: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting payment: {str(e)}'
        }), 400

@app.route('/api/users/payments', methods=['GET'])
@token_required
def get_user_payments():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Query parameters
    status = request.args.get('status', '')
    role = request.args.get('role', 'all')  # 'payer', 'receiver', or 'all'
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    try:
        result = []
        
        # Build query
        query = {}
        if status:
            query['payment_status'] = status
        
        if role == 'payer':
            query['rider_id'] = user_id
        elif role == 'receiver':
            query['driver_id'] = user_id
        else:  # 'all'
            query['$or'] = [{'rider_id': user_id}, {'driver_id': user_id}]
        
        # Get payments
        payments = list(payments_collection.find(query).sort('created_at', -1).skip(offset).limit(limit))
        
        # Format payments for response
        for payment in payments:
            payment_data = json.loads(json.dumps(payment, cls=MongoJSONEncoder))
            
            # Add ride details if available
            if payment.get('ride_id'):
                ride = rides_collection.find_one({'_id': ObjectId(payment['ride_id'])})
                if ride:
                    payment_data['ride'] = {
                        'id': str(ride['_id']),
                        'start_location': ride['start_location'],
                        'end_location': ride['end_location'],
                        'departure_time': ride['departure_time'].isoformat()
                    }
            
            # Add counterparty details
            if payment['rider_id'] == user_id:
                # User is the payer, get driver details
                if payment.get('driver_id'):
                    driver = users_collection.find_one({'_id': ObjectId(payment['driver_id'])})
                    if driver:
                        payment_data['counterparty'] = {
                            'id': str(driver['_id']),
                            'name': driver['name'],
                            'role': 'driver'
                        }
            else:
                # User is the receiver, get rider details
                rider = users_collection.find_one({'_id': ObjectId(payment['rider_id'])})
                if rider:
                    payment_data['counterparty'] = {
                        'id': str(rider['_id']),
                        'name': rider['name'],
                        'role': 'rider'
                    }
            
            result.append(payment_data)
        
        return jsonify({
            'success': True,
            'count': len(result),
            'payments': result
        })
    
    except Exception as e:
        app.logger.error(f"Error getting user payments: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting user payments: {str(e)}'
        }), 400

# Admin routes
@app.route('/api/admin/stats', methods=['GET'])
@token_required
def get_admin_stats():
    user = request.current_user
    
    # Check if user is an admin
    if user.get('user_type') != 'admin':
        return jsonify({
            'success': False,
            'message': 'Unauthorized access'
        }), 403
    
    try:
        # Get counts
        total_users = users_collection.count_documents({})
        total_drivers = users_collection.count_documents({'user_type': 'driver'})
        total_riders = users_collection.count_documents({'user_type': 'rider'})
        
        total_rides = rides_collection.count_documents({})
        active_rides = rides_collection.count_documents({'status': 'active'})
        completed_rides = rides_collection.count_documents({'status': 'completed'})
        
        total_requests = ride_requests_collection.count_documents({})
        pending_requests = ride_requests_collection.count_documents({'status': 'pending'})
        
        total_payments = payments_collection.count_documents({})
        payment_volume = 0
        
        # Calculate payment volume
        payment_cursor = payments_collection.find({'payment_status': 'completed'})
        for payment in payment_cursor:
            payment_volume += payment.get('amount', 0)
        
        return jsonify({
            'success': True,
            'stats': {
                'users': {
                    'total': total_users,
                    'drivers': total_drivers,
                    'riders': total_riders
                },
                'rides': {
                    'total': total_rides,
                    'active': active_rides,
                    'completed': completed_rides
                },
                'requests': {
                    'total': total_requests,
                    'pending': pending_requests
                },
                'payments': {
                    'total': total_payments,
                    'volume': round(payment_volume, 2)
                }
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting admin stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting admin stats: {str(e)}'
        }), 400

@app.route('/api/admin/verify-driver/<driver_id>', methods=['POST'])
@token_required
def verify_driver(driver_id):
    user = request.current_user
    
    # Check if user is an admin
    if user.get('user_type') != 'admin':
        return jsonify({
            'success': False,
            'message': 'Unauthorized access'
        }), 403
    
    try:
        # Check if driver exists
        driver = users_collection.find_one({'_id': ObjectId(driver_id), 'user_type': 'driver'})
        if not driver:
            return jsonify({
                'success': False,
                'message': f'Driver with id {driver_id} not found'
            }), 404
        
        # Update driver's verification status
        users_collection.update_one(
            {'_id': ObjectId(driver_id)},
            {'$set': {
                'is_verified': True,
                'verification_date': datetime.now(),
                'verified_by': str(user['_id']),
                'updated_at': datetime.now()
            }}
        )
        
        return jsonify({
            'success': True,
            'message': 'Driver verified successfully'
        })
    
    except Exception as e:
        app.logger.error(f"Error verifying driver: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error verifying driver: {str(e)}'
        }), 400

# Search routes
@app.route('/api/search/drivers', methods=['GET'])
@token_required
def search_drivers():
    # Query parameters
    query = request.args.get('q', '')
    verified_only = request.args.get('verified_only', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    try:
        # Build query
        search_query = {
            'user_type': 'driver',
            '$or': [
                {'name': {'$regex': query, '$options': 'i'}},
                {'email': {'$regex': query, '$options': 'i'}}
            ]
        }
        
        if verified_only:
            search_query['is_verified'] = True
        
        # Get drivers
        drivers = list(users_collection.find(search_query).skip(offset).limit(limit))
        
        # Format drivers for response
        result = []
        for driver in drivers:
            driver_data = {
                'id': str(driver['_id']),
                'name': driver['name'],
                'email': driver['email'],
                'phone_number': driver['phone_number'],
                'profile_picture': driver.get('profile_picture', ''),
                'rating': driver.get('rating', 5.0),
                'is_verified': driver.get('is_verified', False),
                'vehicle_info': driver.get('vehicle_info', {})
            }
            result.append(driver_data)
        
        return jsonify({
            'success': True,
            'count': len(result),
            'drivers': result
        })
    
    except Exception as e:
        app.logger.error(f"Error searching drivers: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error searching drivers: {str(e)}'
        }), 400

# Notifications (webhook endpoint for external notification service)
@app.route('/api/notifications/webhook', methods=['POST'])
def notification_webhook():
    data = request.get_json()
    webhook_secret = request.headers.get('X-Webhook-Secret')
    
    # Verify webhook secret
    if webhook_secret != os.getenv('NOTIFICATION_WEBHOOK_SECRET'):
        app.logger.warning("Invalid webhook secret received")
        return jsonify({
            'success': False,
            'message': 'Invalid webhook secret'
        }), 401
    
    # Process notification data
    try:
        app.logger.info(f"Received notification webhook: {data}")
        
        # In a real app, you'd process the notification data here
        # For demo purposes, we'll just log it
        
        return jsonify({
            'success': True,
            'message': 'Notification received'
        })
    except Exception as e:
        app.logger.error(f"Error processing notification webhook: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing notification: {str(e)}'
        }), 400

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Resource not found'
    }), 404

@app.errorhandler(500)
def server_error(error):
    app.logger.error(f"Server error: {error}")
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'message': 'Method not allowed'
    }), 405

# Route for requesting to join another passenger's ride
@app.route('/api/rides/<ride_id>/request-pool', methods=['POST'])
@token_required
def request_ride_pool(ride_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    # Get request data
    data = request.get_json()
    needed_seats = data.get('needed_seats', 1)
    pickup_location = data.get('pickup_location')
    dropoff_location = data.get('dropoff_location')
    
    if not pickup_location or not dropoff_location:
        return jsonify({
            'success': False,
            'message': 'Pickup and dropoff locations are required'
        }), 400
    
    try:
        # Check if ride exists and is active
        ride = rides_collection.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return jsonify({
                'success': False,
                'message': 'Ride not found'
            }), 404
        
        # Check if ride is shareable
        if not ride.get('shareable', False):
            return jsonify({
                'success': False,
                'message': 'This ride is not available for sharing'
            }), 400
        
        # Check if there are enough available seats
        if ride.get('available_seats', 0) < needed_seats:
            return jsonify({
                'success': False,
                'message': 'Not enough available seats'
            }), 400
        
        # Create pool request
        pool_requests_collection = db['pool_requests']
        
        pool_request = {
            'ride_id': ride_id,
            'requester_id': user_id,
            'primary_rider_id': ride['riders'][0]['rider_id'] if ride.get('riders') else None,
            'driver_id': ride.get('driver_id'),
            'pickup_location': pickup_location,
            'dropoff_location': dropoff_location,
            'needed_seats': needed_seats,
            'status': 'pending',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        result = pool_requests_collection.insert_one(pool_request)
        
        # Notify primary rider and driver
        if ride.get('riders') and len(ride['riders']) > 0:
            # Publish notification to the primary rider
            primary_rider_id = ride['riders'][0]['rider_id']
            notification = {
                'user_id': primary_rider_id,
                'type': 'pool_request',
                'title': 'New Pool Request',
                'message': f'Someone wants to share your ride',
                'ride_id': ride_id,
                'pool_request_id': str(result.inserted_id),
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
        
        # Notify driver
        driver_notification = {
            'user_id': ride['driver_id'],
            'type': 'pool_request',
            'title': 'New Pool Request',
            'message': f'A passenger wants to join your current ride',
            'ride_id': ride_id,
            'pool_request_id': str(result.inserted_id),
            'created_at': datetime.now()
        }
        notifications_collection.insert_one(driver_notification)
        
        return jsonify({
            'success': True,
            'message': 'Pool request submitted successfully',
            'request_id': str(result.inserted_id)
        })
    
    except Exception as e:
        app.logger.error(f"Error requesting ride pool: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error requesting ride pool: {str(e)}'
        }), 400

# Route for primary rider to accept/reject pool request
@app.route('/api/pool-requests/<request_id>/primary-rider-action', methods=['POST'])
@token_required
def primary_rider_pool_action(request_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    # Get request data
    data = request.get_json()
    action = data.get('action')  # 'accept' or 'reject'
    
    if action not in ['accept', 'reject']:
        return jsonify({
            'success': False,
            'message': 'Invalid action. Must be "accept" or "reject"'
        }), 400
    
    try:
        pool_requests_collection = db['pool_requests']
        
        # Get the pool request
        pool_request = pool_requests_collection.find_one({'_id': ObjectId(request_id)})
        if not pool_request:
            return jsonify({
                'success': False,
                'message': 'Pool request not found'
            }), 404
        
        # Check if user is the primary rider
        if pool_request['primary_rider_id'] != user_id:
            return jsonify({
                'success': False,
                'message': 'Unauthorized. You are not the primary rider for this request'
            }), 403
        
        # Check if request is still pending
        if pool_request['status'] != 'pending':
            return jsonify({
                'success': False,
                'message': f'This request has already been {pool_request["status"]}'
            }), 400
        
        # Update request status based on action
        if action == 'accept':
            pool_requests_collection.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': 'primary_rider_accepted',
                    'primary_rider_action_at': datetime.now(),
                    'updated_at': datetime.now()
                }}
            )
            
            # Notify driver that primary rider accepted
            notification = {
                'user_id': pool_request['driver_id'],
                'type': 'pool_request_update',
                'title': 'Pool Request Update',
                'message': 'Primary rider has accepted the pool request',
                'ride_id': pool_request['ride_id'],
                'pool_request_id': request_id,
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
            
            message = 'You have accepted the pool request. Waiting for driver confirmation.'
            
        else:  # reject
            pool_requests_collection.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': 'rejected_by_primary_rider',
                    'primary_rider_action_at': datetime.now(),
                    'updated_at': datetime.now()
                }}
            )
            
            # Notify requester of rejection
            notification = {
                'user_id': pool_request['requester_id'],
                'type': 'pool_request_update',
                'title': 'Pool Request Update',
                'message': 'Your pool request was declined by the primary rider',
                'pool_request_id': request_id,
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
            
            message = 'You have rejected the pool request'
        
        return jsonify({
            'success': True,
            'message': message
        })
    
    except Exception as e:
        app.logger.error(f"Error processing pool request action: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing pool request action: {str(e)}'
        }), 400

# Route for driver to accept/reject pool request
@app.route('/api/pool-requests/<request_id>/driver-action', methods=['POST'])
@token_required
def driver_pool_action(request_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    # Get request data
    data = request.get_json()
    action = data.get('action')  # 'accept' or 'reject'
    reason = data.get('reason', '')  # Optional reason for rejection
    
    if action not in ['accept', 'reject']:
        return jsonify({
            'success': False,
            'message': 'Invalid action. Must be "accept" or "reject"'
        }), 400
    
    try:
        pool_requests_collection = db['pool_requests']
        
        # Get the pool request
        pool_request = pool_requests_collection.find_one({'_id': ObjectId(request_id)})
        if not pool_request:
            return jsonify({
                'success': False,
                'message': 'Pool request not found'
            }), 404
        
        # Check if user is the driver for this ride
        if pool_request['driver_id'] != user_id:
            return jsonify({
                'success': False,
                'message': 'Unauthorized. You are not the driver for this ride'
            }), 403
        
        # Check ride status for primary rider approval if needed
        if pool_request.get('primary_rider_id') and action == 'accept':
            if pool_request['status'] not in ['pending', 'primary_rider_accepted']:
                return jsonify({
                    'success': False,
                    'message': f'This request has already been {pool_request["status"]}'
                }), 400
        
        # Handle the action
        if action == 'accept':
            # Update pool request status
            pool_requests_collection.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': 'accepted',
                    'driver_action_at': datetime.now(),
                    'updated_at': datetime.now()
                }}
            )
            
            # Get ride and update it with the new rider
            ride = rides_collection.find_one({'_id': ObjectId(pool_request['ride_id'])})
            
            new_rider = {
                'rider_id': pool_request['requester_id'],
                'pickup_location': pool_request['pickup_location'],
                'dropoff_location': pool_request['dropoff_location'],
                'seats': pool_request['needed_seats'],
                'is_shared': True,
                'joined_at': datetime.now()
            }
            
            # Update the ride
            rides_collection.update_one(
                {'_id': ObjectId(pool_request['ride_id'])},
                {
                    '$push': {'riders': new_rider},
                    '$inc': {'available_seats': -pool_request['needed_seats']},
                    '$set': {'updated_at': datetime.now()}
                }
            )
            
            # Get requester info for notification
            requester = users_collection.find_one({'_id': ObjectId(pool_request['requester_id'])})
            requester_name = requester['name'] if requester else 'New passenger'
            
            # Notify the requester
            notification = {
                'user_id': pool_request['requester_id'],
                'type': 'pool_request_update',
                'title': 'Pool Request Accepted',
                'message': 'Your pool request has been accepted. The auto is on its way!',
                'ride_id': pool_request['ride_id'],
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
            
            # Notify primary rider if applicable
            if pool_request.get('primary_rider_id'):
                primary_notification = {
                    'user_id': pool_request['primary_rider_id'],
                    'type': 'pool_update',
                    'title': 'New Pool Passenger',
                    'message': f'{requester_name} will be joining your ride',
                    'ride_id': pool_request['ride_id'],
                    'created_at': datetime.now()
                }
                notifications_collection.insert_one(primary_notification)
            
            return jsonify({
                'success': True,
                'message': 'Pool request accepted successfully'
            })
            
        else:  # reject
            # Update pool request status
            pool_requests_collection.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': 'rejected_by_driver',
                    'rejection_reason': reason,
                    'driver_action_at': datetime.now(),
                    'updated_at': datetime.now()
                }}
            )
            
            # Notify the requester
            notification = {
                'user_id': pool_request['requester_id'],
                'type': 'pool_request_update',
                'title': 'Pool Request Declined',
                'message': f'Your pool request was declined by the driver. {reason}',
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
            
            # Notify primary rider if they approved
            if pool_request.get('primary_rider_id') and pool_request['status'] == 'primary_rider_accepted':
                primary_notification = {
                    'user_id': pool_request['primary_rider_id'],
                    'type': 'pool_update',
                    'title': 'Pool Request Update',
                    'message': 'Driver declined the pool request',
                    'ride_id': pool_request['ride_id'],
                    'created_at': datetime.now()
                }
                notifications_collection.insert_one(primary_notification)
            
            return jsonify({
                'success': True,
                'message': 'Pool request rejected'
            })
    
    except Exception as e:
        app.logger.error(f"Error processing driver pool action: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing driver pool action: {str(e)}'
        }), 400

# Route for users to view their pool requests
@app.route('/api/users/pool-requests', methods=['GET'])
@token_required
def get_user_pool_requests():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Query parameters
    status = request.args.get('status', '')
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    try:
        pool_requests_collection = db['pool_requests']
        
        # Build query - get requests made by this user
        query = {'requester_id': user_id}
        if status:
            query['status'] = status
        
        # Get requests
        requests = list(pool_requests_collection.find(query).sort('created_at', -1).skip(offset).limit(limit))
        
        # Format requests for response
        result = []
        for req in requests:
            # Get ride info
            ride = rides_collection.find_one({'_id': ObjectId(req['ride_id'])})
            
            # Format request data
            req_data = {
                'id': str(req['_id']),
                'status': req['status'],
                'pickup_location': req['pickup_location'],
                'dropoff_location': req['dropoff_location'],
                'needed_seats': req['needed_seats'],
                'created_at': req['created_at'].isoformat()
            }
            
            # Add ride info if available
            if ride:
                driver = users_collection.find_one({'_id': ObjectId(ride['driver_id'])})
                req_data['ride'] = {
                    'id': str(ride['_id']),
                    'departure_time': ride['departure_time'].isoformat() if 'departure_time' in ride else None,
                    'status': ride['status'],
                    'driver': {
                        'id': str(driver['_id']),
                        'name': driver['name'],
                        'rating': driver.get('rating', 5.0),
                        'vehicle_info': driver.get('vehicle_info', {})
                    } if driver else {}
                }
            
            # Add primary rider info if available
            if req.get('primary_rider_id'):
                primary_rider = users_collection.find_one({'_id': ObjectId(req['primary_rider_id'])})
                if primary_rider:
                    req_data['primary_rider'] = {
                        'id': str(primary_rider['_id']),
                        'name': primary_rider['name'],
                        'profile_picture': primary_rider.get('profile_picture', '')
                    }
            
            result.append(req_data)
        
        return jsonify({
            'success': True,
            'count': len(result),
            'requests': result
        })
    
    except Exception as e:
        app.logger.error(f"Error getting user pool requests: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting user pool requests: {str(e)}'
        }), 400

# Route for primary riders to view incoming pool requests
@app.route('/api/users/incoming-pool-requests', methods=['GET'])
@token_required
def get_incoming_pool_requests():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Query parameters
    status = request.args.get('status', '')
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    try:
        pool_requests_collection = db['pool_requests']
        
        # Build query - get requests where this user is the primary rider
        query = {'primary_rider_id': user_id}
        if status:
            query['status'] = status
        
        # Get requests
        requests = list(pool_requests_collection.find(query).sort('created_at', -1).skip(offset).limit(limit))
        
        # Format requests for response
        result = []
        for req in requests:
            # Get requester info
            requester = users_collection.find_one({'_id': ObjectId(req['requester_id'])})
            requester_info = {
                'id': str(requester['_id']),
                'name': requester['name'],
                'profile_picture': requester.get('profile_picture', ''),
                'rating': requester.get('rating', 5.0)
            } if requester else {}
            
            # Get ride info
            ride = rides_collection.find_one({'_id': ObjectId(req['ride_id'])})
            
            # Format request data
            req_data = {
                'id': str(req['_id']),
                'status': req['status'],
                'pickup_location': req['pickup_location'],
                'dropoff_location': req['dropoff_location'],
                'needed_seats': req['needed_seats'],
                'created_at': req['created_at'].isoformat(),
                'requester': requester_info
            }
            
            # Add ride info if available
            if ride:
                req_data['ride'] = {
                    'id': str(ride['_id']),
                    'start_location': ride['start_location'],
                    'end_location': ride['end_location'],
                    'departure_time': ride['departure_time'].isoformat() if 'departure_time' in ride else None,
                    'available_seats': ride.get('available_seats', 0),
                    'status': ride['status']
                }
            
            result.append(req_data)
        
        return jsonify({
            'success': True,
            'count': len(result),
            'requests': result
        })
    
    except Exception as e:
        app.logger.error(f"Error getting incoming pool requests: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting incoming pool requests: {str(e)}'
        }), 400

# Route for drivers to view pool requests for their rides
@app.route('/api/drivers/pool-requests', methods=['GET'])
@token_required
def get_driver_pool_requests():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    # Query parameters
    status = request.args.get('status', '')
    ride_id = request.args.get('ride_id', '')
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    try:
        pool_requests_collection = db['pool_requests']
        
        # Build query
        query = {'driver_id': user_id}
        if status:
            query['status'] = status
        if ride_id:
            query['ride_id'] = ride_id
        
        # Get requests
        requests = list(pool_requests_collection.find(query).sort('created_at', -1).skip(offset).limit(limit))
        
        # Format requests for response
        result = []
        for req in requests:
            # Get requester info
            requester = users_collection.find_one({'_id': ObjectId(req['requester_id'])})
            requester_info = {
                'id': str(requester['_id']),
                'name': requester['name'],
                'profile_picture': requester.get('profile_picture', ''),
                'rating': requester.get('rating', 5.0)
            } if requester else {}
            
            # Get ride info
            ride = rides_collection.find_one({'_id': ObjectId(req['ride_id'])})
            
            # Format request data
            req_data = {
                'id': str(req['_id']),
                'status': req['status'],
                'pickup_location': req['pickup_location'],
                'dropoff_location': req['dropoff_location'],
                'needed_seats': req['needed_seats'],
                'created_at': req['created_at'].isoformat(),
                'requester': requester_info
            }
            
            # Add ride info if available
            if ride:
                req_data['ride'] = {
                    'id': str(ride['_id']),
                    'start_location': ride['start_location'],
                    'end_location': ride['end_location'],
                    'departure_time': ride['departure_time'].isoformat() if 'departure_time' in ride else None,
                    'available_seats': ride.get('available_seats', 0),
                    'status': ride['status']
                }
            
            # Add primary rider approval status
            if req.get('primary_rider_id'):
                primary_rider = users_collection.find_one({'_id': ObjectId(req['primary_rider_id'])})
                if primary_rider:
                    req_data['primary_rider'] = {
                        'id': str(primary_rider['_id']),
                        'name': primary_rider['name'],
                        'has_approved': req['status'] == 'primary_rider_accepted'
                    }
            
            result.append(req_data)
        
        return jsonify({
            'success': True,
            'count': len(result),
            'requests': result
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver pool requests: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver pool requests: {str(e)}'
        }), 400

# Route to mark a ride as shareable/not shareable
@app.route('/api/rides/<ride_id>/update-shareability', methods=['POST'])
@token_required
def update_ride_shareability(ride_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    # Get request data
    data = request.get_json()
    is_shareable = data.get('shareable', False)
    
    try:
        # Check if ride exists and belongs to user
        ride = rides_collection.find_one({
            '_id': ObjectId(ride_id),
            '$or': [
                {'driver_id': user_id},  # User is the driver
                {'riders.rider_id': user_id}  # User is a rider
            ]
        })
        
        if not ride:
            return jsonify({
                'success': False,
                'message': 'Ride not found or you do not have permission to update it'
            }), 404
        
        # Update ride shareability
        rides_collection.update_one(
            {'_id': ObjectId(ride_id)},
            {'$set': {
                'shareable': is_shareable,
                'updated_at': datetime.now()
            }}
        )
        
        return jsonify({
            'success': True,
            'message': f'Ride updated successfully. Shareability set to {is_shareable}'
        })
    
    except Exception as e:
        app.logger.error(f"Error updating ride shareability: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating ride shareability: {str(e)}'
        }), 400

# Route to check if a ride has pending pool requests
@app.route('/api/rides/<ride_id>/pending-pool-requests', methods=['GET'])
@token_required
def check_pending_pool_requests(ride_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    try:
        # Check if ride exists and user is involved
        ride = rides_collection.find_one({
            '_id': ObjectId(ride_id),
            '$or': [
                {'driver_id': user_id},  # User is the driver
                {'riders.rider_id': user_id}  # User is a rider
            ]
        })
        
        if not ride:
            return jsonify({
                'success': False,
                'message': 'Ride not found or you do not have permission to view it'
            }), 404
        
        # Check if there are any pending pool requests
        pool_requests_collection = db['pool_requests']
        
        # Different queries based on user role
        if ride.get('driver_id') == user_id:
            # Driver - check all pending requests
            pending_count = pool_requests_collection.count_documents({
                'ride_id': ride_id,
                'status': {'$in': ['pending', 'primary_rider_accepted']}
            })
        else:
            # Rider - check requests where they are the primary rider
            pending_count = pool_requests_collection.count_documents({
                'ride_id': ride_id,
                'primary_rider_id': user_id,
                'status': 'pending'
            })
        
        return jsonify({
            'success': True,
            'has_pending_requests': pending_count > 0,
            'pending_count': pending_count
        })
    
    except Exception as e:
        app.logger.error(f"Error checking pending pool requests: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error checking pending pool requests: {str(e)}'
        }), 400

# Dashboard endpoint for all users to see ride sharing benefits
@app.route('/api/users/rideshare-benefits', methods=['GET'])
@token_required
def get_rideshare_benefits():
    user = request.current_user
    user_id = str(user['_id'])
    
    try:
        # Get stats for rides where user was involved
        user_rides = list(rides_collection.find({
            '$or': [
                {'driver_id': user_id},  # User is the driver
                {'riders.rider_id': user_id}  # User is a rider
            ]
        }))
        
        # Calculate statistics
        total_rides = len(user_rides)
        shared_rides = sum(1 for ride in user_rides if ride.get('shareable', False))
        
        # Calculate environmental impact (simplified calculations)
        total_distance = sum(ride.get('distance_km', 5) for ride in user_rides)  # Default 5km if not available
        
        # Estimate savings from ride sharing
        co2_saved_kg = 0
        fuel_saved_liters = 0
        money_saved = 0
        
        for ride in user_rides:
            if ride.get('shareable', False) and ride.get('riders') and len(ride.get('riders', [])) > 1:
                # Count shared riders
                shared_riders = sum(1 for r in ride.get('riders', []) if r.get('is_shared', False))
                if shared_riders > 0:
                    distance = ride.get('distance_km', 5)
                    # Assume 0.2kg CO2 per km per person
                    co2_saved_kg += 0.2 * distance * shared_riders
                    # Assume 0.08 liters per km per person
                    fuel_saved_liters += 0.08 * distance * shared_riders
                    # Assume ₹15 per km per person
                    money_saved += 15 * distance * shared_riders
        
        return jsonify({
            'success': True,
            'stats': {
                'total_rides': total_rides,
                'shared_rides': shared_rides,
                'sharing_percentage': round((shared_rides / total_rides) * 100, 1) if total_rides > 0 else 0,
                'environmental_impact': {
                    'co2_saved_kg': round(co2_saved_kg, 1),
                    'fuel_saved_liters': round(fuel_saved_liters, 1),
                    'money_saved': round(money_saved, 2)
                }
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting rideshare benefits: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting rideshare benefits: {str(e)}'
        }), 400

# Add driver level and points fields to the user model in the database initialization
# This would typically be in your database setup code or migration script
'''
db.users.updateMany(
    { "user_type": "driver" },
    { $set: { 
        "driver_level": 1,
        "driver_points": 0,
        "driver_rewards": [],
        "points_history": []
    }}
)
'''

# Configuration for level requirements and rewards
DRIVER_LEVEL_CONFIG = {
    1: {"points_required": 0, "rewards": ["Basic Driver Badge"]},
    2: {"points_required": 1000, "rewards": ["Bronze Driver Badge", "5% Commission Reduction"]},
    3: {"points_required": 2000, "rewards": ["Silver Driver Badge", "10% Commission Reduction", "Priority Ride Matching"]},
    4: {"points_required": 4000, "rewards": ["Gold Driver Badge", "15% Commission Reduction", "VIP Support"]},
    5: {"points_required": 8000, "rewards": ["Platinum Driver Badge", "20% Commission Reduction", "VIP Support", "Weekly Bonus"]}
}

# Traffic zones configuration - these would be defined based on city data
TRAFFIC_ZONES = {
    "high": {"multiplier": 2.0, "areas": ["downtown", "tech_park", "airport"]},
    "medium": {"multiplier": 1.5, "areas": ["residential_dense", "shopping_district"]},
    "normal": {"multiplier": 1.0, "areas": ["suburbs", "residential_sparse"]}
}

# Points calculation constants
POINTS_BASE_RIDE_COMPLETION = 10
POINTS_SHARED_RIDE_BONUS = 5
POINTS_CANCELLATION_PENALTY = -20

# Function to calculate points for ride completion
def calculate_ride_completion_points(ride):
    base_points = POINTS_BASE_RIDE_COMPLETION
    
    # Check if the ride was in a high traffic zone
    end_location_area = determine_traffic_zone(ride['end_location'])
    traffic_multiplier = TRAFFIC_ZONES[end_location_area]['multiplier']
    
    # Check if it was a shared ride
    shared_bonus = 0
    if ride.get('shareable', False) and ride.get('riders'):
        shared_riders = sum(1 for rider in ride.get('riders', []) if rider.get('is_shared', False))
        if shared_riders > 0:
            shared_bonus = POINTS_SHARED_RIDE_BONUS * shared_riders
    
    # Calculate total points
    total_points = int((base_points * traffic_multiplier) + shared_bonus)
    
    return total_points

# Function to determine traffic zone based on location
def determine_traffic_zone(location):
    # This would use geocoding or predefined zones
    # For simplicity, we'll use a random assignment, but in production
    # this would use actual geospatial queries
    
    # Mock implementation - in real life this would use geographical data
    location_str = f"{location['lat']},{location['lng']}"
    location_hash = hash(location_str) % 100
    
    if location_hash < 30:
        return "high"
    elif location_hash < 70:
        return "medium"
    else:
        return "normal"

# Function to update driver points
def update_driver_points(driver_id, points_change, description, reference_id=None):
    # Create a points history entry
    points_entry = {
        'points_change': points_change,
        'description': description,
        'reference_id': reference_id,
        'timestamp': datetime.now()
    }
    
    # Update the driver's points and history
    users_collection.update_one(
        {'_id': ObjectId(driver_id)},
        {
            '$inc': {'driver_points': points_change},
            '$push': {'points_history': points_entry}
        }
    )

# Function to check if driver leveled up and update level if needed
def check_and_update_driver_level(driver_id):
    # Get the driver
    driver = users_collection.find_one({'_id': ObjectId(driver_id)})
    if not driver:
        return {'leveled_up': False}
    
    current_level = driver.get('driver_level', 1)
    current_points = driver.get('driver_points', 0)
    
    # Check if driver has enough points for next level
    next_level = current_level + 1
    if next_level in DRIVER_LEVEL_CONFIG and current_points >= DRIVER_LEVEL_CONFIG[next_level]['points_required']:
        # Driver has leveled up
        new_rewards = DRIVER_LEVEL_CONFIG[next_level]['rewards']
        
        # Update driver level and add new rewards
        users_collection.update_one(
            {'_id': ObjectId(driver_id)},
            {
                '$set': {'driver_level': next_level},
                '$push': {'driver_rewards': {'$each': new_rewards}}
            }
        )
        
        # Create a notification for the driver
        notification = {
            'user_id': driver_id,
            'type': 'level_up',
            'title': f'Congratulations! You reached Level {next_level}',
            'message': f'You\'ve earned new rewards: {", ".join(new_rewards)}',
            'created_at': datetime.now()
        }
        notifications_collection.insert_one(notification)
        
        return {
            'leveled_up': True,
            'new_level': next_level,
            'rewards': new_rewards
        }
    
    return {'leveled_up': False}

# Route to get driver level and points info
@app.route('/api/drivers/game-status', methods=['GET'])
@token_required
def get_driver_game_status():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get the driver's current status
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        current_level = driver.get('driver_level', 1)
        current_points = driver.get('driver_points', 0)
        
        # Get points required for next level
        next_level = current_level + 1
        points_for_next_level = DRIVER_LEVEL_CONFIG.get(next_level, {}).get('points_required', float('inf'))
        points_needed = max(0, points_for_next_level - current_points)
        
        # Get recent points history
        recent_history = []
        if 'points_history' in driver:
            recent_history = driver['points_history'][-10:]  # Last 10 entries
        
        # Get available rewards
        current_rewards = driver.get('driver_rewards', [])
        
        # Get level progress percentage
        current_level_points = DRIVER_LEVEL_CONFIG.get(current_level, {}).get('points_required', 0)
        if next_level in DRIVER_LEVEL_CONFIG:
            next_level_points = DRIVER_LEVEL_CONFIG[next_level]['points_required']
            progress_percentage = min(100, ((current_points - current_level_points) / 
                                           (next_level_points - current_level_points)) * 100)
        else:
            # Max level reached
            progress_percentage = 100
        
        return jsonify({
            'success': True,
            'game_status': {
                'current_level': current_level,
                'current_points': current_points,
                'next_level': next_level if next_level in DRIVER_LEVEL_CONFIG else None,
                'points_needed': points_needed if next_level in DRIVER_LEVEL_CONFIG else None,
                'progress_percentage': round(progress_percentage, 1),
                'rewards': current_rewards,
                'recent_history': [
                    {
                        'points_change': entry['points_change'],
                        'description': entry['description'],
                        'timestamp': entry['timestamp'].isoformat()
                    } for entry in recent_history
                ]
            },
            'all_levels': {
                level: {
                    'points_required': config['points_required'],
                    'rewards': config['rewards']
                }
                for level, config in DRIVER_LEVEL_CONFIG.items()
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver game status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver game status: {str(e)}'
        }), 400

# Route to get driver leaderboard
# Complete the leaderboard implementation
@app.route('/api/drivers/leaderboard', methods=['GET'])
@token_required
def get_driver_leaderboard():
    user = request.current_user
    
    # Get query parameters
    time_period = request.args.get('period', 'all_time')  # 'week', 'month', 'all_time'
    limit = int(request.args.get('limit', 10))
    
    try:
        # Build query based on time period
        query = {'user_type': 'driver'}
        
        if time_period == 'week':
            # Get drivers with rides in the last week
            one_week_ago = datetime.now() - timedelta(days=7)
            driver_ids = rides_collection.distinct('driver_id', {
                'created_at': {'$gte': one_week_ago}
            })
            query['_id'] = {'$in': [ObjectId(id) for id in driver_ids]}
        elif time_period == 'month':
            # Get drivers with rides in the last month
            one_month_ago = datetime.now() - timedelta(days=30)
            driver_ids = rides_collection.distinct('driver_id', {
                'created_at': {'$gte': one_month_ago}
            })
            query['_id'] = {'$in': [ObjectId(id) for id in driver_ids]}
        
        # Get top drivers by points
        top_drivers = list(users_collection.find(
            query,
            {'name': 1, 'driver_points': 1, 'driver_level': 1, 'profile_picture': 1}
        ).sort('driver_points', -1).limit(limit))
        
        # Format response
        leaderboard = []
        for i, driver in enumerate(top_drivers):
            leaderboard.append({
                'rank': i + 1,
                'driver_id': str(driver['_id']),
                'name': driver['name'],
                'profile_picture': driver.get('profile_picture', ''),
                'points': driver.get('driver_points', 0),
                'level': driver.get('driver_level', 1),
                'is_you': str(driver['_id']) == str(user['_id'])
            })
        
        # Get user's own rank if not in top list
        user_in_list = any(entry['is_you'] for entry in leaderboard)
        user_rank = None
        
        if not user_in_list and user.get('user_type') == 'driver':
            # Count drivers with more points than the current user
            higher_ranked_count = users_collection.count_documents({
                'user_type': 'driver',
                'driver_points': {'$gt': user.get('driver_points', 0)}
            })
            user_rank = higher_ranked_count + 1
            
            # Add user's entry to response
            user_entry = {
                'rank': user_rank,
                'driver_id': str(user['_id']),
                'name': user['name'],
                'profile_picture': user.get('profile_picture', ''),
                'points': user.get('driver_points', 0),
                'level': user.get('driver_level', 1),
                'is_you': True
            }
        
        return jsonify({
            'success': True,
            'leaderboard': leaderboard,
            'user_rank': user_rank,
            'user_entry': user_entry if not user_in_list and user.get('user_type') == 'driver' else None,
            'time_period': time_period
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver leaderboard: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver leaderboard: {str(e)}'
        }), 400

# Route to get special missions/challenges for drivers
@app.route('/api/drivers/challenges', methods=['GET'])
@token_required
def get_driver_challenges():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # In a real implementation, this would fetch from a challenges collection
        # For now, we'll generate some sample challenges based on the driver's level
        
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        driver_level = driver.get('driver_level', 1)
        now = datetime.now()
        
        # Generate challenges based on driver level
        daily_challenges = [
            {
                'id': f"daily_{now.strftime('%Y%m%d')}_1",
                'title': 'Complete 3 rides',
                'description': 'Complete 3 rides today',
                'points_reward': 50,
                'expires_at': (datetime(now.year, now.month, now.day) + timedelta(days=1)).isoformat(),
                'difficulty': 'easy',
                'progress': {
                    'current': 0,
                    'target': 3
                }
            },
            {
                'id': f"daily_{now.strftime('%Y%m%d')}_2",
                'title': 'High traffic area rides',
                'description': 'Complete 2 rides in high traffic areas',
                'points_reward': 75,
                'expires_at': (datetime(now.year, now.month, now.day) + timedelta(days=1)).isoformat(),
                'difficulty': 'medium',
                'progress': {
                    'current': 0,
                    'target': 2
                }
            }
        ]
        
        weekly_challenges = [
            {
                'id': f"weekly_{now.strftime('%Y%m%d')}_1",
                'title': 'Ride marathon',
                'description': f'Complete {5 + driver_level} rides this week',
                'points_reward': 150 * driver_level,
                'expires_at': (datetime(now.year, now.month, now.day) - timedelta(days=now.weekday()) + timedelta(days=7)).isoformat(),
                'difficulty': 'medium',
                'progress': {
                    'current': 0,
                    'target': 5 + driver_level
                }
            },
            {
                'id': f"weekly_{now.strftime('%Y%m%d')}_2",
                'title': 'Shared ride specialist',
                'description': 'Complete 3 shared rides',
                'points_reward': 200,
                'expires_at': (datetime(now.year, now.month, now.day) - timedelta(days=now.weekday()) + timedelta(days=7)).isoformat(),
                'difficulty': 'hard',
                'progress': {
                    'current': 0,
                    'target': 3
                }
            }
        ]
        
        # Add level-specific challenges
        if driver_level >= 3:
            weekly_challenges.append({
                'id': f"weekly_{now.strftime('%Y%m%d')}_premium",
                'title': 'Premium Service',
                'description': 'Maintain a 4.8+ rating for 10 consecutive rides',
                'points_reward': 300,
                'expires_at': (datetime(now.year, now.month, now.day) - timedelta(days=now.weekday()) + timedelta(days=7)).isoformat(),
                'difficulty': 'hard',
                'progress': {
                    'current': 0,
                    'target': 10
                }
            })
        
        # In a real implementation, we would track progress from the database
        # For now, we'll just return the challenges with zero progress
        
        return jsonify({
            'success': True,
            'challenges': {
                'daily': daily_challenges,
                'weekly': weekly_challenges
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver challenges: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver challenges: {str(e)}'
        }), 400

# Route to track challenge progress
@app.route('/api/drivers/challenges/<challenge_id>/progress', methods=['POST'])
@token_required
def update_challenge_progress(challenge_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get request data
        data = request.get_json()
        progress_value = data.get('progress', 1)  # Default increment by 1
        
        # In a real implementation, this would update a challenges collection
        # For now, we'll simulate a successful update
        
        # This simulates checking if the challenge is completed
        challenge_completed = True
        points_awarded = 50  # Default value
        
        if challenge_completed:
            # Award points to the driver
            update_driver_points(user_id, points_awarded, f"Completed challenge {challenge_id}", challenge_id)
            
            # Check if driver leveled up
            level_up_info = check_and_update_driver_level(user_id)
            
            return jsonify({
                'success': True,
                'message': 'Challenge progress updated',
                'challenge_completed': True,
                'points_awarded': points_awarded,
                'level_up_info': level_up_info if level_up_info['leveled_up'] else None
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Challenge progress updated',
                'challenge_completed': False
            })
    
    except Exception as e:
        app.logger.error(f"Error updating challenge progress: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating challenge progress: {str(e)}'
        }), 400

# Route to get driver statistics for gamification display
@app.route('/api/drivers/statistics', methods=['GET'])
@token_required
def get_driver_statistics():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get time period from query parameters
        time_period = request.args.get('period', 'month')  # 'week', 'month', 'year', 'all_time'
        
        # Calculate the start date based on time period
        now = datetime.now()
        if time_period == 'week':
            start_date = now - timedelta(days=7)
        elif time_period == 'month':
            start_date = now - timedelta(days=30)
        elif time_period == 'year':
            start_date = now - timedelta(days=365)
        else:  # all_time
            start_date = datetime(1970, 1, 1)  # Beginning of time
        
        # Get driver rides
        rides = list(rides_collection.find({
            'driver_id': user_id,
            'created_at': {'$gte': start_date}
        }))
        
        # Get driver points history
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        points_history = []
        if driver and 'points_history' in driver:
            points_history = [entry for entry in driver['points_history'] 
                             if entry['timestamp'] >= start_date]
        
        # Calculate statistics
        total_rides = len(rides)
        completed_rides = sum(1 for ride in rides if ride.get('status') == 'completed')
        cancelled_rides = sum(1 for ride in rides if ride.get('status') == 'cancelled' and ride.get('cancelled_by') == 'driver')
        shared_rides = sum(1 for ride in rides if ride.get('shareable', False) and ride.get('riders') and 
                          any(rider.get('is_shared', False) for rider in ride.get('riders', [])))
        
        high_traffic_rides = sum(1 for ride in rides if ride.get('status') == 'completed' and 
                                determine_traffic_zone(ride.get('end_location', {})) == 'high')
        
        total_points_earned = sum(entry['points_change'] for entry in points_history if entry['points_change'] > 0)
        total_points_lost = sum(abs(entry['points_change']) for entry in points_history if entry['points_change'] < 0)
        
        # Group points by day for chart data
        points_by_day = {}
        for entry in points_history:
            day_key = entry['timestamp'].strftime('%Y-%m-%d')
            if day_key not in points_by_day:
                points_by_day[day_key] = 0
            points_by_day[day_key] += entry['points_change']
        
        chart_data = [{'date': day, 'points': points} for day, points in sorted(points_by_day.items())]
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_rides': total_rides,
                'completed_rides': completed_rides,
                'cancelled_rides': cancelled_rides,
                'shared_rides': shared_rides,
                'high_traffic_rides': high_traffic_rides,
                'completion_rate': round(completed_rides / total_rides * 100, 1) if total_rides > 0 else 0,
                'total_points_earned': total_points_earned,
                'total_points_lost': total_points_lost,
                'net_points': total_points_earned - total_points_lost,
                'chart_data': chart_data
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver statistics: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver statistics: {str(e)}'
        }), 400

# Route to claim rewards
@app.route('/api/drivers/rewards/<reward_id>/claim', methods=['POST'])
@token_required
def claim_reward(reward_id):
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get the driver
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        # Check if driver has the reward
        driver_rewards = driver.get('driver_rewards', [])
        
        if reward_id not in driver_rewards:
            return jsonify({
                'success': False,
                'message': 'Reward not found or not available'
            }), 404
        
        # Check if reward has already been claimed
        claimed_rewards = driver.get('claimed_rewards', [])
        if reward_id in claimed_rewards:
            return jsonify({
                'success': False,
                'message': 'Reward already claimed'
            }), 400
        
        # Process the reward (this would vary based on reward type)
        # For this example, we'll just mark it as claimed
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$addToSet': {'claimed_rewards': reward_id}}
        )
        
        # Create a notification for the driver
        notification = {
            'user_id': user_id,
            'type': 'reward_claimed',
            'title': f'Reward Claimed: {reward_id}',
            'message': f'You have successfully claimed the reward: {reward_id}',
            'created_at': datetime.now()
        }
        notifications_collection.insert_one(notification)
        
        return jsonify({
            'success': True,
            'message': 'Reward claimed successfully',
            'reward_id': reward_id
        })
    
    except Exception as e:
        app.logger.error(f"Error claiming reward: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error claiming reward: {str(e)}'
        }), 400

# Route to get special achievements/badges for drivers
@app.route('/api/drivers/achievements', methods=['GET'])
@token_required
def get_driver_achievements():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get the driver
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        # Get driver statistics for achievement calculation
        # For a real app, this would be more sophisticated
        ride_count = rides_collection.count_documents({
            'driver_id': user_id,
            'status': 'completed'
        })
        
        shared_ride_count = rides_collection.count_documents({
            'driver_id': user_id,
            'status': 'completed',
            'shareable': True,
            'riders': {'$elemMatch': {'is_shared': True}}
        })
        
        high_traffic_ride_count = 0
        for ride in rides_collection.find({
            'driver_id': user_id,
            'status': 'completed'
        }):
            if determine_traffic_zone(ride.get('end_location', {})) == 'high':
                high_traffic_ride_count += 1
        
        # Define achievements
        all_achievements = [
            {
                'id': 'first_ride',
                'title': 'First Ride',
                'description': 'Complete your first ride',
                'icon': 'award',
                'unlocked': ride_count >= 1,
                'progress': min(1, ride_count),
                'target': 1
            },
            {
                'id': 'ride_10',
                'title': 'Rising Star',
                'description': 'Complete 10 rides',
                'icon': 'star',
                'unlocked': ride_count >= 10,
                'progress': min(10, ride_count),
                'target': 10
            },
            {
                'id': 'ride_50',
                'title': 'Road Warrior',
                'description': 'Complete 50 rides',
                'icon': 'shield',
                'unlocked': ride_count >= 50,
                'progress': min(50, ride_count),
                'target': 50
            },
            {
                'id': 'ride_100',
                'title': 'Centurion',
                'description': 'Complete 100 rides',
                'icon': 'trophy',
                'unlocked': ride_count >= 100,
                'progress': min(100, ride_count),
                'target': 100
            },
            {
                'id': 'shared_10',
                'title': 'Social Driver',
                'description': 'Complete 10 shared rides',
                'icon': 'users',
                'unlocked': shared_ride_count >= 10,
                'progress': min(10, shared_ride_count),
                'target': 10
            },
            {
                'id': 'traffic_master',
                'title': 'Traffic Navigator',
                'description': 'Complete 20 rides in high traffic areas',
                'icon': 'map',
                'unlocked': high_traffic_ride_count >= 20,
                'progress': min(20, high_traffic_ride_count),
                'target': 20
            }
        ]
        
        # Get driver's unlocked achievements
        unlocked_achievements = [a for a in all_achievements if a['unlocked']]
        locked_achievements = [a for a in all_achievements if not a['unlocked']]
        
        return jsonify({
            'success': True,
            'achievements': {
                'unlocked': unlocked_achievements,
                'locked': locked_achievements,
                'total': len(all_achievements),
                'unlocked_count': len(unlocked_achievements)
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver achievements: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver achievements: {str(e)}'
        }), 400

# Route to get nearby high traffic zones for earning more points
@app.route('/api/drivers/high-traffic-zones', methods=['GET'])
@token_required
def get_high_traffic_zones():
    user = request.current_user
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get current location from query parameters
        current_lat = float(request.args.get('lat', 0))
        current_lng = float(request.args.get('lng', 0))
        
        # In a real app, you'd use geospatial queries to find nearby high-traffic zones
        # For this example, we'll return some sample zones
        
        # These would typically come from a database of predefined zones
        # or be calculated in real-time based on current traffic data
        high_traffic_areas = [
            {
                'name': 'Downtown',
                'traffic_level': 'high',
                'points_multiplier': TRAFFIC_ZONES['high']['multiplier'],
                'location': {
                    'lat': current_lat + 0.01,  # Sample offset
                    'lng': current_lng + 0.01
                },
                'distance_km': 1.5,  # This would be calculated based on actual distance
                'estimated_time_min': 10
            },
            {
                'name': 'Tech Park',
                'traffic_level': 'high',
                'points_multiplier': TRAFFIC_ZONES['high']['multiplier'],
                'location': {
                    'lat': current_lat - 0.02,
                    'lng': current_lng + 0.02
                },
                'distance_km': 3.2,
                'estimated_time_min': 15
            },
            {
                'name': 'Airport',
                'traffic_level': 'high',
                'points_multiplier': TRAFFIC_ZONES['high']['multiplier'],
                'location': {
                    'lat': current_lat + 0.05,
                    'lng': current_lng - 0.03
                },
                'distance_km': 7.8,
                'estimated_time_min': 25
            }
        ]
        
        # Also include some medium traffic areas
        medium_traffic_areas = [
            {
                'name': 'Shopping District',
                'traffic_level': 'medium',
                'points_multiplier': TRAFFIC_ZONES['medium']['multiplier'],
                'location': {
                    'lat': current_lat + 0.008,
                    'lng': current_lng - 0.01
                },
                'distance_km': 1.2,
                'estimated_time_min': 8
            },
            {
                'name': 'Residential Area',
                'traffic_level': 'medium',
                'points_multiplier': TRAFFIC_ZONES['medium']['multiplier'],
                'location': {
                    'lat': current_lat - 0.01,
                    'lng': current_lng - 0.02
                },
                'distance_km': 2.5,
                'estimated_time_min': 12
            }
        ]
        
        return jsonify({
            'success': True,
            'traffic_zones': {
                'high': high_traffic_areas,
                'medium': medium_traffic_areas
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting high traffic zones: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting high traffic zones: {str(e)}'
        }), 400

# Route to get detailed point history with pagination
@app.route('/api/drivers/points-history', methods=['GET'])
@token_required
def get_points_history():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Get the driver
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        # Get points history
        points_history = driver.get('points_history', [])
        
        # Sort by timestamp (newest first)
        points_history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Calculate pagination
        total_items = len(points_history)
        total_pages = math.ceil(total_items / per_page)
        
        # Get paginated results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_history = points_history[start_idx:end_idx]
        
        # Format for response
        formatted_history = []
        for entry in paginated_history:
            formatted_entry = {
                'points_change': entry['points_change'],
                'description': entry['description'],
                'timestamp': entry['timestamp'].isoformat(),
                'reference_id': entry.get('reference_id')
            }
            
            # If there's a reference to a ride, add ride details
            if entry.get('reference_id') and entry['description'].startswith('Completed ride'):
                ride = rides_collection.find_one({'_id': ObjectId(entry['reference_id'])})
                if ride:
                    formatted_entry['ride_details'] = {
                        'pickup': ride.get('pickup_address', ''),
                        'dropoff': ride.get('dropoff_address', ''),
                        'distance': ride.get('distance_km', 0),
                        'duration': ride.get('duration_minutes', 0)
                    }
            
            formatted_history.append(formatted_entry)
        
        return jsonify({
            'success': True,
            'points_history': formatted_history,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting points history: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting points history: {str(e)}'
        }), 400

# Add a scheduled task to reset weekly/monthly points for leaderboards
# This would typically be implemented as a cron job or scheduled task
def reset_periodic_points():
    """
    Reset weekly and monthly points for leaderboard calculations.
    This function would be scheduled to run at appropriate intervals.
    """
    now = datetime.now()
    
    # Reset weekly points (run every Monday at midnight)
    if now.weekday() == 0 and now.hour == 0 and now.minute < 5:
        users_collection.update_many(
            {'user_type': 'driver'},
            {'$set': {'weekly_points': 0}}
        )
        app.logger.info("Weekly points reset successfully")
    
    # Reset monthly points (run on first day of month at midnight)
    if now.day == 1 and now.hour == 0 and now.minute < 5:
        users_collection.update_many(
            {'user_type': 'driver'},
            {'$set': {'monthly_points': 0}}
        )
        app.logger.info("Monthly points reset successfully")

# Function to update driver weekly and monthly points
def update_driver_periodic_points(driver_id, points_change):
    """
    Update a driver's weekly and monthly points for leaderboard calculations.
    Called whenever points are awarded or deducted.
    """
    users_collection.update_one(
        {'_id': ObjectId(driver_id)},
        {
            '$inc': {
                'weekly_points': points_change,
                'monthly_points': points_change
            }
        }
    )

# Update the original update_driver_points function to also update periodic points
# Update the original update_driver_points function to also update periodic points (continued)
def update_driver_points(driver_id, points_change, description, reference_id=None):
    # Create a points history entry
    points_entry = {
        'points_change': points_change,
        'description': description,
        'reference_id': reference_id,
        'timestamp': datetime.now()
    }
    
    # Update the driver's points and history
    users_collection.update_one(
        {'_id': ObjectId(driver_id)},
        {
            '$inc': {'driver_points': points_change},
            '$push': {'points_history': points_entry}
        }
    )
    
    # Also update weekly and monthly points for leaderboards
    update_driver_periodic_points(driver_id, points_change)

# Webhook for external integrations (e.g., connecting to a rewards vendor)
@app.route('/api/webhooks/driver-rewards', methods=['POST'])
def driver_rewards_webhook():
    # Validate webhook signature (in a real app, you'd implement proper security)
    webhook_token = request.headers.get('X-Webhook-Token')
    if not webhook_token or webhook_token != os.environ.get('WEBHOOK_SECRET'):
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 401
    
    try:
        data = request.get_json()
        event_type = data.get('event_type')
        driver_id = data.get('driver_id')
        
        if not event_type or not driver_id:
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        if event_type == 'reward_redeemed':
            # Update driver record when a reward is redeemed
            reward_id = data.get('reward_id')
            if not reward_id:
                return jsonify({
                    'success': False,
                    'message': 'Missing reward_id'
                }), 400
            
            users_collection.update_one(
                {'_id': ObjectId(driver_id)},
                {'$addToSet': {'redeemed_rewards': reward_id}}
            )
            
            # Create a notification
            notification = {
                'user_id': driver_id,
                'type': 'reward_redeemed',
                'title': 'Reward Redeemed',
                'message': f'Your reward {data.get("reward_name", "reward")} has been redeemed.',
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
            
            return jsonify({
                'success': True,
                'message': 'Reward redemption recorded'
            })
        
        elif event_type == 'special_promotion':
            # Add special promotion points to driver
            points = data.get('points', 0)
            description = data.get('description', 'Special promotion')
            
            update_driver_points(driver_id, points, description)
            
            # Create a notification
            notification = {
                'user_id': driver_id,
                'type': 'special_promotion',
                'title': 'Special Promotion',
                'message': f'You\'ve earned {points} points from a special promotion!',
                'created_at': datetime.now()
            }
            notifications_collection.insert_one(notification)
            
            return jsonify({
                'success': True,
                'message': 'Special promotion points added'
            })
        
        else:
            return jsonify({
                'success': False,
                'message': 'Unsupported event type'
            }), 400
    
    except Exception as e:
        app.logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing webhook: {str(e)}'
        }), 500

# Route to get driver next milestone
@app.route('/api/drivers/next-milestone', methods=['GET'])
@token_required
def get_driver_next_milestone():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get the driver
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        current_level = driver.get('driver_level', 1)
        current_points = driver.get('driver_points', 0)
        
        # Get points needed for next level
        next_level = current_level + 1
        if next_level in DRIVER_LEVEL_CONFIG:
            points_needed = max(0, DRIVER_LEVEL_CONFIG[next_level]['points_required'] - current_points)
            next_rewards = DRIVER_LEVEL_CONFIG[next_level]['rewards']
            
            # Calculate progress percentage
            current_level_points = DRIVER_LEVEL_CONFIG[current_level]['points_required']
            next_level_points = DRIVER_LEVEL_CONFIG[next_level]['points_required']
            total_points_needed = next_level_points - current_level_points
            points_earned = current_points - current_level_points
            progress_percentage = (points_earned / total_points_needed) * 100
            
            # Find the quickest way to get points
            points_per_ride = POINTS_BASE_RIDE_COMPLETION * TRAFFIC_ZONES['high']['multiplier']
            rides_needed = math.ceil(points_needed / points_per_ride)
            
            return jsonify({
                'success': True,
                'next_milestone': {
                    'current_level': current_level,
                    'next_level': next_level,
                    'points_needed': points_needed,
                    'progress_percentage': round(progress_percentage, 1),
                    'rewards': next_rewards,
                    'recommendation': {
                        'rides_needed': rides_needed,
                        'points_per_ride': points_per_ride,
                        'message': f"Complete {rides_needed} rides in high traffic areas to reach level {next_level}"
                    }
                }
            })
        else:
            # Driver has reached the maximum level
            return jsonify({
                'success': True,
                'next_milestone': {
                    'current_level': current_level,
                    'next_level': None,
                    'message': "Congratulations! You've reached the maximum level."
                }
            })
    
    except Exception as e:
        app.logger.error(f"Error getting driver next milestone: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver next milestone: {str(e)}'
        }), 400

# Route to get driver badges
@app.route('/api/drivers/badges', methods=['GET'])
@token_required
def get_driver_badges():
    user = request.current_user
    user_id = str(user['_id'])
    
    # Check if user is a driver
    if user.get('user_type') != 'driver':
        return jsonify({
            'success': False,
            'message': 'Only drivers can access this endpoint'
        }), 403
    
    try:
        # Get the driver
        driver = users_collection.find_one({'_id': ObjectId(user_id)})
        if not driver:
            return jsonify({
                'success': False,
                'message': 'Driver not found'
            }), 404
        
        # Get level-based badges
        level_badges = []
        current_level = driver.get('driver_level', 1)
        
        for level in range(1, current_level + 1):
            if level in DRIVER_LEVEL_CONFIG:
                badge = DRIVER_LEVEL_CONFIG[level]['rewards'][0]  # Assuming first reward is the badge
                level_badges.append({
                    'id': f"level_{level}_badge",
                    'name': badge,
                    'description': f"Reached driver level {level}",
                    'image_url': f"/badges/level_{level}.png",
                    'earned_at': driver.get('level_up_dates', {}).get(str(level), datetime.now().isoformat()),
                    'category': 'level'
                })
        
        # Get achievement badges
        achievements = driver.get('achievements', [])
        achievement_badges = []
        for achievement in achievements:
            achievement_badges.append({
                'id': achievement,
                'name': achievement.replace('_', ' ').title(),
                'description': f"Completed achievement: {achievement.replace('_', ' ').title()}",
                'image_url': f"/badges/achievement_{achievement}.png",
                'earned_at': driver.get('achievement_dates', {}).get(achievement, datetime.now().isoformat()),
                'category': 'achievement'
            })
        
        # Add special badges
        special_badges = []
        if driver.get('driver_points', 0) >= 10000:
            special_badges.append({
                'id': 'elite_driver',
                'name': 'Elite Driver',
                'description': 'Earned 10,000 or more driver points',
                'image_url': '/badges/elite_driver.png',
                'earned_at': datetime.now().isoformat(),
                'category': 'special'
            })
        
        # Combine all badges
        all_badges = level_badges + achievement_badges + special_badges
        
        return jsonify({
            'success': True,
            'badges': all_badges,
            'total_badges': len(all_badges),
            'badges_by_category': {
                'level': level_badges,
                'achievement': achievement_badges,
                'special': special_badges
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error getting driver badges: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting driver badges: {str(e)}'
        }), 400

# Function to initialize driver gamification system
def initialize_driver_gamification():
    """
    Initialize the driver gamification system - this would be run during app startup
    """
    app.logger.info("Initializing driver gamification system...")
    
    # Create indexes for efficient queries
    users_collection.create_index([('user_type', 1), ('driver_points', -1)])
    users_collection.create_index([('user_type', 1), ('weekly_points', -1)])
    users_collection.create_index([('user_type', 1), ('monthly_points', -1)])
    
    # Set up scheduled tasks
    # In a real app, you'd use a task scheduler like Celery or a cron job
    # For this example, we'll just log that initialization is complete
    
    app.logger.info("Driver gamification system initialized successfully")

# Add a health check endpoint for the gamification system
@app.route('/api/gamification/health', methods=['GET'])
def gamification_health_check():
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'level_config': len(DRIVER_LEVEL_CONFIG),
        'traffic_zones': len(TRAFFIC_ZONES)
    })

# Run the app
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    initialize_driver_gamification()
    app.run(host='0.0.0.0', port=port, debug=debug)