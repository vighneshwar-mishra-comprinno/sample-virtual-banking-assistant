/*********************************************************************************************************************
*  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           *
*                                                                                                                    *
*  Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance        *
*  with the License. A copy of the License is located at                                                             *
*                                                                                                                    *
*      http://aws.amazon.com/asl/                                                                                    *
*                                                                                                                    *
*  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES *
*  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    *
*  and limitations under the License.                                                                                *
**********************************************************************************************************************/

/**
 * AWS Configuration for AI Astrologer with Nova Sonic
 * 
 * This module exports configuration settings for AWS services used by the application.
 * Values are populated during deployment from CloudFormation outputs.
 */

/**
 * AWS Amplify authentication configuration.
 * Contains Cognito User Pool and Identity Pool settings for user authentication.
 * 
 * @constant
 * @type {Object}
 * @property {string} Auth.Cognito.userPoolClientId - Cognito User Pool Client ID
 * @property {string} Auth.Cognito.userPoolId - Cognito User Pool ID
 * @property {string} Auth.Cognito.identityPoolId - Cognito Identity Pool ID
 * @property {string} Auth.Cognito.region - AWS region for Cognito services
 */
export const awsConfig = {
    Auth: {
        Cognito: {
            userPoolClientId: '3cges9l6tndtdrvougjoqm5r8u',
            userPoolId: 'us-east-1_EIM8Flata',
            identityPoolId: 'us-east-1:262d1551-cdc5-4c02-8028-4810360a2bbe',
            region: 'us-east-1'
        }
    }
}

/**
 * WebSocket API secret
 * 
 * @constant
 * @type {string}
 */
export const apiKey = "Your-own-long-secret-text-to-access-the-api"

/**
 * WebSocket endpoint URL - Using HTTP WebSocket for development with correct Load Balancer DNS
 * 
 * @constant
 * @type {string}
 */
export const apiUrl = "ws://Virtua-Virtu-GrFnAXxZKoUs-55b2890dc973f850.elb.us-east-1.amazonaws.com/ws"

/**
 * Avatar .glb model filename
 * 
 * @constant
 * @type {string}
 */
export const avatarFileName = "sophia.glb"

/**
 * Avatar jaw bone name
 * 
 * @constant
 * @type {string}
 */
export const avatarJawboneName = "rp_sophia_animated_003_idling_jaw"
