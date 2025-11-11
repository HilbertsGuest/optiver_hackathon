"""
Safe startup version with connection checking and retry logic
"""
import datetime as dt
import time
import logging
from optibook.synchronous_client import Exchange

logging.getLogger("client").setLevel("ERROR")

# Configuration
STOCK_A_ID = "PHILLIPS_A"
STOCK_B_ID = "PHILLIPS_B"
POSITION_LIMIT = 100
ARBITRAGE_THRESHOLD = 0.02
MIN_TRADE_VOLUME = 10
MAX_TRADE_VOLUME = 50
SLEEP_TIME = 0.2
POSITION_BUFFER = 5

print("=" * 70)
print("SAFE STARTUP - CONNECTION MANAGER")
print("=" * 70)

# Create exchange connection
exchange = Exchange()

# Try to connect with retry logic
max_retries = 3
retry_delay = 5

for attempt in range(max_retries):
    try:
        print(f"\nAttempt {attempt + 1}/{max_retries}: Connecting to exchange...")

        if exchange.is_connected():
            print("Already connected! Disconnecting first...")
            exchange.disconnect()
            time.sleep(2)

        exchange.connect()

        if exchange.is_connected():
            print("✓ Successfully connected!")
            break
        else:
            print(f"✗ Connection failed (not connected)")
            if attempt < max_retries - 1:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)

    except Exception as e:
        print(f"✗ Connection error: {e}")
        if "someone else logged in" in str(e).lower():
            print("\n⚠ ANOTHER SESSION IS ACTIVE!")
            print("Actions:")
            print("1. Close all other terminal windows running trading algos")
            print("2. Wait 30 seconds for old session to timeout")
            print("3. Run this script again")
            exit(1)

        if attempt < max_retries - 1:
            print(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)
else:
    print("\n✗ Failed to connect after all retries")
    print("Please check:")
    print("1. No other scripts are running")
    print("2. Credentials are correct")
    print("3. Exchange is online")
    exit(1)

# Display initial state
print("\n" + "=" * 70)
print("INITIAL STATE")
print("=" * 70)

try:
    positions = exchange.get_positions()
    pnl = exchange.get_pnl()

    print("\nCurrent Positions:")
    for instrument, position in positions.items():
        if position != 0:
            print(f"  {instrument}: {position}")

    if not any(positions.values()):
        print("  (No open positions)")

    # Calculate delta
    pos_a = positions.get(STOCK_A_ID, 0)
    pos_b = positions.get(STOCK_B_ID, 0)
    delta = pos_a + pos_b

    print(f"\nDelta (A+B): {delta}")
    print(f"P&L: ${pnl:.2f}")

    if abs(delta) > 10:
        print("\n⚠ WARNING: Large delta detected!")
        print(f"Current delta: {delta}")
        print("Consider manual rebalancing before starting automated trading")

        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Exiting...")
            exchange.disconnect()
            exit(0)

    if pnl < -100:
        print(f"\n⚠ WARNING: Significant losses detected (${pnl:.2f})")

        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Exiting...")
            exchange.disconnect()
            exit(0)

except Exception as e:
    print(f"Error getting initial state: {e}")
    exchange.disconnect()
    exit(1)

print("\n" + "=" * 70)
print("STARTING TRADING ALGORITHM")
print("=" * 70)
print(f"Instruments: {STOCK_A_ID} <-> {STOCK_B_ID}")
print(f"Arbitrage threshold: {ARBITRAGE_THRESHOLD:.2f}")
print(f"Trade volume range: {MIN_TRADE_VOLUME}-{MAX_TRADE_VOLUME} lots")
print(f"Sleep time: {SLEEP_TIME}s")
print("=" * 70)
print("\nPress Ctrl+C to stop safely\n")

iteration_count = 0
trades_executed = 0


def get_available_capacity(instrument_id, side):
    """Calculate how much we can trade without breaching limits"""
    positions = exchange.get_positions()
    current_position = positions.get(instrument_id, 0)

    if side == "bid":
        available = POSITION_LIMIT - current_position - POSITION_BUFFER
    else:
        available = current_position + POSITION_LIMIT - POSITION_BUFFER

    return max(0, available)


def calculate_dynamic_volume(spread, cheap_id, expensive_id):
    """Calculate optimal trade volume"""
    spread_based_volume = MIN_TRADE_VOLUME + int((spread / 0.10) * 10)
    desired_volume = min(spread_based_volume, MAX_TRADE_VOLUME)

    buy_capacity = get_available_capacity(cheap_id, "bid")
    sell_capacity = get_available_capacity(expensive_id, "ask")
    max_feasible = min(buy_capacity, sell_capacity)

    final_volume = min(desired_volume, max_feasible)
    return int(final_volume)


