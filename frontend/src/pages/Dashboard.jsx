import { useState, useEffect, useCallback } from 'react';
import { 
  Activity, RefreshCw, Settings, BarChart3, TrendingUp, TrendingDown,
  DollarSign, Newspaper, Bell, Zap, Target, Shield, Brain, Clock,
  ArrowUpRight, ArrowDownRight, AlertTriangle, CheckCircle, XCircle
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Link } from 'react-router-dom';
import {
  PnLTicker,
  KillSwitch,
  RegimeIndicator,
  PortfolioChart,
  WebhookSettings,
  MarketStatus
} from '../components/trading';
import axios from 'axios';

// Backend URL - localhost için sabit
const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Signal Strength Badge Component
const SignalBadge = ({ strength }) => {
  const colors = {
    strong_buy: 'bg-green-500 text-white',
    buy: 'bg-green-400 text-white',
    weak_buy: 'bg-green-300 text-green-900',
    neutral: 'bg-gray-400 text-white',
    weak_sell: 'bg-red-300 text-red-900',
    sell: 'bg-red-400 text-white',
    strong_sell: 'bg-red-500 text-white'
  };
  
  const labels = {
    strong_buy: 'GÜÇLÜ AL',
    buy: 'AL',
    weak_buy: 'ZAYIF AL',
    neutral: 'NÖTR',
    weak_sell: 'ZAYIF SAT',
    sell: 'SAT',
    strong_sell: 'GÜÇLÜ SAT'
  };
  
  return (
    <Badge className={`${colors[strength] || colors.neutral} text-xs`}>
      {labels[strength] || strength}
    </Badge>
  );
};

// News Sentiment Badge
const SentimentBadge = ({ sentiment }) => {
  const colors = {
    very_bullish: 'text-green-500',
    bullish: 'text-green-400',
    neutral: 'text-gray-400',
    bearish: 'text-red-400',
    very_bearish: 'text-red-500'
  };
  
  return (
    <span className={`${colors[sentiment] || colors.neutral} font-medium`}>
      {sentiment === 'very_bullish' && '🟢🟢'}
      {sentiment === 'bullish' && '🟢'}
      {sentiment === 'neutral' && '⚪'}
      {sentiment === 'bearish' && '🔴'}
      {sentiment === 'very_bearish' && '🔴🔴'}
    </span>
  );
};

