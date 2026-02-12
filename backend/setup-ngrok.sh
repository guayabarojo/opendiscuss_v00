#!/bin/bash

echo "Installing ngrok..."
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

echo ""
echo "Ngrok installed! Now run:"
echo ""
echo "  # In terminal 1 (frontend):"
echo "  ngrok http 3000"
echo ""
echo "  # In terminal 2 (backend):"
echo "  ngrok http 8000"
echo ""
echo "You'll get public URLs like: https://abc123.ngrok.io"
echo "Share these URLs to access from any device!"
