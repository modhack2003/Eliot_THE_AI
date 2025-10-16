#!/bin/bash
# ELIOT - Hacker Assistant by Bikram@2003
# Linux/Kali Linux ELF Binary Builder

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BUILD_DIR="build"
DIST_DIR="dist"
SPEC_FILE="eliot.spec"
BINARY_NAME="eliot"
INTERACTIVE_BINARY_NAME="eliot-interactive"
PACKAGE_NAME="eliot-hacker-assistant"

echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}    ELIOT - HACKER ASSISTANT BUILDER   ${NC}"
echo -e "${PURPLE}           by Bikram@2003               ${NC}"
echo -e "${PURPLE}========================================${NC}"

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${YELLOW}Warning: This script is optimized for Linux${NC}"
    echo -e "${YELLOW}Current OS: $OSTYPE${NC}"
fi

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$NAME
    echo -e "${GREEN}Detected Linux distribution: $DISTRO${NC}"
else
    echo -e "${YELLOW}Could not detect Linux distribution${NC}"
    DISTRO="Unknown"
fi

# Check for Kali Linux
if [[ "$DISTRO" == *"Kali"* ]] || [[ "$DISTRO" == *"kali"* ]]; then
    echo -e "${CYAN}Kali Linux detected - Optimizing for penetration testing${NC}"
    KALI_MODE=true
else
    KALI_MODE=false
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR" "__pycache__"
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Install build dependencies
echo -e "${YELLOW}Installing build dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv python3-dev
    sudo apt-get install -y build-essential libssl-dev libffi-dev
    sudo apt-get install -y upx-ucl  # For binary compression
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip python3-devel
    sudo yum install -y gcc gcc-c++ make openssl-devel libffi-devel
elif command -v pacman &> /dev/null; then
    sudo pacman -S python python-pip base-devel openssl libffi
fi

# Install PyInstaller
echo -e "${YELLOW}Installing PyInstaller...${NC}"
pip3 install --upgrade pip
pip3 install pyinstaller

# Create PyInstaller spec file for ELIOT
echo -e "${YELLOW}Creating PyInstaller spec file for ELIOT...${NC}"
cat > "$SPEC_FILE" << 'EOF'
# -*- mode: python ; coding: utf-8 -*-
# ELIOT - Hacker Assistant by Bikram@2003

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all data files
datas = []
datas += collect_data_files('agent')

# Collect all submodules for ELIOT
hiddenimports = []
hiddenimports += collect_submodules('agent')
hiddenimports += [
    'motor',
    'pymongo',
    'google.generativeai',
    'yaml',
    'asyncio',
    'aiofiles',
    'requests',
    'subprocess',
    'platform',
    'json',
    'time',
    'logging',
    'traceback',
    'signal',
    'typing',
    'dataclasses',
    'enum',
    're',
    'os',
    'sys',
    'concurrent.futures',
    'threading',
    'multiprocessing'
]

# ELIOT Autonomous binary
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pandas',
        'numpy',
        'scipy',
        'PIL',
        'cv2',
        'tensorflow',
        'torch'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='eliot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# ELIOT Interactive binary
