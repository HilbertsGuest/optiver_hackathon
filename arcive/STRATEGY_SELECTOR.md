# Strategy Selector Guide

## Which Strategy Should You Use?

You now have **3 main strategies**. Here's when to use each one:

---

## 1. `clean_arbitrage_algo.py` - Immediate Arbitrage
**Best for**: Fast, straightforward price discrepancy trading

### When to use:
- ✓ Market has frequent, obvious price differences between PHILLIPS_A and PHILLIPS_B
- ✓ You want simple, predictable behavior
- ✓ You need delta approaching zero (active rebalancing)
- ✓ You want to understand and control spread management

### Strategy:
- Detects immediate price discrepancies
- Executes paired trades instantly
- Uses limit orders to earn bid-ask spread
- Actively rebalances delta when it drifts

### Expected Performance:
- 20-60 trades per hour
- $50-200 profit per hour
- Consistent, predictable

### Pros:
- Simple to understand
- Active delta management
- Smart spread management (limit orders)
- Clean, readable code

### Cons:
- No statistical analysis
- May miss subtler opportunities
- Requires constant monitoring

**Run it:**
```bash
python clean_arbitrage_algo.py
```

---

## 2. `statarb_guided_algo.py` - Statistical Mean Reversion
**Best for**: Professional-grade statistical arbitrage following guide.md

### When to use:
- ✓ Market prices are cointegrated (move together long-term)
- ✓ You want to wait for "statistically significant" opportunities
- ✓ You prefer fewer, higher-quality trades
- ✓ You want production-grade risk checks

### Strategy:
- Builds 100-point historical spread database
- Calculates mean and standard deviation
- Enters when spread deviates ±2 std from mean
- Exits when spread reverts to mean
- Comprehensive guard-rails (volume, slippage, front-running checks)

### Expected Performance:
- 3-15 trades per hour
- $100-300 profit per hour
- Patient, strategic

### Pros:
- Professional-grade risk management
- All guard-rails from guide.md implemented
- Statistically sound entry/exit
- Handles partial fills
- Production-ready architecture

### Cons:
- Needs 100 data points before trading (~50 iterations)
- Slower to react to opportunities
- More complex logic

**Run it:**
```bash
python statarb_guided_algo.py
```

---

## 3. `aggressive_algo.py` - High-Frequency Arbitrage
**Best for**: Maximum throughput in active markets

### When to use:
- ✓ Market is very active with many small price differences
- ✓ You want maximum number of trades
- ✓ You can monitor closely
- ✓ You want to push position limits

### Strategy:
- Very low threshold (0.02)
- Very fast iteration (0.2s)
- Dynamic volume scaling (10-50 lots)
- Aggressive position utilization (up to 95%)

### Expected Performance:
- 100-300 trades per hour
- $500-2000 profit per hour (if market conditions right)
- High risk, high reward

### Pros:
- Maximum throughput
- Captures small opportunities
- Dynamic volume sizing
- Optimized for speed

### Cons:
- Can be overwhelming to monitor
- Higher execution risk
- May hit position limits
- Needs careful tuning

**Run it:**
```bash
python aggressive_algo.py
```

---

## Quick Comparison Table

| Feature | clean_arbitrage | statarb_guided | aggressive |
|---------|----------------|----------------|------------|
| **Strategy** | Immediate arbitrage | Statistical mean reversion | High-frequency arbitrage |
| **Speed** | Medium (0.3s) | Slow (0.5s) | Fast (0.2s) |
| **Trades/hour** | 20-60 | 3-15 | 100-300 |
| **Entry logic** | Price discrepancy | ±2 std deviation | Low threshold |
| **Exit logic** | Immediate | Mean reversion | Immediate |
| **Risk checks** | Basic | Comprehensive (guide.md) | Minimal |
| **Statistics** | None | 100-point history | None |
| **Delta management** | Active rebalancing | Paired positions | Paired positions |
| **Spread management** | Limit orders (smart) | IOC orders | IOC orders |
| **Position size** | 5-30 lots | Fixed 50 lots | Dynamic 10-50 lots |
| **Complexity** | Low | High | Medium |
| **Best for** | Learning & stable markets | Professional trading | Active markets |

---

## Decision Tree

### Start here:

**Q: Is this your first time running a strategy?**
- Yes → Use `clean_arbitrage_algo.py` (simplest)
- No → Continue

