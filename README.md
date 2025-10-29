# LibrdKafka Statistics Parser

A Python tool for parsing, analyzing, and visualizing statistics output from librdkafka clients (Kafka producers and consumers).

## Overview

This tool processes JSON statistics emitted by librdkafka and generates comprehensive time-series graphs showing:
- **Broker metrics**: RTT, connection state, data rates, errors, throttle times
- **Consumer metrics**: lag, committed offsets, leader epochs (consumer clients only)

## Features

- ✅ Parse single or multiple JSON objects from a file
- ✅ Automatic deduplication and merging of duplicate timestamps
- ✅ Beautiful time-series visualizations with Matplotlib
- ✅ Intelligent handling of missing data and sentinel values
- ✅ Debug mode with detailed CSV output for troubleshooting
- ✅ Customizable graph appearance and filtering options

## Installation

### Requirements

- Python 3.7+
- matplotlib
- numpy

### Install Dependencies

```bash
pip install matplotlib numpy
```

## Usage

### Basic Usage

```bash
# Print summary of statistics
python kafka_stats_parser.py stats.json

# Generate graphs
python kafka_stats_parser.py stats.json --graph
```

### Advanced Options

```bash
# Specify output directory
python kafka_stats_parser.py stats.json --graph --output my_graphs

# Enable debug mode (creates CSV files and summaries)
python kafka_stats_parser.py stats.json --graph --debug-data

# Show empty series (series with no valid data)
python kafka_stats_parser.py stats.json --graph --show-empty

# Customize line width
python kafka_stats_parser.py stats.json --graph --line-width 2.0

# Disable legend annotations
python kafka_stats_parser.py stats.json --graph --no-legend-valid --no-annotate
```

### Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `stats_file` | Path to file containing librdkafka JSON statistics (required) |
| `--graph` | Generate time-series graphs |
| `--output DIR` | Output directory for graphs (default: `kafka_graphs`) |
| `--debug-data` | Write debug CSV files and summaries for each plot |
| `--show-empty` | Include series with no valid data points |
| `--no-legend-valid` | Don't show data point counts in legend |
| `--no-annotate` | Disable plot annotations (series/const counts) |
| `--line-width N` | Line width for plots in points (default: 3.0) |

## Input File Format

The tool accepts three input formats:

1. **Single JSON object**:
   ```json
   {"ts": 1234567890, "time": 1234567, "type": "consumer", ...}
   ```

2. **JSON array**:
   ```json
   [
     {"ts": 1234567890, ...},
     {"ts": 1234567891, ...}
   ]
   ```

3. **Multiple concatenated JSON objects** (one per line or back-to-back):
   ```json
   {"ts": 1234567890, ...}
   {"ts": 1234567891, ...}
   ```

## Output Files

### Graph Files

- `broker_metrics.png` - Multi-panel graph with all broker metrics
- `topic_<name>.png` - Per-topic graphs with partition metrics (consumers only)

### Debug Files (with `--debug-data`)

- `debug/debug_data.txt` - Raw dump of all parsed time-series data
- `debug/brokers/*.csv` - Per-plot CSV files for broker metrics
- `debug/brokers/*.summary.txt` - Statistical summaries for broker plots
- `debug/topics/*.csv` - Per-plot CSV files for topic metrics
- `debug/topics/*.summary.txt` - Statistical summaries for topic plots

## Understanding the Graphs

### Broker Metrics

1. **Broker RTT** - Round-trip time to each broker in milliseconds
2. **Broker Data Rate (TX/RX)** - Transmit/receive rates in MB/s
3. **Broker Connections/Disconnections** - Connection event counts
4. **Broker Throttle Time** - Kafka broker throttle time in milliseconds
5. **Broker Receive Errors** - Cumulative receive error count
6. **Broker State** - Connection state (UP, INIT, DOWN)

### Consumer Metrics (Consumer Clients Only)

For each topic, the following per-partition metrics are displayed:

1. **Committed Offset** - Last committed offset for the partition
2. **Stored Offset** - Last stored (not yet committed) offset
3. **Committed Leader Epoch** - Leader epoch at commit time
4. **Consumer Lag** - Number of messages behind the high water mark
5. **Stored Consumer Lag** - Lag based on stored (uncommitted) offset

### Special Values

- **-1**: "Not Assigned" - Partition not assigned to this consumer
- **-1001**: Invalid/unset offset value
- **NaN**: Missing or unavailable data point

These special values are displayed as gaps in the graphs and clearly marked in legends when `--show-empty` is used.

## Code Architecture

### Main Classes

#### `RdKafkaStats`
Container for a single statistics snapshot with timestamp, broker data, and topic data.

#### `BrokerStats`
Statistics for a single broker connection including state, I/O metrics, and timing.

#### `TopicStats` / `PartitionStats`
Topic and partition-level statistics, primarily for consumer lag and offset tracking.

#### `LibrdKafkaStatsParser`
Main parser class that:
- Loads and parses statistics files
- Deduplicates and merges records
- Generates time-series data structures
- Creates visualizations

### Key Methods

- `_load_stats()` - Parse JSON from file with format auto-detection
- `_get_time_series_data()` - Extract plottable time-series from history
- `generate_graphs()` - Create and save all visualization plots
- `write_debug_data()` - Export debug information for troubleshooting

## Troubleshooting

### No Lines Visible in Graphs

If graphs appear empty or have no visible lines:

1. **Check data validity**: Use `--debug-data` to see CSV files
2. **Look for warnings**: The tool prints warnings for series with < 2 valid points
3. **Verify time range**: Ensure statistics span multiple timestamps
4. **Check for constant values**: Series with constant values appear as flat lines

### Understanding Debug Output

When using `--debug-data`, check the `.summary.txt` files:
- `valid`: Number of valid (non-NaN, non-sentinel) data points
- `constant`: Whether all values are identical (flat line)
- `not_assigned`: Count of sentinel values (-1 or -1001)
- `min`/`max`: Range of valid values

## Contributing

When contributing improvements:

1. **Maintain backward compatibility** - Existing scripts depend on current behavior
2. **Add docstrings** - Document all new functions and classes
3. **Test with real data** - Use actual librdkafka statistics files
4. **Update this README** - Document new features and options

## Examples

### Monitoring Consumer Lag

```bash
# Generate graphs focusing on lag metrics
python kafka_stats_parser.py consumer_stats.json --graph --output lag_analysis
```

Check the generated `topic_*.png` files for the "Consumer Lag" subplot.

### Debugging Missing Data

```bash
# Enable full debug output
python kafka_stats_parser.py stats.json --graph --debug-data --show-empty
```

Review the `debug/` directory for CSV files and summaries explaining data issues.

### Customizing for Presentations

```bash
# Thinner lines, cleaner legends
python kafka_stats_parser.py stats.json --graph --line-width 1.5 --no-annotate
```

## License

This tool is provided as-is for parsing librdkafka statistics. Modify and distribute freely.
