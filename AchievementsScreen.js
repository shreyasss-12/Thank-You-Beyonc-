import React from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';

const rewards = [
  { id: '1', title: '10% Discount on Next Ride' },
  { id: '2', title: 'Free Coffee Coupon' },
  { id: '3', title: 'Priority Support for a Month' },
  { id: '4', title: 'Cashback on Next 5 Rides' },
];

export default function RewardsScreen({ navigation }) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Your Rewards</Text>
      <FlatList
        data={rewards}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.rewardItem}>
            <Text style={styles.rewardText}>{item.title}</Text>
          </View>
        )}
      />
      <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}>
        <Text style={styles.buttonText}>Back to Dashboard</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#f8f9fa',
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 20,
  },
  rewardItem: {
    backgroundColor: '#d1e7ff',
    padding: 15,
    marginVertical: 5,
    borderRadius: 10,
    width: '100%',
  },
  rewardText: {
    fontSize: 16,
  },
  button: {
    marginTop: 20,
    padding: 15,
    backgroundColor: '#007bff',
    borderRadius: 10,
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
  },
});
