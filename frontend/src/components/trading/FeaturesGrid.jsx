import { TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';

export const FeaturesGrid = ({ features = [] }) => {
  const getIndicatorColor = (value, type) => {
    if (type === 'rsi') {
      if (value > 70) return 'loss';
      if (value < 30) return 'profit';
      return 'text-muted-foreground';
    }
    if (type === 'return') {
      return value >= 0 ? 'profit' : 'loss';
    }
    return 'text-foreground';
  };

  const getIcon = (value) => {
    if (value > 0.5) return <TrendingUp className="w-3 h-3" />;
    if (value < -0.5) return <TrendingDown className="w-3 h-3" />;
    return <Minus className="w-3 h-3" />;
  };

  if (features.length === 0) {
    return (
      <div className="trading-card p-4 rounded-sm" data-testid="features-grid">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          Technical Indicators
        </h3>
        <div className="text-center py-8 text-muted-foreground text-sm">
          Loading features...
        </div>
      </div>
    );
  }

  return (
    <div className="trading-card rounded-sm overflow-hidden" data-testid="features-grid">
      <div className="p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Technical Indicators
        </h3>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {features.map((feature) => (
          <div 
            key={feature.symbol}
            className="p-4 border-b border-border/30 hover:bg-muted/30 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-foreground">{feature.symbol}</span>
              <span className="font-mono text-lg text-foreground">${feature.price}</span>
            </div>
            <div className="grid grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-muted-foreground">1D</span>
                <div className={`font-mono ${getIndicatorColor(feature.return_1d, 'return')}`}>
                  {feature.return_1d >= 0 ? '+' : ''}{feature.return_1d}%
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">5D</span>
                <div className={`font-mono ${getIndicatorColor(feature.return_5d, 'return')}`}>
                  {feature.return_5d >= 0 ? '+' : ''}{feature.return_5d}%
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">20D</span>
                <div className={`font-mono ${getIndicatorColor(feature.return_20d, 'return')}`}>
                  {feature.return_20d >= 0 ? '+' : ''}{feature.return_20d}%
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">RSI</span>
                <div className={`font-mono ${getIndicatorColor(feature.rsi_14, 'rsi')}`}>
                  {feature.rsi_14}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Vol</span>
                <div className="font-mono text-foreground">
                  {feature.volatility_annualized}%
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">ADX</span>
                <div className="font-mono text-foreground">
                  {feature.adx_14}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FeaturesGrid;
