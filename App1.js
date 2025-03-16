import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  FlatList, 
  Image, 
  TouchableOpacity, 
  ActivityIndicator, 
  RefreshControl,
  SafeAreaView,
  StatusBar,
  Alert
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';

// Replace with your actual API URL
const API_URL = 'https://your-api-endpoint.com/pool-requests';

export default function RideRequestsScreen() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetchRequests = async () => {
    try {
      setError(null);
      const response = await fetch(API_URL);
      const data = await response.json();
      
      if (data.success) {
        setRequests(data.requests);
      } else {
        setError(data.message || 'Failed to fetch requests');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
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

  const formatDate = (isoDate) => {
    if (!isoDate) return 'N/A';
    const date = new Date(isoDate);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + 
           ', ' + date.toLocaleDateString();
  };

  const renderRideRequest = ({ item }) => {
    const ride = item.ride || {};
    const driver = ride.driver || {};
    const primaryRider = item.primary_rider || {};
    
    return (
      <View style={styles.card}>
        {/* Status Bar */}
        <View style={[styles.statusBar, { backgroundColor: getStatusColor(ride.status) }]}>
          <Text style={styles.statusText}>{ride.status?.toUpperCase() || 'UNKNOWN'}</Text>
        </View>

        {/* Ride Info */}
        <View style={styles.rideInfo}>
          <Text style={styles.departureTime}>
            Departure: {formatDate(ride.departure_time)}
          </Text>
          <Text style={styles.rideId}>Ride ID: {ride.id?.substring(0, 8) || 'N/A'}</Text>
        </View>

        {/* Driver Info */}
        {driver.id && (
          <View style={styles.driverSection}>
            <Text style={styles.sectionTitle}>Driver</Text>
            <View style={styles.driverInfo}>
              <View style={styles.driverAvatar}>
                <Ionicons name="person-circle" size={50} color="#555" />
              </View>
              <View style={styles.driverDetails}>
                <Text style={styles.driverName}>{driver.name || 'Unknown Driver'}</Text>
                <View style={styles.ratingContainer}>
                  <Ionicons name="star" size={16} color="#FFD700" />
                  <Text style={styles.rating}>{driver.rating?.toFixed(1) || 'N/A'}</Text>
                </View>
                {driver.vehicle_info && (
                  <Text style={styles.vehicleInfo}>
                    {driver.vehicle_info.make} {driver.vehicle_info.model} • {driver.vehicle_info.color}
                  </Text>
                )}
              </View>
            </View>
          </View>
        )}

        {/* Primary Rider Info */}
        {primaryRider.id && (
          <View style={styles.riderSection}>
            <Text style={styles.sectionTitle}>Primary Rider</Text>
            <View style={styles.riderInfo}>
              {primaryRider.profile_picture ? (
                <Image 
                  source={{ uri: primaryRider.profile_picture }} 
                  style={styles.riderAvatar} 
                />
              ) : (
                <View style={styles.riderAvatar}>
                  <Ionicons name="person" size={30} color="#555" />
                </View>
              )}
              <Text style={styles.riderName}>{primaryRider.name || 'Unknown Rider'}</Text>
            </View>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <TouchableOpacity style={styles.button} onPress={() => Alert.alert('Details', `Ride ID: ${ride.id}`)}>
            <Text style={styles.buttonText}>View Details</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.button, styles.contactButton]} 
            onPress={() => Alert.alert('Contact', 'Contact feature coming soon!')}
          >
            <Text style={styles.contactButtonText}>Contact</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const getStatusColor = (status) => {
    switch(status?.toLowerCase()) {
      case 'confirmed': return '#4CAF50';
      case 'pending': return '#FFC107';
      case 'cancelled': return '#F44336';
      case 'completed': return '#2196F3';
      default: return '#9E9E9E';
    }
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#0000ff" />
        <Text style={styles.loadingText}>Loading ride requests...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" />
      
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Ride Requests</Text>
      </View>
      
      {error && (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={24} color="#F44336" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}
      
      <FlatList
        data={requests}
        renderItem={renderRideRequest}
        keyExtractor={(item) => item.ride?.id || Math.random().toString()}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="car-outline" size={64} color="#ccc" />
            <Text style={styles.emptyText}>No ride requests found</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#fff',
    paddingVertical: 15,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  loadingText: {
    marginTop: 10,
    color: '#555',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 15,
    backgroundColor: '#FFEBEE',
    margin: 10,
    borderRadius: 5,
  },
  errorText: {
    marginLeft: 10,
    color: '#D32F2F',
    flex: 1,
  },
  listContainer: {
    padding: 10,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 50,
  },
  emptyText: {
    marginTop: 10,
    color: '#757575',
    fontSize: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 8,
    marginBottom: 15,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  statusBar: {
    padding: 8,
    alignItems: 'center',
  },
  statusText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 12,
  },
  rideInfo: {
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  departureTime: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  rideId: {
    fontSize: 12,
    color: '#757575',
  },
  sectionTitle: {
    fontSize: 14,
    color: '#757575',
    marginBottom: 10,
    paddingHorizontal: 15,
    paddingTop: 15,
  },
  driverSection: {
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
    paddingBottom: 15,
  },
  driverInfo: {
    flexDirection: 'row',
    paddingHorizontal: 15,
    alignItems: 'center',
  },
  driverAvatar: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: '#e0e0e0',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 15,
  },
  driverDetails: {
    flex: 1,
  },
  driverName: {
    fontSize: 16,
    fontWeight: '600',
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 5,
  },
  rating: {
    marginLeft: 5,
    color: '#555',
  },
  vehicleInfo: {
    fontSize: 12,
    color: '#757575',
    marginTop: 5,
  },
  riderSection: {
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
    paddingBottom: 15,
  },
  riderInfo: {
    flexDirection: 'row',
    paddingHorizontal: 15,
    alignItems: 'center',
  },
  riderAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#e0e0e0',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 15,
  },
  riderName: {
    fontSize: 16,
    fontWeight: '600',
  },
  actionButtons: {
    flexDirection: 'row',
    padding: 15,
  },
  button: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 12,
    borderRadius: 5,
    alignItems: 'center',
    marginRight: 10,
  },
  contactButton: {
    backgroundColor: '#2962FF',
    marginRight: 0,
  },
  buttonText: {
    color: '#555',
    fontWeight: '600',
  },
  contactButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  statsCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  statsTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 8,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statItem: {
    alignItems: 'center',
    flex: 1,
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2c3e50',
  },
  statLabel: {
    fontSize: 14,
    color: '#7f8c8d',
  },
});

import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  FlatList, 
  Image, 
  TouchableOpacity, 
  ActivityIndicator, 
  RefreshControl,
  SafeAreaView,
  StatusBar,
  Alert,
  Dimensions,
  Modal
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { MaterialIcons } from '@expo/vector-icons';
import Constants from 'expo-constants';


export default function IncomingPoolRequestsScreen({ navigation }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [limit] = useState(10);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [modalVisible, setModalVisible] = useState(false);

  // Fetch initial data
  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  const fetchRequests = async (loadMore = false) => {
    try {
      setError(null);
      const newOffset = loadMore ? offset + limit : 0;
      if (!loadMore) setLoading(true);
      
      // Get token from secure storage in a real app
      const token = "your-auth-token";
      
      const queryParams = new URLSearchParams({
        limit: limit.toString(),
        offset: newOffset.toString()
      });
      
      if (statusFilter) {
        queryParams.append("status", statusFilter);
      }
      
      const response = await fetch(`${API_URL}?${queryParams.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      const data = await response.json();
      
      if (data.success) {
        if (loadMore) {
          setRequests(prevRequests => [...prevRequests, ...data.requests]);
        } else {
          setRequests(data.requests);
        }
        
        setOffset(newOffset);
        setHasMore(data.requests.length === limit);
      } else {
        setError(data.message || 'Failed to fetch requests');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    setOffset(0);
    fetchRequests();
  };

  const loadMore = () => {
    if (hasMore && !loading && !refreshing) {
      fetchRequests(true);
    }
  };

  const formatDate = (isoDate) => {
    if (!isoDate) return 'N/A';
    const date = new Date(isoDate);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + 
           ', ' + date.toLocaleDateString();
  };
  
  const handleFilterChange = (newStatus) => {
    setStatusFilter(newStatus);
    setOffset(0);
    setHasMore(true);
  };
  
  const openRequestDetails = (request) => {
    setSelectedRequest(request);
    setModalVisible(true);
  };
  
  const handleAccept = (requestId) => {
    Alert.alert(
      "Accept Request",
      "Are you sure you want to accept this ride request?",
      [
        { text: "Cancel", style: "cancel" },
        { 
          text: "Accept", 
          onPress: () => {
            // API call would go here
            Alert.alert("Success", "Request accepted successfully!");
            // Update local state or refetch
            onRefresh();
            setModalVisible(false);
          }
        }
      ]
    );
  };
  
  const handleDecline = (requestId) => {
    Alert.alert(
      "Decline Request",
      "Are you sure you want to decline this ride request?",
      [
        { text: "Cancel", style: "cancel" },
        { 
          text: "Decline", 
          onPress: () => {
            // API call would go here
            Alert.alert("Success", "Request declined successfully!");
            // Update local state or refetch
            onRefresh();
            setModalVisible(false);
          }
        }
      ]
    );
  };

  const renderRequestItem = ({ item }) => {
    const ride = item.ride || {};
    const requester = item.requester || {};
    
    return (
      <TouchableOpacity 
        style={styles.card}
        onPress={() => openRequestDetails(item)}
      >
        {/* Status Badge */}
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
          <Text style={styles.statusText}>{item.status?.toUpperCase() || 'UNKNOWN'}</Text>
        </View>
        
        {/* Requester Info */}
        <View style={styles.requesterSection}>
          {requester.profile_picture ? (
            <Image 
              source={{ uri: requester.profile_picture }} 
              style={styles.profilePic} 
            />
          ) : (
            <View style={styles.profilePlaceholder}>
              <Ionicons name="person" size={24} color="#757575" />
            </View>
          )}
          
          <View style={styles.requesterInfo}>
            <Text style={styles.requesterName}>{requester.name || 'Unknown User'}</Text>
            <View style={styles.ratingContainer}>
              <Ionicons name="star" size={14} color="#FFD700" />
              <Text style={styles.ratingText}>{requester.rating?.toFixed(1) || '5.0'}</Text>
            </View>
          </View>
          
          <Text style={styles.timeAgo}>{formatTimeAgo(new Date(item.created_at))}</Text>
        </View>
        
        {/* Request Details */}
        <View style={styles.detailsSection}>
          {/* Departure */}
          <View style={styles.locationRow}>
            <View style={styles.locationIconContainer}>
              <MaterialIcons name="trip-origin" size={16} color="#4CAF50" />
            </View>
            <Text style={styles.locationText} numberOfLines={1}>
              {item.pickup_location?.address || 'Pickup location'}
            </Text>
          </View>
          
          {/* Destination */}
          <View style={styles.locationRow}>
            <View style={styles.locationIconContainer}>
              <MaterialIcons name="place" size={16} color="#F44336" />
            </View>
            <Text style={styles.locationText} numberOfLines={1}>
              {item.dropoff_location?.address || 'Dropoff location'}
            </Text>
          </View>
        </View>
        
        {/* Ride Info */}
        {ride.id && (
          <View style={styles.rideInfoSection}>
            <View style={styles.rideInfoRow}>
              <Ionicons name="time-outline" size={16} color="#757575" />
              <Text style={styles.rideInfoText}>
                Departure: {formatDate(ride.departure_time)}
              </Text>
            </View>
            
            <View style={styles.rideInfoRow}>
              <Ionicons name="people-outline" size={16} color="#757575" />
              <Text style={styles.rideInfoText}>
                Seats needed: {item.needed_seats} (Available: {ride.available_seats})
              </Text>
            </View>
          </View>
        )}
      </TouchableOpacity>
    );
  };
  
  const formatTimeAgo = (date) => {
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  };

  const getStatusColor = (status) => {
    switch(status?.toLowerCase()) {
      case 'pending': return '#FFC107';
      case 'accepted': return '#4CAF50';
      case 'declined': return '#F44336';
      case 'cancelled': return '#9E9E9E';
      default: return '#9E9E9E';
    }
  };
  
  const renderFilterButton = (filterName, value) => {
    const isActive = statusFilter === value;
    return (
      <TouchableOpacity
        style={[styles.filterButton, isActive && styles.activeFilterButton]}
        onPress={() => handleFilterChange(value)}
      >
        <Text style={[styles.filterButtonText, isActive && styles.activeFilterText]}>
          {filterName}
        </Text>
      </TouchableOpacity>
    );
  };
  
  const renderDetailModal = () => {
    if (!selectedRequest) return null;
    
    const ride = selectedRequest.ride || {};
    const requester = selectedRequest.requester || {};
    
    return (
      <Modal
        animationType="slide"
        transparent={true}
        visible={modalVisible}
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Request Details</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close" size={24} color="#000" />
              </TouchableOpacity>
            </View>
            
            {/* Requester Details */}
            <View style={styles.modalSection}>
              <Text style={styles.sectionTitle}>Requester</Text>
              <View style={styles.requesterDetailRow}>
                {requester.profile_picture ? (
                  <Image 
                    source={{ uri: requester.profile_picture }} 
                    style={styles.modalProfilePic} 
                  />
                ) : (
                  <View style={styles.modalProfilePlaceholder}>
                    <Ionicons name="person" size={40} color="#757575" />
                  </View>
                )}
                
                <View style={styles.requesterDetailInfo}>
                  <Text style={styles.modalRequesterName}>{requester.name || 'Unknown User'}</Text>
                  <View style={styles.ratingContainer}>
                    <Ionicons name="star" size={16} color="#FFD700" />
                    <Text style={styles.modalRating}>{requester.rating?.toFixed(1) || '5.0'}</Text>
                  </View>
                </View>
              </View>
            </View>
            
            {/* Request Details */}
            <View style={styles.modalSection}>
              <Text style={styles.sectionTitle}>Request Details</Text>
              
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Status:</Text>
                <View style={[styles.statusChip, { backgroundColor: getStatusColor(selectedRequest.status) }]}>
                  <Text style={styles.statusChipText}>{selectedRequest.status?.toUpperCase() || 'UNKNOWN'}</Text>
                </View>
              </View>
              
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Created:</Text>
                <Text style={styles.detailValue}>{formatDate(selectedRequest.created_at)}</Text>
              </View>
              
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Seats:</Text>
                <Text style={styles.detailValue}>{selectedRequest.needed_seats}</Text>
              </View>
              
              <View style={styles.locationDetailRow}>
                <Text style={styles.detailLabel}>Pickup:</Text>
                <View style={styles.locationDetail}>
                  <MaterialIcons name="trip-origin" size={16} color="#4CAF50" style={styles.locationDetailIcon} />
                  <Text style={styles.locationDetailText}>{selectedRequest.pickup_location?.address}</Text>
                </View>
              </View>
              
              <View style={styles.locationDetailRow}>
                <Text style={styles.detailLabel}>Dropoff:</Text>
                <View style={styles.locationDetail}>
                  <MaterialIcons name="place" size={16} color="#F44336" style={styles.locationDetailIcon} />
                  <Text style={styles.locationDetailText}>{selectedRequest.dropoff_location?.address}</Text>
                </View>
              </View>
            </View>
            
            {/* Ride Details */}
            {ride.id && (
              <View style={styles.modalSection}>
                <Text style={styles.sectionTitle}>Ride Details</Text>
                
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>Departure:</Text>
                  <Text style={styles.detailValue}>{formatDate(ride.departure_time)}</Text>
                </View>
                
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>Available Seats:</Text>
                  <Text style={styles.detailValue}>{ride.available_seats}</Text>
                </View>
                
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>Ride Status:</Text>
                  <View style={[styles.statusChip, { backgroundColor: getStatusColor(ride.status) }]}>
                    <Text style={styles.statusChipText}>{ride.status?.toUpperCase() || 'UNKNOWN'}</Text>
                  </View>
                </View>
              </View>
            )}
            
            {/* Action Buttons */}
            {selectedRequest.status === 'pending' && (
              <View style={styles.modalActions}>
                <TouchableOpacity 
                  style={[styles.actionButton, styles.declineButton]}
                  onPress={() => handleDecline(selectedRequest.id)}
                >
                  <Text style={styles.declineButtonText}>Decline</Text>
                </TouchableOpacity>
                
                <TouchableOpacity 
                  style={[styles.actionButton, styles.acceptButton]}
                  onPress={() => handleAccept(selectedRequest.id)}
                >
                  <Text style={styles.acceptButtonText}>Accept</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      </Modal>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" />
      
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Incoming Pool Requests</Text>
      </View>
      
      {/* Filters */}
      <View style={styles.filtersContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
          {renderFilterButton('All', '')}
          {renderFilterButton('Pending', 'pending')}
          {renderFilterButton('Accepted', 'accepted')}
          {renderFilterButton('Declined', 'declined')}
          {renderFilterButton('Cancelled', 'cancelled')}
        </ScrollView>
      </View>
      
      {error && (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={24} color="#F44336" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}
      
      <FlatList
        data={requests}
        renderItem={renderRequestItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="car-outline" size={64} color="#ccc" />
              <Text style={styles.emptyText}>No incoming pool requests found</Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          loading && !refreshing && requests.length > 0 ? (
            <View style={styles.footerLoader}>
              <ActivityIndicator size="small" color="#0000ff" />
              <Text style={styles.footerLoaderText}>Loading more...</Text>
            </View>
          ) : null
        }
      />
      
      {loading && requests.length === 0 && !refreshing && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#0000ff" />
          <Text style={styles.loadingText}>Loading requests...</Text>
        </View>
      )}
      
      {renderDetailModal()}
    </SafeAreaView>
  );
}

import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  FlatList, 
  TouchableOpacity, 
  Switch, 
  SafeAreaView, 
  ActivityIndicator,
  Image,
  Alert,
  RefreshControl
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Base URL for API
const API_BASE_URL = 'https://your-api-url.com';

// Axios instance with auth token
const api = axios.create({
  baseURL: API_BASE_URL
});

// Add token to requests
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default function RidesharingApp() {
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="auto" />
      <TabNavigator />
    </SafeAreaView>
  );
}

// Simple Tab Navigator Component
function TabNavigator() {
  const [activeTab, setActiveTab] = useState('poolRequests');
  
  const renderScreen = () => {
    switch(activeTab) {
      case 'poolRequests':
        return <PoolRequestsScreen />;
      case 'benefits':
        return <RideshareBenefitsScreen />;
      default:
        return <PoolRequestsScreen />;
    }
  };
  
  return (
    <View style={styles.mainContainer}>
      {renderScreen()}
      
      <View style={styles.tabBar}>
        <TouchableOpacity 
          style={[styles.tabButton, activeTab === 'poolRequests' && styles.activeTab]} 
          onPress={() => setActiveTab('poolRequests')}
        >
          <Ionicons 
            name="car" 
            size={24} 
            color={activeTab === 'poolRequests' ? '#3498db' : '#7f8c8d'} 
          />
          <Text style={activeTab === 'poolRequests' ? styles.activeTabText : styles.tabText}>
            Pool Requests
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.tabButton, activeTab === 'benefits' && styles.activeTab]} 
          onPress={() => setActiveTab('benefits')}
        >
          <Ionicons 
            name="leaf" 
            size={24} 
            color={activeTab === 'benefits' ? '#3498db' : '#7f8c8d'} 
          />
          <Text style={activeTab === 'benefits' ? styles.activeTabText : styles.tabText}>
            Benefits
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// Pool Requests Screen
function PoolRequestsScreen() {
  const [poolRequests, setPoolRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  
  // Fetch pool requests
  const fetchPoolRequests = async () => {
    try {
      setLoading(true);
      const endpoint = `/api/drivers/pool-requests${statusFilter ? `?status=${statusFilter}` : ''}`;
      const response = await api.get(endpoint);
      
      if (response.data.success) {
        setPoolRequests(response.data.requests);
      } else {
        Alert.alert('Error', response.data.message || 'Failed to load pool requests');
      }
    } catch (error) {
      console.error('Error fetching pool requests:', error);
      Alert.alert('Error', 'Failed to load pool requests. Please try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  // Handle refresh
  const onRefresh = () => {
    setRefreshing(true);
    fetchPoolRequests();
  };
  
  // Update ride shareability
  const updateRideShareability = async (rideId, isShareable) => {
    try {
      const response = await api.post(`/api/rides/${rideId}/update-shareability`, {
        shareable: isShareable
      });
      
      if (response.data.success) {
        Alert.alert('Success', response.data.message);
        fetchPoolRequests(); // Refresh list
      } else {
        Alert.alert('Error', response.data.message || 'Failed to update ride');
      }
    } catch (error) {
      console.error('Error updating ride shareability:', error);
      Alert.alert('Error', 'Failed to update ride shareability. Please try again.');
    }
  };
  
  // Check pending pool requests
  const checkPendingRequests = async (rideId) => {
    try {
      const response = await api.get(`/api/rides/${rideId}/pending-pool-requests`);
      
      if (response.data.success) {
        Alert.alert(
          'Pending Requests', 
          `This ride has ${response.data.pending_count} pending pool request(s).`
        );
      } else {
        Alert.alert('Error', response.data.message || 'Failed to check pending requests');
      }
    } catch (error) {
      console.error('Error checking pending requests:', error);
      Alert.alert('Error', 'Failed to check pending requests. Please try again.');
    }
  };
  
  // Apply status filter
  const applyFilter = (status) => {
    setStatusFilter(status);
  };
  
  // Load data on component mount
  useEffect(() => {
    fetchPoolRequests();
  }, [statusFilter]);
  
  // Render each request item
  const renderRequestItem = ({ item }) => {
    return (
      <View style={styles.requestCard}>
        <View style={styles.requestHeader}>
          <View style={styles.requesterInfo}>
            {item.requester?.profile_picture ? (
              <Image 
                source={{ uri: item.requester.profile_picture }} 
                style={styles.profilePic} 
              />
            ) : (
              <View style={[styles.profilePic, styles.profilePlaceholder]}>
                <Text style={styles.profileInitial}>
                  {item.requester?.name ? item.requester.name.charAt(0).toUpperCase() : '?'}
                </Text>
              </View>
            )}
            <View>
              <Text style={styles.requesterName}>{item.requester?.name || 'Unknown User'}</Text>
              <View style={styles.ratingContainer}>
                <Ionicons name="star" size={16} color="#f1c40f" />
                <Text style={styles.ratingText}>
                  {item.requester?.rating?.toFixed(1) || '5.0'}
                </Text>
              </View>
            </View>
          </View>
          <View style={styles.statusBadge}>
            <Text style={styles.statusText}>{item.status}</Text>
          </View>
        </View>
        
        <View style={styles.rideDetails}>
          <View style={styles.locationRow}>
            <Ionicons name="location" size={18} color="#3498db" />
            <Text style={styles.locationText}>{item.pickup_location}</Text>
          </View>
          <View style={styles.locationDivider}></View>
          <View style={styles.locationRow}>
            <Ionicons name="flag" size={18} color="#e74c3c" />
            <Text style={styles.locationText}>{item.dropoff_location}</Text>
          </View>
        </View>
        
        <View style={styles.requestInfoRow}>
          <View style={styles.infoItem}>
            <Ionicons name="people" size={16} color="#7f8c8d" />
            <Text style={styles.infoText}>{item.needed_seats} seat(s)</Text>
          </View>
          
          <View style={styles.infoItem}>
            <Ionicons name="calendar" size={16} color="#7f8c8d" />
            <Text style={styles.infoText}>
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </View>
        </View>
        
        {item.ride && (
          <View style={styles.rideSection}>
            <Text style={styles.sectionTitle}>Ride Information</Text>
            <View style={styles.rideInfoRow}>
              <Text style={styles.rideLabel}>Status:</Text>
              <Text style={styles.rideValue}>{item.ride.status}</Text>
            </View>
            <View style={styles.rideInfoRow}>
              <Text style={styles.rideLabel}>Available Seats:</Text>
              <Text style={styles.rideValue}>{item.ride.available_seats}</Text>
            </View>
            <View style={styles.rideInfoRow}>
              <Text style={styles.rideLabel}>Departure:</Text>
              <Text style={styles.rideValue}>
                {item.ride.departure_time ? 
                  new Date(item.ride.departure_time).toLocaleString() : 
                  'Not specified'}
              </Text>
            </View>
            <View style={styles.toggleRow}>
              <Text style={styles.toggleLabel}>Make Shareable:</Text>
              <Switch
                value={item.ride.shareable || false}
                onValueChange={(value) => updateRideShareability(item.ride.id, value)}
                trackColor={{ false: '#bdc3c7', true: '#2ecc71' }}
                thumbColor="#ffffff"
              />
            </View>
          </View>
        )}
        
        {item.primary_rider && (
          <View style={styles.primaryRiderSection}>
            <Text style={styles.sectionTitle}>Primary Rider Approval</Text>
            <View style={styles.approvalStatus}>
              <Text style={styles.approvalLabel}>
                Status: 
              </Text>
              <Text style={[
                styles.approvalValue, 
                item.primary_rider.has_approved ? styles.approved : styles.pending
              ]}>
                {item.primary_rider.has_approved ? 'Approved' : 'Pending'}
              </Text>
            </View>
            <Text style={styles.primaryRiderName}>
              Primary Rider: {item.primary_rider.name}
            </Text>
          </View>
        )}
        
        <View style={styles.actionButtons}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => checkPendingRequests(item.ride?.id)}
          >
            <Text style={styles.actionButtonText}>Check Pending</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };
  
  return (
    <View style={styles.screenContainer}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>Pool Requests</Text>
        <View style={styles.filterButtons}>
          <TouchableOpacity 
            style={[styles.filterButton, statusFilter === '' && styles.activeFilter]}
            onPress={() => applyFilter('')}
          >
            <Text style={styles.filterText}>All</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterButton, statusFilter === 'pending' && styles.activeFilter]}
            onPress={() => applyFilter('pending')}
          >
            <Text style={styles.filterText}>Pending</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterButton, statusFilter === 'accepted' && styles.activeFilter]}
            onPress={() => applyFilter('accepted')}
          >
            <Text style={styles.filterText}>Accepted</Text>
          </TouchableOpacity>
        </View>
      </View>
      
      {loading && !refreshing ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3498db" />
          <Text style={styles.loadingText}>Loading requests...</Text>
        </View>
      ) : (
        <FlatList
          data={poolRequests}
          renderItem={renderRequestItem}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.listContainer}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="car-outline" size={64} color="#bdc3c7" />
              <Text style={styles.emptyText}>No pool requests found</Text>
              <Text style={styles.emptySubtext}>
                Pool requests for your rides will appear here
              </Text>
            </View>
          }
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={['#3498db']}
            />
          }
        />
      )}
    </View>
  );
}

// Rideshare Benefits Screen
function RideshareBenefitsScreen() {
  const [benefits, setBenefits] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  
  // Fetch benefits data
  const fetchBenefits = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/users/rideshare-benefits');
      
      if (response.data.success) {
        setBenefits(response.data.stats);
      } else {
        Alert.alert('Error', response.data.message || 'Failed to load benefits data');
      }
    } catch (error) {
      console.error('Error fetching benefits:', error);
      Alert.alert('Error', 'Failed to load benefits data. Please try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  // Handle refresh
  const onRefresh = () => {
    setRefreshing(true);
    fetchBenefits();
  };
  
  // Load data on component mount
  useEffect(() => {
    fetchBenefits();
  }, []);
  
  const BenefitItem = ({ icon, title, value, unit, color }) => (
    <View style={styles.benefitItem}>
      <View style={[styles.benefitIcon, { backgroundColor: color }]}>
        <Ionicons name={icon} size={24} color="#fff" />
      </View>
      <View style={styles.benefitContent}>
        <Text style={styles.benefitTitle}>{title}</Text>
        <Text style={styles.benefitValue}>{value} <Text style={styles.benefitUnit}>{unit}</Text></Text>
      </View>
    </View>
  );
  
  return (
    <View style={styles.screenContainer}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>Your Impact</Text>
      </View>
      
      {loading && !refreshing ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3498db" />
          <Text style={styles.loadingText}>Loading impact data...</Text>
        </View>
      ) : (
        <FlatList
        data={[1]} // Just need one item for the entire content
        renderItem={() => (
          <View>
            <View style={styles.statsCard}>
              <Text style={styles.statsTitle}>Overall Stats</Text>
              <View style={styles.statsRow}>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{benefits.total_rides}</Text>
                  <Text style={styles.statLabel}>Total Rides</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{benefits.shared_rides}</Text>
                  <Text style={styles.statLabel}>Shared Rides</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{benefits.sharing_percentage}%</Text>
                  <Text style={styles.statLabel}>Sharing Rate</Text>
                </View>
              </View>
            </View>
          </View>
        )}
        keyExtractor={(item, index) => index.toString()}
      />
    )
  };
<View>
                <View style={styles.statsCard}>
                  <Text style={styles.statsTitle}>Overall Stats</Text>
                  <View style={styles.statsRow}>
                    <View style={styles.statItem}>
                      <Text style={styles.statValue}>{benefits.total_rides}</Text>
                      <Text style={styles.statLabel}>Total Rides</Text>
                    </View>
                    <View style={styles.statItem}>
                      <Text style={styles.statValue}>{benefits.shared_rides}</Text>
                      <Text style={styles.statLabel}>Shared Rides</Text>
                    </View>
                    <View style={styles.statItem}>
                      <Text style={styles.statValue}>{benefits.sharing_percentage}%</Text>
                      <Text style={styles.statLabel}>Sharing Rate</Text>
                    </View>
                  </View>
                </View>
                
                <Text style={styles.impactTitle}>Environmental Impact</Text>
                
                <BenefitItem 
                  icon="leaf" 
                  title="CO₂ Emissions Saved" 
                  value={benefits.environmental_impact.co2_saved_kg}
                  unit="kg"
                  color="#2ecc71"
                />
                
                <BenefitItem 
                  icon="water" 
                  title="Fuel Saved" 
                  value={benefits.environmental_impact.fuel_saved_liters}
                  unit="liters"
                  color="#3498db"
                />
                
                <BenefitItem 
                  icon="wallet" 
                  title="Money Saved" 
                  value={`₹${benefits.environmental_impact.money_saved}`}
                  unit=""
                  color="#f39c12"
                />
                
                <View style={styles.tipCard}>
                  <View style={styles.tipHeader}>
                    <Ionicons name="bulb" size={20} color="#f39c12" />
                    <Text style={styles.tipTitle}>Green Tip</Text>
                  </View>
                  <Text style={styles.tipText}>
                    By increasing your ride sharing by just 10%, you could save approximately 
                    {Math.round(benefits.environmental_impact.co2_saved_kg * 0.1)} kg more CO₂ per month!
                  </Text>
                </View>
              </View>
            ) : (
              <View style={styles.emptyContainer}>
                <Ionicons name="analytics-outline" size={64} color="#bdc3c7" />
                <Text style={styles.emptyText}>No benefits data found</Text>
                <Text style={styles.emptySubtext}>
                  Share more rides to see your environmental impact
                </Text>
              </View>
            )
          )
          keyExtractor={() => 'benefits'}
          contentContainerStyle={styles.benefitsContainer}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={['#3498db']}
            />
          }
        
      )
    </View>
  );
}

