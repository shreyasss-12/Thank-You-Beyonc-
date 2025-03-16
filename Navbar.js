import React, { useContext } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useNavigation } from "@react-navigation/native";
import AuthContext from "./AuthContext";

const Navbar = () => {
  const navigation = useNavigation();
  const { user, logout } = useContext(AuthContext);

  return (
    <View style={styles.navbar}>
      <TouchableOpacity onPress={() => navigation.navigate("Rides")}>
        <Text style={styles.logo}>RideShare</Text>
      </TouchableOpacity>
      <View style={styles.links}>
        <TouchableOpacity onPress={() => navigation.navigate("Rides")}>
          <Text style={styles.link}>Rides</Text>
        </TouchableOpacity>
        {user ? (
          <>
            <TouchableOpacity onPress={() => navigation.navigate("Profile")}>
              <Text style={styles.link}>Profile</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={logout} style={styles.logoutButton}>
              <Text style={styles.logoutText}>Logout</Text>
            </TouchableOpacity>
          </>
        ) : (
          <>
            <TouchableOpacity onPress={() => navigation.navigate("Login")}>
              <Text style={styles.link}>Login</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => navigation.navigate("Register")} style={styles.registerButton}>
              <Text style={styles.registerText}>Register</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  navbar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#007bff",
    paddingVertical: 15,
    paddingHorizontal: 20,
  },
  logo: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#fff",
  },
  links: {
    flexDirection: "row",
    alignItems: "center",
  },
  link: {
    fontSize: 16,
    color: "#fff",
    marginHorizontal: 10,
  },
  logoutButton: {
    backgroundColor: "#d9534f",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 5,
    marginLeft: 10,
  },
  logoutText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "bold",
  },
  registerButton: {
    backgroundColor: "#fff",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 5,
    marginLeft: 10,
  },
  registerText: {
    color: "#007bff",
    fontSize: 14,
    fontWeight: "bold",
  },
});

export default Navbar;