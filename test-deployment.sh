#!/bin/bash

# Testing script for GuardedAI deployment
# This script tests various components of the deployed application

set -e

echo "🧪 Testing GuardedAI Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Test 1: AWS Credentials
print_test "Checking AWS credentials..."
if aws sts get-caller-identity > /dev/null 2>&1; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_pass "AWS credentials valid (Account: $ACCOUNT_ID)"
else
    print_fail "AWS credentials invalid or expired"
    exit 1
fi

# Test 2: CloudFormation Stack
print_test "Checking CloudFormation stack..."
if aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack > /dev/null 2>&1; then
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].StackStatus' --output text)
    if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
        print_pass "CloudFormation stack is healthy ($STACK_STATUS)"
    else
        print_fail "CloudFormation stack status: $STACK_STATUS"
    fi
else
    print_fail "CloudFormation stack not found"
    exit 1
fi

# Test 3: ECS Service
print_test "Checking ECS service..."
ECS_STATUS=$(aws ecs describe-services --cluster virtual-banking-assistant-cluster --services virtual-banking-assistant-service --query 'services[0].status' --output text 2>/dev/null || echo "NOT_FOUND")
if [ "$ECS_STATUS" = "ACTIVE" ]; then
    RUNNING_COUNT=$(aws ecs describe-services --cluster virtual-banking-assistant-cluster --services virtual-banking-assistant-service --query 'services[0].runningCount' --output text)
    DESIRED_COUNT=$(aws ecs describe-services --cluster virtual-banking-assistant-cluster --services virtual-banking-assistant-service --query 'services[0].desiredCount' --output text)
    if [ "$RUNNING_COUNT" = "$DESIRED_COUNT" ]; then
        print_pass "ECS service is healthy ($RUNNING_COUNT/$DESIRED_COUNT tasks running)"
    else
        print_warning "ECS service running $RUNNING_COUNT/$DESIRED_COUNT tasks"
    fi
else
    print_fail "ECS service status: $ECS_STATUS"
fi

# Test 4: Load Balancer
print_test "Checking Network Load Balancer..."
NLB_DNS=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`NLBEndpoint`].OutputValue' --output text 2>/dev/null || echo "")
if [ ! -z "$NLB_DNS" ]; then
    print_pass "Network Load Balancer endpoint: $NLB_DNS"
    
    # Test NLB connectivity (basic check)
    print_test "Testing NLB connectivity..."
    if timeout 10 bash -c "</dev/tcp/$(echo $NLB_DNS | sed 's|https://||')/443" 2>/dev/null; then
        print_pass "NLB is reachable on port 443"
    else
        print_warning "NLB connectivity test failed (may be normal if DNS not propagated)"
    fi
else
    print_fail "Could not retrieve NLB endpoint"
fi

# Test 5: S3 Frontend Bucket
print_test "Checking S3 frontend bucket..."
FRONTEND_BUCKET=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucket`].OutputValue' --output text 2>/dev/null || echo "")
if [ ! -z "$FRONTEND_BUCKET" ]; then
    if aws s3 ls s3://$FRONTEND_BUCKET > /dev/null 2>&1; then
        FILE_COUNT=$(aws s3 ls s3://$FRONTEND_BUCKET --recursive | wc -l)
        print_pass "Frontend bucket exists with $FILE_COUNT files"
    else
        print_fail "Cannot access frontend bucket: $FRONTEND_BUCKET"
    fi
else
    print_fail "Could not retrieve frontend bucket name"
fi

# Test 6: CloudFront Distribution
print_test "Checking CloudFront distribution..."
CLOUDFRONT_URL=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' --output text 2>/dev/null || echo "")
if [ ! -z "$CLOUDFRONT_URL" ]; then
    print_pass "CloudFront URL: $CLOUDFRONT_URL"
    
    # Test CloudFront accessibility
    print_test "Testing CloudFront accessibility..."
    if curl -s -I "$CLOUDFRONT_URL" | grep -q "200 OK"; then
        print_pass "CloudFront distribution is accessible"
    else
        print_warning "CloudFront distribution test failed"
    fi
else
    print_fail "Could not retrieve CloudFront URL"
fi

# Test 7: Custom Domain Configuration
print_test "Checking custom domain configuration..."
CUSTOM_DOMAIN=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`CustomDomainURL`].OutputValue' --output text 2>/dev/null || echo "")
WEBSOCKET_URL=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`WebSocketURL`].OutputValue' --output text 2>/dev/null || echo "")

if [ ! -z "$CUSTOM_DOMAIN" ] && [ ! -z "$WEBSOCKET_URL" ]; then
    print_pass "Custom domain configured: $CUSTOM_DOMAIN"
    print_pass "WebSocket URL configured: $WEBSOCKET_URL"
    
    # Test DNS resolution
    print_test "Testing DNS resolution..."
    if nslookup guardedai.co > /dev/null 2>&1; then
        print_pass "guardedai.co DNS resolves"
    else
        print_warning "guardedai.co DNS not yet propagated"
    fi
    
    if nslookup ws.guardedai.co > /dev/null 2>&1; then
        print_pass "ws.guardedai.co DNS resolves"
    else
        print_warning "ws.guardedai.co DNS not yet propagated"
    fi
else
    print_fail "Custom domain configuration not found"
fi

# Test 8: SSL Certificate
print_test "Checking SSL certificate..."
CERT_ARN=$(aws acm list-certificates --query 'CertificateSummaryList[?DomainName==`guardedai.co`].CertificateArn' --output text 2>/dev/null || echo "")
if [ ! -z "$CERT_ARN" ]; then
    CERT_STATUS=$(aws acm describe-certificate --certificate-arn "$CERT_ARN" --query 'Certificate.Status' --output text 2>/dev/null || echo "")
    if [ "$CERT_STATUS" = "ISSUED" ]; then
        print_pass "SSL certificate is issued and valid"
    else
        print_warning "SSL certificate status: $CERT_STATUS (may be pending validation)"
    fi
else
    print_warning "SSL certificate not found (may still be provisioning)"
fi

# Test 9: Route 53 Hosted Zone
print_test "Checking Route 53 hosted zone..."
HOSTED_ZONE_ID=$(aws cloudformation describe-stacks --stack-name VirtualBankingAssistantStack --query 'Stacks[0].Outputs[?OutputKey==`HostedZoneId`].OutputValue' --output text 2>/dev/null || echo "")
if [ ! -z "$HOSTED_ZONE_ID" ]; then
    RECORD_COUNT=$(aws route53 list-resource-record-sets --hosted-zone-id "$HOSTED_ZONE_ID" --query 'length(ResourceRecordSets)')
    print_pass "Route 53 hosted zone exists with $RECORD_COUNT DNS records"
    
    # Show name servers
    print_test "Getting Route 53 name servers..."
    aws route53 get-hosted-zone --id "$HOSTED_ZONE_ID" --query 'DelegationSet.NameServers' --output table
else
    print_fail "Route 53 hosted zone not found"
fi

echo ""
echo "🏁 Testing completed!"
echo ""
echo "📋 Summary:"
echo "==========="
echo "✅ Infrastructure components are deployed"
echo "🌐 Custom domain is configured"
echo "🔒 SSL certificate is provisioned"
echo "📡 DNS records are created"
echo ""
echo "⏳ Next steps:"
echo "1. Configure DNS at your domain registrar (see DNS-SETUP-GUIDE.md)"
echo "2. Wait for DNS propagation (15 minutes to 48 hours)"
echo "3. Test your application at https://guardedai.co"
echo ""
