import datetime as dt
import time
import logging
import json
import csv
from pathlib import Path

from optibook.synchronous_client import Exchange

exchange = Exchange()
exchange.connect()

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

# Data logging configuration
DATA_DIR = Path("trading_data")
DATA_DIR.mkdir(exist_ok=True)

# Create timestamped log files
SESSION_TIMESTAMP = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
ITERATION_LOG = DATA_DIR / f"iterations_{SESSION_TIMESTAMP}.csv"
TRADE_LOG = DATA_DIR / f"trades_{SESSION_TIMESTAMP}.csv"
SUMMARY_LOG = DATA_DIR / f"summary_{SESSION_TIMESTAMP}.json"

# Initialize CSV files with headers
with open(ITERATION_LOG, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'timestamp', 'iteration', 'a_bid', 'a_ask', 'a_mid',
        'b_bid', 'b_ask', 'b_mid', 'spread', 'fair_value',
        'pos_a', 'pos_b', 'delta', 'pnl', 'opportunity_detected',
        'trade_executed', 'reason'
    ])

with open(TRADE_LOG, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'timestamp', 'iteration', 'cheap_instrument', 'expensive_instrument',
        'cheap_price', 'expensive_price', 'volume', 'expected_profit',
        'spread', 'pos_a_before', 'pos_b_before', 'delta_before',
        'pos_a_after', 'pos_b_after', 'delta_after', 'pnl_before', 'pnl_after', 'pnl_change'
    ])

# Performance tracking
class PerformanceTracker:
    def __init__(self):
        self.start_time = dt.datetime.now()
        self.iterations = 0
        self.opportunities_detected = 0
        self.trades_executed = 0
        self.trades_skipped_volume = 0
        self.trades_skipped_limit = 0
        self.total_expected_profit = 0
        self.spread_history = []
        self.pnl_history = []
        self.delta_history = []
        self.position_utilization_history = []

    def log_iteration(self, spread):
        self.iterations += 1
        self.spread_history.append(spread)

    def log_opportunity(self):
        self.opportunities_detected += 1

    def log_trade(self, expected_profit):
        self.trades_executed += 1
        self.total_expected_profit += expected_profit

    def log_skip(self, reason):
        if reason == "volume":
            self.trades_skipped_volume += 1
        elif reason == "limit":
            self.trades_skipped_limit += 1

    def log_state(self, pnl, delta, position_util):
        self.pnl_history.append((dt.datetime.now(), pnl))
        self.delta_history.append((dt.datetime.now(), delta))
        self.position_utilization_history.append((dt.datetime.now(), position_util))

    def get_summary(self):
        elapsed = (dt.datetime.now() - self.start_time).total_seconds()
        return {
            'session_start': self.start_time.isoformat(),
            'session_duration_seconds': elapsed,
            'total_iterations': self.iterations,
            'iterations_per_second': self.iterations / elapsed if elapsed > 0 else 0,
            'opportunities_detected': self.opportunities_detected,
            'trades_executed': self.trades_executed,
            'trade_execution_rate': self.trades_executed / self.opportunities_detected if self.opportunities_detected > 0 else 0,
            'trades_skipped_volume': self.trades_skipped_volume,
            'trades_skipped_limit': self.trades_skipped_limit,
            'total_expected_profit': self.total_expected_profit,
            'avg_expected_profit_per_trade': self.total_expected_profit / self.trades_executed if self.trades_executed > 0 else 0,
            'avg_spread': sum(self.spread_history) / len(self.spread_history) if self.spread_history else 0,
            'max_spread': max(self.spread_history) if self.spread_history else 0,
            'min_spread': min(self.spread_history) if self.spread_history else 0,
            'final_pnl': self.pnl_history[-1][1] if self.pnl_history else 0,
            'max_delta': max(abs(d[1]) for d in self.delta_history) if self.delta_history else 0,
            'avg_delta': sum(abs(d[1]) for d in self.delta_history) / len(self.delta_history) if self.delta_history else 0,
            'max_position_util': max(p[1] for p in self.position_utilization_history) if self.position_utilization_history else 0,
        }

tracker = PerformanceTracker()


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


def get_current_state():
    """Get current positions, PnL, and delta"""
    positions = exchange.get_positions()
    pos_a = positions.get(STOCK_A_ID, 0)
    pos_b = positions.get(STOCK_B_ID, 0)
    delta = pos_a + pos_b
    pnl = exchange.get_pnl()
    return pos_a, pos_b, delta, pnl


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

    pos_a = positions.get(STOCK_A_ID, 0)
    pos_b = positions.get(STOCK_B_ID, 0)
    delta = pos_a + pos_b
    print(f"  {'Delta (A+B)':20s}: {delta:4.0f}")

    max_abs_pos = max(abs(pos_a), abs(pos_b))
    utilization = (max_abs_pos / POSITION_LIMIT) * 100
    print(f"  {'Position Util':20s}: {utilization:4.1f}%")

    pnl = exchange.get_pnl()
    if pnl:
        print(f"\nPnL: {pnl:.2f}")


