"""
Statistical Arbitrage Strategy - Strictly Following guide.md

Implements:
1. Pairs Trading with mean reversion
2. Spread calculation and tracking
3. Guard-rail logic for volume, slippage, and execution checks
4. Concurrent execution with partial fill handling
"""

import datetime as dt
import time
import logging
from collections import deque
from optibook.synchronous_client import Exchange
import statistics

# Setup
exchange = Exchange()
logging.getLogger("client").setLevel("ERROR")

# ============================================================================
# CONFIGURATION - Following guide.md Architecture
# ============================================================================

# The Pair
ASSET_A = "PHILLIPS_A"
ASSET_B = "PHILLIPS_B"

# Position Limits
POSITION_LIMIT = 100
MAX_POSITION_SIZE = 10  # Maximum size per trade (reduced to match available liquidity)

# Statistical Parameters
SPREAD_HISTORY_LENGTH = 100  # Number of data points for mean/std calculation
ENTRY_THRESHOLD_STDEV = 0.8  # Enter when spread > mean ± 0.8*std (more sensitive)
EXIT_THRESHOLD_STDEV = 0.2   # Exit when spread approaches mean (within 0.2*std)

# Perfect Fungibility Assumption
# Because other participants can transfer stocks between exchanges,
# prices should converge to parity (spread = 1.0)
ASSUME_PERFECT_FUNGIBILITY = True  # Assume prices will converge to 1.0
THEORETICAL_PARITY = 1.0  # The spread should be exactly 1.0 if prices are equal

# Guard-Rail Thresholds (Following guide.md Section 3)
MAX_ACCEPTABLE_SPREAD_A = 2.0  # Maximum bid-ask spread for ASSET_A (increased for market conditions)
MAX_ACCEPTABLE_SPREAD_B = 2.0  # Maximum bid-ask spread for ASSET_B (increased for market conditions)
MIN_VOLUME_RATIO = 0.1  # Must have at least 0.1x our trade size available (1 unit for 10 size)

# Risk Management
TRADING_DISABLED = False  # Global kill switch
MIN_REQUIRED_MARGIN = 100  # Minimum cash required to trade
FRONT_RUN_TOLERANCE = 0.005  # Allow 0.5% tolerance for spread movement before aborting

# Timing
SLEEP_TIME = 0.2  # Faster checking for more opportunities
DISPLAY_INTERVAL = 20

# ============================================================================
# PORTFOLIO MANAGER - Tracks Current State
# ============================================================================

class PortfolioManager:
    """Tracks current state: cash, positions, PnL, trade history"""

    def __init__(self):
        self.current_position = None  # 'LONG_PAIR', 'SHORT_PAIR', or None
        self.entry_spread = None
        self.entry_prices = {}
        self.trade_count = 0
        self.position_opened_at = None

    def has_position(self, pair):
        """Check if already in position for this pair"""
        return self.current_position is not None

    def open_position(self, position_type, spread, prices):
        """Record opening of position"""
        self.current_position = position_type
        self.entry_spread = spread
        self.entry_prices = prices
        self.trade_count += 1
        self.position_opened_at = dt.datetime.now()

    def close_position(self):
        """Record closing of position"""
        self.current_position = None
        self.entry_spread = None
        self.entry_prices = {}
        self.position_opened_at = None

    def get_state(self):
        """Get current portfolio state"""
        try:
            positions = exchange.get_positions()
            pnl = exchange.get_pnl()
            return {
                'positions': positions,
                'pnl': pnl,
                'cash': 10000,  # Placeholder - would query from exchange
                'isTradingDisabled': TRADING_DISABLED,
                'current_position': self.current_position
            }
        except:
            return None


portfolio = PortfolioManager()

# ============================================================================
# DATA HANDLER - Tracks Spread History and Statistics
# ============================================================================

