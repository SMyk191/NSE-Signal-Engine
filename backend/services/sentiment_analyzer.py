from __future__ import annotations

"""
Sentiment Analysis Engine
Uses Anthropic Claude API for news sentiment analysis on stock symbols.
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import anthropic
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


class SentimentAnalyzer:
    """Fetches news for a stock symbol and analyzes sentiment via Claude API."""

    MODEL = "claude-sonnet-4-20250514"
    CACHE_TTL_SECONDS = 3600  # 1 hour

    def __init__(self):
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.finnhub_key = os.environ.get("FINNHUB_API_KEY", "")
        self._cache: dict[str, dict] = {}  # symbol -> {result, timestamp}

    # ------------------------------------------------------------------ #
    #  Fetch news articles via yfinance
    # ------------------------------------------------------------------ #
    def fetch_news(self, symbol: str) -> list[dict]:
        """
        Fetch recent news articles for a stock symbol using yfinance.
        Returns a list of article dicts with keys: title, publisher, link, publish_time.
        """
        try:
            ticker = yf.Ticker(symbol)
            raw_news = ticker.news or []
        except Exception as e:
            logger.error(f"Failed to fetch news for {symbol}: {e}")
            return []

        # Detect yfinance response format: v1.2.0+ nests data under "content"
        new_format = raw_news and isinstance(raw_news[0], dict) and "content" in raw_news[0]

        articles = []
        for item in raw_news:
            if new_format:
                content = item.get("content", {})
                provider = content.get("provider", {})
                canonical = content.get("canonicalUrl", {})
                clickthrough = content.get("clickThroughUrl", {})
                article = {
                    "title": content.get("title", ""),
                    "publisher": provider.get("displayName", ""),
                    "link": canonical.get("url", "") or clickthrough.get("url", ""),
                    "publish_time": content.get("pubDate", ""),
                    "type": content.get("type", ""),
                }
                if content.get("summary"):
                    article["summary"] = content["summary"]
            else:
                # Legacy flat format (yfinance < 1.2.0)
                article = {
                    "title": item.get("title", ""),
                    "publisher": item.get("publisher", ""),
                    "link": item.get("link", ""),
                    "publish_time": item.get("providerPublishTime", ""),
                    "type": item.get("type", ""),
                }
                if "summary" in item:
                    article["summary"] = item["summary"]
                if "relatedTickers" in item:
                    article["related_tickers"] = item["relatedTickers"]
            articles.append(article)

        return articles

    # ------------------------------------------------------------------ #
    #  Finnhub: Company News
    # ------------------------------------------------------------------ #
    def fetch_finnhub_news(self, symbol: str) -> List[dict]:
        """Fetch company news from Finnhub for the last 7 days."""
        if not self.finnhub_key:
            return []
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            resp = requests.get(
                f"{FINNHUB_BASE_URL}/company-news",
                params={
                    "symbol": symbol,
                    "from": week_ago,
                    "to": today,
                    "token": self.finnhub_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            articles = []
            for item in resp.json()[:20]:
                articles.append({
                    "title": item.get("headline", ""),
                    "publisher": item.get("source", ""),
                    "link": item.get("url", ""),
                    "publish_time": item.get("datetime", ""),
                    "summary": item.get("summary", ""),
                })
            return articles
        except Exception as e:
            logger.warning(f"Finnhub news fetch failed for {symbol}: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  Finnhub: Analyst Recommendations
    # ------------------------------------------------------------------ #
    def fetch_analyst_recommendations(self, symbol: str) -> Dict:
        """Fetch analyst recommendation trends from Finnhub."""
        if not self.finnhub_key:
            return {}
        try:
            resp = requests.get(
                f"{FINNHUB_BASE_URL}/stock/recommendation",
                params={"symbol": symbol, "token": self.finnhub_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return {}
            latest = data[0]  # most recent period
            return {
                "period": latest.get("period", ""),
                "strong_buy": latest.get("strongBuy", 0),
                "buy": latest.get("buy", 0),
                "hold": latest.get("hold", 0),
                "sell": latest.get("sell", 0),
                "strong_sell": latest.get("strongSell", 0),
            }
        except Exception as e:
            logger.warning(f"Finnhub recommendations failed for {symbol}: {e}")
            return {}

    # ------------------------------------------------------------------ #
    #  Finnhub: Insider Transactions
    # ------------------------------------------------------------------ #
    def fetch_insider_activity(self, symbol: str) -> List[dict]:
        """Fetch recent insider transactions from Finnhub."""
        if not self.finnhub_key:
            return []
        try:
            resp = requests.get(
                f"{FINNHUB_BASE_URL}/stock/insider-transactions",
                params={"symbol": symbol, "token": self.finnhub_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            transactions = []
            for txn in data[:10]:  # last 10 transactions
                transactions.append({
                    "name": txn.get("name", ""),
                    "share": txn.get("share", 0),
                    "change": txn.get("change", 0),
                    "transaction_type": txn.get("transactionType", ""),
                    "filing_date": txn.get("filingDate", ""),
                })
            return transactions
        except Exception as e:
            logger.warning(f"Finnhub insider activity failed for {symbol}: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  Analyze sentiment via Claude API
    # ------------------------------------------------------------------ #
    def analyze_sentiment(self, articles: list[dict], symbol: str) -> dict:
        """
        Send articles to Claude API for sentiment analysis.
        Returns a dict with:
            sentiment_score: float (-1.0 to +1.0)
            key_themes: list[str]
            price_impact: {short_term: str, medium_term: str}
            risk_factors: list[str]
            catalysts: list[str]
        """
        if not articles:
            return {
                "sentiment_score": 0.0,
                "key_themes": [],
                "price_impact": {"short_term": "neutral", "medium_term": "neutral"},
                "risk_factors": [],
                "catalysts": [],
                "article_count": 0,
                "note": "No news articles available for analysis",
            }

        # Build article summaries for the prompt
        article_texts = []
        for i, art in enumerate(articles[:20], 1):  # limit to 20 articles
            parts = [f"{i}. Title: {art.get('title', 'N/A')}"]
            if art.get("publisher"):
                parts.append(f"   Publisher: {art['publisher']}")
            if art.get("summary"):
                parts.append(f"   Summary: {art['summary']}")
            article_texts.append("\n".join(parts))

        articles_block = "\n\n".join(article_texts)

        prompt = f"""Analyze the sentiment of the following news articles about the stock symbol {symbol}.

Articles:
{articles_block}

Provide your analysis as a JSON object with exactly these fields:
{{
    "sentiment_score": <float from -1.0 (very bearish) to +1.0 (very bullish)>,
    "key_themes": [<list of 3-5 key themes from the articles>],
    "price_impact": {{
        "short_term": "<bullish/bearish/neutral with brief explanation>",
        "medium_term": "<bullish/bearish/neutral with brief explanation>"
    }},
    "risk_factors": [<list of risk factors identified>],
    "catalysts": [<list of positive catalysts identified>]
}}

Be precise with the sentiment_score. Consider the overall tone, specific positive/negative events,
market implications, and any forward-looking statements. Return ONLY the JSON object, no other text."""

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            # Parse JSON from response (handle possible markdown wrapping)
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                response_text = "\n".join(json_lines)

            result = json.loads(response_text)

            # Validate and clamp sentiment_score
            score = float(result.get("sentiment_score", 0.0))
            result["sentiment_score"] = max(-1.0, min(1.0, score))
            result["article_count"] = len(articles)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON for {symbol}: {e}")
            return {
                "sentiment_score": 0.0,
                "key_themes": [],
                "price_impact": {"short_term": "neutral", "medium_term": "neutral"},
                "risk_factors": [],
                "catalysts": [],
                "article_count": len(articles),
                "error": f"JSON parse error: {str(e)}",
            }
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error for {symbol}: {e}")
            return {
                "sentiment_score": 0.0,
                "key_themes": [],
                "price_impact": {"short_term": "neutral", "medium_term": "neutral"},
                "risk_factors": [],
                "catalysts": [],
                "article_count": len(articles),
                "error": f"API error: {str(e)}",
            }

    # ------------------------------------------------------------------ #
    #  Orchestrator with caching
    # ------------------------------------------------------------------ #
    def get_stock_sentiment(self, symbol: str, force_refresh: bool = False) -> dict:
        """
        Main entry point. Fetches news and analyzes sentiment for a symbol.
        Results are cached for CACHE_TTL_SECONDS.
        """
        symbol = symbol.upper()
        now = time.time()

        # Check cache
        if not force_refresh and symbol in self._cache:
            cached = self._cache[symbol]
            if now - cached["timestamp"] < self.CACHE_TTL_SECONDS:
                logger.info(f"Returning cached sentiment for {symbol}")
                return cached["result"]

        # Fetch from multiple sources and merge
        logger.info(f"Fetching fresh sentiment for {symbol}")
        yf_articles = self.fetch_news(symbol)
        finnhub_articles = self.fetch_finnhub_news(symbol)

        # Deduplicate by title (prefer Finnhub for richer summaries)
        seen_titles = set()
        articles = []
        for art in finnhub_articles + yf_articles:
            title_key = art.get("title", "").strip().lower()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                articles.append(art)

        result = self.analyze_sentiment(articles, symbol)
        result["symbol"] = symbol
        result["timestamp"] = now
        result["sources"] = {
            "yfinance_articles": len(yf_articles),
            "finnhub_articles": len(finnhub_articles),
            "total_unique": len(articles),
        }

        # Add Finnhub analyst recommendations & insider activity
        result["analyst_recommendations"] = self.fetch_analyst_recommendations(symbol)
        result["insider_activity"] = self.fetch_insider_activity(symbol)

        # Cache the result
        self._cache[symbol] = {"result": result, "timestamp": now}

        return result
