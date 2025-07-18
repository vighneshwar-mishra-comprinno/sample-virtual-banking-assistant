"""
FastAPI WebSocket Server for AI Astrologer

This module implements a WebSocket server using FastAPI that handles real-time audio communication
between clients and Sophia, an AI astrologer powered by Claude 3 Sonnet and AWS Polly.

Key Components:
- WebSocket endpoint for real-time audio streaming
- Claude 3 Sonnet for intelligent astrological responses
- AWS Polly for natural text-to-speech synthesis
- Simple audio processing without complex pipelines

Dependencies:
- FastAPI for WebSocket server
- Claude 3 Sonnet via AWS Bedrock
- AWS Polly for speech synthesis
- AWS Transcribe for speech-to-text (future enhancement)
"""

import asyncio
import json
import base64
import traceback
import boto3
import os
from datetime import datetime
from pathlib import Path
import logging

from fastapi import FastAPI, WebSocket, Request, Response, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from claude_astrologer_v2 import PracticalClaudeAstrologer, PracticalWebSocketHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Key for WebSocket authentication
API_KEY = "Your-own-long-secret-text-to-access-the-api"

# Initialize FastAPI app
app = FastAPI(title="Sophia - AI Astrologer", description="Speech-to-speech AI astrologer powered by Claude 3 Sonnet")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_aws_credentials():
    """
    Get AWS credentials from environment or container metadata.
    """
    try:
        # Try to get credentials from environment
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        session_token = os.getenv('AWS_SESSION_TOKEN')
        
        if access_key and secret_key:
            return access_key, secret_key, session_token
        
        # Try to get credentials from container metadata
        container_credentials_uri = os.getenv('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI')
        if container_credentials_uri:
            import httpx
            response = httpx.get(f"http://169.254.170.2{container_credentials_uri}")
            if response.status_code == 200:
                creds = response.json()
                return creds['AccessKeyId'], creds['SecretAccessKey'], creds['Token']
        
        # Fallback to default credentials
        return None, None, None
        
    except Exception as e:
        logger.error(f"Error getting AWS credentials: {e}")
        return None, None, None

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Sophia AI Astrologer", "timestamp": datetime.now().isoformat()}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio communication with Sophia the AI Astrologer.
    """
    try:
        # Validate API key
        protocol = websocket.headers.get('sec-websocket-protocol')
        logger.info(f'WebSocket protocol: {protocol}')
        
        if protocol != API_KEY:
            logger.warning("Invalid API key provided")
            await websocket.close(code=1008, reason="Invalid API key")
            return
        
        # Accept WebSocket connection
        await websocket.accept(subprotocol=API_KEY)
        logger.info("WebSocket connection established")
        
        # Get AWS credentials
        access_key, secret_key, session_token = get_aws_credentials()
        
        # Initialize Claude Astrologer
        claude_astrologer = PracticalClaudeAstrologer(
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=session_token,
            region="us-east-1",
            voice_id="Joanna",  # Warm, friendly voice for the astrologer
            system_prompt_file="prompt.txt"
        )
        
        # Initialize WebSocket handler
        ws_handler = PracticalWebSocketHandler(claude_astrologer)
        
        logger.info("Sophia the AI Astrologer is ready to provide cosmic guidance")
        
        # Send welcome message
        welcome_text = "Greetings, dear soul. I am Sophia, your AI astrologer. The stars have aligned for our meeting today. How may I guide you through the cosmic energies?"
        welcome_audio = await claude_astrologer._synthesize_speech(welcome_text)
        
        if welcome_audio:
            welcome_base64 = base64.b64encode(welcome_audio).decode('utf-8')
            await websocket.send_text(json.dumps({
                "event": "media",
                "data": welcome_base64
            }))
            await websocket.send_text(json.dumps({"event": "stop"}))
        
        # Handle incoming messages
        while True:
            try:
                # Receive message from client
                message = await websocket.receive_text()
                logger.info(f"Received message: {message[:100]}...")
                
                # Check if it's audio data (base64 encoded)
                if message and len(message) > 100:  # Likely audio data
                    # Process audio data
                    async for response in ws_handler.handle_audio_data(message):
                        await websocket.send_text(response)
                else:
                    # Handle as text message (for testing)
                    try:
                        parsed_message = json.loads(message)
                        if parsed_message.get("type") == "text":
                            text_response = await ws_handler.handle_text_message(parsed_message.get("content", ""))
                            await websocket.send_text(text_response)
                    except json.JSONDecodeError:
                        # Treat as plain text
                        text_response = await ws_handler.handle_text_message(message)
                        await websocket.send_text(text_response)
                        
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                logger.error(traceback.format_exc())
                
                # Send error response
                error_response = json.dumps({
                    "event": "error",
                    "message": "I sense some cosmic interference. Please try again, dear soul."
                })
                await websocket.send_text(error_response)
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        logger.error(traceback.format_exc())
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Sophia - AI Astrologer",
        "description": "Speech-to-speech AI astrologer powered by Claude 3 Sonnet",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health"
        },
        "features": [
            "Real-time audio communication",
            "Astrological guidance and insights",
            "Birth chart analysis",
            "Daily horoscopes",
            "Relationship compatibility",
            "Career guidance"
        ]
    }

if __name__ == "__main__":
    # Configure uvicorn server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )
