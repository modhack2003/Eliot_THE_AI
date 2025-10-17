#!/bin/bash
# ELIOT - Hacker Assistant by Bikram@2003
# Kali Linux Deployment Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}    ELIOT - HACKER ASSISTANT           ${NC}"
echo -e "${PURPLE}        by Bikram@2003                 ${NC}"
echo -e "${PURPLE}     Kali Linux Deployment             ${NC}"
echo -e "${PURPLE}========================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Detect Kali Linux
if ! grep -q "Kali" /etc/os-release 2>/dev/null; then
    echo -e "${YELLOW}Warning: This script is optimized for Kali Linux${NC}"
    read -p "Continue anyway? (y/N): " continue_anyway
    if [ "$continue_anyway" != "y" ]; then
        echo "Deployment cancelled"
        exit 0
    fi
else
    echo -e "${GREEN}Kali Linux detected - Perfect for ELIOT!${NC}"
fi

# Update system
echo -e "${YELLOW}Updating Kali Linux system...${NC}"
apt-get update
apt-get upgrade -y

# Install Python and development tools
echo -e "${YELLOW}Installing Python and development tools...${NC}"
apt-get install -y python3 python3-pip python3-venv python3-dev
apt-get install -y build-essential libssl-dev libffi-dev
apt-get install -y git curl wget

# Install PyInstaller for ELF building
echo -e "${YELLOW}Installing PyInstaller...${NC}"
pip3 install --upgrade pip
pip3 install pyinstaller

# Install UPX for binary compression
echo -e "${YELLOW}Installing UPX for binary compression...${NC}"
apt-get install -y upx-ucl

# Install MongoDB (optional - can use Atlas instead)
read -p "Install local MongoDB? (y/N): " install_mongo
if [ "$install_mongo" = "y" ]; then
    echo -e "${YELLOW}Installing MongoDB...${NC}"
    apt-get install -y mongodb
    systemctl enable mongodb
    systemctl start mongodb
    echo -e "${GREEN}MongoDB installed and started${NC}"
fi

# Create ELIOT user
echo -e "${YELLOW}Creating ELIOT service user...${NC}"
useradd -r -s /bin/false -d /opt/eliot eliot 2>/dev/null || echo "User eliot already exists"

# Create directories
echo -e "${YELLOW}Creating ELIOT directories...${NC}"
mkdir -p /opt/eliot
mkdir -p /etc/eliot
mkdir -p /var/log/eliot
chown -R eliot:eliot /opt/eliot
chown -R eliot:eliot /var/log/eliot

# Copy ELIOT files
echo -e "${YELLOW}Installing ELIOT files...${NC}"
cp -r . /opt/eliot/
chown -R eliot:eliot /opt/eliot

# Install Python dependencies
echo -e "${YELLOW}Installing ELIOT Python dependencies...${NC}"
cd /opt/eliot
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create configuration
echo -e "${YELLOW}Creating ELIOT configuration...${NC}"
cat > /etc/eliot/config.yaml << 'EOF'
llm:
  providers:
    - name: gemini
      model: gemini-2.5-pro
      api_keys: 
        - "YOUR_GEMINI_API_KEY_1"
        - "YOUR_GEMINI_API_KEY_2"
      max_tokens: 4000
      temperature: 0.7
      priority: 1

agent:
  autonomous: false
  interactive_mode: true
  never_ask: false
  continuous_mode: false
  max_iterations: unlimited
  decision_timeout: 30
  retry_attempts: 5
  escalation_threshold: 10

database:
  type: mongodb
  host: localhost
  # MongoDB Atlas connection string will be configured in config.yaml
  database: eliot_hacker_agent
  username: ""
  password: ""
  auth_source: admin
  connection_string: "mongodb+srv://user:pass@cluster.mongodb.net/database"

network:
  scan_timeout: 300
  max_targets: 100
  concurrent_scans: 10

learning:
  enabled: true
  model_path: "./models"
  training_data_path: "./training_data"
EOF

chown eliot:eliot /etc/eliot/config.yaml

