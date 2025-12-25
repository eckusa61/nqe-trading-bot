import { Check, X, AlertCircle, Wifi, WifiOff, Database, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export const SystemHealth = ({ status }) => {
  if (!status) {
    return (
      <div className="trading-card p-4 rounded-sm" data-testid="system-health">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          System Status
        </h3>
        <div className="text-center py-4 text-muted-foreground text-sm">
          Loading...
        </div>
      </div>
    );
  }

  const isHealthy = status.status === 'running' && status.connected;

  return (
    <div className="trading-card rounded-sm overflow-hidden" data-testid="system-health">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          System Status
        </h3>
        <div className={`w-2 h-2 rounded-full ${isHealthy ? 'status-connected pulse-live' : 'status-disconnected'}`} />
      </div>
      <div className="p-4 space-y-3">
        {/* Status Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertCircle className="w-4 h-4" />
            <span>Status</span>
          </div>
          <span className={`text-sm font-medium ${
            status.status === 'running' ? 'profit' : 
            status.status === 'kill_switch_active' ? 'loss' : 'text-muted-foreground'
          }`}>
            {status.status?.toUpperCase()}
          </span>
        </div>

        {/* Connection Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {status.connected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
            <span>Connection</span>
          </div>
          <span className={`text-sm font-medium ${status.connected ? 'profit' : 'loss'}`}>
            {status.connected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>

        {/* Mode Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Database className="w-4 h-4" />
            <span>Mode</span>
          </div>
          <span className="text-sm font-mono text-foreground uppercase">
            {status.mode}
          </span>
        </div>

        {/* Data Loaded Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Database className="w-4 h-4" />
            <span>Data</span>
          </div>
          <span className={`text-sm font-medium ${status.data_loaded ? 'profit' : 'text-warning'}`}>
            {status.data_loaded ? 'LOADED' : 'LOADING...'}
          </span>
        </div>

        {/* Uptime Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="w-4 h-4" />
            <span>Uptime</span>
          </div>
          <span className="text-sm font-mono text-foreground">
            {Math.floor(status.uptime_seconds / 60)}m {Math.floor(status.uptime_seconds % 60)}s
          </span>
        </div>

        {/* Symbols Row */}
        <div className="pt-2 border-t border-border">
          <div className="text-xs text-muted-foreground mb-2">Tracking</div>
          <div className="flex flex-wrap gap-1">
            {status.symbols_tracked?.map((symbol) => (
              <span 
                key={symbol}
                className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs font-mono rounded-sm"
              >
                {symbol}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemHealth;
