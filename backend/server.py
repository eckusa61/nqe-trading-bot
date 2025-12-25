"""
Trading Bot API Server
Phase 1: Foundation - IBKR Connection, Data Management, Feature Engineering
"""
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import asyncio
import json

# Add parent to path for imports
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / '.env')

# Import trading bot modules
from trading_bot.config import CONFIG, TradingMode, MarketRegime
from trading_bot.data.ibkr_connector import (
    IBKRConnector, BaseIBKRConnector, SimulatedIBKRConnector,
    MarketData, HistoricalBar, OrderStatus
)
from trading_bot.data.data_manager import DataManager
from trading_bot.data.feature_engine import FeatureEngine, FeatureSet
from trading_bot.models import (
    SystemStatus, MarketDataResponse, HistoricalBarResponse,
    PositionResponse, AccountSummary, TradeResponse, FeatureSetResponse,
    StrategySignal, PortfolioSnapshot, DataQualityReport,
    DashboardData, OrderRequest, BacktestRequest, ConfigUpdate, KillSwitchAction,
    PerformanceMetrics
)
from trading_bot.monitoring import alert_manager, Alert, AlertLevel, AlertType
from trading_bot.monitoring.models import (
    WebhookConfigRequest, WebhookConfigResponse, AlertResponse,
    AlertHistoryResponse, TestAlertRequest
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Institutional Trading Bot API",
    description="Phase 1: Foundation - IBKR Connection, Data, Features",
    version="1.0.0"
)

# Create API router with /api prefix
api_router = APIRouter(prefix="/api")

# Global state
class TradingState:
    """Global trading system state"""
    def __init__(self):
        self.connector: Optional[BaseIBKRConnector] = None
        self.data_manager: Optional[DataManager] = None
        self.feature_engine: Optional[FeatureEngine] = None
        self.start_time: datetime = datetime.now(timezone.utc)
        self.kill_switch_active: bool = False
        self.current_regime: MarketRegime = MarketRegime.SIDEWAYS
        self.last_heartbeat: datetime = datetime.now(timezone.utc)
        self.data_loaded: bool = False
        self.cached_features: Dict[str, FeatureSet] = {}
        self.portfolio_history: List[Dict] = []

state = TradingState()


# ===== Startup/Shutdown Events =====

@app.on_event("startup")
async def startup():
    """Initialize trading system components"""
    logger.info("Starting Trading Bot API...")
    
    # Initialize connector (simulated by default)
    state.connector = IBKRConnector.create(CONFIG.mode)
    await state.connector.connect()
    
    # Initialize data manager
    db_path = os.path.join(ROOT_DIR, CONFIG.data.db_path)
    state.data_manager = DataManager(db_path)
    
    # Initialize feature engine
    state.feature_engine = FeatureEngine()
    
    logger.info(f"Trading Bot initialized in {CONFIG.mode.value} mode")
    
    # Start background task to load data
    asyncio.create_task(load_initial_data())


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down Trading Bot...")
    
    if state.connector:
        await state.connector.disconnect()
    
    if state.data_manager:
        state.data_manager.close()
    
    # Close alert manager session
    await alert_manager.close()


async def load_initial_data():
    """Load historical data on startup"""
    try:
        logger.info("Loading initial historical data...")
        
        symbols = CONFIG.symbols.all_symbols
        results = await state.data_manager.load_historical_data(
            state.connector,
            symbols,
            duration="5 Y"
        )
        
        state.data_loaded = True
        logger.info(f"Data loaded: {results}")
        
        # Calculate initial features
        for symbol in symbols:
            await update_features(symbol)
            
    except Exception as e:
        logger.error(f"Error loading initial data: {e}")


async def update_features(symbol: str) -> Optional[FeatureSet]:
    """Update cached features for a symbol"""
    try:
        bars = state.data_manager.get_historical_bars(symbol)
        if bars and len(bars) > 252:
            features = state.feature_engine.calculate_features(bars)
            if features:
                state.cached_features[symbol] = features
                return features
    except Exception as e:
        logger.error(f"Error updating features for {symbol}: {e}")
    return None


# ===== System Status Endpoints =====

