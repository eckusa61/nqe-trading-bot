import { useState, useEffect, useCallback } from 'react';
import { Activity, RefreshCw, Settings, BarChart3 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Link } from 'react-router-dom';
import {
  PnLTicker,
  KillSwitch,
  RegimeIndicator,
  MetricsGrid,
  PositionsTable,
  TradesTable,
  PortfolioChart,
  FeaturesGrid,
  SystemHealth,
  WebhookSettings,
  MarketStatus
} from '../components/trading';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [currentRegime, setCurrentRegime] = useState('sideways');

  const fetchDashboardData = useCallback(async () => {
    try {
      const [dashboardRes, featuresRes, regimeRes] = await Promise.all([
        axios.get(`${API_URL}/api/dashboard`),
        axios.get(`${API_URL}/api/features`),
        axios.get(`${API_URL}/api/ensemble/regime`).catch(() => ({ data: { current_regime: 'sideways' } }))
      ]);
      
      setDashboardData(dashboardRes.data);
      setFeatures(featuresRes.data);
      setKillSwitchActive(dashboardRes.data.system_status?.status === 'kill_switch_active');
      setCurrentRegime(regimeRes.data.current_regime || 'sideways');
      setError(null);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError('Failed to connect to trading system');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchDashboardData, 5000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  const handleKillSwitch = async (action, reason) => {
    try {
      await axios.post(`${API_URL}/api/kill-switch`, { action, reason });
      setKillSwitchActive(action === 'activate');
      fetchDashboardData();
    } catch (err) {
      console.error('Error toggling kill switch:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Activity className="w-8 h-8 text-primary animate-pulse" />
          <p className="text-muted-foreground">Connecting to trading system...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background" data-testid="trading-dashboard">
      {/* Ticker */}
      <PnLTicker marketData={dashboardData?.market_data || []} />

      {/* Header */}
      <header className="glass-header sticky top-0 z-50 px-4 md:px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <Activity className="w-6 h-6 text-primary" />
                <h1 className="text-xl font-bold tracking-tight text-foreground">
                  TradingBot
                </h1>
              </div>
              <span className="text-[10px] text-muted-foreground ml-8">Development by ECK</span>
            </div>
            <div className="hidden md:block h-6 w-px bg-border" />
            <RegimeIndicator regime={currentRegime} />
          </div>
          
          <div className="flex items-center gap-3">
            <Link to="/backtest">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
                data-testid="backtest-link"
              >
                <BarChart3 className="w-4 h-4" />
              </Button>
            </Link>
            <WebhookSettings />
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
              className="text-muted-foreground hover:text-foreground"
              data-testid="refresh-btn"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
            <KillSwitch 
              isActive={killSwitchActive} 
              onToggle={handleKillSwitch}
            />
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-destructive/10 border border-destructive/30 px-4 py-2 text-center">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {/* Main Dashboard Grid */}
      <main className="p-4 md:p-6 space-y-6">
        {/* Metrics Row */}
        <MetricsGrid account={dashboardData?.account} />

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column - Chart & Positions */}
          <div className="lg:col-span-8 space-y-6">
            <PortfolioChart 
              data={dashboardData?.portfolio_history || []} 
              height={350}
            />
            <PositionsTable positions={dashboardData?.account?.positions || []} />
          </div>

          {/* Right Column - System, Market, Trades, Features */}
          <div className="lg:col-span-4 space-y-6">
            <SystemHealth status={dashboardData?.system_status} />
            <MarketStatus />
            <TradesTable trades={dashboardData?.recent_trades || []} />
            <FeaturesGrid features={features} />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border px-4 md:px-6 py-4 mt-8">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Phase 1: Foundation | Mode: {dashboardData?.system_status?.mode?.toUpperCase()}</span>
          <span>
            Last update: {new Date().toLocaleTimeString()}
          </span>
        </div>
      </footer>
    </div>
  );
}
