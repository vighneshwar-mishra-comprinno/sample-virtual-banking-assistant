"""
Astrology Analysis Module using Claude 3 Sonnet with Enhanced Knowledge Base

This module provides astrological analysis functionality using Claude 3 Sonnet
integrated with specialized knowledge base for money and health guidance based on birth chart information.
"""

import boto3
import json
from datetime import datetime
from typing import Dict, Any, Optional

class AstrologyAnalyzer:
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.bedrock_agent_client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Claude 3 Sonnet
        self.knowledge_base_id = "JR8OOG1HR5"  # Internal knowledge base ID
        
    def retrieve_specialized_knowledge(self, query: str, question_type: str) -> str:
        """
        Retrieve relevant specialized astrological knowledge from internal knowledge base
        
        Args:
            query: Query to search in the knowledge base
            question_type: Type of question (money/health)
            
        Returns:
            Retrieved specialized astrological knowledge
        """
        try:
            # Create a focused query for specialized knowledge
            search_query = f"astrology {question_type} {query} calculations remedies predictions planetary positions"
            
            response = self.bedrock_agent_client.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={
                    'text': search_query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': 5,  # Get top 5 relevant results
                        'overrideSearchType': 'HYBRID'  # Use both semantic and keyword search
                    }
                }
            )
            
            # Extract and combine relevant knowledge
            knowledge_chunks = []
            for result in response.get('retrievalResults', []):
                content = result.get('content', {}).get('text', '')
                if content:
                    knowledge_chunks.append(content)
            
            # Combine the knowledge chunks
            combined_knowledge = "\n\n".join(knowledge_chunks[:3])  # Use top 3 results
            
            return combined_knowledge if combined_knowledge else "No specific specialized knowledge found for this query."
            
        except Exception as e:
            print(f"Error retrieving specialized knowledge: {str(e)}", flush=True)
            return "Unable to access specialized knowledge base at this time."

    def analyze_birth_chart(self, birth_date: str, birth_time: str, birth_place: str, 
                           question_type: str, specific_question: str = "") -> str:
        """
        Analyze birth chart information using Claude 3 Sonnet with specialized knowledge
        
        Args:
            birth_date: Date of birth in DD/MM/YYYY format
            birth_time: Time of birth in HH:MM AM/PM format
            birth_place: Place of birth (City, Country)
            question_type: Type of question (money/health)
            specific_question: Specific question from user
            
        Returns:
            Astrological analysis response based on specialized principles
        """
        
        # First, retrieve relevant specialized knowledge
        birth_info_query = f"birth date {birth_date} time {birth_time} place {birth_place}"
        specialized_knowledge = self.retrieve_specialized_knowledge(birth_info_query, question_type)
        
        # Create the enhanced prompt for Claude 3 Sonnet with specialized knowledge
        system_prompt = """You are a professional astrologer specializing in financial and health astrology. 
        You provide insightful, practical guidance based on traditional astrological principles while maintaining a warm, 
        mystical but grounded approach. Keep responses concise and actionable for voice interaction.
        
        Specialization:
        - Use traditional astrological calculations and house systems
        - Apply authentic remedies and predictions methodology
        - Focus on practical remedies and timing guidance
        - Consider planetary positions and their traditional effects
        
        Focus areas:
        - Financial astrology: Career, income, investments, business timing
        - Health astrology: Wellness tendencies, preventive guidance, energy patterns
        
        Always provide:
        1. Brief astrological insight based on traditional principles
        2. Practical remedies or timing suggestions
        3. Encouraging but realistic perspective based on authentic astrological knowledge
        
        Keep responses to 2-3 sentences maximum for voice interaction."""
        
        user_prompt = f"""Please provide astrological guidance for:

Birth Information:
- Date: {birth_date}
- Time: {birth_time}  
- Place: {birth_place}

Question Type: {question_type}
{f"Specific Question: {specific_question}" if specific_question else ""}

Relevant Astrological Knowledge:
{specialized_knowledge}

Based on the above traditional astrological knowledge and principles, please provide a brief astrological analysis focusing on {question_type} matters. 
Use authentic astrological calculations and methodology to provide accurate predictions and practical remedies.
Consider the specific traditional principles mentioned in the knowledge for this birth chart analysis."""

        try:
            # Prepare the request for Claude 3 Sonnet
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,  # Increased for detailed analysis
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "temperature": 0.7,
                "top_p": 0.9
            }
            
            # Call Claude 3 Sonnet via Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            analysis = response_body['content'][0]['text']
            
            return analysis.strip()
            
        except Exception as e:
            print(f"Error in astrological analysis: {str(e)}", flush=True)
            return "I'm having trouble accessing the cosmic insights right now. Please try again in a moment."
    
    def validate_birth_info(self, birth_date: str, birth_time: str, birth_place: str) -> tuple[bool, str]:
        """
        Validate birth information format
        
        Returns:
            (is_valid, error_message)
        """
        # Validate date format (DD/MM/YYYY)
        try:
            datetime.strptime(birth_date, "%d/%m/%Y")
        except ValueError:
            return False, "Please provide birth date in DD/MM/YYYY format"
        
        # Validate time format (basic check)
        if not birth_time or len(birth_time.strip()) < 4:
            return False, "Please provide birth time in HH:MM AM/PM format"
        
        # Validate place (basic check)
        if not birth_place or len(birth_place.strip()) < 3:
            return False, "Please provide birth place as City, Country"
        
        return True, ""

# Global instance
astrology_analyzer = AstrologyAnalyzer()
