import React, { createContext, useState, useEffect } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";
import { Alert } from "react-native";

const AuthContext = createContext();

export const AuthProvider = ({ children, navigation }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);

  useEffect(() => {
    const loadToken = async () => {
      const storedToken = await AsyncStorage.getItem("token");
      if (storedToken) {
        setToken(storedToken);
      }
    };
    loadToken();
  }, []);

  const login = async (email, password) => {
    try {
      const response = await axios.post("http://localhost:5000/api/auth/login", {
        email,
        password,
      });
      const userToken = response.data.token;
      await AsyncStorage.setItem("token", userToken);
      setToken(userToken);
      Alert.alert("Success", "Login successful!");
      if (navigation) {
        navigation.navigate("Rides");
      }
    } catch (error) {
      Alert.alert("Error", "Login failed! Please check your credentials.");
      console.error("Login failed", error);
    }
  };

  const logout = async () => {
    await AsyncStorage.removeItem("token");
    setToken(null);
    Alert.alert("Info", "Logged out successfully.");
    if (navigation) {
      navigation.navigate("Login");
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
