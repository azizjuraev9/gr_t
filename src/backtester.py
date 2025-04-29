import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
from typing import Dict, List, Optional
from datetime import datetime
from src.data_feed import DataFeed
from src.strategies.smc import SMCStrategy
from src.strategies.ict import ICTStrategy
from src.order_manager import OrderManager
from src.risk_manager import RiskManager
from src.stop_loss_take_profit import StopLossTakeProfit
from src.early_exit import EarlyExit

class Backtester:
    def __init__(self, smc_strategy: SMCStrategy, ict_strategy: ICTStrategy, data_feed: DataFeed,
                 order_manager: OrderManager, risk_manager: RiskManager, sl_tp_calculator: StopLossTakeProfit,
                 early_exit: EarlyExit, config: Dict):
        self.smc_strategy = smc_strategy
        self.ict_strategy = ict_strategy
        self.data_feed = data_feed
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.sl_tp_calculator = sl_tp_calculator
        self.early_exit = early_exit
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.equity = []
        self.trades = []
        self.open_positions = []

    async def run(self, start_date: str, end_date: str, initial_balance: float) -> None:
        """Запуск бэктестинга с учётом спредов, проскальзывания и комиссий."""
        try:
            self.logger.info(f"Starting backtest from {start_date} to {end_date}")
            balance = initial_balance
            self.equity.append(balance)
            self.risk_manager.update_balance(balance)

            # Загрузка данных из CSV
            data = self._load_data(start_date, end_date)
            if data.empty:
                self.logger.error("No data for backtesting")
                return

            # Основной цикл
            for i in range(1, len(data)):
                window = data.iloc[:i+1]
                current_price = data.iloc[i]["close"]
                current_time = data.iloc[i]["timestamp"]

                # Подмена data_feed для стратегий
                self.smc_strategy.data_feed.get_data = lambda *args, **kwargs: window
                self.ict_strategy.data_feed.get_data = lambda *args, **kwargs: window
                self.early_exit.data_feed.get_data = lambda *args, **kwargs: window

                # Выполнение стратегий
                await self.smc_strategy.execute()
                await self.ict_strategy.execute()

                # Проверка открытых позиций
                await self._process_positions(current_price, current_time, window)

                # Проверка досрочного выхода
                await self.early_exit.check_positions(self.smc_strategy.symbol, self.smc_strategy.timeframe)

                # Обновление баланса
                balance = self.risk_manager.account_balance
                self.equity.append(balance)

            # Закрытие всех позиций в конце
            await self._close_all_positions(data.iloc[-1]["close"])

            # Сохранение результатов
            self._save_results()
            self._calculate_metrics()
            self._plot_equity_curve()
            self.logger.info(f"Backtest completed. Final balance: {balance}")

        except Exception as e:
            self.logger.error(f"Backtest error: {e}")

    def _load_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Загрузка исторических данных из CSV."""
        try:
            symbol = self.smc_strategy.symbol
            timeframe = self.smc_strategy.timeframe
            file_path = f"data/{symbol}_{timeframe}.csv"
            df = pd.read_csv(file_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df[(df["timestamp"] >= start_date) & (df["timestamp"] <= end_date)]
            if df.empty:
                self.logger.warning(f"No data found in {file_path} for specified period")
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            return pd.DataFrame()

    async def place_order(self, symbol: str, direction: str, size: float, price: float,
                          stop_loss: float, take_profit: float) -> None:
        """Симуляция размещения ордера с учётом спреда и проскальзывания."""
        try:
            # Учёт спреда
            spread = self.config["spread"]  # Например, 0.00015 для EURUSD
            if direction.upper() == "BUY":
                entry_price = price + spread / 2
            else:
                entry_price = price - spread / 2

            # Учёт проскальзывания
            slippage = self._calculate_slippage()
            entry_price += slippage if direction.upper() == "BUY" else -slippage

            # Сохранение позиции
            position = {
                "symbol": symbol,
                "direction": direction.upper(),
                "size": size,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "open_time": datetime.now(),
                "deal_id": f"BACKTEST_{len(self.open_positions)}"
            }
            self.open_positions.append(position)
            self.logger.info(f"Backtest order placed: {position}")

        except Exception as e:
            self.logger.error(f"Error placing backtest order: {e}")

    async def _process_positions(self, current_price: float, current_time: datetime, data: pd.DataFrame) -> None:
        """Обработка открытых позиций (проверка SL/TP)."""
        for pos in self.open_positions[:]:
            profit = 0
            close_position = False

            # Проверка SL/TP
            if pos["direction"] == "BUY":
                if current_price <= pos["stop_loss"]:
                    profit = (pos["stop_loss"] - pos["entry_price"]) * pos["size"]
                    close_position = True
                elif current_price >= pos["take_profit"]:
                    profit = (pos["take_profit"] - pos["entry_price"]) * pos["size"]
                    close_position = True
            else:  # SELL
                if current_price >= pos["stop_loss"]:
                    profit = (pos["entry_price"] - pos["stop_loss"]) * pos["size"]
                    close_position = True
                elif current_price <= pos["take_profit"]:
                    profit = (pos["entry_price"] - pos["take_profit"]) * pos["size"]
                    close_position = True

            # Учёт комиссий
            if close_position:
                commission = pos["size"] * self.config["commission"]
                profit -= commission
                self.trades.append({
                    "symbol": pos["symbol"],
                    "direction": pos["direction"],
                    "entry_price": pos["entry_price"],
                    "exit_price": current_price,
                    "size": pos["size"],
                    "profit": profit,
                    "open_time": pos["open_time"],
                    "close_time": current_time
                })
                self.risk_manager.update_balance(self.risk_manager.account_balance + profit)
                self.open_positions.remove(pos)
                self.logger.info(f"Position closed: {pos['deal_id']}, Profit: {profit}")

    async def _close_all_positions(self, current_price: float) -> None:
        """Закрытие всех открытых позиций в конце бэктеста."""
        for pos in self.open_positions[:]:
            profit = (current_price - pos["entry_price"]) * pos["size"] if pos["direction"] == "BUY" else \
                     (pos["entry_price"] - current_price) * pos["size"]
            commission = pos["size"] * self.config["commission"]
            profit -= commission
            self.trades.append({
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "entry_price": pos["entry_price"],
                "exit_price": current_price,
                "size": pos["size"],
                "profit": profit,
                "open_time": pos["open_time"],
                "close_time": datetime.now()
            })
            self.risk_manager.update_balance(self.risk_manager.account_balance + profit)
            self.open_positions.remove(pos)
            self.logger.info(f"Position closed at end: {pos['deal_id']}, Profit: {profit}")

    def _calculate_slippage(self) -> float:
        """Рассчёт проскальзывания (случайное отклонение)."""
        volatility = self.config["slippage_volatility"]  # Например, 0.0001
        return np.random.normal(0, volatility)

    def _calculate_metrics(self) -> None:
        """Рассчёт метрик производительности."""
        try:
            equity_series = pd.Series(self.equity)
            returns = equity_series.pct_change().dropna()
            total_trades = len(self.trades)
            win_trades = sum(1 for t in self.trades if t["profit"] > 0)
            win_rate = win_trades / total_trades if total_trades > 0 else 0
            max_drawdown = (equity_series / equity_series.cummax() - 1).min()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0

            metrics = {
                "total_trades": total_trades,
                "win_rate": win_rate,
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe_ratio,
                "final_balance": self.equity[-1],
                "profit_factor": sum(t["profit"] for t in self.trades if t["profit"] > 0) / \
                                 abs(sum(t["profit"] for t in self.trades if t["profit"] < 0)) if any(t["profit"] < 0 for t in self.trades) else float("inf")
            }
            pd.DataFrame([metrics]).to_csv("backtest_metrics.csv")
            self.logger.info(f"Metrics: {metrics}")
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {e}")

    def _plot_equity_curve(self) -> None:
        """Построение графика эквити."""
        try:
            plt.figure(figsize=(10, 6))
            plt.plot(self.equity, label="Equity")
            plt.title("Backtest Equity Curve")
            plt.xlabel("Trade")
            plt.ylabel("Balance")
            plt.legend()
            plt.grid(True)
            plt.savefig("equity_curve.png")
            plt.close()
            self.logger.info("Equity curve saved to equity_curve.png")
        except Exception as e:
            self.logger.error(f"Error plotting equity curve: {e}")

    def _save_results(self) -> None:
        """Сохранение результатов бэктестинга."""
        try:
            pd.Series(self.equity).to_csv("backtest_equity.csv")
            pd.DataFrame(self.trades).to_csv("backtest_trades.csv")
            self.logger.info("Backtest results saved to backtest_equity.csv and backtest_trades.csv")
        except Exception as e:
            self.logger.error(f"Failed to save backtest results: {e}")