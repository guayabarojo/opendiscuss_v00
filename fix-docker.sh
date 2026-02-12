#!/bin/bash
# Docker Permission Fix Script
# Run this with: bash fix-docker.sh

echo "🔧 OpenDiscuss Docker Fix Script"
echo "================================"
echo ""

echo "This script will:"
echo "1. Add your user to the docker group"
echo "2. Start Docker services"
echo ""
echo "You will be prompted for your password."
echo ""

# Add user to docker group
echo "Adding $USER to docker group..."
sudo usermod -aG docker $USER

echo "✓ User added to docker group"
echo ""

# Apply changes in current shell
echo "Applying group changes..."
newgrp docker << 'EOFNEWGRP'

cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00

echo "Starting Docker services..."
docker-compose down 2>/dev/null
docker-compose up -d

echo ""
echo "Waiting 10 seconds for services to initialize..."
sleep 10

echo ""
echo "=== Docker Status ==="
docker ps

echo ""
echo "✅ Docker services should now be running!"
echo ""
echo "If you see postgres and redis containers above, you're ready!"
echo ""

EOFNEWGRP

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Docker fix complete!"
echo ""
echo "Next steps:"
echo "1. Open a NEW terminal (to apply group changes)"
echo "2. Run: cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00"
echo "3. Run: docker ps"
echo "4. You should see postgres and redis running"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
