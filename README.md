Trading Application (SMC & ICT)
A Python application for automated trading using SMC and ICT strategies with Capital.com API.
Features

SMC: Order Blocks, Fair Value Gaps, Liquidity Grabs, Break of Structure, Change of Character.
ICT: Market Structure, Kill Zones, Judas Swing, Optimal Trade Entry, Daily Bias.
Risk management with fixed % risk per trade.
Optimal Stop-Loss/Take-Profit calculation using ATR and support/resistance.
Early exit for positions at risk of trend change (BOS, CHOCH, RSI).
Advanced backtesting with spreads, slippage, and commissions.
Configurable via YAML.

Setup

Install dependencies:pip install -r requirements.txt


Update config.yaml with your Capital.com API credentials.
Add historical data to data/ (e.g., EURUSD_MINUTE_5.csv).
Run in live mode:python main.py


For backtesting, set mode: backtest in config.yaml.

Historical Data

Place CSV files in data/ with format:timestamp,open,high,low,close,volume
2023-01-01 00:00:00,1.0700,1.0705,1.0698,1.0702,1000


Sources: TradingView, Yahoo Finance, or broker data.

Backtesting

Outputs:
backtest_equity.csv: Equity curve.
backtest_trades.csv: Trade details.
backtest_metrics.csv: Metrics (win rate, drawdown, Sharpe Ratio).
equity_curve.png: Equity plot.


Configure spreads, commissions, and slippage in config.yaml.

Structure

src/client.py: Capital.com API client.
src/strategies/: SMC and ICT strategies.
src/data_feed.py: Market data handling.
src/order_manager.py: Order placement and closing.
src/risk_manager.py: Risk management.
src/stop_loss_take_profit.py: Optimal SL/TP calculation.
src/early_exit.py: Early exit logic.
src/backtester.py: Advanced backtesting.
config.yaml: Configuration.
data/: Historical data.

Creating a ZIP
tar -a -c -f trading_app.zip trading_app

Notes

Replace YOUR_API_KEY, YOUR_API_SECRET, YOUR_ACCOUNT_ID in config.yaml.
Adjust backtest parameters (spread, commission, slippage_volatility) for realism.
Use CSV data for accurate backtesting over long periods.

