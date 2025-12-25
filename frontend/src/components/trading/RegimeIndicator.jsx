import { Shield, Zap } from 'lucide-react';

export const RegimeIndicator = ({ regime = 'sideways' }) => {
  const regimeConfig = {
    bull_quiet: {
      label: 'BULL',
      sublabel: 'Low Volatility',
      color: 'profit',
      bgClass: 'regime-bull',
      icon: '📈'
    },
    bull_volatile: {
      label: 'BULL',
      sublabel: 'High Volatility',
      color: 'profit',
      bgClass: 'regime-bull',
      icon: '🚀'
    },
    bear_quiet: {
      label: 'BEAR',
      sublabel: 'Low Volatility',
      color: 'loss',
      bgClass: 'regime-bear',
      icon: '📉'
    },
    bear_volatile: {
      label: 'BEAR',
      sublabel: 'High Volatility',
      color: 'loss',
      bgClass: 'regime-bear',
      icon: '⚠️'
    },
    sideways: {
      label: 'SIDEWAYS',
      sublabel: 'Range Bound',
      color: 'warning',
      bgClass: 'regime-sideways',
      icon: '➡️'
    },
    crisis: {
      label: 'CRISIS',
      sublabel: 'Extreme Vol',
      color: 'loss',
      bgClass: 'regime-bear',
      icon: '🔴'
    }
  };

  const config = regimeConfig[regime] || regimeConfig.sideways;

  return (
    <div 
      className={`${config.bgClass} px-3 py-1.5 rounded-sm flex items-center gap-2`}
      data-testid="regime-indicator"
    >
      <Shield className="w-4 h-4" />
      <div className="flex flex-col">
        <span className="text-xs font-bold tracking-wide">{config.label}</span>
        <span className="text-[10px] opacity-70">{config.sublabel}</span>
      </div>
    </div>
  );
};

export default RegimeIndicator;
