# ELIOT - AI Pentesting Assistant (MCP Version)

**Simplified AI-Driven Pentesting with Kali MCP Server**
*Powered by Kali Linux MCP Server for maximum tool compatibility*

## 🚀 **by Bikram@2003**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Kali Linux](https://img.shields.io/badge/Kali-2025.3-red.svg)](https://kali.org)
[![MCP](https://img.shields.io/badge/MCP-Enabled-green.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-Educational-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Kali%20Linux-red.svg)](https://kali.org)

---

## 🎯 **Overview**

**ELIOT** is a simplified AI-powered penetration testing assistant that uses the official Kali Linux MCP (Model Context Protocol) server. This approach provides:

- **Simplified Architecture**: Uses official Kali MCP server instead of custom tool wrappers
- **All Kali Tools Available**: Access to every tool in Kali Linux without manual configuration  
- **AI-Driven Intelligence**: Natural language understanding with automatic tool selection
- **Clean Codebase**: Reduced from 600+ lines to ~200 lines of clean, maintainable code
- **Official Support**: Built on Kali's official MCP implementation

### **Key Features**
- 🤖 **AI-Powered Intelligence** - Gemini 2.5 Pro integration
- 💬 **Interactive Mode** - Chat-based command interface
- 🔄 **Autonomous Mode** - Unattended penetration testing
- 🎯 **Smart Targeting** - Automatic network discovery
- 🛠️ **Tool Integration** - nmap, metasploit, sqlmap, hydra, and more
- 📊 **Minimal Token Usage** - Optimized for long-term operation
- 🔧 **ELF Binary** - Single executable deployment

---

## 🚀 **Quick Start**

### **Quick Start (Clone & Run)**
```bash
# Clone and run immediately
git clone https://github.com/modhack2003/Eliot_THE_AI.git
cd Eliot_THE_AI
python3 main.py 2>/dev/null
```

### **Running ELIOT**
```bash
# Clean interface (recommended - no warnings/errors in chat)
python3 main.py 2>/dev/null

# Or use the binary
chmod +x eliot
./eliot

# Direct execution (with warnings visible)
python3 main.py
```

### **Installation (Kali Linux)**
```bash
# Clone the repository
git clone https://github.com/modhack2003/Eliot_THE_AI.git
cd Eliot_THE_AI

# Deploy ELIOT
chmod +x deploy_eliot_kali.sh
sudo ./deploy_eliot_kali.sh

# Configure
sudo nano /etc/eliot/config.yaml

# Start hacking!
eliot-interactive
```

### **Build ELF Binaries**
```bash
# Build standalone ELF binaries
chmod +x build_eliot_linux.sh
./build_eliot_linux.sh

# Install from package
tar -xzf eliot-hacker-assistant-linux.tar.gz
cd eliot-hacker-assistant
sudo ./install.sh
```

---

## 🎮 **Usage Examples**

### **Interactive Mode**
```bash
eliot-interactive

[USER] You: find gateway
[AI] ELIOT: [Detects your LAN gateway: 192.168.1.1]

[USER] You: scan 192.168.1.0/24
[AI] ELIOT: [Scans network and shows live hosts]

[USER] You: do anything
[AI] ELIOT: [Switches to autonomous mode]
```

### **Autonomous Mode**
```bash
eliot
# ELIOT automatically discovers targets and attempts exploitation
```

---

## 🛠️ **Commands Reference**

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

---

## 🔧 **Configuration**

### **Main Config File**
```yaml
# /etc/eliot/config.yaml
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
  connection_string: "mongodb+srv://user:pass@cluster.mongodb.net/database"
```

---

## 🏗️ **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    ELIOT ARCHITECTURE                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              INTERACTIVE MODE                          │ │
│  │  • Chat Interface                                      │ │
│  │  • User Commands                                       │ │
│  │  • Real-time Execution                                 │ │
│  │  • Ethical Oversight                                  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                │                             │
│                                ▼                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              AUTONOMOUS MODE                           │ │
│  │  • AI Decision Making                                  │ │
│  │  • Target Discovery                                    │ │
│  │  • Automated Exploitation                              │ │
│  │  • Learning & Adaptation                               │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                │                             │
│                                ▼                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              TOOL INTEGRATION                          │ │
│  │  • nmap, metasploit, sqlmap                           │ │
│  │  • hydra, john, hashcat                               │ │
│  │  • dirb, gobuster, nikto                              │ │
│  │  • Custom Exploits                                     │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 **Features**

### **Interactive Mode**
- ✅ Chat-based interface with natural language
- ✅ Real-time command execution
- ✅ User-controlled actions with ethical oversight
- ✅ Step-by-step guidance and explanations
- ✅ Target specification and validation
- ✅ Seamless switch to autonomous mode

### **Autonomous Mode**
- ✅ Unattended operation with AI decision making
- ✅ Automatic target discovery and reconnaissance
- ✅ Smart failure handling with alternative methods
- ✅ Limited cycles (prevents infinite loops)
- ✅ Minimal token usage for long-term operation
- ✅ Learning from successful/failed attempts

### **Technical Features**
- ✅ Gemini 2.5 Pro AI integration
- ✅ Dual API key rotation for reliability
- ✅ MongoDB persistence for experience storage
- ✅ Cross-platform support (Linux/Kali optimized)
- ✅ Systemd service integration
- ✅ ELF binary distribution (single executable)
- ✅ Professional logging and monitoring

---

## 🛡️ **Security Notice**

**⚠️ IMPORTANT: ELIOT is designed for authorized penetration testing only.**

- Use only in controlled environments with proper authorization
- Ensure legal compliance before testing any systems
- User assumes full legal responsibility for all activities
- Not intended for malicious or unauthorized activities
- Follow ethical hacking guidelines and responsible disclosure

---

## 📁 **Project Structure**

```
Eliot_THE_AI/
├── agent/                          # Core agent modules
│   ├── interactive_agent.py       # Interactive chat interface
│   ├── autonomous_workflow.py     # Optimized autonomous workflow
│   ├── llm_manager.py            # LLM provider management
│   ├── config_manager.py         # Configuration management
│   ├── tools/                    # Pentesting tool integrations
│   └── persistence/              # Database and logging
├── main.py                       # Autonomous mode entry point
├── interactive_main.py           # Interactive mode entry point
├── config.yaml                   # Configuration template
├── requirements.txt              # Python dependencies
├── build_eliot_linux.sh          # ELF binary builder
├── deploy_eliot_kali.sh          # Kali Linux deployment
├── ELIOT_DEPLOYMENT_GUIDE.md     # Complete deployment guide
└── README.md                     # This file
```

---

## 🐛 **Troubleshooting**

### **Common Issues**

**MongoDB Connection Error**
```bash
# Check MongoDB status
sudo systemctl status mongodb
sudo systemctl start mongodb

# Or configure Atlas connection in config.yaml
```

**API Key Issues**
```bash
# Verify API keys in configuration
sudo nano /etc/eliot/config.yaml
eliot --check
```

**Permission Errors**
```bash
# Fix permissions
sudo chown -R eliot:eliot /opt/eliot
sudo chown -R eliot:eliot /var/log/eliot
```

---

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 **License**

This project is for educational and authorized testing purposes only. See [LICENSE](LICENSE) for details.

---

## 👨‍💻 **Author**

**ELIOT - THE AI HACKER ASSISTANT**  
**by Bikram@2003**

---

## 🙏 **Acknowledgments**

- Gemini 2.5 Pro for AI capabilities
- Kali Linux community for penetration testing tools
- Open source security tools (nmap, metasploit, sqlmap, etc.)

---

## 📞 **Support**

- 📖 **Documentation**: [ELIOT_DEPLOYMENT_GUIDE.md](ELIOT_DEPLOYMENT_GUIDE.md)
- 🐛 **Issues**: [GitHub Issues](https://github.com/your-username/Eliot_THE_AI/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-username/Eliot_THE_AI/discussions)

---

## 🎉 **Ready to Hack!**

ELIOT is ready to assist you with your penetration testing tasks. Remember to use it responsibly and ethically!

```bash
# Start hacking with ELIOT!
eliot-interactive
```

---

**ELIOT - THE AI HACKER ASSISTANT by Bikram@2003** 🚀

*"Intelligence meets penetration testing"*