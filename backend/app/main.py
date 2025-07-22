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

async def get_astrology_reading(params: FunctionCallParams):
    """
    Provide astrological analysis using Claude 4 based on birth information
    """
    try:
        from astrology_analysis import astrology_analyzer
        
        birth_date = params.arguments.get("birth_date", "")
        birth_time = params.arguments.get("birth_time", "")
        birth_place = params.arguments.get("birth_place", "")
        question_type = params.arguments.get("question_type", "money")
        specific_question = params.arguments.get("specific_question", "")
        
        # Validate birth information
        is_valid, error_msg = astrology_analyzer.validate_birth_info(birth_date, birth_time, birth_place)
        
        if not is_valid:
            await params.result_callback({
                "message": error_msg
            })
            return
        
        # Get astrological analysis from Claude 4
        analysis = astrology_analyzer.analyze_birth_chart(
            birth_date=birth_date,
            birth_time=birth_time,
            birth_place=birth_place,
            question_type=question_type,
            specific_question=specific_question
        )
        
        await params.result_callback({
            "analysis": analysis,
            "birth_info": f"Born {birth_date} at {birth_time} in {birth_place}",
            "focus": question_type
        })
        
    except Exception as e:
        print(f"Error in astrology reading: {str(e)}", flush=True)
        await params.result_callback({
            "message": "I'm having trouble accessing the cosmic insights right now. Please try again."
        })

astrology_function = FunctionSchema(
    name="get_astrology_reading",
    description="Get comprehensive astrological analysis for money or health guidance based on birth chart information using traditional astrological principles and calculations.",
    properties={
        "birth_date": {
            "type": "string",
            "description": "Date of birth in DD/MM/YYYY format (e.g., 15/03/1990).",
        },
        "birth_time": {
            "type": "string", 
            "description": "Time of birth in HH:MM AM/PM format (e.g., 2:30 PM).",
        },
        "birth_place": {
            "type": "string",
            "description": "Place of birth as City, Country (e.g., New York, USA).",
        },
        "question_type": {
            "type": "string",
            "description": "Type of astrological guidance needed: either 'money' for financial matters or 'health' for wellness guidance.",
            "enum": ["money", "health"]
        },
        "specific_question": {
            "type": "string",
            "description": "Optional: Specific question about money or health matters for detailed analysis.",
        }
    },
    required=["birth_date", "birth_time", "birth_place", "question_type"],
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
    llm.register_function("get_astrology_reading", get_astrology_reading)

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
