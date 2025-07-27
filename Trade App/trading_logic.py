# file: trading_logic.py
import os
import time
import pandas as pd
from selenium import webdriver
from dhanhq.dhanhq import dhanhq
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.support import expected_conditions as EC

# This is the main function that the GUI will call.
def run_trading_script(link, total_amount, profit_percent, loss_percent, no_of_stocks_to_buy, CLIENT_ID, ACCESS_TOKEN, log_callback):
    
    # --- Helper and Core Logic Functions (Nested for encapsulation) ---

    def round_to_tick(price, tick=0.05):
        return round(price / tick) * tick

    def place_single_order(seq_id, price, amount, loss_percent, name, profit_percent, symbol):
        """Places a single buy order followed by Stop-Loss and Target orders."""
        try:
            dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
            quantity = int(amount / price)
            if quantity == 0:
                log_callback(f"Stock {name} is too expensive for the allocated amount. Skipping.")
                return 0
            
            log_callback(f"\nAttempting to place a BUY for {name} (Quantity: {quantity})")
            response = dhan.place_order(
                security_id=seq_id,
                exchange_segment=dhan.NSE,
                transaction_type=dhan.BUY,
                quantity=quantity,
                order_type=dhan.MARKET,
                product_type=dhan.INTRA,
                price=0
            )
            
            log_callback(f"--> Buy Order Response for {name}: {response.get('status', 'N/A')}")
            
            if response and response.get("status") == "success":
                s_loss = round_to_tick(price - price * (loss_percent / 100))
                s_loss_bar = round_to_tick(price - price * ((loss_percent + 0.2) / 100))
                s_profit = round_to_tick(price + price * (profit_percent / 100))

                log_callback(f"Placing Stop-Loss for {name} at Trigger {s_loss}...")
                sl_response = dhan.place_order(
                    security_id=seq_id,
                    exchange_segment=dhan.NSE,
                    transaction_type=dhan.SELL,
                    quantity=quantity,
                    order_type=dhan.SL,
                    product_type=dhan.INTRA,
                    price=s_loss_bar,
                    trigger_price=s_loss
                )
                if sl_response and sl_response.get("status") == "failure":
                    log_callback(f"--> WARNING: Failed to place Stop-Loss for {name}. Please place it manually.")
                else:
                    log_callback(f"--> Stop-Loss placed successfully for {name}.")

                log_callback(f"Placing Target for {name} at {s_profit}...")
                profit_response = dhan.place_order(
                    security_id=seq_id,
                    exchange_segment=dhan.NSE,
                    transaction_type=dhan.SELL,
                    quantity=quantity,
                    order_type=dhan.LIMIT,
                    product_type=dhan.INTRA,
                    price=s_profit
                )
                if profit_response and profit_response.get("status") == "failure":
                    log_callback(f"--> WARNING: Failed to place Profit Target for {name}. Please place it manually.")
                else:
                    log_callback(f"--> Profit Target placed successfully for {name}.")
            else:
                log_callback(f"Buy order failed for {name}. Halting further orders for this stock.")
            return 0
        except Exception as e:
            log_callback(f"An unexpected error occurred while placing order for {name}: {e}")
            return -1

    def initiate_buy(seq_ids, names, prices, symbols):
        """Uses a thread pool to place orders for multiple stocks concurrently."""
        if not no_of_stocks_to_buy or no_of_stocks_to_buy == 0:
            log_callback("Number of stocks to buy is zero. No trades will be placed.")
            return
            
        amount_per_stock = total_amount / no_of_stocks_to_buy
        log_callback(f"\nInitiating buys. Amount per stock: ₹{amount_per_stock:.2f}")

        with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
            futures = [
                executor.submit(place_single_order, seq_id, price, amount_per_stock, loss_percent, name, profit_percent, symbol)
                for price, symbol, seq_id, name in zip(prices, symbols, seq_ids, names)
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    log_callback(f"A trading thread failed with an error: {e}")

    def get_seq_id(symbols):
        """Retrieves Dhan security IDs from the local equity.csv file."""
        try:
            df = pd.read_csv('equity.csv', header=None, low_memory=False)
        except FileNotFoundError:
            log_callback("FATAL ERROR: equity.csv not found! Please place it in the application folder.")
            return None
            
        filtered_df = df[(df[0] == 'NSE') & (df.apply(lambda row: 'EQ' in str(row.values), axis=1))]
        seq_ids = []
        for symbol in symbols:
            # Find rows where the symbol is present
            sub_filtered = filtered_df[filtered_df[1] == symbol]
            if not sub_filtered.empty:
                seq_ids.append(sub_filtered.iloc[0, 2])
            else:
                log_callback(f"--> WARNING: Could not find security ID for symbol: {symbol}. It will be skipped.")
        return seq_ids

    def get_data(link, no_of_stocks):
        """Uses Selenium to download stock data from a Chartink screener."""
        log_callback("Initializing browser to fetch data from Chartink...")
        chromedriver_path = os.path.join(os.getcwd(), "drivers", "chromedriver.exe")
        
        if not os.path.exists(chromedriver_path):
            log_callback(f"FATAL ERROR: chromedriver.exe not found in '{os.path.join(os.getcwd(), 'drivers')}'")
            return None, None, None, None

        options = webdriver.ChromeOptions()
        # Run Chrome in "headless" mode so the user doesn't see a browser window
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        prefs = {"download.default_directory": os.getcwd(), "download.prompt_for_download": False, "directory_upgrade": True}
        options.add_experimental_option("prefs", prefs)
        
        driver = None
        try:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(link)
            log_callback("Running scan on Chartink...")
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CLASS_NAME, 'run_scan_button'))).click()
            log_callback("Downloading CSV...")
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[span[text()='CSV']]"))).click()
        except Exception as e:
            log_callback(f"FATAL ERROR during browser operation: {e}")
            if driver:
                driver.quit()
            return None, None, None, None

        # Wait for the download to complete
        csv_filename = "NB 001 Buy, Technical Analysis Scanner.csv"
        csv_path = os.path.join(os.getcwd(), csv_filename)
        for _ in range(40): # Wait up to 4 seconds
            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                break
            time.sleep(0.1)
        
        driver.quit()

        if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
            log_callback("ERROR: CSV file was not downloaded or is empty. Check Chartink link and permissions.")
            return None, None, None, None

        log_callback("CSV downloaded. Processing data...")
        df = pd.read_csv(csv_path)
        os.remove(csv_path) # Clean up by deleting the downloaded file

        if df.empty or df.shape[0] == 0:
            log_callback("No stocks found from the scan. The script will not place any trades.")
            return [], [], [], []

        symbols = df.iloc[:no_of_stocks, 2].tolist()
        names = df.iloc[:no_of_stocks, 1].tolist()
        prices = df.iloc[:no_of_stocks, 5].tolist()
        
        log_callback(f"Found {len(symbols)} stocks to trade: {', '.join(symbols)}")
        seq_ids = get_seq_id(symbols)
        
        # Check if we have a valid security ID for each symbol found
        if seq_ids is None or len(seq_ids) != len(symbols):
            log_callback("ERROR: Could not retrieve Security IDs for all symbols. Halting.")
            return None, None, None, None

        return seq_ids, names, symbols, prices

    # --- Main Execution Flow of the Script ---
    try:
        log_callback("--- Starting Trading Script ---")
        seq_ids, names, symbols, prices = get_data(link, no_of_stocks_to_buy)
        
        if seq_ids is None:
             log_callback("Halting execution due to critical error during data fetching.")
             return
        
        if not symbols:
            log_callback("No symbols to process. Script finished.")
            return

        initiate_buy(seq_ids, names, prices, symbols)
            
        log_callback("\n--- Trading Script Finished ---")

    except Exception as e:
        log_callback(f"\n--- A CRITICAL UNHANDLED ERROR OCCURRED: {e} ---")
        log_callback("--- Script execution has been terminated. ---")
        