export default function Dashboard() {
  const [fullDashboard, setFullDashboard] = useState(null);
  const [signalLevels, setSignalLevels] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState('SPY');

  const symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'META'];

  const fetchData = useCallback(async () => {
    try {
      const [dashboardRes, signalRes] = await Promise.all([
        axios.get(`${API_URL}/api/dashboard/full`),
        axios.get(`${API_URL}/api/signals/levels/${selectedSymbol}`)
      ]);
      
      setFullDashboard(dashboardRes.data);
      setSignalLevels(signalRes.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Sisteme bağlanılamadı');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleKillSwitch = async (action, reason) => {
    try {
      await axios.post(`${API_URL}/api/kill-switch`, { action, reason });
      setKillSwitchActive(action === 'activate');
      fetchData();
    } catch (err) {
      console.error('Error toggling kill switch:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Activity className="w-12 h-12 text-blue-500 animate-pulse" />
          <p className="text-gray-400 text-lg">Trading sistemi yükleniyor...</p>
        </div>
      </div>
    );
  }

  const account = fullDashboard?.account || {};
  const news = fullDashboard?.news || {};
  const regime = fullDashboard?.regime || {};
  const system = fullDashboard?.system || {};
  const strategyWeights = fullDashboard?.strategy_weights?.weights || {};

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Top Header */}
      <header className="bg-gray-900/80 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                  <span className="text-white font-bold text-lg">ECK</span>
                </div>
                <div>
                  <h1 className="text-xl font-bold">NQE Trading Bot</h1>
                  <span className="text-xs text-gray-500">Quantum Engine v2.0 by ECK</span>
                </div>
              </div>
              <Badge variant="outline" className={`ml-4 ${system.mode === 'live_paper' ? 'text-green-400 border-green-400' : 'text-yellow-400 border-yellow-400'}`}>
                {system.mode === 'live_paper' ? 'PAPER TRADING' : 'SIMULATED'}
              </Badge>
            </div>
            
            <div className="flex items-center gap-3">
              <Link to="/backtest">
                <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white">
                  <BarChart3 className="w-4 h-4 mr-1" /> Backtest
                </Button>
              </Link>
              <WebhookSettings />
              <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={refreshing} className="text-gray-400 hover:text-white">
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
              <KillSwitch isActive={killSwitchActive} onToggle={handleKillSwitch} />
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-900/30 border-b border-red-800 px-4 py-2 text-center">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6 space-y-6">
        
        {/* Row 1: Account Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <DollarSign className="w-5 h-5 text-blue-400" />
                <span className="text-xs text-gray-500">Toplam Varlık</span>
              </div>
              <p className="text-2xl font-bold mt-2">${account.equity?.toLocaleString() || '100,000'}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <TrendingUp className="w-5 h-5 text-green-400" />
                <span className="text-xs text-gray-500">Günlük P&L</span>
              </div>
              <p className={`text-2xl font-bold mt-2 ${(account.daily_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(account.daily_pnl || 0) >= 0 ? '+' : ''}{(account.daily_pnl || 0).toLocaleString()} $
              </p>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <Target className="w-5 h-5 text-purple-400" />
                <span className="text-xs text-gray-500">Açık Pozisyon</span>
              </div>
              <p className="text-2xl font-bold mt-2">{fullDashboard?.positions?.length || 0}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <Brain className="w-5 h-5 text-cyan-400" />
                <span className="text-xs text-gray-500">Aktif Strateji</span>
              </div>
              <p className="text-2xl font-bold mt-2">{system.strategies_active || 15}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <Shield className="w-5 h-5 text-yellow-400" />
                <span className="text-xs text-gray-500">Piyasa Rejimi</span>
              </div>
              <p className="text-lg font-bold mt-2 capitalize">{regime.current_regime || 'Sideways'}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-900/50 border-gray-800">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <Clock className="w-5 h-5 text-orange-400" />
                <span className="text-xs text-gray-500">Uptime</span>
              </div>
              <p className="text-lg font-bold mt-2">
                {Math.floor((system.uptime_seconds || 0) / 3600)}s {Math.floor(((system.uptime_seconds || 0) % 3600) / 60)}d
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Row 2: Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column - Signal Levels */}
          <Card className="bg-gray-900/50 border-gray-800 lg:col-span-1">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Target className="w-5 h-5 text-blue-400" />
                  Sinyal Seviyeleri
                </CardTitle>
              </div>
              {/* Symbol Selector */}
              <div className="flex flex-wrap gap-1 mt-2">
                {symbols.map(sym => (
                  <Button
                    key={sym}
                    size="sm"
                    variant={selectedSymbol === sym ? "default" : "ghost"}
                    className={`text-xs px-2 py-1 h-7 ${selectedSymbol === sym ? 'bg-blue-600' : 'text-gray-400'}`}
                    onClick={() => setSelectedSymbol(sym)}
                  >
                    {sym}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {signalLevels.symbol ? (
                <>
                  <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                    <span className="text-gray-400">Sinyal</span>
                    <SignalBadge strength={signalLevels.signal_strength} />
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                    <span className="text-gray-400">Mevcut Fiyat</span>
                    <span className="text-xl font-bold">${signalLevels.current_price?.toFixed(2)}</span>
                  </div>
                  
                  <div className="space-y-2">
                    <p className="text-sm text-gray-500 font-medium">📈 Giriş Seviyeleri</p>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="p-2 bg-green-900/30 rounded text-center">
                        <p className="text-gray-400">Agresif</p>
                        <p className="text-green-400 font-bold">${signalLevels.entry_levels?.aggressive_buy?.toFixed(2)}</p>
                      </div>
                      <div className="p-2 bg-green-900/50 rounded text-center">
                        <p className="text-gray-400">En İyi</p>
                        <p className="text-green-400 font-bold">${signalLevels.entry_levels?.best_buy?.toFixed(2)}</p>
                      </div>
                      <div className="p-2 bg-green-900/30 rounded text-center">
                        <p className="text-gray-400">Güvenli</p>
                        <p className="text-green-400 font-bold">${signalLevels.entry_levels?.conservative_buy?.toFixed(2)}</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <p className="text-sm text-gray-500 font-medium">🎯 Çıkış Seviyeleri</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 bg-blue-900/30 rounded">
                        <p className="text-gray-400">TP1</p>
                        <p className="text-blue-400 font-bold">${signalLevels.exit_levels?.take_profit_1?.toFixed(2)}</p>
                      </div>
                      <div className="p-2 bg-blue-900/50 rounded">
                        <p className="text-gray-400">TP2</p>
                        <p className="text-blue-400 font-bold">${signalLevels.exit_levels?.take_profit_2?.toFixed(2)}</p>
                      </div>
                      <div className="p-2 bg-blue-900/30 rounded">
                        <p className="text-gray-400">TP3</p>
                        <p className="text-blue-400 font-bold">${signalLevels.exit_levels?.take_profit_3?.toFixed(2)}</p>
                      </div>
                      <div className="p-2 bg-red-900/50 rounded">
                        <p className="text-gray-400">Stop Loss</p>
                        <p className="text-red-400 font-bold">${signalLevels.exit_levels?.stop_loss?.toFixed(2)}</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <p className="text-sm text-gray-500 font-medium">📊 İndikatörler</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 bg-gray-800/50 rounded flex justify-between">
                        <span className="text-gray-400">RSI</span>
                        <span className={`font-bold ${(signalLevels.indicators?.rsi || 50) < 30 ? 'text-green-400' : (signalLevels.indicators?.rsi || 50) > 70 ? 'text-red-400' : 'text-gray-300'}`}>
                          {signalLevels.indicators?.rsi?.toFixed(1)}
                        </span>
                      </div>
                      <div className="p-2 bg-gray-800/50 rounded flex justify-between">
                        <span className="text-gray-400">Trend</span>
                        <span className="font-bold capitalize">{signalLevels.indicators?.trend}</span>
                      </div>
                      <div className="p-2 bg-gray-800/50 rounded flex justify-between">
                        <span className="text-gray-400">MACD</span>
                        <span className="font-bold capitalize">{signalLevels.indicators?.macd_signal?.replace('_', ' ')}</span>
                      </div>
                      <div className="p-2 bg-gray-800/50 rounded flex justify-between">
                        <span className="text-gray-400">R:R</span>
                        <span className="font-bold text-yellow-400">{signalLevels.risk_metrics?.risk_reward_ratio?.toFixed(2)}:1</span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-gray-500 text-center py-8">Sinyal verisi yükleniyor...</p>
              )}
            </CardContent>
          </Card>

          {/* Middle Column - News Feed */}
          <Card className="bg-gray-900/50 border-gray-800 lg:col-span-1">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Newspaper className="w-5 h-5 text-purple-400" />
                Haberler
                {news.sentiment && (
                  <Badge variant="outline" className={`ml-auto text-xs ${news.sentiment?.sentiment === 'bullish' ? 'text-green-400 border-green-400' : news.sentiment?.sentiment === 'bearish' ? 'text-red-400 border-red-400' : 'text-gray-400 border-gray-400'}`}>
                    {news.sentiment?.sentiment?.toUpperCase()}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {news.latest?.map((item, idx) => (
                  <div key={idx} className={`p-3 rounded-lg border ${item.is_breaking ? 'bg-red-900/20 border-red-800' : 'bg-gray-800/30 border-gray-700/50'}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        {item.is_breaking && (
                          <Badge className="bg-red-600 text-white text-xs mb-1">BREAKING</Badge>
                        )}
                        <p className="text-sm font-medium text-gray-200 line-clamp-2">{item.title}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                          <span>{item.source}</span>
                          <span>•</span>
                          <span>{item.age_minutes}dk önce</span>
                        </div>
                      </div>
                      <SentimentBadge sentiment={item.sentiment} />
                    </div>
                    {item.symbols?.length > 0 && (
                      <div className="flex gap-1 mt-2">
                        {item.symbols.map(sym => (
                          <Badge key={sym} variant="outline" className="text-xs text-blue-400 border-blue-400/50">${sym}</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {(!news.latest || news.latest.length === 0) && (
                  <p className="text-gray-500 text-center py-8">Haber bulunamadı</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Right Column - Strategies & System */}
          <Card className="bg-gray-900/50 border-gray-800 lg:col-span-1">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Brain className="w-5 h-5 text-cyan-400" />
                Strateji Ağırlıkları
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {Object.entries(strategyWeights).sort((a, b) => b[1] - a[1]).map(([name, weight]) => (
                  <div key={name} className="flex items-center justify-between p-2 bg-gray-800/30 rounded">
                    <span className="text-sm text-gray-300 capitalize">{name.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full"
                          style={{ width: `${(weight * 100).toFixed(0)}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-10 text-right">{(weight * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* System Status */}
              <div className="mt-6 pt-4 border-t border-gray-700">
                <p className="text-sm text-gray-500 font-medium mb-3">Sistem Durumu</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center gap-2 p-2 bg-gray-800/30 rounded">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    <span>Backend</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-gray-800/30 rounded">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    <span>Data Feed</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-gray-800/30 rounded">
                    {system.mode === 'live_paper' ? (
                      <CheckCircle className="w-4 h-4 text-green-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                    )}
                    <span>IBKR</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-gray-800/30 rounded">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    <span>AI Engine</span>
                  </div>
                </div>
              </div>
              
              {/* Tracked Symbols */}
              <div className="mt-4">
                <p className="text-sm text-gray-500 font-medium mb-2">Takip Edilen Semboller</p>
                <div className="flex flex-wrap gap-1">
                  {system.symbols_tracked?.map(sym => (
                    <Badge key={sym} variant="outline" className="text-xs">{sym}</Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Row 3: Telegram & Execution Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-gray-900/50 border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Bell className="w-5 h-5 text-blue-400" />
                Telegram Kanalları
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-blue-900/20 border border-blue-800/50 rounded-lg">
                  <p className="text-sm font-medium">📰 Haber Kanalı</p>
                  <p className="text-xs text-gray-400 mt-1">Piyasa haberleri & analizler</p>
                </div>
                <div className="p-3 bg-green-900/20 border border-green-800/50 rounded-lg">
                  <p className="text-sm font-medium">📊 Sinyal Kanalı</p>
                  <p className="text-xs text-gray-400 mt-1">AL/SAT sinyalleri</p>
                </div>
                <div className="p-3 bg-purple-900/20 border border-purple-800/50 rounded-lg">
                  <p className="text-sm font-medium">🔬 Analiz Kanalı</p>
                  <p className="text-xs text-gray-400 mt-1">Teknik & temel analiz</p>
                </div>
                <div className="p-3 bg-orange-900/20 border border-orange-800/50 rounded-lg">
                  <p className="text-sm font-medium">⚙️ Optimizasyon</p>
                  <p className="text-xs text-gray-400 mt-1">Sistem güncellemeleri</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-900/50 border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Zap className="w-5 h-5 text-yellow-400" />
                Execution İstatistikleri
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-800/30 rounded-lg">
                  <p className="text-xs text-gray-400">Toplam Order</p>
                  <p className="text-xl font-bold">{fullDashboard?.execution_stats?.total_orders || 0}</p>
                </div>
                <div className="p-3 bg-gray-800/30 rounded-lg">
                  <p className="text-xs text-gray-400">Ort. Slippage</p>
                  <p className="text-xl font-bold">{fullDashboard?.execution_stats?.avg_slippage_bps || 0} bps</p>
                </div>
                <div className="p-3 bg-gray-800/30 rounded-lg">
                  <p className="text-xs text-gray-400">Fill Rate</p>
                  <p className="text-xl font-bold">{fullDashboard?.execution_stats?.avg_fill_rate_pct || 100}%</p>
                </div>
                <div className="p-3 bg-gray-800/30 rounded-lg">
                  <p className="text-xs text-gray-400">Ort. Süre</p>
                  <p className="text-xl font-bold">{fullDashboard?.execution_stats?.avg_execution_time_sec || 0}s</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 px-4 py-4 mt-8">
        <div className="container mx-auto flex items-center justify-between text-xs text-gray-500">
          <span className="flex items-center gap-2">
            <span className="text-blue-400 font-bold">ECK</span>
            <span>|</span>
            <span>NQE Trading Bot v2.0 | 15 Strateji | {system.mode?.toUpperCase()}</span>
          </span>
          <span className="flex items-center gap-4">
            <span className="text-yellow-400">Development by ECK</span>
            <span>|</span>
            <span>Son güncelleme: {new Date().toLocaleTimeString('tr-TR')}</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
