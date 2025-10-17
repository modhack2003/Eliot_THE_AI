#!/bin/bash

# ELIOT THE AI - Self-Installing Binary
# Made by Bikram Dey
# Universal installer for all Linux environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ELIOT THE AI Banner
show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                              ║"
    echo "║  ███████╗██╗     ██╗ ██████╗ ████████╗    ███████╗████████╗ █████╗ ████████╗ ║"
    echo "║  ██╔════╝██║     ██║██╔═══██╗╚══██╔══╝    ██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝ ║"
    echo "║  █████╗  ██║     ██║██║   ██║   ██║       ███████╗   ██║   ███████║   ██║    ║"
    echo "║  ██╔══╝  ██║     ██║██║   ██║   ██║       ╚════██║   ██║   ██╔══██║   ██║    ║"
    echo "║  ██║     ███████╗██║╚██████╔╝   ██║       ███████║   ██║   ██║  ██║   ██║    ║"
    echo "║  ╚═╝     ╚══════╝╚═╝ ╚═════╝    ╚═╝       ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝    ║"
    echo "║                                                                              ║"
    echo "║  ███████╗██╗  ██╗███████╗    ████████╗██╗  ██╗███████╗    █████╗ ██╗          ║"
    echo "║  ██╔════╝██║  ██║██╔════╝    ╚══██╔══╝██║  ██║██╔════╝   ██╔══██╗██║          ║"
    echo "║  █████╗  ███████║█████╗         ██║   ███████║█████╗     ███████║██║          ║"
    echo "║  ██╔══╝  ██╔══██║██╔══╝         ██║   ██╔══██║██╔══╝     ██╔══██║██║          ║"
    echo "║  ██║     ██║  ██║███████╗       ██║   ██║  ██║███████╗   ██║  ██║███████╗     ║"
    echo "║  ╚═╝     ╚═╝  ╚═╝╚══════╝       ╚═╝   ╚═╝  ╚═╝╚══════╝   ╚═╝  ╚═╝╚══════╝     ║"
    echo "║                                                                              ║"
    echo "║  🎯 AI-Powered Pentesting Assistant with MCP Integration                     ║"
    echo "║  🚀 Direct Shell Access + Intelligent Tool Selection                         ║"
    echo "║  👨‍💻 Made by BIKRAM DEY                                                       ║"
    echo "║                                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        echo -e "${GREEN}✅ Running as root - full system access available${NC}"
        PIP_FLAGS="--break-system-packages"
        INSTALL_MODE="system"
    else
        echo -e "${YELLOW}⚠️  Running as regular user - will install in user directory${NC}"
        PIP_FLAGS="--user"
        INSTALL_MODE="user"
    fi
}

# Detect operating system
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
    else
        OS=$(uname -s)
        VERSION=$(uname -r)
    fi
    
    echo -e "${BLUE}🔍 Detected: $OS $VERSION${NC}"
    
    # Check if it's Kali Linux
    if [[ $OS == *"Kali"* ]]; then
        echo -e "${GREEN}✅ Kali Linux detected - optimal environment${NC}"
        IS_KALI=true
    else
        echo -e "${YELLOW}⚠️  Non-Kali Linux detected - some features may be limited${NC}"
        IS_KALI=false
    fi
}

# Check Python installation
check_python() {
    echo -e "${BLUE}🐍 Checking Python installation...${NC}"
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
        
        # Check version
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 8 ]]; then
            echo -e "${GREEN}✅ Python version is compatible${NC}"
        else
            echo -e "${RED}❌ Python 3.8+ required. Found: $PYTHON_VERSION${NC}"
            echo -e "${YELLOW}Please upgrade Python and try again${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Python 3 not found${NC}"
        echo -e "${YELLOW}Installing Python 3...${NC}"
        
        if [[ $IS_KALI == true ]]; then
            sudo apt update && sudo apt install -y python3 python3-pip
        else
            echo -e "${RED}❌ Please install Python 3 manually and try again${NC}"
            exit 1
        fi
    fi
}

