"""
Create test users and JWT tokens for Playwright testing.
Generates host and participant tokens with proper user IDs.
"""

import jwt
from datetime import datetime, timedelta
from uuid import uuid4
import json

# Secret key (should match your backend config)
SECRET_KEY = "your-secret-key-change-in-production"

def create_jwt_token(user_id: str, username: str, email: str, expires_in_hours: int = 24):
    """Create a JWT token for a test user."""
    payload = {
        "user_id": user_id,
        "participant_id": user_id,  # Same as user_id for compatibility
        "username": username,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token

# Create test users
host_user_id = str(uuid4())
participant1_id = str(uuid4())
participant2_id = str(uuid4())
participant3_id = str(uuid4())

users = {
    "host": {
        "user_id": host_user_id,
        "username": "alice_host",
        "email": "alice@example.com",
        "token": create_jwt_token(host_user_id, "alice_host", "alice@example.com")
    },
    "participant1": {
        "user_id": participant1_id,
        "username": "bob_participant",
        "email": "bob@example.com",
        "token": create_jwt_token(participant1_id, "bob_participant", "bob@example.com")
    },
    "participant2": {
        "user_id": participant2_id,
        "username": "charlie_participant",
        "email": "charlie@example.com",
        "token": create_jwt_token(participant2_id, "charlie_participant", "charlie@example.com")
    },
    "participant3": {
        "user_id": participant3_id,
        "username": "diana_participant",
        "email": "diana@example.com",
        "token": create_jwt_token(participant3_id, "diana_participant", "diana@example.com")
    }
}

# Print tokens
print("=" * 80)
print("TEST USERS AND TOKENS")
print("=" * 80)
print()

for role, user in users.items():
    print(f"{role.upper()}:")
    print(f"  User ID: {user['user_id']}")
    print(f"  Username: {user['username']}")
    print(f"  Email: {user['email']}")
    print(f"  Token: {user['token'][:50]}...")
    print()

# Save to JSON file for easy access
with open("/tmp/test_users.json", "w") as f:
    json.dump(users, f, indent=2)

print("=" * 80)
print("Saved to /tmp/test_users.json")
print("=" * 80)
