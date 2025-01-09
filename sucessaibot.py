from ast import main
import base64
import json
import sys
import signal
import datetime
import threading
import random
import time
from datetime import datetime,timedelta
from selenium.webdriver.common.by import By
from driver import companies, get_driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import queue
import numpy as np
import pandas as pd

# Global Variables
tr = 0
stop_threads_flag = False
previous_amount = 0
candles = []  # Holds processed candles
significant_reversals = {}
confirmed_reversals = {}
fast_ema_period = 0
signal1 = 0
signal_price = 0
slow_ema_period = 0
na=0
NUMBERS = {
    '0': '11', '1': '7', '2': '8', '3': '9', '4': '4', '5': '5', '6': '6', 
    '7': '1', '8': '2', '9': '3','.' : '10',
}
n1 = 0
STACK = {}
LENGTH_STACK_MIN = 460
LENGTH_STACK_MAX = 1000
CURRENCY = None
CURRENCY_CHANGE = False
CURRENCY_CHANGE_DATE = None
HISTORY_TAKEN = False
BASE_URL = 'https://pocketoption.com'
driver = get_driver()
def get_driver_instance():
    """
    This function simply returns the existing WebDriver instance.
    """
    global driver
    if driver is None:
        driver = get_driver()  # Initialize the WebDriver if not already initialized
    return driver

# Last processed time to ensure only fresh data is processed
last_processed_time = 0
last_processed_candle_time = None
# Function to load the WebDriver and open the page
def load_web_driver():
    url = f'{BASE_URL}/en/cabinet/demo-quick-high-low/'
    driver.get(url)
    print(f"WebDriver loaded with URL: {url}")

# Function to run websocket_log independently
def websocket_log(last_update_time):
    global STACK, CURRENCY,PERIOD, CURRENCY_CHANGE, CURRENCY_CHANGE_DATE, HISTORY_TAKEN, in_deposit, last_processed_time

    current_time = datetime.now()
    if (current_time - last_update_time).total_seconds() >= 1:  # Process every 1 seconds
        last_update_time = current_time  # Update the timestamp

        try:
            current_symbol = driver.find_element(by=By.CLASS_NAME, value='current-symbol').text
            if current_symbol != CURRENCY:
                CURRENCY = current_symbol
                CURRENCY_CHANGE = True
                CURRENCY_CHANGE_DATE = current_time
        except:
            pass

        if CURRENCY_CHANGE and CURRENCY_CHANGE_DATE < current_time - timedelta(seconds=5):
            STACK = {}
            HISTORY_TAKEN = False
            driver.refresh()
            CURRENCY_CHANGE = False
            set_platform()

        # Process WebSocket data
        for wsData in driver.get_log('performance'):
            message = json.loads(wsData['message'])['message']
            response = message.get('params', {}).get('response', {})
            if response.get('opcode', 0) == 2 and not CURRENCY_CHANGE:
                payload_str = base64.b64decode(response['payloadData']).decode('utf-8')
                data = json.loads(payload_str)
                if not HISTORY_TAKEN and 'history' in data and data['history']:
                    STACK = {int(d[0]): d[1] for d in data['history']}
                    PERIOD = data['period']
                    print(f"History taken for asset: {data['asset']}, period: {data['period']}, len_history: {len(data['history'])}, len_stack: {len(STACK)}")
                    HISTORY_TAKEN = True

                try:
                    symbol, timestamp, value = data[0]
                except:
                    continue

                if len(STACK) == LENGTH_STACK_MAX:
                    first_element = list(STACK.keys())[0]
                    if timestamp - first_element > PERIOD:
                        STACK = {k: v for k, v in STACK.items() if k > timestamp - LENGTH_STACK_MIN}
                STACK[timestamp] = value

    return last_update_time

