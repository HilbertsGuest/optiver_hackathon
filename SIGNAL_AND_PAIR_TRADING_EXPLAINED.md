# Signal Generation & Pair Trading - Complete Explanation

## The Complete Flow (Step-by-Step)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN TRADING LOOP                             │
│                                                                   │
│  1. Get Orderbooks                                               │
│  2. Data Handler: Calculate Spread                               │
│  3. Signal Generator: Analyze Spread → Generate Signal           │
│  4. Execution Handler: Validate & Execute Signal                 │
│  5. Portfolio Manager: Record Trade                              │
└─────────────────────────────────────────────────────────────────┘
```

Let me explain each part in detail:

---

## Part 1: Data Collection & Spread Calculation

### What Happens:
```python
# 1. Get current prices from both orderbooks
book_a = exchange.get_last_price_book("PHILLIPS_A")
book_b = exchange.get_last_price_book("PHILLIPS_B")

# 2. Calculate midpoint prices (fair value)
mid_a = (book_a.bids[0].price + book_a.asks[0].price) / 2  # e.g., 100.50
mid_b = (book_b.bids[0].price + book_b.asks[0].price) / 2  # e.g., 99.75

# 3. Calculate SPREAD (price ratio)
spread = mid_a / mid_b  # e.g., 100.50 / 99.75 = 1.0075
```

### Why Spread, Not Difference?

**Spread (ratio)**: `spread = price_A / price_B`
- Example: 100.50 / 99.75 = 1.0075
- Means: A is 0.75% more expensive than B

**Why not just difference?**: `difference = price_A - price_B`
- Example: 100.50 - 99.75 = 0.75
- Problem: 0.75 difference means different things if prices are $10 vs $1000

**Ratio is scale-independent!**

### History & Statistics:
```python
# Build history of spreads over time
spread_history = [1.0052, 1.0048, 1.0055, 1.0051, ...]  # 100 data points

# Calculate statistics
mean = 1.0050  # Average spread
std_dev = 0.0015  # Standard deviation (volatility)
```

**If PERFECT_FUNGIBILITY = True:**
```python
# Instead of empirical mean, use theoretical parity
effective_mean = 1.0  # Prices SHOULD be exactly equal
```

---

## Part 2: Signal Generation (The Decision Maker)

### The Logic:

```python
# Calculate entry/exit bands
upper_band = mean + (2.0 * std_dev)  # e.g., 1.0050 + 0.0030 = 1.0080
lower_band = mean - (2.0 * std_dev)  # e.g., 1.0050 - 0.0030 = 1.0020

exit_upper = mean + (0.2 * std_dev)  # e.g., 1.0050 + 0.0003 = 1.0053
exit_lower = mean - (0.2 * std_dev)  # e.g., 1.0050 - 0.0003 = 1.0047
```

### Visual Representation:

```
Spread Value
    │
    │     ┌─── ENTRY: SHORT_PAIR (sell when too high)
1.0080 ────┤   Upper Band (mean + 2*std)
    │     │
    │     │
1.0053 ────┤   Exit Upper (mean + 0.2*std)
    │     │
1.0050 ────┼─── MEAN (equilibrium)
    │     │
1.0047 ────┤   Exit Lower (mean - 0.2*std)
    │     │
    │     │
1.0020 ────┤   Lower Band (mean - 2*std)
    │     └─── ENTRY: LONG_PAIR (buy when too low)
    │
```

### Signal Types Generated:

#### Signal 1: OPEN_SHORT_PAIR
**When**: `spread > upper_band` (A is too expensive)

**Example**:
```python
spread = 1.0082  # Current spread
upper_band = 1.0080

# Spread is ABOVE upper band → A is overpriced!
signal = {
    'type': 'OPEN_SHORT_PAIR',
    'reason': 'spread=1.0082 > upper_band=1.0080',
    'params': {
        'pair': 'PHILLIPS_A-PHILLIPS_B',
        'amount': 50  # lots
    }
}
```

**What it means**:
- PHILLIPS_A is abnormally expensive relative to PHILLIPS_B
- We expect spread to revert back to mean (1.0050)
- **Trade**: Sell A (expensive), Buy B (cheap)

#### Signal 2: OPEN_LONG_PAIR
**When**: `spread < lower_band` (A is too cheap)

**Example**:
```python
spread = 1.0018  # Current spread
lower_band = 1.0020

