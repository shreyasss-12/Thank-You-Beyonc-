import React, { useContext } from "react";
import { View, ActivityIndicator } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import AuthContext from "./AuthContext";
import Login from "./Login";
import Register from "./Register";
import Rides from "./Rides";
import Profile from "./Profile";

const Stack = createStackNavigator();

const ProtectedRoute = () => {
  const { token } = useContext(AuthContext);

  if (token === null) {
    return <ActivityIndicator size="large" color="#007bff" style={{ flex: 1, justifyContent: "center" }} />;
  }

  return (
    <NavigationContainer>
      <Stack.Navigator>
        {token ? (
          <Stack.Screen name="Rides" component={Rides} />
        ) : (
          <>
            <Stack.Screen name="Login" component={Login} />
            <Stack.Screen name="Register" component={Register} />
          </>
        )}
        <Stack.Screen name="Profile" component={Profile} />
      </Stack.Navigator>
    </NavigationContainer>
  );
};

export default ProtectedRoute;