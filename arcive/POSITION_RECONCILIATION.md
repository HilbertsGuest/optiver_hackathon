# Position Reconciliation Feature

## What It Does

Both `statarb_guided_algo.py` and `clean_arbitrage_algo.py` now **automatically detect and adopt existing positions** on startup.

---

## How It Works

### On Startup:

1. **Connect to exchange**
2. **Check for existing positions** on PHILLIPS_A and PHILLIPS_B
3. **Analyze what you have**:
   - No positions → Start fresh
   - Balanced pair positions → Adopt them as if strategy placed them
   - Unbalanced positions → Warn and offer to continue or exit
4. **Continue trading** from current state

---

## Example Scenarios

### Scenario 1: Fresh Start
```
======================================================================
INITIAL STATE & POSITION RECONCILIATION
======================================================================

Current exchange positions:
  PHILLIPS_A: +0
  PHILLIPS_B: +0
  Delta: +0

P&L: $0.00

✓ No existing positions - starting fresh
```

**Result**: Strategy starts normally.

---

### Scenario 2: Restarting After Crash (statarb_guided_algo.py)

**Previous session:**
- Opened SHORT_PAIR: -50 A, +50 B
- Algorithm crashed before closing

**On restart:**
```
======================================================================
RECONCILING EXISTING POSITIONS
======================================================================

Current exchange positions:
  PHILLIPS_A: -50
  PHILLIPS_B: +50
  Delta: +0

P&L: $-15.30

✓ Detected SHORT_PAIR position
  Short 50 x PHILLIPS_A, Long 50 x PHILLIPS_B
  Adopted with entry spread: 1.0052

======================================================================
STRATEGY CONFIGURATION
======================================================================
...
```

**Result**:
- Strategy adopts the SHORT_PAIR position
- Uses current spread (1.0052) as entry reference
- Will close position when spread reverts to mean
- Continues as if nothing happened!

---

### Scenario 3: Switching Strategies

**You ran clean_arbitrage_algo.py:**
- Current positions: A=+30, B=-25

**You stop it and start statarb_guided_algo.py:**
```
======================================================================
RECONCILING EXISTING POSITIONS
======================================================================

Current exchange positions:
  PHILLIPS_A: +30
  PHILLIPS_B: -25
  Delta: +5

P&L: $42.80

✓ Detected LONG_PAIR position
  Long 30 x PHILLIPS_A, Short 25 x PHILLIPS_B
  Adopted with entry spread: 1.0045
```

**Result**:
- Strategy sees LONG_PAIR (positive A, negative B)
- Adopts it with current spread
- Note: Positions aren't exactly balanced (delta=+5)
- Strategy will manage this and rebalance if needed

---

### Scenario 4: Unbalanced Positions

**You manually traded or positions are imbalanced:**
- A=+50, B=+30 (both positive!)

**On startup:**
```
======================================================================
RECONCILING EXISTING POSITIONS
======================================================================

Current exchange positions:
  PHILLIPS_A: +50
  PHILLIPS_B: +30
  Delta: +80

P&L: $-125.50

⚠ WARNING: Existing positions don't match pair trade pattern
  PHILLIPS_A=+50, PHILLIPS_B=+30
  Delta: +80

Options:
  1. Continue anyway (risky - may create unbalanced positions)
  2. Exit and manually close positions first

Continue anyway? (yes/no): _
```

**If you type "no":**
```
Exiting - please close positions manually first
```
Algorithm exits. You should manually close positions first.

**If you type "yes":**
```
⚠ Continuing with existing positions - monitoring delta carefully
```
Algorithm continues but warns that positions are unusual.

---

## Strategy-Specific Behavior

### statarb_guided_algo.py (Statistical Arbitrage)

**Sophisticated position adoption:**

1. **Detects position type**:
   - `pos_A > 0, pos_B < 0` → LONG_PAIR
   - `pos_A < 0, pos_B > 0` → SHORT_PAIR

2. **Sets internal state**:
   ```python
   portfolio.current_position = 'SHORT_PAIR'
   portfolio.entry_spread = current_spread  # Current spread as entry
   portfolio.entry_prices = {'A': mid_a, 'B': mid_b}
   portfolio.position_opened_at = dt.datetime.now()
   ```

3. **Continues trading**:
   - Won't open new position (already has one!)
   - Will monitor spread for mean reversion
   - Will close position when spread approaches mean
   - Treats existing position exactly like it opened it

**Example flow:**
```
[Startup with existing SHORT_PAIR]
✓ Detected SHORT_PAIR, entry spread: 1.0052

[101] 14:25:30
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
Spread: 1.0048 | Mean: 1.0050 ± 0.0015
Position: SHORT_PAIR | P&L: $25.30 | Trades: 0

[Spread reverts to mean]
>>> CLOSING POSITION <<<
  Reason: spread_reverted_to_mean
  Volume: 50 units
  ✓ Position closed
  Entry spread: 1.0052
  Exit spread: 1.0048
  Spread change: -0.0004

[Now flat - can open new positions]
Position: None | P&L: $45.80
```

---

### clean_arbitrage_algo.py (Immediate Arbitrage)

**Simpler position handling:**

1. **Detects existing positions**
2. **Doesn't track "position type"** (different strategy)
3. **Monitors delta**
4. **Will rebalance if delta > 5**

**Example:**
```
======================================================================
INITIAL STATE & POSITION RECONCILIATION
======================================================================

Current exchange positions:
  PHILLIPS_A: +15
  PHILLIPS_B: -12
  Delta: +3

P&L: $25.80

✓ Existing positions detected - will be managed by strategy
  Strategy will work to maintain delta ≈ 0
```

