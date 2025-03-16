import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { 
  StyleSheet, 
  Text, 
  View, 
  TouchableOpacity, 
  FlatList, 
  ActivityIndicator, 
  SafeAreaView, 
  TextInput,
  Alert,
  Modal
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import MapView, { Marker } from 'react-native-maps';
import * as Location from 'expo-location';

// API configuration
const API_URL = 'https://your-api-url.com';

// Authentication token handling
const getAuthToken = async () => {
  try {
    return await AsyncStorage.getItem('authToken');
  } catch (error) {
    console.error('Error getting auth token:', error);
    return null;
  }
}

// Create the axios instance with interceptors for auth token
const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use(
  async (config) => {
    const token = await getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Stack and Tab navigators
const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

// Login Screen
const LoginScreen = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Error', 'Please enter both email and password.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/api/auth/login', {
        email,
        password,
      });

      if (response.data.success) {
        await AsyncStorage.setItem('authToken', response.data.token);
        await AsyncStorage.setItem('userId', response.data.user_id);
        setLoading(false);
        navigation.replace('Main');
      } else {
        Alert.alert('Login Failed', response.data.message);
        setLoading(false);
      }
    } catch (error) {
      console.error('Login error:', error);
      Alert.alert('Login Failed', error.response?.data?.message || 'An error occurred during login.');
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Ride Pool App</Text>
      <View style={styles.formContainer}>
        <TextInput
          style={styles.input}
          placeholder="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />
        <TouchableOpacity 
          style={styles.button} 
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Login</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity onPress={() => navigation.navigate('Register')}>
          <Text style={styles.linkText}>New user? Register here</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

// Register Screen
const RegisterScreen = ({ navigation }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [userType, setUserType] = useState('rider'); // 'rider' or 'driver'
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    if (!name || !email || !password || !confirmPassword) {
      Alert.alert('Error', 'Please fill all fields.');
      return;
    }

    if (password !== confirmPassword) {
      Alert.alert('Error', 'Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/api/auth/register', {
        name,
        email,
        password,
        user_type: userType,
      });

      if (response.data.success) {
        Alert.alert('Success', 'Registration successful! Please login.');
        setLoading(false);
        navigation.navigate('Login');
      } else {
        Alert.alert('Registration Failed', response.data.message);
        setLoading(false);
      }
    } catch (error) {
      console.error('Registration error:', error);
      Alert.alert('Registration Failed', error.response?.data?.message || 'An error occurred during registration.');
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Create Account</Text>
      <View style={styles.formContainer}>
        <TextInput
          style={styles.input}
          placeholder="Full Name"
          value={name}
          onChangeText={setName}
        />
        <TextInput
          style={styles.input}
          placeholder="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />
        <TextInput
          style={styles.input}
          placeholder="Confirm Password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
        />
        <View style={styles.userTypeContainer}>
          <Text>I am a:</Text>
          <View style={styles.radioContainer}>
            <TouchableOpacity
              style={[styles.radioButton, userType === 'rider' && styles.radioButtonSelected]}
              onPress={() => setUserType('rider')}
            >
              <Text style={[styles.radioText, userType === 'rider' && styles.radioTextSelected]}>Rider</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.radioButton, userType === 'driver' && styles.radioButtonSelected]}
              onPress={() => setUserType('driver')}
            >
              <Text style={[styles.radioText, userType === 'driver' && styles.radioTextSelected]}>Driver</Text>
            </TouchableOpacity>
          </View>
        </View>
        <TouchableOpacity 
          style={styles.button} 
          onPress={handleRegister}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Register</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity onPress={() => navigation.navigate('Login')}>
          <Text style={styles.linkText}>Already have an account? Login</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

// Home Screen
const HomeScreen = ({ navigation }) => {
  const [availableRides, setAvailableRides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userType, setUserType] = useState('');

  useEffect(() => {
    const getUserType = async () => {
      try {
        const type = await AsyncStorage.getItem('userType');
        setUserType(type || 'rider');
      } catch (error) {
        console.error('Error getting user type:', error);
      }
    };

    const fetchAvailableRides = async () => {
      try {
        const response = await api.get('/api/rides/available');
        if (response.data.success) {
          setAvailableRides(response.data.rides);
        }
      } catch (error) {
        console.error('Error fetching available rides:', error);
        Alert.alert('Error', 'Failed to load available rides');
      } finally {
        setLoading(false);
      }
    };

    getUserType();
    fetchAvailableRides();
  }, []);

  const renderRideItem = ({ item }) => (
    <TouchableOpacity 
      style={styles.rideCard}
      onPress={() => navigation.navigate('RideDetails', { ride: item })}
    >
      <View style={styles.rideCardHeader}>
        <Text style={styles.rideTitle}>
          {item.start_location.address.substring(0, 20)}... → {item.end_location.address.substring(0, 20)}...
        </Text>
        <Text style={styles.rideTime}>
          {new Date(item.departure_time).toLocaleTimeString()}
        </Text>
      </View>
      <View style={styles.rideCardDetails}>
        <Text style={styles.rideDetailText}>Available seats: {item.available_seats}</Text>
        <Text style={styles.rideDetailText}>Shareable: {item.shareable ? 'Yes' : 'No'}</Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Available Rides</Text>
      {loading ? (
        <ActivityIndicator size="large" color="#0000ff" />
      ) : (
        <FlatList
          data={availableRides}
          renderItem={renderRideItem}
          keyExtractor={item => item._id}
          style={styles.list}
          ListEmptyComponent={
            <View style={styles.emptyListContainer}>
              <Text style={styles.emptyListText}>No available rides at the moment</Text>
            </View>
          }
        />
      )}
      {userType === 'driver' && (
        <TouchableOpacity 
          style={styles.floatingButton}
          onPress={() => navigation.navigate('CreateRide')}
        >
          <Ionicons name="add" size={24} color="white" />
        </TouchableOpacity>
      )}
    </SafeAreaView>
  );
};

// Ride Details Screen - for passengers to request pool
const RideDetailsScreen = ({ route, navigation }) => {
  const { ride } = route.params;
  const [neededSeats, setNeededSeats] = useState(1);
  const [pickupLocation, setPickupLocation] = useState(null);
  const [dropoffLocation, setDropoffLocation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [locationType, setLocationType] = useState('pickup'); // 'pickup' or 'dropoff'
  const [mapRegion, setMapRegion] = useState({
    latitude: 37.78825,
    longitude: -122.4324,
    latitudeDelta: 0.0922,
    longitudeDelta: 0.0421,
  });

  useEffect(() => {
    (async () => {
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Permission to access location was denied');
        return;
      }

      let location = await Location.getCurrentPositionAsync({});
      setMapRegion({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        latitudeDelta: 0.0922,
        longitudeDelta: 0.0421,
      });
    })();
  }, []);

  const handleSelectLocation = async (event) => {
    const { latitude, longitude } = event.nativeEvent.coordinate;
    
    try {
      const response = await Location.reverseGeocodeAsync({
        latitude,
        longitude
      });
      
      const address = response[0] ? 
        `${response[0].name}, ${response[0].street}, ${response[0].city}, ${response[0].region}` : 
        `${latitude}, ${longitude}`;
      
      const locationData = {
        latitude,
        longitude,
        address
      };
      
      if (locationType === 'pickup') {
        setPickupLocation(locationData);
      } else {
        setDropoffLocation(locationData);
      }
      
      setShowLocationModal(false);
    } catch (error) {
      console.error('Error getting location address:', error);
      Alert.alert('Error', 'Failed to get location address');
    }
  };

  const openLocationPicker = (type) => {
    setLocationType(type);
    setShowLocationModal(true);
  };

  const handleRequestPool = async () => {
    if (!pickupLocation || !dropoffLocation) {
      Alert.alert('Error', 'Please select both pickup and dropoff locations');
      return;
    }

    if (neededSeats < 1 || neededSeats > ride.available_seats) {
      Alert.alert('Error', `Please select between 1 and ${ride.available_seats} seats`);
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/api/rides/${ride._id}/request-pool`, {
        needed_seats: neededSeats,
        pickup_location: pickupLocation,
        dropoff_location: dropoffLocation
      });

      if (response.data.success) {
        Alert.alert('Success', 'Pool request submitted successfully');
        navigation.navigate('MyRequests');
      } else {
        Alert.alert('Error', response.data.message);
      }
    } catch (error) {
      console.error('Error requesting ride pool:', error);
      Alert.alert('Error', error.response?.data?.message || 'Failed to submit pool request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.detailCard}>
        <Text style={styles.detailTitle}>Ride Details</Text>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>From:</Text>
          <Text style={styles.detailText}>{ride.start_location.address}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>To:</Text>
          <Text style={styles.detailText}>{ride.end_location.address}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Departure:</Text>
          <Text style={styles.detailText}>{new Date(ride.departure_time).toLocaleString()}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Available Seats:</Text>
          <Text style={styles.detailText}>{ride.available_seats}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Shareable:</Text><Text style={styles.detailText}>{ride.shareable ? 'Yes' : 'No'}</Text>
          </View>
        </View>
  
        <Text style={styles.sectionTitle}>Request to Join Pool</Text>
        <View style={styles.formContainer}>
          <View style={styles.formRow}>
            <Text style={styles.formLabel}>Seats Needed:</Text>
            <View style={styles.counterContainer}>
              <TouchableOpacity 
                style={styles.counterButton}
                onPress={() => setNeededSeats(Math.max(1, neededSeats - 1))}
              >
                <Text style={styles.counterButtonText}>-</Text>
              </TouchableOpacity>
              <Text style={styles.counterText}>{neededSeats}</Text>
              <TouchableOpacity 
                style={styles.counterButton}
                onPress={() => setNeededSeats(Math.min(ride.available_seats, neededSeats + 1))}
              >
                <Text style={styles.counterButtonText}>+</Text>
              </TouchableOpacity>
            </View>
          </View>
  
          <View style={styles.formRow}>
            <Text style={styles.formLabel}>Pickup Location:</Text>
            <TouchableOpacity 
              style={styles.locationButton}
              onPress={() => openLocationPicker('pickup')}
            >
              <Text style={styles.locationButtonText}>
                {pickupLocation ? pickupLocation.address.substring(0, 25) + '...' : 'Select Location'}
              </Text>
            </TouchableOpacity>
          </View>
  
          <View style={styles.formRow}>
            <Text style={styles.formLabel}>Dropoff Location:</Text>
            <TouchableOpacity 
              style={styles.locationButton}
              onPress={() => openLocationPicker('dropoff')}
            >
              <Text style={styles.locationButtonText}>
                {dropoffLocation ? dropoffLocation.address.substring(0, 25) + '...' : 'Select Location'}
              </Text>
            </TouchableOpacity>
          </View>
  
          <TouchableOpacity 
            style={[styles.button, (!pickupLocation || !dropoffLocation) && styles.buttonDisabled]}
            onPress={handleRequestPool}
            disabled={loading || !pickupLocation || !dropoffLocation}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Request Pool</Text>
            )}
          </TouchableOpacity>
        </View>
  
        <Modal
          visible={showLocationModal}
          animationType="slide"
          transparent={false}
        >
          <SafeAreaView style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                Select {locationType === 'pickup' ? 'Pickup' : 'Dropoff'} Location
              </Text>
              <TouchableOpacity onPress={() => setShowLocationModal(false)}>
                <Ionicons name="close" size={24} color="black" />
              </TouchableOpacity>
            </View>
            <MapView
              style={styles.map}
              region={mapRegion}
              onPress={handleSelectLocation}
            >
              {locationType === 'pickup' && pickupLocation && (
                <Marker
                  coordinate={{
                    latitude: pickupLocation.latitude,
                    longitude: pickupLocation.longitude
                  }}
                  pinColor="green"
                  title="Pickup Location"
                />
              )}
              {locationType === 'dropoff' && dropoffLocation && (
                <Marker
                  coordinate={{
                    latitude: dropoffLocation.latitude,
                    longitude: dropoffLocation.longitude
                  }}
                  pinColor="red"
                  title="Dropoff Location"
                />
              )}
            </MapView>
            <View style={styles.modalFooter}>
              <TouchableOpacity 
                style={styles.modalButton}
                onPress={() => setShowLocationModal(false)}
              >
                <Text style={styles.modalButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </SafeAreaView>
        </Modal>
      </SafeAreaView>
    );
  };
  
  // My Requests Screen
  const MyRequestsScreen = () => {
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
  
    const fetchRequests = async () => {
      try {
        const response = await api.get('/api/users/pool-requests');
        if (response.data.success) {
          setRequests(response.data.requests);
        }
      } catch (error) {
        console.error('Error fetching pool requests:', error);
        Alert.alert('Error', 'Failed to load your pool requests');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    };
  
    useEffect(() => {
      fetchRequests();
    }, []);
  
    const onRefresh = () => {
      setRefreshing(true);
      fetchRequests();
    };
  
    const getStatusColor = (status) => {
      switch (status) {
        case 'accepted':
          return '#4CAF50'; // Green
        case 'primary_rider_accepted':
          return '#FFC107'; // Yellow
        case 'rejected_by_driver':
        case 'rejected_by_primary_rider':
          return '#F44336'; // Red
        case 'pending':
        default:
          return '#2196F3'; // Blue
      }
    };
  
    const getStatusText = (status) => {
      switch (status) {
        case 'accepted':
          return 'Accepted';
        case 'primary_rider_accepted':
          return 'Approved by rider, waiting for driver';
        case 'rejected_by_driver':
          return 'Rejected by driver';
        case 'rejected_by_primary_rider':
          return 'Rejected by primary rider';
        case 'pending':
        default:
          return 'Pending';
      }
    };
  
    const renderRequestItem = ({ item }) => (
      <View style={styles.requestCard}>
        <View style={styles.requestCardHeader}>
          <Text style={styles.requestCardTitle}>Request #{item.id.substring(0, 6)}</Text>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
            <Text style={styles.statusText}>{getStatusText(item.status)}</Text>
          </View>
        </View>
        <View style={styles.requestCardDetails}>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>From:</Text>
            <Text style={styles.detailText}>{item.pickup_location.address}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>To:</Text>
            <Text style={styles.detailText}>{item.dropoff_location.address}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Seats:</Text>
            <Text style={styles.detailText}>{item.needed_seats}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Requested:</Text>
            <Text style={styles.detailText}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
        </View>
      </View>
    );
  
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.title}>My Pool Requests</Text>
        {loading ? (
          <ActivityIndicator size="large" color="#0000ff" />
        ) : (
          <FlatList
            data={requests}
            renderItem={renderRequestItem}
            keyExtractor={item => item.id}
            style={styles.list}
            refreshing={refreshing}
            onRefresh={onRefresh}
            ListEmptyComponent={
              <View style={styles.emptyListContainer}>
                <Text style={styles.emptyListText}>You have no pool requests</Text>
              </View>
            }
          />
        )}
      </SafeAreaView>
    );
  };
  
  // Notifications Screen
  const NotificationsScreen = () => {
    const [notifications, setNotifications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
  
    const fetchNotifications = async () => {
      try {
        const response = await api.get('/api/users/notifications');
        if (response.data.success) {
          setNotifications(response.data.notifications);
        }
      } catch (error) {
        console.error('Error fetching notifications:', error);
        Alert.alert('Error', 'Failed to load notifications');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    };
  
    useEffect(() => {
      fetchNotifications();
    }, []);
  
    const onRefresh = () => {
      setRefreshing(true);
      fetchNotifications();
    };
  
    const handlePoolRequest = async (notification, action) => {
      if (notification.type !== 'pool_request') return;
      
      try {
        const userType = await AsyncStorage.getItem('userType');
        const endpoint = userType === 'driver' 
          ? `/api/pool-requests/${notification.pool_request_id}/driver-action`
          : `/api/pool-requests/${notification.pool_request_id}/primary-rider-action`;
        
        const response = await api.post(endpoint, { action });
        
        if (response.data.success) {
          Alert.alert('Success', response.data.message);
          fetchNotifications();
        } else {
          Alert.alert('Error', response.data.message);
        }
      } catch (error) {
        console.error('Error handling pool request:', error);
        Alert.alert('Error', error.response?.data?.message || 'Failed to process request');
      }
    };
  
    const renderNotificationItem = ({ item }) => (
      <View style={styles.notificationCard}>
        <View style={styles.notificationHeader}>
          <Text style={styles.notificationTitle}>{item.title}</Text>
          <Text style={styles.notificationTime}>{new Date(item.created_at).toLocaleTimeString()}</Text>
        </View>
        <Text style={styles.notificationMessage}>{item.message}</Text>
        
        {item.type === 'pool_request' && (
          <View style={styles.actionButtons}>
            <TouchableOpacity
              style={[styles.actionButton, styles.acceptButton]}
              onPress={() => handlePoolRequest(item, 'accept')}
            >
              <Text style={styles.actionButtonText}>Accept</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionButton, styles.rejectButton]}
              onPress={() => handlePoolRequest(item, 'reject')}
            >
              <Text style={styles.actionButtonText}>Reject</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.title}>Notifications</Text>
        {loading ? (
          <ActivityIndicator size="large" color="#0000ff" />
        ) : (
          <FlatList
            data={notifications}
            renderItem={renderNotificationItem}
            keyExtractor={item => item._id}
            style={styles.list}
            refreshing={refreshing}
            onRefresh={onRefresh}
            ListEmptyComponent={
              <View style={styles.emptyListContainer}>
                <Text style={styles.emptyListText}>No notifications</Text>
              </View>
            }
          />
        )}
      </SafeAreaView>
    );
  };
  
  // Profile Screen
  const ProfileScreen = ({ navigation }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
  
    useEffect(() => {
      const fetchUserProfile = async () => {
        try {
          const response = await api.get('/api/users/profile');
          if (response.data.success) {
            setUser(response.data.user);
          }
        } catch (error) {
          console.error('Error fetching user profile:', error);
          Alert.alert('Error', 'Failed to load user profile');
        } finally {
          setLoading(false);
        }
      };
  
      fetchUserProfile();
    }, []);
  
    const handleLogout = async () => {
      try {
        await AsyncStorage.removeItem('authToken');
        await AsyncStorage.removeItem('userId');
        await AsyncStorage.removeItem('userType');
        navigation.reset({
          index: 0,
          routes: [{ name: 'Auth' }],
        });
      } catch (error) {
        console.error('Error logging out:', error);
        Alert.alert('Error', 'Failed to log out');
      }
    };
  
    if (loading) {
      return (
        <SafeAreaView style={styles.container}>
          <ActivityIndicator size="large" color="#0000ff" />
        </SafeAreaView>
      );
    }
  
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.profileHeader}>
          <View style={styles.profileImageContainer}>
            <Text style={styles.profileImageText}>
              {user?.name ? user.name.charAt(0).toUpperCase() : '?'}
            </Text>
          </View>
          <Text style={styles.profileName}>{user?.name || 'User'}</Text>
          <Text style={styles.profileEmail}>{user?.email || 'No email'}</Text>
          <View style={styles.userTypeBadge}>
            <Text style={styles.userTypeText}>{user?.user_type === 'driver' ? 'Driver' : 'Rider'}</Text>
          </View>
        </View>
  
        <View style={styles.profileDetails}>
          <TouchableOpacity style={styles.profileOption}>
            <Ionicons name="person-outline" size={24} color="#333" />
            <Text style={styles.profileOptionText}>Edit Profile</Text>
            <Ionicons name="chevron-forward" size={24} color="#ccc" />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.profileOption}>
            <Ionicons name="settings-outline" size={24} color="#333" />
            <Text style={styles.profileOptionText}>Settings</Text>
            <Ionicons name="chevron-forward" size={24} color="#ccc" />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.profileOption}>
            <Ionicons name="help-circle-outline" size={24} color="#333" />
            <Text style={styles.profileOptionText}>Help & Support</Text>
            <Ionicons name="chevron-forward" size={24} color="#ccc" />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.profileOption} onPress={handleLogout}>
            <Ionicons name="log-out-outline" size={24} color="#f44336" />
            <Text style={[styles.profileOptionText, { color: '#f44336' }]}>Log Out</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  };
  
  // Tab Navigator
  const MainTabNavigator = () => {
    return (
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => {
            let iconName;
            
            if (route.name === 'Home') {
            iconName = focused ? 'home' : 'home-outline';
          } else if (route.name === 'My Requests') {
            iconName = focused ? 'list' : 'list-outline';
          } else if (route.name === 'Notifications') {
            iconName = focused ? 'notifications' : 'notifications-outline';
          } else if (route.name === 'Profile') {
            iconName = focused ? 'person' : 'person-outline';
          }
          
          return <Ionicons name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#2196F3',
        tabBarInactiveTintColor: 'gray',
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="My Requests" component={MyRequestsScreen} />
      <Tab.Screen name="Notifications" component={NotificationsScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
};

// Create Ride Screen (for drivers)
const CreateRideScreen = ({ navigation }) => {
  const [pickupLocation, setPickupLocation] = useState(null);
  const [dropoffLocation, setDropoffLocation] = useState(null);
  const [departureDate, setDepartureDate] = useState(new Date());
  const [availableSeats, setAvailableSeats] = useState(1);
  const [shareable, setShareable] = useState(true);
  const [fareAmount, setFareAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [locationType, setLocationType] = useState('pickup'); // 'pickup' or 'dropoff'
  const [mapRegion, setMapRegion] = useState({
    latitude: 37.78825,
    longitude: -122.4324,
    latitudeDelta: 0.0922,
    longitudeDelta: 0.0421,
  });

  useEffect(() => {
    (async () => {
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Permission to access location was denied');
        return;
      }

      let location = await Location.getCurrentPositionAsync({});
      setMapRegion({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        latitudeDelta: 0.0922,
        longitudeDelta: 0.0421,
      });
    })();
  }, []);

  const handleSelectLocation = async (event) => {
    const { latitude, longitude } = event.nativeEvent.coordinate;
    
    try {
      const response = await Location.reverseGeocodeAsync({
        latitude,
        longitude
      });
      
      const address = response[0] ? 
        `${response[0].name}, ${response[0].street}, ${response[0].city}, ${response[0].region}` : 
        `${latitude}, ${longitude}`;
      
      const locationData = {
        latitude,
        longitude,
        address
      };
      
      if (locationType === 'pickup') {
        setPickupLocation(locationData);
      } else {
        setDropoffLocation(locationData);
      }
      
      setShowLocationModal(false);
    } catch (error) {
      console.error('Error getting location address:', error);
      Alert.alert('Error', 'Failed to get location address');
    }
  };

  const openLocationPicker = (type) => {
    setLocationType(type);
    setShowLocationModal(true);
  };

  const handleCreateRide = async () => {
    if (!pickupLocation || !dropoffLocation) {
      Alert.alert('Error', 'Please select both pickup and dropoff locations');
      return;
    }

    if (availableSeats < 1) {
      Alert.alert('Error', 'Please set at least 1 available seat');
      return;
    }

    if (!fareAmount || isNaN(parseFloat(fareAmount))) {
      Alert.alert('Error', 'Please enter a valid fare amount');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/api/rides', {
        start_location: pickupLocation,
        end_location: dropoffLocation,
        departure_time: departureDate.toISOString(),
        available_seats: availableSeats,
        shareable,
        fare: parseFloat(fareAmount)
      });

      if (response.data.success) {
        Alert.alert('Success', 'Ride created successfully');
        navigation.goBack();
      } else {
        Alert.alert('Error', response.data.message);
      }
    } catch (error) {
      console.error('Error creating ride:', error);
      Alert.alert('Error', error.response?.data?.message || 'Failed to create ride');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Create New Ride</Text>
      <View style={styles.formContainer}>
        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Pickup Location:</Text>
          <TouchableOpacity 
            style={styles.locationButton}
            onPress={() => openLocationPicker('pickup')}
          >
            <Text style={styles.locationButtonText}>
              {pickupLocation ? pickupLocation.address.substring(0, 25) + '...' : 'Select Location'}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Dropoff Location:</Text>
          <TouchableOpacity 
            style={styles.locationButton}
            onPress={() => openLocationPicker('dropoff')}
          >
            <Text style={styles.locationButtonText}>
              {dropoffLocation ? dropoffLocation.address.substring(0, 25) + '...' : 'Select Location'}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Departure Date:</Text>
          <TouchableOpacity style={styles.dateButton}>
            <Text style={styles.dateButtonText}>
              {departureDate.toLocaleString()}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Available Seats:</Text>
          <View style={styles.counterContainer}>
            <TouchableOpacity 
              style={styles.counterButton}
              onPress={() => setAvailableSeats(Math.max(1, availableSeats - 1))}
            >
              <Text style={styles.counterButtonText}>-</Text>
            </TouchableOpacity>
            <Text style={styles.counterText}>{availableSeats}</Text>
            <TouchableOpacity 
              style={styles.counterButton}
              onPress={() => setAvailableSeats(availableSeats + 1)}
            >
              <Text style={styles.counterButtonText}>+</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Fare Amount ($):</Text>
          <TextInput
            style={styles.input}
            value={fareAmount}
            onChangeText={setFareAmount}
            keyboardType="numeric"
            placeholder="Enter fare amount"
          />
        </View>

        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Shareable:</Text>
          <View style={styles.switchContainer}>
            <TouchableOpacity
              style={[styles.switchOption, shareable && styles.switchOptionSelected]}
              onPress={() => setShareable(true)}
            >
              <Text style={[styles.switchText, shareable && styles.switchTextSelected]}>Yes</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.switchOption, !shareable && styles.switchOptionSelected]}
              onPress={() => setShareable(false)}
            >
              <Text style={[styles.switchText, !shareable && styles.switchTextSelected]}>No</Text>
            </TouchableOpacity>
          </View>
        </View>

        <TouchableOpacity 
          style={[styles.button, (!pickupLocation || !dropoffLocation) && styles.buttonDisabled]}
          onPress={handleCreateRide}
          disabled={loading || !pickupLocation || !dropoffLocation}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Create Ride</Text>
          )}
        </TouchableOpacity>
      </View>

      <Modal
        visible={showLocationModal}
        animationType="slide"
        transparent={false}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>
              Select {locationType === 'pickup' ? 'Pickup' : 'Dropoff'} Location
            </Text>
            <TouchableOpacity onPress={() => setShowLocationModal(false)}>
              <Ionicons name="close" size={24} color="black" />
            </TouchableOpacity>
          </View>
          <MapView
            style={styles.map}
            region={mapRegion}
            onPress={handleSelectLocation}
          >
            {locationType === 'pickup' && pickupLocation && (
              <Marker
                coordinate={{
                  latitude: pickupLocation.latitude,
                  longitude: pickupLocation.longitude
                }}
                pinColor="green"
                title="Pickup Location"
              />
            )}
            {locationType === 'dropoff' && dropoffLocation && (
              <Marker
                coordinate={{
                  latitude: dropoffLocation.latitude,
                  longitude: dropoffLocation.longitude
                }}
                pinColor="red"
                title="Dropoff Location"
              />
            )}
          </MapView>
          <View style={styles.modalFooter}>
            <TouchableOpacity 
              style={styles.modalButton}
              onPress={() => setShowLocationModal(false)}
            >
              <Text style={styles.modalButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
};

// Main Navigation
const App = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Auth">
        <Stack.Screen 
          name="Auth" 
          component={AuthNavigator} 
          options={{ headerShown: false }}
        />
        <Stack.Screen 
          name="Main" 
          component={MainTabNavigator} 
          options={{ headerShown: false }}
        />
        <Stack.Screen name="RideDetails" component={RideDetailsScreen} options={{ title: 'Ride Details' }} />
        <Stack.Screen name="CreateRide" component={CreateRideScreen} options={{ title: 'Create Ride' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
};

// Auth Navigator
const AuthNavigator = () => {
  return (
    <Stack.Navigator initialRouteName="Login" screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen name="Register" component={RegisterScreen} />
    </Stack.Navigator>
  );
};

// Styles
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 16,
    color: '#333',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 16,
    marginBottom: 8,
    color: '#333',
  },
  formContainer: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  formRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  formLabel: {
    fontSize: 16,
    color: '#333',
    flex: 1,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 4,
    padding: 8,
    flex: 2,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#2196F3',
    padding: 16,
    borderRadius: 4,
    alignItems: 'center',
    marginTop: 16,
  },
  buttonDisabled: {
    backgroundColor: '#B0BEC5',
  },
  buttonText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16,
  },
  linkText: {
    color: '#2196F3',
    textAlign: 'center',
    marginTop: 16,
  },
  rideCard: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  rideCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  rideTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    flex: 1,
  },
  rideTime: {
    fontSize: 14,
    color: '#757575',
  },
  rideCardDetails: {
    marginTop: 8,
  },
  rideDetailText: {
    fontSize: 14,
    color: '#757575',
    marginBottom: 4,
  },
  list: {
    flex: 1,
  },
  emptyListContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  emptyListText: {
    fontSize: 16,
    color: '#757575',
    textAlign: 'center',
  },
  floatingButton: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#2196F3',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  requestCard: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  requestCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  requestCardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  requestCardDetails: {
    marginTop: 8,
  },
  detailCard: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  detailTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 12,
    color: '#333',
  },
  detailRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  detailLabel: {
    fontWeight: 'bold',
    width: 100,
    color: '#333',
  },
  detailText: {
    flex: 1,
    color: '#555',
  },
  counterContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: 120,
  },
  counterButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#2196F3',
    justifyContent: 'center',
    alignItems: 'center',
  },
  counterButtonText: {
    color: '#fff',
    fontSize: 20,
    fontWeight: 'bold',
  },
  counterText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    width: 30,
    textAlign: 'center',
  },
  locationButton: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 4,
    padding: 8,
    flex: 2,
  },
  locationButtonText: {
    color: '#333',
  },
  map: {
    width: '100%',
    height: '100%',
    flex: 1,
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  modalFooter: {
    padding: 16,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#ddd',
    flexDirection: 'row',
    justifyContent: 'center',
  },
  modalButton: {
    backgroundColor: '#2196F3',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 4,
  },
  modalButtonText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16,
  },
  notificationCard: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  notificationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  notificationTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  notificationTime: {
    fontSize: 14,
    color: '#757575',
  },
  notificationMessage: {
    fontSize: 14,
    color: '#555',
    marginBottom: 12,
  },
  actionButtons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
  },
  actionButton: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 4,
    marginLeft: 8,
  },
  acceptButton: {
    backgroundColor: '#4CAF50',
  },
  rejectButton: {
    backgroundColor: '#F44336',
  },
  actionButtonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  statusBadge: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
  },
  statusText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  userTypeContainer: {
    marginBottom: 16,
  },
  radioContainer: {
    flexDirection: 'row',
    marginTop: 8,
  },
  radioButton: {
    borderWidth: 1,
    borderColor: '#2196F3',
    borderRadius: 4,
    paddingVertical: 8,
    paddingHorizontal: 16,
    marginRight: 8,
  },
  radioButtonSelected: {
    backgroundColor: '#2196F3',
  },
  radioText: {
    color: '#2196F3',
  },
  radioTextSelected: {
    color: '#fff',
  },
  profileHeader: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#fff',
    borderRadius: 8,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  profileImageContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#2196F3',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  profileImageText: {
    fontSize: 32,
    color: '#fff',
    fontWeight: 'bold',
  },
  profileName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  profileEmail: {
    fontSize: 16,
    color: '#757575',
    marginBottom: 12,
  },
  userTypeBadge: {
    backgroundColor: '#E3F2FD',
    paddingVertical: 4,
    paddingHorizontal: 12,
    borderRadius: 12,
  },
  userTypeText: {
    color: '#2196F3',
    fontWeight: 'bold',
  },
  profileDetails: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  profileOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  profileOptionText: {
    flex: 1,
    fontSize: 16,
    color: '#333',
    marginLeft: 12,
  },
  dateButton: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 4,
    padding: 8,
    flex: 2,
  },
  dateButtonText: {
    color: '#333',
  },
  switchContainer: {
    flexDirection: 'row',
    flex: 2,
  },
  switchOption: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#2196F3',
    paddingVertical: 8,
    alignItems: 'center',
  },
  switchOptionSelected: {
    backgroundColor: '#2196F3',
  },
  switchText: {
    color: '#2196F3',
  },
  switchTextSelected: {
    color: '#fff',
  },
});

export default App;