def log_iteration_data(iteration, a_bid, a_ask, a_mid, b_bid, b_ask, b_mid,
                        spread, fair_value, pos_a, pos_b, delta, pnl,
                        opportunity, executed, reason=""):
    """Log iteration data to CSV"""
    with open(ITERATION_LOG, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            dt.datetime.now().isoformat(), iteration, a_bid, a_ask, a_mid,
            b_bid, b_ask, b_mid, spread, fair_value,
            pos_a, pos_b, delta, pnl, opportunity, executed, reason
        ])


def log_trade_data(iteration, cheap_id, expensive_id, cheap_price, expensive_price,
                   volume, expected_profit, spread, pos_a_before, pos_b_before,
                   delta_before, pnl_before):
    """Log trade execution data to CSV"""
    # Wait a moment for exchange to process
    time.sleep(0.05)

    # Get state after trade
    pos_a_after, pos_b_after, delta_after, pnl_after = get_current_state()
    pnl_change = pnl_after - pnl_before if (pnl_after and pnl_before) else 0

    with open(TRADE_LOG, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            dt.datetime.now().isoformat(), iteration, cheap_id, expensive_id,
            cheap_price, expensive_price, volume, expected_profit, spread,
            pos_a_before, pos_b_before, delta_before,
            pos_a_after, pos_b_after, delta_after,
            pnl_before, pnl_after, pnl_change
        ])


def execute_arbitrage(iteration, cheap_id, expensive_id, cheap_price, expensive_price, volume, spread):
    """Execute paired trades with data logging"""
    if volume <= 0:
        print(f"Volume too small ({volume}), skipping trade")
        tracker.log_skip("volume")
        return False

    # Capture state before trade
    pos_a_before, pos_b_before, delta_before, pnl_before = get_current_state()

    total_profit = (expensive_price - cheap_price) * volume
    tracker.log_opportunity()

    print(f"\n>>> ARBITRAGE EXECUTING <<<")
    print(f"Buy {volume} lots {cheap_id} @ {cheap_price:.2f}")
    print(f"Sell {volume} lots {expensive_id} @ {expensive_price:.2f}")
    print(f"Profit: {total_profit:.2f} ({expensive_price - cheap_price:.2f}/lot)")

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
        tracker.log_trade(total_profit)

        # Log trade details
        log_trade_data(iteration, cheap_id, expensive_id, cheap_price, expensive_price,
                       volume, total_profit, spread, pos_a_before, pos_b_before,
                       delta_before, pnl_before)

        return True
    except Exception as e:
        print(f"Error executing trade: {e}")
        return False


