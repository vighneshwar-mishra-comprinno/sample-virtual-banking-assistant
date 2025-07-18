"""
Claude 3 Sonnet Astrologer with AWS Polly TTS
This module provides speech-to-speech functionality using Claude 3 Sonnet for text generation
and AWS Polly for text-to-speech synthesis.
"""

import asyncio
import json
import base64
import io
import wave
from typing import Optional, AsyncGenerator, Dict, Any
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class ClaudeAstrologer:
    """
    AI Astrologer using Claude 3 Sonnet for text generation and AWS Polly for speech synthesis.
    """
    
    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        region: str = "us-east-1",
        claude_model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        voice_id: str = "Joanna",  # Polly voice for the astrologer
        system_prompt_file: str = "prompt.txt"
    ):
        """
        Initialize the Claude Astrologer.
        
        Args:
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
            session_token: AWS session token
            region: AWS region
            claude_model: Claude model identifier
            voice_id: Polly voice ID (Joanna, Matthew, Amy, etc.)
            system_prompt_file: Path to the system prompt file
        """
        self.region = region
        self.claude_model = claude_model
        self.voice_id = voice_id
        
        # Initialize AWS clients
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
            region_name=region
        )
        
        self.bedrock_client = session.client('bedrock-runtime')
        self.polly_client = session.client('polly')
        self.transcribe_client = session.client('transcribe')
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt(system_prompt_file)
        
        # Conversation history
        self.conversation_history = []
        
    def _load_system_prompt(self, prompt_file: str) -> str:
        """Load the system prompt from file."""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"Prompt file {prompt_file} not found, using default")
            return "You are Sophia, a wise AI astrologer. Provide mystical yet practical guidance."
    
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio to text using AWS Transcribe.
        For now, we'll use a simple approach - in production, you might want to use
        streaming transcription or a more sophisticated method.
        """
        try:
            # For this implementation, we'll assume the audio is already transcribed
            # In a real implementation, you'd use AWS Transcribe streaming
            # or another speech-to-text service
            
            # Placeholder - in real implementation, integrate with Transcribe
            return "Hello, I'd like to know about my horoscope today."
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    async def generate_response(self, user_message: str) -> str:
        """
        Generate a response using Claude 3 Sonnet.
        """
        try:
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            # Prepare the request for Claude
            messages = [
                {"role": "user", "content": self.system_prompt},
                *self.conversation_history[-10:]  # Keep last 10 exchanges
            ]
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.7,
                "messages": messages
            }
            
            # Invoke Claude 3 Sonnet
            response = self.bedrock_client.invoke_model(
                modelId=self.claude_model,
                body=json.dumps(body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            assistant_message = response_body['content'][0]['text']
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            return assistant_message
            
        except ClientError as e:
            logger.error(f"Claude API error: {e}")
            return "I sense some cosmic interference in our connection. Please try again, dear soul."
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return "The stars are momentarily clouded. Let me try to reconnect with the cosmic energies."
    
    async def synthesize_speech(self, text: str) -> bytes:
        """
        Convert text to speech using AWS Polly.
        """
        try:
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat='pcm',
                VoiceId=self.voice_id,
                SampleRate='16000',
                TextType='text'
            )
            
            # Get the audio stream
            audio_stream = response['AudioStream']
            audio_data = audio_stream.read()
            
            return audio_data
            
        except ClientError as e:
            logger.error(f"Polly synthesis error: {e}")
            return b""
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
            return b""
    
    async def process_audio_chunk(self, audio_chunk: bytes) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process an audio chunk and yield response chunks.
        This simulates the streaming behavior of Nova Sonic.
        """
        try:
            # Step 1: Transcribe audio (simplified for this example)
            # In production, you'd use streaming transcription
            user_text = await self.transcribe_audio(audio_chunk)
            
            if not user_text.strip():
                return
            
            logger.info(f"User said: {user_text}")
            
            # Step 2: Generate response with Claude
            response_text = await self.generate_response(user_text)
            logger.info(f"Sophia responds: {response_text}")
            
            # Step 3: Convert to speech
            audio_data = await self.synthesize_speech(response_text)
            
            if audio_data:
                # Encode audio data as base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                # Yield the response in chunks (simulating streaming)
                chunk_size = 4096
                for i in range(0, len(audio_base64), chunk_size):
                    chunk = audio_base64[i:i + chunk_size]
                    yield {
                        "event": "media",
                        "data": chunk
                    }
                
                # Signal end of response
                yield {
                    "event": "stop"
                }
            
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            yield {
                "event": "error",
                "message": "I'm having trouble connecting with the cosmic energies right now."
            }
    
    def reset_conversation(self):
        """Reset the conversation history."""
        self.conversation_history = []
        logger.info("Conversation history reset")


class ClaudeAstrologerWebSocketHandler:
    """
    WebSocket handler for the Claude Astrologer.
    This class manages the WebSocket connection and audio streaming.
    """
    
    def __init__(self, claude_astrologer: ClaudeAstrologer):
        self.astrologer = claude_astrologer
        self.is_processing = False
    
    async def handle_audio_data(self, audio_data: str) -> AsyncGenerator[str, None]:
        """
        Handle incoming audio data and yield response messages.
        """
        if self.is_processing:
            return
        
        try:
            self.is_processing = True
            
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Process the audio and get responses
            async for response_chunk in self.astrologer.process_audio_chunk(audio_bytes):
                yield json.dumps(response_chunk)
                
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
            yield json.dumps({
                "event": "error",
                "message": "The cosmic connection was interrupted."
            })
        finally:
            self.is_processing = False
    
    async def handle_text_message(self, message: str) -> str:
        """
        Handle text-based messages (for testing or fallback).
        """
        try:
            response_text = await self.astrologer.generate_response(message)
            return json.dumps({
                "event": "text_response",
                "data": response_text
            })
        except Exception as e:
            logger.error(f"Text message handler error: {e}")
            return json.dumps({
                "event": "error",
                "message": "I couldn't process your message through the cosmic channels."
            })