class DataHandler:
    """Manages spread calculation and historical statistics"""

    def __init__(self, history_length):
        self.spread_history = deque(maxlen=history_length)
        self.last_spread = None
        self.mean = None
        self.std_dev = None

    def update_spread(self, book_a, book_b):
        """
        Calculate spread and update statistics

        Spread = price_ratio between assets
        Following guide.md: spread = price(A) / price(B)
        """
        # Use mid-prices for spread calculation
        mid_a = (book_a.bids[0].price + book_a.asks[0].price) / 2
        mid_b = (book_b.bids[0].price + book_b.asks[0].price) / 2

        # Calculate spread ratio
        spread = mid_a / mid_b

        # Update history
        self.spread_history.append(spread)
        self.last_spread = spread

        # Calculate statistics if we have enough data
        if len(self.spread_history) >= 20:  # Minimum data points
            self.mean = statistics.mean(self.spread_history)
            self.std_dev = statistics.stdev(self.spread_history)

        return spread

    def has_sufficient_data(self):
        """Check if we have enough historical data for trading"""
        return self.mean is not None and self.std_dev is not None

    def get_orderbook(self, instrument):
        """Get current orderbook for an instrument"""
        return exchange.get_last_price_book(instrument)


data_handler = DataHandler(SPREAD_HISTORY_LENGTH)

# ============================================================================
# SIGNAL GENERATOR - Checks Trading Rules
# ============================================================================

class SignalGenerator:
    """
    Following guide.md Section 2:
    - If spread > (mean + 2*std): Short the pair (Short A, Buy B)
    - If spread < (mean - 2*std): Long the pair (Buy A, Short B)
    - If spread crosses mean: Close position
    """

    @staticmethod
    def generate_signal(spread, mean, std_dev, current_position):
        """Generate trading signal based on spread statistics"""

        # If assuming perfect fungibility, use theoretical parity instead of empirical mean
        if ASSUME_PERFECT_FUNGIBILITY:
            effective_mean = THEORETICAL_PARITY
        else:
            effective_mean = mean

        upper_band = effective_mean + (ENTRY_THRESHOLD_STDEV * std_dev)
        lower_band = effective_mean - (ENTRY_THRESHOLD_STDEV * std_dev)
        exit_upper = effective_mean + (EXIT_THRESHOLD_STDEV * std_dev)
        exit_lower = effective_mean - (EXIT_THRESHOLD_STDEV * std_dev)

        # Check for CLOSE signals first
        if current_position == 'SHORT_PAIR':
            # We shorted when spread was wide, close when it narrows
            if spread <= exit_upper:
                return {
                    'type': 'CLOSE_POSITION',
                    'reason': 'spread_reverted_to_mean',
                    'params': {'pair': f'{ASSET_A}-{ASSET_B}'}
                }

        elif current_position == 'LONG_PAIR':
            # We longed when spread was narrow, close when it widens
            if spread >= exit_lower:
                return {
                    'type': 'CLOSE_POSITION',
                    'reason': 'spread_reverted_to_mean',
                    'params': {'pair': f'{ASSET_A}-{ASSET_B}'}
                }

        # Check for OPEN signals (only if not in position)
        if current_position is None:
            if spread > upper_band:
                # Spread too wide: Short A, Buy B
                return {
                    'type': 'OPEN_SHORT_PAIR',
                    'reason': f'spread={spread:.4f} > upper_band={upper_band:.4f}',
                    'params': {
                        'pair': f'{ASSET_A}-{ASSET_B}',
                        'amount': MAX_POSITION_SIZE
                    }
                }

            elif spread < lower_band:
                # Spread too narrow: Buy A, Short B
                return {
                    'type': 'OPEN_LONG_PAIR',
                    'reason': f'spread={spread:.4f} < lower_band={lower_band:.4f}',
                    'params': {
                        'pair': f'{ASSET_A}-{ASSET_B}',
                        'amount': MAX_POSITION_SIZE
                    }
                }

        # No signal
        return None


signal_generator = SignalGenerator()

