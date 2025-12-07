"""
Binance API Client - базовый HTTP клиент для публичных эндпоинтов Binance

Особенности:
- Rate limiting (автоматические паузы)
- Retry логика с exponential backoff
- Валидация символов криптовалют
- Не требует API ключа (только публичные данные)
"""

import requests
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OHLCV:
    """Структура свечи (candlestick)"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades_count: int
    taker_buy_base: float
    taker_buy_quote: float
    
    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "datetime": self.datetime.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "trades_count": self.trades_count,
        }


@dataclass
class Trade:
    """Структура сделки"""
    id: int
    price: float
    qty: float
    quote_qty: float
    time: int
    is_buyer_maker: bool
    
    @property
    def is_buy(self) -> bool:
        return not self.is_buyer_maker
    
    @property
    def side(self) -> str:
        return "buy" if self.is_buy else "sell"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "price": self.price,
            "qty": self.qty,
            "quote_qty": self.quote_qty,
            "time": self.time,
            "side": self.side,
        }


@dataclass
class OrderBook:
    """Структура стакана"""
    last_update_id: int
    bids: List[List[float]]
    asks: List[List[float]]
    
    @property
    def best_bid(self) -> float:
        return float(self.bids[0][0]) if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return float(self.asks[0][0]) if self.asks else 0.0
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid
    
    @property
    def spread_percent(self) -> float:
        if self.mid_price == 0:
            return 0.0
        return (self.spread / self.mid_price) * 100


@dataclass
class Ticker24h:
    """24-часовая статистика"""
    symbol: str
    price_change: float
    price_change_percent: float
    last_price: float
    high_price: float
    low_price: float
    volume: float
    quote_volume: float
    open_time: int
    close_time: int
    trades_count: int


class BinanceClient:
    """HTTP клиент для Binance API (публичные эндпоинты)"""
    
    BASE_URL = "https://api.binance.com"
    MAX_REQUESTS_PER_MINUTE = 1200
    MIN_REQUEST_INTERVAL = 0.05
    
    VALID_INTERVALS = [
        "1s", "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M"
    ]
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "CryptoAnalystBot/1.0"
        })
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = time.time()
    
    def _rate_limit(self):
        current_time = time.time()
        if current_time - self._minute_start > 60:
            self._request_count = 0
            self._minute_start = current_time
        
        if self._request_count >= self.MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (current_time - self._minute_start)
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self._request_count = 0
                self._minute_start = time.time()
        
        elapsed = current_time - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        
        self._last_request_time = time.time()
        self._request_count += 1
    
    def _request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Binance rate limit, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                if response.status_code >= 500:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"Server error {response.status_code}, retry in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
        
        raise Exception(f"Failed after {max_retries} attempts: {endpoint}")
    
    def normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.upper().strip()
        symbol = symbol.replace("/", "").replace("-", "").replace("_", "")
        if symbol.endswith("USDT") or symbol.endswith("BUSD") or symbol.endswith("BTC"):
            return symbol
        return f"{symbol}USDT"
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100,
                   start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[OHLCV]:
        symbol = self.normalize_symbol(symbol)
        if interval not in self.VALID_INTERVALS:
            raise ValueError(f"Invalid interval: {interval}")
        
        params = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        data = self._request("/api/v3/klines", params)
        
        return [OHLCV(
            timestamp=int(k[0]), open=float(k[1]), high=float(k[2]), low=float(k[3]),
            close=float(k[4]), volume=float(k[5]), close_time=int(k[6]),
            quote_volume=float(k[7]), trades_count=int(k[8]),
            taker_buy_base=float(k[9]), taker_buy_quote=float(k[10]),
        ) for k in data]
    
    def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Trade]:
        symbol = self.normalize_symbol(symbol)
        params = {"symbol": symbol, "limit": min(limit, 1000)}
        data = self._request("/api/v3/trades", params)
        
        return [Trade(
            id=t["id"], price=float(t["price"]), qty=float(t["qty"]),
            quote_qty=float(t["quoteQty"]), time=t["time"], is_buyer_maker=t["isBuyerMaker"],
        ) for t in data]
    
    def get_order_book(self, symbol: str, limit: int = 1000) -> OrderBook:
        symbol = self.normalize_symbol(symbol)
        valid_limits = [5, 10, 20, 50, 100, 500, 1000, 5000]
        limit = min([l for l in valid_limits if l >= limit], default=1000)
        
        params = {"symbol": symbol, "limit": limit}
        data = self._request("/api/v3/depth", params)
        
        return OrderBook(
            last_update_id=data["lastUpdateId"],
            bids=[[float(b[0]), float(b[1])] for b in data["bids"]],
            asks=[[float(a[0]), float(a[1])] for a in data["asks"]],
        )
    
    def get_ticker_24h(self, symbol: str) -> Ticker24h:
        symbol = self.normalize_symbol(symbol)
        data = self._request("/api/v3/ticker/24hr", {"symbol": symbol})
        
        return Ticker24h(
            symbol=data["symbol"],
            price_change=float(data["priceChange"]),
            price_change_percent=float(data["priceChangePercent"]),
            last_price=float(data["lastPrice"]),
            high_price=float(data["highPrice"]),
            low_price=float(data["lowPrice"]),
            volume=float(data["volume"]),
            quote_volume=float(data["quoteVolume"]),
            open_time=data["openTime"],
            close_time=data["closeTime"],
            trades_count=data["count"],
        )
    
    def get_current_price(self, symbol: str) -> float:
        symbol = self.normalize_symbol(symbol)
        data = self._request("/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])


_client: Optional[BinanceClient] = None

def get_binance_client() -> BinanceClient:
    global _client
    if _client is None:
        _client = BinanceClient()
    return _client