# Spread is BELOW lower band → A is underpriced!
signal = {
    'type': 'OPEN_LONG_PAIR',
    'reason': 'spread=1.0018 < lower_band=1.0020',
    'params': {
        'pair': 'PHILLIPS_A-PHILLIPS_B',
        'amount': 50
    }
}
```

**What it means**:
- PHILLIPS_A is abnormally cheap relative to PHILLIPS_B
- We expect spread to revert back to mean (1.0050)
- **Trade**: Buy A (cheap), Sell B (expensive)

#### Signal 3: CLOSE_POSITION
**When**: Spread returns near mean

**Example (closing SHORT_PAIR)**:
```python
current_position = 'SHORT_PAIR'  # We're short A, long B
spread = 1.0052  # Current spread
exit_upper = 1.0053

# Spread has reverted to mean!
signal = {
    'type': 'CLOSE_POSITION',
    'reason': 'spread_reverted_to_mean',
    'params': {'pair': 'PHILLIPS_A-PHILLIPS_B'}
}
```

**What it means**:
- We entered when spread was 1.0082 (A expensive)
- Now spread is 1.0052 (near mean)
- **Trade**: Close our position, take profit!

---

## Part 3: handle_signal Function (The Brain)

This is the **guard-rail logic** that validates EVERY signal before executing.

### The 5 Checkpoints:

#### Checkpoint 1: Get Current State
```python
portfolio_state = portfolio.get_state()  # Am I in a position?
book_a = exchange.get_orderbook(ASSET_A)  # What's the market?
book_b = exchange.get_orderbook(ASSET_B)
```

#### Checkpoint 2: Sanity Checks
```python
# Is trading disabled?
if portfolio_state['isTradingDisabled']:
    return  # ABORT!

# Already in a position?
if portfolio.has_position('PHILLIPS_A-PHILLIPS_B'):
    return  # ABORT! No double positions

# Enough money?
if portfolio_state['cash'] < required_margin:
    return  # ABORT! Not enough cash
```

#### Checkpoint 3: Determine Execution Prices

**For SHORT_PAIR** (Sell A, Buy B):
```python
# We SELL A → get bid price (what buyers will pay us)
exec_price_a = book_a.bids[0].price  # e.g., 100.48

# We BUY B → pay ask price (what sellers want)
exec_price_b = book_b.asks[0].price  # e.g., 99.77

# Check volume available
vol_a = book_a.bids[0].volume  # e.g., 150 lots available
vol_b = book_b.asks[0].volume  # e.g., 120 lots available
```

**For LONG_PAIR** (Buy A, Sell B):
```python
# We BUY A → pay ask price
exec_price_a = book_a.asks[0].price  # e.g., 100.52

# We SELL B → get bid price
exec_price_b = book_b.bids[0].price  # e.g., 99.73
```

#### Checkpoint 4: Volume Check (Critical!)
```python
if vol_a < 50:  # Need 50, only have 45
    print("⚠ VOLUME LOCKED")
    return  # ABORT!

if vol_b < 50:
    print("⚠ VOLUME LOCKED")
    return  # ABORT!
```

**Why critical?**
```
You want to buy 50 A and sell 50 B
If only 30 B available:
  - You buy 50 A ✓
  - You sell 30 B ✓
  - Result: +50 A, -30 B
  - Delta: +20 (UNHEDGED EXPOSURE!)
  - DISASTER!
```

#### Checkpoint 5: Slippage Check
```python
# Bid-ask spread on each instrument
spread_a = book_a.asks[0].price - book_a.bids[0].price  # e.g., 0.10
spread_b = book_b.asks[0].price - book_b.bids[0].price  # e.g., 0.08

if spread_a > 0.50:  # Too wide!
    print("⚠ SLIPPAGE RISK HIGH")
    return  # ABORT!
```

**Why check this?**
- Wide bid-ask spread = illiquid or volatile market
- We'd lose too much just entering the trade
- Not worth it

#### Checkpoint 6: Front-Running Check (Final!)
```python
# Re-calculate spread using ACTUAL execution prices
execution_spread = exec_price_a / exec_price_b

# Was signal based on mid-prices
signal_spread = mid_a / mid_b = 1.0082

# But execution prices might be different!
execution_spread = 100.48 / 99.77 = 1.0071

# Check if still above threshold
if execution_spread < upper_threshold:
    print("⚠ FRONT-RUN/SLIPPED")
    return  # ABORT! Opportunity gone
