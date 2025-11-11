# Data-Driven Strategy Optimization Guide

## Quick Start: Collect & Analyze Workflow

### Step 1: Run Data Logging Algorithm
```bash
cd your_optiver_workspace/dual_listing
python data_logging_algo.py
```

Let it run for 5-10 minutes, then press `Ctrl+C` to stop gracefully.

### Step 2: Analyze the Data
```bash
python analyze_trading_data.py 20251111_140530
# Replace with your session timestamp
```

### Step 3: Adjust Parameters Based on Analysis
Use insights from analysis to modify configuration in your algorithm.

### Step 4: Repeat
Run again with new parameters, compare results.

---

## What Data Gets Collected

### 1. Iteration Log (`iterations_TIMESTAMP.csv`)
**Every iteration records:**
- Timestamp
- Both orderbooks (bid/ask/mid for PHILLIPS_A and PHILLIPS_B)
- Calculated spread and fair value
- Current positions and delta
- Current P&L
- Whether opportunity was detected
- Whether trade was executed
- Reason (why traded or why skipped)

**Use this for:**
- Understanding market conditions
- Threshold sensitivity analysis
- Identifying missed opportunities
- Validating delta neutrality

### 2. Trade Log (`trades_TIMESTAMP.csv`)
**Every trade records:**
- Which instruments traded (cheap vs expensive)
- Prices and volumes
- Expected profit
- Positions before and after trade
- P&L before and after trade
- Actual P&L change from trade

**Use this for:**
- Calculating actual fill rates
- Profitability analysis
- Volume optimization
- Execution quality assessment

### 3. Summary Log (`summary_TIMESTAMP.json`)
**Session-level statistics:**
- Total iterations, opportunities, trades
- Execution rates
- P&L performance
- Delta statistics
- Position utilization
- Configuration used

**Use this for:**
- Quick session comparison
- High-level performance metrics
- Parameter tracking

---

## Key Analyses & How to Use Them

### 1. Threshold Sensitivity Analysis

**What it shows:** How many opportunities you would capture at different threshold levels.

**Example output:**
```
Threshold    Opportunities   Avg Spread
0.01         450            0.045
0.02         280  <--       0.062  (CURRENT)
0.05         120            0.098
0.10          45            0.156
```

**How to optimize:**

**If you see:**
- Many opportunities at lower thresholds (e.g., 450 at 0.01 vs 280 at 0.02)
  - **Action:** LOWER threshold to 0.01
  - **Rationale:** You're missing 170 profitable opportunities

- Few additional opportunities at lower thresholds (e.g., 290 at 0.01 vs 280 at 0.02)
  - **Action:** KEEP current threshold
  - **Rationale:** Lower threshold adds complexity for minimal gain

- Very few opportunities at current threshold (e.g., 45 at 0.10)
  - **Action:** DRASTICALLY LOWER to 0.02-0.03
  - **Rationale:** Market doesn't have large spreads often

**Optimal range:** Typically 0.01 - 0.05 depending on market volatility

---

### 2. Volume Optimization Analysis

**What it shows:** Distribution of trade volumes and if you're hitting limits.

**Example output:**
```
Trade volume distribution:
  Min traded: 10 lots
  Max traded: 50 lots
  Avg traded: 32.5 lots

  Trades at MAX volume (50): 45 (75%)  ← Problem!
  Trades at MIN volume (10): 3 (5%)
```

**How to optimize:**

**If 30%+ trades hit MAX volume:**
```python
# You're leaving money on the table
MAX_TRADE_VOLUME = 80  # Increase from 50
```

**If 50%+ trades at MIN volume:**
```python
# Market doesn't support large trades
MIN_TRADE_VOLUME = 5   # Decrease from 10
MAX_TRADE_VOLUME = 25  # Also decrease max
```

**If well distributed (10-30% at max, 10-30% at min):**
```python
# Keep current settings - well calibrated
```

**Optimal:** Avg volume around 50-60% of MAX, with 10-20% of trades hitting maximum.

---

### 3. Timing & Latency Analysis

**What it shows:** Iteration efficiency and if your speed is optimal.

**Example output:**
```
Iteration efficiency:
  Total iterations: 3000
  Opportunities: 280 (9.3%)
  Trades executed: 220 (7.3%)

  Idle iterations: 2780 (92.7%)
```