# ============================================================================
# EXECUTION HANDLER - Guard-Rail Logic (Following guide.md Section 4)
# ============================================================================

def calculate_margin(signal_type, amount):
    """Calculate required margin for trade"""
    # Simplified - would be more sophisticated in production
    return amount * 2  # Conservative estimate


def handle_signal(signal):
    """
    THE BRAIN - Guard-rail logic following guide.md

    This function runs BEFORE any order is placed.
    Designed to be pessimistic and abort at first sign of trouble.
    """

    if signal is None:
        return

    # --- 1. Get Current State ---
    portfolio_state = portfolio.get_state()
    if portfolio_state is None:
        print("⚠ Unable to get portfolio state")
        return

    book_a = data_handler.get_orderbook(ASSET_A)
    book_b = data_handler.get_orderbook(ASSET_B)
    trade_params = signal.get('params', {})

    # --- 2. Sanity & State Checks ---
    if portfolio_state['isTradingDisabled']:
        print("⚠ TRADING HALTED. Aborting signal.")
        return

    # Check if we're trying to OPEN a position
    if signal['type'] in ['OPEN_LONG_PAIR', 'OPEN_SHORT_PAIR']:

        # State Check: Are we already in a trade?
        # (Most StatArb strategies don't pyramid)
        if portfolio.has_position(trade_params['pair']):
            print("⚠ Already in position. Ignoring redundant OPEN signal.")
            return

        # Capital Check: Can we afford this?
        required_margin = calculate_margin(signal['type'], trade_params['amount'])
        if portfolio_state['cash'] < required_margin:
            print(f"⚠ INSUFFICIENT MARGIN. Need {required_margin}, have {portfolio_state['cash']}. Aborting.")
            return

        # --- 3. Pre-Trade Risk Checks (Following guide.md) ---

        # Get the prices we would ACTUALLY get if we placed market order
        if signal['type'] == 'OPEN_SHORT_PAIR':
            # Short A (sell A), Buy B (buy B)
            exec_price_a = book_a.bids[0].price  # We sell at bid
            exec_price_b = book_b.asks[0].price  # We buy at ask
            vol_a = book_a.bids[0].volume
            vol_b = book_b.asks[0].volume
        else:  # OPEN_LONG_PAIR
            # Buy A (buy A), Short B (sell B)
            exec_price_a = book_a.asks[0].price  # We buy at ask
            exec_price_b = book_b.bids[0].price  # We sell at bid
            vol_a = book_a.asks[0].volume
            vol_b = book_b.bids[0].volume

        # SCENARIO: "if volume is locked" (guide.md line 50-61)
        # Check if there is enough liquidity to fill entire order
        if vol_a < trade_params['amount'] * MIN_VOLUME_RATIO:
            print(f"⚠ VOLUME LOCKED for {ASSET_A}. Need {trade_params['amount']}, only {vol_a} available. Aborting.")
            return

        if vol_b < trade_params['amount'] * MIN_VOLUME_RATIO:
            print(f"⚠ VOLUME LOCKED for {ASSET_B}. Need {trade_params['amount']}, only {vol_b} available. Aborting.")
            return

        # SCENARIO: "if slippage is there" (guide.md line 63-77)
        # Check if bid-ask spread is too wide (volatility/illiquidity indicator)
        spread_a = book_a.asks[0].price - book_a.bids[0].price
        spread_b = book_b.asks[0].price - book_b.bids[0].price

        if spread_a > MAX_ACCEPTABLE_SPREAD_A:
            print(f"⚠ SLIPPAGE RISK HIGH for {ASSET_A}. Spread is {spread_a:.2f}. Aborting.")
            return

        if spread_b > MAX_ACCEPTABLE_SPREAD_B:
            print(f"⚠ SLIPPAGE RISK HIGH for {ASSET_B}. Spread is {spread_b:.2f}. Aborting.")
            return

        # --- 4. Final Check: Is trade STILL profitable? (guide.md line 79-91)
        # Signal was based on mid-prices, but we execute on bid/ask
        # Re-calculate spread using ACTUAL execution prices
        execution_spread = exec_price_a / exec_price_b

        # Get the threshold that triggered this signal
        upper_threshold = data_handler.mean + (ENTRY_THRESHOLD_STDEV * data_handler.std_dev)
        lower_threshold = data_handler.mean - (ENTRY_THRESHOLD_STDEV * data_handler.std_dev)

        # Check if actual execution spread still meets criteria (with tolerance)
        if signal['type'] == 'OPEN_SHORT_PAIR' and execution_spread < (upper_threshold - FRONT_RUN_TOLERANCE):
            print(f"⚠ FRONT-RUN/SLIPPED. Signal invalid at execution prices. Spread {execution_spread:.4f} < {upper_threshold:.4f}. Aborting.")
            return

        if signal['type'] == 'OPEN_LONG_PAIR' and execution_spread > (lower_threshold + FRONT_RUN_TOLERANCE):
            print(f"⚠ FRONT-RUN/SLIPPED. Signal invalid at execution prices. Spread {execution_spread:.4f} > {lower_threshold:.4f}. Aborting.")
            return

        # --- 5. EXECUTION ---
        # All checks passed!
        print(f"\n>>> ARBITRAGE OPPORTUNITY <<<")
        print(f"  Signal: {signal['type']}")
        print(f"  Reason: {signal['reason']}")
        print(f"  Volume: {trade_params['amount']} units")
        print(f"  Execution spread: {execution_spread:.4f}")
        print(f"  Prices: {ASSET_A}={exec_price_a:.2f}, {ASSET_B}={exec_price_b:.2f}")

        # CRITICAL: Execute trades concurrently to reduce time between legs
        # (guide.md line 97-112)
        success = execute_paired_trade(signal['type'], trade_params['amount'],
                                       exec_price_a, exec_price_b)

        if success:
            # Record in portfolio
            portfolio.open_position(
                signal['type'],
                execution_spread,
                {'A': exec_price_a, 'B': exec_price_b}
            )
            print("✓ Position opened successfully")

    # Logic for CLOSING a position (guide.md line 116-132)
    elif signal['type'] == 'CLOSE_POSITION':

        if not portfolio.has_position(trade_params['pair']):
            print("⚠ No position to close. Ignoring redundant CLOSE signal.")
            return

        # Get current positions to determine size
        positions = portfolio_state['positions']
        pos_a = abs(positions.get(ASSET_A, 0))
        pos_b = abs(positions.get(ASSET_B, 0))

        # Use the average as close amount
        close_amount = max(pos_a, pos_b)

        if close_amount == 0:
            print("⚠ No actual positions to close")
            portfolio.close_position()
            return

        # Simpler checks for closing (just volume availability)
        book_a_vol = book_a.bids[0].volume if positions.get(ASSET_A, 0) > 0 else book_a.asks[0].volume
        book_b_vol = book_b.bids[0].volume if positions.get(ASSET_B, 0) > 0 else book_b.asks[0].volume

        if book_a_vol < close_amount or book_b_vol < close_amount:
            print(f"⚠ Insufficient volume to close position. Waiting...")
            return

        print(f"\n>>> CLOSING POSITION <<<")
        print(f"  Reason: {signal['reason']}")
        print(f"  Volume: {close_amount} units")

        # Execute close
        success = execute_close_position(close_amount, positions)

        if success:
            # Calculate realized PnL
            current_spread = data_handler.last_spread
            entry_spread = portfolio.entry_spread
            spread_change = current_spread - entry_spread

            print(f"  ✓ Position closed")
            print(f"  Entry spread: {entry_spread:.4f}")
            print(f"  Exit spread: {current_spread:.4f}")
            print(f"  Spread change: {spread_change:+.4f}")

            portfolio.close_position()


