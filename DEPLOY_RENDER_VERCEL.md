# 🚀 Deploy to Render + Vercel

**Perfect combo:** Vercel hosts your blazing-fast frontend, Render hosts your backend + database.

Both platforms have generous free tiers and automatic HTTPS!

---

## 📋 Prerequisites

- GitHub account
- Render account (sign up at https://render.com)
- Vercel account (sign up at https://vercel.com)

---

## Step 1: Push to GitHub

First, commit all the deployment files:

```bash
# Make sure you're in the project root
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00

# Add all deployment configs
git add .

# Commit
git commit -m "Add Render + Vercel deployment configs"

# Push to GitHub
git push origin main
```

If you haven't set up a GitHub repo yet:

```bash
# Create new repo on GitHub (https://github.com/new)
# Then:
git init
git add .
git commit -m "Initial commit with deployment configs"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/opendiscuss_v00.git
git push -u origin main
```

---

## Step 2: Deploy Backend to Render (5 minutes)

### 2.1 Create Render Account
- Go to https://render.com
- Sign up with GitHub

### 2.2 Deploy from Blueprint

1. **Click "New +" → "Blueprint"**

2. **Connect Repository:**
   - Select your `opendiscuss_v00` repo
   - Click "Connect"

3. **Render Auto-Detects:**
   - Render finds `render.yaml`
   - Shows: Backend service, PostgreSQL, Redis
   - Click "Apply"

4. **Set API Keys:**
   - Go to backend service in dashboard
   - Environment → Add Environment Variable
   - Add:
     - `OPENAI_API_KEY`: `your-openai-key`
     - `ANTHROPIC_API_KEY`: `your-anthropic-key`
   - Click "Save Changes"

5. **Wait for Deployment:**
   - Watch logs (takes ~5 minutes)
   - When done, you'll see: `✓ Build successful!`

6. **Copy Backend URL:**
   - Look for: `https://opendiscuss-backend.onrender.com`
   - **Save this URL** - you'll need it for Vercel!

---

## Step 3: Deploy Frontend to Vercel (3 minutes)

### 3.1 Create Vercel Account
- Go to https://vercel.com
- Sign up with GitHub

### 3.2 Import Project

1. **Click "Add New..." → "Project"**

2. **Import Repository:**
   - Find `opendiscuss_v00`
   - Click "Import"

3. **Configure Project:**
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`

4. **Environment Variables:**
   Click "Environment Variables" and add:
   ```
   Name: VITE_API_URL
   Value: https://opendiscuss-backend.onrender.com
   ```
   (Use the URL from Step 2.6)

5. **Deploy:**
   - Click "Deploy"
   - Wait ~2 minutes
   - When done: `🎉 Deployed successfully!`

6. **Copy Frontend URL:**
   - Look for: `https://opendiscuss-v00.vercel.app`
   - This is your live app!

---

## Step 4: Update CORS Settings

Now that frontend is deployed, update backend to allow frontend domain:

1. **Go to Render Dashboard:**
   - Navigate to `opendiscuss-backend` service

2. **Update CORS_ORIGINS:**
   - Environment tab
   - Find `CORS_ORIGINS`
   - Change from `*` to: `https://opendiscuss-v00.vercel.app`
   - Click "Save Changes"
   - Backend will auto-redeploy

---

## Step 5: Test Your Deployment! 🎉

### Desktop Test:
1. Open `https://opendiscuss-v00.vercel.app`
2. Should load instantly
3. Test creating a discussion

### Mobile Test:
1. Open phone browser
2. Visit `https://opendiscuss-v00.vercel.app`
3. Works on any device!

### API Test:
```bash
curl https://opendiscuss-backend.onrender.com/health
# Should return: {"status":"ok"}
```

---

## 🎯 Your Live URLs

After deployment, you have:

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | `https://opendiscuss-v00.vercel.app` | Main app (share this!) |
| **Backend** | `https://opendiscuss-backend.onrender.com` | API |
| **Docs** | `https://opendiscuss-backend.onrender.com/docs` | API documentation |

---

## 🔄 Auto-Deploy on Git Push

Both platforms auto-deploy when you push to GitHub:

```bash
# Make changes to your code
git add .
git commit -m "Update feature"
git push origin main

# Vercel deploys frontend automatically
# Render deploys backend automatically
# Wait ~2-3 minutes
```

---

## 💰 Cost Breakdown

### Free Tier (Both Platforms):

**Render (Free):**
- ✅ Backend API
- ✅ PostgreSQL (256MB)
- ✅ Redis
- ⚠️ Services sleep after 15 min inactivity
- ⚠️ 750 hours/month (enough for 1 service always-on)

**Vercel (Free):**
- ✅ Frontend hosting
- ✅ 100GB bandwidth/month
- ✅ Automatic HTTPS
- ✅ Global CDN
- ✅ Always fast (no sleep)

**Total:** $0/month (perfect for testing/demos)

### Paid Tier (If Needed):

**Render ($7/month):**
- Always-on services (no sleep)
- More resources

**Vercel ($20/month):**
- Unlimited bandwidth
- Advanced features

**Total:** $7-27/month for production

---

## 🔧 Troubleshooting

### "Backend service is starting..."
- **Cause:** Free tier services sleep after 15 min
- **Fix:** First request wakes it up (takes ~30 seconds)
- **Upgrade:** Render Starter plan ($7/mo) keeps it always-on

### "API request failed"
- Check CORS settings in Render backend
- Ensure VITE_API_URL is correct in Vercel
- Check backend logs in Render dashboard

### "Database connection error"
- Wait for all services to start
- Check Render dashboard for service status
- Verify DATABASE_URL is set automatically

### "White screen on mobile"
- Open browser console (mobile Chrome → Settings → Developer)
- Check for CORS or API errors
- Ensure backend is awake

---

## 📱 Mobile Optimization

The app is already responsive, but you can add these improvements:

### Add to Home Screen (PWA):

1. **Install PWA plugin:**
```bash
cd frontend
npm install vite-plugin-pwa -D
```

2. **Update vite.config.ts:**
```typescript
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'OpenDiscuss',
        short_name: 'OpenDiscuss',
        description: 'Democratic discussion platform',
        theme_color: '#ffffff',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ]
})
```

3. **Redeploy:** Push to GitHub, Vercel auto-deploys

Now users can "Add to Home Screen" on mobile!

---

## 🔒 Security Best Practices

- [x] HTTPS automatic on both platforms ✅
- [x] Environment variables (never in code) ✅
- [ ] Update CORS_ORIGINS to your actual domain
- [ ] Change database password in Render dashboard
- [ ] Set up proper authentication for users
- [ ] Enable rate limiting in backend
- [ ] Add Sentry for error tracking (optional)

---

## 📊 Monitoring

### Free Monitoring Options:

**Vercel Analytics:**
- Built-in, enable in project settings
- See page views, performance

**Render Logs:**
- Dashboard → Service → Logs tab
- Real-time backend logs

**Uptime Robot:**
- https://uptimerobot.com (free)
- Monitors if your app is up
- Sends alerts if down

**Sentry (Error Tracking):**
```bash
# Frontend
cd frontend
npm install @sentry/react

# Add to main.tsx
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "YOUR_SENTRY_DSN",
  environment: "production"
});
```

---

## 🎨 Custom Domain (Optional)

### Add Your Domain to Vercel:

1. **Buy domain** (Namecheap, Google Domains, etc.)

2. **In Vercel:**
   - Project Settings → Domains
   - Add domain: `yourdomain.com`
   - Follow DNS instructions

3. **Update Backend CORS:**
   - In Render, update CORS_ORIGINS
   - Add: `https://yourdomain.com`

---

## 🚀 Performance Tips

### Frontend (Vercel):
- Already optimized with edge caching
- Vite creates optimized builds
- Images: Use Next.js Image or compress

### Backend (Render):
- Free tier sleeps → Upgrade to $7/mo for always-on
- Enable Redis caching (already configured)
- Add database indexes for common queries

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Backend deployed to Render
- [ ] Frontend deployed to Vercel
- [ ] API keys added to Render
- [ ] VITE_API_URL set in Vercel
- [ ] CORS updated with Vercel domain
- [ ] Tested on desktop
- [ ] Tested on mobile
- [ ] API health check passes
- [ ] Database connected
- [ ] Optional: Custom domain added
- [ ] Optional: Monitoring set up

---

## 🆘 Need Help?

**Render Support:**
- Docs: https://render.com/docs
- Community: https://community.render.com

**Vercel Support:**
- Docs: https://vercel.com/docs
- Discord: https://vercel.com/discord

**Your Project:**
- Open an issue on GitHub
- Check deployment logs in dashboards

---

## 🎉 You're Live!

Your app is now accessible from:
- ✅ Any desktop browser
- ✅ Any mobile device
- ✅ Anywhere in the world
- ✅ With automatic HTTPS

Share your Vercel URL with anyone and they can access it instantly!

Next: Run that 100-participant simulation and share the Sankey diagram! 🚀
