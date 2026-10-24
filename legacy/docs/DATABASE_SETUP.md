# MongoDB Atlas Setup Guide

## 🗄️ **MongoDB Atlas Configuration for ELIOT AI Pentesting Agent**

ELIOT uses MongoDB Atlas (cloud database) to store experiences, targets, exploits, and learning data. Local MongoDB is not supported.

## Step-by-Step Setup

### **Step 1: Create MongoDB Atlas Account**

1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a free account
3. Create a new cluster:
   - Choose "M0 Sandbox" (free tier)
   - Select your preferred cloud provider (AWS, Google Cloud, or Azure)
   - Choose a region close to your location
   - Name your cluster (e.g., "eliot-cluster")

### **Step 2: Configure Database Access**

1. Go to "Database Access" in the left sidebar
2. Click "Add New Database User"
3. Create a user with:
   - Username: `eliot_user` (or your preference)
   - Password: Generate a secure password and save it
   - Database User Privileges: "Read and write to any database"
4. Click "Add User"

### **Step 3: Configure Network Access**

1. Go to "Network Access" in the left sidebar
2. Click "Add IP Address"
3. For development: Add your current IP address
4. For production: Add your server's IP address
5. Or use `0.0.0.0/0` for access from anywhere (less secure)
6. Click "Confirm"

### **Step 4: Get Connection String**

1. Go to "Clusters" in the left sidebar
2. Click "Connect" on your cluster
3. Choose "Connect your application"
4. Select "Python" and version "3.6 or later"
5. Copy the connection string (starts with `mongodb+srv://`)

## Configuration Methods

### **Method 1: Environment Variables (Recommended)**

Set this environment variable before running ELIOT:

```bash
# MongoDB Atlas connection string
export MONGODB_URL="mongodb+srv://eliot_user:your_password@eliot-cluster.xxxxx.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority"
```

### **Method 2: Configuration File**

Edit `config.yaml` and update the database section:

```yaml
database:
  type: mongodb
  # MongoDB Atlas connection string (recommended)
  connection_string: "mongodb+srv://eliot_user:your_password@eliot-cluster.xxxxx.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority"
  # Alternative: Individual Atlas parameters
  database: ai_pentesting_agent
  username: "eliot_user"
  password: "your_password"
  auth_source: admin
```

## Connection String Format

**MongoDB Atlas Connection String:**
```
mongodb+srv://username:password@cluster.mongodb.net/database_name?retryWrites=true&w=majority
```

**Example:**
```
mongodb+srv://eliot_user:MySecurePassword123@eliot-cluster.abc123.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority
```

## Testing Your Connection

### **Test Connection with Python**

Create a test script to verify your connection:

```python
import pymongo
from pymongo import MongoClient

# Replace with your connection string
connection_string = "mongodb+srv://eliot_user:your_password@eliot-cluster.xxxxx.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority"

try:
    client = MongoClient(connection_string)
    # Test connection
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB Atlas!")
    
    # Test database access
    db = client['ai_pentesting_agent']
    collection = db['test_collection']
    collection.insert_one({"test": "connection", "timestamp": "2024-01-01"})
    print("✅ Successfully wrote to database!")
    
    # Clean up test document
    collection.delete_one({"test": "connection"})
    print("✅ Successfully deleted test document!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

### **Test with ELIOT**

Run ELIOT to test the database connection:

```bash
# Set your connection string
export MONGODB_URL="mongodb+srv://eliot_user:your_password@eliot-cluster.xxxxx.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority"

# Run ELIOT
python3 main.py --check
```

## Troubleshooting

### **Common Issues**

1. **Authentication Failed**
   - Verify username and password are correct
   - Check that the user has read/write permissions

2. **Network Access Denied**
   - Add your IP address to the network access list
   - Wait a few minutes for changes to take effect

3. **Connection Timeout**
   - Check your internet connection
   - Verify the connection string is correct
   - Try using `0.0.0.0/0` temporarily for testing

4. **Database Not Found**
   - The database will be created automatically when first used
   - Make sure the database name in the connection string is correct

### **Security Best Practices**

1. **Use Strong Passwords**
   - Generate random, complex passwords
   - Store passwords securely (use environment variables)

2. **Limit Network Access**
   - Only add necessary IP addresses
   - Avoid using `0.0.0.0/0` in production

3. **Regular Security Updates**
   - Keep your MongoDB Atlas cluster updated
   - Monitor access logs regularly

## Database Collections

ELIOT will automatically create these collections:

- `experiences` - Store exploitation attempts and results
- `targets` - Store discovered targets and their information
- `exploits` - Store custom generated exploits
- `sessions` - Store session data and handoffs

## Free Tier Limits

MongoDB Atlas M0 Sandbox (Free Tier):
- 512 MB storage
- Shared RAM
- No backup
- Suitable for development and testing

For production use, consider upgrading to a paid tier for better performance and reliability.

## Support

If you encounter issues:
1. Check the MongoDB Atlas documentation
2. Verify your connection string format
3. Test with the provided Python script
4. Check ELIOT logs for specific error messages