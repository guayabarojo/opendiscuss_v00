# 🚀 Quick Start Deployment Guide

Deploy OpenDiscuss to make it accessible from any device (desktop, mobile, tablet).

## ⚡ Fastest Option: Ngrok (5 minutes)

Perfect for demos, testing on mobile, or showing to a few people.

```bash
# 1. Run the deployment script
./deploy.sh

# 2. Choose option 4 (Test ngrok setup)

# 3. Follow the prompts to get your public URL
```

Your app will be available at URLs like:
- Frontend: `https://abc123.ngrok.io`
- Backend: `https://def456.ngrok.io`

**Share these URLs** to access from any device!

---

## 🆓 Best Free Option: Render (15 minutes)

Free hosting with automatic HTTPS and managed database.

### Steps:

1. **Push to GitHub:**
```bash
git add .
git commit -m "Add deployment configs"
git push origin main
```

2. **Deploy on Render:**
   - Go to https://render.com/login
   - Sign in with GitHub
   - Click "New +" → "Blueprint"
   - Select your repository
   - Render detects `render.yaml` automatically
   - Click "Apply"

3. **Set API Keys:**
   - In Render dashboard, go to backend service
   - Add environment variables:
     - `OPENAI_API_KEY`: your OpenAI key
     - `ANTHROPIC_API_KEY`: your Anthropic key

4. **Done!** Your app is live at `https://your-app.onrender.com`

**Pros:** Free, automatic HTTPS, managed database
**Cons:** Free tier sleeps after 15 min inactivity

---

## 💰 Best Paid Option: DigitalOcean ($6/month)

Full control, fast, predictable pricing.

### Option A: Automated Deployment

```bash
# 1. Set up environment
cp .env.production.example .env.production
nano .env.production  # Edit with your values

# 2. Run deployment script
./deploy.sh

# 3. Choose option 2 (DigitalOcean Droplet)
# Enter your droplet IP when prompted
```

### Option B: Manual Setup

1. **Create Droplet:**
   - Go to https://cloud.digitalocean.com
   - Create → Droplets
   - Ubuntu 22.04, $6/month plan
   - Add SSH key

2. **SSH to Droplet:**
```bash
ssh root@YOUR_DROPLET_IP

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

3. **Deploy App:**
```bash
# Clone your repo
git clone https://github.com/yourusername/opendiscuss_v00.git
cd opendiscuss_v00

# Set up environment
cp .env.production.example .env.production
nano .env.production  # Edit with your values

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

4. **Access:** Your app is now at `http://YOUR_DROPLET_IP:3000`

5. **Add Domain (Optional):**
```bash
# Point your domain to droplet IP in DNS settings
# Install Certbot for free SSL
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 📱 Mobile Access

Once deployed with any method above:

1. **Open browser on phone**
2. **Go to your public URL** (from ngrok, Render, or DigitalOcean)
3. **Works immediately!** Responsive design adapts to screen size

### Make it a PWA (Optional):

To allow "Add to Home Screen":

```bash
cd frontend
npm install next-pwa
```

Then add to `next.config.js`:
```javascript
const withPWA = require('next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
});

module.exports = withPWA({
  // ... your config
});
```

---

## 🔒 Security Checklist

Before going live:

- [ ] Change all default passwords in `.env.production`
- [ ] Use strong random passwords (run `openssl rand -base64 32`)
- [ ] Enable HTTPS (automatic on Render, use Certbot on DigitalOcean)
- [ ] Set CORS origins to your actual domain
- [ ] Don't commit `.env.production` to git (it's in .gitignore)
- [ ] Enable database backups
- [ ] Set up monitoring (optional: Sentry, UptimeRobot)

---

## 🆘 Troubleshooting

### "Can't connect from phone"

**If using localhost:**
- You MUST use ngrok or deploy to a server
- Localhost only works on the same computer

**If using ngrok:**
- Make sure ngrok is still running
- Free tier URLs expire when ngrok stops

**If using server:**
- Check firewall allows ports 3000 and 8000
- Verify services are running: `docker-compose ps`

### "White screen on mobile"

- Check browser console for errors
- Ensure VITE_API_URL is set correctly in frontend
- Verify backend is accessible from frontend URL

### "Database connection failed"

- Check DATABASE_URL in .env.production
- Verify PostgreSQL container is running
- Check logs: `docker-compose logs postgres`

---

## 📊 Comparison

| Method | Cost | Setup Time | Best For |
|--------|------|------------|----------|
| **Ngrok** | Free/Paid | 5 min | Quick demos, mobile testing |
| **Render** | Free | 15 min | Free hosting, small projects |
| **Railway** | Free/$5 | 10 min | Easy deployment, good free tier |
| **DigitalOcean** | $6/mo | 30 min | Production, full control |
| **AWS Lightsail** | $5/mo | 30 min | Production, AWS ecosystem |

---

## 🎯 Recommended Path

1. **Testing/Demo:** Start with **ngrok** (instant)
2. **Show to users:** Deploy to **Render** (free)
3. **Production:** Move to **DigitalOcean** ($6/mo)

---

## 🔗 Useful Links

- **Ngrok:** https://ngrok.com
- **Render:** https://render.com
- **Railway:** https://railway.app
- **DigitalOcean:** https://digitalocean.com
- **AWS Lightsail:** https://aws.amazon.com/lightsail/

---

## 📝 Next Steps After Deployment

1. ✅ Test on mobile device
2. ✅ Share URL with team/users
3. ✅ Set up custom domain (optional)
4. ✅ Enable HTTPS/SSL
5. ✅ Set up monitoring
6. ✅ Configure backups
7. ✅ Add analytics (optional)

---

Need help? Check the full [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) or open an issue!