a_interactive = Analysis(
    ['interactive_main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pandas',
        'numpy',
        'scipy',
        'PIL',
        'cv2',
        'tensorflow',
        'torch'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz_interactive = PYZ(a_interactive.pure, a_interactive.zipped_data, cipher=None)

exe_interactive = EXE(
    pyz_interactive,
    a_interactive.scripts,
    a_interactive.binaries,
    a_interactive.zipfiles,
    a_interactive.datas,
    [],
    name='eliot-interactive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
EOF

# Build the ELIOT binaries
echo -e "${YELLOW}Building ELIOT ELF binaries...${NC}"
pyinstaller --clean "$SPEC_FILE"

# Check if build was successful
if [ -f "$DIST_DIR/$BINARY_NAME" ] && [ -f "$DIST_DIR/$INTERACTIVE_BINARY_NAME" ]; then
    echo -e "${GREEN}ELIOT build successful!${NC}"
    
    # Get file sizes
    SIZE_AUTO=$(du -h "$DIST_DIR/$BINARY_NAME" | cut -f1)
    SIZE_INTERACTIVE=$(du -h "$DIST_DIR/$INTERACTIVE_BINARY_NAME" | cut -f1)
    
    echo -e "${BLUE}Generated ELIOT binaries:${NC}"
    echo -e "  Autonomous:   ${GREEN}$DIST_DIR/$BINARY_NAME${NC} (${SIZE_AUTO})"
    echo -e "  Interactive:  ${GREEN}$DIST_DIR/$INTERACTIVE_BINARY_NAME${NC} (${SIZE_INTERACTIVE})"
    
    # Test the binaries
    echo -e "${YELLOW}Testing ELIOT binaries...${NC}"
    
    # Test autonomous binary (help command)
    if timeout 10 "$DIST_DIR/$BINARY_NAME" --help > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ELIOT autonomous binary works"
    else
        echo -e "  ${RED}✗${NC} ELIOT autonomous binary failed"
    fi
    
    # Test interactive binary (help command)
    if echo "help" | timeout 5 "$DIST_DIR/$INTERACTIVE_BINARY_NAME" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ELIOT interactive binary works"
    else
        echo -e "  ${RED}✗${NC} ELIOT interactive binary failed"
    fi
    
    # Create installation package
    echo -e "${YELLOW}Creating ELIOT installation package...${NC}"
    mkdir -p "$PACKAGE_NAME"
    cp "$DIST_DIR/$BINARY_NAME" "$PACKAGE_NAME/"
    cp "$DIST_DIR/$INTERACTIVE_BINARY_NAME" "$PACKAGE_NAME/"
    
    # Create installation script for ELIOT
    cat > "$PACKAGE_NAME/install.sh" << 'EOF'
#!/bin/bash
# ELIOT - Hacker Assistant Installer by Bikram@2003

set -e

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
echo -e "${PURPLE}========================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

INSTALL_DIR="/opt/eliot"
CONFIG_DIR="/etc/eliot"

# Create directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "/var/log/eliot"

# Copy binaries
echo -e "${YELLOW}Installing ELIOT binaries...${NC}"
cp eliot "$INSTALL_DIR/"
cp eliot-interactive "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR"/*

# Create symlinks
echo -e "${YELLOW}Creating system links...${NC}"
ln -sf "$INSTALL_DIR/eliot" /usr/local/bin/
ln -sf "$INSTALL_DIR/eliot-interactive" /usr/local/bin/

# Create default config
echo -e "${YELLOW}Creating ELIOT configuration...${NC}"
cat > "$CONFIG_DIR/config.yaml" << 'CONFIGEOF'
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
  port: 27017
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
CONFIGEOF

# Create systemd service
echo -e "${YELLOW}Creating ELIOT systemd service...${NC}"
cat > /etc/systemd/system/eliot.service << 'SERVICEEOF'
[Unit]
Description=ELIOT - Hacker Assistant (Autonomous Mode)
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/eliot
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=eliot
Environment=CONFIG_FILE=/etc/eliot/config.yaml

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload

# Create man pages
echo -e "${YELLOW}Creating ELIOT man pages...${NC}"
mkdir -p /usr/local/share/man/man1

cat > /usr/local/share/man/man1/eliot.1 << 'MANEOF'
.TH ELIOT 1 "2024" "ELIOT Hacker Assistant" "by Bikram@2003"
.SH NAME
eliot \- Autonomous Hacker Assistant
.SH SYNOPSIS
.B eliot
[\fIOPTIONS\fR]
.SH DESCRIPTION
ELIOT is an autonomous hacker assistant that can perform penetration testing
tasks including network scanning, vulnerability assessment, and exploitation.
.SH OPTIONS
.TP
.B \-\-help
Show help message and exit
.TP
.B \-\-check
Check system requirements
.TP
.B \-\-config \fIFILE\fR
Use custom configuration file
.SH EXAMPLES
.TP
.B eliot \-\-help
Show help information
.TP
.B eliot \-\-check
Check if all dependencies are available
.SH FILES
.TP
.B /etc/eliot/config.yaml
Main configuration file
.TP
.B /var/log/eliot/
Log directory
.SH AUTHOR
Bikram@2003
.SH SEE ALSO
.BR eliot-interactive (1)
MANEOF

cat > /usr/local/share/man/man1/eliot-interactive.1 << 'MANEOF'
.TH ELIOT-INTERACTIVE 1 "2024" "ELIOT Hacker Assistant" "by Bikram@2003"
.SH NAME
eliot-interactive \- Interactive Hacker Assistant
.SH SYNOPSIS
.B eliot-interactive
.SH DESCRIPTION
ELIOT Interactive is a chat-based hacker assistant that allows users to
interact with the AI and give specific commands for penetration testing tasks.
.SH EXAMPLES
.TP
.B eliot-interactive
Start interactive chat session
.SH COMMANDS
.TP
.B find gateway
Detect LAN gateway/router
.TP
.B ping \fITARGET\fR
Ping a target host
.TP
.B scan \fINETWORK\fR
Scan network range
.TP
.B help
Show available commands
.TP
.B do anything
Switch to autonomous mode
.SH FILES
.TP
.B /etc/eliot/config.yaml
Main configuration file
.TP
.B /var/log/eliot/
Log directory
.SH AUTHOR
Bikram@2003
.SH SEE ALSO
.BR eliot (1)
MANEOF

mandb /usr/local/share/man/man1

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ELIOT INSTALLATION COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Usage:${NC}"
echo -e "  Interactive mode: ${GREEN}eliot-interactive${NC}"
echo -e "  Autonomous mode:  ${GREEN}eliot${NC}"
echo -e "  Service start:    ${GREEN}systemctl start eliot${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  Config file: ${GREEN}$CONFIG_DIR/config.yaml${NC}"
echo -e "  Logs:        ${GREEN}/var/log/eliot/${NC}"
echo ""
echo -e "${CYAN}ELIOT Commands:${NC}"
echo -e "  ${GREEN}eliot-interactive${NC}  - Start interactive hacker assistant"
echo -e "  ${GREEN}eliot --help${NC}       - Show autonomous mode help"
echo -e "  ${GREEN}man eliot${NC}          - Read manual page"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Edit $CONFIG_DIR/config.yaml"
echo -e "2. Add your Gemini API keys"
echo -e "3. Run: ${GREEN}eliot-interactive${NC}"
echo ""
echo -e "${PURPLE}ELIOT - Hacker Assistant by Bikram@2003${NC}"
EOF

    chmod +x "$PACKAGE_NAME/install.sh"
    
    # Create README for ELIOT
    cat > "$PACKAGE_NAME/README.md" << 'EOF'
# ELIOT - Hacker Assistant by Bikram@2003

## Overview

ELIOT is an advanced hacker assistant that combines AI intelligence with traditional penetration testing tools. It operates in two modes: Interactive (chat-based) and Autonomous (unattended).

## Features

- **Interactive Mode**: Chat with ELIOT to perform specific hacking tasks
- **Autonomous Mode**: ELIOT works independently to discover and exploit targets
- **AI-Powered**: Uses Gemini 2.5 Pro for intelligent decision making
- **Tool Integration**: Integrates with nmap, metasploit, sqlmap, hydra, and more
- **Minimal Token Usage**: Optimized for long-term operation
- **Smart Failure Handling**: Tries different methods when attacks fail

## Quick Start

1. **Install:**
   ```bash
   sudo ./install.sh
   ```

2. **Configure:**
   ```bash
   sudo nano /etc/eliot/config.yaml
   ```

3. **Run Interactive Mode:**
   ```bash
   eliot-interactive
   ```

## Usage Examples

### Interactive Mode
```bash
eliot-interactive

[USER] You: find gateway
[AI] ELIOT: [Detects your LAN gateway]

[USER] You: scan 192.168.1.0/24
[AI] ELIOT: [Scans network and shows results]

[USER] You: do anything
[AI] ELIOT: [Switches to autonomous mode]
```

### Autonomous Mode
```bash
eliot
# ELIOT automatically discovers targets and attempts exploitation
```

## Configuration

Edit `/etc/eliot/config.yaml` to configure:
- Gemini API keys
- MongoDB connection
- Network settings
- Learning parameters

## Commands

### Interactive Commands
- `find gateway` - Detect LAN gateway
- `ping TARGET` - Ping a target
- `scan NETWORK` - Scan network range
- `help` - Show all commands
- `do anything` - Switch to autonomous mode

### Service Management
```bash
systemctl start eliot      # Start autonomous service
systemctl stop eliot       # Stop service
systemctl status eliot     # Check status
journalctl -u eliot -f     # View logs
```

## Requirements

- Linux x86_64
- MongoDB (local or Atlas)
- Gemini API keys
- Kali Linux tools (optional but recommended)

## File Locations

- **Binaries**: `/opt/eliot/`
- **Configuration**: `/etc/eliot/config.yaml`
- **Logs**: `/var/log/eliot/`
- **Systemd**: `/etc/systemd/system/eliot.service`

## Security Notice

ELIOT is designed for authorized penetration testing only. Users assume full legal responsibility for all activities performed by ELIOT.

## Author

**Bikram@2003**

## License

This software is for educational and authorized testing purposes only.
EOF

    # Create uninstall script
    cat > "$PACKAGE_NAME/uninstall.sh" << 'EOF'
#!/bin/bash
# ELIOT Uninstaller

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}     ELIOT UNINSTALLER${NC}"
echo -e "${RED}========================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

read -p "Are you sure you want to uninstall ELIOT? (y/N): " confirm
if [ "$confirm" != "y" ]; then
    echo "Uninstall cancelled"
    exit 0
fi

echo -e "${YELLOW}Stopping ELIOT services...${NC}"
systemctl stop eliot || true
systemctl disable eliot || true

echo -e "${YELLOW}Removing files...${NC}"
rm -f /etc/systemd/system/eliot.service
rm -rf /opt/eliot
rm -rf /etc/eliot
rm -rf /var/log/eliot
rm -f /usr/local/bin/eliot
rm -f /usr/local/bin/eliot-interactive
rm -f /usr/local/share/man/man1/eliot.1
rm -f /usr/local/share/man/man1/eliot-interactive.1

systemctl daemon-reload
mandb /usr/local/share/man/man1

echo -e "${GREEN}ELIOT uninstalled successfully!${NC}"
EOF

    chmod +x "$PACKAGE_NAME/uninstall.sh"
    
    # Create tarball
    echo -e "${YELLOW}Creating ELIOT distribution package...${NC}"
    tar -czf "${PACKAGE_NAME}-linux.tar.gz" "$PACKAGE_NAME/"
    
    echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ELIOT BUILD COMPLETE!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Generated files:${NC}"
    echo -e "  Binaries:     ${GREEN}$DIST_DIR/${NC}"
    echo -e "  Package:      ${GREEN}$PACKAGE_NAME/${NC}"
    echo -e "  Archive:      ${GREEN}${PACKAGE_NAME}-linux.tar.gz${NC}"
    echo ""
    echo -e "${CYAN}Installation:${NC}"
    echo -e "  1. Extract: ${GREEN}tar -xzf ${PACKAGE_NAME}-linux.tar.gz${NC}"
    echo -e "  2. Install: ${GREEN}cd $PACKAGE_NAME && sudo ./install.sh${NC}"
    echo -e "  3. Run:     ${GREEN}eliot-interactive${NC}"
    echo ""
    echo -e "${PURPLE}ELIOT - Hacker Assistant by Bikram@2003${NC}"
    
else
    echo -e "${RED}ELIOT build failed!${NC}"
    echo -e "${RED}Check the output above for errors${NC}"
    exit 1
fi
