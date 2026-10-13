// Simple test to verify API connection
const API_BASE_URL = 'http://localhost:8000/api';

async function testConnection() {
  try {
    console.log('Testing API connection...');

    // Test health endpoint
    const response = await fetch(`${API_BASE_URL}/health`);
    if (response.ok) {
      console.log('✅ API health check passed');
      const data = await response.json();
      console.log('Health response:', data);
    } else {
      console.log('❌ API health check failed');
    }

    // Test pipeline status endpoint
    const statusResponse = await fetch(`${API_BASE_URL}/pipeline/status`);
    if (statusResponse.ok) {
      console.log('✅ Pipeline status endpoint working');
      const statusData = await statusResponse.json();
      console.log('Pipeline status:', statusData);
    } else {
      console.log('❌ Pipeline status endpoint failed');
    }

  } catch (error) {
    console.error('❌ Connection failed:', error.message);
  }
}

testConnection();