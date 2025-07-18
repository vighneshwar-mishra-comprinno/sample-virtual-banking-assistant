# Quick Start Guide - GuardedAI Custom Domain Setup

## 🚀 One-Command Deployment

Once you have fresh AWS credentials, run this single command to deploy everything:

```bash
cd sample-virtual-banking-assistant
./deploy-custom-domain.sh
```

## 📋 What This Does

The deployment script will:
1. ✅ Deploy AWS infrastructure (ECS, NLB, CloudFront, Route 53, SSL Certificate)
2. ✅ Build and deploy the frontend with updated WebSocket URL
3. ✅ Configure custom domain `guardedai.co`
4. ✅ Set up WebSocket endpoint `wss://ws.guardedai.co/ws`
5. ✅ Provide DNS configuration instructions

## 🔧 Prerequisites

1. **Fresh AWS Credentials**: Make sure you have valid AWS credentials
   ```bash
   aws sts get-caller-identity  # Should return your account info
   ```

2. **Domain Ownership**: You must own `guardedai.co` domain

## 📝 Step-by-Step Process

### Step 1: Deploy Infrastructure
```bash
# Ensure you're in the right directory
cd sample-virtual-banking-assistant

# Run the deployment script
./deploy-custom-domain.sh
```

### Step 2: Configure DNS
After deployment, you'll get AWS Route 53 name servers. Update your domain registrar:

1. Go to your domain registrar (where you bought `guardedai.co`)
2. Find DNS/Nameserver settings
3. Replace existing nameservers with the AWS ones provided
4. Save changes

### Step 3: Wait for Propagation
- DNS propagation: 15 minutes to 48 hours (usually 30 minutes)
- SSL certificate validation: 5-30 minutes after DNS is configured

### Step 4: Test Your Application
```bash
# Run the testing script
./test-deployment.sh

# Or test manually:
curl -I https://guardedai.co
```

## 🧪 Testing & Verification

### Automated Testing
```bash
./test-deployment.sh
```

### Manual Testing
1. **Frontend**: Visit `https://guardedai.co`
2. **Login**: Use credentials `testuser` / `demo` with password `TempPassword123!`
3. **Audio**: Click "Engage" and test microphone functionality

## 🔍 Troubleshooting

### Common Issues

#### 1. AWS Credentials Expired
```bash
# Error: "The security token included in the request is expired"
# Solution: Get fresh credentials and re-run deployment
```

#### 2. DNS Not Propagating
```bash
# Check DNS status
dig guardedai.co
nslookup guardedai.co

# Clear local DNS cache
# macOS:
sudo dscacheutil -flushcache

# Windows:
ipconfig /flushdns
```

#### 3. WebSocket Connection Failed
- Ensure ECS service is running: `./test-deployment.sh`
- Check if DNS has propagated for `ws.guardedai.co`
- Verify Network Load Balancer is healthy

#### 4. SSL Certificate Issues
- Check AWS Certificate Manager in console
- Ensure DNS is properly configured at registrar
- Wait for automatic validation (up to 30 minutes)

## 📊 Expected Results

### After Successful Deployment:
- ✅ Frontend accessible at `https://guardedai.co`
- ✅ WebSocket connects to `wss://ws.guardedai.co/ws`
- ✅ Audio functionality works properly
- ✅ Avatar responds to voice input
- ✅ SSL certificate is valid

### Infrastructure Created:
- ECS Fargate service (backend)
- Network Load Balancer (WebSocket API)
- CloudFront distribution (frontend)
- S3 bucket (static files)
- Route 53 hosted zone (DNS)
- ACM certificate (SSL)
- Cognito User Pool (authentication)

## 🎯 Success Criteria

Your deployment is successful when:
1. `./test-deployment.sh` shows all tests passing
2. `https://guardedai.co` loads the application
3. You can log in with test credentials
4. Audio functionality works (avatar responds to voice)
5. No WebSocket connection errors in browser console

## 📞 Support

If you encounter issues:
1. Run `./test-deployment.sh` to identify problems
2. Check AWS CloudWatch logs for backend errors
3. Verify all AWS resources are healthy in the console
4. Ensure DNS is properly configured at your registrar

## 🔄 Re-deployment

To update or fix issues:
```bash
# Re-run the deployment script
./deploy-custom-domain.sh

# Or deploy just the CDK stack
cd backend
cdk deploy --require-approval never
```

---

**🎉 Once DNS propagates, your Astro Consultant will be live at https://guardedai.co with full audio functionality!**
