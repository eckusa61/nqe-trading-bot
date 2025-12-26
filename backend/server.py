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
from trading_bot.strategies import (
    BaseStrategy, Signal, StrategyResult, strategy_registry,
    MomentumStrategy, MeanReversionStrategy, VolatilityBreakoutStrategy,
    TrendFollowingStrategy, StatisticalArbitrageStrategy
)
from trading_bot.backtest import BacktestEngine, BacktestResult, RealisticCostModel, PerformanceAnalyzer
from trading_bot.risk import (
    GuardianAgent, GuardianDecision, TradeRequest, ReconciliationEngine, PDTEnforcer,
    TimeSyncManager, time_sync_manager, MarketSession, MarketStatus, OrderTimeValidation,
    CorporateActionsHandler, corporate_actions_handler, CorporateAction, CorporateActionType, Position, PositionAdjustment
)
from trading_bot.ensemble import (
    RegimeDetector, MarketRegime as EnsembleMarketRegime, RegimeState,
    StrategyWeightManager, MetaLearner, EnsembleSignal
)
from trading_bot.notifications import telegram_manager, TelegramManager
from trading_bot.ai import ai_supervisor, AISupervisor
from trading_bot.social import social_analyzer, SocialSentimentAnalyzer
from trading_bot.execution import ExecutionEngine, ExecutionAlgorithm
from trading_bot.signals import SignalLevelsCalculator, SignalStrength
from trading_bot.news import NewsAggregator
from trading_bot.learning import SelfLearningEngine
from trading_bot.strategies import get_all_strategies, STRATEGY_REGISTRY
from trading_bot.social.data_sources import (
    RedditFeed, StockTwitsFeed, YahooFinanceFeed,
    CryptoFeed, NewsFeed, FinvizFeed, ForexFeed, TwitterFeed
)

# Initialize data feeds
reddit_feed = RedditFeed()
stocktwits_feed = StockTwitsFeed()
yahoo_feed = YahooFinanceFeed()
crypto_feed = CryptoFeed()
news_feed = NewsFeed()
finviz_feed = FinvizFeed()
forex_feed = ForexFeed()
twitter_feed = TwitterFeed()

# Initialize new modules
execution_engine = ExecutionEngine()
signal_calculator = SignalLevelsCalculator()
news_aggregator = NewsAggregator()
learning_engine = SelfLearningEngine()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NQE Trading Bot API",
    description="Institutional Trading Bot with AI Supervisor - All Markets",
    version="2.0.0"
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
        self.backtest_engine: Optional[BacktestEngine] = None
        self.guardian: Optional[GuardianAgent] = None
        self.reconciliation: Optional[ReconciliationEngine] = None
        self.pdt_enforcer: Optional[PDTEnforcer] = None
        self.regime_detector: Optional[RegimeDetector] = None
        self.weight_manager: Optional[StrategyWeightManager] = None
        self.meta_learner: Optional[MetaLearner] = None
        self.start_time: datetime = datetime.now(timezone.utc)
        self.kill_switch_active: bool = False
        self.current_regime: MarketRegime = MarketRegime.SIDEWAYS
        self.last_heartbeat: datetime = datetime.now(timezone.utc)
        self.data_loaded: bool = False
        self.cached_features: Dict[str, FeatureSet] = {}
        self.portfolio_history: List[Dict] = []
        self.last_backtest_result: Optional[Dict] = None

state = TradingState()

# Initialize strategies
def init_strategies():
    """Register all strategies"""
    strategy_registry.register(MomentumStrategy())
    strategy_registry.register(MeanReversionStrategy())
    strategy_registry.register(VolatilityBreakoutStrategy())
    strategy_registry.register(TrendFollowingStrategy())
    strategy_registry.register(StatisticalArbitrageStrategy())
    logger.info(f"Registered {len(strategy_registry.get_all())} strategies")

# Initialize risk modules
def init_risk_modules():
    """Initialize Guardian, Reconciliation, PDT"""
    state.guardian = GuardianAgent()
    state.reconciliation = ReconciliationEngine()
    state.pdt_enforcer = PDTEnforcer()
    logger.info("Risk modules initialized: Guardian, Reconciliation, PDT")

# Initialize ensemble modules
def init_ensemble_modules():
    """Initialize Regime Detector, Weight Manager, Meta-Learner"""
    state.regime_detector = RegimeDetector()
    state.weight_manager = StrategyWeightManager()
    state.meta_learner = MetaLearner(
        regime_detector=state.regime_detector,
        weight_manager=state.weight_manager
    )
    logger.info("Ensemble modules initialized: RegimeDetector, WeightManager, MetaLearner")


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
    
    # Initialize backtest engine
    state.backtest_engine = BacktestEngine()
    
    # Initialize strategies
    init_strategies()
    
    # Initialize risk modules
    init_risk_modules()
    
    # Initialize ensemble modules
    init_ensemble_modules()
    
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
async def toggle_kill_switch(action: KillSwitchAction, background_tasks: BackgroundTasks):
    """Activate or deactivate kill switch"""
    if action.action == "activate":
        state.kill_switch_active = True
        logger.warning(f"KILL SWITCH ACTIVATED: {action.reason}")
        
        # Send critical alert
        background_tasks.add_task(
            alert_manager.alert_drawdown_critical,
            current_drawdown=15.0,
            threshold=15.0
        )
        
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
        "version": "2.0.0",
        "phase": "2 - Strategies & Backtesting",
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
            "/api/config",
            "/api/webhooks",
            "/api/alerts",
            "/api/strategies",
            "/api/strategies/{name}/signals",
            "/api/backtest"
        ]
    }


# ===== Strategy Endpoints =====

@api_router.get("/strategies", response_model=List[dict])
async def get_strategies():
    """Get all registered strategies"""
    strategies = strategy_registry.get_all()
    return [
        {
            "name": s.name,
            "description": s.description,
            "enabled": s.enabled,
            "parameters": s.get_parameters()
        }
        for s in strategies
    ]


@api_router.get("/strategies/{name}", response_model=dict)
async def get_strategy(name: str):
    """Get a specific strategy"""
    strategy = strategy_registry.get(name)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    
    return {
        "name": strategy.name,
        "description": strategy.description,
        "enabled": strategy.enabled,
        "parameters": strategy.get_parameters()
    }


