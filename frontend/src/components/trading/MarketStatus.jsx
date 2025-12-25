import { useState, useEffect } from 'react';
import { Clock, Calendar, AlertTriangle, CheckCircle2, XCircle, Sun, Moon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SESSION_CONFIG = {
  regular: { 
    label: 'Market Open', 
    color: 'bg-green-500', 
    textColor: 'text-green-500',
    icon: CheckCircle2 
  },
  pre_market: { 
    label: 'Pre-Market', 
    color: 'bg-yellow-500', 
    textColor: 'text-yellow-500',
    icon: Sun 
  },
  after_hours: { 
    label: 'After Hours', 
    color: 'bg-orange-500', 
    textColor: 'text-orange-500',
    icon: Moon 
  },
  closed: { 
    label: 'Market Closed', 
    color: 'bg-gray-500', 
    textColor: 'text-gray-500',
    icon: XCircle 
  },
  holiday: { 
    label: 'Holiday', 
    color: 'bg-red-500', 
    textColor: 'text-red-500',
    icon: Calendar 
  },
  weekend: { 
    label: 'Weekend', 
    color: 'bg-gray-500', 
    textColor: 'text-gray-500',
    icon: XCircle 
  }
};

export default function MarketStatus() {
  const [marketStatus, setMarketStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMarketStatus = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/market/status`);
        setMarketStatus(response.data);
      } catch (error) {
        console.error('Error fetching market status:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMarketStatus();
    // Refresh every 30 seconds
    const interval = setInterval(fetchMarketStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="bg-card border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Market Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-muted rounded w-24"></div>
            <div className="h-3 bg-muted rounded w-32"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!marketStatus) return null;

  const sessionConfig = SESSION_CONFIG[marketStatus.session] || SESSION_CONFIG.closed;
  const SessionIcon = sessionConfig.icon;

  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      timeZoneName: 'short'
    });
  };

  const formatMinutes = (minutes) => {
    if (!minutes) return 'N/A';
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Market Status
          </div>
          <Badge 
            variant="outline" 
            className={`${sessionConfig.textColor} border-current`}
          >
            <SessionIcon className="w-3 h-3 mr-1" />
            {sessionConfig.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Current Time */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Current Time (ET)</span>
          <span className="font-mono text-foreground">
            {formatTime(marketStatus.current_time_et)}
          </span>
        </div>

        {/* Can Trade Status */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Can Trade</span>
          <span className={marketStatus.can_trade ? 'text-green-500' : 'text-red-500'}>
            {marketStatus.can_trade ? (
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Yes
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <XCircle className="w-3 h-3" /> No
              </span>
            )}
          </span>
        </div>

        {/* Holiday Name */}
        {marketStatus.holiday_name && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Holiday</span>
            <span className="text-red-400 font-medium">
              {marketStatus.holiday_name.includes('-') 
                ? new Date(marketStatus.holiday_name).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                : marketStatus.holiday_name}
            </span>
          </div>
        )}

        {/* Next Open/Close */}
        {marketStatus.is_open ? (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Closes In</span>
            <span className="text-orange-400 font-mono">
              {formatMinutes(marketStatus.time_to_close_minutes)}
            </span>
          </div>
        ) : (
          marketStatus.next_open && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Opens In</span>
              <span className="text-green-400 font-mono">
                {formatMinutes(marketStatus.time_to_open_minutes)}
              </span>
            </div>
          )
        )}

        {/* Time Drift Warning */}
        {Math.abs(marketStatus.time_drift_seconds) > 2 && (
          <div className="flex items-center gap-2 text-yellow-500 text-xs mt-2 p-2 bg-yellow-500/10 rounded">
            <AlertTriangle className="w-3 h-3" />
            Time drift: {marketStatus.time_drift_seconds.toFixed(1)}s
          </div>
        )}
      </CardContent>
    </Card>
  );
}