@api_router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get system health status"""
    state.last_heartbeat = datetime.now(timezone.utc)
    
    return SystemStatus(
        status="running" if not state.kill_switch_active else "kill_switch_active",
        mode=CONFIG.mode.value,
        connected=state.connector.is_connected if state.connector else False,
        uptime_seconds=(datetime.now(timezone.utc) - state.start_time).total_seconds(),
        last_heartbeat=state.last_heartbeat.isoformat(),
        symbols_tracked=CONFIG.symbols.all_symbols,
        data_loaded=state.data_loaded
    )


@api_router.post("/kill-switch", response_model=dict)
async def toggle_kill_switch(action: KillSwitchAction):
    """Activate or deactivate kill switch"""
    if action.action == "activate":
        state.kill_switch_active = True
        logger.warning(f"KILL SWITCH ACTIVATED: {action.reason}")
        
        # Close all positions (simulated)
        if state.connector:
            positions = await state.connector.get_positions()
            for symbol, qty in positions.items():
                if qty > 0:
                    await state.connector.place_order(symbol, qty, "MKT", "SELL")
                elif qty < 0:
                    await state.connector.place_order(symbol, abs(qty), "MKT", "BUY")
        
        return {"status": "activated", "reason": action.reason}
    else:
        state.kill_switch_active = False
        logger.info("Kill switch deactivated")
        return {"status": "deactivated"}


# ===== Market Data Endpoints =====

@api_router.get("/market-data", response_model=List[MarketDataResponse])
async def get_all_market_data():
    """Get real-time market data for all symbols"""
    if not state.connector or not state.connector.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to broker")
    
    results = []
    for symbol in CONFIG.symbols.all_symbols:
        data = await state.connector.get_market_data(symbol)
        if data:
            results.append(MarketDataResponse(
                symbol=data.symbol,
                timestamp=data.timestamp.isoformat(),
                bid=round(data.bid, 2),
                ask=round(data.ask, 2),
                last=round(data.last, 2),
                volume=data.volume,
                high=round(data.high, 2),
                low=round(data.low, 2),
                open=round(data.open, 2),
                close=round(data.close, 2),
                spread=round(data.spread, 4),
                spread_pct=round(data.spread_pct * 100, 4)
            ))
    
    return results


@api_router.get("/market-data/{symbol}", response_model=MarketDataResponse)
async def get_market_data(symbol: str):
    """Get real-time market data for a specific symbol"""
    if not state.connector or not state.connector.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to broker")
    
    data = await state.connector.get_market_data(symbol.upper())
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    
    return MarketDataResponse(
        symbol=data.symbol,
        timestamp=data.timestamp.isoformat(),
        bid=round(data.bid, 2),
        ask=round(data.ask, 2),
        last=round(data.last, 2),
        volume=data.volume,
        high=round(data.high, 2),
        low=round(data.low, 2),
        open=round(data.open, 2),
        close=round(data.close, 2),
        spread=round(data.spread, 4),
        spread_pct=round(data.spread_pct * 100, 4)
    )


@api_router.get("/historical/{symbol}", response_model=List[HistoricalBarResponse])
async def get_historical_data(
    symbol: str,
    days: int = 252,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get historical OHLCV data"""
    if not state.data_manager:
        raise HTTPException(status_code=503, detail="Data manager not initialized")
    
    start = datetime.fromisoformat(start_date) if start_date else datetime.now(timezone.utc) - timedelta(days=days)
    end = datetime.fromisoformat(end_date) if end_date else datetime.now(timezone.utc)
    
    bars = state.data_manager.get_historical_bars(symbol.upper(), start, end)
    
    return [
        HistoricalBarResponse(
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            open=round(bar.open, 2),
            high=round(bar.high, 2),
            low=round(bar.low, 2),
            close=round(bar.close, 2),
            volume=bar.volume
        )
        for bar in bars
    ]


# ===== Feature Endpoints =====

@api_router.get("/features/{symbol}", response_model=FeatureSetResponse)
async def get_features(symbol: str):
    """Get calculated features for a symbol"""
    symbol = symbol.upper()
    
    if symbol not in state.cached_features:
        features = await update_features(symbol)
        if not features:
            raise HTTPException(status_code=404, detail=f"No features for {symbol}")
    
    f = state.cached_features[symbol]
    
    return FeatureSetResponse(
        symbol=f.symbol,
        timestamp=f.timestamp.isoformat(),
        price=round(f.price, 2),
        return_1d=round(f.return_1d * 100, 2),
        return_5d=round(f.return_5d * 100, 2),
        return_20d=round(f.return_20d * 100, 2),
        volatility_20d=round(f.volatility_20d * 100, 2),
        volatility_annualized=round(f.volatility_annualized * 100, 2),
        rsi_14=round(f.rsi_14, 1),
        macd_histogram=round(f.macd_histogram, 4),
        bollinger_pct_b=round(f.bollinger_pct_b, 2),
        atr_pct=round(f.atr_pct * 100, 2),
        adx_14=round(f.adx_14, 1),
        volume_ratio=round(f.volume_ratio, 2)
    )


