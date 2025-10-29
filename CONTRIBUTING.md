# Contributing to LibrdKafka Statistics Parser

Thank you for your interest in improving this tool! This guide will help you understand the codebase and make effective contributions.

## Getting Started

### Understanding the Code Flow

1. **Input** → `_load_stats()` parses JSON file(s)
2. **Deduplication** → Merges records with same timestamp
3. **Time Series Extraction** → `_get_time_series_data()` creates plottable arrays
4. **Visualization** → `generate_graphs()` creates PNG files

### Code Structure

```
kafka_stats_parser.py
├── Data Classes (lines 25-140)
│   ├── RdKafkaStats - Top-level container
│   ├── BrokerStats - Broker metrics
│   ├── TopicStats - Topic container
│   └── PartitionStats - Partition metrics
│
├── LibrdKafkaStatsParser (lines 142-827)
│   ├── _load_stats() - Parse and deduplicate
│   ├── print_summary() - Console output
│   ├── _get_time_series_data() - Extract time series
│   ├── write_debug_data() - Legacy debug output
│   ├── _series_stats() - Calculate statistics
│   ├── _write_plot_debug() - Per-plot debug files
│   └── generate_graphs() - Create visualizations
│
└── main() - CLI entry point (lines 829-877)
```

## Common Improvement Areas

### 1. Adding New Metrics

To add a new metric to the graphs:

**Step 1**: Add to time-series extraction in `_get_time_series_data()`:

```python
# In the broker data initialization (around line 268)
'brokers': {
    b: {
        'rtt': [], 
        'state': [],
        'your_new_metric': [],  # Add here
        # ... existing metrics
    } for b in all_broker_keys
}

# In the stats collection loop (around line 285)
for stats in plottable_stats:
    # ... existing code
    b_data['your_new_metric'].append(
        broker.your_field if broker else np.nan
    )
```

**Step 2**: Add to plot definitions in `generate_graphs()`:

```python
# In broker_plots list (around line 741)
broker_plots = [
    ('Your Metric Title', 'Units', {k: v['your_new_metric'] for k, v in data['brokers'].items()}),
    # ... existing plots
]
```

### 2. Improving Plot Appearance

Plot styling is handled in the `plot_data()` function (lines 628-730). Key areas:

- **Line styles**: Modify `drawstyle` parameter
- **Colors**: Add `color` parameter to `ax.plot()`
- **Markers**: Adjust `marker` and `markersize` logic
- **Y-axis scaling**: Modify the `center_y` logic (lines 688-714)

### 3. Adding New File Formats

If you need to support a different input format:

1. Modify `_load_stats()` method (lines 166-231)
2. Add your parsing logic after the existing try/except blocks
3. Ensure output is a list of `RdKafkaStats` objects
4. Update `EXAMPLES.md` with the new format

### 4. Performance Improvements

Current bottlenecks and optimization opportunities:

- **Large files**: Consider streaming parser for huge stats files
- **Many partitions**: Optimize the nested loops in `_get_time_series_data()`
- **Graph generation**: Could parallelize per-topic plot creation

## Code Style Guidelines

### Documentation

All public methods and classes must have docstrings:

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.
    
    More detailed explanation if needed, including any special
    behaviors, edge cases, or important notes.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When and why this might be raised
    """
```

### Type Hints

Use type hints for all function signatures:

```python
from typing import List, Dict, Any, Optional

def process_data(stats: List[RdKafkaStats]) -> Dict[str, Any]:
    ...
```

### Comments

- Use inline comments for complex logic
- Explain **why**, not **what** (code shows what)
- Mark special values: `-1` (Not Assigned), `-1001` (Invalid)

### Naming Conventions

- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Private methods: `_leading_underscore`
- Constants: `UPPER_CASE`

## Testing Your Changes

### Manual Testing

1. **Basic functionality**:
   ```bash
   python kafka_stats_parser.py test_data.json
   python kafka_stats_parser.py test_data.json --graph
   ```

2. **Edge cases**:
   - Single timestamp (should not generate graphs)
   - Missing brokers/topics
   - All NaN values
   - Constant values

3. **Different formats**:
   - Single JSON object
   - JSON array
   - Concatenated objects

### Validation Checklist

Before submitting changes:

- [ ] Code runs without errors
- [ ] Docstrings added for new functions/classes
- [ ] Type hints included
- [ ] Backward compatibility maintained
- [ ] README.md updated if adding features
- [ ] Examples added to EXAMPLES.md if relevant
- [ ] Tested with real librdkafka statistics

## Common Patterns

### Handling Sentinel Values

Special values in librdkafka statistics:

```python
# -1 means "Not Assigned" (partition not assigned to consumer)
# -1001 means "Invalid" (offset not set)

# Always filter these out for calculations:
valid_points = [
    v for v in values 
    if v is not None and not np.isnan(v) and v != -1 and v != -1001
]

# Replace with NaN for plotting (won't draw lines through them):
plot_values = [np.nan if (v == -1 or v == -1001) else v for v in values]
```

### Accessing Nested Statistics

```python
# Safely access nested fields with .get():
rtt_avg = broker_data.get('rtt', {}).get('avg')

# Check for None before using:
if rtt_avg is not None:
    rtt_ms = rtt_avg / 1000
```

### Time Series Data Structure

The data structure from `_get_time_series_data()`:

```python
{
    'timestamps': [datetime, datetime, ...],  # X-axis values
    'client_type': 'consumer',                 # or 'producer'
    'brokers': {
        'broker_name': {
            'rtt': [float, float, ...],        # One per timestamp
            'state': [int, int, ...],          # Mapped: UP=1, INIT=0, DOWN=-1
            # ... more metrics
        }
    },
    'topics': {
        'topic_name': {
            'topic-partition_id': {
                'lag': [int, int, ...],
                'committed': [int, int, ...],
                # ... more metrics
            }
        }
    }
}
```

## Debugging Tips

### Enable Debug Mode

```bash
python kafka_stats_parser.py stats.json --graph --debug-data
```

This creates CSV files showing exact values plotted.

### Console Warnings

The tool prints warnings for common visibility issues:
- Series with < 2 valid points (won't draw line)
- Constant values (flat line)

### Check Summary Files

Look at `debug/*/`*.summary.txt` files:
```
Plot: Broker RTT
Points per series: 100

- Broker #1: total=100, valid=95, first_idx=5, last_idx=99, min=2.3, max=8.7, constant=False
- Broker #2: total=100, valid=0 (all NaN - won't be visible)
```

## Questions?

If you need help:

1. Check existing code comments and docstrings
2. Review the librdkafka [STATISTICS.md](https://github.com/confluentinc/librdkafka/blob/master/STATISTICS.md)
3. Look at the debug output with `--debug-data`
4. Open an issue describing what you're trying to do

## Example Contribution Workflow

```bash
# 1. Make your changes
vim kafka_stats_parser.py

# 2. Test basic functionality
python kafka_stats_parser.py test_stats.json --graph

# 3. Test with debug output
python kafka_stats_parser.py test_stats.json --graph --debug-data

# 4. Check for errors
python -m py_compile kafka_stats_parser.py

# 5. Update documentation
vim README.md  # If adding features
vim EXAMPLES.md  # If changing input format

# 6. Commit with clear message
git add kafka_stats_parser.py README.md
git commit -m "Add support for XYZ metric visualization"
```

Thank you for contributing! 🎉
