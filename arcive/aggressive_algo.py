import datetime as dt
import time
import logging

from optibook.synchronous_client import Exchange

exchange = Exchange()
exchange.connect()

logging.getLogger("client").setLevel("ERROR")

# AGGRESSIVE Configuration - Optimized for maximum throughput
STOCK_A_ID = "PHILLIPS_A"
STOCK_B_ID = "PHILLIPS_B"
POSITION_LIMIT = 100
ARBITRAGE_THRESHOLD = 0.02  # AGGRESSIVE: Lower threshold = more trades
MIN_TRADE_VOLUME = 10  # AGGRESSIVE: Larger minimum size
MAX_TRADE_VOLUME = 50  # AGGRESSIVE: Can trade up to 50 lots at once
SLEEP_TIME = 0.2  # AGGRESSIVE: 5x faster iteration (0.2s vs 1s)
POSITION_BUFFER = 5  # Safety buffer from position limit


def get_available_capacity(instrument_id, side):
    """Calculate how much we can trade without breaching limits"""
    positions = exchange.get_positions()
    current_position = positions.get(instrument_id, 0)

    if side == "bid":
        # Buying increases position
        available = POSITION_LIMIT - current_position - POSITION_BUFFER
    else:  # ask
        # Selling decreases position
        available = current_position + POSITION_LIMIT - POSITION_BUFFER

    return max(0, available)


def calculate_dynamic_volume(spread, cheap_id, expensive_id):
    """
    Calculate optimal trade volume based on:
    1. Arbitrage spread size (bigger spread = bigger trade)
    2. Available position capacity
    3. Configured min/max bounds
    """
    # Scale volume with spread: trade more when spread is larger
    # For every 0.10 spread, add 10 lots to base volume
    spread_based_volume = MIN_TRADE_VOLUME + int((spread / 0.10) * 10)

    # Cap at maximum
    desired_volume = min(spread_based_volume, MAX_TRADE_VOLUME)

    # Check available capacity for both legs
    buy_capacity = get_available_capacity(cheap_id, "bid")
    sell_capacity = get_available_capacity(expensive_id, "ask")

    # Can only trade the minimum of what both sides allow
    max_feasible = min(buy_capacity, sell_capacity)

    # Final volume is the smaller of desired and feasible
    final_volume = min(desired_volume, max_feasible)

    return int(final_volume)


def print_positions_and_pnl(always_display=None):
    """Display current positions and P&L"""
    positions = exchange.get_positions()
    print("Positions:")
    for instrument_id in positions:
        if (
            not always_display
            or instrument_id in always_display
            or positions[instrument_id] != 0
        ):
            print(f"  {instrument_id:20s}: {positions[instrument_id]:4.0f}")

    # Calculate delta (should be close to 0)
    pos_a = positions.get(STOCK_A_ID, 0)
    pos_b = positions.get(STOCK_B_ID, 0)
    delta = pos_a + pos_b
    print(f"  {'Delta (A+B)':20s}: {delta:4.0f}")

    # Show position utilization
    max_abs_pos = max(abs(pos_a), abs(pos_b))
    utilization = (max_abs_pos / POSITION_LIMIT) * 100
    print(f"  {'Position Util':20s}: {utilization:4.1f}%")

    pnl = exchange.get_pnl()
    if pnl:
        print(f"\nPnL: {pnl:.2f}")


def execute_arbitrage(cheap_id, expensive_id, cheap_price, expensive_price, volume):
    """Execute paired trades: buy cheap, sell expensive"""
    if volume <= 0:
        print(f"Volume too small ({volume}), skipping trade")
        return False

    total_profit = (expensive_price - cheap_price) * volume

    print(f"\n>>> ARBITRAGE EXECUTING <<<")
    print(f"Buy {volume} lots {cheap_id} @ {cheap_price:.2f}")
    print(f"Sell {volume} lots {expensive_id} @ {expensive_price:.2f}")
    print(f"Profit: {total_profit:.2f} ({expensive_price - cheap_price:.2f}/lot)")

    # Execute both legs simultaneously
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

        print(">>> Trades executed <<<")
        return True
    except Exception as e:
        print(f"Error executing trade: {e}")
        return False


