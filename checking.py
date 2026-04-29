from azure.cosmos import CosmosClient
import hashlib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get connection string
COSMOS_CONNECTION_STRING = os.getenv('COSMOS_CONNECTION_STRING')

# Connect to Cosmos DB
client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
database = client.get_database_client("pictor")
users_container = database.get_container_client("users")

def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

# Test users to add
test_users = [
    {
        "id": "consumer_jill",
        "user_id": "consumer_jill",
        "email": "jill@gmail.com",
        "password_hash": hash_value("upthehill"),
        "role": "consumer",
        "fullname": "Jill Consumer",
        "username": "@jill",
        "created_at": "2026-04-26T00:00:00Z"
    },
    {
        "id": "creator_sam",
        "user_id": "creator_sam",
        "email": "sam@example.com",
        "password_hash": hash_value("sam1234"),
        "role": "creator",
        "fullname": "Sam Taylor",
        "username": "@samtaylor",
        "created_at": "2026-04-26T00:00:00Z"
    }
]

# Add users
for user in test_users:
    try:
        # Check if user already exists
        query = f"SELECT * FROM users WHERE users.email = '{user['email']}'"
        existing = list(users_container.query_items(query=query, enable_cross_partition_query=True))
        
        if existing:
            print(f"⚠️ User already exists: {user['email']}")
        else:
            users_container.create_item(body=user)
            print(f"✅ Added user: {user['email']} (role: {user['role']})")
    except Exception as e:
        print(f"❌ Error adding {user['email']}: {e}")

print("\n📊 Summary: Test users added to Cosmos DB!")

# Verify
print("\n🔍 Verifying users in database:")
query = "SELECT * FROM users"
all_users = list(users_container.query_items(query=query, enable_cross_partition_query=True))
for u in all_users:
    print(f"   - {u['email']} ({u['role']})")