def execute_arbitrage(cheap_id, expensive_id, cheap_price, expensive_price, volume):
    """Execute paired trades"""
    global trades_executed

    if volume <= 0:
        return False

    total_profit = (expensive_price - cheap_price) * volume

    print(f"\n>>> ARBITRAGE [{iteration_count}] <<<")
    print(f"Buy {volume} lots {cheap_id} @ {cheap_price:.2f}")
    print(f"Sell {volume} lots {expensive_id} @ {expensive_price:.2f}")
    print(f"Expected profit: ${total_profit:.2f}")

    try:
        exchange.insert_order(
            instrument_id=cheap_id,
            price=cheap_price,
            volume=volume,
            side="bid",
            order_type="ioc",
        )

        exchange.insert_order(
            instrument_id=expensive_id,
            price=expensive_price,
            volume=volume,
            side="ask",
            order_type="ioc",
        )

        trades_executed += 1
        print(">>> Executed <<<")
        return True

    except Exception as e:
        print(f"Error executing trade: {e}")

        # Check if we got disconnected
        if not exchange.is_connected():
            print("\n⚠ DISCONNECTED! Exiting...")
            raise

        return False


try:
    while True:
        iteration_count += 1

        # Status update every 50 iterations
        if iteration_count % 50 == 1:
            print(f"\n{'-' * 70}")
            print(f"[{iteration_count}] {dt.datetime.now()}")

            positions = exchange.get_positions()
            pos_a = positions.get(STOCK_A_ID, 0)
            pos_b = positions.get(STOCK_B_ID, 0)
            delta = pos_a + pos_b
            pnl = exchange.get_pnl()

            print(f"Positions: A={pos_a:+.0f}, B={pos_b:+.0f}, Delta={delta:+.0f}")
            print(f"P&L: ${pnl:.2f} | Trades: {trades_executed}")

        # Check connection
        if not exchange.is_connected():
            print("\n⚠ Lost connection to exchange!")
            raise Exception("Connection lost")

        # Get orderbooks
        book_a = exchange.get_last_price_book(STOCK_A_ID)
        book_b = exchange.get_last_price_book(STOCK_B_ID)

        # Validate orderbooks
        if not (book_a and book_a.bids and book_a.asks):
            time.sleep(SLEEP_TIME)
            continue

        if not (book_b and book_b.bids and book_b.asks):
            time.sleep(SLEEP_TIME)
            continue

        # Extract prices
        a_bid = book_a.bids[0].price
        a_ask = book_a.asks[0].price
        b_bid = book_b.bids[0].price
        b_ask = book_b.asks[0].price

        a_mid = (a_bid + a_ask) / 2
        b_mid = (b_bid + b_ask) / 2
        spread = abs(a_mid - b_mid)

        # Check for arbitrage
        if spread >= ARBITRAGE_THRESHOLD:
            if a_mid > b_mid + ARBITRAGE_THRESHOLD:
                volume = calculate_dynamic_volume(spread, STOCK_B_ID, STOCK_A_ID)
                if volume > 0:
                    execute_arbitrage(STOCK_B_ID, STOCK_A_ID, b_ask, a_bid, volume)

            elif b_mid > a_mid + ARBITRAGE_THRESHOLD:
                volume = calculate_dynamic_volume(spread, STOCK_A_ID, STOCK_B_ID)
                if volume > 0:
                    execute_arbitrage(STOCK_A_ID, STOCK_B_ID, a_ask, b_bid, volume)

        time.sleep(SLEEP_TIME)

except KeyboardInterrupt:
    print("\n\n⚠ Stopped by user")

except Exception as e:
    print(f"\n\n⚠ Error occurred: {e}")

finally:
    print("\nShutting down safely...")

    # Final state
    try:
        positions = exchange.get_positions()
        pnl = exchange.get_pnl()
        pos_a = positions.get(STOCK_A_ID, 0)
        pos_b = positions.get(STOCK_B_ID, 0)
        delta = pos_a + pos_b

        print("\n" + "=" * 70)
        print("FINAL STATE")
        print("=" * 70)
        print(f"Iterations: {iteration_count}")
        print(f"Trades executed: {trades_executed}")
        print(f"Final positions: A={pos_a:+.0f}, B={pos_b:+.0f}, Delta={delta:+.0f}")
        print(f"Final P&L: ${pnl:.2f}")
        print("=" * 70)

    except:
        pass

    # Disconnect cleanly
    if exchange.is_connected():
        print("Disconnecting...")
        exchange.disconnect()
        print("✓ Disconnected")
