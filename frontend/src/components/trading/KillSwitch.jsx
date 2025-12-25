import { useState } from 'react';
import { AlertTriangle, ShieldOff, Shield } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../ui/alert-dialog';
import { Button } from '../ui/button';

export const KillSwitch = ({ isActive, onToggle, loading = false }) => {
  const [reason, setReason] = useState('');

  const handleActivate = () => {
    onToggle('activate', reason || 'Manual activation');
    setReason('');
  };

  const handleDeactivate = () => {
    onToggle('deactivate');
  };

  if (isActive) {
    return (
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button 
            variant="destructive"
            className="kill-switch-btn active flex items-center gap-2 px-4 py-2 rounded-sm font-medium"
            data-testid="kill-switch-btn"
          >
            <ShieldOff className="w-4 h-4" />
            <span className="hidden sm:inline">KILL SWITCH ACTIVE</span>
            <span className="sm:hidden">STOPPED</span>
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="bg-card border-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-foreground">
              <Shield className="w-5 h-5 text-primary" />
              Deactivate Kill Switch?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              This will resume normal trading operations. Make sure market conditions 
              are favorable before reactivating.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-secondary text-secondary-foreground hover:bg-secondary/80">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDeactivate}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
              disabled={loading}
            >
              Resume Trading
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    );
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button 
          variant="outline"
          className="kill-switch-btn flex items-center gap-2 px-4 py-2 rounded-sm font-medium"
          data-testid="kill-switch-btn"
        >
          <AlertTriangle className="w-4 h-4" />
          <span className="hidden sm:inline">KILL SWITCH</span>
          <span className="sm:hidden">STOP</span>
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent className="bg-card border-border">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="w-5 h-5" />
            Activate Kill Switch?
          </AlertDialogTitle>
          <AlertDialogDescription className="text-muted-foreground">
            This will immediately:
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>Stop all trading activity</li>
              <li>Cancel all pending orders</li>
              <li>Close all open positions at market price</li>
            </ul>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="py-2">
          <label className="text-sm text-muted-foreground">Reason (optional)</label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Market volatility, System error..."
            className="w-full mt-1 px-3 py-2 bg-background border border-input rounded-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel className="bg-secondary text-secondary-foreground hover:bg-secondary/80">
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction 
            onClick={handleActivate}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={loading}
          >
            ACTIVATE KILL SWITCH
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default KillSwitch;