@api_router.post("/strategies/{name}/toggle", response_model=dict)
async def toggle_strategy(name: str):
    """Enable/disable a strategy"""
    strategy = strategy_registry.get(name)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    
    strategy.enabled = not strategy.enabled
    return {"name": strategy.name, "enabled": strategy.enabled}


@api_router.get("/strategies/{name}/signals", response_model=List[dict])
async def get_strategy_signals(name: str):
    """Generate signals for a specific strategy"""
    strategy = strategy_registry.get(name)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    
    # Get current features
    features_list = []
    for symbol in CONFIG.symbols.all_symbols:
        if symbol in state.cached_features:
            features_list.append(state.cached_features[symbol])
        else:
            await update_features(symbol)
            if symbol in state.cached_features:
                features_list.append(state.cached_features[symbol])
    
    if not features_list:
        return []
    
    result = strategy.evaluate(features_list)
    return [s.to_dict() for s in result.signals]


@api_router.get("/signals", response_model=List[dict])
async def get_all_signals():
    """Generate signals from all enabled strategies"""
    # Get current features
    features_list = []
    for symbol in CONFIG.symbols.all_symbols:
        if symbol in state.cached_features:
            features_list.append(state.cached_features[symbol])
    
    if not features_list:
        return []
    
    results = strategy_registry.evaluate_all(features_list)
    
    all_signals = []
    for result in results:
        for signal in result.signals:
            all_signals.append(signal.to_dict())
    
    return all_signals


# ===== Backtest Endpoints =====

