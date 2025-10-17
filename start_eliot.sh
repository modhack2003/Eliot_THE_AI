#!/bin/bash

echo "🚀 Starting ELIOT - AI Pentesting Assistant (MCP Version)"
echo "========================================================="

# Check if MCP server is running
if ! curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "⚠️  MCP server not running. Starting it..."
    echo "Starting Kali MCP server on port 5000..."
    kali-server-mcp --port 5000 --debug &
    sleep 3
    
    # Check if server started successfully
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo "✅ MCP server started successfully"
    else
        echo "❌ Failed to start MCP server. Please start manually:"
        echo "   kali-server-mcp --port 5000"
        exit 1
    fi
else
    echo "✅ MCP server is already running"
fi

echo ""
echo "🤖 Starting ELIOT..."
echo ""

# Start ELIOT
python3 main.py