# Function to handle trading logic, run independently in a thread
def trade_process():
    global STACK, candles, last_processed_time, fast_ema_period, slow_ema_period, last_processed_candle_time, n1
    global signal_price, tr, PERIOD
    processed_candles_count = 0
    if PERIOD == 5:
        fast_ema_period = 10
        slow_ema_period = 21
    elif PERIOD == 10:
        fast_ema_period = 8
        slow_ema_period = 16
    elif PERIOD == 15:
        fast_ema_period = 6
        slow_ema_period = 12
    else:
        fast_ema_period = 5
        slow_ema_period = 10
    while True:
        # Filter fresh data from STACK
        fresh_data = [(ts, price) for ts, price in STACK.items() if ts > last_processed_time]
        fresh_data.sort()  # Ensure data is sorted by timestamp

        while len(fresh_data) >= PERIOD:
            candle_data = fresh_data[:PERIOD]
            if candle_data:
                candle_time = candle_data[0][0] - (candle_data[0][0] % PERIOD)
                open_price = candle_data[0][1]
                high_price = open_price
                low_price = open_price
                close_price = open_price

                for ts, price in candle_data[1:]:
                    high_price = max(high_price, price)
                    low_price = min(low_price, price)
                    close_price = price

                candles.append({
                    'time': candle_time,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price
                })

                processed_candles_count += 1
                
                fresh_data = fresh_data[PERIOD:]  # Remove processed data points
             
                # Update the last processed timestamp
                last_processed_time = candle_data[-1][0]
        
        if len(candles) >= 10:
                 capture_reversal_points(candles)
                 fast_ema = calculate_ema(candles, fast_ema_period)
                 slow_ema = calculate_ema(candles, slow_ema_period)
                 signal_price = candles[-1]['close']

                 print(f"signal generated price:{signal_price}")
                 nearest_price = 0
                 min_diff = float('inf')  # Initialize the minimum difference to infinity
                 price = signal_price
                # Iterate through confirmed reversals and find the nearest price
                 for price in confirmed_reversals.keys():
                      diff = abs(price - signal_price)  # Calculate absolute difference
                      if diff < min_diff:
                          min_diff = diff
                          nearest_price = price
                 print(f"nearest price:{nearest_price}")
                # Signal generation logic 
                 if fast_ema > slow_ema and signal_price > fast_ema:
                         basic_signal = "call"
                         print(f"signal generated with candles:{basic_signal}")
                            
                 elif fast_ema < slow_ema and signal_price < fast_ema:
                         basic_signal = "put"
                         print(f"signal generated with candles:{basic_signal}")
                 else:
                         basic_signal = "hold"
                         print(f"signal generated with candles:{basic_signal}")  
                 if nearest_price > 0:
                         if basic_signal == "call" and nearest_price <= signal_price:
                                semi_final_signal = "call"
                         elif basic_signal == "put" and nearest_price >= signal_price:
                                semi_final_signal = "put"
                         else:
                                semi_final_signal = "Hold:1"
                 else:
                            semi_final_signal = "Hold"
                 print(f"snr signal: {semi_final_signal}") 
                 if semi_final_signal == "call" or semi_final_signal == "put" : 
                           f_signal = heiken_ashi_trading_logic(candles, window_size=2) 
                           if tr == 0 and f_signal == semi_final_signal:                                     
                                     do_action(semi_final_signal)
                                     dummy_work_with_countdown() 
        if len(candles) > 30:
            capture_reversal_points(candles)
            if n1 == 0:
                 n1 = n1 + 1
            candles.clear()    
            print(f"candles cleared")
            
        time.sleep(1)  # Wait for a second before checking again
def do_action(signal):
    global signal_price, CURRENCY, in_deposit, previous_amount, tradeprofit, PERIOD, na, candles, trade_profit, indeposit
    global signal1, tr
    tr = PERIOD+3
    print(f"signal : {signal}")
    driver = get_driver_instance()
      
    if signal1 != signal_price:
        print(f"market is trending :and final signal executed: {signal}")
        driver.find_element(by=By.CLASS_NAME, value=f'btn-{signal}').click()
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {signal.upper()}, currency: {CURRENCY} signal price: {signal_price}")
        signal1 = signal_price
        dummy_work_with_countdown()
        indeposit = in_deposit
        closed_trades = driver.find_elements(by=By.CLASS_NAME, value='deals-list__item')
        if closed_trades:
            last_split = closed_trades[0].text.split('\n')
            print("Last Split:", last_split)
            amount_won = last_split[4].replace('$', '').strip() 
            loss = last_split[3].replace('$', '').strip()
            try:
                amount = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#put-call-buttons-chart-1 > div > div.blocks-wrap > div.block.block--bet-amount > div.block__control.control > div.control__value.value.value--several-items > div > input[type=text]'))
                )

                dep = in_deposit / 10 
                if amount_won == '0':
                    if loss == '0':    
                          # If loss, move to the next Martingale value
                        next_amount = previous_amount * 2
                        tradeprofit -= previous_amount
                        print(f"trading profit:{tradeprofit}")
                    else:
                        next_amount = previous_amount
                        print(f"trading profit:{tradeprofit}")     
                         
                else:  # If win, reset to the first value
                    next_amount = previous_amount
                    tradeprofit += float(amount_won)
                    print(f"trading profit:{tradeprofit}")
                
                if dep < next_amount : 
                    next_amount = dep
                if next_amount < 1 :
                    next_amount = 1   
                trade_profit = tradeprofit
                next_amount = round(next_amount,2)    
                print(f"Next Trade amount: {next_amount}") 
                if next_amount != previous_amount:
                    amount.click()
                    base = '#modal-root > div > div > div > div > div.trading-panel-modal__in > div.virtual-keyboard > div > div:nth-child(%s) > div'
                    for char in str(next_amount):
                        driver.find_element(by=By.CSS_SELECTOR, value=base % NUMBERS[char]).click()
                        hand_delay()
                    hand_delay()         
                    amount.click()
                previous_amount = next_amount
            except Exception as e:
                print(f"Error updating amount: {e}")
        tr = 0
        
        pass
                    
    else:
        print(f"Market is consolidating or reverse")
        pass

