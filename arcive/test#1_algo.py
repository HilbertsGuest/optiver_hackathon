import datetime as dt
import time
import logging

from optibook.synchronous_client import Exchange

exchange = Exchange()
exchange.connect()

logging.getLogger("client").setLevel("ERROR")

# Configuration
STOCK_A_ID = "PHILLIPS_A"
STOCK_B_ID = "PHILLIPS_B"
POSITION_LIMIT = 100
ARBITRAGE_THRESHOLD = 0.10  # Minimum price difference to trigger trade
TRADE_VOLUME = 5  # Lots to trade per arbitrage opportunity
SLEEP_TIME = 1  # Seconds between iterations


def trade_would_breach_position_limit(instrument_id, volume, side, position_limit=POSITION_LIMIT):
    """Check if a trade would breach position limits"""
    positions = exchange.get_positions()
    position_instrument = positions[instrument_id]

    if side == "bid":
        return position_instrument + volume > position_limit
    elif side == "ask":
        return position_instrument - volume < -position_limit
    else:
        raise Exception(f"""Invalid side provided: {side}, expecting 'bid' or 'ask'.""")


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
    if STOCK_A_ID in positions and STOCK_B_ID in positions:
        delta = positions[STOCK_A_ID] + positions[STOCK_B_ID]
        print(f"  {'Delta (A+B)':20s}: {delta:4.0f}")

    pnl = exchange.get_pnl()
    if pnl:
        print(f"\nPnL: {pnl:.2f}")


def execute_arbitrage(cheap_id, expensive_id, cheap_price, expensive_price, volume):
    """Execute paired trades: buy cheap, sell expensive"""
    print(f"\n>>> ARBITRAGE OPPORTUNITY DETECTED <<<")
    print(f"Buy {volume} lots of {cheap_id} at {cheap_price:.2f}")
    print(f"Sell {volume} lots of {expensive_id} at {expensive_price:.2f}")
    print(f"Expected profit per lot: {expensive_price - cheap_price:.2f}")

    # Check if trades would breach position limits
    can_buy_cheap = not trade_would_breach_position_limit(cheap_id, volume, "bid")
    can_sell_expensive = not trade_would_breach_position_limit(expensive_id, volume, "ask")

    if not can_buy_cheap:
        print(f"Cannot buy {cheap_id} - would breach position limit")
        return False

    if not can_sell_expensive:
        print(f"Cannot sell {expensive_id} - would breach position limit")
        return False

    # Execute both legs of the arbitrage
    print(f"Executing buy order for {cheap_id}...")
    exchange.insert_order(
        instrument_id=cheap_id,
        price=cheap_price,
        volume=volume,
        side="bid",
        order_type="ioc",
    )

    print(f"Executing sell order for {expensive_id}...")
    exchange.insert_order(
        instrument_id=expensive_id,
        price=expensive_price,
        volume=volume,
        side="ask",
        order_type="ioc",
    )

    print(">>> Paired trades executed <<<")
    return True


# Main trading loop
print("=" * 70)
print("DELTA-NEUTRAL DUAL LISTING ARBITRAGE STRATEGY")
print("=" * 70)
print(f"Instruments: {STOCK_A_ID} <-> {STOCK_B_ID}")
print(f"Arbitrage threshold: {ARBITRAGE_THRESHOLD:.2f}")
print(f"Trade volume: {TRADE_VOLUME} lots")
print(f"Position limit: ±{POSITION_LIMIT} lots")
print("=" * 70)

while True:
    print(f"\n{'-' * 70}")
    print(f"ITERATION AT {str(dt.datetime.now()):18s} UTC")
    print(f"{'-' * 70}")

    print_positions_and_pnl(always_display=[STOCK_A_ID, STOCK_B_ID])
    print("")

    # Get both orderbooks
    book_a = exchange.get_last_price_book(STOCK_A_ID)
    book_b = exchange.get_last_price_book(STOCK_B_ID)

    # Validate both orderbooks have data
    if not (book_a and book_a.bids and book_a.asks):
        print(f"Orderbook for {STOCK_A_ID} incomplete. Skipping iteration.")
        time.sleep(SLEEP_TIME)
        continue

    if not (book_b and book_b.bids and book_b.asks):
        print(f"Orderbook for {STOCK_B_ID} incomplete. Skipping iteration.")
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

    # Calculate fair value as average of both midpoints
    fair_value = (a_mid + b_mid) / 2

    print(f"{STOCK_A_ID:15s}: Bid={a_bid:7.2f}  Ask={a_ask:7.2f}  Mid={a_mid:7.2f}")
    print(f"{STOCK_B_ID:15s}: Bid={b_bid:7.2f}  Ask={b_ask:7.2f}  Mid={b_mid:7.2f}")
    print(f"{'Fair Value':15s}: {fair_value:7.2f}")

    # Calculate price discrepancies (how much each deviates from fair value)
    a_deviation = a_mid - fair_value
    b_deviation = b_mid - fair_value

    print(f"\nPrice deviations from fair value:")
    print(f"{STOCK_A_ID}: {a_deviation:+.2f}")
    print(f"{STOCK_B_ID}: {b_deviation:+.2f}")

    # Determine arbitrage opportunity
    # If A is expensive (above fair value), sell A and buy B
    # If B is expensive (above fair value), sell B and buy A

    if abs(a_mid - b_mid) < ARBITRAGE_THRESHOLD:
        print(f"\nNo arbitrage: spread {abs(a_mid - b_mid):.2f} < threshold {ARBITRAGE_THRESHOLD:.2f}")
    else:
        if a_mid > b_mid + ARBITRAGE_THRESHOLD:
            # A is overpriced, B is underpriced
            # Buy B (at ask), Sell A (at bid)
            execute_arbitrage(
                cheap_id=STOCK_B_ID,
                expensive_id=STOCK_A_ID,
                cheap_price=b_ask,  # Pay the ask to buy cheap
                expensive_price=a_bid,  # Hit the bid to sell expensive
                volume=TRADE_VOLUME
            )
        elif b_mid > a_mid + ARBITRAGE_THRESHOLD:
            # B is overpriced, A is underpriced
            # Buy A (at ask), Sell B (at bid)
            execute_arbitrage(
                cheap_id=STOCK_A_ID,
                expensive_id=STOCK_B_ID,
                cheap_price=a_ask,  # Pay the ask to buy cheap
                expensive_price=b_bid,  # Hit the bid to sell expensive
                volume=TRADE_VOLUME
            )

    print(f"\nSleeping for {SLEEP_TIME} seconds...")
    time.sleep(SLEEP_TIME)
