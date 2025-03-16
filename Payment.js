import React, { useState, useContext } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from "react-native";
import AuthContext from "./AuthContext";
import axios from "axios";

const Payment = () => {
  const { token } = useContext(AuthContext);
  const [rideRequestId, setRideRequestId] = useState("");
  const [amount, setAmount] = useState("");

  const handlePayment = async () => {
    try {
      const response = await axios.post(
        "http://localhost:5000/api/payments",
        { ride_request_id: rideRequestId, amount, payment_method: "credit_card" },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      Alert.alert("Success", "Payment successful!");
    } catch (error) {
      Alert.alert("Error", "Payment failed! Try again.");
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Make a Payment</Text>
      <TextInput
        placeholder="Ride Request ID"
        value={rideRequestId}
        onChangeText={setRideRequestId}
        style={styles.input}
      />
      <TextInput
        placeholder="Amount"
        value={amount}
        onChangeText={setAmount}
        style={styles.input}
        keyboardType="numeric"
      />
      <TouchableOpacity onPress={handlePayment} style={styles.button}>
        <Text style={styles.buttonText}>Pay Now</Text>
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
  input: {
    width: "80%",
    padding: 12,
    marginVertical: 10,
    backgroundColor: "#fff",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
  },
  button: {
    backgroundColor: "#28a745",
    paddingVertical: 12,
    paddingHorizontal: 40,
    borderRadius: 8,
    marginTop: 20,
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "bold",
  },
});

export default Payment;
