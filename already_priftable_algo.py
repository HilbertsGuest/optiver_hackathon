import datetime as dt
import time
import logging

from optibook.synchronous_client import Exchange

exchange = Exchange()
exchange.connect()

logging.getLogger("client").setLevel("ERROR")


def trade_would_breach_position_limit(instrument_id, volume, side, position_limit=100):
    positions = exchange.get_positions()
    position_instrument = positions[instrument_id]

    if side == "bid":
        return position_instrument + volume > position_limit
    elif side == "ask":
        return position_instrument - volume < -position_limit
    else:
        raise Exception(f"Invalid side: {side}, expecting 'bid' or 'ask'.")


def print_positions_and_pnl(always_display=None):
    positions = exchange.get_positions()
    print("Positions:")
    for instrument_id in positions:
        if (
            not always_display
            or instrument_id in always_display
            or positions[instrument_id] != 0
        ):
            print(f"  {instrument_id:20s}: {positions[instrument_id]:4.0f}")

    pnl = exchange.get_pnl()
    if pnl:
        print(f"\nPnL: {pnl:.2f}")


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------
STOCK_A_ID = "PHILIPS_A"   # Primary / leader
STOCK_B_ID = "PHILIPS_B"   # Secondary / follower

EDGE = 0.1                  # Minimum mispricing (1 tick)
VOLUME = 10                  # Lots per trade
SLEEP_TIME = 0.           # Loop interval (seconds)
TICK_SIZE = 0.1             # Exchange tick size


def round_to_tick(price):
    """Ensure submitted prices are aligned with tick size."""
    return round(price / TICK_SIZE) * TICK_SIZE


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------
while True:
    print("\n-----------------------------------------------------------------")
    print(f"TRADE LOOP ITERATION ENTERED AT {str(dt.datetime.now()):18s} UTC.")
    print("-----------------------------------------------------------------")

    print_positions_and_pnl(always_display=[STOCK_A_ID, STOCK_B_ID])
    print("")

    # Obtain both order books
    book_A = exchange.get_last_price_book(STOCK_A_ID)
    book_B = exchange.get_last_price_book(STOCK_B_ID)
    print(book_A)
    print(book_B)

    if not (book_A and book_A.bids and book_A.asks):
        print(f"No bids/asks for {STOCK_A_ID}. Skipping.")
        time.sleep(SLEEP_TIME)
        continue
    if not (book_B and book_B.bids and book_B.asks):
        print(f"No bids/asks for {STOCK_B_ID}. Skipping.")
        time.sleep(SLEEP_TIME)
        continue

    bid_A, ask_A = book_A.bids[0].price, book_A.asks[0].price
    bid_B, ask_B = book_B.bids[0].price, book_B.asks[0].price

    print(
        f"Top of book  A: {bid_A:.2f} :: {ask_A:.2f}    |    "
        f"B: {bid_B:.2f} :: {ask_B:.2f}"
    )

    # ---------------------------------------
    # Arbitrage logic
    # ---------------------------------------
    # Case 1: B too cheap (buy B, sell A)
    if (bid_A - ask_B) >= EDGE:
        print("Detected B undervalued vs A → Buy B / Sell A")

        if not trade_would_breach_position_limit(STOCK_B_ID, VOLUME, "bid"):
            exchange.insert_order(
                instrument_id=STOCK_B_ID,
                price=round_to_tick(ask_B),
                volume=VOLUME,
                side="bid",
                order_type="ioc",
            )
            print(f"  Bought {VOLUME} B at {ask_B:.2f}")
        else:
            print("  Skipped B buy (position limit).")

        if not trade_would_breach_position_limit(STOCK_A_ID, VOLUME, "ask"):
            exchange.insert_order(
                instrument_id=STOCK_A_ID,
                price=round_to_tick(bid_A),
                volume=VOLUME,
                side="ask",
                order_type="ioc",
            )
            print(f"  Hedged by selling {VOLUME} A at {bid_A:.2f}")
        else:
            print("  Skipped A hedge (position limit).")

    # Case 2: B too expensive (sell B, buy A)
    elif (bid_B - ask_A) >= EDGE:
        print("Detected B overvalued vs A → Sell B / Buy A")

        if not trade_would_breach_position_limit(STOCK_B_ID, VOLUME, "ask"):
            exchange.insert_order(
                instrument_id=STOCK_B_ID,
                price=round_to_tick(bid_B),
                volume=VOLUME,
                side="ask",
                order_type="ioc",
            )
            print(f"  Sold {VOLUME} B at {bid_B:.2f}")
        else:
            print("  Skipped B sell (position limit).")

        if not trade_would_breach_position_limit(STOCK_A_ID, VOLUME, "bid"):
            exchange.insert_order(
                instrument_id=STOCK_A_ID,
                price=round_to_tick(ask_A),
                volume=VOLUME,
                side="bid",
                order_type="ioc",
            )
            print(f"  Hedged by buying {VOLUME} A at {ask_A:.2f}")
        else:
            print("  Skipped A hedge (position limit).")

    else:
        print("No arbitrage opportunity (within 1 tick).")

    print(f"\nSleeping for {SLEEP_TIME} seconds.")
    time.sleep(SLEEP_TIME)