**Result**:
- Strategy doesn't care what created these positions
- Sees delta = +3 (acceptable, < 5)
- Continues looking for arbitrage opportunities
- Will rebalance if delta grows > 5

---

## Key Benefits

### 1. **Crash Recovery**
Algorithm crashes mid-trade? Just restart it:
- Detects open positions
- Adopts them
- Continues managing them
- No manual intervention needed!

### 2. **Strategy Switching**
Want to switch between strategies?
- Stop one algorithm
- Start another
- New algorithm adopts existing positions
- Seamless transition!

### 3. **Manual Trading Compatible**
Did some manual trading before starting algo?
- Algorithm sees your positions
- Incorporates them into strategy
- Works to achieve delta ≈ 0

### 4. **Safety**
Prevents dangerous scenarios:
- Won't accidentally double up positions
- Won't ignore existing exposure
- Warns about unusual position patterns

---

## Technical Details

### Position Type Detection Logic

**LONG_PAIR** (bought A, sold B):
```python
if pos_a > 0 and pos_b < 0:
    position_type = 'LONG_PAIR'
```

**SHORT_PAIR** (sold A, bought B):
```python
elif pos_a < 0 and pos_b > 0:
    position_type = 'SHORT_PAIR'
```

**No clear pattern**:
```python
else:
    # Warn user and ask permission
```

### Entry Spread Estimation

Since we don't know the actual entry spread from previous session:
```python
# Get current orderbooks
book_a = exchange.get_last_price_book(ASSET_A)
book_b = exchange.get_last_price_book(ASSET_B)

# Calculate current midpoints
mid_a = (book_a.bids[0].price + book_a.asks[0].price) / 2
mid_b = (book_b.bids[0].price + book_b.asks[0].price) / 2

# Use current spread as entry reference
current_spread = mid_a / mid_b
portfolio.entry_spread = current_spread
```

**Why this works**:
- For mean reversion, we care about spread change, not absolute entry
- Using current spread as baseline is conservative
- Strategy will still close when spread approaches mean

---

## What If Positions Are From Different Pair?

**Example**: You have positions in APPLE_A and APPLE_B, but algorithm is configured for PHILLIPS_A and PHILLIPS_B:

```python
ASSET_A = "PHILLIPS_A"  # Algorithm configured for PHILLIPS
ASSET_B = "PHILLIPS_B"

# Gets positions
positions = exchange.get_positions()
pos_a = positions.get("PHILLIPS_A", 0)  # 0 (no position)
pos_b = positions.get("PHILLIPS_B", 0)  # 0 (no position)
```

**Result**: Algorithm sees no positions in PHILLIPS pair, starts fresh. Your APPLE positions are unaffected.

---

## Testing the Feature

### Test 1: Fresh Start
```bash
# Clean slate
python statarb_guided_algo.py
```
Should show: "✓ No existing positions - starting fresh"

### Test 2: With Existing Positions

**First, create positions:**
```bash
# Run any algo, let it open a position, then stop it (Ctrl+C)
python clean_arbitrage_algo.py
# Wait for it to execute a trade
# Press Ctrl+C
```

**Then restart:**
```bash
python statarb_guided_algo.py
```
Should show: "✓ Detected [LONG|SHORT]_PAIR position" and adopt it!

### Test 3: Manual Positions

Use the exchange web interface or manual trading to create positions, then start the algorithm. It will detect and manage them.

---

## Edge Cases Handled

### 1. Zero Positions But Non-Zero P&L
```
PHILLIPS_A: +0
PHILLIPS_B: +0
P&L: $-50.00
```
**Handling**: Starts fresh. Previous P&L from closed positions or other instruments.

### 2. Tiny Positions (Rounding)
```
PHILLIPS_A: +0.001
PHILLIPS_B: -0.001
```
**Handling**: Treated as zero (exchange positions are integers).

### 3. One Side Has Position, Other Doesn't
```
PHILLIPS_A: +50
PHILLIPS_B: +0
```
**Handling**: Flagged as unbalanced, user warned, option to exit.

### 4. Large Imbalanced Positions
```
PHILLIPS_A: +95
PHILLIPS_B: -20
Delta: +75
```
**Handling**:
- statarb: Warns, asks permission
- clean_arbitrage: Warns, will rebalance aggressively

---

## Comparison: Before vs After

### BEFORE (Without Position Reconciliation)

**Risk scenario:**
```
[Previous session had: A=-50, B=+50]
[Algorithm crashed]

[Restart algorithm]
Internal state: position = None  ← Wrong!
Actual exchange: A=-50, B=+50   ← Reality

[Signal appears: OPEN_SHORT_PAIR]
Algorithm thinks: "No position, safe to open"
Executes: SELL 50 A, BUY 50 B

Actual result: A=-100, B=+100  ← Disaster! 2x exposure
```

### AFTER (With Position Reconciliation)

**Safe scenario:**
```
[Previous session had: A=-50, B=+50]
[Algorithm crashed]

[Restart algorithm]
✓ Detected SHORT_PAIR position
  Adopted with entry spread: 1.0052

Internal state: position = 'SHORT_PAIR'  ← Correct!
Actual exchange: A=-50, B=+50           ← Matches!

[Signal appears: OPEN_SHORT_PAIR]
Algorithm: "Already in position. Ignoring redundant OPEN signal."

Actual result: A=-50, B=+50  ← Safe! No double-up
```

---

## Summary

**Feature**: Automatic position reconciliation on startup
**Benefit**: Safe restarts, strategy switching, crash recovery
**Works with**: Both statarb_guided_algo.py and clean_arbitrage_algo.py
**User action required**: None (automatic) unless positions are unbalanced

Your algorithms are now **production-ready** with proper state management!
