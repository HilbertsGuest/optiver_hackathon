"""
Trading Data Analysis Tool

Analyzes logged trading data to provide insights for parameter optimization.
Usage: python analyze_trading_data.py <session_timestamp>
Example: python analyze_trading_data.py 20251111_140530
"""

import json
import csv
import sys
from pathlib import Path
from collections import defaultdict
import statistics


def load_summary(session_timestamp):
    """Load session summary JSON"""
    summary_file = Path(f"trading_data/summary_{session_timestamp}.json")
    if not summary_file.exists():
        print(f"Error: Summary file not found: {summary_file}")
        return None

    with open(summary_file, 'r') as f:
        return json.load(f)


def load_iterations(session_timestamp):
    """Load iteration log CSV"""
    iteration_file = Path(f"trading_data/iterations_{session_timestamp}.csv")
    if not iteration_file.exists():
        print(f"Error: Iteration file not found: {iteration_file}")
        return []

    iterations = []
    with open(iteration_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            iterations.append(row)

    return iterations


def load_trades(session_timestamp):
    """Load trade log CSV"""
    trade_file = Path(f"trading_data/trades_{session_timestamp}.csv")
    if not trade_file.exists():
        return []

    trades = []
    with open(trade_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)

    return trades


def analyze_threshold_sensitivity(iterations, current_threshold):
    """Analyze what would happen with different thresholds"""
    print("\n" + "=" * 70)
    print("THRESHOLD SENSITIVITY ANALYSIS")
    print("=" * 70)

    thresholds = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20]

    print(f"Current threshold: {current_threshold}")
    print(f"\nWhat if we used different thresholds?")
    print(f"{'Threshold':<12} {'Opportunities':<15} {'Change':<10} {'Avg Spread':<12}")
    print("-" * 70)

    for threshold in thresholds:
        opportunities = 0
        spreads_above_threshold = []

        for row in iterations:
            try:
                spread = float(row['spread'])
                if spread >= threshold:
                    opportunities += 1
                    spreads_above_threshold.append(spread)
            except (ValueError, KeyError):
                continue

        avg_spread = statistics.mean(spreads_above_threshold) if spreads_above_threshold else 0
        change = "CURRENT" if abs(threshold - current_threshold) < 0.001 else f"{opportunities / len(iterations) * 100:.1f}%"

        marker = " <--" if abs(threshold - current_threshold) < 0.001 else ""
        print(f"{threshold:<12.2f} {opportunities:<15} {change:<10} {avg_spread:<12.3f}{marker}")

    print("\nRecommendation:")
    # Find optimal threshold (balance between opportunities and quality)
    opportunity_counts = []
    for threshold in [0.01, 0.02, 0.03, 0.05]:
        count = sum(1 for row in iterations if float(row.get('spread', 0)) >= threshold)
        opportunity_counts.append((threshold, count))

    best_threshold = max(opportunity_counts, key=lambda x: x[1])
    print(f"  - Consider threshold {best_threshold[0]:.2f} for {best_threshold[1]} opportunities")


def analyze_volume_optimization(iterations, trades, current_min, current_max):
    """Analyze if volume settings are optimal"""
    print("\n" + "=" * 70)
    print("VOLUME OPTIMIZATION ANALYSIS")
    print("=" * 70)

    print(f"Current settings: MIN={current_min}, MAX={current_max}")

    if not trades:
        print("No trades executed - cannot analyze volume")
        return

    # Analyze executed trade volumes
    volumes = [int(row['volume']) for row in trades if row['volume']]
    if volumes:
        print(f"\nTrade volume distribution:")
        print(f"  Min traded: {min(volumes)} lots")
        print(f"  Max traded: {max(volumes)} lots")
        print(f"  Avg traded: {statistics.mean(volumes):.1f} lots")
        print(f"  Median traded: {statistics.median(volumes)} lots")

        # Check if we're hitting limits
        hitting_max = sum(1 for v in volumes if v >= current_max)
        hitting_min = sum(1 for v in volumes if v <= current_min)

        print(f"\n  Trades at MAX volume ({current_max}): {hitting_max} ({hitting_max/len(volumes)*100:.1f}%)")
        print(f"  Trades at MIN volume ({current_min}): {hitting_min} ({hitting_min/len(volumes)*100:.1f}%)")

        print("\nRecommendation:")
        if hitting_max / len(volumes) > 0.3:
            print(f"  - Consider INCREASING MAX_TRADE_VOLUME to {current_max + 20}")
            print(f"    (30%+ trades hitting max limit)")
        if hitting_min / len(volumes) > 0.5:
            print(f"  - Consider DECREASING MIN_TRADE_VOLUME to {max(5, current_min - 5)}")
            print(f"    (50%+ trades at minimum volume)")
        if 0.1 < hitting_max / len(volumes) < 0.3:
            print(f"  - Volume settings appear well-calibrated")


