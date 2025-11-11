"""
OPTIMAL MERGED ALGORITHM - Best of Both Worlds

Combines:
- Direct arbitrage logic from already_priftable_algo (proven profitable)
- Better display and monitoring from statarb_guided_algo
- Minimal blocking, maximum speed

Strategy: When bid_A - ask_B >= EDGE, execute immediately
"""

import datetime as dt
import time
import logging

from optibook.synchronous_client import Exchange

exchange = Exchange()
exchange.connect()

logging.getLogger("client").setLevel("ERROR")

# =============================================================================
# CONFIGURATION - Optimized for Profitability
# =============================================================================

# Asset names (CRITICAL: Use correct spelling)
STOCK_A_ID = "PHILIPS_A"   # Primary/leader (correct spelling: single L)
STOCK_B_ID = "PHILIPS_B"   # Secondary/follower

# Trading parameters (from profitable algo - proven to work)
EDGE = 0.1                  # Minimum profit opportunity (1 tick)
VOLUME = 10                 # Lots per trade
SLEEP_TIME = 0.0            # React instantly (from profitable algo)
TICK_SIZE = 0.1             # Exchange tick size

# Risk management (keep position limits, remove blocking checks)
POSITION_LIMIT = 100        # Maximum position per asset
DISPLAY_INTERVAL = 20       # Show status every N iterations

# =============================================================================
# UTILITIES
# =============================================================================

def round_to_tick(price):
    """Ensure submitted prices are aligned with tick size (from profitable algo)"""
    return round(price / TICK_SIZE) * TICK_SIZE


def trade_would_breach_position_limit(instrument_id, volume, side, position_limit=POSITION_LIMIT):
    """Check if trade would exceed position limits (from profitable algo)"""
    positions = exchange.get_positions()
    position_instrument = positions.get(instrument_id, 0)

    if side == "bid":
        return position_instrument + volume > position_limit
    elif side == "ask":
        return position_instrument - volume < -position_limit
    else:
        raise Exception(f"Invalid side: {side}, expecting 'bid' or 'ask'.")


def print_status(iteration, book_A, book_B):
    """Enhanced status display (from guided algo)"""
    positions = exchange.get_positions()
    pnl = exchange.get_pnl()
    pos_a = positions.get(STOCK_A_ID, 0)
    pos_b = positions.get(STOCK_B_ID, 0)
    delta = pos_a + pos_b

    bid_A = book_A.bids[0].price if book_A.bids else 0
    ask_A = book_A.asks[0].price if book_A.asks else 0
    bid_B = book_B.bids[0].price if book_B.bids else 0
    ask_B = book_B.asks[0].price if book_B.asks else 0

    # Calculate arbitrage opportunities
    arb_buy_b = bid_A - ask_B  # Profit if we buy B, sell A
    arb_sell_b = bid_B - ask_A  # Profit if we sell B, buy A

    print(f"\n{'-' * 70}")
    print(f"[{iteration}] {dt.datetime.now().strftime('%H:%M:%S')}")
    print(f"Positions: A={pos_a:+.0f}, B={pos_b:+.0f}, Delta={delta:+.0f} | P&L: ${pnl:.2f}")
    print(f"Prices: A[{bid_A:.1f}|{ask_A:.1f}] B[{bid_B:.1f}|{ask_B:.1f}]")
    print(f"Arb Opportunities: Buy_B={arb_buy_b:+.2f}, Sell_B={arb_sell_b:+.2f} (need >={EDGE:.1f})")


# =============================================================================
# RECONCILIATION - Adopt existing positions if any
# =============================================================================

def reconcile_positions():
    """Check and display any existing positions"""
    try:
        positions = exchange.get_positions()
        pos_a = positions.get(STOCK_A_ID, 0)
        pos_b = positions.get(STOCK_B_ID, 0)
        pnl = exchange.get_pnl()

        print("\n" + "=" * 70)
        print("STARTING STATE")
        print("=" * 70)
        print(f"{STOCK_A_ID}: {pos_a:+.0f}")
        print(f"{STOCK_B_ID}: {pos_b:+.0f}")
        print(f"P&L: ${pnl:.2f}")

        if pos_a != 0 or pos_b != 0:
            print("\n⚠ Warning: Starting with existing positions")
            print("Strategy will continue trading from current state")
        else:
            print("\n✓ Starting fresh with no positions")

        print("=" * 70)
        return True

    except Exception as e:
        print(f"✗ Error checking positions: {e}")
        return False


# =============================================================================
# MAIN TRADING LOOP - Direct Arbitrage (from profitable algo)
# =============================================================================

