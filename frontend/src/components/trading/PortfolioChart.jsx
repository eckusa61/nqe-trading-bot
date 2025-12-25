import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export const PortfolioChart = ({ data = [], height = 300 }) => {
  // Transform data for the chart
  const chartData = data.map(item => ({
    timestamp: new Date(item.timestamp).toLocaleDateString(),
    value: item.portfolio_value,
    pnl: item.total_pnl
  }));

  // If no data, show placeholder
  if (chartData.length === 0) {
    // Generate sample data for visualization
    const sampleData = [];
    const startValue = 100000;
    for (let i = 0; i < 30; i++) {
      const change = (Math.random() - 0.48) * 2000;
      const value = startValue + change * (i / 10);
      sampleData.push({
        timestamp: new Date(Date.now() - (30 - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
        value: value,
        pnl: value - startValue
      });
    }
    chartData.push(...sampleData);
  }

  const minValue = Math.min(...chartData.map(d => d.value)) * 0.995;
  const maxValue = Math.max(...chartData.map(d => d.value)) * 1.005;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const value = payload[0].value;
      const pnl = payload[0].payload.pnl;
      const isPositive = pnl >= 0;

      return (
        <div className="bg-card border border-border p-3 rounded-sm shadow-lg">
          <p className="text-xs text-muted-foreground mb-1">{label}</p>
          <p className="font-mono text-lg font-semibold text-foreground">
            ${value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
          <p className={`font-mono text-sm ${isPositive ? 'profit' : 'loss'}`}>
            {isPositive ? '+' : ''}${pnl?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </div>
      );
    }
    return null;
  };

  const latestPnL = chartData[chartData.length - 1]?.pnl || 0;
  const isPositive = latestPnL >= 0;
  const strokeColor = isPositive ? 'hsl(160, 84%, 39%)' : 'hsl(350, 89%, 60%)';
  const fillColor = isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)';

  return (
    <div className="trading-card rounded-sm overflow-hidden" data-testid="portfolio-chart">
      <div className="p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Portfolio Value
        </h3>
      </div>
      <div style={{ height: height }} className="p-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={strokeColor} stopOpacity={0.3} />
                <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="hsl(240, 3.7%, 15.9%)"
              vertical={false}
            />
            <XAxis 
              dataKey="timestamp"
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'hsl(240, 5%, 64.9%)', fontSize: 10 }}
              tickMargin={10}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[minValue, maxValue]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'hsl(240, 5%, 64.9%)', fontSize: 10 }}
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
              width={50}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={strokeColor}
              strokeWidth={2}
              fill="url(#portfolioGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default PortfolioChart;
