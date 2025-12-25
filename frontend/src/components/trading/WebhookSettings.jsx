import { useState, useEffect } from 'react';
import { Settings, Bell, Send, Check, X, AlertTriangle } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Switch } from '../ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../ui/dialog';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const WebhookSettings = () => {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState({
    slack_url: '',
    discord_url: '',
    enabled: true
  });
  const [savedConfig, setSavedConfig] = useState({
    slack_configured: false,
    discord_configured: false,
    enabled: true
  });
  const [loading, setLoading] = useState(false);
  const [testStatus, setTestStatus] = useState(null);

  useEffect(() => {
    if (open) {
      fetchConfig();
    }
  }, [open]);

  const fetchConfig = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/webhooks`);
      setSavedConfig(res.data);
      setConfig({
        slack_url: '',
        discord_url: '',
        enabled: res.data.enabled
      });
    } catch (err) {
      console.error('Error fetching webhook config:', err);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const payload = {};
      if (config.slack_url) payload.slack_url = config.slack_url;
      if (config.discord_url) payload.discord_url = config.discord_url;
      payload.enabled = config.enabled;
      
      const res = await axios.post(`${API_URL}/api/webhooks`, payload);
      setSavedConfig(res.data);
      setConfig({ ...config, slack_url: '', discord_url: '' });
    } catch (err) {
      console.error('Error saving webhook config:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    setTestStatus('sending');
    try {
      const res = await axios.post(`${API_URL}/api/alerts/test`, { alert_type: 'test' });
      setTestStatus(res.data.status === 'sent' ? 'success' : 'failed');
    } catch (err) {
      setTestStatus('failed');
    }
    setTimeout(() => setTestStatus(null), 3000);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button 
          variant="ghost" 
          size="sm"
          className="text-muted-foreground hover:text-foreground"
          data-testid="webhook-settings-btn"
        >
          <Bell className="w-4 h-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-card border-border sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <Bell className="w-5 h-5" />
            Alert Webhooks
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Configure Slack/Discord webhooks for real-time alerts.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          {/* Status indicators */}
          <div className="flex items-center gap-4 p-3 bg-secondary/30 rounded-sm">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${savedConfig.slack_configured ? 'status-connected' : 'bg-muted-foreground'}`} />
              <span className="text-sm text-muted-foreground">Slack</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${savedConfig.discord_configured ? 'status-connected' : 'bg-muted-foreground'}`} />
              <span className="text-sm text-muted-foreground">Discord</span>
            </div>
          </div>
          
          {/* Slack URL */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Slack Webhook URL</label>
            <Input
              type="url"
              placeholder={savedConfig.slack_configured ? "••••••• (configured)" : "https://hooks.slack.com/services/..."}
              value={config.slack_url}
              onChange={(e) => setConfig({ ...config, slack_url: e.target.value })}
              className="bg-background border-input"
            />
          </div>
          
          {/* Discord URL */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Discord Webhook URL</label>
            <Input
              type="url"
              placeholder={savedConfig.discord_configured ? "••••••• (configured)" : "https://discord.com/api/webhooks/..."}
              value={config.discord_url}
              onChange={(e) => setConfig({ ...config, discord_url: e.target.value })}
              className="bg-background border-input"
            />
          </div>
          
          {/* Enable/Disable */}
          <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-sm">
            <div className="space-y-0.5">
              <label className="text-sm font-medium text-foreground">Enable Alerts</label>
              <p className="text-xs text-muted-foreground">Send alerts to configured webhooks</p>
            </div>
            <Switch
              checked={config.enabled}
              onCheckedChange={(checked) => setConfig({ ...config, enabled: checked })}
            />
          </div>
          
          {/* Alert Types */}
          <div className="p-3 bg-secondary/20 rounded-sm">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Enabled Alerts</p>
            <div className="flex flex-wrap gap-1">
              {['Drawdown Warning', 'Kill Switch', 'Connection Lost', 'Data Anomaly', 'Strategy Failure'].map(alert => (
                <span key={alert} className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs rounded-sm">
                  {alert}
                </span>
              ))}
            </div>
          </div>
        </div>
        
        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            onClick={handleTest}
            disabled={!savedConfig.slack_configured && !savedConfig.discord_configured}
            className="flex items-center gap-2"
            data-testid="test-webhook-btn"
          >
            {testStatus === 'sending' ? (
              <span className="animate-pulse">Sending...</span>
            ) : testStatus === 'success' ? (
              <>
                <Check className="w-4 h-4 profit" />
                Sent!
              </>
            ) : testStatus === 'failed' ? (
              <>
                <X className="w-4 h-4 loss" />
                Failed
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Test Alert
              </>
            )}
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={loading || (!config.slack_url && !config.discord_url && config.enabled === savedConfig.enabled)}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
            data-testid="save-webhook-btn"
          >
            {loading ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default WebhookSettings;
