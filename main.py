import asyncio
import logging
from src.client import CapitalClient
from src.strategies.smc import SMCStrategy
from src.strategies.ict import ICTStrategy
from src.config import load_config
from src.logger import setup_logger
from src.data_feed import DataFeed
from src.order_manager import OrderManager
from src.risk_manager import RiskManager
from src.stop_loss_take_profit import StopLossTakeProfit
from src.early_exit import EarlyExit
from src.backtester import Backtester

async def main():
    setup_logger()
    logger = logging.getLogger(__name__)
    logger.info("Starting trading application")

    config = load_config("config.yaml")
    client = CapitalClient(
        api_key=config["capital"]["api_key"],
        api_secret=config["capital"]["api_secret"],
        account_id=config["capital"]["account_id"]
    )
    data_feed = DataFeed(client)
    order_manager = OrderManager(client)
    risk_manager = RiskManager(
        max_risk_per_trade=config["trading"]["max_risk_per_trade"],
        account_balance=config["trading"]["account_balance"]
    )
    sl_tp_calculator = StopLossTakeProfit(config["sl_tp"])
    early_exit = EarlyExit(config["early_exit"], data_feed, order_manager)

    smc_strategy = SMCStrategy(
        symbol=config["trading"]["symbol"],
        timeframe=config["trading"]["timeframe"],
        data_feed=data_feed,
        order_manager=order_manager,
        risk_manager=risk_manager,
        sl_tp_calculator=sl_tp_calculator,
        early_exit=early_exit,
        config=config["strategies"]["smc"]
    )
    ict_strategy = ICTStrategy(
        symbol=config["trading"]["symbol"],
        timeframe=config["trading"]["timeframe"],
        data_feed=data_feed,
        order_manager=order_manager,
        risk_manager=risk_manager,
        sl_tp_calculator=sl_tp_calculator,
        early_exit=early_exit,
        config=config["strategies"]["ict"]
    )

    if config["mode"] == "backtest":
        backtester = Backtester(
            smc_strategy, ict_strategy, data_feed, order_manager, risk_manager,
            sl_tp_calculator, early_exit, config["backtest"]
        )
        # Перехват размещения ордеров для бэктестинга
        smc_strategy.order_manager.place_order = backtester.place_order
        ict_strategy.order_manager.place_order = backtester.place_order
        await backtester.run(
            start_date=config["backtest"]["start_date"],
            end_date=config["backtest"]["end_date"],
            initial_balance=config["trading"]["account_balance"]
        )
    else:
        try:
            while True:
                await smc_strategy.execute()
                await ict_strategy.execute()
                await early_exit.check_positions(smc_strategy.symbol, smc_strategy.timeframe)
                await asyncio.sleep(config["trading"]["poll_interval"])
        except KeyboardInterrupt:
            logger.info("Shutting down")
        except Exception as e:
            logger.error(f"Main loop error: {e}")

if __name__ == "__main__":
    asyncio.run(main())