@api_router.post("/backtest", response_model=dict)
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    Run backtest for specified strategies
    
    Request body:
    - symbols: List of symbols to trade
    - start_date: Backtest start date (ISO format)
    - end_date: Backtest end date (ISO format)
    - initial_capital: Starting capital
    - strategies: List of strategy names to test
    - leverage: Target leverage (1.0 = no leverage)
    """
    if not state.data_manager:
        raise HTTPException(status_code=503, detail="Data manager not initialized")
    
    # Get strategies
    strategies_to_test = []
    for name in request.strategies:
        strategy = strategy_registry.get(name)
        if strategy:
            strategies_to_test.append(strategy)
    
    if not strategies_to_test:
        raise HTTPException(status_code=400, detail="No valid strategies specified")
    
    # Get historical data for symbols
    historical_data = {}
    for symbol in request.symbols:
        bars = state.data_manager.get_historical_bars(symbol)
        if bars:
            historical_data[symbol] = bars
    
    if not historical_data:
        raise HTTPException(status_code=400, detail="No historical data available for specified symbols")
    
    # Parse dates
    try:
        start_date = datetime.fromisoformat(request.start_date) if request.start_date else None
        end_date = datetime.fromisoformat(request.end_date) if request.end_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Run backtest for each strategy
    results = []
    for strategy in strategies_to_test:
        backtest_engine = BacktestEngine(initial_capital=request.initial_capital)
        result = backtest_engine.run(
            strategy=strategy,
            historical_data=historical_data,
            start_date=start_date,
            end_date=end_date
        )
        results.append(result.to_dict())
    
    # Store last result
    state.last_backtest_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results
    }
    
    return {
        "status": "completed",
        "results": results
    }


@api_router.get("/backtest/last", response_model=dict)
async def get_last_backtest():
    """Get the last backtest result"""
    if not state.last_backtest_result:
        raise HTTPException(status_code=404, detail="No backtest results available")
    return state.last_backtest_result


# ===== Guardian/Risk Endpoints =====

@api_router.get("/guardian/status", response_model=dict)
async def get_guardian_status():
    """Get Guardian Agent status"""
    if not state.guardian:
        raise HTTPException(status_code=503, detail="Guardian not initialized")
    return state.guardian.get_status()


@api_router.post("/guardian/evaluate", response_model=dict)
async def evaluate_trade_with_guardian(
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    strategy: str = "Manual"
):
    """Evaluate a trade request with Guardian"""
    if not state.guardian:
        raise HTTPException(status_code=503, detail="Guardian not initialized")
    
    request = TradeRequest(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        strategy=strategy,
        signal_strength=0.5,
        confidence=0.5
    )
    
    decision = state.guardian.evaluate_trade(request)
    
    return {
        "action": decision.action.value,
        "original_quantity": request.quantity,
        "modified_quantity": decision.modified_quantity,
        "reason": decision.reason,
        "risk_score": decision.risk_score,
        "checks_passed": decision.checks_passed,
        "checks_failed": decision.checks_failed
    }


@api_router.post("/guardian/update-state", response_model=dict)
async def update_guardian_state(
    drawdown: float = None,
    vix: float = None,
    sharpe: float = None,
    portfolio_value: float = None
):
    """Update Guardian state with current metrics"""
    if not state.guardian:
        raise HTTPException(status_code=503, detail="Guardian not initialized")
    
    state.guardian.update_state(
        drawdown=drawdown,
        vix=vix,
        sharpe=sharpe,
        portfolio_value=portfolio_value
    )
    
    return {"status": "updated", "guardian_status": state.guardian.get_status()}


@api_router.get("/reconciliation/status", response_model=dict)
async def get_reconciliation_status():
    """Get reconciliation status"""
    if not state.reconciliation:
        raise HTTPException(status_code=503, detail="Reconciliation not initialized")
    return state.reconciliation.get_status()


@api_router.post("/reconciliation/run", response_model=dict)
async def run_reconciliation():
    """Run reconciliation check"""
    if not state.reconciliation or not state.connector:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    # Get broker state
    broker_positions = await state.connector.get_positions()
    broker_summary = await state.connector.get_account_summary()
    broker_cash = broker_summary.get('cash', 0)
    
    # Get system state (from connector's internal state for simulation)
    system_positions = broker_positions  # In simulation, they're the same
    system_cash = broker_cash
    
    # Run reconciliation
    result = state.reconciliation.full_reconciliation(
        broker_positions=broker_positions,
        system_positions=system_positions,
        broker_cash=broker_cash,
        system_cash=system_cash
    )
    
    return result


@api_router.get("/reconciliation/history", response_model=dict)
async def get_reconciliation_history(limit: int = 20):
    """Get reconciliation discrepancy history"""
    if not state.reconciliation:
        raise HTTPException(status_code=503, detail="Reconciliation not initialized")
    return {"history": state.reconciliation.get_history(limit)}


@api_router.get("/pdt/status", response_model=dict)
async def get_pdt_status():
    """Get PDT enforcer status"""
    if not state.pdt_enforcer or not state.connector:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    account = await state.connector.get_account_summary()
    account_value = account.get('portfolio_value', 0)
    
    return state.pdt_enforcer.get_status(account_value)


@api_router.post("/pdt/check", response_model=dict)
async def check_pdt_for_trade(symbol: str, side: str):
    """Check if trade would violate PDT rules"""
    if not state.pdt_enforcer or not state.connector:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    account = await state.connector.get_account_summary()
    account_value = account.get('portfolio_value', 0)
    
    return state.pdt_enforcer.check_before_trade(symbol, side, account_value)


# ===== Webhook/Alert Endpoints =====

@api_router.get("/webhooks", response_model=WebhookConfigResponse)
async def get_webhook_config():
    """Get current webhook configuration"""
    return WebhookConfigResponse(
        slack_configured=bool(alert_manager.config.slack_url),
        discord_configured=bool(alert_manager.config.discord_url),
        enabled=alert_manager.config.enabled,
        rate_limit=alert_manager.config.rate_limit,
        enabled_alerts=[a.value for a in alert_manager.config.enabled_alerts]
    )


@api_router.post("/webhooks", response_model=WebhookConfigResponse)
async def configure_webhooks(config: WebhookConfigRequest):
    """Configure Slack/Discord webhook URLs"""
    alert_manager.update_config(
        slack_url=config.slack_url,
        discord_url=config.discord_url,
        enabled=config.enabled
    )
    
    return WebhookConfigResponse(
        slack_configured=bool(alert_manager.config.slack_url),
        discord_configured=bool(alert_manager.config.discord_url),
        enabled=alert_manager.config.enabled,
        rate_limit=alert_manager.config.rate_limit,
        enabled_alerts=[a.value for a in alert_manager.config.enabled_alerts]
    )


@api_router.get("/alerts", response_model=AlertHistoryResponse)
async def get_alert_history(limit: int = 50):
    """Get recent alert history"""
    history = alert_manager.get_alert_history(limit=limit)
    return AlertHistoryResponse(
        alerts=[AlertResponse(**a) for a in history],
        total=len(history)
    )


@api_router.post("/alerts/test", response_model=dict)
async def send_test_alert(request: TestAlertRequest):
    """Send a test alert to configured webhooks"""
    if not alert_manager.config.slack_url and not alert_manager.config.discord_url:
        raise HTTPException(
            status_code=400, 
            detail="No webhooks configured. Set slack_url or discord_url first."
        )
    
    test_alert = Alert(
        alert_type=AlertType.DRAWDOWN_WARNING,
        level=AlertLevel.INFO,
        title="Test Alert",
        message="This is a test alert from TradingBot to verify webhook configuration.",
        data={
            "Type": request.alert_type,
            "Status": "TEST",
            "System": "TradingBot Phase 1"
        }
    )
    
    # Force send regardless of level filter
    original_level = alert_manager.config.min_level
    alert_manager.config.min_level = AlertLevel.INFO
    
    success = await alert_manager.send_alert(test_alert)
    
    alert_manager.config.min_level = original_level
    
    if success:
        return {"status": "sent", "message": "Test alert sent successfully"}
    else:
        return {"status": "failed", "message": "Failed to send test alert. Check webhook URLs."}


@api_router.post("/alerts/drawdown-warning", response_model=dict)
async def trigger_drawdown_warning(drawdown: float = 10.5):
    """Manually trigger a drawdown warning (for testing)"""
    await alert_manager.alert_drawdown_warning(drawdown, threshold=10.0)
    return {"status": "sent", "drawdown": drawdown}


@api_router.post("/alerts/connection-lost", response_model=dict)
async def trigger_connection_lost():
    """Manually trigger connection lost alert (for testing)"""
    await alert_manager.alert_connection_lost("IBKR")
    return {"status": "sent", "alert": "connection_lost"}


# ===== Time Sync Manager Endpoints =====

@api_router.get("/market/status", response_model=dict)
async def get_market_status():
    """
    Get current market status including:
    - Is market open/closed
    - Current session (pre-market, regular, after-hours)
    - Time to open/close
    - Holiday information
    """
    status = time_sync_manager.get_market_status()
    return status.to_dict()


@api_router.get("/market/can-trade", response_model=dict)
async def check_can_trade(allow_extended_hours: bool = False):
    """
    Check if trading is allowed at current time
    
    Args:
        allow_extended_hours: Allow trading during pre-market/after-hours
    """
    validation = time_sync_manager.validate_order_time(allow_extended_hours)
    return {
        "allowed": validation.allowed,
        "reason": validation.reason,
        "session": validation.session.value,
        "suggested_action": validation.suggested_action,
        "minutes_until_allowed": validation.minutes_until_allowed
    }


@api_router.get("/market/calendar", response_model=dict)
async def get_trading_calendar(days_ahead: int = 30):
    """
    Get trading calendar for upcoming days
    
    Args:
        days_ahead: Number of days to look ahead (max 90)
    """
    days = min(days_ahead, 90)
    return time_sync_manager.get_trading_calendar(days)


@api_router.post("/market/sync-broker-time", response_model=dict)
async def sync_broker_time():
    """
    Synchronize time with broker and detect drift
    Uses current broker connection time
    """
    if not state.connector or not state.connector.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to broker")
    
    # Get broker time (for simulation, use system time)
    broker_time = datetime.now(timezone.utc)
    
    result = time_sync_manager.sync_with_broker(broker_time)
    return result


@api_router.get("/market/time-sync-status", response_model=dict)
async def get_time_sync_status():
    """Get comprehensive time sync manager status"""
    return time_sync_manager.get_status()


# ===== Corporate Actions Endpoints =====

@api_router.get("/corporate-actions/status", response_model=dict)
async def get_corporate_actions_status():
    """Get corporate actions handler status"""
    return corporate_actions_handler.get_status()


@api_router.get("/corporate-actions/pending", response_model=dict)
async def get_pending_corporate_actions(symbol: Optional[str] = None):
    """
    Get pending corporate actions
    
    Args:
        symbol: Optional symbol filter
    """
    actions = corporate_actions_handler.get_pending_actions(symbol)
    return {
        "count": len(actions),
        "actions": [a.to_dict() for a in actions]
    }


@api_router.post("/corporate-actions/split", response_model=dict)
async def add_stock_split(
    symbol: str,
    ratio_to: int,
    ratio_from: int,
    ex_date: str
):
    """
    Add a stock split corporate action
    
    Example: For a 2:1 split, ratio_to=2, ratio_from=1
    Example: For a 1:5 reverse split, ratio_to=1, ratio_from=5
    
    Args:
        symbol: Stock symbol
        ratio_to: New share count
        ratio_from: Old share count
        ex_date: Ex-date in ISO format (YYYY-MM-DD)
    """
    try:
        ex_datetime = datetime.fromisoformat(ex_date).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    action = corporate_actions_handler.create_split_action(
        symbol=symbol.upper(),
        ratio_to=ratio_to,
        ratio_from=ratio_from,
        ex_date=ex_datetime
    )
    
    success = corporate_actions_handler.add_corporate_action(action)
    
    if success:
        return {"status": "added", "action": action.to_dict()}
    else:
        raise HTTPException(status_code=400, detail="Failed to add action (duplicate?)")


@api_router.post("/corporate-actions/dividend", response_model=dict)
async def add_dividend(
    symbol: str,
    amount: float,
    ex_date: str,
    payment_date: Optional[str] = None,
    is_stock_dividend: bool = False
):
    """
    Add a dividend corporate action
    
    Args:
        symbol: Stock symbol
        amount: Dividend per share (cash) or percentage (stock dividend)
        ex_date: Ex-dividend date (YYYY-MM-DD)
        payment_date: Optional payment date (YYYY-MM-DD)
        is_stock_dividend: True if stock dividend (amount is percentage)
    """
    try:
        ex_datetime = datetime.fromisoformat(ex_date).replace(tzinfo=timezone.utc)
        pay_datetime = None
        if payment_date:
            pay_datetime = datetime.fromisoformat(payment_date).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    action = corporate_actions_handler.create_dividend_action(
        symbol=symbol.upper(),
        amount=amount,
        ex_date=ex_datetime,
        payment_date=pay_datetime,
        is_stock_dividend=is_stock_dividend
    )
    
    success = corporate_actions_handler.add_corporate_action(action)
    
    if success:
        return {"status": "added", "action": action.to_dict()}
    else:
        raise HTTPException(status_code=400, detail="Failed to add action (duplicate?)")


@api_router.post("/corporate-actions/process/{symbol}", response_model=dict)
async def process_corporate_actions_for_symbol(symbol: str):
    """
    Process all pending corporate actions for a symbol
    Applies to current positions
    """
    symbol = symbol.upper()
    
    # Get current position
    if not state.connector:
        raise HTTPException(status_code=503, detail="Not connected")
    
    positions = await state.connector.get_positions()
    qty = positions.get(symbol, 0)
    
    if qty == 0:
        return {
            "status": "no_position",
            "message": f"No position in {symbol} to adjust"
        }
    
    # Get market data for current price
    market_data = await state.connector.get_market_data(symbol)
    current_price = market_data.last if market_data else None
    
    # Get pending actions for this symbol
    pending = corporate_actions_handler.get_pending_actions(symbol)
    
    if not pending:
        return {
            "status": "no_actions",
            "message": f"No pending corporate actions for {symbol}"
        }
    
    # Create position object
    position = Position(
        symbol=symbol,
        quantity=qty,
        avg_cost=current_price * 0.98 if current_price else 100.0  # Estimate
    )
    
    # Process each action
    adjustments = []
    for action in pending:
        if not action.processed:
            updated_position, adjustment = corporate_actions_handler.apply_action_to_position(
                position, action, current_price
            )
            position = updated_position
            adjustments.append(adjustment.to_dict())
    
    # Get cash adjustment
    cash_adjustment = corporate_actions_handler.get_cash_adjustment()
    
    return {
        "status": "processed",
        "symbol": symbol,
        "adjustments": adjustments,
        "final_position": {
            "quantity": position.quantity,
            "avg_cost": round(position.avg_cost, 4)
        },
        "cash_adjustment": round(cash_adjustment, 2)
    }


@api_router.get("/corporate-actions/history", response_model=dict)
async def get_corporate_actions_history(symbol: Optional[str] = None, limit: int = 100):
    """
    Get history of position adjustments from corporate actions
    
    Args:
        symbol: Optional symbol filter
        limit: Maximum records to return
    """
    history = corporate_actions_handler.get_adjustment_history(symbol, limit)
    return {
        "count": len(history),
        "history": history
    }


# ===== Ensemble System Endpoints =====

@api_router.get("/ensemble/status", response_model=dict)
async def get_ensemble_status():
    """
    Get full ensemble system status including:
    - Current regime and probabilities
    - Strategy weights by regime
    - Meta-learner settings
    """
    if not state.meta_learner:
        raise HTTPException(status_code=503, detail="Ensemble system not initialized")
    
    return state.meta_learner.get_status()


@api_router.get("/ensemble/regime", response_model=dict)
async def get_current_regime():
    """
    Get current market regime detected by HMM
    
    Returns:
    - Current regime (bull/bear/sideways/crisis)
    - Regime probabilities
    - Confidence level
    - Duration in current regime
    """
    if not state.regime_detector:
        raise HTTPException(status_code=503, detail="Regime detector not initialized")
    
    # Update regime with current features
    features_list = list(state.cached_features.values())
    
    if features_list:
        regime_state = state.regime_detector.detect_from_features(features_list)
        return regime_state.to_dict()
    
    # Return current state without update
    return {
        "current_regime": state.regime_detector.current_state.value,
        "regime_probabilities": {
            r.value: round(p, 3)
            for r, p in state.regime_detector.state_probabilities.items()
        },
        "confidence": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "indicators": {}
    }


@api_router.post("/ensemble/regime/update", response_model=dict)
async def update_regime_manually(
    vix: float = 15.0,
    return_20d: float = 0.0,
    volatility: float = 0.15,
    adx: float = 25.0
):
    """
    Manually update regime with specific indicators
    Useful for testing or when real data is unavailable
    """
    if not state.regime_detector:
        raise HTTPException(status_code=503, detail="Regime detector not initialized")
    
    regime_state = state.regime_detector.update(
        return_20d=return_20d,
        volatility=volatility,
        vix=vix,
        adx=adx
    )
    
    return regime_state.to_dict()


@api_router.get("/ensemble/weights", response_model=dict)
async def get_strategy_weights(regime: Optional[str] = None):
    """
    Get strategy weights for current or specified regime
    
    Args:
        regime: Optional regime override (bull/bear/sideways/crisis)
    """
    if not state.weight_manager:
        raise HTTPException(status_code=503, detail="Weight manager not initialized")
    
    if regime:
        try:
            target_regime = EnsembleMarketRegime(regime.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid regime: {regime}")
    else:
        target_regime = state.regime_detector.current_state if state.regime_detector else EnsembleMarketRegime.SIDEWAYS
    
    # Get optimal weights (includes performance adaptation and correlation penalty)
    weights = state.weight_manager.get_optimal_weights(target_regime)
    base_weights = state.weight_manager.get_weights(target_regime)
    
    return {
        "regime": target_regime.value,
        "optimal_weights": {k: round(v, 3) for k, v in weights.items()},
        "base_weights": {k: round(v, 3) for k, v in base_weights.items()}
    }


@api_router.get("/ensemble/signal", response_model=dict)
async def get_ensemble_signal():
    """
    Get combined ensemble signal from all strategies
    
    Returns weighted combination of all strategy signals based on current regime
    """
    if not state.meta_learner:
        raise HTTPException(status_code=503, detail="Meta-learner not initialized")
    
    # Update regime first
    features_list = list(state.cached_features.values())
    if features_list:
        state.meta_learner.update_regime(features_list)
    
    # Get signals from all strategies
    strategy_results = []
    for strategy in strategy_registry.get_all():
        if strategy.enabled:
            result = strategy.evaluate(features_list)
            strategy_results.append(result)
    
    # Combine signals
    ensemble_signals = state.meta_learner.combine_signals(strategy_results)
    
    return {
        "regime": state.meta_learner.regime_detector.current_state.value,
        "signals": [s.to_dict() for s in ensemble_signals],
        "strategy_count": len(strategy_results),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/ensemble/signal/{symbol}", response_model=dict)
async def get_ensemble_signal_for_symbol(symbol: str):
    """
    Get ensemble signal for a specific symbol
    """
    if not state.meta_learner:
        raise HTTPException(status_code=503, detail="Meta-learner not initialized")
    
    symbol = symbol.upper()
    
    # Get summary from history
    summary = state.meta_learner.get_ensemble_summary(symbol)
    
    if summary:
        return summary
    
    # Generate fresh signal
    full_response = await get_ensemble_signal()
    
    for signal in full_response.get("signals", []):
        if signal.get("symbol") == symbol:
            return signal
    
    return {
        "symbol": symbol,
        "message": "No signal available for this symbol"
    }


@api_router.get("/ensemble/regime/statistics", response_model=dict)
async def get_regime_statistics():
    """
    Get statistics about regime detection over time
    """
    if not state.regime_detector:
        raise HTTPException(status_code=503, detail="Regime detector not initialized")
    
    return state.regime_detector.get_regime_statistics()


@api_router.post("/ensemble/weights/update", response_model=dict)
async def update_strategy_weights(
    regime: str,
    weights: Dict[str, float]
):
    """
    Manually update strategy weights for a regime
    
    Args:
        regime: Target regime (bull/bear/sideways/crisis)
        weights: Dictionary of strategy_name -> weight
    """
    if not state.weight_manager:
        raise HTTPException(status_code=503, detail="Weight manager not initialized")
    
    try:
        target_regime = EnsembleMarketRegime(regime.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid regime: {regime}")
    
    state.weight_manager.update_regime_weights(
        regime=target_regime,
        new_weights=weights,
        reason="Manual API update"
    )
    
    return {
        "status": "updated",
        "regime": target_regime.value,
        "new_weights": state.weight_manager.get_weights(target_regime)
    }


# ===== Telegram Endpoints =====

@api_router.get("/telegram/status", response_model=dict)
async def get_telegram_status():
    """Get Telegram integration status"""
    return telegram_manager.get_status()


@api_router.post("/telegram/test", response_model=dict)
async def test_telegram_channels():
    """Test all Telegram channels"""
    results = await telegram_manager.test_all_channels()
    return {
        "status": "tested",
        "results": results
    }


@api_router.post("/telegram/send-signal", response_model=dict)
async def send_telegram_signal(
    symbol: str,
    action: str,
    price: float,
    target: Optional[float] = None,
    stop_loss: Optional[float] = None,
    confidence: float = 0.8,
    reason: str = ""
):
    """Send trading signal to Telegram"""
    await telegram_manager.send_signal(
        symbol=symbol.upper(),
        action=action.upper(),
        price=price,
        target=target,
        stop_loss=stop_loss,
        confidence=confidence,
        reason=reason
    )
    return {"status": "sent", "channel": "sinyal"}


@api_router.post("/telegram/send-news", response_model=dict)
async def send_telegram_news(
    title: str,
    source: str,
    summary: str,
    sentiment: str = "neutral"
):
    """Send news to Telegram"""
    await telegram_manager.send_news(title, source, summary, sentiment)
    return {"status": "sent", "channel": "haber"}


# ===== AI Supervisor Endpoints =====

@api_router.get("/ai/supervisor/status", response_model=dict)
async def get_ai_supervisor_status():
    """Get AI Supervisor status"""
    return ai_supervisor.get_status()


@api_router.post("/ai/supervisor/start", response_model=dict)
async def start_ai_supervisor(background_tasks: BackgroundTasks):
    """Start the AI Supervisor background task"""
    if ai_supervisor.is_running:
        return {"status": "already_running"}
    
    background_tasks.add_task(ai_supervisor.start)
    return {"status": "starting"}


@api_router.post("/ai/supervisor/stop", response_model=dict)
async def stop_ai_supervisor():
    """Stop the AI Supervisor"""
    await ai_supervisor.stop()
    return {"status": "stopped"}


@api_router.post("/ai/analyze-market", response_model=dict)
async def ai_analyze_market():
    """Get AI market analysis"""
    from trading_bot.ai.llm_client import LLMClient
    
    llm = LLMClient()
    
    # Collect current state
    market_data = {
        "regime": state.regime_detector.current_state.value if state.regime_detector else "unknown",
        "features": {k: v.to_dict() for k, v in list(state.cached_features.items())[:3]}
    }
    
    positions = []
    if state.connector:
        pos = await state.connector.get_positions()
        positions = [{"symbol": k, "qty": v} for k, v in pos.items() if v != 0]
    
    performance = {
        "daily_pnl": ai_supervisor.daily_pnl,
        "consecutive_losses": ai_supervisor.consecutive_losses
    }
    
    analysis = await llm.analyze_market(
        market_data=market_data,
        regime=market_data["regime"],
        positions=positions,
        performance=performance
    )
    
    return analysis


# ===== Social Sentiment Endpoints =====

@api_router.get("/social/status", response_model=dict)
async def get_social_status():
    """Get social sentiment analyzer status"""
    return social_analyzer.get_status()


@api_router.get("/social/sentiment/{symbol}", response_model=dict)
async def get_symbol_sentiment(symbol: str):
    """Get sentiment for a specific symbol"""
    sentiment = social_analyzer.get_sentiment(symbol.upper())
    if sentiment:
        return sentiment.to_dict()
    
    # Try to analyze on-demand
    sentiment = await social_analyzer.analyze_symbol(symbol.upper())
    if sentiment:
        return sentiment.to_dict()
    
    return {"symbol": symbol, "sentiment": "no_data"}


@api_router.get("/social/sentiment", response_model=dict)
async def get_all_sentiments():
    """Get all cached sentiments"""
    return {
        "sentiments": social_analyzer.get_all_sentiments(),
        "count": len(social_analyzer.sentiment_cache)
    }


@api_router.get("/social/signal/{symbol}", response_model=dict)
async def get_sentiment_signal(symbol: str):
    """Get sentiment-based trading signal"""
    return social_analyzer.get_sentiment_signal(symbol.upper())


@api_router.post("/social/start", response_model=dict)
async def start_social_analyzer(background_tasks: BackgroundTasks):
    """Start social sentiment monitoring"""
    if social_analyzer.is_running:
        return {"status": "already_running"}
    
    background_tasks.add_task(social_analyzer.start)
    return {"status": "starting"}


# ===== Data Feeds Endpoints =====

@api_router.get("/feeds/status", response_model=dict)
async def get_all_feeds_status():
    """Get status of all data feeds"""
    return {
        "reddit": reddit_feed.get_status(),
        "stocktwits": stocktwits_feed.get_status(),
        "yahoo": yahoo_feed.get_status(),
        "crypto": crypto_feed.get_status(),
        "news": news_feed.get_status(),
        "finviz": finviz_feed.get_status(),
        "forex": forex_feed.get_status(),
        "twitter": twitter_feed.get_status()
    }


# Reddit Endpoints
@api_router.get("/feeds/reddit/trending", response_model=dict)
async def get_reddit_trending():
    """Get trending tickers from Reddit"""
    trending = await reddit_feed.get_trending_tickers()
    posts = await reddit_feed.get_all_finance_posts(limit_per_sub=5)
    return {
        "trending_tickers": trending,
        "top_posts": [
            {
                "title": p.title,
                "subreddit": p.subreddit,
                "score": p.score,
                "symbols": p.symbols_mentioned
            }
            for p in posts[:20]
        ]
    }


@api_router.get("/feeds/reddit/{symbol}", response_model=dict)
async def get_reddit_symbol_mentions(symbol: str):
    """Get Reddit mentions for a symbol"""
    posts = await reddit_feed.get_symbol_mentions(symbol.upper())
    return {
        "symbol": symbol.upper(),
        "mention_count": len(posts),
        "posts": [
            {
                "title": p.title,
                "subreddit": p.subreddit,
                "score": p.score,
                "comments": p.num_comments
            }
            for p in posts[:10]
        ]
    }


# StockTwits Endpoints
@api_router.get("/feeds/stocktwits/trending", response_model=dict)
async def get_stocktwits_trending():
    """Get trending symbols on StockTwits"""
    trending = await stocktwits_feed.get_trending()
    return {"trending": trending}


@api_router.get("/feeds/stocktwits/{symbol}", response_model=dict)
async def get_stocktwits_sentiment(symbol: str):
    """Get StockTwits sentiment for a symbol"""
    return await stocktwits_feed.get_sentiment_score(symbol.upper())


# Yahoo Finance Endpoints
@api_router.get("/feeds/yahoo/market", response_model=dict)
async def get_yahoo_market_summary():
    """Get market summary from Yahoo Finance"""
    return yahoo_feed.get_market_summary()


@api_router.get("/feeds/yahoo/{symbol}", response_model=dict)
async def get_yahoo_quote(symbol: str):
    """Get Yahoo Finance quote and news"""
    quote = yahoo_feed.get_quote(symbol.upper())
    news = yahoo_feed.get_news(symbol.upper(), limit=5)
    
    return {
        "quote": {
            "symbol": quote.symbol,
            "price": quote.price,
            "change": quote.change,
            "change_percent": quote.change_percent,
            "volume": quote.volume,
            "market_cap": quote.market_cap,
            "pe_ratio": quote.pe_ratio,
            "52w_high": quote.fifty_two_week_high,
            "52w_low": quote.fifty_two_week_low
        } if quote else None,
        "news": [
            {
                "title": n.title,
                "publisher": n.publisher,
                "link": n.link
            }
            for n in news
        ]
    }


# Crypto Endpoints
@api_router.get("/feeds/crypto/top", response_model=dict)
async def get_top_cryptos():
    """Get top cryptocurrencies"""
    cryptos = await crypto_feed.get_top_cryptos(limit=20)
    fear_greed = await crypto_feed.get_fear_greed_index()
    
    return {
        "fear_greed_index": fear_greed,
        "top_cryptos": [
            {
                "symbol": c.symbol,
                "name": c.name,
                "price": c.price_usd,
                "change_24h": c.change_24h,
                "market_cap": c.market_cap,
                "rank": c.rank
            }
            for c in cryptos
        ]
    }


@api_router.get("/feeds/crypto/{symbol}", response_model=dict)
async def get_crypto_price(symbol: str):
    """Get crypto price"""
    quote = await crypto_feed.get_price(symbol.upper())
    if quote:
        return {
            "symbol": quote.symbol,
            "name": quote.name,
            "price": quote.price_usd,
            "change_24h": quote.change_24h,
            "change_7d": quote.change_7d,
            "volume_24h": quote.volume_24h,
            "market_cap": quote.market_cap
        }
    return {"symbol": symbol, "error": "Not found"}


# Forex Endpoints
@api_router.get("/feeds/forex/summary", response_model=dict)
async def get_forex_summary():
    """Get forex market summary"""
    return await forex_feed.get_market_summary()


@api_router.get("/feeds/forex/{base}/{quote}", response_model=dict)
async def get_forex_rate(base: str, quote: str):
    """Get forex exchange rate"""
    rate = await forex_feed.get_rate(base.upper(), quote.upper())
    return {
        "pair": f"{base.upper()}/{quote.upper()}",
        "rate": rate
    }


# Finviz Endpoints
@api_router.get("/feeds/finviz/gainers", response_model=dict)
async def get_finviz_gainers():
    """Get top gainers from Finviz"""
    gainers = await finviz_feed.get_top_gainers()
    return {"gainers": gainers}


@api_router.get("/feeds/finviz/losers", response_model=dict)
async def get_finviz_losers():
    """Get top losers from Finviz"""
    losers = await finviz_feed.get_top_losers()
    return {"losers": losers}


@api_router.get("/feeds/finviz/oversold", response_model=dict)
async def get_finviz_oversold():
    """Get oversold stocks (potential buys)"""
    oversold = await finviz_feed.get_oversold()
    return {"oversold": oversold}


@api_router.get("/feeds/finviz/overbought", response_model=dict)
async def get_finviz_overbought():
    """Get overbought stocks (potential sells)"""
    overbought = await finviz_feed.get_overbought()
    return {"overbought": overbought}


@api_router.get("/feeds/finviz/unusual-volume", response_model=dict)
async def get_finviz_unusual_volume():
    """Get stocks with unusual volume"""
    unusual = await finviz_feed.get_unusual_volume()
    return {"unusual_volume": unusual}


@api_router.get("/feeds/finviz/{symbol}/news", response_model=dict)
async def get_finviz_news(symbol: str):
    """Get news for a symbol from Finviz"""
    news = await finviz_feed.get_stock_news(symbol.upper())
    return {
        "symbol": symbol.upper(),
        "news": [
            {"title": n.title, "link": n.link, "source": n.source, "time": n.time}
            for n in news
        ]
    }


# Twitter Endpoints
@api_router.get("/feeds/twitter/trading", response_model=dict)
async def get_twitter_trading_feed():
    """Get tweets from tracked trading accounts"""
    tweets = await twitter_feed.get_trading_feed()
    return {
        "tracked_accounts": twitter_feed.TRADING_ACCOUNTS,
        "tweets": [
            {
                "text": t.text,
                "author": t.author,
                "likes": t.likes,
                "retweets": t.retweets,
                "symbols": t.symbols_mentioned
            }
            for t in tweets[:20]
        ]
    }


@api_router.get("/feeds/twitter/{symbol}", response_model=dict)
async def get_twitter_symbol_sentiment(symbol: str):
    """Get Twitter sentiment for a symbol"""
    return await twitter_feed.get_symbol_sentiment(symbol.upper())


# News Endpoints  
@api_router.get("/feeds/news/market", response_model=dict)
async def get_market_news():
    """Get general market news"""
    articles = await news_feed.get_market_news(limit=20)
    return {
        "articles": [
            {
                "title": a.title,
                "source": a.source,
                "url": a.url,
                "published": a.published.isoformat(),
                "sentiment": a.sentiment
            }
            for a in articles
        ]
    }


@api_router.get("/feeds/news/{symbol}", response_model=dict)
async def get_symbol_news(symbol: str):
    """Get news for a specific symbol"""
    articles = await news_feed.get_symbol_news(symbol.upper())
    return {
        "symbol": symbol.upper(),
        "articles": [
            {
                "title": a.title,
                "source": a.source,
                "url": a.url,
                "sentiment": a.sentiment
            }
            for a in articles
        ]
    }


# ===== NEW API ENDPOINTS =====

# Signal Levels Endpoints
@api_router.get("/signals/levels/{symbol}", response_model=dict)
async def get_signal_levels(symbol: str):
    """Get trading signal levels for a symbol"""
    if state.data_manager:
        bars = state.data_manager.get_historical_bars(symbol.upper(), limit=200)
        if bars and len(bars) > 0:
            market_data = {
                'close': [b.close for b in bars],
                'high': [b.high for b in bars],
                'low': [b.low for b in bars],
                'volume': [b.volume for b in bars]
            }
            signal = signal_calculator.calculate_signal_levels(symbol.upper(), market_data)
            return signal.to_dict()
    return {"symbol": symbol, "error": "No data available"}


@api_router.get("/signals/best", response_model=dict)
async def get_best_signals():
    """Get best buy and sell signals across all symbols"""
    # Calculate signals for all tracked symbols
    for symbol in CONFIG.symbols.all_symbols:
        if state.data_manager:
            data = state.data_manager.get_data(symbol)
            if data is not None and len(data) > 0:
                market_data = {
                    'close': data['close'].tolist(),
                    'high': data['high'].tolist(),
                    'low': data['low'].tolist(),
                    'volume': data['volume'].tolist()
                }
                signal_calculator.calculate_signal_levels(symbol, market_data)
    
    return signal_calculator.get_best_signals()


@api_router.get("/signals/all", response_model=dict)
async def get_all_signals():
    """Get all signal levels"""
    return {"signals": signal_calculator.get_all_signals()}


# News Aggregator Endpoints
@api_router.get("/news/latest", response_model=dict)
async def get_latest_news(limit: int = 20):
    """Get latest aggregated news"""
    await news_aggregator.update_news()
    return {
        "news": news_aggregator.get_latest_news(limit),
        "sentiment_summary": news_aggregator.get_sentiment_summary()
    }


@api_router.get("/news/breaking", response_model=dict)
async def get_breaking_news():
    """Get breaking news only"""
    return {"breaking_news": news_aggregator.get_breaking_news()}


@api_router.get("/news/symbol/{symbol}", response_model=dict)
async def get_news_for_symbol(symbol: str, limit: int = 10):
    """Get news for specific symbol"""
    return {
        "symbol": symbol.upper(),
        "news": news_aggregator.get_news_by_symbol(symbol.upper(), limit)
    }


@api_router.get("/news/category/{category}", response_model=dict)
async def get_news_by_category(category: str, limit: int = 10):
    """Get news by category (macro, earnings, sector, etc.)"""
    return {
        "category": category,
        "news": news_aggregator.get_news_by_category(category, limit)
    }


# Execution Engine Endpoints
@api_router.post("/execution/order", response_model=dict)
async def execute_order(
    symbol: str,
    side: str,
    quantity: int,
    algorithm: str = "adaptive",
    limit_price: float = None,
    urgency: float = 0.5
):
    """Execute order using smart execution algorithms"""
    algo_map = {
        "market": ExecutionAlgorithm.MARKET,
        "vwap": ExecutionAlgorithm.VWAP,
        "twap": ExecutionAlgorithm.TWAP,
        "iceberg": ExecutionAlgorithm.ICEBERG,
        "adaptive": ExecutionAlgorithm.ADAPTIVE
    }
    
    algo = algo_map.get(algorithm.lower(), ExecutionAlgorithm.ADAPTIVE)
    
    report = await execution_engine.execute_order(
        symbol=symbol.upper(),
        side=side.upper(),
        quantity=quantity,
        algorithm=algo,
        limit_price=limit_price,
        urgency=urgency
    )
    
    return report.to_dict()


@api_router.get("/execution/stats", response_model=dict)
async def get_execution_stats():
    """Get execution performance statistics"""
    return execution_engine.get_execution_stats()


# Learning Engine Endpoints
@api_router.get("/learning/weights", response_model=dict)
async def get_strategy_weights():
    """Get current strategy weights from learning engine"""
    return learning_engine.get_strategy_weights()


@api_router.get("/learning/performance", response_model=dict)
async def get_learning_performance():
    """Get strategy performance summary"""
    return learning_engine.get_performance_summary()


@api_router.post("/learning/cycle", response_model=dict)
async def run_learning_cycle(cycle_type: str = "daily"):
    """Run a learning cycle to adjust strategy weights"""
    cycle = await learning_engine.run_learning_cycle(cycle_type)
    return cycle.to_dict()


@api_router.get("/learning/history", response_model=dict)
async def get_learning_history(limit: int = 10):
    """Get learning cycle history"""
    return {"cycles": learning_engine.get_learning_history(limit)}


# Strategy Registry Endpoints
@api_router.get("/strategy-registry/all", response_model=dict)
async def get_strategy_registry():
    """Get all registered strategies"""
    return {
        "strategies": list(STRATEGY_REGISTRY.keys()),
        "total_count": len(STRATEGY_REGISTRY),
        "categories": {
            "trend": ["trend_following", "momentum", "breakout", "macd_crossover"],
            "mean_reversion": ["mean_reversion", "rsi_divergence", "bollinger_squeeze", "vwap_reversion"],
            "statistical": ["stat_arb", "pairs_trading"],
            "intraday": ["orb", "gap_trading", "volume_profile"],
            "macro": ["sector_rotation"]
        }
    }


# Dashboard Data - Enhanced
@api_router.get("/dashboard/full", response_model=dict)
async def get_full_dashboard():
    """Get complete dashboard data with all components"""
    # Gather all data
    dashboard_data = {}
    
    # Basic dashboard data
    if state.connector and state.data_manager:
        account = state.connector.get_account()
        positions = state.connector.get_positions()
        
        dashboard_data["account"] = {
            "equity": account.equity,
            "cash": account.cash,
            "buying_power": account.buying_power,
            "daily_pnl": account.daily_pnl,
            "unrealized_pnl": account.unrealized_pnl
        }
        
        dashboard_data["positions"] = [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_cost": p.avg_cost,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_pct": (p.current_price - p.avg_cost) / p.avg_cost * 100 if p.avg_cost > 0 else 0
            }
            for p in positions
        ]
    
    # Regime and signals
    if state.regime_detector:
        regime_state = state.regime_detector.detect_regime({})
        dashboard_data["regime"] = regime_state.to_dict()
    
    # Best signals
    dashboard_data["best_signals"] = signal_calculator.get_best_signals()
    
    # News summary
    await news_aggregator.update_news()
    dashboard_data["news"] = {
        "latest": news_aggregator.get_latest_news(5),
        "sentiment": news_aggregator.get_sentiment_summary()
    }
    
    # Strategy weights
    dashboard_data["strategy_weights"] = learning_engine.get_strategy_weights()
    
    # Execution stats
    dashboard_data["execution_stats"] = execution_engine.get_execution_stats()
    
    # System status
    dashboard_data["system"] = {
        "mode": CONFIG.mode.value,
        "uptime_seconds": (datetime.now(timezone.utc) - state.start_time).total_seconds(),
        "kill_switch": state.kill_switch_active,
        "strategies_active": len(STRATEGY_REGISTRY),
        "symbols_tracked": CONFIG.symbols.all_symbols
    }
    
    return dashboard_data

# Include router - MUST be after all endpoint definitions
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
