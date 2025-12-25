"""
Data Manager Module
SQLite-based time-series data storage with quality checks
"""
import asyncio
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import statistics
import os

from trading_bot.config import CONFIG, DataConfig
from trading_bot.data.ibkr_connector import HistoricalBar, BaseIBKRConnector

logger = logging.getLogger(__name__)


class DataManager:
    """
    Manages historical and real-time data storage in SQLite
    Optimized for time-series queries
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize DataManager with SQLite database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or os.path.join(
            Path(__file__).parent.parent.parent,
            CONFIG.data.db_path
        )
        self._conn: Optional[sqlite3.Connection] = None
        self._setup_database()
        
    def _setup_database(self) -> None:
        """Create database tables if they don't exist"""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrent access
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        
        # Create tables
        self._conn.executescript("""
            -- Historical OHLCV bars
            CREATE TABLE IF NOT EXISTS historical_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                bar_count INTEGER DEFAULT 1,
                wap REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp)
            );
            
            -- Index for fast time-series queries
            CREATE INDEX IF NOT EXISTS idx_bars_symbol_time 
            ON historical_bars(symbol, timestamp DESC);
            
            -- Real-time ticks (for high-frequency data)
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                bid REAL,
                ask REAL,
                last REAL,
                volume INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time 
            ON ticks(symbol, timestamp DESC);
            
            -- Corporate actions (splits, dividends)
            CREATE TABLE IF NOT EXISTS corporate_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action_type TEXT NOT NULL,
                ex_date TEXT NOT NULL,
                factor REAL,
                amount REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Data quality log
            CREATE TABLE IF NOT EXISTS data_quality_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Trades history
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                filled_qty INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                commission REAL NOT NULL,
                strategy TEXT,
                signal_strength REAL,
                regime TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Portfolio snapshots for tracking
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cash REAL NOT NULL,
                portfolio_value REAL NOT NULL,
                daily_pnl REAL,
                total_pnl REAL,
                positions_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Strategy signals history
            CREATE TABLE IF NOT EXISTS strategy_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                signal REAL NOT NULL,
                confidence REAL,
                features_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")
    
    def close(self) -> None:
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    # ===== Historical Data Methods =====
    
    async def store_historical_bars(self, bars: List[HistoricalBar]) -> int:
        """
        Store historical bars in database
        Uses INSERT OR REPLACE for upsert behavior
        
        Returns: Number of bars stored
        """
        if not bars:
            return 0
        
        cursor = self._conn.cursor()
        
        for bar in bars:
            cursor.execute("""
                INSERT OR REPLACE INTO historical_bars 
                (symbol, timestamp, open, high, low, close, volume, bar_count, wap)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bar.symbol,
                bar.timestamp.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.bar_count,
                bar.wap
            ))
        
        self._conn.commit()
        logger.info(f"Stored {len(bars)} bars for {bars[0].symbol}")
        return len(bars)
    
    def get_historical_bars(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[HistoricalBar]:
        """
        Retrieve historical bars from database
        
        Args:
            symbol: Stock symbol
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            limit: Maximum number of bars to return
        
        Returns: List of HistoricalBar objects, sorted by timestamp ascending
        """
        query = "SELECT * FROM historical_bars WHERE symbol = ?"
        params = [symbol]
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY timestamp ASC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            HistoricalBar(
                symbol=row["symbol"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                bar_count=row["bar_count"],
                wap=row["wap"]
            )
            for row in rows
        ]
    
    def get_latest_bar(self, symbol: str) -> Optional[HistoricalBar]:
        """Get the most recent bar for a symbol"""
        cursor = self._conn.execute("""
            SELECT * FROM historical_bars 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (symbol,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return HistoricalBar(
            symbol=row["symbol"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            bar_count=row["bar_count"],
            wap=row["wap"]
        )
    
    def get_bar_count(self, symbol: str) -> int:
        """Get total number of bars for a symbol"""
        cursor = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM historical_bars WHERE symbol = ?",
            (symbol,)
        )
        return cursor.fetchone()["cnt"]
    
    # ===== Data Quality Methods =====
    
    def check_data_quality(self, symbol: str) -> Dict:
        """
        Perform data quality checks on stored data
        
        Returns: Dictionary with quality metrics
        """
        bars = self.get_historical_bars(symbol)
        
        if not bars:
            return {"status": "no_data", "symbol": symbol}
        
        issues = []
        
        # Check for missing dates (gaps > 4 days = business week)
        for i in range(1, len(bars)):
            gap = (bars[i].timestamp - bars[i-1].timestamp).days
            if gap > 4:  # Allow for weekends + 1 holiday
                issues.append(f"Gap of {gap} days at {bars[i-1].timestamp.date()}")
        
        # Check for outliers
        closes = [b.close for b in bars]
        returns = [(closes[i] - closes[i-1]) / closes[i-1] 
                   for i in range(1, len(closes))]
        
        if returns:
            mean_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 0
            
            outliers = []
            for i, ret in enumerate(returns):
                if abs(ret - mean_ret) > CONFIG.data.outlier_std_threshold * std_ret:
                    outliers.append({
                        "date": bars[i+1].timestamp.date().isoformat(),
                        "return": f"{ret*100:.2f}%"
                    })
            
            if outliers:
                issues.append(f"{len(outliers)} potential outliers detected")
        
        # Check for zero/negative prices
        bad_prices = [b for b in bars if b.close <= 0 or b.open <= 0]
        if bad_prices:
            issues.append(f"{len(bad_prices)} bars with invalid prices")
        
        # Check for OHLC consistency
        inconsistent = [b for b in bars if b.high < b.low or 
                       b.high < max(b.open, b.close) or
                       b.low > min(b.open, b.close)]
        if inconsistent:
            issues.append(f"{len(inconsistent)} bars with OHLC inconsistency")
        
        quality_result = {
            "symbol": symbol,
            "status": "pass" if not issues else "issues",
            "total_bars": len(bars),
            "date_range": f"{bars[0].timestamp.date()} to {bars[-1].timestamp.date()}",
            "issues": issues
        }
        
        # Log quality check
        self._conn.execute("""
            INSERT INTO data_quality_log (symbol, check_type, status, details)
            VALUES (?, ?, ?, ?)
        """, (
            symbol,
            "full_check",
            quality_result["status"],
            str(issues)
        ))
        self._conn.commit()
        
        return quality_result
    
    # ===== Trade Recording =====
    
    def record_trade(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        filled_qty: int,
        avg_price: float,
        commission: float,
        strategy: Optional[str] = None,
        signal_strength: Optional[float] = None,
        regime: Optional[str] = None
    ) -> None:
        """Record a trade execution"""
        self._conn.execute("""
            INSERT INTO trades 
            (order_id, symbol, side, quantity, filled_qty, avg_price, 
             commission, strategy, signal_strength, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, symbol, side, quantity, filled_qty, avg_price,
            commission, strategy, signal_strength, regime
        ))
        self._conn.commit()
    
    def get_trades(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get recent trades"""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        query += f" ORDER BY timestamp DESC LIMIT {limit}"
        
        cursor = self._conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # ===== Portfolio Snapshots =====
    
    def save_portfolio_snapshot(
        self,
        cash: float,
        portfolio_value: float,
        daily_pnl: float,
        total_pnl: float,
        positions: Dict[str, int]
    ) -> None:
        """Save a portfolio snapshot"""
        import json
        
        self._conn.execute("""
            INSERT INTO portfolio_snapshots 
            (timestamp, cash, portfolio_value, daily_pnl, total_pnl, positions_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            cash,
            portfolio_value,
            daily_pnl,
            total_pnl,
            json.dumps(positions)
        ))
        self._conn.commit()
    
    def get_portfolio_history(self, days: int = 30) -> List[Dict]:
        """Get portfolio value history"""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        
        cursor = self._conn.execute("""
            SELECT * FROM portfolio_snapshots 
            WHERE timestamp >= ? 
            ORDER BY timestamp ASC
        """, (start.isoformat(),))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ===== Strategy Signals =====
    
    def save_signal(
        self,
        symbol: str,
        strategy: str,
        signal: float,
        confidence: Optional[float] = None,
        features: Optional[Dict] = None
    ) -> None:
        """Save a strategy signal"""
        import json
        
        self._conn.execute("""
            INSERT INTO strategy_signals 
            (timestamp, symbol, strategy, signal, confidence, features_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            symbol,
            strategy,
            signal,
            confidence,
            json.dumps(features) if features else None
        ))
        self._conn.commit()
    
    def get_recent_signals(self, limit: int = 50) -> List[Dict]:
        """Get recent strategy signals"""
        cursor = self._conn.execute("""
            SELECT * FROM strategy_signals 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ===== Data Loading from IBKR =====
    
    async def load_historical_data(
        self,
        connector: BaseIBKRConnector,
        symbols: List[str],
        duration: str = "5 Y"
    ) -> Dict[str, int]:
        """
        Load historical data from IBKR for multiple symbols
        
        Returns: Dictionary of {symbol: bars_loaded}
        """
        results = {}
        
        for symbol in symbols:
            try:
                logger.info(f"Loading historical data for {symbol}...")
                bars = await connector.get_historical_data(symbol, duration)
                
                if bars:
                    count = await self.store_historical_bars(bars)
                    results[symbol] = count
                    
                    # Run quality check
                    quality = self.check_data_quality(symbol)
                    logger.info(f"{symbol}: {count} bars, quality: {quality['status']}")
                else:
                    results[symbol] = 0
                    logger.warning(f"No data received for {symbol}")
                    
            except Exception as e:
                logger.error(f"Error loading data for {symbol}: {e}")
                results[symbol] = 0
        
        return results
    
    # ===== Statistics =====
    
    def get_data_stats(self) -> Dict:
        """Get database statistics"""
        stats = {}
        
        # Bar counts by symbol
        cursor = self._conn.execute("""
            SELECT symbol, COUNT(*) as count, 
                   MIN(timestamp) as first_date,
                   MAX(timestamp) as last_date
            FROM historical_bars
            GROUP BY symbol
        """)
        
        stats["symbols"] = {
            row["symbol"]: {
                "count": row["count"],
                "first_date": row["first_date"],
                "last_date": row["last_date"]
            }
            for row in cursor.fetchall()
        }
        
        # Total trades
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM trades")
        stats["total_trades"] = cursor.fetchone()["cnt"]
        
        # Portfolio snapshots
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM portfolio_snapshots")
        stats["total_snapshots"] = cursor.fetchone()["cnt"]
        
        return stats
