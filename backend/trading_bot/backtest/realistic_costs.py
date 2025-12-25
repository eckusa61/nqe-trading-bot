"""
Realistic Cost Model
Simulates real-world trading costs including slippage, commission, and market impact
"""
from dataclasses import dataclass
from typing import Optional
import random
import math

from trading_bot.config import CONFIG


@dataclass
class ExecutionResult:
    """Result of simulated order execution"""
    symbol: str
    side: str
    requested_qty: int
    filled_qty: int
    avg_fill_price: float
    slippage: float
    commission: float
    market_impact: float
    total_cost: float
    fill_rate: float
    latency_ms: int


class RealisticCostModel:
    """
    Simulates realistic trading costs
    
    Components:
    1. Commission: $0.005/share (min $1)
    2. Slippage: Base + volatility + size impact
    3. Market impact: For large orders
    4. Latency: Signal-to-fill delay
    5. Partial fills: Based on liquidity
    """
    
    def __init__(
        self,
        commission_per_share: float = None,
        min_commission: float = None,
        base_slippage: float = None,
        volatility_slippage_mult: float = None,
        size_impact_threshold: int = None,
        size_impact_rate: float = None,
        latency_ms: int = None,
        partial_fill_prob: float = None,
        avg_fill_rate: float = None
    ):
        # Use config defaults if not specified
        self.commission_per_share = commission_per_share or CONFIG.backtest.commission_per_share
        self.min_commission = min_commission or CONFIG.backtest.min_commission
        self.base_slippage = base_slippage or CONFIG.backtest.base_slippage
        self.volatility_slippage_mult = volatility_slippage_mult or CONFIG.backtest.volatility_slippage_multiplier
        self.size_impact_threshold = size_impact_threshold or CONFIG.backtest.size_impact_threshold
        self.size_impact_rate = size_impact_rate or CONFIG.backtest.size_impact_rate
        self.latency_ms = latency_ms or CONFIG.backtest.signal_to_fill_delay_ms
        self.partial_fill_prob = partial_fill_prob or CONFIG.backtest.partial_fill_probability
        self.avg_fill_rate = avg_fill_rate or CONFIG.backtest.avg_fill_rate
    
    def calculate_slippage(
        self,
        price: float,
        quantity: int,
        side: str,
        volatility: float,
        liquidity_tier: int = 2
    ) -> float:
        """
        Calculate realistic slippage
        
        Args:
            price: Current market price
            quantity: Order quantity
            side: "BUY" or "SELL"
            volatility: Annualized volatility (e.g., 0.25 for 25%)
            liquidity_tier: 1=ultra liquid, 2=liquid, 3=less liquid
        
        Returns:
            Slippage as absolute price impact
        """
        # Base slippage
        base = self.base_slippage
        
        # Volatility component (higher vol = more slippage)
        vol_component = volatility * self.volatility_slippage_mult / 100
        
        # Size impact (larger orders have more impact)
        excess_shares = max(0, quantity - self.size_impact_threshold)
        size_impact = (excess_shares / 1000) * self.size_impact_rate
        
        # Liquidity tier adjustment
        tier_mult = {1: 0.7, 2: 1.0, 3: 1.5}
        tier_adjustment = tier_mult.get(liquidity_tier, 1.0)
        
        # Random component (market microstructure noise)
        random_factor = random.uniform(0.8, 1.2)
        
        # Total slippage percentage
        total_slippage_pct = (base + vol_component + size_impact) * tier_adjustment * random_factor
        
        # Convert to price impact
        slippage = price * total_slippage_pct
        
        # Slippage is always adverse (buy higher, sell lower)
        return slippage
    
    def calculate_commission(self, quantity: int) -> float:
        """Calculate commission for trade"""
        commission = quantity * self.commission_per_share
        return max(self.min_commission, commission)
    
    def calculate_market_impact(
        self,
        price: float,
        quantity: int,
        avg_daily_volume: int,
        side: str
    ) -> float:
        """
        Calculate market impact for large orders
        Uses square-root model: Impact ∝ sqrt(Q/ADV)
        """
        if avg_daily_volume == 0:
            return 0
        
        participation_rate = quantity / avg_daily_volume
        
        if participation_rate < 0.01:  # Less than 1% of ADV
            return 0
        
        # Square root market impact model
        # Impact = price * sigma * sqrt(participation_rate)
        sigma = 0.02  # Assume 2% daily vol
        impact = price * sigma * math.sqrt(participation_rate)
        
        return impact
    
    def simulate_partial_fill(self, quantity: int, liquidity_tier: int = 2) -> int:
        """
        Simulate partial fills based on liquidity
        """
        # Tier 1: Almost always full fill
        # Tier 2: Occasional partial fills
        # Tier 3: More frequent partial fills
        
        tier_prob = {1: 0.05, 2: self.partial_fill_prob, 3: 0.25}
        probability = tier_prob.get(liquidity_tier, self.partial_fill_prob)
        
        if random.random() < probability:
            # Partial fill
            fill_rate = random.uniform(0.5, 0.95)
            return int(quantity * fill_rate)
        
        return quantity
    
    def simulate_latency(self) -> int:
        """Simulate signal-to-fill latency with random variation"""
        # Add random variation ±50ms
        variation = random.randint(-50, 50)
        return max(50, self.latency_ms + variation)
    
    def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        volatility: float = 0.25,
        avg_daily_volume: int = 1000000,
        liquidity_tier: int = 2
    ) -> ExecutionResult:
        """
        Simulate full order execution with all costs
        
        Returns:
            ExecutionResult with all cost components
        """
        # Simulate latency
        latency = self.simulate_latency()
        
        # Simulate partial fill
        filled_qty = self.simulate_partial_fill(quantity, liquidity_tier)
        
        if filled_qty == 0:
            return ExecutionResult(
                symbol=symbol,
                side=side,
                requested_qty=quantity,
                filled_qty=0,
                avg_fill_price=0,
                slippage=0,
                commission=0,
                market_impact=0,
                total_cost=0,
                fill_rate=0,
                latency_ms=latency
            )
        
        # Calculate slippage
        slippage = self.calculate_slippage(price, filled_qty, side, volatility, liquidity_tier)
        
        # Calculate market impact
        market_impact = self.calculate_market_impact(price, filled_qty, avg_daily_volume, side)
        
        # Calculate commission
        commission = self.calculate_commission(filled_qty)
        
        # Calculate fill price
        if side.upper() == "BUY":
            avg_fill_price = price + slippage + market_impact
        else:
            avg_fill_price = price - slippage - market_impact
        
        # Total cost (always negative = cost to trader)
        total_cost = commission + (slippage + market_impact) * filled_qty
        
        return ExecutionResult(
            symbol=symbol,
            side=side,
            requested_qty=quantity,
            filled_qty=filled_qty,
            avg_fill_price=round(avg_fill_price, 4),
            slippage=round(slippage, 4),
            commission=round(commission, 2),
            market_impact=round(market_impact, 4),
            total_cost=round(total_cost, 2),
            fill_rate=filled_qty / quantity,
            latency_ms=latency
        )
    
    def stress_test_costs(self, multiplier: float = 2.0):
        """
        Return a cost model with 2x costs for stress testing
        """
        return RealisticCostModel(
            commission_per_share=self.commission_per_share * multiplier,
            min_commission=self.min_commission * multiplier,
            base_slippage=self.base_slippage * multiplier,
            volatility_slippage_mult=self.volatility_slippage_mult * multiplier,
            size_impact_threshold=int(self.size_impact_threshold / multiplier),
            size_impact_rate=self.size_impact_rate * multiplier,
            latency_ms=int(self.latency_ms * multiplier),
            partial_fill_prob=min(0.5, self.partial_fill_prob * multiplier),
            avg_fill_rate=max(0.5, self.avg_fill_rate / multiplier)
        )