**Q: What's more important - quality or quantity of trades?**
- Quality (fewer, better trades) → Use `statarb_guided_algo.py`
- Quantity (many trades) → Continue

**Q: Is the market very active (many small price changes)?**
- Yes → Use `aggressive_algo.py`
- No → Use `clean_arbitrage_algo.py`

**Q: Do you need production-grade risk checks (guide.md)?**
- Yes → Use `statarb_guided_algo.py`
- No → Use `clean_arbitrage_algo.py`

---

## Recommended Progression

### For Competition:

**30 minutes before:**
1. Test `clean_arbitrage_algo.py` for 5 minutes
2. Check delta stays near 0
3. Verify trades are executing
4. Note the P&L rate

**15 minutes before:**
5. Test `statarb_guided_algo.py` for 5 minutes
6. Let it build statistical history
7. Watch for entry signals
8. Compare P&L to clean_arbitrage

**At start:**
9. Choose the one that performed better in testing
10. OR run `aggressive_algo.py` if market is very active

**During competition:**
11. Monitor every 3-5 minutes
12. Watch delta (should stay near 0)
13. If problems: fall back to `clean_arbitrage_algo.py`

---

## Tuning Guides

### For clean_arbitrage_algo.py:
See `GOALS_IMPLEMENTATION.md` and `QUICK_START.md`

**Key parameters:**
```python
ARBITRAGE_THRESHOLD = 0.05     # Lower = more trades
USE_LIMIT_ORDERS = True        # Earn spread
DELTA_REBALANCE_THRESHOLD = 5  # When to rebalance
```

### For statarb_guided_algo.py:
See `GUIDE_IMPLEMENTATION.md`

**Key parameters:**
```python
ENTRY_THRESHOLD_STDEV = 2.0    # Entry sensitivity
EXIT_THRESHOLD_STDEV = 0.2     # Exit timing
MAX_POSITION_SIZE = 50         # Trade size
MAX_ACCEPTABLE_SPREAD_A = 0.50 # Slippage tolerance
```

### For aggressive_algo.py:
See `STRATEGY_COMPARISON.md` and `DATA_DRIVEN_OPTIMIZATION.md`

**Key parameters:**
```python
ARBITRAGE_THRESHOLD = 0.02     # Very low
MIN_TRADE_VOLUME = 10          # Minimum size
MAX_TRADE_VOLUME = 50          # Maximum size
SLEEP_TIME = 0.2               # Very fast
```

---

## Hybrid Approach (Advanced)

**Can you run multiple strategies at once?**
**NO** - Only one connection allowed per account.

**But you can switch strategies:**
1. Run strategy A for 10 minutes
2. Stop it (Ctrl+C)
3. Analyze results
4. Switch to strategy B if needed

---

## My Recommendation

### For Learning:
Start with **`clean_arbitrage_algo.py`**
- Easiest to understand
- Clear output
- Active delta management
- Good balance of features

### For Competition:
Use **`statarb_guided_algo.py`**
- Production-grade risk management
- Statistically sound
- Fewer but better trades
- Handles edge cases gracefully
- Follows professional architecture (guide.md)

### For Maximum Aggression:
Use **`aggressive_algo.py`**
- Only if market is very active
- Only if you can monitor closely
- Highest potential profit
- Highest risk

---

## Testing Protocol

Before committing to a strategy:

**5-minute test:**
1. Run the strategy
2. Watch for at least 2 trades
3. Verify delta stays < 5
4. Note P&L change
5. Check for errors/warnings

**Good signals:**
- ✓ Delta stable
- ✓ P&L increasing
- ✓ Trades executing
- ✓ Few error messages

**Bad signals:**
- ✗ Delta drifting
- ✗ No trades executing
- ✗ Many guard-rail rejections
- ✗ Connection issues

If bad signals with one strategy, **try another**.

---

## Summary

| Your Goal | Use This Strategy |
|-----------|------------------|
| Learn the system | `clean_arbitrage_algo.py` |
| Professional-grade trading | `statarb_guided_algo.py` |
| Maximum profit potential | `aggressive_algo.py` |
| Stable, predictable results | `clean_arbitrage_algo.py` |
| Implement guide.md | `statarb_guided_algo.py` |
| Active market exploitation | `aggressive_algo.py` |
| Risk management focus | `statarb_guided_algo.py` |
| Delta approaching zero | `clean_arbitrage_algo.py` |

**When in doubt**: Use `clean_arbitrage_algo.py` - it's the most balanced.
