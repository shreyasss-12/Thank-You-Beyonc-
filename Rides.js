import React, { useState, useEffect, useContext } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import { useNavigation } from "@react-navigation/native";
import AuthContext from "./AuthContext";
import axios from "axios";

const Rides = () => {
  const { token } = useContext(AuthContext);
  const navigation = useNavigation();
  const [rides, setRides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchRides = async () => {
      try {
        const response = await axios.get("http://localhost:5000/api/rides", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setRides(response.data.rides);
      } catch (err) {
        setError("Failed to load rides");
      } finally {
        setLoading(false);
      }
    };
    if (token) fetchRides();
  }, [token]);

  if (loading) return <Text style={styles.loadingText}>Loading...</Text>;
  if (error) return <Text style={styles.errorText}>{error}</Text>;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Available Rides</Text>
      <FlatList
        data={rides}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.rideCard}
            onPress={() => navigation.navigate("RideDetails", { id: item.id })}
          >
            <Text style={styles.rideText}>From {item.start_location} to {item.end_location}</Text>
            <Text style={styles.driverText}>Driver: {item.driver_name}</Text>
            <Text style={styles.detailsText}>Seats: {item.available_seats} | Price: ${item.price_per_seat}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f5f5",
    padding: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 20,
    textAlign: "center",
    color: "#333",
  },
  rideCard: {
    backgroundColor: "#fff",
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 5,
    elevation: 3,
  },
  rideText: {
    fontSize: 16,
    fontWeight: "bold",
  },
  driverText: {
    fontSize: 14,
    color: "#555",
  },
  detailsText: {
    fontSize: 14,
    color: "#777",
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

export default Rides;