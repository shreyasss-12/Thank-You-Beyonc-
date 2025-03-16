import React, { useContext, useState, useEffect } from "react";
import AuthContext from "./AuthContext";
import axios from "axios";

const Profile = () => {
  const { user, token, logout } = useContext(AuthContext);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await axios.get("http://localhost:5000/api/users/profile", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setProfile(response.data.user);
      } catch (err) {
        setError("Failed to load profile");
      } finally {
        setLoading(false);
      }
    };

    if (token) fetchProfile();
  }, [token]);

  if (loading) return <div className="text-center mt-10">Loading...</div>;
  if (error) return <div className="text-center text-red-500 mt-10">{error}</div>;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-lg w-96 text-center">
        <h2 className="text-2xl font-bold mb-4">Profile</h2>
        <div className="mb-4">
          <strong>Name:</strong> {profile?.name}
        </div>
        <div className="mb-4">
          <strong>Email:</strong> {profile?.email}
        </div>
        <div className="mb-4">
          <strong>Phone:</strong> {profile?.phone_number || "N/A"}
        </div>
        <button
          onClick={logout}
          className="w-full bg-red-500 text-white py-2 rounded-lg hover:bg-red-600 transition duration-200 mt-4"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default Profile;