@api_router.get("/features", response_model=List[FeatureSetResponse])
async def get_all_features():
    """Get features for all symbols"""
    results = []
    for symbol in CONFIG.symbols.all_symbols:
        try:
            f = state.cached_features.get(symbol)
            if not f:
                f = await update_features(symbol)
            if f:
                results.append(FeatureSetResponse(
                    symbol=f.symbol,
                    timestamp=f.timestamp.isoformat(),
                    price=round(f.price, 2),
                    return_1d=round(f.return_1d * 100, 2),
                    return_5d=round(f.return_5d * 100, 2),
                    return_20d=round(f.return_20d * 100, 2),
                    volatility_20d=round(f.volatility_20d * 100, 2),
                    volatility_annualized=round(f.volatility_annualized * 100, 2),
                    rsi_14=round(f.rsi_14, 1),
                    macd_histogram=round(f.macd_histogram, 4),
                    bollinger_pct_b=round(f.bollinger_pct_b, 2),
                    atr_pct=round(f.atr_pct * 100, 2),
                    adx_14=round(f.adx_14, 1),
                    volume_ratio=round(f.volume_ratio, 2)
                ))
        except Exception as e:
            logger.error(f"Error getting features for {symbol}: {e}")
    
    return results


# ===== Account & Positions Endpoints =====

@api_router.get("/account", response_model=AccountSummary)
async def get_account():
    """Get account summary with positions"""
    if not state.connector:
        raise HTTPException(status_code=503, detail="Not connected")
    
    summary = await state.connector.get_account_summary()
    positions_raw = await state.connector.get_positions()
    
    positions = []
    for symbol, qty in positions_raw.items():
        if qty != 0:
            market_data = await state.connector.get_market_data(symbol)
            if market_data:
                # Estimate avg cost (simplified for simulation)
                avg_cost = market_data.last * 0.98 if qty > 0 else market_data.last * 1.02
                market_value = market_data.last * qty
                unrealized_pnl = market_value - (avg_cost * qty)
                
                positions.append(PositionResponse(
                    symbol=symbol,
                    quantity=qty,
                    avg_cost=round(avg_cost, 2),
                    current_price=round(market_data.last, 2),
                    market_value=round(market_value, 2),
                    unrealized_pnl=round(unrealized_pnl, 2),
                    unrealized_pnl_pct=round(unrealized_pnl / (avg_cost * abs(qty)) * 100, 2) if avg_cost * qty != 0 else 0
                ))
    
    # Calculate daily P&L (simplified)
    daily_pnl = summary.get('pnl', 0) * 0.1  # Estimate
    
    return AccountSummary(
        cash=round(summary.get('cash', 0), 2),
        portfolio_value=round(summary.get('portfolio_value', 0), 2),
        initial_capital=round(summary.get('initial_capital', 100000), 2),
        total_pnl=round(summary.get('pnl', 0), 2),
        total_pnl_pct=round(summary.get('pnl_pct', 0), 2),
        daily_pnl=round(daily_pnl, 2),
        daily_pnl_pct=round(daily_pnl / summary.get('initial_capital', 100000) * 100, 2),
        positions=positions
    )


