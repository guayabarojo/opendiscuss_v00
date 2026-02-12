# 🏗️ Deployment Architecture

## Render + Vercel Setup

```
                                    INTERNET
                                       │
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
                    │                                     │
            ┌───────▼────────┐                   ┌───────▼────────┐
            │                │                   │                │
            │    VERCEL      │                   │   USERS        │
            │   (Frontend)   │◄──────────────────│  (Desktop &    │
            │                │   HTTPS           │   Mobile)      │
            └───────┬────────┘                   └────────────────┘
                    │
                    │ API Calls
                    │ (HTTPS)
                    │
            ┌───────▼────────┐
            │                │
            │    RENDER      │
            │   (Backend)    │
            │                │
            └───────┬────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
┌───────▼──────┐ ┌──▼──────┐ ┌─▼──────┐
│ PostgreSQL   │ │  Redis  │ │ Python │
│   Database   │ │  Cache  │ │FastAPI │
│  (Render)    │ │(Render) │ │Backend │
└──────────────┘ └─────────┘ └────────┘
```

## Component Breakdown

### 🎨 Frontend (Vercel)
- **Tech:** React + Vite + TypeScript
- **URL:** `https://your-app.vercel.app`
- **Hosting:** Vercel Global CDN
- **Features:**
  - ✅ Always fast (edge caching)
  - ✅ Automatic HTTPS
  - ✅ Auto-deploy on git push
  - ✅ Free tier: 100GB bandwidth/month
  - ✅ No sleep (always available)

### ⚙️ Backend (Render)
- **Tech:** Python 3.11 + FastAPI
- **URL:** `https://your-backend.onrender.com`
- **Features:**
  - ✅ REST API
  - ✅ Automatic HTTPS
  - ✅ Auto-deploy on git push
  - ⚠️ Free tier sleeps after 15min (30s wake-up)
  - ✅ Upgrade to $7/mo for always-on

### 🗄️ Database (Render PostgreSQL)
- **Type:** PostgreSQL 15 with pgvector
- **Size:** 256MB (free tier)
- **Features:**
  - ✅ Automated backups
  - ✅ Persistent storage
  - ✅ Vector embeddings support

### 💾 Cache (Render Redis)
- **Type:** Redis 7
- **Size:** 25MB (free tier)
- **Uses:**
  - LLM response caching
  - Session management
  - Rate limiting

## Data Flow

```
User (Mobile/Desktop)
    │
    │ 1. Visits app
    ▼
Vercel Frontend
    │
    │ 2. Loads React app
    │ 3. User creates discussion
    ▼
Render Backend API
    │
    ├─ 4a. Save to PostgreSQL
    │       └─ Discussion data, participants, submissions
    │
    ├─ 4b. Cache in Redis
    │       └─ LLM responses, session data
    │
    ├─ 4c. Call LLM APIs
    │       └─ OpenAI, Anthropic (summaries, embeddings)
    │
    └─ 5. Return data
         │
         ▼
    Vercel Frontend
         │
         │ 6. Display Sankey diagram
         ▼
    User sees results!
```

## Security

```
┌─────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. HTTPS/TLS (Automatic)                              │
│     └─ All traffic encrypted                            │
│                                                         │
│  2. CORS Protection                                    │
│     └─ Only allowed origins                             │
│                                                         │
│  3. Environment Variables                              │
│     └─ Secrets never in code                            │
│                                                         │
│  4. Database Isolation                                 │
│     └─ Not publicly accessible                          │
│                                                         │
│  5. Rate Limiting                                      │
│     └─ Prevent abuse                                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Scaling Strategy

### Current Setup (Free Tier)
- **Users:** ~100 concurrent
- **Cost:** $0/month
- **Limitation:** Backend sleeps after 15min

### Small Production ($7/month)
- **Upgrade:** Render Starter plan
- **Users:** ~500 concurrent
- **Features:** Always-on, more resources

### Medium Production ($27/month)
- **Upgrade:** Render + Vercel Pro
- **Users:** ~5,000 concurrent
- **Features:** Advanced analytics, priority support

### Large Production ($100+/month)
- **Upgrade:** Dedicated infrastructure
- **Users:** 50,000+ concurrent
- **Tech:** Kubernetes, load balancers, CDN

## Monitoring

```
┌──────────────────┐
│  Vercel          │  → Page views, performance
│  Analytics       │     (free, built-in)
└──────────────────┘

┌──────────────────┐
│  Render          │  → Server logs, health
│  Dashboard       │     (free, built-in)
└──────────────────┘

┌──────────────────┐
│  Sentry          │  → Error tracking
│  (Optional)      │     (free tier available)
└──────────────────┘

┌──────────────────┐
│  UptimeRobot     │  → Uptime monitoring
│  (Optional)      │     (free)
└──────────────────┘
```

## Deployment Flow

```
Developer
    │
    │ git push
    ▼
GitHub Repo
    │
    ├───────────────┬───────────────┐
    │               │               │
    ▼               ▼               ▼
Vercel Auto     Render Auto    Render Auto
Deploy          Deploy          Deploy
(Frontend)      (Backend)       (Database)
    │               │               │
    │               │               │
    │   Builds in   │   Builds in   │   Provisions
    │   ~2 min      │   ~5 min      │   instantly
    │               │               │
    ▼               ▼               ▼
Live on CDN    Live on Server   Ready
    │               │               │
    └───────────────┴───────────────┘
                    │
                    ▼
            Users can access!
```

## Cost Comparison

| Platform | Free Tier | Paid Tier |
|----------|-----------|-----------|
| **Vercel (Frontend)** | ✅ 100GB bandwidth<br>✅ Always fast<br>✅ Unlimited sites | $20/mo<br>Unlimited bandwidth<br>Advanced features |
| **Render (Backend)** | ✅ 750 hours/mo<br>⚠️ Sleeps after 15min<br>✅ 256MB DB | $7/mo<br>Always-on<br>More resources |
| **Total** | **$0/month** | **$7-27/month** |

## Performance

### Frontend (Vercel)
- **Load Time:** < 1 second (global CDN)
- **Uptime:** 99.99%
- **Geography:** Serves from nearest edge

### Backend (Render - Free)
- **First Request:** ~30 seconds (wake-up)
- **Subsequent:** ~100-200ms
- **Uptime:** 99.9%

### Backend (Render - Paid)
- **All Requests:** ~100-200ms
- **Uptime:** 99.99%

## When to Upgrade

### Stay on Free Tier If:
- 👥 < 50 daily users
- 🧪 Testing/demo phase
- 💰 $0 budget
- ⏱️ OK with 30s wake-up time

### Upgrade to Paid If:
- 👥 > 100 daily users
- 🚀 Production ready
- 💼 Business/commercial use
- ⚡ Need instant response times
- 📊 Need detailed analytics

## Next: Deploy!

Ready to deploy? Follow: **DEPLOY_RENDER_VERCEL.md**

Questions? Check: **deployment-checklist.txt**