**How to optimize:**

**If 95%+ iterations idle:**
```python
# You're wasting CPU cycles
SLEEP_TIME = 0.5  # Slow down from 0.2
```
**Benefit:** Same performance, less resource usage

**If <70% iterations idle (>30% active):**
```python
# Market is VERY active
SLEEP_TIME = 0.1  # Speed up from 0.2
```
**Benefit:** Catch more opportunities before they disappear

**If 85-93% idle:**
```python
# Keep current speed - well balanced
```

**Advanced:** If market has bursts of activity, consider adaptive sleep times.

---

### 4. Delta Neutrality Analysis

**What it shows:** How well you're maintaining market-neutral positioning.

**Example output:**
```
Delta statistics:
  Max delta: 8 lots
  Avg delta: 1.2 lots

Delta distribution:
  Perfect (≤1): 2400 (80%)
  Good (≤5): 2850 (95%)
  Concerning (>20): 0 (0%)
```

**How to interpret:**

**Excellent (like example above):**
- Avg delta < 2
- 95%+ iterations with delta ≤ 5
- No large delta spikes
- **Action:** Keep current approach

**Concerning:**
```
Max delta: 45 lots
Avg delta: 12.3 lots
Concerning (>20): 300 (10%)
```
- **Problem:** Trades not executing in pairs
- **Possible causes:**
  - One leg filling, other rejected
  - Partial fills
  - Position limit hit on one side
- **Action:** Review trade execution logic, check for order rejections

**Delta drift is the biggest risk** - monitor closely.

---

### 5. Profitability Analysis

**What it shows:** Expected profit vs actual P&L.

**Example output:**
```
Expected vs Actual:
  Total expected profit: $2,450.00
  Final P&L: $1,960.00
  Estimated fill rate: 80.0%
```

**How to interpret:**

**Fill rate >80%:**
- Excellent execution
- IOC orders working well
- Keep current approach

**Fill rate 50-80%:**
- Moderate execution
- Consider limit orders instead of IOC
- May be crossing spread too aggressively

**Fill rate <50%:**
- Poor execution
- **Problem:** Orders not filling
- **Solutions:**
  - Use limit orders at mid-price
  - Improve price calculation
  - Check for stale orderbook data

**Expected fill rate:** 70-90% for IOC orders on liquid markets.

---

### 6. Missed Opportunity Analysis

**What it shows:** Why opportunities weren't captured.

**Example output:**
```
Missed opportunities breakdown:
  insufficient_capacity: 45 (75%)
  spread_too_small_0.018: 10 (17%)
  orderbook_a_incomplete: 5 (8%)
```

**How to optimize:**

**If "insufficient_capacity" > 30%:**
```python
# Hitting position limits too often
# Option 1: Reduce trade sizes
MIN_TRADE_VOLUME = 5   # From 10
MAX_TRADE_VOLUME = 30  # From 50

# Option 2: Increase buffer (more conservative)
POSITION_BUFFER = 10   # From 5

# Option 3: Add position unwinding logic
# (Advanced - requires additional code)
```

**If "orderbook incomplete" > 10%:**
- Network issues
- Exchange connectivity problems
- Add retry logic or error handling

**If "spread_too_small" common:**
- Your threshold is well-calibrated
- Market naturally consolidating
- Consider lowering threshold slightly

---

## Iterative Optimization Process

### Round 1: Baseline
```python
# Start conservative
ARBITRAGE_THRESHOLD = 0.05
MIN_TRADE_VOLUME = 10
MAX_TRADE_VOLUME = 30
SLEEP_TIME = 0.5
```

**Run for 5 minutes → Analyze**

### Round 2: Increase Sensitivity
Based on threshold analysis:
```python
ARBITRAGE_THRESHOLD = 0.02  # Lowered
# Keep others same
```

**Run for 5 minutes → Analyze**

### Round 3: Optimize Volume
Based on volume analysis:
```python
ARBITRAGE_THRESHOLD = 0.02
MAX_TRADE_VOLUME = 50  # Increased
# Keep others same
```

**Run for 5 minutes → Analyze**

### Round 4: Optimize Speed
Based on timing analysis:
```python
ARBITRAGE_THRESHOLD = 0.02
MAX_TRADE_VOLUME = 50
SLEEP_TIME = 0.2  # Decreased
```

