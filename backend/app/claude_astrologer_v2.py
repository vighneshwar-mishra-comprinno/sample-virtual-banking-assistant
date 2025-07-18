"""
Practical Claude 3 Sonnet Astrologer with Speech Processing
This implementation provides a more realistic approach to speech-to-speech
using Claude 3 Sonnet for text generation and AWS Polly for TTS.
"""

import asyncio
import json
import base64
import io
import wave
import tempfile
import os
from typing import Optional, AsyncGenerator, Dict, Any, List
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class PracticalClaudeAstrologer:
    """
    AI Astrologer using Claude 3 Sonnet with practical audio handling.
    """
    
    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        region: str = "us-east-1",
        claude_model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        voice_id: str = "Joanna",
        system_prompt_file: str = "prompt.txt"
    ):
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
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt(system_prompt_file)
        
        # Conversation history
        self.conversation_history = []
        
        # Audio buffer for accumulating audio chunks
        self.audio_buffer = []
        self.is_listening = False
        self.silence_threshold = 0.01
        self.min_audio_length = 1.0  # seconds
        
    def _load_system_prompt(self, prompt_file: str) -> str:
        """Load the system prompt from file."""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"Prompt file {prompt_file} not found, using default")
            return "You are Sophia, a wise AI astrologer. Provide mystical yet practical guidance."
    
    def _detect_speech_end(self, audio_chunk: bytes) -> bool:
        """
        Simple speech end detection based on audio energy.
        In production, you'd use a more sophisticated VAD.
        """
        try:
            # Convert bytes to audio samples (assuming 16-bit PCM)
            import struct
            samples = struct.unpack('<' + 'h' * (len(audio_chunk) // 2), audio_chunk)
            
            # Calculate RMS energy
            if len(samples) > 0:
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                normalized_rms = rms / 32768.0  # Normalize to 0-1
                
                # If energy is below threshold, consider it silence
                return normalized_rms < self.silence_threshold
            
            return True
        except Exception as e:
            logger.error(f"Speech detection error: {e}")
            return False
    
    async def process_audio_chunk(self, audio_chunk_b64: str) -> Optional[str]:
        """
        Process an audio chunk. Accumulate until speech ends, then process.
        """
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_chunk_b64)
            
            # Add to buffer
            self.audio_buffer.append(audio_bytes)
            
            # Check if speech has ended
            if self._detect_speech_end(audio_bytes):
                if len(self.audio_buffer) > 10:  # Minimum chunks for processing
                    # Combine all audio chunks
                    combined_audio = b''.join(self.audio_buffer)
                    
                    # Process the complete audio
                    result = await self._process_complete_audio(combined_audio)
                    
                    # Clear buffer
                    self.audio_buffer = []
                    
                    return result
            
            return None
            
        except Exception as e:
            logger.error(f"Audio chunk processing error: {e}")
            return None
    
    async def _process_complete_audio(self, audio_data: bytes) -> str:
        """
        Process complete audio: transcribe -> generate response -> synthesize speech
        """
        try:
            # Step 1: Transcribe audio (simplified - in production use AWS Transcribe)
            user_text = await self._transcribe_audio(audio_data)
            
            if not user_text.strip():
                return ""
            
            logger.info(f"User said: {user_text}")
            
            # Step 2: Generate response with Claude
            response_text = await self._generate_claude_response(user_text)
            logger.info(f"Sophia responds: {response_text}")
            
            # Step 3: Convert to speech
            audio_response = await self._synthesize_speech(response_text)
            
            if audio_response:
                return base64.b64encode(audio_response).decode('utf-8')
            
            return ""
            
        except Exception as e:
            logger.error(f"Complete audio processing error: {e}")
            return ""
    
    async def _transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio to text. 
        For this demo, we'll simulate transcription.
        In production, integrate with AWS Transcribe or another STT service.
        """
        # Simulate different user queries for demo
        import random
        demo_queries = [
            "What does my horoscope say for today?",
            "Can you tell me about my compatibility with a Leo?",
            "What career path should I consider based on my birth chart?",
            "When is the best time for me to make important decisions?",
            "What do the stars say about my love life?",
            "Can you give me guidance about my spiritual journey?",
            "What does Mercury retrograde mean for me?",
            "How will the full moon affect my energy?",
            "What are my natural talents according to astrology?",
            "Should I start a new project this month?"
        ]
        
        # Return a random query for demo purposes
        return random.choice(demo_queries)
    
    async def _generate_claude_response(self, user_message: str) -> str:
        """Generate response using Claude 3 Sonnet."""
        try:
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            # Prepare messages for Claude
            messages = [
                {"role": "user", "content": self.system_prompt},
                *self.conversation_history[-6:]  # Keep last 6 exchanges
            ]
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 800,
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
            
            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            return assistant_message
            
        except ClientError as e:
            logger.error(f"Claude API error: {e}")
            return "I sense some cosmic interference in our connection. The stars are momentarily clouded, but I'm here to guide you."
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return "The celestial energies are shifting. Let me realign with the cosmic forces to better assist you."
    
    async def _synthesize_speech(self, text: str) -> bytes:
        """Convert text to speech using AWS Polly."""
        try:
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat='pcm',
                VoiceId=self.voice_id,
                SampleRate='16000',
                TextType='text'
            )
            
            audio_stream = response['AudioStream']
            return audio_stream.read()
            
        except ClientError as e:
            logger.error(f"Polly synthesis error: {e}")
            return b""
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
            return b""
    
    def reset_conversation(self):
        """Reset conversation history and audio buffer."""
        self.conversation_history = []
        self.audio_buffer = []
        logger.info("Conversation and audio buffer reset")


class PracticalWebSocketHandler:
    """WebSocket handler for the practical Claude Astrologer."""
    
    def __init__(self, astrologer: PracticalClaudeAstrologer):
        self.astrologer = astrologer
        self.is_processing = False
    
    async def handle_audio_data(self, audio_data: str) -> AsyncGenerator[str, None]:
        """Handle incoming audio data."""
        try:
            # Process the audio chunk
            response_audio = await self.astrologer.process_audio_chunk(audio_data)
            
            if response_audio:
                # Send the audio response in chunks
                chunk_size = 4096
                for i in range(0, len(response_audio), chunk_size):
                    chunk = response_audio[i:i + chunk_size]
                    yield json.dumps({
                        "event": "media",
                        "data": chunk
                    })
                
                # Signal end of response
                yield json.dumps({"event": "stop"})
                
        except Exception as e:
            logger.error(f"WebSocket audio handler error: {e}")
            yield json.dumps({
                "event": "error",
                "message": "The cosmic energies are fluctuating. Please try again."
            })
    
    async def handle_text_message(self, message: str) -> str:
        """Handle text messages for testing."""
        try:
            response_text = await self.astrologer._generate_claude_response(message)
            return json.dumps({
                "event": "text_response",
                "data": response_text
            })
        except Exception as e:
            logger.error(f"Text handler error: {e}")
            return json.dumps({
                "event": "error",
                "message": "I couldn't process your message through the cosmic channels."
            })
