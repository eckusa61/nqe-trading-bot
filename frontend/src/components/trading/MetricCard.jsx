import { DollarSign, TrendingUp, TrendingDown, Activity, Percent, BarChart3 } from 'lucide-react';

export const MetricCard = ({ 
  title, 
  value, 
  change, 
  changeLabel,
  icon: Icon = DollarSign,
  prefix = '',
  suffix = '',
  format = 'number'
}) => {
  const isPositive = change >= 0;
  const ChangeIcon = isPositive ? TrendingUp : TrendingDown;

  const formatValue = (val) => {
    if (format === 'currency') {
      return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    if (format === 'percent') {
      return `${val.toFixed(2)}%`;
    }
    return val.toLocaleString();
  };

  return (
    <div className="trading-card p-4 rounded-sm" data-testid={`metric-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {title}
          </p>
          <p className="text-2xl font-bold font-mono mt-1 text-foreground tracking-tight">
            {prefix}{formatValue(value)}{suffix}
          </p>
        </div>
        <div className={`p-2 rounded-sm ${isPositive ? 'bg-[hsl(var(--profit)/0.1)]' : 'bg-[hsl(var(--loss)/0.1)]'}`}>
          <Icon className={`w-5 h-5 ${isPositive ? 'profit' : 'loss'}`} />
        </div>
      </div>
      {change !== undefined && (
        <div className={`flex items-center gap-1 mt-2 ${isPositive ? 'profit' : 'loss'}`}>
          <ChangeIcon className="w-3 h-3" />
          <span className="text-sm font-mono">
            {isPositive ? '+' : ''}{change.toFixed(2)}%
          </span>
          {changeLabel && (
            <span className="text-xs text-muted-foreground ml-1">
              {changeLabel}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export const MetricsGrid = ({ account }) => {
  if (!account) return null;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="metrics-grid">
      <MetricCard
        title="Portfolio Value"
        value={account.portfolio_value || 0}
        change={account.total_pnl_pct || 0}
        changeLabel="total"
        icon={DollarSign}
        format="currency"
      />
      <MetricCard
        title="Daily P&L"
        value={account.daily_pnl || 0}
        change={account.daily_pnl_pct || 0}
        changeLabel="today"
        icon={account.daily_pnl >= 0 ? TrendingUp : TrendingDown}
        format="currency"
      />
      <MetricCard
        title="Total P&L"
        value={account.total_pnl || 0}
        change={account.total_pnl_pct || 0}
        icon={Activity}
        format="currency"
      />
      <MetricCard
        title="Cash Available"
        value={account.cash || 0}
        icon={BarChart3}
        format="currency"
      />
    </div>
  );
};

export default MetricCard;