**Run for 10 minutes → Final validation**

### Round 5: Fine-tune
Make small adjustments:
```python
ARBITRAGE_THRESHOLD = 0.015  # Slight tweak
MIN_TRADE_VOLUME = 12       # Slight tweak
```

**Run for competition!**

---

## Real-Time Monitoring During Competition

While algorithm runs, watch for:

### Every 50 iterations (automatic output):
```
Performance:
  Opportunities: 45
  Trades executed: 38
  Execution rate: 84.4%  ← Should be >70%
  Avg spread: 0.035      ← Shows market conditions
  Total expected profit: $450.00
```

### Position status:
```
Positions:
  PHILLIPS_A: +42
  PHILLIPS_B: -40
  Delta: +2              ← Should be close to 0
  Position Util: 42.0%   ← Can go higher
```

### Red flags to watch for:
1. **Delta > 10:** Something wrong with trade execution
2. **Execution rate < 50%:** Orders not filling
3. **Opportunities = 0 for >1 minute:** Threshold too high or market dead
4. **Position util hitting 100%:** Need to unwind or reduce volume

---

## Quick Reference: Parameter Impact Table

| Parameter | Increase Effect | Decrease Effect | Optimal Range |
|-----------|----------------|-----------------|---------------|
| ARBITRAGE_THRESHOLD | Fewer, higher quality trades | More, smaller profit trades | 0.01 - 0.05 |
| MIN_TRADE_VOLUME | Higher min profit per trade | More flexibility | 5 - 15 |
| MAX_TRADE_VOLUME | Larger profit on big spreads | More conservative | 30 - 80 |
| SLEEP_TIME | Lower CPU, miss opportunities | Higher CPU, catch more | 0.1 - 0.5 |
| POSITION_BUFFER | More conservative, miss trades | More aggressive, risk breach | 2 - 10 |

---

## Advanced: Multi-Session Comparison

To compare multiple sessions:

```bash
# Run session 1 (conservative)
python data_logging_algo.py  # Run 10 min
# Modify parameters
python data_logging_algo.py  # Run 10 min again

# Compare
python analyze_trading_data.py 20251111_140530
python analyze_trading_data.py 20251111_141530

# Compare final P&L and execution rates
```

Look for:
- Which session had better P&L per minute?
- Which had better execution rate?
- Which maintained delta better?
- Which utilized positions more efficiently?

**Best session = highest P&L with delta < 5 and execution rate > 70%**

---

## Competition Day Checklist

**30 minutes before:**
- [ ] Run data_logging_algo.py for 5 minutes
- [ ] Analyze results
- [ ] Tune parameters
- [ ] Run again for 5 minutes
- [ ] Validate delta stays near 0
- [ ] Validate execution rate > 70%

**At competition start:**
- [ ] Start optimized algorithm
- [ ] Monitor output every 2-3 minutes
- [ ] Watch for delta drift
- [ ] Watch for position limit issues
- [ ] Let it run!

**During competition:**
- [ ] Only intervene if delta > 15
- [ ] Only intervene if execution rate < 40%
- [ ] Otherwise: trust the algorithm

---

## Troubleshooting Common Issues

### Issue: Delta keeps drifting positive
**Diagnosis:** More buys than sells executing
**Fix:** Check position limits, may be hitting sell limit

### Issue: Delta keeps drifting negative
**Diagnosis:** More sells than buys executing
**Fix:** Check position limits, may be hitting buy limit

### Issue: P&L much lower than expected profit
**Diagnosis:** Low fill rate
**Fix:** Orders not executing at intended prices, use limit orders

### Issue: Very few opportunities detected
**Diagnosis:** Threshold too high
**Fix:** Lower ARBITRAGE_THRESHOLD

### Issue: Position utilization always at 100%
**Diagnosis:** Trading too aggressively
**Fix:** Reduce MAX_TRADE_VOLUME or increase POSITION_BUFFER

---

## Summary: Data-Driven Optimization Loop

```
1. RUN → Collect data for 5-10 minutes
2. ANALYZE → Run analysis script
3. IDENTIFY → Find bottleneck (threshold? volume? speed?)
4. ADJUST → Change ONE parameter
5. REPEAT → Run again and compare
6. ITERATE → Until P&L maximized while delta < 5
```

The key is **incremental changes** and **comparing results**.

Good luck in the competition!
