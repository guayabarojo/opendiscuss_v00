# OpenDiscuss Deployment Guide

This guide covers deploying OpenDiscuss to make it accessible from desktop and mobile devices.

## Table of Contents
1. [Quick Testing with Ngrok](#quick-testing-with-ngrok)
2. [Deploy to Render (Free Tier)](#deploy-to-render)
3. [Deploy to Railway](#deploy-to-railway)
4. [Deploy to DigitalOcean](#deploy-to-digitalocean)
5. [Deploy to AWS](#deploy-to-aws)

---

## Quick Testing with Ngrok

**Best for:** Quick demos, testing on mobile devices, sharing with a few people

### Setup:
```bash
# Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Sign up at https://dashboard.ngrok.com/signup
# Get your authtoken and run:
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### Usage:
```bash
# Terminal 1 - Expose frontend
ngrok http 3000

# Terminal 2 - Expose backend
ngrok http 8000

# Terminal 3 - Update frontend to use ngrok backend URL
cd frontend
# Edit .env to add: VITE_API_URL=https://your-backend-url.ngrok.io
npm run dev
```

**Pros:** Instant setup, HTTPS included, works on any network
**Cons:** URLs change on restart, limited free tier, not for production

---

## Deploy to Render (Free Tier)

**Best for:** Free hosting, automatic HTTPS, simple deployment

### Prerequisites:
- GitHub account
- Push your code to GitHub

### Steps:

1. **Create render.yaml** (already created below)

2. **Push to GitHub:**
```bash
git add .
git commit -m "Add deployment configs"
git push origin main
```

3. **Deploy on Render:**
   - Go to https://render.com
   - Click "New +" → "Blueprint"
   - Connect your GitHub repo
   - Render will automatically detect render.yaml and deploy

4. **Update Frontend Environment:**
   - After backend deploys, copy the backend URL
   - Add to frontend environment variables in Render dashboard

**Pros:** Free tier available, auto-deploy on git push, managed database
**Cons:** Free tier sleeps after inactivity, slower cold starts

---

## Deploy to Railway

**Best for:** Simple deployment, generous free tier, PostgreSQL included

### Steps:

1. **Install Railway CLI:**
```bash
npm install -g @railway/cli
railway login
```

2. **Deploy:**
```bash
# From project root
railway init
railway up

# Link PostgreSQL
railway add
# Select PostgreSQL from the list
```

3. **Set Environment Variables:**
```bash
railway variables set DATABASE_URL=${{PostgreSQL.DATABASE_URL}}
railway variables set REDIS_URL=${{Redis.REDIS_URL}}
```

**Pros:** Fast deployments, generous free tier, auto-scaling
**Cons:** Pricing can increase with usage

---

## Deploy to DigitalOcean

**Best for:** Full control, predictable pricing, production-ready

### Option A: App Platform (Easiest)

1. **Create digitalocean-app.yaml** (created below)

2. **Deploy:**
   - Go to https://cloud.digitalocean.com/apps
   - Click "Create App"
   - Connect GitHub repo
   - Select "Use existing app spec"
   - Upload digitalocean-app.yaml

**Cost:** ~$12/month for basic setup

### Option B: Droplet (More Control)

1. **Create Droplet:**
```bash
# On DigitalOcean dashboard
# Create → Droplets → Ubuntu 22.04 → $6/month
```

2. **SSH and Setup:**
```bash
ssh root@your-droplet-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Clone repo
git clone https://github.com/yourusername/opendiscuss_v00.git
cd opendiscuss_v00

# Run with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

**Cost:** $6-12/month depending on size

---

## Deploy to AWS

**Best for:** Enterprise-grade, scalable, many features

### Option A: AWS Lightsail (Simplest)

1. **Create Instance:**
   - Go to https://lightsail.aws.amazon.com
   - Create instance → Linux/Unix → OS Only → Ubuntu
   - Select $5/month plan

2. **Setup:**
```bash
# SSH to instance
ssh ubuntu@your-instance-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Deploy
git clone your-repo
docker-compose up -d
```

**Cost:** $5-10/month

### Option B: ECS with Fargate (Production)

1. **Create ECR Repositories:**
```bash
aws ecr create-repository --repository-name opendiscuss-backend
aws ecr create-repository --repository-name opendiscuss-frontend
```

2. **Push Images:**
```bash
# Build and push (see docker-build.sh below)
./docker-build.sh
```

3. **Deploy to ECS:**
   - Use AWS Console or CDK
   - See aws-ecs-task-definition.json below

**Cost:** ~$30-50/month with RDS

---

## Environment Variables

### Backend (.env):
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/opendiscuss

# Redis
REDIS_URL=redis://host:6379

# API Keys
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key

# CORS
CORS_ORIGINS=https://your-frontend-url.com

# Auth (if using)
JWT_SECRET=your-secret-key
```

### Frontend (.env):
```bash
VITE_API_URL=https://your-backend-url.com
```

---

## SSL/HTTPS

### Option 1: Cloudflare (Free)
- Point your domain to Cloudflare
- Cloudflare provides free SSL
- Set SSL mode to "Full"

### Option 2: Let's Encrypt
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### Option 3: Platform SSL
Most platforms (Render, Railway, Vercel) include automatic HTTPS

---

## Recommended Setup for Different Needs

### For Quick Demo/Testing:
**→ Use Ngrok** (5 minutes setup)

### For Free Production:
**→ Use Render** (Free tier with some limitations)

### For Small Production ($5-15/month):
**→ Use Railway or DigitalOcean Droplet**

### For Serious Production:
**→ Use DigitalOcean App Platform or AWS**

---

## Next Steps

1. Choose your deployment method above
2. Run the setup commands
3. Access from any device with your public URL
4. Optional: Add custom domain
5. Optional: Set up monitoring (Sentry, LogRocket, etc.)

## Mobile Considerations

### Responsive Design
The current Next.js frontend should work on mobile, but test:
- Touch interactions
- Screen sizes (320px to 768px)
- Landscape/portrait modes

### PWA (Optional)
To make it installable on phones:
```bash
cd frontend
npm install next-pwa
# Configure next.config.js (see PWA_SETUP.md)
```

## Security Checklist

- [ ] Change default passwords
- [ ] Use environment variables (never commit secrets)
- [ ] Enable HTTPS/SSL
- [ ] Set up CORS properly
- [ ] Rate limit API endpoints
- [ ] Set up database backups
- [ ] Use strong JWT secrets
- [ ] Configure firewall rules

## Monitoring

### Free Options:
- **Uptime:** UptimeRobot (free)
- **Errors:** Sentry (free tier)
- **Analytics:** Plausible (self-hosted) or Google Analytics

### Paid Options:
- **DataDog:** Full observability
- **New Relic:** Application monitoring
- **LogRocket:** Session replay

---

Need help? Check the deployment-specific guides below or open an issue!