# Create systemd service
echo -e "${YELLOW}Creating ELIOT systemd service...${NC}"
cat > /etc/systemd/system/eliot.service << 'EOF'
[Unit]
Description=ELIOT - Hacker Assistant (Autonomous Mode)
After=network.target

[Service]
Type=simple
User=eliot
Group=eliot
WorkingDirectory=/opt/eliot
Environment=PATH=/opt/eliot/venv/bin
ExecStart=/opt/eliot/venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=eliot
Environment=CONFIG_FILE=/etc/eliot/config.yaml

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Create startup scripts
echo -e "${YELLOW}Creating ELIOT startup scripts...${NC}"
cat > /usr/local/bin/eliot << 'EOF'
#!/bin/bash
cd /opt/eliot
source venv/bin/activate
python3 main.py "$@"
EOF

cat > /usr/local/bin/eliot-interactive << 'EOF'
#!/bin/bash
cd /opt/eliot
source venv/bin/activate
python3 interactive_main.py "$@"
EOF

chmod +x /usr/local/bin/eliot
chmod +x /usr/local/bin/eliot-interactive

# Build ELF binaries
echo -e "${YELLOW}Building ELIOT ELF binaries...${NC}"
cd /opt/eliot
chmod +x build_eliot_linux.sh
./build_eliot_linux.sh

# Create aliases
echo -e "${YELLOW}Creating ELIOT aliases...${NC}"
cat > /etc/profile.d/eliot.sh << 'EOF'
# ELIOT - Hacker Assistant by Bikram@2003
alias eliot-h='eliot --help'
alias eliot-c='eliot --check'
alias eliot-i='eliot-interactive'
EOF

# Set up log rotation
echo -e "${YELLOW}Setting up log rotation...${NC}"
cat > /etc/logrotate.d/eliot << 'EOF'
/var/log/eliot/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 eliot eliot
    postrotate
        systemctl reload eliot || true
    endscript
}
EOF

# Create desktop entry (if desktop environment)
if [ -d "/usr/share/applications" ]; then
    echo -e "${YELLOW}Creating ELIOT desktop entry...${NC}"
    cat > /usr/share/applications/eliot.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=ELIOT - Hacker Assistant
Comment=Interactive Hacker Assistant by Bikram@2003
Exec=eliot-interactive
Icon=applications-internet
Terminal=true
Categories=Network;Security;
Keywords=hacker;pentest;security;ai;
EOF
fi

# Final setup
echo -e "${YELLOW}Finalizing ELIOT setup...${NC}"
systemctl enable eliot

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ELIOT DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}ELIOT is now installed and ready!${NC}"
echo ""
echo -e "${CYAN}Usage Commands:${NC}"
echo -e "  ${GREEN}eliot-interactive${NC}  - Start interactive hacker assistant"
echo -e "  ${GREEN}eliot${NC}            - Start autonomous mode"
echo -e "  ${GREEN}eliot --help${NC}     - Show help"
echo -e "  ${GREEN}eliot --check${NC}    - Check system requirements"
echo ""
echo -e "${CYAN}Service Management:${NC}"
echo -e "  ${GREEN}systemctl start eliot${NC}    - Start autonomous service"
echo -e "  ${GREEN}systemctl stop eliot${NC}     - Stop service"
echo -e "  ${GREEN}systemctl status eliot${NC}   - Check status"
echo -e "  ${GREEN}journalctl -u eliot -f${NC}   - View logs"
echo ""
echo -e "${CYAN}Configuration:${NC}"
echo -e "  ${GREEN}/etc/eliot/config.yaml${NC}   - Main configuration"
echo -e "  ${GREEN}/var/log/eliot/${NC}         - Log directory"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "1. Edit configuration: ${GREEN}sudo nano /etc/eliot/config.yaml${NC}"
echo -e "2. Add your Gemini API keys"
echo -e "3. Start ELIOT: ${GREEN}eliot-interactive${NC}"
echo ""
echo -e "${PURPLE}ELIOT - Hacker Assistant by Bikram@2003${NC}"
echo -e "${PURPLE}Ready to hack! 🚀${NC}"
