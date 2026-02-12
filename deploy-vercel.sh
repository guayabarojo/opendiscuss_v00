#!/bin/bash

# Quick Vercel + Render Deployment Script
# Run this after initial setup to deploy updates

set -e

echo "🚀 OpenDiscuss Deployment to Vercel + Render"
echo "=============================================="
echo ""

# Check if we're in the right directory
if [ ! -d "frontend" ]; then
    echo "❌ Error: frontend directory not found"
    echo "Please run this script from the project root"
    exit 1
fi

# Deploy Frontend to Vercel
echo "📦 Step 1: Deploying Frontend to Vercel..."
echo ""

cd frontend

# Check if Vercel is configured
if [ ! -f ".vercel/project.json" ]; then
    echo "⚙️  First time deployment - configuring Vercel..."
    echo ""
    echo "When prompted:"
    echo "  - Set up and deploy: Yes"
    echo "  - Scope: Select your account"
    echo "  - Link to existing project: No"
    echo "  - Project name: opendiscuss-v00 (or your choice)"
    echo "  - Directory: ./"
    echo "  - Override settings: No"
    echo ""
    vercel --prod
else
    echo "✅ Vercel already configured, deploying..."
    vercel --prod
fi

cd ..

echo ""
echo "=============================================="
echo "✅ Frontend Deployment Complete!"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Copy your frontend URL from above"
echo ""
echo "2. Deploy backend to Render:"
echo "   - Go to: https://render.com/login"
echo "   - New + → Blueprint"
echo "   - Select: guayabarojo/opendiscuss_v00"
echo "   - Render will auto-detect render.yaml"
echo "   - Click 'Apply'"
echo ""
echo "3. Set environment variables in Render dashboard:"
echo "   - OPENAI_API_KEY"
echo "   - ANTHROPIC_API_KEY"
echo "   - CORS_ORIGINS (add your Vercel URL)"
echo ""
echo "4. Your app will be live in ~5 minutes!"
echo ""