def save_summary():
    """Save session summary to JSON"""
    summary = tracker.get_summary()
    summary['config'] = {
        'arbitrage_threshold': ARBITRAGE_THRESHOLD,
        'min_trade_volume': MIN_TRADE_VOLUME,
        'max_trade_volume': MAX_TRADE_VOLUME,
        'sleep_time': SLEEP_TIME,
        'position_limit': POSITION_LIMIT,
        'position_buffer': POSITION_BUFFER,
    }

    with open(SUMMARY_LOG, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSession summary saved to {SUMMARY_LOG}")


# Main trading loop
print("=" * 70)
print("DATA LOGGING ARBITRAGE STRATEGY")
print("=" * 70)
print(f"Instruments: {STOCK_A_ID} <-> {STOCK_B_ID}")
print(f"Session: {SESSION_TIMESTAMP}")
print(f"Data directory: {DATA_DIR}")
print(f"Iteration log: {ITERATION_LOG.name}")
print(f"Trade log: {TRADE_LOG.name}")
print(f"Summary log: {SUMMARY_LOG.name}")
print("=" * 70)

iteration_count = 0

try:
    while True:
        iteration_count += 1

        # Detailed output every 50 iterations
        if iteration_count % 50 == 1:
            print(f"\n{'-' * 70}")
            print(f"ITERATION {iteration_count} AT {str(dt.datetime.now()):18s} UTC")
            print(f"{'-' * 70}")
            print_positions_and_pnl(always_display=[STOCK_A_ID, STOCK_B_ID])

            # Print tracker stats
            summary = tracker.get_summary()
            print(f"\nPerformance:")
            print(f"  Opportunities: {tracker.opportunities_detected}")
            print(f"  Trades executed: {tracker.trades_executed}")
            print(f"  Execution rate: {summary['trade_execution_rate']:.1%}")
            print(f"  Avg spread: {summary['avg_spread']:.3f}")
            print(f"  Total expected profit: {tracker.total_expected_profit:.2f}")
            print("")

        # Get both orderbooks
        book_a = exchange.get_last_price_book(STOCK_A_ID)
        book_b = exchange.get_last_price_book(STOCK_B_ID)

        # Get current state
        pos_a, pos_b, delta, pnl = get_current_state()
        max_abs_pos = max(abs(pos_a), abs(pos_b))
        position_util = (max_abs_pos / POSITION_LIMIT) * 100

        # Track state
        tracker.log_state(pnl if pnl else 0, delta, position_util)

        # Validate orderbooks
        if not (book_a and book_a.bids and book_a.asks):
            log_iteration_data(iteration_count, 0, 0, 0, 0, 0, 0, 0, 0,
                              pos_a, pos_b, delta, pnl, False, False, "orderbook_a_incomplete")
            time.sleep(SLEEP_TIME)
            continue

        if not (book_b and book_b.bids and book_b.asks):
            log_iteration_data(iteration_count, 0, 0, 0, 0, 0, 0, 0, 0,
                              pos_a, pos_b, delta, pnl, False, False, "orderbook_b_incomplete")
            time.sleep(SLEEP_TIME)
            continue

        # Extract prices
        a_bid = book_a.bids[0].price
        a_ask = book_a.asks[0].price
        b_bid = book_b.bids[0].price
        b_ask = book_b.asks[0].price

        a_mid = (a_bid + a_ask) / 2
        b_mid = (b_bid + b_ask) / 2
        fair_value = (a_mid + b_mid) / 2
        spread = abs(a_mid - b_mid)

        tracker.log_iteration(spread)

        # Check for arbitrage
        opportunity_detected = spread >= ARBITRAGE_THRESHOLD
        trade_executed = False
        reason = ""

        if not opportunity_detected:
            reason = f"spread_too_small_{spread:.3f}"
            log_iteration_data(iteration_count, a_bid, a_ask, a_mid, b_bid, b_ask, b_mid,
                              spread, fair_value, pos_a, pos_b, delta, pnl,
                              False, False, reason)
        else:
            if a_mid > b_mid + ARBITRAGE_THRESHOLD:
                volume = calculate_dynamic_volume(spread, STOCK_B_ID, STOCK_A_ID)

                if volume > 0:
                    print(f"\n[{iteration_count}] A overpriced by {spread:.2f}")
                    trade_executed = execute_arbitrage(
                        iteration_count, STOCK_B_ID, STOCK_A_ID,
                        b_ask, a_bid, volume, spread
                    )
                    reason = "a_overpriced"
                else:
                    reason = "insufficient_capacity"
                    tracker.log_skip("limit")

            elif b_mid > a_mid + ARBITRAGE_THRESHOLD:
                volume = calculate_dynamic_volume(spread, STOCK_A_ID, STOCK_B_ID)

                if volume > 0:
                    print(f"\n[{iteration_count}] B overpriced by {spread:.2f}")
                    trade_executed = execute_arbitrage(
                        iteration_count, STOCK_A_ID, STOCK_B_ID,
                        a_ask, b_bid, volume, spread
                    )
                    reason = "b_overpriced"
                else:
                    reason = "insufficient_capacity"
                    tracker.log_skip("limit")

            # Log iteration
            log_iteration_data(iteration_count, a_bid, a_ask, a_mid, b_bid, b_ask, b_mid,
                              spread, fair_value, pos_a, pos_b, delta, pnl,
                              opportunity_detected, trade_executed, reason)

        time.sleep(SLEEP_TIME)

except KeyboardInterrupt:
    print("\n\nTrading stopped by user")
finally:
    # Save summary on exit
    print("\nGenerating final summary...")
    save_summary()

    summary = tracker.get_summary()
    print("\n" + "=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"Duration: {summary['session_duration_seconds']:.0f}s")
    print(f"Iterations: {summary['total_iterations']} ({summary['iterations_per_second']:.2f}/s)")
    print(f"Opportunities: {summary['opportunities_detected']}")
    print(f"Trades executed: {summary['trades_executed']}")
    print(f"Execution rate: {summary['trade_execution_rate']:.1%}")
    print(f"Expected profit: ${summary['total_expected_profit']:.2f}")
    print(f"Final P&L: ${summary['final_pnl']:.2f}")
    print(f"Max delta deviation: {summary['max_delta']}")
    print(f"Avg delta deviation: {summary['avg_delta']:.2f}")
    print(f"Max position utilization: {summary['max_position_util']:.1f}%")
    print("=" * 70)
    print(f"\nData files saved in: {DATA_DIR}")
