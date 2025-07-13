#!/usr/bin/env python3
"""
AI Provider Abstraction

This module provides a unified interface for different AI providers (OpenAI and Claude)
to generate release note summaries.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    def generate_summary(self, system_prompt: str, user_prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> str:
        """
        Generate a summary using the AI provider.
        
        Args:
            system_prompt: The system prompt defining the AI's role
            user_prompt: The user prompt with the actual content to analyze
            max_tokens: Maximum tokens for the response
            temperature: Temperature for response generation
            
        Returns:
            Generated summary text
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the AI provider.
        
        Returns:
            True if connection is successful
        """
        pass

class OpenAIProvider(AIProvider):
    """OpenAI API provider implementation."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model to use for generation
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
            logger.info(f"Initialized OpenAI provider with model: {model}")
        except ImportError:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
    
    def generate_summary(self, system_prompt: str, user_prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> str:
        """Generate summary using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            summary = response.choices[0].message.content
            if summary:
                summary = summary.strip()
                logger.info("Generated summary using OpenAI")
                return summary
            else:
                logger.warning("Empty response from OpenAI")
                return "Unable to generate summary."
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test OpenAI connection."""
        try:
            self.client.models.list()
            logger.info("OpenAI connection successful")
            return True
        except Exception as e:
            logger.error(f"OpenAI connection failed: {e}")
            return False

class ClaudeProvider(AIProvider):
    """Claude API provider implementation."""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        Initialize Claude provider.
        
        Args:
            api_key: Anthropic API key
            model: Model to use for generation
        """
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
            self.model = model
            logger.info(f"Initialized Claude provider with model: {model}")
        except ImportError:
            raise ImportError("Anthropic library not installed. Run: pip install anthropic")
    
    def generate_summary(self, system_prompt: str, user_prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> str:
        """Generate summary using Claude."""
        try:
            # Claude doesn't support system messages, so combine them
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": combined_prompt}
                ]
            )
            
            # Extract text from response content
            summary = ""
            for block in response.content:
                try:
                    if hasattr(block, 'text'):
                        summary += str(getattr(block, 'text', ''))
                except AttributeError:
                    continue
                
            if summary:
                summary = summary.strip()
                logger.info("Generated summary using Claude")
                return summary
            else:
                logger.warning("Empty response from Claude")
                return "Unable to generate summary."
                
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test Claude connection."""
        try:
            # Test by listing models
            self.client.models.list()
            logger.info("Claude connection successful")
            return True
        except Exception as e:
            logger.error(f"Claude connection failed: {e}")
            return False

def create_ai_provider(provider: str, api_key: str, model: Optional[str] = None) -> AIProvider:
    """
    Factory function to create an AI provider.
    
    Args:
        provider: Provider name ('openai' or 'claude')
        api_key: API key for the provider
        model: Optional model name to override default
        
    Returns:
        AIProvider instance
    """
    if provider.lower() == 'openai':
        model = model or "gpt-4o-mini"
        return OpenAIProvider(api_key, model)
    elif provider.lower() == 'claude':
        model = model or "claude-3-haiku-20240307"
        return ClaudeProvider(api_key, model)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}. Supported providers: openai, claude") 