def dummy_work_with_countdown():
    # Access the global PERIOD variable directly
    global PERIOD, duration
    duration = PERIOD + 2
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        remaining_time = int(end_time - time.time())
        print(f"\rWait till: {remaining_time} seconds remaining", end="")

def hand_delay():
    time.sleep(random.choice([0.2, 0.3, 0.4, 0.5, 0.6,1]))
def calculate_ema(candles, period):
    prices = [candle['close'] for candle in candles[-period:]]
    ema = sum(prices) / len(prices)  # Simple average for initial calculation
    multiplier = 2 / (period + 1)
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def capture_reversal_points(candles):
    global significant_reversals, confirmed_reversals

    # Ensure we have at least 50 candles before processing

    # If this is the first time we're processing, calculate reversals for the first 50 ca
    calculate_reversals(candles)

def calculate_reversals(candles):
    global significant_reversals, confirmed_reversals

    # Iterate through candles (except the first candle)
    for i in range(1, len(candles)):
        current_candle = candles[i]
        prev_candle = candles[i - 1]

        # Check for price reversal condition
        if current_candle['close'] < prev_candle['close']:  # Downward reversal
            reversal_price = current_candle['close']
            significant_reversals[reversal_price] = significant_reversals.get(reversal_price, {'count': 0, 'last_touched': current_candle['time']})
            significant_reversals[reversal_price]['count'] += 1

        elif current_candle['close'] > prev_candle['close']:  # Upward reversal
            reversal_price = current_candle['close']
            significant_reversals[reversal_price] = significant_reversals.get(reversal_price, {'count': 0, 'last_touched': current_candle['time']})
            significant_reversals[reversal_price]['count'] += 1

    # Populate confirmed_reversals
    confirmed_reversals = {price: data for price, data in significant_reversals.items() if data['count'] >= 2}

def heiken_ashi_trading_logic(candles, window_size=2):
    # Ensure there are at least `window_size` candles
    if len(candles) < window_size:
        print("Not enough candles for analysis.")
        return "neutral"
    
    # Get the last `window_size` candles
    recent_candles = candles[-window_size:]

    # Calculate Heikin Ashi candles for the 3 most recent candles
    heiken_ashi_candles = []
    for i in range(len(recent_candles)):
        if i == 0:
            ha_open = recent_candles[i]['open']
            ha_close = recent_candles[i]['close']
        else:
            ha_open = (heiken_ashi_candles[i-1]['open'] + heiken_ashi_candles[i-1]['close']) / 2
            ha_close = (recent_candles[i]['open'] + recent_candles[i]['high'] + recent_candles[i]['low'] + recent_candles[i]['close']) / 4

        ha_high = max(recent_candles[i]['high'], ha_open, ha_close)
        ha_low = min(recent_candles[i]['low'], ha_open, ha_close)

        heiken_ashi_candles.append({
            'open': ha_open,
            'close': ha_close,
            'high': ha_high,
            'low': ha_low,
        })

    # Perform price action momentum check for the last 3 Heikin Ashi candles
    high_low_diff = [c['high'] - c['low'] for c in heiken_ashi_candles]
    diff_increase = all(x < y for x, y in zip(high_low_diff, high_low_diff[1:]))  # Check if differences are increasing

    # Check for upward momentum (all closes > opens)
    if diff_increase and all(c['close'] > c['open'] for c in heiken_ashi_candles):
        print("Uptrend detected. Trigger Buy Signal.")
        return "call"
    # Check for downward momentum (all closes < opens)
    elif not diff_increase and all(c['close'] < c['open'] for c in heiken_ashi_candles):
        print("Downtrend detected. Trigger Sell Signal.")
        return "put"
    
    print("No clear trend detected.")
    return "hold"

