#!/bin/bash

# ELIOT Production Deployment Script
# For Kali Linux 2025.3+ with mcp-kali-server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}║  ███████╗██╗     ██╗ ██████╗ ████████╗    ███████╗████████╗ █████╗ ████████╗ ║${NC}"
echo -e "${BLUE}║  ██╔════╝██║     ██║██╔═══██╗╚══██╔══╝    ██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝ ║${NC}"
echo -e "${BLUE}║  █████╗  ██║     ██║██║   ██║   ██║       ███████╗   ██║   ███████║   ██║    ║${NC}"
echo -e "${BLUE}║  ██╔══╝  ██║     ██║██║   ██║   ██║       ╚════██║   ██║   ██╔══██║   ██║    ║${NC}"
echo -e "${BLUE}║  ██║     ███████╗██║╚██████╔╝   ██║       ███████║   ██║   ██║  ██║   ██║    ║${NC}"
echo -e "${BLUE}║  ╚═╝     ╚══════╝╚═╝ ╚═════╝    ╚═╝       ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝    ║${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}║  🚀 Production Deployment Script for Kali Linux 2025.3+                    ║${NC}"
echo -e "${BLUE}║  🎯 AI-Powered Pentesting Assistant with MCP Integration                     ║${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}⚠️  Running as root. This will install packages system-wide.${NC}"
   read -p "Continue? (y/N): " -n 1 -r
   echo
   if [[ ! $REPLY =~ ^[Yy]$ ]]; then
       echo -e "${RED}❌ Deployment cancelled.${NC}"
       exit 1
   fi
   PIP_FLAGS="--break-system-packages"
else
   PIP_FLAGS=""
fi

echo -e "${BLUE}🔍 Checking system requirements...${NC}"

# Check Kali Linux version
if ! grep -q "Kali" /etc/os-release; then
    echo -e "${RED}❌ This script is designed for Kali Linux.${NC}"
    echo -e "${YELLOW}⚠️  Continue anyway? (y/N): ${NC}"
    read -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
    echo -e "${RED}❌ Python 3.8+ required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python $PYTHON_VERSION detected${NC}"

# Check if mcp-kali-server is available
if command -v kali-server-mcp &> /dev/null; then
    echo -e "${GREEN}✅ mcp-kali-server found${NC}"
else
    echo -e "${RED}❌ mcp-kali-server not found${NC}"
    echo -e "${YELLOW}Please install mcp-kali-server first:${NC}"
    echo "sudo apt update && sudo apt install mcp-kali-server"
    exit 1
fi

echo -e "${BLUE}📦 Installing Python dependencies...${NC}"

# Install Python packages
pip3 install $PIP_FLAGS -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Python dependencies installed successfully${NC}"
else
    echo -e "${RED}❌ Failed to install Python dependencies${NC}"
    exit 1
fi

echo -e "${BLUE}🔧 Setting up configuration...${NC}"

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}⚠️  config.yaml not found. Creating from template...${NC}"
    # Create basic config.yaml
    cat > config.yaml << EOF
# ELIOT Configuration
llm:
  providers:
    - name: gemini
      model: gemini-2.5-pro
      api_keys:
        - "YOUR_API_KEY_HERE"
        - "SECOND_API_KEY_HERE"
        - "THIRD_API_KEY_HERE"
      max_tokens: 8192
      temperature: 0.7

database:
  type: mongodb
  connection_string: "mongodb+srv://user:pass@cluster.mongodb.net/database"

autonomous: true
EOF
    echo -e "${YELLOW}📝 Please edit config.yaml and add your API keys${NC}"
fi

echo -e "${BLUE}🔍 Testing MCP server connection...${NC}"

# Start MCP server in background for testing
echo -e "${YELLOW}Starting MCP server for testing...${NC}"
kali-server-mcp --port 5000 &
MCP_PID=$!

# Wait for server to start
sleep 3

# Test connection
if curl -s http://localhost:5000/health > /dev/null; then
    echo -e "${GREEN}✅ MCP server is working${NC}"
    kill $MCP_PID
else
    echo -e "${RED}❌ MCP server connection failed${NC}"
    kill $MCP_PID 2>/dev/null || true
    exit 1
fi

echo -e "${BLUE}🧪 Testing ELIOT installation...${NC}"

