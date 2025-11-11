"""
Clean Dual Listing Arbitrage Strategy
Directly implements goals from goals.md:
1. Price discrepancy between orderbooks
2. Delta approaching zero strategy
3. Bid-ask spread management
4. Dual listing arbitrage (PHILLIPS_A / PHILLIPS_B)
5. Arbitrage strategy
"""

import datetime as dt
import time
import logging
from optibook.synchronous_client import Exchange

# Setup
exchange = Exchange()
logging.getLogger("client").setLevel("ERROR")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Dual listing instruments
STOCK_A = "PHILLIPS_A"
STOCK_B = "PHILLIPS_B"

# Risk limits
POSITION_LIMIT = 100
POSITION_BUFFER = 5  # Safety margin

# Arbitrage parameters
ARBITRAGE_THRESHOLD = 0.05  # Minimum price discrepancy to trade
MIN_VOLUME = 5
MAX_VOLUME = 30

# Delta management (GOAL: Delta approaching zero)
MAX_ACCEPTABLE_DELTA = 10  # If delta exceeds this, prioritize rebalancing
DELTA_REBALANCE_THRESHOLD = 5  # Start rebalancing if |delta| > this

# Spread management (GOAL: Bid-ask spread management)
USE_LIMIT_ORDERS = True  # Earn spread instead of paying it
LIMIT_ORDER_AGGRESSIVENESS = 0.5  # 0=passive, 1=aggressive (cross spread)

# Timing
SLEEP_TIME = 0.3
ITERATION_DISPLAY_INTERVAL = 20

# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

def safe_connect():
    """Connect to exchange with error handling"""
    print("=" * 70)
    print("DUAL LISTING ARBITRAGE - CLEAN START")
    print("=" * 70)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"\nConnecting to exchange (attempt {attempt + 1}/{max_retries})...")

            if exchange.is_connected():
                exchange.disconnect()
                time.sleep(2)

            exchange.connect()

            if exchange.is_connected():
                print("✓ Connected successfully")
                return True

        except Exception as e:
            print(f"✗ Connection failed: {e}")
            if "someone else logged in" in str(e).lower():
                print("\n⚠ ERROR: Another session is active with same credentials")
                print("  → Close all other trading scripts and wait 30 seconds")
                return False

            if attempt < max_retries - 1:
                time.sleep(3)

    print("✗ Failed to connect after all retries")
    return False


def display_initial_state():
    """Show starting positions and P&L, detect existing positions"""
    print("\n" + "=" * 70)
    print("INITIAL STATE & POSITION RECONCILIATION")
    print("=" * 70)

    try:
        positions = exchange.get_positions()
        pnl = exchange.get_pnl()

        pos_a = positions.get(STOCK_A, 0)
        pos_b = positions.get(STOCK_B, 0)
        delta = pos_a + pos_b

        print(f"\nCurrent exchange positions:")
        print(f"  {STOCK_A}: {pos_a:+.0f}")
        print(f"  {STOCK_B}: {pos_b:+.0f}")
        print(f"  Delta: {delta:+.0f}")
        print(f"\nP&L: ${pnl:.2f}")

        # Inform user about existing positions
        if pos_a == 0 and pos_b == 0:
            print("\n✓ No existing positions - starting fresh")
        else:
            print(f"\n✓ Existing positions detected - will be managed by strategy")
            print(f"  Strategy will work to maintain delta ≈ 0")

        # Warn if delta is large
        if abs(delta) > MAX_ACCEPTABLE_DELTA:
            print(f"\n⚠ WARNING: Large delta detected ({delta:+.0f})")
            print("  → Algorithm will prioritize rebalancing to bring delta toward 0")

        return True

    except Exception as e:
        print(f"Error getting initial state: {e}")
        return False


# ============================================================================
# GOAL 1: PRICE DISCREPANCY DETECTION
# ============================================================================

def detect_price_discrepancy(book_a, book_b):
    """
    GOAL: Price discrepancy between orderbooks

    Returns: (discrepancy_size, cheap_instrument, expensive_instrument, cheap_price, expensive_price)
    """
    # Calculate fair values (midpoints)
    mid_a = (book_a.bids[0].price + book_a.asks[0].price) / 2
    mid_b = (book_b.bids[0].price + book_b.asks[0].price) / 2

    # Detect discrepancy
    discrepancy = abs(mid_a - mid_b)

    if mid_a > mid_b:
        # A is expensive, B is cheap
        # To arbitrage: buy B (cheap), sell A (expensive)
        return discrepancy, STOCK_B, STOCK_A, book_b.asks[0].price, book_a.bids[0].price
    else:
        # B is expensive, A is cheap
        # To arbitrage: buy A (cheap), sell B (expensive)
        return discrepancy, STOCK_A, STOCK_B, book_a.asks[0].price, book_b.bids[0].price


# ============================================================================
# GOAL 2: DELTA APPROACHING ZERO STRATEGY
# ============================================================================

