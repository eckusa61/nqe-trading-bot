import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export const PnLTicker = ({ marketData = [] }) => {
  const [tickerData, setTickerData] = useState([]);

  useEffect(() => {
    if (marketData.length > 0) {
      // Duplicate for seamless loop
      setTickerData([...marketData, ...marketData]);
    }
  }, [marketData]);

  const getPriceChange = (item) => {
    const change = item.last - item.open;
    const changePct = (change / item.open) * 100;
    return { change, changePct };
  };

  const getIcon = (changePct) => {
    if (changePct > 0.1) return <TrendingUp className="w-3 h-3" />;
    if (changePct < -0.1) return <TrendingDown className="w-3 h-3" />;
    return <Minus className="w-3 h-3" />;
  };

  if (tickerData.length === 0) {
    return (
      <div className="h-8 bg-card border-b border-border flex items-center px-4">
        <span className="text-muted-foreground text-sm">Loading market data...</span>
      </div>
    );
  }

  return (
    <div 
      className="h-8 bg-card border-b border-border overflow-hidden"
      data-testid="pnl-ticker"
    >
      <div className="ticker-scroll flex items-center h-full whitespace-nowrap">
        {tickerData.map((item, idx) => {
          const { change, changePct } = getPriceChange(item);
          const isPositive = changePct >= 0;
          
          return (
            <div 
              key={`${item.symbol}-${idx}`}
              className="flex items-center gap-2 px-4 border-r border-border/30"
            >
              <span className="font-mono text-sm font-medium text-foreground">
                {item.symbol}
              </span>
              <span className="font-mono text-sm text-muted-foreground">
                ${item.last?.toFixed(2)}
              </span>
              <span 
                className={`flex items-center gap-1 font-mono text-xs ${
                  isPositive ? 'profit' : 'loss'
                }`}
              >
                {getIcon(changePct)}
                {isPositive ? '+' : ''}{changePct.toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PnLTicker;
