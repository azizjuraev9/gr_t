import yfinance as yf
import pandas as pd
import logging
import os
from datetime import datetime
from typing import Optional

def setup_logger() -> None:
    """Настройка логирования."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("import_data.log")
        ]
    )

def import_yfinance_data(symbol: str, timeframe: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Загрузка данных с Yahoo Finance."""
    logger = logging.getLogger(__name__)
    try:
        # Преобразование таймфрейма в формат yfinance
        timeframe_map = {
            "MINUTE_1": "1m",
            "MINUTE_5": "5m",
            "MINUTE_15": "15m",
            "HOUR_1": "1h",
            "DAY": "1d"
        }
        yf_timeframe = timeframe_map.get(timeframe, "5m")
        
        # Загрузка данных
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_date,
            end=end_date,
            interval=yf_timeframe,
            auto_adjust=False,
            prepost=False
        )
        
        if df.empty:
            logger.warning(f"No data found for {symbol} on {timeframe}")
            return None
            
        # Форматирование данных
        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        
        logger.info(f"Imported {len(df)} rows for {symbol} on {timeframe}")
        return df
        
    except Exception as e:
        logger.error(f"Error importing data from Yahoo Finance: {e}")
        return None

def save_data(df: pd.DataFrame, symbol: str, timeframe: str, output_dir: str = "data") -> None:
    """Сохранение данных в CSV."""
    logger = logging.getLogger(__name__)
    try:
        # Создание директории, если не существует
        os.makedirs(output_dir, exist_ok=True)
        
        # Формирование имени файла
        filename = f"{output_dir}/{symbol.replace('=X', '')}_{timeframe}.csv"
        
        # Сохранение
        df.to_csv(filename, index=False)
        logger.info(f"Data saved to {filename}")
        
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def main():
    setup_logger()
    logger = logging.getLogger(__name__)
    
    # Настройки
    symbol = "XAUT-USD"  # Символ для Yahoo Finance
    timeframe = "MINUTE_5"  # Таймфрейм
    start_date = "2025-01-01"
    end_date = "2025-04-27"
    output_dir = "data"
    
    logger.info(f"Starting data import for {symbol} ({timeframe}) from {start_date} to {end_date}")
    
    # Загрузка данных
    df = import_yfinance_data(symbol, timeframe, start_date, end_date)
    
    if df is not None:
        # Сохранение данных
        save_data(df, symbol, timeframe, output_dir)
    else:
        logger.error("Failed to import data")

if __name__ == "__main__":
    main()