def get_current_delta():
    """Calculate current delta (should approach zero)"""
    positions = exchange.get_positions()
    pos_a = positions.get(STOCK_A, 0)
    pos_b = positions.get(STOCK_B, 0)
    return pos_a + pos_b, pos_a, pos_b


def needs_rebalancing(delta):
    """
    GOAL: Delta approaching zero strategy

    Returns True if delta is too far from zero and needs correction
    """
    return abs(delta) > DELTA_REBALANCE_THRESHOLD


def calculate_rebalancing_trade(delta, book_a, book_b):
    """
    Calculate trade to bring delta back toward zero

    If delta > 0: we're long overall → sell the long side
    If delta < 0: we're short overall → buy the short side
    """
    if delta == 0:
        return None

    volume = min(abs(delta), MAX_VOLUME)

    if delta > 0:
        # We're net long, need to sell
        # Sell whichever is more expensive
        if book_a.bids[0].price > book_b.bids[0].price:
            return ("rebalance", STOCK_A, "sell", book_a.bids[0].price, volume)
        else:
            return ("rebalance", STOCK_B, "sell", book_b.bids[0].price, volume)
    else:
        # We're net short, need to buy
        # Buy whichever is cheaper
        if book_a.asks[0].price < book_b.asks[0].price:
            return ("rebalance", STOCK_A, "buy", book_a.asks[0].price, volume)
        else:
            return ("rebalance", STOCK_B, "buy", book_b.asks[0].price, volume)


# ============================================================================
# GOAL 3: BID-ASK SPREAD MANAGEMENT
# ============================================================================

def calculate_limit_order_prices(cheap_side_ask, expensive_side_bid):
    """
    GOAL: Bid-ask spread management

    Instead of crossing the spread (paying it), we post limit orders
    to earn the spread by providing liquidity.

    Strategy: Post slightly inside the current spread to get filled quickly
    while still earning most of the spread.
    """
    if not USE_LIMIT_ORDERS:
        # Aggressive IOC orders that cross the spread
        return cheap_side_ask, expensive_side_bid

    # Post limit orders inside the spread
    # Buy limit: post above current bid but below ask
    # Sell limit: post below current ask but above bid

    spread = expensive_side_bid - cheap_side_ask
    adjustment = spread * LIMIT_ORDER_AGGRESSIVENESS

    buy_price = cheap_side_ask - adjustment  # Below ask = earn spread
    sell_price = expensive_side_bid + adjustment  # Above bid = earn spread

    return buy_price, sell_price


# ============================================================================
# GOAL 5: ARBITRAGE STRATEGY EXECUTION
# ============================================================================

def check_position_capacity(instrument, side, volume):
    """Check if trade would breach position limits"""
    positions = exchange.get_positions()
    current_pos = positions.get(instrument, 0)

    if side == "buy":
        new_pos = current_pos + volume
        return new_pos <= (POSITION_LIMIT - POSITION_BUFFER)
    else:  # sell
        new_pos = current_pos - volume
        return new_pos >= -(POSITION_LIMIT - POSITION_BUFFER)


def execute_arbitrage_pair(cheap_instrument, expensive_instrument, cheap_price, expensive_price, volume):
    """
    GOAL: Arbitrage strategy

    Execute paired trades to capture price discrepancy while maintaining delta=0
    """
    # Check position limits for both sides
    can_buy = check_position_capacity(cheap_instrument, "buy", volume)
    can_sell = check_position_capacity(expensive_instrument, "sell", volume)

    if not can_buy or not can_sell:
        return False, "position_limit"

    expected_profit = (expensive_price - cheap_price) * volume

    print(f"\n>>> ARBITRAGE OPPORTUNITY <<<")
    print(f"  Buy  {volume} x {cheap_instrument} @ {cheap_price:.2f}")
    print(f"  Sell {volume} x {expensive_instrument} @ {expensive_price:.2f}")
    print(f"  Expected profit: ${expected_profit:.2f}")

    try:
        # Execute buy order (cheap side)
        exchange.insert_order(
            instrument_id=cheap_instrument,
            price=cheap_price,
            volume=volume,
            side="bid",
            order_type="limit" if USE_LIMIT_ORDERS else "ioc"
        )

        # Execute sell order (expensive side)
        exchange.insert_order(
            instrument_id=expensive_instrument,
            price=expensive_price,
            volume=volume,
            side="ask",
            order_type="limit" if USE_LIMIT_ORDERS else "ioc"
        )

        print("  ✓ Orders submitted")
        return True, "executed"

    except Exception as e:
        print(f"  ✗ Execution error: {e}")
        return False, str(e)