```

**Why critical?**
- Signal generated on mid-prices (theoretical)
- Execution happens at bid/ask (reality)
- Market might have moved between signal and execution
- Other traders might have front-run us

### If ALL Checks Pass:
```python
print(">>> ARBITRAGE OPPORTUNITY <<<")
execute_paired_trade(signal_type, amount, price_a, price_b)
portfolio.open_position(...)
print("✓ Position opened successfully")
```

---

## Part 4: Pair Execution (The Actual Trade)

### SHORT_PAIR Example:

**Market Situation:**
```
PHILLIPS_A: Bid=100.48, Ask=100.52 (mid=100.50)
PHILLIPS_B: Bid=99.73,  Ask=99.77  (mid=99.75)
Spread = 100.50 / 99.75 = 1.0075 (A is 0.75% expensive)
```

**Signal Says:** Open SHORT_PAIR (sell expensive A, buy cheap B)

**Execution:**
```python
# Leg 1: SELL 50 lots of PHILLIPS_A
exchange.insert_order(
    instrument_id="PHILLIPS_A",
    price=100.48,      # Sell at bid (what buyers will pay)
    volume=50,
    side="ask",        # We're asking (selling)
    order_type="ioc"   # Immediate or cancel
)
# Result: -50 PHILLIPS_A, +$5,024 cash

# Leg 2: BUY 50 lots of PHILLIPS_B
exchange.insert_order(
    instrument_id="PHILLIPS_B",
    price=99.77,       # Buy at ask (what sellers want)
    volume=50,
    side="bid",        # We're bidding (buying)
    order_type="ioc"
)
# Result: +50 PHILLIPS_B, -$4,988.50 cash

# Net Result:
# Position: -50 A, +50 B (delta = 0!)
# Cash: +$5,024 - $4,988.50 = +$35.50
```

**Why This Makes Money:**
```
Entry:
  Sold A at 100.48
  Bought B at 99.77
  Difference: 0.71 per share

Exit (when spread reverts to 1.0000):
  Buy back A at ~100.00
  Sell B at ~100.00
  Difference: 0.00 per share

Profit = Entry difference - Exit difference
       = 0.71 - 0.00 = $0.71 per share
       = $0.71 × 50 shares = $35.50
```

### LONG_PAIR Example:

**Market Situation:**
```
PHILLIPS_A: Bid=99.98,  Ask=100.02 (mid=100.00)
PHILLIPS_B: Bid=100.18, Ask=100.22 (mid=100.20)
Spread = 100.00 / 100.20 = 0.9980 (A is 0.2% cheap)
```

**Signal Says:** Open LONG_PAIR (buy cheap A, sell expensive B)

**Execution:**
```python
# Leg 1: BUY 50 lots of PHILLIPS_A
exchange.insert_order(
    instrument_id="PHILLIPS_A",
    price=100.02,      # Buy at ask
    volume=50,
    side="bid",        # We're bidding (buying)
    order_type="ioc"
)
# Result: +50 PHILLIPS_A, -$5,001 cash

# Leg 2: SELL 50 lots of PHILLIPS_B
exchange.insert_order(
    instrument_id="PHILLIPS_B",
    price=100.18,      # Sell at bid
    volume=50,
    side="ask",        # We're asking (selling)
    order_type="ioc"
)
# Result: -50 PHILLIPS_B, +$5,009 cash

# Net Result:
# Position: +50 A, -50 B (delta = 0!)
# Cash: -$5,001 + $5,009 = +$8
```

---

## Part 5: Why Pairs? (The Core Concept)

### What Makes This Delta-Neutral:

**Position:**
```
PHILLIPS_A: +50
PHILLIPS_B: -50
Delta: +50 + (-50) = 0
```

**Market moves up 5%:**
```
Before: A=100, B=100
After:  A=105, B=105

Position value:
  +50 A × 105 = +$5,250
  -50 B × 105 = -$5,250
  Net change: $0
```

**Market moves down 5%:**
```
Before: A=100, B=100
After:  A=95,  B=95

Position value:
  +50 A × 95 = +$4,750
  -50 B × 95 = -$4,750
  Net change: $0
```

**WE DON'T CARE ABOUT MARKET DIRECTION!**

### What We DO Care About: Spread Convergence

**Scenario: SHORT_PAIR**
```
Entry:
  A = 100.50, B = 99.75
  Spread = 1.0075
  Position: -50 A, +50 B

Spread converges to 1.0:
  A = 100.00, B = 100.00
  Spread = 1.0000

Exit (close position):
  Buy back A at 100.00 (we sold at 100.50)
    Profit: 0.50 per share × 50 = $25

  Sell B at 100.00 (we bought at 99.75)
    Profit: 0.25 per share × 50 = $12.50

  Total profit: $37.50