# Install system dependencies
install_system_deps() {
    echo -e "${BLUE}📦 Installing system dependencies...${NC}"
    
    if [[ $IS_KALI == true ]]; then
        # Update package list
        echo -e "${YELLOW}Updating package list...${NC}"
        sudo apt update
        
        # Install essential packages
        echo -e "${YELLOW}Installing essential packages...${NC}"
        sudo apt install -y \
            python3-pip \
            python3-venv \
            curl \
            wget \
            git \
            build-essential \
            libssl-dev \
            libffi-dev \
            python3-dev
            
        # Install MCP server if available
        if command -v apt-cache &> /dev/null && apt-cache search mcp-kali-server &> /dev/null; then
            echo -e "${YELLOW}Installing MCP Kali server...${NC}"
            sudo apt install -y mcp-kali-server
            echo -e "${GREEN}✅ MCP Kali server installed${NC}"
        else
            echo -e "${YELLOW}⚠️  MCP Kali server not available in repositories${NC}"
        fi
        
    else
        echo -e "${YELLOW}⚠️  Please install the following packages manually:${NC}"
        echo "  - python3-pip"
        echo "  - curl"
        echo "  - wget"
        echo "  - git"
        echo "  - build-essential"
        read -p "Press Enter after installing dependencies..."
    fi
}

# Install Python dependencies
install_python_deps() {
    echo -e "${BLUE}🐍 Installing Python dependencies...${NC}"
    
    # Create requirements.txt if it doesn't exist
    if [[ ! -f "requirements.txt" ]]; then
        echo -e "${YELLOW}Creating requirements.txt...${NC}"
        cat > requirements.txt << 'EOF'
google-generativeai>=0.3.0
pymongo>=4.0.0
motor>=3.0.0
requests>=2.28.0
pyyaml>=6.0
EOF
    fi
    
    # Install packages
    echo -e "${YELLOW}Installing Python packages...${NC}"
    pip3 install $PIP_FLAGS -r requirements.txt
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ Python dependencies installed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to install Python dependencies${NC}"
        echo -e "${YELLOW}Trying alternative installation method...${NC}"
        
        # Try installing packages individually
        pip3 install $PIP_FLAGS google-generativeai pymongo motor requests pyyaml
        
        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Python dependencies installed successfully${NC}"
        else
            echo -e "${RED}❌ Failed to install Python dependencies${NC}"
            exit 1
        fi
    fi
}

# Setup configuration
setup_config() {
    echo -e "${BLUE}⚙️  Setting up configuration...${NC}"
    
    # Create config.yaml if it doesn't exist
    if [[ ! -f "config.yaml" ]]; then
        echo -e "${YELLOW}Creating configuration file...${NC}"
        cat > config.yaml << 'EOF'
# ELIOT THE AI Configuration
# Made by Bikram Dey

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
        echo -e "${GREEN}✅ Configuration file created${NC}"
        echo -e "${YELLOW}📝 Please edit config.yaml and add your Gemini API keys${NC}"
    else
        echo -e "${GREEN}✅ Configuration file already exists${NC}"
    fi
    
    # Create logs directory
    mkdir -p logs
    echo -e "${GREEN}✅ Logs directory created${NC}"
}

