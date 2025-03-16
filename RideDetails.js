import React, { useState, useEffect, useContext } from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useRoute } from "@react-navigation/native";
import AuthContext from "./AuthContext";
import axios from "axios";

const RideDetails = () => {
  const route = useRoute();
  const { id } = route.params;
  const { token } = useContext(AuthContext);
  const [ride, setRide] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchRideDetails = async () => {
      try {
        const response = await axios.get(`http://localhost:5000/api/rides/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setRide(response.data.ride);
      } catch (err) {
        setError("Failed to load ride details");
      } finally {
        setLoading(false);
      }
    };
    if (token) fetchRideDetails();
  }, [id, token]);

  if (loading) return <Text style={styles.loadingText}>Loading...</Text>;
  if (error) return <Text style={styles.errorText}>{error}</Text>;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Ride Details</Text>
      <Text style={styles.detail}><Text style={styles.label}>From:</Text> {ride.start_location}</Text>
      <Text style={styles.detail}><Text style={styles.label}>To:</Text> {ride.end_location}</Text>
      <Text style={styles.detail}><Text style={styles.label}>Driver:</Text> {ride.driver_name} (⭐ {ride.driver_rating})</Text>
      <Text style={styles.detail}><Text style={styles.label}>Seats Available:</Text> {ride.available_seats}</Text>
      <Text style={styles.detail}><Text style={styles.label}>Price per Seat:</Text> ${ride.price_per_seat}</Text>
      <TouchableOpacity style={styles.button}>
        <Text style={styles.buttonText}>Request Ride</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f5f5f5",
    padding: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 20,
    color: "#333",
  },
  detail: {
    fontSize: 16,
    marginBottom: 10,
  },
  label: {
    fontWeight: "bold",
    color: "#555",
  },
  button: {
    marginTop: 20,
    backgroundColor: "#007bff",
    paddingVertical: 12,
    paddingHorizontal: 40,
    borderRadius: 8,
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "bold",
  },
  loadingText: {
    textAlign: "center",
    fontSize: 18,
    marginTop: 20,
  },
  errorText: {
    textAlign: "center",
    fontSize: 18,
    color: "red",
    marginTop: 20,
  },
});

export default RideDetails;