# Test basic import
python3 -c "
try:
    from agent.config_manager import ConfigManager
    from agent.llm_manager import LLMManager
    print('✅ Core modules imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ ELIOT installation test passed${NC}"
else
    echo -e "${RED}❌ ELIOT installation test failed${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Creating startup scripts...${NC}"

# Create production startup script
cat > start_eliot_production.sh << 'EOF'
#!/bin/bash

# ELIOT Production Startup Script

echo "🚀 Starting ELIOT AI Pentesting Assistant..."

# Check if MCP server is running
if ! curl -s http://localhost:5000/health > /dev/null; then
    echo "🔧 Starting MCP server..."
    kali-server-mcp --port 5000 &
    MCP_PID=$!
    sleep 3
    
    if curl -s http://localhost:5000/health > /dev/null; then
        echo "✅ MCP server started successfully"
    else
        echo "❌ Failed to start MCP server"
        exit 1
    fi
else
    echo "✅ MCP server already running"
fi

# Start ELIOT with clean output
echo "🎯 Starting ELIOT..."
python3 main.py 2>/dev/null

# Cleanup MCP server if we started it
if [ ! -z "$MCP_PID" ]; then
    kill $MCP_PID 2>/dev/null || true
fi
EOF

chmod +x start_eliot_production.sh

echo -e "${GREEN}✅ Production startup script created${NC}"

echo -e "${BLUE}📖 Creating usage instructions...${NC}"

cat > USAGE_INSTRUCTIONS.md << 'EOF'
# ELIOT Production Usage Instructions

## Quick Start

1. **Configure API Keys:**
   ```bash
   nano config.yaml
   # Add your Gemini API keys to the api_keys list
   ```

2. **Start ELIOT:**
   ```bash
   ./start_eliot_production.sh
   ```

3. **Manual Start (if needed):**
   ```bash
   # Terminal 1: Start MCP server
   kali-server-mcp --port 5000
   
   # Terminal 2: Start ELIOT
   python3 main.py 2>/dev/null
   ```

## Available Commands

### Shell Commands (Direct Execution)
- `ls`, `pwd`, `cd`, `ping`, `ifconfig`, `ps`, `top`, etc.

### Pentesting Commands (AI-driven)
- `scan 192.168.1.1` - Network scan
- `test web https://example.com` - Web application test
- `ping 8.8.8.8` - Network connectivity test

### Utility Commands
- `help` - Show all commands
- `status` - Show session status
- `quota` - Check API key status
- `tools` - List available tools
- `clear` - Clear session
- `add key` - Add new API key
- `quit` - Exit

## Configuration

- **config.yaml** - Main configuration file
- **MongoDB** - Optional, for token tracking
- **API Keys** - Required for AI features

## Troubleshooting

1. **MCP server not found:**
   ```bash
   sudo apt update && sudo apt install mcp-kali-server
   ```

2. **API keys exhausted:**
   - Use `quota` command to check status
   - Use `add key` to add new keys
   - Get free keys at: https://makersuite.google.com/app/apikey

3. **Permission errors:**
   ```bash
   sudo ./production_deploy.sh
   ```

## Production Features

- ✅ Real API testing at startup
- ✅ MongoDB token tracking
- ✅ Smart API key rotation
- ✅ Graceful error handling
- ✅ Professional UI with boxes
- ✅ Hybrid command system
- ✅ Session persistence
- ✅ Health monitoring
EOF

echo -e "${GREEN}✅ Usage instructions created${NC}"

echo -e "${BLUE}🔒 Setting permissions...${NC}"

# Make scripts executable
chmod +x main.py
chmod +x mcp_client.py
chmod +x start_eliot_production.sh

echo -e "${GREEN}✅ Permissions set${NC}"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}║  🎉 ELIOT PRODUCTION DEPLOYMENT COMPLETE!                                   ║${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}║  Next Steps:                                                                 ║${NC}"
echo -e "${BLUE}║  1. Edit config.yaml and add your Gemini API keys                          ║${NC}"
echo -e "${BLUE}║  2. Run: ./start_eliot_production.sh                                        ║${NC}"
echo -e "${BLUE}║  3. Use 'help' command for available options                                ║${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}║  📖 See USAGE_INSTRUCTIONS.md for detailed usage                            ║${NC}"
echo -e "${BLUE}║                                                                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"

echo -e "${GREEN}🚀 ELIOT is ready for production use!${NC}"