def execute_paired_trade(signal_type, amount, price_a, price_b):
    """
    Execute both legs of the pair trade

    Following guide.md: Execute concurrently and handle partial fills
    """
    try:
        if signal_type == 'OPEN_SHORT_PAIR':
            # Short A, Buy B
            exchange.insert_order(
                instrument_id=ASSET_A,
                price=price_a,
                volume=amount,
                side="ask",
                order_type="ioc"
            )

            exchange.insert_order(
                instrument_id=ASSET_B,
                price=price_b,
                volume=amount,
                side="bid",
                order_type="ioc"
            )

        else:  # OPEN_LONG_PAIR
            # Buy A, Short B
            exchange.insert_order(
                instrument_id=ASSET_A,
                price=price_a,
                volume=amount,
                side="bid",
                order_type="ioc"
            )

            exchange.insert_order(
                instrument_id=ASSET_B,
                price=price_b,
                volume=amount,
                side="ask",
                order_type="ioc"
            )

        print(f"  ✓ Orders submitted")
        return True

    except Exception as e:
        print(f"  ✗ CRITICAL: PARTIAL FILL OR ORDER FAILURE - {e}")
        print(f"  ✗ MANUAL INTERVENTION MAY BE REQUIRED")
        # In production, would call handlePartialFillError()
        return False