@api_router.get("/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get current positions"""
    account = await get_account()
    return account.positions


# ===== Trading Endpoints =====

@api_router.post("/orders", response_model=TradeResponse)
async def place_order(order: OrderRequest):
    """Place a new order"""
    if state.kill_switch_active:
        raise HTTPException(status_code=403, detail="Kill switch is active")
    
    if not state.connector:
        raise HTTPException(status_code=503, detail="Not connected")
    
    result = await state.connector.place_order(
        symbol=order.symbol.upper(),
        quantity=order.quantity,
        order_type=order.order_type,
        side=order.side.upper(),
        limit_price=order.limit_price
    )
    
    # Record trade
    if state.data_manager and result.status in ['filled', 'partial']:
        state.data_manager.record_trade(
            order_id=result.order_id,
            symbol=order.symbol.upper(),
            side=order.side.upper(),
            quantity=order.quantity,
            filled_qty=result.filled_qty,
            avg_price=result.avg_fill_price,
            commission=result.commission,
            regime=state.current_regime.value
        )
    
    return TradeResponse(
        order_id=result.order_id,
        symbol=order.symbol.upper(),
        side=order.side.upper(),
        quantity=order.quantity,
        filled_qty=result.filled_qty,
        avg_price=round(result.avg_fill_price, 2),
        commission=round(result.commission, 2),
        strategy=None,
        regime=state.current_regime.value,
        timestamp=result.timestamp.isoformat()
    )


@api_router.get("/trades", response_model=List[TradeResponse])
async def get_trades(limit: int = 50):
    """Get recent trades"""
    if not state.data_manager:
        return []
    
    trades = state.data_manager.get_trades(limit=limit)
    
    return [
        TradeResponse(
            order_id=t['order_id'],
            symbol=t['symbol'],
            side=t['side'],
            quantity=t['quantity'],
            filled_qty=t['filled_qty'],
            avg_price=t['avg_price'],
            commission=t['commission'],
            strategy=t.get('strategy'),
            regime=t.get('regime'),
            timestamp=t['timestamp']
        )
        for t in trades
    ]


# ===== Data Quality Endpoints =====

@api_router.get("/data-quality/{symbol}", response_model=DataQualityReport)
async def check_data_quality(symbol: str):
    """Check data quality for a symbol"""
    if not state.data_manager:
        raise HTTPException(status_code=503, detail="Data manager not initialized")
    
    result = state.data_manager.check_data_quality(symbol.upper())
    
    return DataQualityReport(
        symbol=result['symbol'],
        status=result['status'],
        total_bars=result.get('total_bars', 0),
        date_range=result.get('date_range', 'N/A'),
        issues=result.get('issues', [])
    )


@api_router.get("/data-stats", response_model=dict)
async def get_data_stats():
    """Get database statistics"""
    if not state.data_manager:
        raise HTTPException(status_code=503, detail="Data manager not initialized")
    
    return state.data_manager.get_data_stats()


# ===== Dashboard Endpoint =====

@api_router.get("/dashboard", response_model=DashboardData)
async def get_dashboard_data():
    """Get all dashboard data in one call"""
    status = await get_system_status()
    account = await get_account()
    trades = await get_trades(limit=10)
    market_data = await get_all_market_data()
    
    # Get portfolio history
    history = []
    if state.data_manager:
        raw_history = state.data_manager.get_portfolio_history(days=30)
        history = [
            PortfolioSnapshot(
                timestamp=h['timestamp'],
                portfolio_value=h['portfolio_value'],
                cash=h['cash'],
                daily_pnl=h.get('daily_pnl', 0),
                total_pnl=h.get('total_pnl', 0)
            )
            for h in raw_history
        ]
    
    # Get recent signals
    signals = []
    if state.data_manager:
        raw_signals = state.data_manager.get_recent_signals(limit=10)
        signals = [
            StrategySignal(
                strategy=s['strategy'],
                symbol=s['symbol'],
                signal=s['signal'],
                confidence=s.get('confidence', 0),
                timestamp=s['timestamp']
            )
            for s in raw_signals
        ]
    
    return DashboardData(
        system_status=status,
        account=account,
        recent_trades=trades,
        market_data=market_data,
        portfolio_history=history,
        regime=state.current_regime.value,
        signals=signals
    )


# ===== Configuration Endpoint =====

@api_router.get("/config", response_model=dict)
async def get_config():
    """Get current configuration"""
    return {
        "mode": CONFIG.mode.value,
        "symbols": CONFIG.symbols.all_symbols,
        "risk": {
            "target_volatility": CONFIG.risk.target_annual_volatility,
            "max_drawdown": CONFIG.risk.max_drawdown,
            "kill_switch_drawdown": CONFIG.risk.kill_switch_drawdown,
            "max_position_size": CONFIG.risk.max_single_position,
            "max_leverage": CONFIG.risk.max_gross_exposure
        },
        "backtest": {
            "commission_per_share": CONFIG.backtest.commission_per_share,
            "base_slippage": CONFIG.backtest.base_slippage,
            "signal_delay_ms": CONFIG.backtest.signal_to_fill_delay_ms
        }
    }


# ===== Root endpoint =====

@api_router.get("/")
async def root():
    """API root"""
    return {
        "name": "Institutional Trading Bot API",
        "version": "1.0.0",
        "phase": "1 - Foundation",
        "mode": CONFIG.mode.value,
        "endpoints": [
            "/api/status",
            "/api/dashboard",
            "/api/market-data",
            "/api/features",
            "/api/account",
            "/api/positions",
            "/api/trades",
            "/api/orders",
            "/api/config"
        ]
    }


# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