def analyze_timing(iterations, trades, current_sleep):
    """Analyze if iteration speed is optimal"""
    print("\n" + "=" * 70)
    print("TIMING & LATENCY ANALYSIS")
    print("=" * 70)

    print(f"Current sleep time: {current_sleep}s")

    total_iterations = len(iterations)
    opportunities = sum(1 for row in iterations if row['opportunity_detected'] == 'True')
    executed = sum(1 for row in iterations if row['trade_executed'] == 'True')

    print(f"\nIteration efficiency:")
    print(f"  Total iterations: {total_iterations}")
    print(f"  Opportunities found: {opportunities} ({opportunities/total_iterations*100:.1f}%)")
    print(f"  Trades executed: {executed} ({executed/total_iterations*100:.1f}%)")

    # Analyze trade clustering
    if trades:
        print(f"\nTrade timing:")
        print(f"  Total trades: {len(trades)}")

        # Check if we could go faster
        idle_iterations = total_iterations - executed
        print(f"  Idle iterations: {idle_iterations} ({idle_iterations/total_iterations*100:.1f}%)")

        print("\nRecommendation:")
        if idle_iterations / total_iterations > 0.95:
            print(f"  - INCREASE sleep time to {current_sleep * 2:.2f}s (95%+ iterations idle)")
        elif idle_iterations / total_iterations < 0.70:
            print(f"  - DECREASE sleep time to {current_sleep / 2:.2f}s (market very active)")
        else:
            print(f"  - Sleep time appears reasonable")


def analyze_delta_performance(iterations):
    """Analyze delta neutrality performance"""
    print("\n" + "=" * 70)
    print("DELTA NEUTRALITY ANALYSIS")
    print("=" * 70)

    deltas = []
    for row in iterations:
        try:
            delta = float(row.get('delta', 0))
            deltas.append(abs(delta))
        except (ValueError, TypeError):
            continue

    if not deltas:
        print("No delta data available")
        return

    print(f"Delta statistics (absolute values):")
    print(f"  Max delta: {max(deltas):.0f} lots")
    print(f"  Avg delta: {statistics.mean(deltas):.2f} lots")
    print(f"  Median delta: {statistics.median(deltas):.0f} lots")

    # Check how often delta is very close to 0
    perfect_delta = sum(1 for d in deltas if d <= 1)
    good_delta = sum(1 for d in deltas if d <= 5)
    concerning_delta = sum(1 for d in deltas if d > 20)

    print(f"\nDelta distribution:")
    print(f"  Perfect (≤1): {perfect_delta} ({perfect_delta/len(deltas)*100:.1f}%)")
    print(f"  Good (≤5): {good_delta} ({good_delta/len(deltas)*100:.1f}%)")
    print(f"  Concerning (>20): {concerning_delta} ({concerning_delta/len(deltas)*100:.1f}%)")

    print("\nAssessment:")
    if concerning_delta / len(deltas) > 0.1:
        print("  ⚠ WARNING: Delta drifting too much - check trade execution logic")
    elif good_delta / len(deltas) > 0.9:
        print("  ✓ EXCELLENT: Delta neutrality well maintained")
    else:
        print("  ✓ GOOD: Delta generally well controlled")


