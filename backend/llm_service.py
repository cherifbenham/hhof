"""
LLM Service - Modular service for LLM operations
File: llm_service.py

Supports multiple LLM providers with a unified interface, including Azure OpenAI.
"""

import os
import logging
from typing import Optional, Dict, List, Literal
from enum import Enum
from dotenv import load_dotenv
import json
from openai import OpenAI, AzureOpenAI 

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class LLMProvider(Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai" # Standard OpenAI
    AZURE_OPENAI = "azure_openai" # Azure-hosted OpenAI
    MISTRAL = "mistral"


class LLMService:
    """Unified LLM service supporting multiple providers"""
    
    def __init__(
        self, 
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        # Azure-specific parameters
        azure_endpoint: Optional[str] = None,
        api_version: Optional[str] = None
    ):
        # Load from environment if not provided
        if provider is None:
            provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
            self.provider = LLMProvider(provider_str)
        else:
            self.provider = provider
        
        self.temperature = temperature or float(os.getenv("LLM_TEMPERATURE", "0.0"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "4096"))
        
        # Azure-specific attributes
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version or os.getenv("AZURE_API_VERSION", "2024-02-15") 
        
        # Set model from environment or use defaults
        if model is None:
            model = self._get_model_from_env()
        self.model = model
        
        # Initialize client based on provider
        self.client = self._initialize_client(api_key)
        logger.info(f"LLM Service initialized: {self.provider.value} / {self.model}")
    
    def _get_model_from_env(self) -> str:
        """Get model or deployment name from environment variables based on provider"""
        if self.provider == LLMProvider.ANTHROPIC:
            return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        elif self.provider == LLMProvider.OPENAI:
            return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif self.provider == LLMProvider.AZURE_OPENAI:
            # Azure uses DEPLOYMENT_NAME (which is passed as 'model' in the client call)
            return os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o") 
        elif self.provider == LLMProvider.MISTRAL:
            return os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        return "gpt-4o-mini"  # fallback
    
    def _initialize_client(self, api_key: Optional[str]):
        """Initialize the appropriate LLM client"""
        try:
            if self.provider == LLMProvider.ANTHROPIC:
                from anthropic import Anthropic
                api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not found in environment")
                return Anthropic(api_key=api_key)
            
            elif self.provider == LLMProvider.OPENAI:
                api_key = api_key or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment")
                return OpenAI(api_key=api_key)
            
            elif self.provider == LLMProvider.AZURE_OPENAI:
                api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("AZURE_OPENAI_API_KEY not found in environment")
                if not self.azure_endpoint:
                    raise ValueError("AZURE_OPENAI_ENDPOINT not found in environment")
                
                # Check for necessary Azure libraries
                try:
                    from openai import AzureOpenAI 
                except ImportError:
                    raise ImportError("openai package not installed. Run: pip install openai")
                
                return AzureOpenAI(
                    azure_endpoint=self.azure_endpoint,
                    api_key=api_key,
                    api_version=self.api_version
                )
            
            elif self.provider == LLMProvider.MISTRAL:
                from mistralai.client import MistralClient
                api_key = api_key or os.getenv("MISTRAL_API_KEY")
                if not api_key:
                    raise ValueError("MISTRAL_API_KEY not found in environment")
                return MistralClient(api_key=api_key)
            
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except ImportError as e:
            if 'anthropic' in str(e):
                 raise ImportError("anthropic package not installed. Run: pip install anthropic")
            elif 'openai' in str(e):
                 # OpenAI package is used for both OpenAI and AzureOpenAI
                 raise ImportError("openai package not installed. Run: pip install openai")
            elif 'mistralai' in str(e):
                 raise ImportError("mistralai package not installed. Run: pip install mistralai")
            raise
    
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        response_format: Literal["text", "json"] = "text"
    ) -> str:
        """
        Generate completion from LLM
        """
        try:
            if self.provider in (LLMProvider.OPENAI, LLMProvider.AZURE_OPENAI):
                return self._generate_openai_compatible(prompt, system_prompt, response_format)
            elif self.provider == LLMProvider.ANTHROPIC:
                return self._generate_anthropic(prompt, system_prompt)
            elif self.provider == LLMProvider.MISTRAL:
                return self._generate_mistral(prompt, system_prompt, response_format)
        except Exception as e:
            logger.error(f"Error generating completion with {self.provider.value}: {e}")
            raise

    # Combined function for standard OpenAI and AzureOpenAI 
    def _generate_openai_compatible(self, prompt: str, system_prompt: Optional[str], response_format: str) -> str:
        """Generate using OpenAI-compatible clients (OpenAI or AzureOpenAI)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": self.model, 
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"} 
        
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _generate_anthropic(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Generate using Anthropic Claude"""
        messages = [{"role": "user", "content": prompt}]
        
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = self.client.messages.create(**kwargs)
        return response.content[0].text
    
    def _generate_mistral(self, prompt: str, system_prompt: Optional[str], response_format: str) -> str:
        """Generate using Mistral"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"} 
        
        response = self.client.chat(messages=messages, **kwargs)
        return response.choices[0].message.content
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count (approximate: 1 token ≈ 4 characters)
        """
        return len(text) // 4
    
    # La méthode chunk_text est conservée mais n'est plus utilisée dans LLMProcessor
    def chunk_text(self, text: str, max_chunk_tokens: int = 3000) -> List[str]:
        """
        Split text into chunks that fit within token limits
        """
        # Simple paragraph-based chunking
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self.count_tokens(para)
            
            if current_tokens + para_tokens > max_chunk_tokens:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks


def create_llm_service_from_env() -> LLMService:
    """
    Factory function to create LLM service from environment variables
    """
    return LLMService()