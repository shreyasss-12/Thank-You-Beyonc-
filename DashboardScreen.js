import React from "react";
import { View, Text, StyleSheet, Button } from "react-native";
import { useNavigation } from "@react-navigation/native";

const DashboardScreen = () => {
  const navigation = useNavigation();

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Driver Dashboard</Text>
      <Text style={styles.info}>Welcome! Here is your dashboard.</Text>
      
      <Button title="Rewards" onPress={() => navigation.navigate("RewardsScreen")} />
      <Button title="Leaderboard" onPress={() => navigation.navigate("LeaderboardScreen")} />
      <Button title="Logout" onPress={() => console.log("Logout pressed")}/>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f5f5f5",
  },
  heading: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 20,
  },
  info: {
    fontSize: 16,
    marginBottom: 20,
  },
});

export default DashboardScreen;
