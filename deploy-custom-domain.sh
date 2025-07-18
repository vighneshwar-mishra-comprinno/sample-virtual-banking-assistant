#!/bin/bash

# Deployment script for GuardedAI custom domain setup
# This script deploys the infrastructure and frontend with custom domain support

set -e  # Exit on any error

echo "🚀 Starting GuardedAI Custom Domain Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check AWS credentials
print_status "Checking AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    print_error "AWS credentials are not configured or expired."
    print_error "Please run: aws configure or set environment variables"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_status "Using AWS Account: $ACCOUNT_ID"

# Navigate to backend directory
cd backend

# Step 1: Deploy CDK Stack
print_status "Deploying CDK stack with custom domain configuration..."
cdk deploy --require-approval never

if [ $? -ne 0 ]; then
    print_error "CDK deployment failed!"
    exit 1
fi

print_status "CDK deployment completed successfully!"

# Step 2: Get stack outputs
print_status "Retrieving stack outputs..."
FRONTEND_BUCKET=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucket`].OutputValue' --output text)
DISTRIBUTION_ID=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' --output text 2>/dev/null || echo "")
HOSTED_ZONE_ID=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`HostedZoneId`].OutputValue' --output text)
CUSTOM_DOMAIN_URL=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`CustomDomainURL`].OutputValue' --output text)
WEBSOCKET_URL=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`WebSocketURL`].OutputValue' --output text)

print_status "Frontend Bucket: $FRONTEND_BUCKET"
print_status "Hosted Zone ID: $HOSTED_ZONE_ID"
print_status "Custom Domain: $CUSTOM_DOMAIN_URL"
print_status "WebSocket URL: $WEBSOCKET_URL"

# Step 3: Get CloudFront Distribution ID if not in outputs
if [ -z "$DISTRIBUTION_ID" ]; then
    print_status "Getting CloudFront Distribution ID..."
    DISTRIBUTION_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='Astro Consultant Frontend - GuardedAI'].Id" --output text)
fi

print_status "CloudFront Distribution ID: $DISTRIBUTION_ID"

# Step 4: Deploy frontend
print_status "Deploying frontend to S3..."
cd ../frontend/react-web

# Sync build files to S3
aws s3 sync build/ s3://$FRONTEND_BUCKET --delete

if [ $? -ne 0 ]; then
    print_error "Frontend deployment to S3 failed!"
    exit 1
fi

print_status "Frontend deployed to S3 successfully!"

# Step 5: Invalidate CloudFront cache
if [ ! -z "$DISTRIBUTION_ID" ]; then
    print_status "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
    print_status "CloudFront cache invalidation initiated!"
else
    print_warning "Could not find CloudFront Distribution ID. Cache invalidation skipped."
fi

# Step 6: Get Route 53 Name Servers
print_status "Getting Route 53 name servers for DNS configuration..."
NAME_SERVERS=$(aws route53 get-hosted-zone --id $HOSTED_ZONE_ID --query 'DelegationSet.NameServers' --output table)

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Next Steps:"
echo "=============="
echo ""
echo "1. Configure DNS at your domain registrar:"
echo "   - Go to your domain registrar where you bought 'guardedai.co'"
echo "   - Update the name servers to:"
echo "$NAME_SERVERS"
echo ""
echo "2. Wait for DNS propagation (up to 48 hours)"
echo ""
echo "3. Test your application:"
echo "   - Frontend: $CUSTOM_DOMAIN_URL"
echo "   - WebSocket: $WEBSOCKET_URL"
echo ""
echo "4. SSL Certificate validation:"
echo "   - The SSL certificate will be automatically validated via DNS"
echo "   - This may take 5-10 minutes after DNS is configured"
echo ""
echo "🔍 Monitoring:"
echo "   - Check certificate status in AWS Certificate Manager"
echo "   - Monitor Route 53 hosted zone for DNS queries"
echo "   - Test WebSocket connectivity once DNS propagates"
echo ""

# Step 7: Test current endpoints (before DNS propagation)
print_status "Testing current infrastructure..."

# Test ECS service
ECS_SERVICE_STATUS=$(aws ecs describe-services --cluster virtual-banking-assistant-cluster --services virtual-banking-assistant-service --query 'services[0].status' --output text 2>/dev/null || echo "NOT_FOUND")
print_status "ECS Service Status: $ECS_SERVICE_STATUS"

# Test load balancer
NLB_DNS=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`NLBEndpoint`].OutputValue' --output text)
print_status "Network Load Balancer: $NLB_DNS"

echo ""
echo "✅ Infrastructure is ready!"
echo "🌐 Configure DNS at your registrar to complete the setup."
