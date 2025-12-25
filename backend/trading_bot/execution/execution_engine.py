"""
Execution Engine - Smart Order Execution
VWAP, TWAP, and Smart Order Router algorithms
"""
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class ExecutionAlgorithm(Enum):
    MARKET = "market"
    LIMIT = "limit"
    VWAP = "vwap"
    TWAP = "twap"
    ICEBERG = "iceberg"
    ADAPTIVE = "adaptive"


class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class ExecutionOrder:
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: int
    algorithm: ExecutionAlgorithm
    limit_price: Optional[float] = None
    urgency: float = 0.5  # 0 = passive, 1 = aggressive
    duration_minutes: int = 30
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    child_orders: List[Dict] = field(default_factory=list)


@dataclass
class ExecutionReport:
    order_id: str
    symbol: str
    side: str
    requested_qty: int
    filled_qty: int
    avg_price: float
    vwap_benchmark: float
    slippage_bps: float
    execution_time_seconds: float
    algorithm_used: str
    child_order_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "requested_qty": self.requested_qty,
            "filled_qty": self.filled_qty,
            "avg_price": self.avg_price,
            "vwap_benchmark": self.vwap_benchmark,
            "slippage_bps": self.slippage_bps,
            "execution_time_seconds": self.execution_time_seconds,
            "algorithm_used": self.algorithm_used,
            "child_order_count": self.child_order_count,
            "timestamp": self.timestamp.isoformat()
        }


