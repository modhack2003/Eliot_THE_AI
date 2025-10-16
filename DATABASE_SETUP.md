# Database Setup Guide

## 🗄️ **MongoDB Configuration for Autonomous AI Pentesting Agent**

The agent requires MongoDB to store experiences, targets, exploits, and learning data. Here are all the ways to configure your database connection:

### **Method 1: Environment Variables (Recommended)**

Set these environment variables before running the agent:

```bash
# Basic connection
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export MONGODB_DATABASE=ai_pentesting_agent

# With authentication
export MONGODB_USERNAME=your_username
export MONGODB_PASSWORD=your_password
export MONGODB_AUTH_SOURCE=admin

# Or use full connection string
export MONGODB_URL="mongodb+srv://bikram20031213:2dYTwXlrYpgpyGxC@cluster0.8zrf3zz.mongodb.net"
```

### **Method 2: Configuration File**

Edit `config.yaml` and update the database section:

```yaml
database:
  type: mongodb
  host: localhost
  port: 27017
  database: ai_pentesting_agent
  username: your_username
  password: your_password
  auth_source: admin
  # Or use full connection string:
  # connection_string: "mongodb://username:password@host:port/database?authSource=admin"
```

### **Method 3: Automated Setup**

Run the database setup script:

```bash
python3 setup_database.py
```

This will:
- Check if MongoDB is installed
- Install MongoDB if needed
- Start MongoDB service
- Create database user
- Generate environment file
- Test connection

### **Connection String Examples**

**Local MongoDB (no auth):**
```
mongodb://localhost:27017/ai_pentesting_agent
```

**Local MongoDB with auth:**
```
mongodb://username:password@localhost:27017/ai_pentesting_agent?authSource=admin
```

**Remote MongoDB:**
```
mongodb://username:password@remote-host:27017/ai_pentesting_agent?authSource=admin
```

**MongoDB Atlas (cloud):**
```
mongodb+srv://username:password@cluster.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority
```

### **Quick Start Commands**

**1. Install MongoDB (Linux):**
```bash
sudo apt update
sudo apt install mongodb
sudo systemctl start mongodb
sudo systemctl enable mongodb
```

**2. Install MongoDB (macOS):**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb/brew/mongodb-community
```

**3. Install MongoDB (Windows):**
- Download from: https://www.mongodb.com/try/download/community
- Run installer
- Start MongoDB service

**4. Set environment variables:**
```bash
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export MONGODB_DATABASE=ai_pentesting_agent
```

**5. Test connection:**
```bash
python3 quick_test.py
```

### **Database Collections**

The agent automatically creates these collections:

- **experiences** - All exploitation attempts and outcomes
- **targets** - Discovered systems and their profiles
- **exploits** - Available exploits and custom generated ones
- **sessions** - Active compromised sessions
- **patterns** - Learned attack patterns
- **strategies** - Optimized attack strategies

### **Troubleshooting**

**Connection Refused:**
```bash
# Check if MongoDB is running
sudo systemctl status mongodb  # Linux
brew services list | grep mongodb  # macOS

# Start MongoDB
sudo systemctl start mongodb  # Linux
brew services start mongodb/brew/mongodb-community  # macOS
```

**Authentication Failed:**
```bash
# Connect to MongoDB and create user
mongosh
use admin
db.createUser({
  user: "ai_pentest_agent",
  pwd: "secure_password",
  roles: [{role: "readWrite", db: "ai_pentesting_agent"}]
})
```

**Permission Denied:**
```bash
# Check MongoDB logs
sudo journalctl -u mongodb  # Linux
tail -f /usr/local/var/log/mongodb/mongo.log  # macOS
```

### **Security Notes**

⚠️ **WARNING**: The agent stores sensitive data including:
- Successful exploits and payloads
- Compromised system details
- Network topology information
- Attack strategies and patterns

**Recommendations:**
- Use authentication for production deployments
- Encrypt database connections
- Regular backups
- Network isolation
- Access controls

### **Cloud Deployment**

For cloud deployment, consider:
- **MongoDB Atlas** - Fully managed MongoDB service
- **AWS DocumentDB** - MongoDB-compatible service
- **Azure Cosmos DB** - Multi-model database service

Example Atlas connection:
```bash
export MONGODB_URL="mongodb+srv://user:pass@cluster.mongodb.net/ai_pentesting_agent?retryWrites=true&w=majority"
```

### **Testing Database Connection**

```bash
# Quick test
python3 -c "
import pymongo
client = pymongo.MongoClient('mongodb://localhost:27017/')
print('Connection successful!' if client.admin.command('ping') else 'Connection failed')
"

# Full system test
python3 quick_test.py
```

The agent will automatically create all necessary database structures when it first connects.
