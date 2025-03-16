import React, { useState, useEffect, useContext } from "react";
import AuthContext from "./AuthContext";
import axios from "axios";

const RideRequests = () => {
  const { token } = useContext(AuthContext);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchRequests = async () => {
      try {
        const response = await axios.get("http://localhost:5000/api/ride-requests", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setRequests(response.data.requests);
      } catch (err) {
        setError("Failed to load ride requests");
      } finally {
        setLoading(false);
      }
    };

    if (token) fetchRequests();
  }, [token]);

  if (loading) return <div className="text-center mt-10">Loading...</div>;
  if (error) return <div className="text-center text-red-500 mt-10">{error}</div>;

  return (
    <div className="min-h-screen flex flex-col items-center bg-gray-100 py-10">
      <h2 className="text-3xl font-bold mb-6">Your Ride Requests</h2>
      <div className="w-full max-w-4xl bg-white p-6 rounded-lg shadow-lg">
        {requests.length === 0 ? (
          <p className="text-center text-gray-600">No ride requests found</p>
        ) : (
          requests.map((request) => (
            <div key={request.id} className="border-b p-4 last:border-none">
              <p><strong>Pickup:</strong> {request.pickup_location}</p>
              <p><strong>Dropoff:</strong> {request.dropoff_location}</p>
              <p><strong>Status:</strong> {request.status}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default RideRequests;
