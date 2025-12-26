"""
News Module
News aggregation and sentiment analysis
"""

from .news_aggregator import (
    NewsAggregator,
    NewsItem,
    NewsSentiment,
    NewsSource
)

__all__ = [
    'NewsAggregator',
    'NewsItem',
    'NewsSentiment',
    'NewsSource'
]
