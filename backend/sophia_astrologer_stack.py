# /*********************************************************************************************************************
# *  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           *
# *                                                                                                                    *
# *  Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance        *
# *  with the License. A copy of the License is located at                                                             *
# *                                                                                                                    *
# *      http://aws.amazon.com/asl/                                                                                    *
# *                                                                                                                    *
# *  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES *
# *  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    *
# *  and limitations under the License.                                                                                *
# **********************************************************************************************************************/

"""
AWS CDK Stack for Sophia AI Astrologer

This module defines the AWS CDK stack for deploying Sophia, the AI Astrologer infrastructure.
It sets up all necessary AWS resources including:
- ECS Fargate service for running the Claude-based backend
- Network Load Balancer for handling WebSocket connections
- Cognito User Pool for authentication
- S3 and CloudFront for frontend hosting
- IAM roles with Claude 3 Sonnet and Polly permissions

The stack is designed to provide speech-to-speech astrological guidance
powered by Claude 3 Sonnet and AWS Polly.
"""

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr_assets as ecr_assets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_logs as logs,
    RemovalPolicy
)
from constructs import Construct

# Configuration
domain_name = "guardedai.co"
container_port = 8000

class SophiaAstrologerStack(Stack):
    """CDK Stack for Sophia AI Astrologer infrastructure."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create VPC with public subnets
        vpc = ec2.Vpc(self, "SophiaAstrologerVPC",
            max_azs=2,
            nat_gateways=0,  # Use public subnets only for cost optimization
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                )
            ]
        )
        
        # Build and push Docker image to ECR for Claude-based AI Astrologer
        docker_image = ecr_assets.DockerImageAsset(self, "SophiaAstrologerImage",
            directory=".",
            file="Dockerfile_claude",
            platform=ecr_assets.Platform.LINUX_AMD64
        )
        
        # Create Task Role with required permissions
        task_role = iam.Role(self, "SophiaAstrologerTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Task role for Sophia AI Astrologer ECS service"
        )
        
        # Add CloudWatch Logs permissions
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
        
        # Add Bedrock permissions for Claude 3 Sonnet and Polly for TTS
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel"
                ],
                resources=[
                    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                    "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-sonic-v1:0"
                ]
            )
        )
        
        # Add Polly permissions for text-to-speech
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "polly:SynthesizeSpeech"
                ],
                resources=["*"]
            )
        )
        
        # Create ECS Cluster
        cluster = ecs.Cluster(self, "SophiaAstrologerCluster",
            vpc=vpc,
            cluster_name="sophia-astrologer-cluster"
        )
        
        # Create ECS Task Definition
        task_definition = ecs.FargateTaskDefinition(self, "SophiaAstrologerTaskDefinition",
            memory_limit_mib=2048,
            cpu=1024,
            task_role=task_role
        )
        
        # Add container to task definition
        container = task_definition.add_container("SophiaAstrologerContainer",
            image=ecs.ContainerImage.from_docker_image_asset(docker_image),
            port_mappings=[
                ecs.PortMapping(
                    container_port=container_port,
                    protocol=ecs.Protocol.TCP
                )
            ],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="sophia-astrologer",
                log_retention=logs.RetentionDays.ONE_WEEK
            ),
            environment={
                "PORT": str(container_port)
            }
        )
        
        # Create Security Group for ECS service
        ecs_security_group = ec2.SecurityGroup(self, "SophiaAstrologerECSSecurityGroup",
            vpc=vpc,
            description="Security group for Sophia AI Astrologer ECS service",
            allow_all_outbound=True
        )
        
        ecs_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(container_port),
            description="Allow inbound traffic on container port"
        )
        
        # Create ECS Fargate Service
        fargate_service = ecs.FargateService(self, "SophiaAstrologerFargateService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[ecs_security_group],
            assign_public_ip=True,
            service_name="sophia-astrologer-service"
        )
        
        # Create Network Load Balancer
        nlb = elbv2.NetworkLoadBalancer(self, "SophiaAstrologerNLB",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name="sophia-astrologer-nlb"
        )
        
        # Create Target Group for NLB
        target_group = elbv2.NetworkTargetGroup(self, "SophiaAstrologerTargetGroup",
            port=container_port,
            protocol=elbv2.Protocol.TCP,
            vpc=vpc,
            target_type=elbv2.TargetType.IP
        )
        
        # Add ECS service to target group
        fargate_service.attach_to_network_target_group(target_group)
        
        # Create NLB Listener (HTTP for now, can add HTTPS later)
        nlb.add_listener("SophiaAstrologerNLBListener",
            port=80,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[target_group]
        )
        
        # Create Cognito User Pool
        user_pool = cognito.UserPool(self, "SophiaAstrologerUserPool",
            user_pool_name="sophia-astrologer-users",
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False
            ),
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Create Cognito User Pool Client
        user_pool_client = cognito.UserPoolClient(self, "SophiaAstrologerUserPoolClient",
            user_pool=user_pool,
            user_pool_client_name="sophia-astrologer-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            )
        )
        
        # Create Cognito Identity Pool
        identity_pool = cognito.CfnIdentityPool(self, "SophiaAstrologerIdentityPool",
            allow_unauthenticated_identities=False,
            allow_classic_flow=False,
            cognito_identity_providers=[cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                client_id=user_pool_client.user_pool_client_id,
                provider_name=user_pool.user_pool_provider_name
            )]
        )
        
        # Create S3 bucket for frontend hosting
        website_bucket = s3.Bucket(self, "SophiaAstrologerBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            bucket_name=f"sophia-astrologer-frontend-{self.account}-{self.region}"
        )
        
        # Create Origin Access Identity for CloudFront
        oai = cloudfront.OriginAccessIdentity(self, "SophiaAstrologerOAI",
            comment="OAI for Sophia AI Astrologer"
        )
        
        # Grant CloudFront access to S3 bucket
        website_bucket.grant_read(oai)
        
        # Create CloudFront distribution
        distribution = cloudfront.Distribution(self, "SophiaAstrologerDistribution",
            comment="Sophia AI Astrologer Frontend",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(website_bucket, origin_access_identity=oai),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html"
                )
            ]
        )
        
        # Output important values
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "IdentityPoolId", value=identity_pool.ref)
        CfnOutput(self, "CloudFrontURL", value=f"https://{distribution.distribution_domain_name}")
        CfnOutput(self, "CloudFrontDistributionId", value=distribution.distribution_id)
        CfnOutput(self, "NLBEndpoint", value=f"http://{nlb.load_balancer_dns_name}")
        CfnOutput(self, "FrontendBucket", value=website_bucket.bucket_name)
        CfnOutput(self, "WebSocketURL", value=f"ws://{nlb.load_balancer_dns_name}/ws")