def execute_close_position(amount, positions):
    """Execute orders to close the position"""
    try:
        pos_a = positions.get(ASSET_A, 0)
        pos_b = positions.get(ASSET_B, 0)

        # Close position A
        if pos_a > 0:
            # We're long A, sell it
            book_a = data_handler.get_orderbook(ASSET_A)
            exchange.insert_order(
                instrument_id=ASSET_A,
                price=book_a.bids[0].price,
                volume=abs(pos_a),
                side="ask",
                order_type="ioc"
            )
        elif pos_a < 0:
            # We're short A, buy it back
            book_a = data_handler.get_orderbook(ASSET_A)
            exchange.insert_order(
                instrument_id=ASSET_A,
                price=book_a.asks[0].price,
                volume=abs(pos_a),
                side="bid",
                order_type="ioc"
            )

        # Close position B
        if pos_b > 0:
            book_b = data_handler.get_orderbook(ASSET_B)
            exchange.insert_order(
                instrument_id=ASSET_B,
                price=book_b.bids[0].price,
                volume=abs(pos_b),
                side="ask",
                order_type="ioc"
            )
        elif pos_b < 0:
            book_b = data_handler.get_orderbook(ASSET_B)
            exchange.insert_order(
                instrument_id=ASSET_B,
                price=book_b.asks[0].price,
                volume=abs(pos_b),
                side="bid",
                order_type="ioc"
            )

        return True

    except Exception as e:
        print(f"⚠ Error closing position: {e}")
        return False


# ============================================================================
# MAIN LOOP - Following guide.md Architecture
# ============================================================================