def set_platform():
      global na, in_deposit, previous_amount, next_amount
      driver = get_driver_instance()
      if na == 0:
        next_amount = 1
        previous_amount = 1
        amount_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '#put-call-buttons-chart-1 > div > div.blocks-wrap > div.block.block--bet-amount > div.block__control.control > div.control__value.value.value--several-items > div > input[type=text]'))
        )
        
                     # Clear any pre-existing value and set the amount  
        amount_input.click()
                   # Click the amount input field (if required)
        base = '#modal-root > div > div > div > div > div.trading-panel-modal__in > div.virtual-keyboard > div > div:nth-child(%s) > div'
        for number in str(next_amount):
            driver.find_element(by=By.CSS_SELECTOR, value=base % NUMBERS[number]).click()
            hand_delay()
        hand_delay()    
        amount_input.click()
        deposit = driver.find_element(by=By.CSS_SELECTOR, value='body > div.wrapper > div.wrapper__top > header > div.right-block.js-right-block > div.right-block__item.js-drop-down-modal-open > div > div.balance-info-block__data > div.balance-info-block__balance > span')
        in_deposit = float(deposit.text.replace(',', ''))
        print(f"deposit :{in_deposit}")
        try:
            closed_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '#bar-chart > div > div > div.right-widget-container > div > div.widget-slot__header > div.divider > ul > li:nth-child(2) > a'))
            )
            hand_delay()
            closed_tab.click()
            hand_delay()
            closed_tab_parent = closed_tab.find_element(by=By.XPATH, value='..')
            if closed_tab_parent.get_attribute('class') == '':
                closed_tab_parent.click()                
        except Exception as e:
            print(f"Error closed value: {e}")
        na = 1
def signal_handler(signal, frame):
    """
    Handles termination signals (SIGTERM, SIGINT).
    Performs the exit logic based on your trade conditions.
    """
    global tradeprofit, in_deposit

    # Check if tradeprofit > 20 and in_deposit < 0
    if tradeprofit > 20 and in_deposit < 0:
        print("Exit conditions met: tradeprofit > 20 and in_deposit < 0.")
        graceful_exit()
    else:
        print("Exit conditions not met. Exiting program.")
        sys.exit(0) 

def graceful_exit():
    global driver, STACK, candles, significant_reversals, confirmed_reversals, tr, previous_amount, tradeprofit
    global signal_price, n1, CURRENCY, CURRENCY_CHANGE, HISTORY_TAKEN, in_deposit

    print("Exiting gracefully...")
    stop_threads()
    # Close the WebDriver instance
    try:
        if driver:
            driver.quit()
            print("WebDriver closed.")
    except Exception as e:
        print(f"Error closing WebDriver: {e}")

    # Clear global variables and data structures
    STACK.clear()
    candles.clear()
    significant_reversals.clear()
    confirmed_reversals.clear()

    tr = 0
    previous_amount = 0
    tradeprofit = 0
    signal_price = 0
    n1 = 0
    CURRENCY = None
    CURRENCY_CHANGE = False
    HISTORY_TAKEN = False
    in_deposit = None

    # Log any additional cleanup actions here
    print("Cleared all stored data.")

    # Exit the program
    sys.exit("Program terminated successfully.")
def stop_threads():
    for thread in threading.enumerate():
        if thread is not threading.current_thread():
            print(f"Stopping thread: {thread.name}")
            thread.join(timeout=1)

    print("All threads stopped.")

# Main function
if __name__ == "__main__":
    global PERIOD, in_deposit, tradeprofit
    PERIOD = 0
    tradeprofit = 0
    in_deposit = 2
    load_web_driver()
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    trade_thread = threading.Thread(target=trade_process, daemon=True)
    trade_thread.start()

    last_update_time = datetime.now()

    while True:
        try:
            if tradeprofit > 20 and in_deposit < 0:
                print("Exit conditions met: tradeprofit > 20 and in_deposit < 0.")
                graceful_exit()
            last_update_time = websocket_log(last_update_time)
        except Exception as e:
            print(f"Error in main: {e}")
            graceful_exit()