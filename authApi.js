import axios from 'axios';

const API_URL = 'http://your-backend-url.com'; // Replace with your actual backend URL

export const authApi = {
  login: async (email, password) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        email,
        password
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },
  
  register: async (userData) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/register`, userData);
      return response.data;
    } catch (error) {
      throw error;
    }
  }
};