# Create startup script
create_startup_script() {
    echo -e "${BLUE}📝 Creating startup script...${NC}"
    
    cat > eliot << 'EOF'
#!/bin/bash

# ELIOT THE AI Startup Script
# Made by Bikram Dey

# Check if MCP server is running
check_mcp_server() {
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Start MCP server if needed
start_mcp_server() {
    echo "🔧 Starting MCP server..."
    kali-server-mcp --port 5000 &
    MCP_PID=$!
    
    # Wait for server to start
    for i in {1..10}; do
        if check_mcp_server; then
            echo "✅ MCP server started successfully"
            return 0
        fi
        sleep 1
    done
    
    echo "❌ Failed to start MCP server"
    return 1
}

# Main startup logic
main() {
    # Check if MCP server is available
    if command -v kali-server-mcp &> /dev/null; then
        if ! check_mcp_server; then
            start_mcp_server
        else
            echo "✅ MCP server already running"
        fi
    else
        echo "⚠️  MCP server not found - some features may be limited"
    fi
    
    # Start ELIOT
    echo "🎯 Starting ELIOT THE AI..."
    python3 main.py 2>/dev/null
    
    # Cleanup MCP server if we started it
    if [[ ! -z "$MCP_PID" ]]; then
        kill $MCP_PID 2>/dev/null || true
    fi
}

main "$@"
EOF
    
    chmod +x eliot
    echo -e "${GREEN}✅ Startup script created${NC}"
}

# Test installation
test_installation() {
    echo -e "${BLUE}🧪 Testing installation...${NC}"
    
    # Test Python imports
    python3 -c "
try:
    import google.generativeai
    import pymongo
    import motor
    import requests
    import yaml
    print('✅ All Python modules imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ Installation test passed${NC}"
    else
        echo -e "${RED}❌ Installation test failed${NC}"
        echo -e "${YELLOW}Some modules may not be available${NC}"
    fi
}

# Create usage instructions
create_usage_instructions() {
    echo -e "${BLUE}📖 Creating usage instructions...${NC}"
    
    cat > USAGE.md << 'EOF'
# ELIOT THE AI - Usage Instructions

## Quick Start

1. **Configure API Keys:**
   ```bash
   nano config.yaml
   # Add your Gemini API keys to the api_keys list
   ```

2. **Start ELIOT:**
   ```bash
   ./eliot
   ```

3. **Manual Start (if needed):**
   ```bash
   # Terminal 1: Start MCP server (Kali only)
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
   - This is normal on non-Kali systems
   - ELIOT will work with limited functionality

2. **API keys exhausted:**
   - Use `quota` command to check status
   - Use `add key` to add new keys
   - Get free keys at: https://makersuite.google.com/app/apikey

3. **Permission errors:**
   - Run installer with sudo if needed
   - Check file permissions

## Features

- ✅ Real API testing at startup
- ✅ MongoDB token tracking
- ✅ Smart API key rotation
- ✅ Graceful error handling
- ✅ Professional UI with boxes
- ✅ Hybrid command system
- ✅ Session persistence
- ✅ Health monitoring

Made by Bikram Dey
EOF
    
    echo -e "${GREEN}✅ Usage instructions created${NC}"
}

# Main installation function
main() {
    show_banner
    
    echo -e "${PURPLE}🚀 Starting ELIOT THE AI installation...${NC}"
    echo -e "${PURPLE}👨‍💻 Made by Bikram Dey${NC}"
    echo ""
    
    # Check if sudo password is needed
    if [[ $EUID -ne 0 ]] && [[ $IS_KALI == true ]]; then
        echo -e "${YELLOW}⚠️  Some operations may require sudo password${NC}"
        echo -e "${YELLOW}You may be prompted for your password during installation${NC}"
        echo ""
    fi
    
    # Installation steps
    check_root
    detect_os
    check_python
    install_system_deps
    install_python_deps
    setup_config
    create_startup_script
    test_installation
    create_usage_instructions
    
    # Final message
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                                              ║${NC}"
    echo -e "${CYAN}║  🎉 ELIOT THE AI INSTALLATION COMPLETE!                                     ║${NC}"
    echo -e "${CYAN}║                                                                              ║${NC}"
    echo -e "${CYAN}║  Next Steps:                                                                 ║${NC}"
    echo -e "${CYAN}║  1. Edit config.yaml and add your Gemini API keys                          ║${NC}"
    echo -e "${CYAN}║  2. Run: ./eliot                                                           ║${NC}"
    echo -e "${CYAN}║  3. Use 'help' command for available options                               ║${NC}"
    echo -e "${CYAN}║                                                                              ║${NC}"
    echo -e "${CYAN}║  📖 See USAGE.md for detailed usage instructions                            ║${NC}"
    echo -e "${CYAN}║  👨‍💻 Made by Bikram Dey                                                       ║${NC}"
    echo -e "${CYAN}║                                                                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}🚀 ELIOT THE AI is ready for use!${NC}"
    echo -e "${BLUE}Run './eliot' to start${NC}"
}

# Run main function
main "$@"
