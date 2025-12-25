#!/usr/bin/env python3
"""
Trading Bot Backend API Test Suite
Tests all endpoints for Phase 1 Foundation
"""
import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

class TradingBotAPITester:
    def __init__(self, base_url="https://tradingai-fusion.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.test_results = {}

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
            self.failed_tests.append({"test": name, "error": details})
        
        self.test_results[name] = {
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }

    def test_api_endpoint(self, method: str, endpoint: str, expected_status: int = 200, 
                         data: Optional[Dict] = None, timeout: int = 10) -> tuple:
        """Test a single API endpoint"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                return False, f"Unsupported method: {method}"

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    return True, response_data
                except json.JSONDecodeError:
                    return True, response.text
            else:
                return False, f"Status {response.status_code}, expected {expected_status}. Response: {response.text[:200]}"

        except requests.exceptions.Timeout:
            return False, f"Request timeout after {timeout}s"
        except requests.exceptions.ConnectionError:
            return False, "Connection error - backend may be down"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def test_system_status(self):
        """Test /api/status endpoint"""
        success, result = self.test_api_endpoint('GET', 'status')
        
        if success:
            required_fields = ['status', 'mode', 'connected', 'data_loaded', 'symbols_tracked']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("System Status", False, f"Missing fields: {missing_fields}")
            elif result.get('connected') != True:
                self.log_test("System Status", False, f"Not connected to broker: {result.get('connected')}")
            elif result.get('mode') != 'simulated':
                self.log_test("System Status", False, f"Expected simulated mode, got: {result.get('mode')}")
            elif result.get('data_loaded') != True:
                self.log_test("System Status", False, f"Data not loaded: {result.get('data_loaded')}")
            else:
                self.log_test("System Status", True, f"Connected: {result.get('connected')}, Mode: {result.get('mode')}")
                return result
        else:
            self.log_test("System Status", False, result)
        
        return None

    def test_market_data(self):
        """Test market data endpoints"""
        # Test all symbols endpoint
        success, result = self.test_api_endpoint('GET', 'market-data')
        
        if success:
            if isinstance(result, list) and len(result) == 7:
                symbols = [item.get('symbol') for item in result]
                expected_symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'META']
                
                if all(symbol in symbols for symbol in expected_symbols):
                    self.log_test("Market Data - All Symbols", True, f"Got {len(result)} symbols")
                    
                    # Test individual symbol
                    test_symbol = 'AAPL'
                    success2, result2 = self.test_api_endpoint('GET', f'market-data/{test_symbol}')
                    
                    if success2:
                        required_fields = ['symbol', 'bid', 'ask', 'last', 'volume']
                        missing_fields = [field for field in required_fields if field not in result2]
                        
                        if missing_fields:
                            self.log_test("Market Data - Single Symbol", False, f"Missing fields: {missing_fields}")
                        else:
                            self.log_test("Market Data - Single Symbol", True, f"{test_symbol}: ${result2.get('last')}")
                    else:
                        self.log_test("Market Data - Single Symbol", False, result2)
                else:
                    self.log_test("Market Data - All Symbols", False, f"Missing symbols. Got: {symbols}")
            else:
                self.log_test("Market Data - All Symbols", False, f"Expected 7 symbols, got: {len(result) if isinstance(result, list) else 'not a list'}")
        else:
            self.log_test("Market Data - All Symbols", False, result)

    def test_historical_data(self):
        """Test historical data endpoint"""
        test_symbol = 'SPY'
        success, result = self.test_api_endpoint('GET', f'historical/{test_symbol}?days=30')
        
        if success:
            if isinstance(result, list) and len(result) > 0:
                bar = result[0]
                required_fields = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
                missing_fields = [field for field in required_fields if field not in bar]
                
                if missing_fields:
                    self.log_test("Historical Data", False, f"Missing fields: {missing_fields}")
                else:
                    self.log_test("Historical Data", True, f"{test_symbol}: {len(result)} bars")
            else:
                self.log_test("Historical Data", False, f"No historical data returned for {test_symbol}")
        else:
            self.log_test("Historical Data", False, result)

    def test_features(self):
        """Test features endpoints"""
        # Test all features
        success, result = self.test_api_endpoint('GET', 'features')
        
        if success:
            if isinstance(result, list) and len(result) > 0:
                feature = result[0]
                required_fields = ['symbol', 'rsi_14', 'macd_histogram', 'volatility_20d']
                missing_fields = [field for field in required_fields if field not in feature]
                
                if missing_fields:
                    self.log_test("Features - All Symbols", False, f"Missing fields: {missing_fields}")
                else:
                    self.log_test("Features - All Symbols", True, f"Got features for {len(result)} symbols")
                    
                    # Test single symbol features
                    test_symbol = feature.get('symbol')
                    success2, result2 = self.test_api_endpoint('GET', f'features/{test_symbol}')
                    
                    if success2:
                        self.log_test("Features - Single Symbol", True, f"{test_symbol}: RSI={result2.get('rsi_14')}")
                    else:
                        self.log_test("Features - Single Symbol", False, result2)
            else:
                self.log_test("Features - All Symbols", False, "No features data returned")
        else:
            self.log_test("Features - All Symbols", False, result)

    def test_account(self):
        """Test account endpoint"""
        success, result = self.test_api_endpoint('GET', 'account')
        
        if success:
            required_fields = ['cash', 'portfolio_value', 'total_pnl', 'daily_pnl', 'positions']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("Account Summary", False, f"Missing fields: {missing_fields}")
            else:
                portfolio_value = result.get('portfolio_value', 0)
                cash = result.get('cash', 0)
                self.log_test("Account Summary", True, f"Portfolio: ${portfolio_value:,.2f}, Cash: ${cash:,.2f}")
        else:
            self.log_test("Account Summary", False, result)

    def test_dashboard(self):
        """Test dashboard endpoint"""
        success, result = self.test_api_endpoint('GET', 'dashboard', timeout=15)
        
        if success:
            required_sections = ['system_status', 'account', 'market_data', 'recent_trades']
            missing_sections = [section for section in required_sections if section not in result]
            
            if missing_sections:
                self.log_test("Dashboard Data", False, f"Missing sections: {missing_sections}")
            else:
                market_data_count = len(result.get('market_data', []))
                trades_count = len(result.get('recent_trades', []))
                self.log_test("Dashboard Data", True, f"Market data: {market_data_count}, Trades: {trades_count}")
        else:
            self.log_test("Dashboard Data", False, result)

    def test_orders(self):
        """Test order placement"""
        order_data = {
            "symbol": "AAPL",
            "quantity": 10,
            "side": "BUY",
            "order_type": "MKT"
        }
        
        success, result = self.test_api_endpoint('POST', 'orders', 200, order_data)
        
        if success:
            required_fields = ['order_id', 'symbol', 'side', 'quantity', 'filled_qty']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("Order Placement", False, f"Missing fields: {missing_fields}")
            else:
                order_id = result.get('order_id')
                filled_qty = result.get('filled_qty', 0)
                self.log_test("Order Placement", True, f"Order {order_id}: {filled_qty} shares filled")
        else:
            self.log_test("Order Placement", False, result)

    def test_trades(self):
        """Test trades endpoint"""
        success, result = self.test_api_endpoint('GET', 'trades')
        
        if success:
            if isinstance(result, list):
                self.log_test("Recent Trades", True, f"Retrieved {len(result)} trades")
            else:
                self.log_test("Recent Trades", False, "Expected list of trades")
        else:
            self.log_test("Recent Trades", False, result)

    def test_kill_switch(self):
        """Test kill switch functionality"""
        # Test activation
        activate_data = {"action": "activate", "reason": "Test activation"}
        success, result = self.test_api_endpoint('POST', 'kill-switch', 200, activate_data)
        
        if success:
            if result.get('status') == 'activated':
                self.log_test("Kill Switch - Activate", True, "Successfully activated")
                
                # Test deactivation
                deactivate_data = {"action": "deactivate"}
                success2, result2 = self.test_api_endpoint('POST', 'kill-switch', 200, deactivate_data)
                
                if success2 and result2.get('status') == 'deactivated':
                    self.log_test("Kill Switch - Deactivate", True, "Successfully deactivated")
                else:
                    self.log_test("Kill Switch - Deactivate", False, result2)
            else:
                self.log_test("Kill Switch - Activate", False, f"Unexpected response: {result}")
        else:
            self.log_test("Kill Switch - Activate", False, result)

    def test_webhook_config(self):
        """Test webhook configuration endpoints"""
        # Test GET webhook config
        success, result = self.test_api_endpoint('GET', 'webhooks')
        
        if success:
            required_fields = ['slack_configured', 'discord_configured', 'enabled', 'rate_limit', 'enabled_alerts']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("Webhook Config - GET", False, f"Missing fields: {missing_fields}")
            else:
                self.log_test("Webhook Config - GET", True, f"Slack: {result.get('slack_configured')}, Discord: {result.get('discord_configured')}")
                
                # Test POST webhook config
                config_data = {
                    "slack_url": "https://hooks.slack.com/services/test/test/test",
                    "discord_url": "https://discord.com/api/webhooks/test/test",
                    "enabled": True
                }
                
                success2, result2 = self.test_api_endpoint('POST', 'webhooks', 200, config_data)
                
                if success2:
                    if result2.get('slack_configured') and result2.get('discord_configured'):
                        self.log_test("Webhook Config - POST", True, "Successfully configured webhooks")
                    else:
                        self.log_test("Webhook Config - POST", False, f"Configuration not saved properly: {result2}")
                else:
                    self.log_test("Webhook Config - POST", False, result2)
        else:
            self.log_test("Webhook Config - GET", False, result)

    def test_alert_history(self):
        """Test alert history endpoint"""
        success, result = self.test_api_endpoint('GET', 'alerts')
        
        if success:
            required_fields = ['alerts', 'total']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("Alert History", False, f"Missing fields: {missing_fields}")
            else:
                alerts_count = len(result.get('alerts', []))
                total_count = result.get('total', 0)
                self.log_test("Alert History", True, f"Retrieved {alerts_count} alerts (total: {total_count})")
        else:
            self.log_test("Alert History", False, result)

    def test_alert_endpoints(self):
        """Test alert trigger endpoints"""
        # Test test alert (should fail gracefully when no webhooks configured)
        test_alert_data = {"alert_type": "test"}
        success, result = self.test_api_endpoint('POST', 'alerts/test', 400, test_alert_data)
        
        if success:
            self.log_test("Test Alert - No Webhooks", True, "Correctly failed when no webhooks configured")
        else:
            # If it doesn't fail with 400, check if it's because webhooks are configured
            success2, result2 = self.test_api_endpoint('POST', 'alerts/test', 200, test_alert_data)
            if success2:
                self.log_test("Test Alert - With Webhooks", True, "Test alert sent successfully")
            else:
                self.log_test("Test Alert", False, f"Unexpected response: {result}")

        # Test drawdown warning alert
        success, result = self.test_api_endpoint('POST', 'alerts/drawdown-warning', 200, None)
        
        if success:
            if result.get('status') == 'sent':
                self.log_test("Drawdown Warning Alert", True, f"Drawdown: {result.get('drawdown')}%")
            else:
                self.log_test("Drawdown Warning Alert", False, f"Unexpected response: {result}")
        else:
            self.log_test("Drawdown Warning Alert", False, result)

        # Test connection lost alert
        success, result = self.test_api_endpoint('POST', 'alerts/connection-lost', 200, None)
        
        if success:
            if result.get('status') == 'sent':
                self.log_test("Connection Lost Alert", True, f"Alert: {result.get('alert')}")
            else:
                self.log_test("Connection Lost Alert", False, f"Unexpected response: {result}")
        else:
            self.log_test("Connection Lost Alert", False, result)

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Trading Bot Backend API Tests")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test system status first
        status_result = self.test_system_status()
        
        if status_result and status_result.get('connected'):
            # Only run other tests if system is connected
            self.test_market_data()
            self.test_historical_data()
            self.test_features()
            self.test_account()
            self.test_dashboard()
            self.test_orders()
            self.test_trades()
            self.test_kill_switch()
            
            # Test webhook and alert functionality
            self.test_webhook_config()
            self.test_alert_history()
            self.test_alert_endpoints()
        else:
            print("⚠️  System not connected - skipping dependent tests")
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"  • {test['test']}: {test['error']}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"✨ Success Rate: {success_rate:.1f}%")
        
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": len(self.failed_tests),
            "success_rate": success_rate,
            "failures": self.failed_tests,
            "detailed_results": self.test_results
        }

def main():
    """Main test execution"""
    tester = TradingBotAPITester()
    results = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if results["failed_tests"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())