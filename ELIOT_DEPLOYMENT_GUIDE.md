# ELIOT - Hacker Assistant by Bikram@2003

## 🚀 **Complete Deployment Guide**

### **Overview**
ELIOT is an advanced hacker assistant that combines AI intelligence with traditional penetration testing tools. It operates in two modes: Interactive (chat-based) and Autonomous (unattended).

---

## 📋 **Quick Start (Kali Linux)**

### **1. Deploy ELIOT on Kali Linux**
```bash
# Download and run deployment script
wget https://your-repo/eliot/deploy_eliot_kali.sh
chmod +x deploy_eliot_kali.sh
sudo ./deploy_eliot_kali.sh
```

### **2. Configure ELIOT**
```bash
# Edit configuration
sudo nano /etc/eliot/config.yaml

# Add your Gemini API keys
# Set MongoDB connection (Atlas or local)
```

### **3. Start ELIOT**
```bash
# Interactive mode (recommended)
eliot-interactive

# Autonomous mode (advanced)
eliot
```

---

## 🛠️ **Manual Installation**

### **Prerequisites**
- Kali Linux (recommended) or any Linux distribution
- Python 3.8+
- MongoDB (local or Atlas)
- Gemini API keys

### **Install Dependencies**
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python and tools
sudo apt-get install -y python3 python3-pip python3-venv python3-dev
sudo apt-get install -y build-essential libssl-dev libffi-dev
sudo apt-get install -y pyinstaller upx-ucl

# Install Kali tools (if not already installed)
sudo apt-get install -y nmap metasploit-framework sqlmap hydra john hashcat
sudo apt-get install -y dirb gobuster nikto netcat netdiscover
```

### **Install ELIOT**
```bash
# Clone repository
git clone https://your-repo/eliot.git
cd eliot

# Install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Build ELF binaries
chmod +x build_eliot_linux.sh
./build_eliot_linux.sh
```

---

## 🔧 **Build ELF Binaries**

### **Build Script**
```bash
# Run the ELF builder
chmod +x build_eliot_linux.sh
./build_eliot_linux.sh
```

### **Generated Files**
- `dist/eliot` - Autonomous ELIOT binary
- `dist/eliot-interactive` - Interactive ELIOT binary
- `eliot-hacker-assistant-linux.tar.gz` - Complete package

### **Install ELF Binaries**
```bash
# Extract package
tar -xzf eliot-hacker-assistant-linux.tar.gz
cd eliot-hacker-assistant

# Install
sudo ./install.sh
```

---

## 🎯 **Usage Examples**

### **Interactive Mode**
```bash
eliot-interactive

[USER] You: find gateway
[AI] ELIOT: [Detects your LAN gateway]

[USER] You: scan 192.168.1.0/24
[AI] ELIOT: [Scans network and shows results]

[USER] You: do anything
[AI] ELIOT: [Switches to autonomous mode]
```

### **Autonomous Mode**
```bash
eliot
# ELIOT automatically discovers targets and attempts exploitation
```

### **Service Management**
```bash
# Start autonomous service
sudo systemctl start eliot

# Check status
sudo systemctl status eliot

# View logs
sudo journalctl -u eliot -f
```

---

## 📝 **Configuration**

### **Main Config File**
Location: `/etc/eliot/config.yaml`

```yaml
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
```

---

## 🎮 **Commands Reference**

### **Interactive Commands**
- `find gateway` - Detect LAN gateway/router
- `ping TARGET` - Ping a target host
- `scan NETWORK` - Scan network range
- `check vulnerabilities TARGET` - Run vulnerability scan
- `exploit TARGET` - Attempt to exploit target
- `test web URL` - Test web application
- `brute force SERVICE TARGET` - Brute force attack
- `help` - Show all commands
- `do anything` - Switch to autonomous mode
- `quit` - Exit ELIOT

### **System Commands**
- `eliot --help` - Show autonomous mode help
- `eliot --check` - Check system requirements
- `eliot --config FILE` - Use custom config file
- `man eliot` - Read manual page

---

## 🔍 **Features**

### **Interactive Mode**
- ✅ Chat-based interface
- ✅ Real-time command execution
- ✅ User-controlled actions
- ✅ Ethical oversight
- ✅ Target specification
- ✅ Step-by-step guidance

### **Autonomous Mode**
- ✅ Unattended operation
- ✅ Automatic target discovery
- ✅ AI-driven decision making
- ✅ Smart failure handling
- ✅ Limited cycles (no infinite loops)
- ✅ Minimal token usage

### **Technical Features**
- ✅ Gemini 2.5 Pro integration
- ✅ Dual API key rotation
- ✅ MongoDB persistence
- ✅ Cross-platform support
- ✅ Systemd service integration
- ✅ Log rotation
- ✅ ELF binary distribution

---

## 📊 **File Locations**

| Component | Location |
|-----------|----------|
| **Binaries** | `/opt/eliot/` |
| **Configuration** | `/etc/eliot/config.yaml` |
| **Logs** | `/var/log/eliot/` |
| **Systemd Service** | `/etc/systemd/system/eliot.service` |
| **Startup Scripts** | `/usr/local/bin/eliot*` |
| **Man Pages** | `/usr/local/share/man/man1/` |

---

## 🛡️ **Security Notice**

**⚠️ IMPORTANT: ELIOT is designed for authorized penetration testing only.**

- Use only in controlled environments
- Ensure proper authorization before testing
- User assumes full legal responsibility
- Not intended for malicious activities
- Follow ethical hacking guidelines

---

## 🐛 **Troubleshooting**

### **Common Issues**

**1. MongoDB Connection Error**
```bash
# Check MongoDB status
sudo systemctl status mongodb

# Start MongoDB
sudo systemctl start mongodb

# Or use Atlas connection string in config
```

**2. API Key Issues**
```bash
# Check API keys in config
sudo nano /etc/eliot/config.yaml

# Test API connection
eliot --check
```

**3. Permission Errors**
```bash
# Fix permissions
sudo chown -R eliot:eliot /opt/eliot
sudo chown -R eliot:eliot /var/log/eliot
```

**4. Service Won't Start**
```bash
# Check service status
sudo systemctl status eliot

# View detailed logs
sudo journalctl -u eliot -f

# Restart service
sudo systemctl restart eliot
```

---

## 📞 **Support**

### **Documentation**
- Configuration guide: `/etc/eliot/config.yaml`
- Manual pages: `man eliot`, `man eliot-interactive`
- Logs: `/var/log/eliot/`

### **Uninstall**
```bash
# Remove ELIOT completely
sudo /opt/eliot/eliot-hacker-assistant/uninstall.sh
```

---

## 👨‍💻 **Author**

**ELIOT - Hacker Assistant**  
**by Bikram@2003**

---

## 📄 **License**

This software is for educational and authorized testing purposes only.

---

## 🎉 **Ready to Hack!**

ELIOT is now ready to assist you with your penetration testing tasks. Remember to use it responsibly and ethically!

```bash
# Start hacking!
eliot-interactive
```

**ELIOT - Hacker Assistant by Bikram@2003** 🚀
