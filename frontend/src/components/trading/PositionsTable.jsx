import { TrendingUp, TrendingDown } from 'lucide-react';

export const PositionsTable = ({ positions = [] }) => {
  if (positions.length === 0) {
    return (
      <div className="trading-card p-4 rounded-sm" data-testid="positions-table">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          Open Positions
        </h3>
        <div className="text-center py-8 text-muted-foreground text-sm">
          No open positions
        </div>
      </div>
    );
  }

  return (
    <div className="trading-card rounded-sm overflow-hidden" data-testid="positions-table">
      <div className="p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Open Positions
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full data-table">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 px-4">Symbol</th>
              <th className="text-right py-2 px-4">Qty</th>
              <th className="text-right py-2 px-4">Avg Cost</th>
              <th className="text-right py-2 px-4">Current</th>
              <th className="text-right py-2 px-4">Value</th>
              <th className="text-right py-2 px-4">P&L</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos) => (
              <tr key={pos.symbol} className="border-b border-border/50">
                <td className="py-3 px-4">
                  <span className="font-semibold text-foreground">{pos.symbol}</span>
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  <span className={pos.quantity > 0 ? 'profit' : 'loss'}>
                    {pos.quantity > 0 ? '+' : ''}{pos.quantity}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-mono text-muted-foreground">
                  ${pos.avg_cost?.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  ${pos.current_price?.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  ${pos.market_value?.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className={`flex items-center justify-end gap-1 ${
                    pos.unrealized_pnl >= 0 ? 'profit' : 'loss'
                  }`}>
                    {pos.unrealized_pnl >= 0 ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    <span className="font-mono">
                      {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl?.toFixed(2)}
                    </span>
                    <span className="text-xs opacity-70">
                      ({pos.unrealized_pnl_pct?.toFixed(1)}%)
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PositionsTable;
