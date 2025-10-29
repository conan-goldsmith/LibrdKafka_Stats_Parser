# Quick Reference Guide

Quick command reference for common tasks with the LibrdKafka Statistics Parser.

## Installation

```bash
pip install matplotlib numpy
```

## Common Commands

### View Statistics Summary
```bash
python kafka_stats_parser.py stats.json
```

### Generate Default Graphs
```bash
python kafka_stats_parser.py stats.json --graph
```

### Generate Graphs with Custom Output
```bash
python kafka_stats_parser.py stats.json --graph --output my_graphs
```

### Enable Debug Mode
```bash
python kafka_stats_parser.py stats.json --graph --debug-data
```

### Show All Series (Including Empty)
```bash
python kafka_stats_parser.py stats.json --graph --show-empty
```

### Customize Line Width
```bash
python kafka_stats_parser.py stats.json --graph --line-width 2.0
```

### Clean Legend (No Counts)
```bash
python kafka_stats_parser.py stats.json --graph --no-legend-valid --no-annotate
```

## File Locations

### Input
- Your librdkafka statistics file (JSON format)

### Output (Default: `kafka_graphs/`)
- `broker_metrics.png` - All broker metrics in one file
- `topic_<name>.png` - Per-topic consumer metrics

### Debug Output (with `--debug-data`)
- `kafka_graphs/debug/debug_data.txt` - Raw data dump
- `kafka_graphs/debug/brokers/*.csv` - Broker metric CSVs
- `kafka_graphs/debug/brokers/*.summary.txt` - Broker statistics
- `kafka_graphs/debug/topics/*.csv` - Topic metric CSVs
- `kafka_graphs/debug/topics/*.summary.txt` - Topic statistics

## Graph Types Generated

### Broker Graphs (All Clients)
1. Broker RTT (ms)
2. Broker Data Rate TX (MB/s)
3. Broker Data Rate RX (MB/s)
4. Broker Connections (count)
5. Broker Disconnections (count)
6. Broker Throttle Time (ms)
7. Broker Receive Errors (cumulative)
8. Broker State (UP/INIT/DOWN)

### Consumer Graphs (Consumer Clients Only)
Per topic:
1. Committed Offset
2. Stored Offset
3. Committed Leader Epoch
4. Consumer Lag (messages)
5. Stored Consumer Lag (messages)

## Special Values in Graphs

| Value | Meaning | Display |
|-------|---------|---------|
| -1 | Not Assigned | Gap in line |
| -1001 | Invalid/Unset | Gap in line |
| NaN | Missing Data | Gap in line |

## Troubleshooting Quick Fixes

### No Lines Visible
```bash
# Enable debug to see what data exists
python kafka_stats_parser.py stats.json --graph --debug-data --show-empty
```

### Too Many Series
```bash
# Default behavior hides empty series (good)
python kafka_stats_parser.py stats.json --graph
```

### Need More Detail
```bash
# Clean legends show less info
python kafka_stats_parser.py stats.json --graph --no-legend-valid
```

### Debugging Specific Plot
1. Generate with `--debug-data`
2. Check `kafka_graphs/debug/brokers/<plot_name>.csv`
3. Check `kafka_graphs/debug/brokers/<plot_name>.summary.txt`

## Collecting Statistics

### Python (confluent-kafka)
```python
conf = {
    'bootstrap.servers': 'localhost:9092',
    'statistics.interval.ms': 5000,
    'stats_cb': lambda stats: write_to_file(stats)
}
```

### Java
```java
props.put("statistics.interval.ms", "5000");
```

See `EXAMPLES.md` for complete code samples.

## Command-Line Options Summary

| Option | Default | Description |
|--------|---------|-------------|
| `stats_file` | (required) | Path to JSON statistics file |
| `--graph` | off | Generate graphs |
| `--output DIR` | `kafka_graphs` | Output directory |
| `--debug-data` | off | Write debug CSVs |
| `--show-empty` | off | Show empty series |
| `--no-legend-valid` | off | Hide data counts in legend |
| `--no-annotate` | off | Hide plot annotations |
| `--line-width N` | 3.0 | Line width in points |

## Help Command

```bash
python kafka_stats_parser.py --help
```

## Getting More Help

- **Full documentation**: See `README.md`
- **Input format**: See `EXAMPLES.md`
- **Contributing**: See `CONTRIBUTING.md`
- **Code reference**: See docstrings in `kafka_stats_parser.py`

## One-Liner Examples

```bash
# Quick analysis
python kafka_stats_parser.py stats.json --graph

# Presentation mode (clean, thin lines)
python kafka_stats_parser.py stats.json --graph --line-width 1.5 --no-annotate

# Debug mode (everything)
python kafka_stats_parser.py stats.json --graph --debug-data --show-empty

# Custom output
python kafka_stats_parser.py stats.json --graph --output ./analysis_$(date +%Y%m%d)
```

## Minimum Data Requirements

- **For summary**: 1 statistics snapshot
- **For graphs**: 2+ snapshots with different timestamps
- **For useful trends**: 10+ snapshots over time

## Performance Notes

- Processing time scales with:
  - Number of brokers
  - Number of topics × partitions
  - Number of time points
- Large files (100+ MB): May take several minutes
- Graph generation: ~1-2 seconds per topic

## Common Workflows

### Initial Analysis
```bash
# 1. Check what you have
python kafka_stats_parser.py stats.json

# 2. Generate graphs
python kafka_stats_parser.py stats.json --graph

# 3. Open broker_metrics.png and topic_*.png files
```

### Investigating Issues
```bash
# 1. Enable debug mode
python kafka_stats_parser.py stats.json --graph --debug-data

# 2. Check console warnings
# 3. Review debug/*.summary.txt files
# 4. Examine debug/*.csv files for raw data
```

### Creating Reports
```bash
# 1. Generate clean graphs
python kafka_stats_parser.py stats.json --graph --line-width 2.0 --no-annotate --output report_$(date +%Y%m%d)

# 2. Graphs are now in report_YYYYMMDD/ directory
# 3. Include broker_metrics.png and relevant topic_*.png files in your report
```

---

**Pro Tip**: Keep your statistics files! They're valuable historical data for performance analysis and troubleshooting.
