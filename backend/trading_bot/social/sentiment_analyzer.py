"""
Social Media Sentiment Analyzer

Monitors:
- Twitter for stock mentions
- Reddit (wallstreetbets, stocks, investing)
- News feeds

Provides real-time sentiment signals for trading decisions.
"""
import os
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import defaultdict
import aiohttp

from ..ai.llm_client import LLMClient, LLMProvider
from ..notifications import telegram_manager

logger = logging.getLogger(__name__)


@dataclass
class SentimentData:
    symbol: str
    source: str
    sentiment_score: float  # -1 to 1
    confidence: float
    volume: int  # Number of mentions
    content_sample: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "sentiment_score": round(self.sentiment_score, 3),
            "confidence": round(self.confidence, 3),
            "volume": self.volume,
            "content_sample": self.content_sample[:200],
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AggregateSentiment:
    symbol: str
    overall_score: float
    twitter_score: Optional[float]
    reddit_score: Optional[float]
    news_score: Optional[float]
    total_mentions: int
    signal: str  # "bullish", "bearish", "neutral"
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "overall_score": round(self.overall_score, 3),
            "twitter_score": round(self.twitter_score, 3) if self.twitter_score else None,
            "reddit_score": round(self.reddit_score, 3) if self.reddit_score else None,
            "news_score": round(self.news_score, 3) if self.news_score else None,
            "total_mentions": self.total_mentions,
            "signal": self.signal,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat()
        }


