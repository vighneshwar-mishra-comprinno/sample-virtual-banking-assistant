#!/usr/bin/env python3

"""
CDK App for Sophia AI Astrologer

This is the main CDK application file for deploying Sophia, the AI Astrologer.
It creates and deploys the complete infrastructure stack including:
- Claude 3 Sonnet powered backend
- AWS Polly for text-to-speech
- ECS Fargate service
- Network Load Balancer
- S3 + CloudFront for frontend
- Cognito for authentication
"""

import aws_cdk as cdk
from sophia_astrologer_stack import SophiaAstrologerStack

app = cdk.App()

# Deploy Sophia AI Astrologer Stack
SophiaAstrologerStack(app, "SophiaAstrologerStack",
    description="Sophia AI Astrologer - Speech-to-speech astrological guidance powered by Claude 3 Sonnet",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1"
    )
)

app.synth()
