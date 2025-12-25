import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export const TradesTable = ({ trades = [] }) => {
  if (trades.length === 0) {
    return (
      <div className="trading-card p-4 rounded-sm" data-testid="trades-table">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          Recent Trades
        </h3>
        <div className="text-center py-8 text-muted-foreground text-sm">
          No trades yet
        </div>
      </div>
    );
  }

  return (
    <div className="trading-card rounded-sm overflow-hidden" data-testid="trades-table">
      <div className="p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Recent Trades
        </h3>
      </div>
      <div className="max-h-80 overflow-y-auto">
        {trades.map((trade, idx) => (
          <div 
            key={`${trade.order_id}-${idx}`}
            className="flex items-center justify-between p-3 border-b border-border/30 hover:bg-muted/30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className={`p-1.5 rounded-sm ${
                trade.side === 'BUY' ? 'bg-[hsl(var(--profit)/0.15)]' : 'bg-[hsl(var(--loss)/0.15)]'
              }`}>
                {trade.side === 'BUY' ? (
                  <ArrowUpRight className="w-4 h-4 profit" />
                ) : (
                  <ArrowDownRight className="w-4 h-4 loss" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">{trade.symbol}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    trade.side === 'BUY' ? 'bg-[hsl(var(--profit)/0.2)] profit' : 'bg-[hsl(var(--loss)/0.2)] loss'
                  }`}>
                    {trade.side}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground font-mono">
                  {trade.filled_qty} @ ${trade.avg_price?.toFixed(2)}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono text-sm text-foreground">
                ${(trade.filled_qty * trade.avg_price).toFixed(2)}
              </div>
              <div className="text-xs text-muted-foreground">
                {trade.timestamp ? formatDistanceToNow(new Date(trade.timestamp), { addSuffix: true }) : 'Just now'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TradesTable;
