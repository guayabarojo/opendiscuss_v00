#!/bin/bash

# OpenDiscuss Deployment Script
# Supports multiple deployment targets

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 OpenDiscuss Deployment Script"
echo "================================"
echo ""

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo -e "${YELLOW}⚠️  .env.production not found!${NC}"
    echo "Creating from template..."
    cp .env.production.example .env.production
    echo -e "${RED}❌ Please edit .env.production with your values before deploying!${NC}"
    exit 1
fi

# Deployment target selection
echo "Select deployment target:"
echo "1) Local Docker (for testing)"
echo "2) DigitalOcean Droplet (VPS)"
echo "3) Build Docker images only"
echo "4) Test ngrok setup"
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo -e "${GREEN}📦 Deploying to Local Docker...${NC}"

        # Load environment variables
        export $(cat .env.production | xargs)

        # Build and start services
        docker-compose -f docker-compose.prod.yml build
        docker-compose -f docker-compose.prod.yml up -d

        echo -e "${GREEN}✅ Deployment complete!${NC}"
        echo ""
        echo "Services:"
        echo "  Frontend: http://localhost:3000"
        echo "  Backend:  http://localhost:8000"
        echo "  Docs:     http://localhost:8000/docs"
        echo ""
        echo "Check status: docker-compose -f docker-compose.prod.yml ps"
        echo "View logs:    docker-compose -f docker-compose.prod.yml logs -f"
        ;;

    2)
        echo -e "${GREEN}🌊 Deploying to DigitalOcean Droplet...${NC}"

        read -p "Enter your droplet IP: " DROPLET_IP
        read -p "Enter SSH user [root]: " SSH_USER
        SSH_USER=${SSH_USER:-root}

        echo "Copying files to droplet..."
        rsync -avz --exclude 'node_modules' --exclude '__pycache__' --exclude '.git' \
            . $SSH_USER@$DROPLET_IP:~/opendiscuss/

        echo "Setting up on remote server..."
        ssh $SSH_USER@$DROPLET_IP << 'ENDSSH'
cd ~/opendiscuss

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Deploy
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

echo "Deployment complete!"
docker-compose -f docker-compose.prod.yml ps
ENDSSH

        echo -e "${GREEN}✅ Remote deployment complete!${NC}"
        echo ""
        echo "Your app is running at: http://$DROPLET_IP:3000"
        echo "Backend API at: http://$DROPLET_IP:8000"
        echo ""
        echo "Next steps:"
        echo "  1. Point your domain to $DROPLET_IP"
        echo "  2. Set up SSL with: ssh $SSH_USER@$DROPLET_IP 'sudo certbot --nginx'"
        ;;

    3)
        echo -e "${GREEN}🔨 Building Docker images...${NC}"

        export $(cat .env.production | xargs)

        docker-compose -f docker-compose.prod.yml build

        echo -e "${GREEN}✅ Images built successfully!${NC}"
        echo ""
        echo "Push to registry:"
        echo "  docker tag opendiscuss-backend your-registry/opendiscuss-backend"
        echo "  docker push your-registry/opendiscuss-backend"
        ;;

    4)
        echo -e "${GREEN}🌐 Setting up Ngrok...${NC}"

        # Check if ngrok is installed
        if ! command -v ngrok &> /dev/null; then
            echo "Ngrok not found. Installing..."
            curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
            echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
            sudo apt update && sudo apt install ngrok
        fi

        echo ""
        echo "Ngrok is installed!"
        echo ""
        echo "To expose your local app:"
        echo "  1. Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken"
        echo "  2. Run: ngrok config add-authtoken YOUR_TOKEN"
        echo "  3. Expose frontend: ngrok http 3000"
        echo "  4. Expose backend: ngrok http 8000 (in another terminal)"
        echo ""
        read -p "Do you want to start ngrok now? [y/N]: " start_ngrok

        if [[ $start_ngrok == "y" || $start_ngrok == "Y" ]]; then
            echo "Starting ngrok for frontend (port 3000)..."
            echo "Open another terminal to expose backend: ngrok http 8000"
            ngrok http 3000
        fi
        ;;

    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac
