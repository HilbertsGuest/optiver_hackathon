# Console Output Comparison

## Changes Made to `statarb_guided_algo.py`

Integrated the cleaner, more concise console output format from `clean_arbitrage_algo.py` into the statistical arbitrage strategy.

---

## Before vs After

### Status Display (Every 20 iterations)

**BEFORE:**
```
----------------------------------------------------------------------
[41] 14:23:45

Spread: 1.0052 | Mean: 1.0048 | Std: 0.0018
Bands: [1.0012, 1.0084]
Position: SHORT_PAIR | PHILLIPS_A=-50, PHILLIPS_B=+50
P&L: $45.30 | Trades: 3
```

**AFTER (Improved):**
```
----------------------------------------------------------------------
[41] 14:23:45
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
Spread: 1.0052 | Mean: 1.0048 ± 0.0018
Bands: [1.0012, 1.0084]
Position: SHORT_PAIR | P&L: $45.30 | Trades: 3
```

**Improvements:**
- ✓ Shows **Delta explicitly** (key metric for strategy)
- ✓ More compact position display
- ✓ Better formatting with ± symbol for mean ± std
- ✓ All key info on fewer lines

---

### Trade Execution Messages

**BEFORE:**
```
>>> CHECKS PASSED <<<
Signal: OPEN_SHORT_PAIR
Reason: spread=1.0078 > upper_band=1.0075
Amount: 50 units
Execution spread: 1.0076
Expected entry: A=100.50, B=99.75

  Executing: SELL 50 x PHILLIPS_A @ 100.50
  Executing: BUY 50 x PHILLIPS_B @ 99.75
```

**AFTER (Cleaner):**
```
>>> ARBITRAGE OPPORTUNITY <<<
  Signal: OPEN_SHORT_PAIR
  Reason: spread=1.0078 > upper_band=1.0075
  Volume: 50 units
  Execution spread: 1.0076
  Prices: PHILLIPS_A=100.50, PHILLIPS_B=99.75
  ✓ Orders submitted
```

**Improvements:**
- ✓ Consistent header format with other algos
- ✓ Indented output for readability
- ✓ Condensed price display
- ✓ Clear success indicator (✓)
- ✓ Removed verbose intermediate messages

---

### Position Closing

**BEFORE:**
```
>>> CLOSING POSITION <<<
Reason: spread_reverted_to_mean
Closing 50 units
✓ Position closed
  Entry spread: 1.0076
  Exit spread: 1.0048
  Change: -0.0028
```

**AFTER (Consistent):**
```
>>> CLOSING POSITION <<<
  Reason: spread_reverted_to_mean
  Volume: 50 units
  ✓ Position closed
  Entry spread: 1.0076
  Exit spread: 1.0048
  Spread change: -0.0028
```

**Improvements:**
- ✓ Consistent indentation
- ✓ Labeled "Volume" for clarity
- ✓ "Spread change" instead of just "Change"

---

## Key Benefits

### 1. **Delta Visibility**
The most critical metric for pair trading is now prominently displayed:
```
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
```
Previously hidden, now front and center.

### 2. **Consistent Formatting**
All three algorithms now share similar output styles:
- `clean_arbitrage_algo.py` ✓
- `statarb_guided_algo.py` ✓ (now updated)
- `aggressive_algo.py` ✓

### 3. **Readability**
- Indented output (2 spaces)
- Clear symbols (✓, ✗, ⚠)
- Consistent terminology ("Volume" not "Amount")

### 4. **Information Density**
Same information in fewer lines:
- Before: 6-7 lines per update
- After: 4-5 lines per update

---

## Complete Output Example

### During Normal Operation

```
======================================================================
STATISTICAL ARBITRAGE STRATEGY - Following guide.md
======================================================================
✓ Connected to exchange

Pair: PHILLIPS_A / PHILLIPS_B
Entry threshold: ± 2.0 std deviations
Exit threshold: ± 0.2 std deviations
Building spread history (100 points)...
======================================================================

Press Ctrl+C to stop

----------------------------------------------------------------------
[1] 14:20:15
Spread: 1.0045 | Building history... 1/100

----------------------------------------------------------------------
[21] 14:20:30
Spread: 1.0048 | Building history... 21/100

----------------------------------------------------------------------
[101] 14:22:00
Positions: PHILLIPS_A=+0, PHILLIPS_B=+0, Delta=+0
Spread: 1.0052 | Mean: 1.0048 ± 0.0015
Bands: [1.0018, 1.0078]
Position: None | P&L: $0.00 | Trades: 0

>>> ARBITRAGE OPPORTUNITY <<<
  Signal: OPEN_SHORT_PAIR
  Reason: spread=1.0082 > upper_band=1.0078
  Volume: 50 units
  Execution spread: 1.0080
  Prices: PHILLIPS_A=100.50, PHILLIPS_B=99.70
  ✓ Orders submitted
✓ Position opened successfully

----------------------------------------------------------------------
[121] 14:22:20
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
Spread: 1.0055 | Mean: 1.0050 ± 0.0016
Bands: [1.0018, 1.0082]
Position: SHORT_PAIR | P&L: $25.50 | Trades: 1

----------------------------------------------------------------------
[201] 14:24:30
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
Spread: 1.0048 | Mean: 1.0048 ± 0.0015
Bands: [1.0018, 1.0078]
Position: SHORT_PAIR | P&L: $62.30 | Trades: 1

>>> CLOSING POSITION <<<
  Reason: spread_reverted_to_mean
  Volume: 50 units
  ✓ Position closed
  Entry spread: 1.0080
  Exit spread: 1.0048
  Spread change: -0.0032

----------------------------------------------------------------------
[221] 14:24:50
Positions: PHILLIPS_A=+0, PHILLIPS_B=+0, Delta=+0
Spread: 1.0046 | Mean: 1.0048 ± 0.0015
Bands: [1.0018, 1.0078]
Position: None | P&L: $85.20 | Trades: 1

⚠ Stopped by user

======================================================================
FINAL STATE
======================================================================

Iterations: 250
Total trades: 1
Current position: None
Positions: PHILLIPS_A=+0, PHILLIPS_B=+0
Final P&L: $85.20

Final spread stats:
  Last spread: 1.0046
  Mean: 1.0048
  Std Dev: 0.0015
======================================================================

Disconnecting...
✓ Disconnected
```

---

## Side-by-Side Comparison

| Aspect | clean_arbitrage | statarb (old) | statarb (NEW) |
|--------|----------------|---------------|---------------|
| **Delta display** | ✓ Explicit | ✗ Hidden | ✓ Explicit |
| **Position format** | `A=+15, B=-12` | `A=-50, B=+50` | `A=+15, B=-12, Delta=+3` |
| **Trade header** | "ARBITRAGE OPPORTUNITY" | "CHECKS PASSED" | "ARBITRAGE OPPORTUNITY" |
| **Indentation** | ✓ 2 spaces | ✗ Mixed | ✓ 2 spaces |
| **Status symbols** | ✓ ✗ ⚠ | ✓ ✗ ⚠ | ✓ ✗ ⚠ |
| **Spread stats** | ✗ Not shown | ✓ Shown | ✓ Shown (improved) |
| **Lines per update** | 4 | 6 | 5 |

---

## Testing the Output

To see the new output format:

```bash
cd your_optiver_workspace/dual_listing
python statarb_guided_algo.py
```

Watch for:
1. **Delta in status updates** - Should always be near 0
2. **Clean trade messages** - Indented and consistent
3. **Spread statistics** - Mean ± Std format
4. **Position clarity** - Easy to see both positions and delta at a glance

---

## Benefits for Competition Day

### Quick Status Check
One glance tells you:
```
Positions: PHILLIPS_A=-50, PHILLIPS_B=+50, Delta=+0
```
- What you own
- What delta is (critical!)
- If strategy is working

### Easy Monitoring
```
Position: SHORT_PAIR | P&L: $62.30 | Trades: 1
```
- Current strategy state
- Current profit
- Trade count

### Clear Alerts
```
⚠ FRONT-RUN/SLIPPED. Signal invalid at execution prices.
✓ Orders submitted
✗ CRITICAL: PARTIAL FILL OR ORDER FAILURE
```
- Easy to spot problems
- Clear success/failure indicators

---

## Summary

**What changed**: Console output formatting
**What didn't change**: Strategy logic, trading decisions, risk checks
**Result**: Same powerful strategy, much easier to monitor

The statistical arbitrage strategy now has the same clean, professional output as the clean_arbitrage strategy, making it easier to monitor during competition!