def main():
    """
    Main loop: Direct arbitrage strategy
    - If bid_A - ask_B >= EDGE: Buy B, Sell A
    - If bid_B - ask_A >= EDGE: Sell B, Buy A
    - Execute immediately with IOC orders
    """

    print("=" * 70)
    print("OPTIMAL MERGED ALGORITHM")
    print("=" * 70)
    print(f"Strategy: Direct arbitrage with {EDGE} tick edge")
    print(f"Pair: {STOCK_A_ID} / {STOCK_B_ID}")
    print(f"Volume: {VOLUME} lots per trade")
    print(f"Sleep time: {SLEEP_TIME}s (instant reaction)")
    print("=" * 70)

    # Check starting state
    if not reconcile_positions():
        return

    print("\nStarting trading loop... (Press Ctrl+C to stop)\n")

    iteration = 0
    trade_count = 0

    try:
        while True:
            iteration += 1

            # Get orderbooks
            book_A = exchange.get_last_price_book(STOCK_A_ID)
            book_B = exchange.get_last_price_book(STOCK_B_ID)

            # Validate orderbooks
            if not (book_A and book_A.bids and book_A.asks):
                if iteration % 100 == 1:
                    print(f"[{iteration}] No bids/asks for {STOCK_A_ID}. Waiting...")
                time.sleep(SLEEP_TIME if SLEEP_TIME > 0 else 0.1)
                continue

            if not (book_B and book_B.bids and book_B.asks):
                if iteration % 100 == 1:
                    print(f"[{iteration}] No bids/asks for {STOCK_B_ID}. Waiting...")
                time.sleep(SLEEP_TIME if SLEEP_TIME > 0 else 0.1)
                continue

            # Get top of book prices
            bid_A = book_A.bids[0].price
            ask_A = book_A.asks[0].price
            bid_B = book_B.bids[0].price
            ask_B = book_B.asks[0].price

            # Display status periodically
            if iteration % DISPLAY_INTERVAL == 1:
                print_status(iteration, book_A, book_B)

            # =================================================================
            # ARBITRAGE LOGIC (from profitable algo - proven to work)
            # =================================================================

            # Case 1: B is undervalued → Buy B, Sell A
            if (bid_A - ask_B) >= EDGE:
                trade_count += 1
                print(f"\n>>> ARBITRAGE #{trade_count} @ {dt.datetime.now().strftime('%H:%M:%S')}")
                print(f"Opportunity: B undervalued (bid_A={bid_A:.1f}, ask_B={ask_B:.1f}, edge={bid_A - ask_B:.2f})")

                # Execute: Buy B
                if not trade_would_breach_position_limit(STOCK_B_ID, VOLUME, "bid"):
                    try:
                        exchange.insert_order(
                            instrument_id=STOCK_B_ID,
                            price=round_to_tick(ask_B),
                            volume=VOLUME,
                            side="bid",
                            order_type="ioc",
                        )
                        print(f"  ✓ Bought {VOLUME} x {STOCK_B_ID} @ {ask_B:.1f}")
                    except Exception as e:
                        print(f"  ✗ Failed to buy B: {e}")
                else:
                    print(f"  ⊗ Skipped B buy (position limit)")

                # Execute: Sell A (hedge)
                if not trade_would_breach_position_limit(STOCK_A_ID, VOLUME, "ask"):
                    try:
                        exchange.insert_order(
                            instrument_id=STOCK_A_ID,
                            price=round_to_tick(bid_A),
                            volume=VOLUME,
                            side="ask",
                            order_type="ioc",
                        )
                        print(f"  ✓ Sold {VOLUME} x {STOCK_A_ID} @ {bid_A:.1f}")
                    except Exception as e:
                        print(f"  ✗ Failed to sell A: {e}")
                else:
                    print(f"  ⊗ Skipped A sell (position limit)")

            # Case 2: B is overvalued → Sell B, Buy A
            elif (bid_B - ask_A) >= EDGE:
                trade_count += 1
                print(f"\n>>> ARBITRAGE #{trade_count} @ {dt.datetime.now().strftime('%H:%M:%S')}")
                print(f"Opportunity: B overvalued (bid_B={bid_B:.1f}, ask_A={ask_A:.1f}, edge={bid_B - ask_A:.2f})")

                # Execute: Sell B
                if not trade_would_breach_position_limit(STOCK_B_ID, VOLUME, "ask"):
                    try:
                        exchange.insert_order(
                            instrument_id=STOCK_B_ID,
                            price=round_to_tick(bid_B),
                            volume=VOLUME,
                            side="ask",
                            order_type="ioc",
                        )
                        print(f"  ✓ Sold {VOLUME} x {STOCK_B_ID} @ {bid_B:.1f}")
                    except Exception as e:
                        print(f"  ✗ Failed to sell B: {e}")
                else:
                    print(f"  ⊗ Skipped B sell (position limit)")

                # Execute: Buy A (hedge)
                if not trade_would_breach_position_limit(STOCK_A_ID, VOLUME, "bid"):
                    try:
                        exchange.insert_order(
                            instrument_id=STOCK_A_ID,
                            price=round_to_tick(ask_A),
                            volume=VOLUME,
                            side="bid",
                            order_type="ioc",
                        )
                        print(f"  ✓ Bought {VOLUME} x {STOCK_A_ID} @ {ask_A:.1f}")
                    except Exception as e:
                        print(f"  ✗ Failed to buy A: {e}")
                else:
                    print(f"  ⊗ Skipped A buy (position limit)")

            # Sleep (0.0 = instant loop for maximum speed)
            if SLEEP_TIME > 0:
                time.sleep(SLEEP_TIME)

    except KeyboardInterrupt:
        print("\n\n⚠ Stopped by user")

    except Exception as e:
        print(f"\n\n⚠ Critical error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Final report
        print("\n" + "=" * 70)
        print("FINAL STATE")
        print("=" * 70)

        try:
            positions = exchange.get_positions()
            pnl = exchange.get_pnl()
            pos_a = positions.get(STOCK_A_ID, 0)
            pos_b = positions.get(STOCK_B_ID, 0)
            delta = pos_a + pos_b

            print(f"\nIterations: {iteration:,}")
            print(f"Trades executed: {trade_count}")
            print(f"\nFinal Positions:")
            print(f"  {STOCK_A_ID}: {pos_a:+.0f}")
            print(f"  {STOCK_B_ID}: {pos_b:+.0f}")
            print(f"  Delta: {delta:+.0f}")
            print(f"\nFinal P&L: ${pnl:.2f}")
            print("=" * 70)

        except Exception as e:
            print(f"Error getting final state: {e}")

        # Disconnect
        if exchange.is_connected():
            print("\nDisconnecting...")
            exchange.disconnect()
            print("✓ Disconnected")


if __name__ == "__main__":
    main()
