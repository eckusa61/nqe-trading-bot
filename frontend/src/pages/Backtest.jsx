import { useState, useEffect, useCallback } from 'react';
import { Activity, Play, TrendingUp, TrendingDown, BarChart3, ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import axios from 'axios';
import { Link } from 'react-router-dom';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Backtest() {
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState(['Momentum']);
  const [symbols, setSymbols] = useState(['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'META']);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/strategies`);
      setStrategies(res.data);
    } catch (err) {
      console.error('Error fetching strategies:', err);
    }
  };

  const runBacktest = async () => {
    setLoading(true);
    setResults(null);
    
    try {
      const res = await axios.post(`${API_URL}/api/backtest`, {
        symbols: symbols,
        start_date: '',
        end_date: '',
        initial_capital: initialCapital,
        strategies: selectedStrategies,
        leverage: 1.0
      });
      setResults(res.data.results);
    } catch (err) {
      console.error('Error running backtest:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleStrategy = (name) => {
    setSelectedStrategies(prev => 
      prev.includes(name) 
        ? prev.filter(s => s !== name)
        : [...prev, name]
    );
  };

  const MetricBox = ({ label, value, suffix = '', positive }) => (
    <div className="trading-card p-3 rounded-sm">
      <div className="text-xs text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className={`text-xl font-mono font-bold mt-1 ${
        positive === undefined ? 'text-foreground' :
        positive ? 'profit' : 'loss'
      }`}>
        {value}{suffix}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background" data-testid="backtest-page">
      {/* Header */}
      <header className="glass-header sticky top-0 z-50 px-4 md:px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-primary" />
              <h1 className="text-xl font-bold tracking-tight text-foreground">
                Backtest Engine
              </h1>
            </div>
          </div>
        </div>
      </header>

      <main className="p-4 md:p-6 space-y-6">
        {/* Configuration Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Strategies */}
          <div className="trading-card p-4 rounded-sm">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
              Strategies
            </h3>
            <div className="space-y-3">
              {strategies.map(strategy => (
                <div key={strategy.name} className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-foreground">{strategy.name}</div>
                    <div className="text-xs text-muted-foreground">{strategy.description}</div>
                  </div>
                  <Switch
                    checked={selectedStrategies.includes(strategy.name)}
                    onCheckedChange={() => toggleStrategy(strategy.name)}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Symbols */}
          <div className="trading-card p-4 rounded-sm">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
              Symbols
            </h3>
            <div className="flex flex-wrap gap-2">
              {['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'META'].map(sym => (
                <button
                  key={sym}
                  onClick={() => setSymbols(prev => 
                    prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]
                  )}
                  className={`px-3 py-1.5 rounded-sm text-sm font-mono transition-colors ${
                    symbols.includes(sym)
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
            <div className="mt-4">
              <label className="text-xs text-muted-foreground">Initial Capital</label>
              <Input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
                className="mt-1 bg-background border-input font-mono"
              />
            </div>
          </div>

          {/* Run Button */}
          <div className="trading-card p-4 rounded-sm flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                Run Backtest
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                Test {selectedStrategies.length} strategies on {symbols.length} symbols with 5 years of historical data.
              </p>
            </div>
            <Button 
              onClick={runBacktest}
              disabled={loading || selectedStrategies.length === 0}
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
              data-testid="run-backtest-btn"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-spin" />
                  Running...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Play className="w-4 h-4" />
                  Run Backtest
                </span>
              )}
            </Button>
          </div>
        </div>

        {/* Results */}
        {results && results.map((result, idx) => (
          <div key={idx} className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">
              {result.strategy_name} Results
            </h2>
            
            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              <MetricBox 
                label="Total Return" 
                value={result.metrics.total_return} 
                suffix="%" 
                positive={result.metrics.total_return >= 0}
              />
              <MetricBox 
                label="Annual Return" 
                value={result.metrics.annual_return} 
                suffix="%" 
                positive={result.metrics.annual_return >= 0}
              />
              <MetricBox 
                label="Sharpe Ratio" 
                value={result.metrics.sharpe_ratio}
                positive={result.metrics.sharpe_ratio >= 1}
              />
              <MetricBox 
                label="Sortino Ratio" 
                value={result.metrics.sortino_ratio}
                positive={result.metrics.sortino_ratio >= 1}
              />
              <MetricBox 
                label="Max Drawdown" 
                value={result.metrics.max_drawdown} 
                suffix="%" 
                positive={result.metrics.max_drawdown < 15}
              />
              <MetricBox 
                label="Win Rate" 
                value={result.metrics.win_rate} 
                suffix="%" 
                positive={result.metrics.win_rate >= 50}
              />
              <MetricBox 
                label="Profit Factor" 
                value={result.metrics.profit_factor}
                positive={result.metrics.profit_factor >= 1}
              />
              <MetricBox 
                label="Total Trades" 
                value={result.metrics.total_trades}
              />
              <MetricBox 
                label="Avg Trade P&L" 
                value={result.metrics.avg_trade_pnl?.toFixed(2) || '0'}
                suffix="$"
                positive={result.metrics.avg_trade_pnl >= 0}
              />
              <MetricBox 
                label="Total Commission" 
                value={result.metrics.total_commission?.toFixed(0) || '0'}
                suffix="$"
              />
              <MetricBox 
                label="Alpha" 
                value={result.metrics.alpha} 
                suffix="%" 
                positive={result.metrics.alpha >= 0}
              />
              <MetricBox 
                label="Beta" 
                value={result.metrics.beta}
              />
            </div>

            {/* Equity Curve */}
            <div className="trading-card rounded-sm overflow-hidden">
              <div className="p-4 border-b border-border">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Equity Curve
                </h3>
              </div>
              <div className="p-4" style={{ height: 350 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={result.equity_curve_sample?.map((val, i) => ({
                      index: i,
                      value: val
                    })) || []}
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id={`gradient-${idx}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={result.metrics.total_return >= 0 ? "hsl(160, 84%, 39%)" : "hsl(350, 89%, 60%)"} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={result.metrics.total_return >= 0 ? "hsl(160, 84%, 39%)" : "hsl(350, 89%, 60%)"} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(240, 3.7%, 15.9%)" vertical={false} />
                    <XAxis 
                      dataKey="index" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: 'hsl(240, 5%, 64.9%)', fontSize: 10 }}
                    />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: 'hsl(240, 5%, 64.9%)', fontSize: 10 }}
                      tickFormatter={(val) => `$${(val/1000).toFixed(0)}k`}
                      width={50}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        background: '#121214', 
                        border: '1px solid hsl(240, 3.7%, 15.9%)',
                        borderRadius: '4px'
                      }}
                      formatter={(val) => [`$${val.toLocaleString()}`, 'Portfolio']}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={result.metrics.total_return >= 0 ? "hsl(160, 84%, 39%)" : "hsl(350, 89%, 60%)"}
                      strokeWidth={2}
                      fill={`url(#gradient-${idx})`}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        ))}

        {/* No Results */}
        {!loading && !results && (
          <div className="trading-card p-8 rounded-sm text-center">
            <BarChart3 className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">No Backtest Results</h3>
            <p className="text-sm text-muted-foreground">
              Select strategies and symbols, then click "Run Backtest" to see results.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