```

**The beauty:** Profit comes from spread change, not price direction!

---

## Part 6: Complete Example (Life of a Trade)

### Iteration 1: Spread Goes Wide
```
[101] 14:25:00
Positions: PHILLIPS_A=+0, PHILLIPS_B=+0, Delta=+0
Spread: 1.0082 | Mean: 1.0050 ± 0.0015
Bands: [1.0020, 1.0080]
Position: None

SIGNAL GENERATED: OPEN_SHORT_PAIR
  Reason: spread=1.0082 > upper_band=1.0080
```

### handle_signal Validates:
```
✓ Not in position
✓ Have margin
✓ Volume available: A=150, B=120
✓ Slippage acceptable: A=0.10, B=0.08
✓ Execution spread still valid: 1.0079

>>> ARBITRAGE OPPORTUNITY <<<
  Signal: OPEN_SHORT_PAIR
  Volume: 50 units
  Prices: PHILLIPS_A=100.48, PHILLIPS_B=99.77
  ✓ Orders submitted
✓ Position opened successfully
```

### Iterations 102-150: Waiting for Mean Reversion
```
[121] 14:25:30
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
Spread: 1.0070 | Mean: 1.0050 ± 0.0015
Position: SHORT_PAIR | P&L: $15.50

[141] 14:26:00
Spread: 1.0058 | Mean: 1.0050 ± 0.0015
Position: SHORT_PAIR | P&L: $28.30
```

### Iteration 151: Spread Reverts to Mean
```
[151] 14:26:15
Spread: 1.0052 | Mean: 1.0050 ± 0.0015
Position: SHORT_PAIR | P&L: $35.20

SIGNAL GENERATED: CLOSE_POSITION
  Reason: spread_reverted_to_mean

>>> CLOSING POSITION <<<
  Volume: 50 units
  ✓ Position closed
  Entry spread: 1.0079
  Exit spread: 1.0052
  Spread change: -0.0027

[161] 14:26:30
Positions: PHILLIPS_A=+0, PHILLIPS_B=+0, Delta=+0
Position: None | P&L: $42.80
```

**Trade complete! Profit captured from spread reversion.**

---

## Summary Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  DATA HANDLER                                                 │
│  - Collects prices from both orderbooks                       │
│  - Calculates spread = price_A / price_B                      │
│  - Maintains 100-point history                                │
│  - Calculates mean and standard deviation                     │
└───────────────────┬──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  SIGNAL GENERATOR                                             │
│  - Compares spread to bands                                   │
│  - If spread > upper_band → SHORT_PAIR signal                 │
│  - If spread < lower_band → LONG_PAIR signal                  │
│  - If spread near mean → CLOSE_POSITION signal                │
└───────────────────┬──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  EXECUTION HANDLER (handle_signal)                            │
│  Checkpoint 1: Get state                                      │
│  Checkpoint 2: Sanity checks (in position? have cash?)        │
│  Checkpoint 3: Determine execution prices                     │
│  Checkpoint 4: Check volume available                         │
│  Checkpoint 5: Check slippage risk                            │
│  Checkpoint 6: Verify signal still valid                      │
│  ─────────────────────────────────────                        │
│  If ALL pass → execute_paired_trade()                         │
└───────────────────┬──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  PAIRED TRADE EXECUTION                                       │
│  SHORT_PAIR: Sell A + Buy B (equal volumes)                   │
│  LONG_PAIR:  Buy A + Sell B (equal volumes)                   │
│  Result: Delta = 0 (market neutral)                           │
└───────────────────┬──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  PORTFOLIO MANAGER                                            │
│  - Records position type (LONG_PAIR or SHORT_PAIR)            │
│  - Records entry spread and prices                            │
│  - Monitors for exit signals                                  │
│  - Calculates P&L                                             │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Pairs = Two Offsetting Trades**
   - Always equal volumes
   - Opposite directions
   - Result: Delta = 0

2. **We Profit From Spread Changes**
   - Not from market direction
   - From mean reversion
   - From perfect fungibility enforcement

3. **handle_signal = Safety First**
   - 6 checkpoints before trading
   - Prevents disasters (partial fills, front-running, slippage)
   - Aborts at first sign of trouble

4. **Signals = When To Act**
   - Based on statistical analysis
   - Entry when spread deviates >2 std
   - Exit when spread reverts to mean

This is **professional-grade statistical arbitrage**!
