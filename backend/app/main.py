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
FastAPI WebSocket Server for Virtual Banking Assistant

This module implements a WebSocket server using FastAPI that handles real-time audio communication
between clients and an AI banking assistant powered by AWS Nova Sonic. It processes audio streams,
manages transcription, and coordinates responses through a pipeline architecture.

Key Components:
- WebSocket endpoint for real-time audio streaming
- Audio processing pipeline with VAD (Voice Activity Detection)
- Integration with AWS Nova Sonic LLM service
- Context management for conversation history
- Credential management for AWS services

Dependencies:
- FastAPI for WebSocket server
- Pipecat for audio processing pipeline
- AWS Bedrock for LLM services
- Silero VAD for voice activity detection

Environment Variables:
- AWS_CONTAINER_CREDENTIALS_RELATIVE_URI: URI for AWS container credentials
- AWS_ACCESS_KEY_ID: AWS access key
- AWS_SECRET_ACCESS_KEY: AWS secret key
- AWS_SESSION_TOKEN: AWS session token
"""

import asyncio
import json
import base64
import traceback
import boto3
import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, WebSocket, Request, Response
import uvicorn

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
# from pipecat.services.aws_nova_sonic.aws import AWSNovaSonicLLMService, Params
from aws import AWSNovaSonicLLMService, Params
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.processors.logger import FrameLogger
from pipecat.processors.transcript_processor import TranscriptProcessor

from base64_serializer import Base64AudioSerializer

SAMPLE_RATE = 16000
API_KEY = "Your-own-long-secret-text-to-access-the-api"

def update_dredentials():
    """
    Updates AWS credentials by fetching from ECS container metadata endpoint.
    Used in containerized environments to maintain fresh credentials.
    """
    try:
        uri = os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        if uri:
            print("Fetching fresh AWS credentials for Bedrock client", flush=True)
            with httpx.Client() as client:
                response = client.get(f"http://169.254.170.2{uri}")
                if response.status_code == 200:
                    creds = response.json()
                    os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                    os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                    os.environ["AWS_SESSION_TOKEN"] = creds["Token"]
                    print("AWS credentials refreshed successfully", flush=True)
                else:
                    print(f"Failed to fetch fresh credentials: {response.status_code}", flush=True)
    except Exception as e:
        print(f"Error refreshing credentials: {str(e)}", flush=True)

import boto3
from datetime import datetime

async def get_astrology_guidance(params: FunctionCallParams):
    """
    Get astrological guidance using OpenSearch knowledge base for money and health topics.
    """
    try:
        # Extract parameters
        birth_date = params.arguments.get("birth_date", "")
        birth_time = params.arguments.get("birth_time", "")
        birth_place = params.arguments.get("birth_place", "")
        query = params.arguments.get("query", "")
        topic = params.arguments.get("topic", "").lower()
        
        # Validate required parameters
        if not all([birth_date, birth_time, birth_place, query]):
            await params.result_callback({
                "message": "I need your complete birth details (date, time, place) and your specific question to provide accurate astrological guidance.",
                "missing_info": True
            })
            return
        
        # Initialize OpenSearch client for knowledge base
        try:
            opensearch_client = boto3.client('opensearchserverless', region_name='us-east-1')
            bedrock_agent = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
            
            # Query the knowledge base for astrology information
            knowledge_base_id = "G7IBKVWH1Q"
            
            # Construct query for knowledge base
            kb_query = f"Astrological guidance for {topic} born on {birth_date} at {birth_time} in {birth_place}. Question: {query}"
            
            # Query the knowledge base
            response = bedrock_agent.retrieve_and_generate(
                input={
                    'text': kb_query
                },
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': knowledge_base_id,
                        'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
                    }
                }
            )
            
            # Extract the generated response
            kb_response = response.get('output', {}).get('text', '')
            
            if kb_response:
                await params.result_callback({
                    "astrological_guidance": kb_response,
                    "birth_details": {
                        "date": birth_date,
                        "time": birth_time,
                        "place": birth_place
                    },
                    "topic": topic,
                    "source": "Astrological Knowledge Base"
                })
            else:
                # Fallback response if knowledge base doesn't return results
                await params.result_callback({
                    "astrological_guidance": f"Based on your birth details ({birth_date}, {birth_time}, {birth_place}), I can provide guidance on {topic}. However, I need to access more specific astrological calculations from my knowledge base. Please try rephrasing your question about {topic}.",
                    "birth_details": {
                        "date": birth_date,
                        "time": birth_time,
                        "place": birth_place
                    },
                    "topic": topic,
                    "source": "General Astrology"
                })
                
        except Exception as e:
            print(f"Knowledge base error: {str(e)}")
            # Fallback to basic astrological response
            await params.result_callback({
                "astrological_guidance": f"Based on your birth details from {birth_place} on {birth_date} at {birth_time}, I can provide some insights about {topic}. For more precise calculations, I recommend consulting detailed astrological charts.",
                "birth_details": {
                    "date": birth_date,
                    "time": birth_time,
                    "place": birth_place
                },
                "topic": topic,
                "source": "Basic Astrology",
                "note": "Knowledge base temporarily unavailable"
            })
            
    except Exception as e:
        print(f"Function error: {str(e)}")
        await params.result_callback({
            "message": "I'm having trouble processing your astrological request. Please provide your birth date, time, place, and specific question about money or health.",
            "error": True
        })

astrology_function = FunctionSchema(
    name="get_astrology_guidance",
    description="Get astrological guidance for money and health topics using birth details and knowledge base calculations.",
    properties={
        "birth_date": {
            "type": "string",
            "description": "Date of birth in DD/MM/YYYY format.",
        },
        "birth_time": {
            "type": "string",
            "description": "Time of birth in HH:MM AM/PM format.",
        },
        "birth_place": {
            "type": "string",
            "description": "Place of birth (City, Country).",
        },
        "query": {
            "type": "string",
            "description": "The specific question or issue the person is facing.",
        },
        "topic": {
            "type": "string",
            "description": "The main topic category: 'money', 'health', 'career', or 'relationships'.",
            "enum": ["money", "health", "career", "relationships"]
        }
    },
    required=["birth_date", "birth_time", "birth_place", "query", "topic"],
)

# Create tools schema
tools = ToolsSchema(standard_tools=[astrology_function])

async def setup(websocket: WebSocket):
    """
    Sets up the audio processing pipeline and WebSocket connection.
    
    Args:
        websocket: The WebSocket connection to set up

    Configures:
    - Audio transport with VAD and transcription
    - AWS Nova Sonic LLM service
    - Context management
    - Event handlers for client connection/disconnection
    """
    update_dredentials()
    
    system_instruction = Path('prompt.txt').read_text() + f"\n{AWSNovaSonicLLMService.AWAIT_TRIGGER_ASSISTANT_RESPONSE_INSTRUCTION}"

    # Configure WebSocket transport with audio processing capabilities
    transport = FastAPIWebsocketTransport(websocket, FastAPIWebsocketParams(
        serializer=Base64AudioSerializer(),
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=0.5)
        ),
        transcription_enabled=True
    ))

    # Configure AWS Nova Sonic parameters
    params = Params()
    params.input_sample_rate = SAMPLE_RATE
    params.output_sample_rate = SAMPLE_RATE

    # Initialize LLM service
    llm = AWSNovaSonicLLMService(
        secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        session_token=os.getenv("AWS_SESSION_TOKEN"),
        region='us-east-1',
        voice_id="tiffany",  # Available voices: matthew, tiffany, amy
        params=params
    )

    # Register function for function calls
    llm.register_function("get_astrology_guidance", get_astrology_guidance)

    # Set up conversation context
    context = OpenAILLMContext(
        messages=[
            {"role": "system", "content": f"{system_instruction}"},
        ],
        tools=tools,
    )
    context_aggregator = llm.create_context_aggregator(context)

    # Create transcript processor
    transcript = TranscriptProcessor()

    # Configure processing pipeline
    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            context_aggregator.user(),
            llm, 
            transport.output(),  # Transport bot output
            transcript.user(),
            transcript.assistant(), 
            context_aggregator.assistant(),
        ]
    )

    # Create pipeline task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        """Handles new client connections and initiates conversation."""
        print(f"Client connected")
        await task.queue_frames([context_aggregator.user().get_context_frame()])
        await llm.trigger_assistant_response()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        """Handles client disconnection and cleanup."""
        print(f"Client disconnected")
        await task.cancel()

    @transcript.event_handler("on_transcript_update")
    async def handle_transcript_update(processor, frame):
        """Logs transcript updates with timestamps."""
        for message in frame.messages:
            print(f"Transcript: [{message.timestamp}] {message.role}: {message.content}")

    runner = PipelineRunner(handle_sigint=False, force_gc=True)
    await runner.run(task)

# Initialize FastAPI application
app = FastAPI()

@app.get('/health')
async def health(request: Request):
    """Health check endpoint."""
    return 'ok'

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint handling client connections.
    Validates API key and sets up the audio processing pipeline.
    """
    protocol = websocket.headers.get('sec-websocket-protocol')
    print('protocol ', protocol)

    await websocket.accept(subprotocol=API_KEY)
    await setup(websocket)

# Configure and start uvicorn server
server = uvicorn.Server(uvicorn.Config(
    app=app,
    host='0.0.0.0',
    port=8000,
    log_level="error"
))

async def serve():
    """Starts the FastAPI server."""
    await server.serve()

# Run the server
asyncio.run(serve())