class ExecutionEngine:
    """
    Smart Execution Engine
    
    Features:
    - VWAP (Volume Weighted Average Price)
    - TWAP (Time Weighted Average Price)
    - Iceberg Orders
    - Adaptive Execution
    - Slippage Minimization
    """
    
    def __init__(self, order_executor: Optional[Callable] = None):
        self.order_executor = order_executor
        self.active_orders: Dict[str, ExecutionOrder] = {}
        self.execution_history: List[ExecutionReport] = []
        self.order_counter = 0
        
        # Execution parameters
        self.min_order_size = 1
        self.max_participation_rate = 0.1  # 10% of volume
        self.price_tolerance_bps = 10  # 10 basis points
        
        logger.info("Execution Engine initialized")
    
    def generate_order_id(self) -> str:
        self.order_counter += 1
        return f"EXE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self.order_counter:04d}"
    
    async def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        algorithm: ExecutionAlgorithm = ExecutionAlgorithm.ADAPTIVE,
        limit_price: Optional[float] = None,
        urgency: float = 0.5,
        duration_minutes: int = 30
    ) -> ExecutionReport:
        """
        Execute order using specified algorithm
        """
        order = ExecutionOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            algorithm=algorithm,
            limit_price=limit_price,
            urgency=urgency,
            duration_minutes=duration_minutes,
            order_id=self.generate_order_id()
        )
        
        self.active_orders[order.order_id] = order
        logger.info(f"Starting execution: {order.order_id} - {side} {quantity} {symbol} via {algorithm.value}")
        
        start_time = datetime.now(timezone.utc)
        
        try:
            if algorithm == ExecutionAlgorithm.VWAP:
                await self._execute_vwap(order)
            elif algorithm == ExecutionAlgorithm.TWAP:
                await self._execute_twap(order)
            elif algorithm == ExecutionAlgorithm.ICEBERG:
                await self._execute_iceberg(order)
            elif algorithm == ExecutionAlgorithm.ADAPTIVE:
                await self._execute_adaptive(order)
            else:
                await self._execute_market(order)
            
            order.status = OrderStatus.FILLED if order.filled_quantity >= quantity else OrderStatus.PARTIAL
            
        except Exception as e:
            logger.error(f"Execution error for {order.order_id}: {e}")
            order.status = OrderStatus.REJECTED
        
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Calculate slippage
        vwap_benchmark = order.avg_fill_price  # Simplified
        slippage_bps = 0.0
        if limit_price and order.avg_fill_price > 0:
            slippage_bps = abs(order.avg_fill_price - limit_price) / limit_price * 10000
        
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=symbol,
            side=side,
            requested_qty=quantity,
            filled_qty=order.filled_quantity,
            avg_price=order.avg_fill_price,
            vwap_benchmark=vwap_benchmark,
            slippage_bps=slippage_bps,
            execution_time_seconds=execution_time,
            algorithm_used=algorithm.value,
            child_order_count=len(order.child_orders)
        )
        
        self.execution_history.append(report)
        del self.active_orders[order.order_id]
        
        logger.info(f"Execution complete: {order.order_id} - Filled {order.filled_quantity}/{quantity} @ {order.avg_fill_price:.2f}")
        
        return report
    
    async def _execute_vwap(self, order: ExecutionOrder):
        """
        VWAP Execution Algorithm
        Splits order based on historical volume profile
        """
        total_qty = order.quantity
        duration = order.duration_minutes
        
        # Split into time slices (5-minute buckets)
        num_slices = max(duration // 5, 1)
        
        # Volume distribution (simplified - normally from historical data)
        volume_weights = self._get_volume_profile(num_slices)
        
        for i, weight in enumerate(volume_weights):
            if order.filled_quantity >= total_qty:
                break
            
            slice_qty = max(int(total_qty * weight), self.min_order_size)
            remaining = total_qty - order.filled_quantity
            slice_qty = min(slice_qty, remaining)
            
            if slice_qty > 0:
                child_order = await self._send_child_order(order, slice_qty)
                order.child_orders.append(child_order)
                
                # Update fill
                order.filled_quantity += child_order.get('filled_qty', slice_qty)
                if order.avg_fill_price == 0:
                    order.avg_fill_price = child_order.get('price', 0)
                else:
                    # Weighted average
                    total_value = order.avg_fill_price * (order.filled_quantity - slice_qty) + \
                                  child_order.get('price', order.avg_fill_price) * slice_qty
                    order.avg_fill_price = total_value / order.filled_quantity
            
            # Wait between slices
            if i < len(volume_weights) - 1:
                await asyncio.sleep(min(duration * 60 / num_slices, 60))
    
    async def _execute_twap(self, order: ExecutionOrder):
        """
        TWAP Execution Algorithm
        Equal-sized orders over time
        """
        total_qty = order.quantity
        duration = order.duration_minutes
        
        # Split into equal time slices
        num_slices = max(duration // 5, 1)
        slice_qty = max(total_qty // num_slices, self.min_order_size)
        
        for i in range(num_slices):
            if order.filled_quantity >= total_qty:
                break
            
            remaining = total_qty - order.filled_quantity
            qty = min(slice_qty, remaining)
            
            if qty > 0:
                child_order = await self._send_child_order(order, qty)
                order.child_orders.append(child_order)
                
                order.filled_quantity += child_order.get('filled_qty', qty)
                if order.avg_fill_price == 0:
                    order.avg_fill_price = child_order.get('price', 0)
                else:
                    total_value = order.avg_fill_price * (order.filled_quantity - qty) + \
                                  child_order.get('price', order.avg_fill_price) * qty
                    order.avg_fill_price = total_value / order.filled_quantity
            
            # Equal intervals
            if i < num_slices - 1:
                await asyncio.sleep(duration * 60 / num_slices)
    
    async def _execute_iceberg(self, order: ExecutionOrder):
        """
        Iceberg Order - Shows only portion of total size
        """
        total_qty = order.quantity
        display_qty = max(total_qty // 10, self.min_order_size)  # Show 10%
        
        while order.filled_quantity < total_qty:
            remaining = total_qty - order.filled_quantity
            slice_qty = min(display_qty, remaining)
            
            child_order = await self._send_child_order(order, slice_qty)
            order.child_orders.append(child_order)
            
            order.filled_quantity += child_order.get('filled_qty', slice_qty)
            if order.avg_fill_price == 0:
                order.avg_fill_price = child_order.get('price', 0)
            else:
                total_value = order.avg_fill_price * (order.filled_quantity - slice_qty) + \
                              child_order.get('price', order.avg_fill_price) * slice_qty
                order.avg_fill_price = total_value / order.filled_quantity
            
            # Small random delay
            await asyncio.sleep(np.random.uniform(1, 5))
    
    async def _execute_adaptive(self, order: ExecutionOrder):
        """
        Adaptive Execution - Adjusts based on market conditions
        """
        # Use urgency to determine approach
        if order.urgency > 0.7:
            # High urgency - TWAP with short duration
            order.duration_minutes = min(order.duration_minutes, 10)
            await self._execute_twap(order)
        elif order.urgency < 0.3:
            # Low urgency - VWAP with full duration
            await self._execute_vwap(order)
        else:
            # Medium urgency - Iceberg
            await self._execute_iceberg(order)
    
    async def _execute_market(self, order: ExecutionOrder):
        """
        Simple market order execution
        """
        child_order = await self._send_child_order(order, order.quantity)
        order.child_orders.append(child_order)
        order.filled_quantity = child_order.get('filled_qty', order.quantity)
        order.avg_fill_price = child_order.get('price', 0)
    
    async def _send_child_order(self, parent: ExecutionOrder, quantity: int) -> Dict:
        """
        Send individual child order to broker
        """
        if self.order_executor:
            result = await self.order_executor(
                symbol=parent.symbol,
                side=parent.side,
                quantity=quantity,
                limit_price=parent.limit_price
            )
            return result
        
        # Simulated fill
        simulated_price = parent.limit_price or 100.0
        slippage = np.random.uniform(-0.001, 0.001) * simulated_price
        fill_price = simulated_price + (slippage if parent.side == 'BUY' else -slippage)
        
        return {
            'filled_qty': quantity,
            'price': fill_price,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _get_volume_profile(self, num_slices: int) -> List[float]:
        """
        Get intraday volume profile (U-shaped for stocks)
        """
        # Typical U-shaped volume distribution
        x = np.linspace(0, np.pi, num_slices)
        weights = np.cos(x - np.pi/2) + 1.5
        weights = weights / np.sum(weights)
        return weights.tolist()
    
    def get_execution_stats(self) -> Dict:
        """Get execution performance statistics"""
        if not self.execution_history:
            return {"message": "No executions yet"}
        
        total_orders = len(self.execution_history)
        avg_slippage = np.mean([r.slippage_bps for r in self.execution_history])
        avg_fill_rate = np.mean([r.filled_qty / r.requested_qty * 100 for r in self.execution_history])
        avg_execution_time = np.mean([r.execution_time_seconds for r in self.execution_history])
        
        by_algorithm = {}
        for report in self.execution_history:
            algo = report.algorithm_used
            if algo not in by_algorithm:
                by_algorithm[algo] = {'count': 0, 'avg_slippage': []}
            by_algorithm[algo]['count'] += 1
            by_algorithm[algo]['avg_slippage'].append(report.slippage_bps)
        
        for algo in by_algorithm:
            by_algorithm[algo]['avg_slippage'] = np.mean(by_algorithm[algo]['avg_slippage'])
        
        return {
            "total_orders": total_orders,
            "avg_slippage_bps": round(avg_slippage, 2),
            "avg_fill_rate_pct": round(avg_fill_rate, 2),
            "avg_execution_time_sec": round(avg_execution_time, 2),
            "by_algorithm": by_algorithm,
            "recent_executions": [r.to_dict() for r in self.execution_history[-10:]]
        }
