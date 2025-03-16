import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import Login from "./Login";
import Register from "./Register";
import Profile from "./Profile";
import Rides from "./Rides";
import RideDetails from "./RideDetails";
import RideRequests from "./RideRequests";
import Payment from "./Payment";
import Admin from "./Admin";
import { AuthProvider } from "./AuthContext";
import Navbar from "./Navbar";

const Stack = createStackNavigator();

export default function App() {
  return (
    <AuthProvider>
      <NavigationContainer>
        <Navbar />
        <Stack.Navigator initialRouteName="Rides" screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Login" component={Login} />
          <Stack.Screen name="Register" component={Register} />
          <Stack.Screen name="Profile" component={Profile} />
          <Stack.Screen name="Rides" component={Rides} />
          <Stack.Screen name="RideDetails" component={RideDetails} />
          <Stack.Screen name="RideRequests" component={RideRequests} />
          <Stack.Screen name="Payment" component={Payment} />
          <Stack.Screen name="Admin" component={Admin} />
        </Stack.Navigator>
      </NavigationContainer>
    </AuthProvider>
  );
}