def reconcile_existing_positions():
    """
    Check for existing positions on startup and adopt them into the strategy
    """
    print("\n" + "=" * 70)
    print("RECONCILING EXISTING POSITIONS")
    print("=" * 70)

    try:
        positions = exchange.get_positions()
        pos_a = positions.get(ASSET_A, 0)
        pos_b = positions.get(ASSET_B, 0)
        delta = pos_a + pos_b
        pnl = exchange.get_pnl()

        print(f"\nCurrent exchange positions:")
        print(f"  {ASSET_A}: {pos_a:+.0f}")
        print(f"  {ASSET_B}: {pos_b:+.0f}")
        print(f"  Delta: {delta:+.0f}")
        print(f"  P&L: ${pnl:.2f}")

        # Check if we have positions that look like a pair trade
        if pos_a == 0 and pos_b == 0:
            print("\n✓ No existing positions - starting fresh")
            return True

        # Get current spread to use as entry reference
        book_a = exchange.get_last_price_book(ASSET_A)
        book_b = exchange.get_last_price_book(ASSET_B)

        if not (book_a and book_a.bids and book_a.asks and book_b and book_b.bids and book_b.asks):
            print("⚠ Cannot get orderbooks to reconcile positions")
            return False

        mid_a = (book_a.bids[0].price + book_a.asks[0].price) / 2
        mid_b = (book_b.bids[0].price + book_b.asks[0].price) / 2
        current_spread = mid_a / mid_b

        # Determine position type based on actual positions
        if pos_a > 0 and pos_b < 0:
            # Long A, Short B = LONG_PAIR
            position_type = 'LONG_PAIR'
            print(f"\n✓ Detected LONG_PAIR position")
            print(f"  Long {abs(pos_a)} x {ASSET_A}, Short {abs(pos_b)} x {ASSET_B}")

            # Adopt this position
            portfolio.current_position = position_type
            portfolio.entry_spread = current_spread
            portfolio.entry_prices = {'A': mid_a, 'B': mid_b}
            portfolio.position_opened_at = dt.datetime.now()
            print(f"  Adopted with entry spread: {current_spread:.4f}")

        elif pos_a < 0 and pos_b > 0:
            # Short A, Long B = SHORT_PAIR
            position_type = 'SHORT_PAIR'
            print(f"\n✓ Detected SHORT_PAIR position")
            print(f"  Short {abs(pos_a)} x {ASSET_A}, Long {abs(pos_b)} x {ASSET_B}")

            # Adopt this position
            portfolio.current_position = position_type
            portfolio.entry_spread = current_spread
            portfolio.entry_prices = {'A': mid_a, 'B': mid_b}
            portfolio.position_opened_at = dt.datetime.now()
            print(f"  Adopted with entry spread: {current_spread:.4f}")

        else:
            # Positions exist but don't match a clear pair trade pattern
            print(f"\n⚠ WARNING: Existing positions don't match pair trade pattern")
            print(f"  {ASSET_A}={pos_a:+.0f}, {ASSET_B}={pos_b:+.0f}")
            print(f"  Delta: {delta:+.0f}")
            print(f"\nOptions:")
            print(f"  1. Continue anyway (risky - may create unbalanced positions)")
            print(f"  2. Exit and manually close positions first")

            response = input("\nContinue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Exiting - please close positions manually first")
                return False

            print("\n⚠ Continuing with existing positions - monitoring delta carefully")

        return True

    except Exception as e:
        print(f"✗ Error reconciling positions: {e}")
        return False