def analyze_profitability(trades, summary):
    """Analyze actual vs expected profitability"""
    print("\n" + "=" * 70)
    print("PROFITABILITY ANALYSIS")
    print("=" * 70)

    if not trades:
        print("No trades to analyze")
        return

    total_expected = sum(float(row['expected_profit']) for row in trades)
    actual_pnl_changes = [float(row['pnl_change']) for row in trades if row['pnl_change']]

    print(f"Expected vs Actual:")
    print(f"  Total expected profit: ${total_expected:.2f}")
    print(f"  Final P&L: ${summary.get('final_pnl', 0):.2f}")

    if actual_pnl_changes:
        total_realized = sum(actual_pnl_changes)
        print(f"  Sum of P&L changes: ${total_realized:.2f}")

        # Calculate fill rate estimate
        if total_expected > 0:
            fill_rate = (total_realized / total_expected) * 100
            print(f"  Estimated fill rate: {fill_rate:.1f}%")

            print("\nAssessment:")
            if fill_rate < 50:
                print("  ⚠ LOW FILL RATE: Consider using limit orders instead of IOC")
            elif fill_rate < 80:
                print("  ⚠ MODERATE FILL RATE: Execution could be improved")
            else:
                print("  ✓ GOOD FILL RATE: Execution is effective")


def analyze_missed_opportunities(iterations, current_threshold):
    """Analyze opportunities missed due to capacity constraints"""
    print("\n" + "=" * 70)
    print("MISSED OPPORTUNITY ANALYSIS")
    print("=" * 70)

    reasons = defaultdict(int)
    for row in iterations:
        if row['opportunity_detected'] == 'True' and row['trade_executed'] == 'False':
            reason = row.get('reason', 'unknown')
            reasons[reason] += 1

    if not reasons:
        print("No missed opportunities - excellent!")
        return

    print(f"Missed opportunities breakdown:")
    total_missed = sum(reasons.values())

    for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count} ({count/total_missed*100:.1f}%)")

    print("\nRecommendations:")
    if reasons['insufficient_capacity'] > total_missed * 0.3:
        print("  - Position limits being hit frequently")
        print("  - Consider: Smaller trade volumes OR faster position unwinding")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_trading_data.py <session_timestamp>")
        print("\nAvailable sessions:")

        data_dir = Path("trading_data")
        if data_dir.exists():
            summaries = list(data_dir.glob("summary_*.json"))
            for summary_file in sorted(summaries, reverse=True):
                timestamp = summary_file.stem.replace("summary_", "")
                print(f"  - {timestamp}")
        return

    session_timestamp = sys.argv[1]

    print("=" * 70)
    print(f"ANALYZING TRADING SESSION: {session_timestamp}")
    print("=" * 70)

    # Load data
    summary = load_summary(session_timestamp)
    if not summary:
        return

    iterations = load_iterations(session_timestamp)
    trades = load_trades(session_timestamp)

    # Print basic summary
    print(f"\nSession Overview:")
    print(f"  Duration: {summary['session_duration_seconds']:.0f}s")
    print(f"  Iterations: {summary['total_iterations']}")
    print(f"  Opportunities: {summary['opportunities_detected']}")
    print(f"  Trades: {summary['trades_executed']}")
    print(f"  Final P&L: ${summary['final_pnl']:.2f}")

    config = summary.get('config', {})

    # Run analyses
    analyze_threshold_sensitivity(iterations, config.get('arbitrage_threshold', 0.02))
    analyze_volume_optimization(iterations, trades,
                                config.get('min_trade_volume', 10),
                                config.get('max_trade_volume', 50))
    analyze_timing(iterations, trades, config.get('sleep_time', 0.2))
    analyze_delta_performance(iterations)
    analyze_profitability(trades, summary)
    analyze_missed_opportunities(iterations, config.get('arbitrage_threshold', 0.02))

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
