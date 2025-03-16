import React, { useState, useEffect, useContext } from "react";
import AuthContext from "./AuthContext";
import axios from "axios";

const Admin = () => {
  const { token } = useContext(AuthContext);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAdminStats = async () => {
      try {
        const response = await axios.get("http://localhost:5000/api/admin/stats", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setStats(response.data.stats);
      } catch (err) {
        setError("Failed to load admin stats");
      } finally {
        setLoading(false);
      }
    };

    if (token) fetchAdminStats();
  }, [token]);

  if (loading) return <div className="text-center mt-10">Loading...</div>;
  if (error) return <div className="text-center text-red-500 mt-10">{error}</div>;

  return (
    <div className="min-h-screen flex flex-col items-center bg-gray-100 py-10">
      <h2 className="text-3xl font-bold mb-6">Admin Dashboard</h2>
      <div className="w-full max-w-4xl bg-white p-6 rounded-lg shadow-lg">
        <h3 className="text-xl font-semibold mb-4">System Statistics</h3>
        <p><strong>Total Users:</strong> {stats.users.total}</p>
        <p><strong>Drivers:</strong> {stats.users.drivers}</p>
        <p><strong>Riders:</strong> {stats.users.riders}</p>
        <p><strong>Total Rides:</strong> {stats.rides.total}</p>
        <p><strong>Active Rides:</strong> {stats.rides.active}</p>
        <p><strong>Completed Rides:</strong> {stats.rides.completed}</p>
        <p><strong>Pending Requests:</strong> {stats.requests.pending}</p>
        <p><strong>Total Payments:</strong> {stats.payments.total}</p>
        <p><strong>Payment Volume:</strong> ${stats.payments.volume}</p>
      </div>
    </div>
  );
};

export default Admin;