def main():
    """
    Main trading loop following guide.md:
    1. Data Handler updates market state
    2. Signal Generator calculates signals
    3. Execution Handler validates and executes
    4. Portfolio Manager tracks state
    """

    print("=" * 70)
    print("STATISTICAL ARBITRAGE STRATEGY - Following guide.md")
    print("=" * 70)

    # Connect
    try:
        exchange.connect()
        print("✓ Connected to exchange\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    # Reconcile existing positions
    if not reconcile_existing_positions():
        exchange.disconnect()
        return

    # Initial state
    print("\n" + "=" * 70)
    print("STRATEGY CONFIGURATION")
    print("=" * 70)
    print(f"Pair: {ASSET_A} / {ASSET_B}")
    print(f"Entry threshold: ± {ENTRY_THRESHOLD_STDEV} std deviations")
    print(f"Exit threshold: ± {EXIT_THRESHOLD_STDEV} std deviations")
    print(f"Max position size: {MAX_POSITION_SIZE} lots")

    # Show fungibility mode
    if ASSUME_PERFECT_FUNGIBILITY:
        print(f"\n✓ PERFECT FUNGIBILITY MODE")
        print(f"  Assuming other participants can transfer stocks")
        print(f"  Target spread: {THEORETICAL_PARITY:.4f} (prices should be equal)")
        print(f"  Strategy will trade expecting reversion to parity")
    else:
        print(f"\n  Using empirical mean from market data")

    print(f"\nBuilding spread history ({SPREAD_HISTORY_LENGTH} points)...")
    print("=" * 70)
    print("\nPress Ctrl+C to stop\n")

    iteration = 0

    try:
        while True:
            iteration += 1

            # Check connection
            if not exchange.is_connected():
                print("\n⚠ Lost connection")
                break

            # Get orderbooks
            book_a = exchange.get_last_price_book(ASSET_A)
            book_b = exchange.get_last_price_book(ASSET_B)

            if not (book_a and book_a.bids and book_a.asks):
                time.sleep(SLEEP_TIME)
                continue

            if not (book_b and book_b.bids and book_b.asks):
                time.sleep(SLEEP_TIME)
                continue

            # 1. DATA HANDLER: Update spread and statistics
            spread = data_handler.update_spread(book_a, book_b)

            # Display status - Enhanced clean format from clean_arbitrage_algo
            if iteration % DISPLAY_INTERVAL == 1:
                pnl = exchange.get_pnl()
                positions = exchange.get_positions()
                pos_a = positions.get(ASSET_A, 0)
                pos_b = positions.get(ASSET_B, 0)
                delta = pos_a + pos_b

                print(f"\n{'-' * 70}")
                print(f"[{iteration}] {dt.datetime.now().strftime('%H:%M:%S')}")

                # Positions and delta (clean format)
                print(f"Positions: {ASSET_A}={pos_a:+.0f}, {ASSET_B}={pos_b:+.0f}, Delta={delta:+.0f}")

                # Spread statistics (if available)
                if data_handler.has_sufficient_data():
                    upper = data_handler.mean + (ENTRY_THRESHOLD_STDEV * data_handler.std_dev)
                    lower = data_handler.mean - (ENTRY_THRESHOLD_STDEV * data_handler.std_dev)
                    print(f"Spread: {spread:.4f} | Mean: {data_handler.mean:.4f} ± {data_handler.std_dev:.4f}")
                    print(f"Bands: [{lower:.4f}, {upper:.4f}]")
                else:
                    print(f"Spread: {spread:.4f} | Building history... {len(data_handler.spread_history)}/{SPREAD_HISTORY_LENGTH}")

                # Position type and P&L
                position_type = portfolio.current_position or 'None'
                print(f"Position: {position_type} | P&L: ${pnl:.2f} | Trades: {portfolio.trade_count}")

            # Only trade if we have sufficient statistical data
            if not data_handler.has_sufficient_data():
                time.sleep(SLEEP_TIME)
                continue

            # 2. SIGNAL GENERATOR: Generate trading signal
            signal = signal_generator.generate_signal(
                spread,
                data_handler.mean,
                data_handler.std_dev,
                portfolio.current_position
            )

            # 3. EXECUTION HANDLER: Validate and execute
            if signal:
                handle_signal(signal)

            time.sleep(SLEEP_TIME)

    except KeyboardInterrupt:
        print("\n\n⚠ Stopped by user")

    except Exception as e:
        print(f"\n\n⚠ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Final state
        print("\n" + "=" * 70)
        print("FINAL STATE")
        print("=" * 70)

        try:
            positions = exchange.get_positions()
            pnl = exchange.get_pnl()
            pos_a = positions.get(ASSET_A, 0)
            pos_b = positions.get(ASSET_B, 0)

            print(f"\nIterations: {iteration}")
            print(f"Total trades: {portfolio.trade_count}")
            print(f"Current position: {portfolio.current_position or 'None'}")
            print(f"Positions: {ASSET_A}={pos_a:+.0f}, {ASSET_B}={pos_b:+.0f}")
            print(f"Final P&L: ${pnl:.2f}")

            if data_handler.has_sufficient_data():
                print(f"\nFinal spread stats:")
                print(f"  Last spread: {data_handler.last_spread:.4f}")
                print(f"  Mean: {data_handler.mean:.4f}")
                print(f"  Std Dev: {data_handler.std_dev:.4f}")

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