class SocialSentimentAnalyzer:
    """
    Analyzes social media sentiment for trading signals
    """
    
    # Tracked symbols
    DEFAULT_SYMBOLS = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'AMZN', 'GOOGL']
    
    def __init__(self):
        self.llm = LLMClient(primary_provider=LLMProvider.OPENAI)
        self.symbols = self.DEFAULT_SYMBOLS.copy()
        self.sentiment_cache: Dict[str, AggregateSentiment] = {}
        self.history: Dict[str, List[SentimentData]] = defaultdict(list)
        self.is_running = False
        self.update_interval = 600  # 10 minutes
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info("Social Sentiment Analyzer initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def start(self):
        """Start the sentiment monitoring loop"""
        self.is_running = True
        logger.info("Social Sentiment Analyzer started")
        
        while self.is_running:
            try:
                await self._update_all_sentiments()
            except Exception as e:
                logger.error(f"Sentiment update error: {e}")
            
            await asyncio.sleep(self.update_interval)
    
    async def stop(self):
        """Stop the analyzer"""
        self.is_running = False
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _update_all_sentiments(self):
        """Update sentiment for all tracked symbols"""
        for symbol in self.symbols:
            try:
                sentiment = await self.analyze_symbol(symbol)
                if sentiment:
                    self.sentiment_cache[symbol] = sentiment
                    
                    # Send alert for significant sentiment changes
                    if abs(sentiment.overall_score) > 0.5 and sentiment.confidence > 0.7:
                        await self._send_sentiment_alert(sentiment)
                        
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
    
    async def analyze_symbol(self, symbol: str) -> Optional[AggregateSentiment]:
        """
        Analyze sentiment for a specific symbol from all sources
        """
        # Collect sentiment from different sources
        twitter_sentiment = await self._get_twitter_sentiment(symbol)
        reddit_sentiment = await self._get_reddit_sentiment(symbol)
        news_sentiment = await self._get_news_sentiment(symbol)
        
        # Aggregate sentiments
        scores = []
        weights = []
        total_mentions = 0
        
        if twitter_sentiment:
            scores.append(twitter_sentiment.sentiment_score)
            weights.append(twitter_sentiment.confidence * 0.3)  # Twitter weight
            total_mentions += twitter_sentiment.volume
            self.history[symbol].append(twitter_sentiment)
        
        if reddit_sentiment:
            scores.append(reddit_sentiment.sentiment_score)
            weights.append(reddit_sentiment.confidence * 0.3)  # Reddit weight
            total_mentions += reddit_sentiment.volume
            self.history[symbol].append(reddit_sentiment)
        
        if news_sentiment:
            scores.append(news_sentiment.sentiment_score)
            weights.append(news_sentiment.confidence * 0.4)  # News weight (higher)
            total_mentions += news_sentiment.volume
            self.history[symbol].append(news_sentiment)
        
        if not scores:
            return None
        
        # Weighted average
        total_weight = sum(weights)
        if total_weight > 0:
            overall_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        else:
            overall_score = sum(scores) / len(scores)
        
        # Determine signal
        if overall_score > 0.3:
            signal = "bullish"
        elif overall_score < -0.3:
            signal = "bearish"
        else:
            signal = "neutral"
        
        return AggregateSentiment(
            symbol=symbol,
            overall_score=overall_score,
            twitter_score=twitter_sentiment.sentiment_score if twitter_sentiment else None,
            reddit_score=reddit_sentiment.sentiment_score if reddit_sentiment else None,
            news_score=news_sentiment.sentiment_score if news_sentiment else None,
            total_mentions=total_mentions,
            signal=signal,
            confidence=total_weight / len(scores) if scores else 0
        )
    
    async def _get_twitter_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Get Twitter sentiment (simulated for now - requires Twitter API v2)
        In production, connect to Twitter API
        """
        # For now, return simulated data
        # TODO: Implement actual Twitter API integration when keys are provided
        return SentimentData(
            symbol=symbol,
            source="twitter",
            sentiment_score=0.0,  # Neutral by default
            confidence=0.5,
            volume=0,
            content_sample="Twitter API integration pending"
        )
    
    async def _get_reddit_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Get Reddit sentiment from wallstreetbets and other finance subs
        """
        # For now, return simulated data
        # TODO: Implement actual Reddit API integration (PRAW)
        return SentimentData(
            symbol=symbol,
            source="reddit",
            sentiment_score=0.0,
            confidence=0.5,
            volume=0,
            content_sample="Reddit API integration pending"
        )
    
    async def _get_news_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Analyze news sentiment using LLM
        """
        try:
            # Use LLM to analyze current market news for the symbol
            prompt = f"""
Analyze the current market sentiment for {symbol} stock.

Consider:
- Recent price movements
- Sector performance
- General market conditions
- Any known recent news

Respond with a JSON object:
{{
    "sentiment_score": <float -1 to 1, where -1 is very bearish, 1 is very bullish>,
    "confidence": <float 0 to 1>,
    "reasoning": "<brief explanation>"
}}
"""
            
            response = await self.llm.ask(
                prompt,
                system_prompt="You are a market sentiment analyst. Respond only with valid JSON.",
                temperature=0.3,
                max_tokens=200
            )
            
            if response.success:
                import json
                try:
                    content = response.content
                    if "```" in content:
                        content = content.split("```")[1].replace("json", "").strip()
                    data = json.loads(content)
                    
                    return SentimentData(
                        symbol=symbol,
                        source="news_ai",
                        sentiment_score=float(data.get('sentiment_score', 0)),
                        confidence=float(data.get('confidence', 0.5)),
                        volume=1,
                        content_sample=data.get('reasoning', '')[:200]
                    )
                except:
                    pass
        except Exception as e:
            logger.error(f"News sentiment error for {symbol}: {e}")
        
        return None
    
    async def _send_sentiment_alert(self, sentiment: AggregateSentiment):
        """Send sentiment alert to Telegram"""
        await telegram_manager.send_news(
            title=f"{sentiment.symbol} Sentiment Alert",
            source="Social Analysis",
            summary=f"Overall sentiment: {sentiment.signal.upper()} ({sentiment.overall_score:+.2f})\n"
                   f"Mentions: {sentiment.total_mentions}\n"
                   f"Confidence: {sentiment.confidence*100:.0f}%",
            sentiment=sentiment.signal
        )
    
    def get_sentiment(self, symbol: str) -> Optional[AggregateSentiment]:
        """Get cached sentiment for a symbol"""
        return self.sentiment_cache.get(symbol)
    
    def get_all_sentiments(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached sentiments"""
        return {
            symbol: sentiment.to_dict()
            for symbol, sentiment in self.sentiment_cache.items()
        }
    
    def get_sentiment_signal(self, symbol: str) -> Dict[str, Any]:
        """
        Get sentiment-based trading signal
        """
        sentiment = self.sentiment_cache.get(symbol)
        
        if not sentiment:
            return {
                "symbol": symbol,
                "signal": "neutral",
                "strength": 0,
                "confidence": 0,
                "reason": "No sentiment data available"
            }
        
        # Convert sentiment to trading signal
        if sentiment.signal == "bullish" and sentiment.confidence > 0.6:
            signal = "BUY"
            strength = min(sentiment.overall_score, 1.0)
        elif sentiment.signal == "bearish" and sentiment.confidence > 0.6:
            signal = "SELL"
            strength = min(abs(sentiment.overall_score), 1.0)
        else:
            signal = "HOLD"
            strength = 0
        
        return {
            "symbol": symbol,
            "signal": signal,
            "strength": strength,
            "confidence": sentiment.confidence,
            "sentiment_score": sentiment.overall_score,
            "mentions": sentiment.total_mentions,
            "reason": f"Sentiment: {sentiment.signal} ({sentiment.overall_score:+.2f})"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get analyzer status"""
        return {
            "is_running": self.is_running,
            "tracked_symbols": self.symbols,
            "cached_sentiments": len(self.sentiment_cache),
            "update_interval_seconds": self.update_interval,
            "llm_status": self.llm.get_status()
        }


# Singleton instance
social_analyzer = SocialSentimentAnalyzer()
