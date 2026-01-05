"""
Simple Load Test - Only basic endpoints
"""
from locust import HttpUser, task, between
import random

PRODUCTION_URL = "https://edutwin.online"
TEST_CREDENTIALS = {
    "username": "testaccount",
    "password": "testaccount"
}

class SimpleUser(HttpUser):
    host = PRODUCTION_URL
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login once at start"""
        response = self.client.post("/auth/login", json=TEST_CREDENTIALS)
        if response.status_code == 200:
            print(f"✅ Login successful")
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
    
    @task(10)  # Most frequent
    def health_check(self):
        """Health check endpoint"""
        self.client.get("/health")
    
    @task(5)
    def get_current_user(self):
        """Get current user info"""
        self.client.get("/auth/me")
    
    @task(3)
    def get_chat_sessions(self):
        """List chat sessions"""
        self.client.get("/chatbot/sessions")
    
    @task(1)
    def get_active_structure(self):
        """Get active teaching structure"""
        self.client.get("/custom-model/get-active-structure")