def execute_rebalancing_trade(instrument, side, price, volume):
    """
    Execute single-sided trade to bring delta toward zero
    """
    print(f"\n>>> DELTA REBALANCING <<<")
    print(f"  {side.upper()} {volume} x {instrument} @ {price:.2f}")

    try:
        exchange.insert_order(
            instrument_id=instrument,
            price=price,
            volume=volume,
            side="bid" if side == "buy" else "ask",
            order_type="ioc"
        )
        print("  ✓ Rebalancing order submitted")
        return True

    except Exception as e:
        print(f"  ✗ Rebalancing error: {e}")
        return False


# ============================================================================
# MAIN TRADING LOOP
# ============================================================================

def main():
    """Main trading loop implementing all goals"""

    # Connect to exchange
    if not safe_connect():
        return

    # Display initial state
    if not display_initial_state():
        exchange.disconnect()
        return

    # Start trading
    print("\n" + "=" * 70)
    print("STRATEGY ACTIVE - Goals Implementation:")
    print("  ✓ Price discrepancy detection")
    print("  ✓ Delta approaching zero")
    print("  ✓ Bid-ask spread management")
    print("  ✓ Dual listing arbitrage")
    print("=" * 70)
    print("\nPress Ctrl+C to stop\n")

    iteration = 0
    trades_executed = 0
    rebalances_executed = 0

    try:
        while True:
            iteration += 1

            # Periodic status display
            if iteration % ITERATION_DISPLAY_INTERVAL == 1:
                delta, pos_a, pos_b = get_current_delta()
                pnl = exchange.get_pnl()

                print(f"\n{'-' * 70}")
                print(f"[{iteration}] {dt.datetime.now().strftime('%H:%M:%S')}")
                print(f"Positions: {STOCK_A}={pos_a:+.0f}, {STOCK_B}={pos_b:+.0f}, Delta={delta:+.0f}")
                print(f"P&L: ${pnl:.2f} | Arbitrages: {trades_executed} | Rebalances: {rebalances_executed}")

            # Check connection
            if not exchange.is_connected():
                print("\n⚠ Connection lost!")
                break

            # Get orderbooks for both instruments
            book_a = exchange.get_last_price_book(STOCK_A)
            book_b = exchange.get_last_price_book(STOCK_B)

            # Validate orderbooks
            if not (book_a and book_a.bids and book_a.asks):
                time.sleep(SLEEP_TIME)
                continue

            if not (book_b and book_b.bids and book_b.asks):
                time.sleep(SLEEP_TIME)
                continue

            # GOAL 2: Check if delta needs rebalancing (PRIORITY)
            delta, pos_a, pos_b = get_current_delta()

            if needs_rebalancing(delta):
                print(f"\n⚠ Delta too large ({delta:+.0f}), rebalancing...")
                rebalance_trade = calculate_rebalancing_trade(delta, book_a, book_b)

                if rebalance_trade:
                    _, instrument, side, price, volume = rebalance_trade
                    if execute_rebalancing_trade(instrument, side, price, volume):
                        rebalances_executed += 1

                time.sleep(SLEEP_TIME)
                continue

            # GOAL 1: Detect price discrepancy
            discrepancy, cheap_instr, expensive_instr, cheap_price, expensive_price = \
                detect_price_discrepancy(book_a, book_b)

            # Check if discrepancy is large enough for arbitrage
            if discrepancy < ARBITRAGE_THRESHOLD:
                time.sleep(SLEEP_TIME)
                continue

            # GOAL 3: Apply bid-ask spread management
            if USE_LIMIT_ORDERS:
                cheap_price, expensive_price = calculate_limit_order_prices(
                    cheap_price, expensive_price
                )

            # Determine volume
            volume = min(MAX_VOLUME, max(MIN_VOLUME, int(discrepancy / 0.05) * 5))

            # GOAL 5: Execute arbitrage strategy
            success, reason = execute_arbitrage_pair(
                cheap_instr, expensive_instr,
                cheap_price, expensive_price,
                volume
            )

            if success:
                trades_executed += 1

            time.sleep(SLEEP_TIME)

    except KeyboardInterrupt:
        print("\n\n⚠ Stopped by user")

    except Exception as e:
        print(f"\n\n⚠ Error: {e}")

    finally:
        # Final state
        print("\n" + "=" * 70)
        print("FINAL STATE")
        print("=" * 70)

        try:
            delta, pos_a, pos_b = get_current_delta()
            pnl = exchange.get_pnl()

            print(f"\nIterations: {iteration}")
            print(f"Arbitrage trades: {trades_executed}")
            print(f"Rebalancing trades: {rebalances_executed}")
            print(f"\nFinal positions:")
            print(f"  {STOCK_A}: {pos_a:+.0f}")
            print(f"  {STOCK_B}: {pos_b:+.0f}")
            print(f"  Delta: {delta:+.0f}")
            print(f"\nFinal P&L: ${pnl:.2f}")
            print("=" * 70)

        except:
            pass

        # Disconnect
        if exchange.is_connected():
            print("\nDisconnecting...")
            exchange.disconnect()
            print("✓ Disconnected")


if __name__ == "__main__":
    main()
