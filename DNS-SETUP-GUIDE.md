# DNS Setup Guide for guardedai.co

## Overview
This guide will help you configure DNS for your custom domain `guardedai.co` to work with your Astro Consultant application.

## Prerequisites
- You own the domain `guardedai.co`
- AWS infrastructure has been deployed successfully
- You have access to your domain registrar's DNS management

## Step 1: Get Name Servers from AWS

After running the deployment script, you'll receive AWS Route 53 name servers. They will look like:
```
ns-1234.awsdns-12.org
ns-5678.awsdns-56.net
ns-9012.awsdns-90.com
ns-3456.awsdns-34.co.uk
```

## Step 2: Configure DNS at Your Registrar

### For Common Registrars:

#### GoDaddy
1. Log into your GoDaddy account
2. Go to "My Products" → "Domains"
3. Click on `guardedai.co`
4. Click "Manage DNS"
5. In the "Nameservers" section, select "Custom"
6. Replace the existing nameservers with the AWS Route 53 nameservers
7. Save changes

#### Namecheap
1. Log into your Namecheap account
2. Go to "Domain List"
3. Click "Manage" next to `guardedai.co`
4. In the "Nameservers" section, select "Custom DNS"
5. Enter the AWS Route 53 nameservers
6. Save changes

#### Cloudflare
1. Log into your Cloudflare account
2. Add `guardedai.co` as a new site
3. Follow Cloudflare's instructions to change nameservers at your registrar
4. **Note**: If using Cloudflare, you'll need to create the DNS records manually in Cloudflare instead of using Route 53

#### Other Registrars
1. Log into your domain registrar's control panel
2. Find the DNS or Nameserver management section
3. Change from default nameservers to "Custom" nameservers
4. Enter the AWS Route 53 nameservers provided
5. Save changes

## Step 3: Verify DNS Configuration

### Using Command Line Tools:
```bash
# Check if DNS is propagating
dig guardedai.co

# Check specific nameservers
dig @8.8.8.8 guardedai.co

# Check WebSocket subdomain
dig ws.guardedai.co
```

### Using Online Tools:
- [whatsmydns.net](https://www.whatsmydns.net/) - Check global DNS propagation
- [dnschecker.org](https://dnschecker.org/) - Verify DNS records worldwide

## Step 4: SSL Certificate Validation

The SSL certificate will be automatically validated via DNS once the nameservers are configured. This process:
- Takes 5-10 minutes after DNS is properly configured
- Is handled automatically by AWS Certificate Manager
- Can be monitored in the AWS Console under Certificate Manager

## Step 5: Test Your Application

Once DNS propagates (can take up to 48 hours, but usually 15-30 minutes):

### Frontend Test:
```bash
curl -I https://guardedai.co
```
Should return a 200 OK response.

### WebSocket Test:
Open browser developer tools and try connecting to:
```
wss://ws.guardedai.co/ws
```

## Troubleshooting

### DNS Not Propagating
- Wait longer (up to 48 hours)
- Clear your local DNS cache:
  - Windows: `ipconfig /flushdns`
  - macOS: `sudo dscacheutil -flushcache`
  - Linux: `sudo systemctl restart systemd-resolved`

### SSL Certificate Issues
- Check AWS Certificate Manager in the console
- Ensure DNS records are properly configured
- Wait for automatic validation (can take up to 30 minutes)

### WebSocket Connection Issues
- Verify the backend ECS service is running
- Check Network Load Balancer health checks
- Ensure security groups allow traffic on the correct ports

## Expected Timeline
- **DNS Configuration**: 5 minutes
- **DNS Propagation**: 15 minutes to 48 hours (typically 30 minutes)
- **SSL Certificate Validation**: 5-30 minutes after DNS is configured
- **Full Functionality**: Available once DNS propagates and SSL is validated

## Support
If you encounter issues:
1. Check the AWS CloudFormation stack for any errors
2. Verify ECS service is running and healthy
3. Check CloudWatch logs for backend service errors
4. Ensure all security groups and network ACLs are properly configured