# Main trading loop
print("=" * 70)
print("AGGRESSIVE DELTA-NEUTRAL ARBITRAGE STRATEGY")
print("=" * 70)
print(f"Instruments: {STOCK_A_ID} <-> {STOCK_B_ID}")
print(f"Arbitrage threshold: {ARBITRAGE_THRESHOLD:.2f}")
print(f"Trade volume range: {MIN_TRADE_VOLUME}-{MAX_TRADE_VOLUME} lots (dynamic)")
print(f"Iteration speed: {SLEEP_TIME}s ({1/SLEEP_TIME:.1f} iterations/sec)")
print(f"Position limit: ±{POSITION_LIMIT} lots")
print("=" * 70)
print("\nAGGRESSIVE MODE OPTIMIZATIONS:")
print("  - 5x faster iteration (0.2s vs 1.0s)")
print("  - Lower threshold (0.02 vs 0.10) = more opportunities")
print("  - Dynamic volume scaling (10-50 lots vs fixed 5)")
print("  - Aggressive position utilization up to ±95 lots")
print("=" * 70)

iteration_count = 0
trades_executed = 0

while True:
    iteration_count += 1

    # Compact output every iteration, detailed every 10
    if iteration_count % 10 == 1:
        print(f"\n{'-' * 70}")
        print(f"ITERATION {iteration_count} AT {str(dt.datetime.now()):18s} UTC")
        print(f"{'-' * 70}")
        print_positions_and_pnl(always_display=[STOCK_A_ID, STOCK_B_ID])
        print(f"Total trades executed: {trades_executed}")
        print("")

    # Get both orderbooks
    book_a = exchange.get_last_price_book(STOCK_A_ID)
    book_b = exchange.get_last_price_book(STOCK_B_ID)

    # Validate both orderbooks have data
    if not (book_a and book_a.bids and book_a.asks):
        print(f"[{iteration_count}] Orderbook for {STOCK_A_ID} incomplete")
        time.sleep(SLEEP_TIME)
        continue

    if not (book_b and book_b.bids and book_b.asks):
        print(f"[{iteration_count}] Orderbook for {STOCK_B_ID} incomplete")
        time.sleep(SLEEP_TIME)
        continue

    # Extract best prices
    a_bid = book_a.bids[0].price
    a_ask = book_a.asks[0].price
    b_bid = book_b.bids[0].price
    b_ask = book_b.asks[0].price

    # Calculate midpoints
    a_mid = (a_bid + a_ask) / 2
    b_mid = (b_bid + b_ask) / 2

    # Calculate spread
    spread = abs(a_mid - b_mid)

    # Only print prices on detailed iterations
    if iteration_count % 10 == 1:
        print(f"{STOCK_A_ID:15s}: Bid={a_bid:7.2f}  Ask={a_ask:7.2f}  Mid={a_mid:7.2f}")
        print(f"{STOCK_B_ID:15s}: Bid={b_bid:7.2f}  Ask={b_ask:7.2f}  Mid={b_mid:7.2f}")
        print(f"Spread: {spread:.2f}")

    # Check for arbitrage opportunity
    if spread < ARBITRAGE_THRESHOLD:
        if iteration_count % 10 == 1:
            print(f"No arbitrage: {spread:.2f} < {ARBITRAGE_THRESHOLD:.2f}")
    else:
        # Determine which side is expensive
        if a_mid > b_mid + ARBITRAGE_THRESHOLD:
            # A is overpriced, B is underpriced
            # Calculate optimal volume
            volume = calculate_dynamic_volume(spread, STOCK_B_ID, STOCK_A_ID)

            if volume > 0:
                print(f"\n[{iteration_count}] A overpriced by {spread:.2f}")
                success = execute_arbitrage(
                    cheap_id=STOCK_B_ID,
                    expensive_id=STOCK_A_ID,
                    cheap_price=b_ask,
                    expensive_price=a_bid,
                    volume=volume
                )
                if success:
                    trades_executed += 1

        elif b_mid > a_mid + ARBITRAGE_THRESHOLD:
            # B is overpriced, A is underpriced
            volume = calculate_dynamic_volume(spread, STOCK_A_ID, STOCK_B_ID)

            if volume > 0:
                print(f"\n[{iteration_count}] B overpriced by {spread:.2f}")
                success = execute_arbitrage(
                    cheap_id=STOCK_A_ID,
                    expensive_id=STOCK_B_ID,
                    cheap_price=a_ask,
                    expensive_price=b_bid,
                    volume=volume
                )
                if success:
                    trades_executed += 1

    time.sleep(SLEEP_TIME)
