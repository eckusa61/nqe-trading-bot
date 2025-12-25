"""
LLM Client - Unified interface for OpenAI and Claude
"""
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    OPENAI = "openai"
    CLAUDE = "claude"


@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None


class LLMClient:
    """
    Unified LLM client supporting OpenAI and Claude
    Automatically falls back between providers
    """
    
    def __init__(self, primary_provider: LLMProvider = LLMProvider.OPENAI):
        self.primary_provider = primary_provider
        self._openai_client = None
        self._claude_client = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize LLM clients"""
        # OpenAI
        openai_key = os.environ.get('OPENAI_API_KEY')
        if openai_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")
        
        # Claude
        claude_key = os.environ.get('CLAUDE_API_KEY')
        if claude_key:
            try:
                from anthropic import Anthropic
                self._claude_client = Anthropic(api_key=claude_key)
                logger.info("Claude client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude: {e}")
    
    async def ask(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: Optional[LLMProvider] = None
    ) -> LLMResponse:
        """
        Ask LLM a question
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Creativity (0-1)
            max_tokens: Max response length
            provider: Force specific provider, or use primary
        """
        target_provider = provider or self.primary_provider
        
        # Try primary provider first
        if target_provider == LLMProvider.OPENAI:
            response = await self._ask_openai(prompt, system_prompt, temperature, max_tokens)
            if response.success:
                return response
            # Fallback to Claude
            logger.warning("OpenAI failed, falling back to Claude")
            return await self._ask_claude(prompt, system_prompt, temperature, max_tokens)
        else:
            response = await self._ask_claude(prompt, system_prompt, temperature, max_tokens)
            if response.success:
                return response
            # Fallback to OpenAI
            logger.warning("Claude failed, falling back to OpenAI")
            return await self._ask_openai(prompt, system_prompt, temperature, max_tokens)
    
    async def _ask_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Query OpenAI"""
        if not self._openai_client:
            return LLMResponse(
                content="",
                provider=LLMProvider.OPENAI,
                model="",
                success=False,
                error="OpenAI client not initialized"
            )
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self._openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                provider=LLMProvider.OPENAI,
                model="gpt-4o",
                tokens_used=response.usage.total_tokens if response.usage else 0,
                success=True
            )
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return LLMResponse(
                content="",
                provider=LLMProvider.OPENAI,
                model="gpt-4o",
                success=False,
                error=str(e)
            )
    
    async def _ask_claude(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Query Claude"""
        if not self._claude_client:
            return LLMResponse(
                content="",
                provider=LLMProvider.CLAUDE,
                model="",
                success=False,
                error="Claude client not initialized"
            )
        
        try:
            response = self._claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system_prompt or "You are a helpful trading assistant.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            return LLMResponse(
                content=response.content[0].text,
                provider=LLMProvider.CLAUDE,
                model="claude-sonnet-4-20250514",
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
                success=True
            )
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return LLMResponse(
                content="",
                provider=LLMProvider.CLAUDE,
                model="claude-sonnet-4-20250514",
                success=False,
                error=str(e)
            )
    
    async def analyze_market(
        self,
        market_data: Dict[str, Any],
        regime: str,
        positions: List[Dict],
        performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze market conditions and provide recommendations
        """
        system_prompt = """You are an expert quantitative trading analyst. Analyze the provided market data and give actionable recommendations.
        
Respond in JSON format with these fields:
- action: "hold", "increase_exposure", "reduce_exposure", "close_all"
- confidence: 0.0 to 1.0
- reasoning: brief explanation
- strategy_adjustment: any recommended strategy changes
- risk_level: "low", "medium", "high", "critical"
"""
        
        prompt = f"""
Current Market Analysis Request:

Market Regime: {regime}

Market Data:
{json.dumps(market_data, indent=2)}

Current Positions:
{json.dumps(positions, indent=2)}

Recent Performance:
{json.dumps(performance, indent=2)}

Provide your analysis and recommendations.
"""
        
        response = await self.ask(prompt, system_prompt, temperature=0.3, max_tokens=1500)
        
        if response.success:
            try:
                # Try to parse JSON response
                content = response.content
                # Extract JSON if wrapped in markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                return json.loads(content)
            except:
                return {
                    "action": "hold",
                    "confidence": 0.5,
                    "reasoning": response.content,
                    "strategy_adjustment": None,
                    "risk_level": "medium"
                }
        else:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reasoning": f"LLM Error: {response.error}",
                "strategy_adjustment": None,
                "risk_level": "high"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get LLM client status"""
        return {
            "primary_provider": self.primary_provider.value,
            "openai_available": self._openai_client is not None,
            "claude_available": self._claude_client is not None
        }
