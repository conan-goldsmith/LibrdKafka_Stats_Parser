"""
LibrdKafka Statistics Parser and Visualizer

This module parses and visualizes statistics JSON output from librdkafka clients
(producers and consumers). It generates comprehensive time-series graphs showing
broker metrics, consumer lag, offsets, and other operational statistics.

Main Features:
- Parse single or multiple librdkafka stats JSON objects from a file
- Automatically deduplicate and merge records with the same timestamp
- Generate detailed time-series graphs for broker and topic/partition metrics
- Support for both producer and consumer statistics
- Debug mode for detailed data analysis and troubleshooting

Usage:
    python kafka_stats_parser.py <stats_file> --graph [--output <dir>] [--debug-data]

Example:
    python kafka_stats_parser.py kafka_stats.json --graph --output my_graphs
"""

import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import ticker as mticker
import os
import re
import numpy as np


class RdKafkaStats:
    """
    Container for a single librdkafka statistics snapshot.
    
    Represents statistics collected at a specific timestamp, including
    information about all brokers and topics/partitions known to the client.
    
    Attributes:
        data (dict): Raw statistics dictionary from librdkafka
        ts (int): Timestamp in microseconds since epoch
        time (int): Timestamp in seconds since epoch
        type (str): Client type ('producer' or 'consumer')
        brokers (dict): Map of broker names to BrokerStats objects
        topics (dict): Map of topic names to TopicStats objects
    """
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.ts = data.get('ts')
        self.time = data.get('time')
        self.type = data.get('type')
        self.brokers = {name: BrokerStats(bdata) for name, bdata in data.get('brokers', {}).items()}
        self.topics = {name: TopicStats(tdata) for name, tdata in data.get('topics', {}).items()}


class BrokerStats:
    """
    Statistics for a single Kafka broker connection.
    
    Tracks connection state, network I/O, errors, and timing metrics for
    communication with a specific broker.
    
    Attributes:
        data (dict): Raw broker statistics dictionary
        name (str): Broker identifier (usually host:port/id)
        source (str): Either 'logical' or actual broker
        state (str): Connection state ('UP', 'DOWN', 'INIT')
        connects (int): Total number of connection attempts
        disconnects (int): Total number of disconnections
        rxbytes (int): Cumulative bytes received from broker
        txbytes (int): Cumulative bytes transmitted to broker
        rxerrs (int): Cumulative receive errors
        txerrs (int): Cumulative transmit errors
        req_timeouts (int): Number of request timeouts
        rtt_avg (int): Average round-trip time in microseconds
        throttle_avg (int): Average throttle time in microseconds
    """
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.name = data.get('name')
        self.source = data.get('source')
        self.state = data.get('state')
        self.connects = data.get('connects', 0)
        self.disconnects = data.get('disconnects', 0)
        self.rxbytes = data.get('rxbytes', 0)
        self.txbytes = data.get('txbytes', 0)
        self.rxerrs = data.get('rxerrs', 0)
        self.txerrs = data.get('txerrs', 0)
        self.req_timeouts = data.get('req_timeouts', 0)
        self.rtt_avg = data.get('rtt', {}).get('avg')
        self.throttle_avg = data.get('throttle', {}).get('avg')


class TopicStats:
    """
    Statistics for a single Kafka topic.
    
    Contains partition-level statistics for all partitions of the topic
    known to this client.
    
    Attributes:
        data (dict): Raw topic statistics dictionary
        topic (str): Topic name
        partitions (dict): Map of partition IDs to PartitionStats objects
    """
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.topic = data.get('topic')
        self.partitions = {pid: PartitionStats(pdata) for pid, pdata in data.get('partitions', {}).items()}


class PartitionStats:
    """
    Statistics for a single topic partition.
    
    Primarily used for consumer clients to track lag and committed offsets.
    
    Special Values:
        -1: Not assigned/available (e.g., partition not assigned to this consumer)
        -1001: Invalid/unset offset value
    
    Attributes:
        data (dict): Raw partition statistics dictionary
        partition (int): Partition number (-1 if not assigned)
        leader (int): Broker ID of the partition leader
        consumer_lag (int): Number of messages behind the high water mark
        consumer_lag_stored (int): Lag based on stored offset
        committed_offset (int): Last committed offset for this partition
        stored_offset (int): Last stored offset (may differ from committed)
        committed_leader_epoch (int): Epoch of the partition leader at commit time
    """
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.partition = data.get('partition')
        self.leader = data.get('leader')
        self.consumer_lag = data.get('consumer_lag', -1)
        self.consumer_lag_stored = data.get('consumer_lag_stored', -1)
        self.committed_offset = data.get('committed_offset', -1001)
        self.stored_offset = data.get('stored_offset', -1001)
        self.committed_leader_epoch = data.get('committed_leader_epoch', -1)


class LibrdKafkaStatsParser:
    """
    Main parser class for librdkafka statistics files.
    
    This class handles loading, parsing, deduplicating, and visualizing
    librdkafka statistics. It supports multiple JSON objects in a single file
    and automatically merges duplicate timestamps.
    
    Attributes:
        stats_file (str): Path to the statistics file
        stats_history (list): List of RdKafkaStats objects, sorted by timestamp
    """
    def __init__(self, stats_file: str):
        """
        Initialize the parser with a statistics file.
        
        Args:
            stats_file: Path to file containing librdkafka JSON statistics
        """
        self.stats_file = stats_file
        self.stats_history: List[RdKafkaStats] = self._load_stats()

    def _load_stats(self) -> List[RdKafkaStats]:
        """
        Load and parse statistics from the input file.
        
        Supports three file formats:
        1. Single JSON object
        2. JSON array of objects
        3. Multiple concatenated JSON objects (one per line or back-to-back)
        
        After loading, deduplicates records with the same timestamp by merging
        their broker and topic data. This handles cases where stats are split
        across multiple JSON objects at the same collection time.
        
        Returns:
            List of RdKafkaStats objects, sorted by timestamp and deduplicated
        """
        history = []
        try:
            with open(self.stats_file, 'r') as f:
                content = f.read()
                try:
                    # Try parsing as single object or array first
                    stats_list = json.loads(content)
                    if isinstance(stats_list, list):
                        for stats_json in stats_list:
                            history.append(RdKafkaStats(stats_json))
                    else:
                        history.append(RdKafkaStats(stats_list))
                except json.JSONDecodeError:
                    # Fall back to parsing multiple concatenated JSON objects
                    decoder = json.JSONDecoder()
                    pos = 0
                    while pos < len(content):
                        content_stripped = content[pos:].lstrip()
                        if not content_stripped: break
                        try:
                            obj, read_len = decoder.raw_decode(content_stripped)
                            history.append(RdKafkaStats(obj))
                            pos += (len(content_stripped) - len(content_stripped[read_len:]))
                        except json.JSONDecodeError: break
        except FileNotFoundError:
            print(f"Error: File not found at {self.stats_file}")
            return []
        
        # Sort by timestamp
        history.sort(key=lambda s: s.ts if s.ts is not None else 0)
        
        # Deduplicate: merge records with the same timestamp
        # This handles cases where the JSON has multiple records per timestamp,
        # each potentially containing different topics or brokers
        seen_timestamps = {}
        for stat in history:
            if stat.time is not None:
                if stat.time in seen_timestamps:
                    # Merge topics and brokers from this record into the existing one
                    existing = seen_timestamps[stat.time]
                    # Merge topics
                    for topic_name, topic_stats in stat.topics.items():
                        if topic_name not in existing.topics:
                            existing.topics[topic_name] = topic_stats
                        else:
                            # Merge partitions within the topic
                            for part_id, part_stats in topic_stats.partitions.items():
                                if part_id not in existing.topics[topic_name].partitions:
                                    existing.topics[topic_name].partitions[part_id] = part_stats
                    # Merge brokers
                    for broker_name, broker_stats in stat.brokers.items():
                        if broker_name not in existing.brokers:
                            existing.brokers[broker_name] = broker_stats
                else:
                    seen_timestamps[stat.time] = stat
        
        deduplicated = list(seen_timestamps.values())
        deduplicated.sort(key=lambda s: s.time if s.time is not None else 0)
        
        if len(deduplicated) < len(history):
            print(f"Deduplicated {len(history)} records down to {len(deduplicated)} unique timestamps (merged data from duplicates)")
        
        return deduplicated

    def print_summary(self):
        """
        Print a human-readable summary of the most recent statistics.
        
        Displays:
        - Timestamp and client information
        - Broker states and RTT metrics
        - Topic partitions with consumer lag (for consumers)
        """
        latest = self.stats_history[-1] if self.stats_history else None
        if not latest:
            print("No stats available.")
            return
        
        print("\n--- Latest Statistics Summary ---")
        timestamp_str = datetime.fromtimestamp(latest.time).isoformat() if latest.time else "N/A"
        print(f"Timestamp: {timestamp_str}")
        print(f"Client: {latest.data.get('name')} ({latest.type})")
        
        print("\nBrokers:")
        for name, broker in sorted(latest.brokers.items()):
            if broker.source == 'logical': continue
            rtt_ms = (broker.rtt_avg / 1000) if broker.rtt_avg is not None else 'N/A'
            print(f"  - {name}: State={broker.state}, RTT(avg)={rtt_ms} ms")

        print("\nTopics:")
        for name, topic in sorted(latest.topics.items()):
            print(f"  - {name}:")
            for part_id, p in sorted(topic.partitions.items(), key=lambda item: int(item[0]) if item[0].isdigit() else -1):
                if p.partition == -1: continue
                lag = p.consumer_lag if p.consumer_lag != -1 else 'N/A'
                print(f"    - Partition {part_id}: Leader={p.leader}, Consumer Lag={lag}")

    def _get_time_series_data(self):
        """
        Extract time-series data from the statistics history for graphing.
        
        Processes all statistics snapshots and organizes them into plottable
        time series for brokers and topics. Calculates derived metrics like
        data rates from cumulative byte counts.
        
        Returns:
            Dictionary containing:
            - timestamps: List of datetime objects
            - client_type: 'producer' or 'consumer'
            - brokers: Dict mapping broker names to metric time series
            - topics: Dict mapping topics to partitions to metric time series
            
            Returns None if insufficient data points (< 2)
        """
        if len(self.stats_history) < 2: return None

        plottable_stats = [s for s in self.stats_history if s.time is not None]
        timestamps = [datetime.fromtimestamp(s.time) for s in plottable_stats]
        
        # Collect all unique broker, topic, and partition keys across all snapshots
        all_broker_keys, all_topic_keys, all_partition_keys = set(), set(), set()
        for s in plottable_stats:
            for b_name, b_stats in s.brokers.items():
                if b_stats.source != 'logical': all_broker_keys.add(b_name)
            for t_name, t_stats in s.topics.items():
                all_topic_keys.add(t_name)
                for p_id, p_stats in t_stats.partitions.items():
                    if p_stats.partition != -1: all_partition_keys.add(f"{t_name}-{p_id}")
        
        # Initialize data structure for time series
        data = {
            'timestamps': timestamps, 'client_type': plottable_stats[0].type if plottable_stats else 'unknown',
            'brokers': {b: {'rtt': [], 'state': [], 'throttle': [], 'connects': [], 'disconnects': [], 'rx_rate': [], 'tx_rate': [], 'rxerrs': [], 'txerrs': [], 'last_rxbytes': None, 'last_txbytes': None} for b in all_broker_keys},
            'topics': {t: {p: {'lag': [], 'lag_stored': [], 'committed': [], 'stored': [], 'leader_epoch': [], 'leader_last': None} for p in all_partition_keys if p.startswith(t)} for t in all_topic_keys}
        }
        
        last_time = plottable_stats[0].time if plottable_stats else 0
        state_map = {"UP": 1, "INIT": 0, "DOWN": -1}

        for stats in plottable_stats:
            # Calculate time delta for rate calculations (MB/s)
            time_delta = stats.time - last_time if last_time and stats.time > last_time else 1
            for b_key in all_broker_keys:
                broker = stats.brokers.get(b_key)
                b_data = data['brokers'][b_key]
                
                # Collect basic broker metrics
                b_data['rtt'].append(broker.rtt_avg / 1000 if broker and broker.rtt_avg is not None else np.nan)
                b_data['state'].append(state_map.get(broker.state, np.nan) if broker else np.nan)
                b_data['throttle'].append(broker.throttle_avg / 1000 if broker and broker.throttle_avg is not None else np.nan)
                b_data['connects'].append(broker.connects if broker else np.nan)
                b_data['disconnects'].append(broker.disconnects if broker else np.nan)
                b_data['rxerrs'].append(broker.rxerrs if broker else np.nan)
                b_data['txerrs'].append(broker.txerrs if broker else np.nan)

                # Calculate RX rate in MB/s from cumulative bytes
                current_rx = broker.rxbytes if broker else 0
                rx_delta = current_rx - b_data['last_rxbytes'] if b_data['last_rxbytes'] is not None and current_rx >= b_data['last_rxbytes'] else 0
                b_data['rx_rate'].append(rx_delta / time_delta / (1024*1024))
                b_data['last_rxbytes'] = current_rx

                # Calculate TX rate in MB/s from cumulative bytes
                current_tx = broker.txbytes if broker else 0
                tx_delta = current_tx - b_data['last_txbytes'] if b_data['last_txbytes'] is not None and current_tx >= b_data['last_txbytes'] else 0
                b_data['tx_rate'].append(tx_delta / time_delta / (1024*1024))
                b_data['last_txbytes'] = current_tx

            # Collect partition metrics for each topic
            for t_key in all_topic_keys:
                topic = stats.topics.get(t_key)
                for p_key in data['topics'][t_key]:
                    _, p_id_str = p_key.rsplit('-', 1)
                    part = topic.partitions.get(p_id_str) if topic else None
                    p_data = data['topics'][t_key][p_key]
                    # Keep actual values including -1 and -1001 (we'll display them meaningfully later)
                    p_data['lag'].append(part.consumer_lag if part else np.nan)
                    p_data['lag_stored'].append(part.consumer_lag_stored if part else np.nan)
                    p_data['committed'].append(part.committed_offset if part else np.nan)
                    p_data['stored'].append(part.stored_offset if part else np.nan)
                    p_data['leader_epoch'].append(part.committed_leader_epoch if part else np.nan)
                    # Track the last valid leader ID for display purposes
                    if part and part.leader is not None and part.leader != -1:
                        p_data['leader_last'] = part.leader
            last_time = stats.time
        return data

    def write_debug_data(self, data, output_file="debug_data.txt"):
        """
        Write a raw dump of the parsed time-series data for debugging.
        
        This preserves previous behavior so existing workflows keep working.
        A richer per-plot debug is produced elsewhere when --debug-data is on.
        
        Args:
            data: Dictionary of time-series data from _get_time_series_data()
            output_file: Path to write debug output (default: "debug_data.txt")
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(f"Writing debug data to {output_file}...")
        with open(output_file, 'w') as f:
            for category, items in data.items():
                if category == 'timestamps':
                    f.write(f"--- TIMESTAMPS ---\n{[ts.isoformat() for ts in items]}\n\n")
                    continue
                if category == 'client_type':
                    f.write(f"--- CLIENT_TYPE ---\n{items}\n\n")
                    continue
                f.write(f"--- {category.upper()} ---\n")
                for name, metrics in items.items():
                    f.write(f"  {name}:\n")
                    for metric_name, values in metrics.items():
                        # Don't write the byte counters used for rate calculation
                        if 'last_rxbytes' in metric_name or 'last_txbytes' in metric_name:
                            continue
                        f.write(f"    {metric_name}: {values}\n")
                    f.write("\n")

    # ------------------------------
    # Plot-level debug helper methods
    # ------------------------------
    
    @staticmethod
    def _slugify(name: str) -> str:
        """
        Convert a name to a filesystem-safe slug.
        
        Replaces non-alphanumeric characters with underscores.
        
        Args:
            name: Original name string
            
        Returns:
            Slugified name safe for filenames
        """
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name)

    def _series_stats(self, data_map: Dict[str, List[float]]):
        """
        Calculate statistics for each time series in a plot.
        
        Computes summary statistics to help identify issues with data visibility,
        such as all NaN values, constant values, or insufficient data points.
        
        Treats -1 and -1001 as special 'Not Assigned' sentinel values that
        are tracked separately from valid data.
        
        Args:
            data_map: Dictionary mapping series names to lists of values
            
        Returns:
            Dictionary mapping series names to their statistics:
            - total: Total number of points
            - valid: Number of valid (non-NaN, non-sentinel) points
            - first_idx: Index of first valid point
            - last_idx: Index of last valid point
            - min: Minimum valid value
            - max: Maximum valid value
            - constant: Whether all valid values are identical
            - not_assigned: Count of sentinel values (-1 or -1001)
        """
        stats = {}
        for key, values in data_map.items():
            total = len(values)
            # Check if all values are "Not Assigned" (-1 or -1001)
            not_assigned_count = sum(1 for v in values if v == -1 or v == -1001)
            # Valid points exclude NaN and "Not Assigned" values
            valid_idx = [i for i, v in enumerate(values) if v is not None and not np.isnan(v) and v != -1 and v != -1001]
            valid = len(valid_idx)
            if valid:
                vals = [values[i] for i in valid_idx]
                vmin, vmax = np.min(vals), np.max(vals)
                constant = bool(np.allclose(vmin, vmax, equal_nan=False))
                stats[key] = {
                    'total': total,
                    'valid': valid,
                    'first_idx': int(valid_idx[0]),
                    'last_idx': int(valid_idx[-1]),
                    'min': float(vmin),
                    'max': float(vmax),
                    'constant': constant,
                    'not_assigned': not_assigned_count,
                }
            else:
                stats[key] = {
                    'total': total,
                    'valid': 0,
                    'first_idx': None,
                    'last_idx': None,
                    'min': None,
                    'max': None,
                    'constant': None,
                    'not_assigned': not_assigned_count,
                }
        return stats

    def _write_plot_debug(self, title: str, timestamps: List[datetime], data_map: Dict[str, List[float]], debug_dir: str):
        """
        Write detailed debug information for a specific plot.
        
        Creates two files:
        1. CSV with exact values plotted (timestamp + all series)
        2. Text summary with per-series statistics
        
        Also prints console warnings for series that may not be visible due to
        insufficient valid data points or constant values.
        
        Args:
            title: Plot title (used to generate filenames)
            timestamps: List of datetime objects for x-axis
            data_map: Dictionary mapping series names to value lists
            debug_dir: Directory to write debug files
        """
        os.makedirs(debug_dir, exist_ok=True)
        slug = self._slugify(title)
        csv_path = os.path.join(debug_dir, f"{slug}.csv")
        summary_path = os.path.join(debug_dir, f"{slug}.summary.txt")

        # CSV (timestamps + each series)
        series_keys = list(sorted(data_map.keys()))
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(",".join(["timestamp"] + [self._slugify(k) for k in series_keys]) + "\n")
            for i, ts in enumerate(timestamps):
                row = [ts.isoformat()]
                for k in series_keys:
                    v = data_map[k][i]
                    if v is None or np.isnan(v):
                        row.append("")
                    elif v == -1 or v == -1001:
                        row.append("Not Assigned")
                    else:
                        row.append(str(v))
                f.write(",".join(row) + "\n")

        # Text summary with per-series stats
        plot_stats = self._series_stats(data_map)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"Plot: {title}\n")
            f.write(f"Points per series: {len(timestamps)}\n\n")
            for k in series_keys:
                s = plot_stats[k]
                # Check if all points are "Not Assigned"
                if s.get('not_assigned', 0) == len(data_map[k]):
                    f.write(f"- {k}: All {len(data_map[k])} points = Not Assigned\n")
                elif s.get('not_assigned', 0) > 0 and s['valid'] > 0:
                    f.write(
                        (
                            f"- {k}: total={s['total']}, valid={s['valid']}, not_assigned={s['not_assigned']}, "
                            f"first_idx={s['first_idx']}, last_idx={s['last_idx']}, "
                            f"min={s['min']}, max={s['max']}, constant={s['constant']}\n"
                        )
                    )
                else:
                    f.write(
                        (
                            f"- {k}: total={s['total']}, valid={s['valid']}, "
                            f"first_idx={s['first_idx']}, last_idx={s['last_idx']}, "
                            f"min={s['min']}, max={s['max']}, constant={s['constant']}\n"
                        )
                    )

        # Console hints for common visibility causes
        for k, s in plot_stats.items():
            if s['valid'] < 2:
                print(
                    f"[debug] '{title}' series '{k}' has only {s['valid']} valid point(s) "
                    "— lines won't render; consider markers."
                )
            elif s['constant'] and s['min'] is not None:
                print(
                    f"[debug] '{title}' series '{k}' is constant at {s['min']} (flat line)."
                )

    def generate_graphs(self, output_dir: str, debug: bool = False, show_empty: bool = False, 
                       legend_valid: bool = True, annotate: bool = True, line_width: float = 3.0):
        """
        Generate comprehensive time-series graphs for all metrics.
        
        Creates PNG files with multiple subplots showing:
        - Broker metrics: RTT, data rates, connections, errors, throttle, state
        - Consumer metrics: lag, offsets, leader epochs (consumer clients only)
        
        Args:
            output_dir: Directory to save graph PNG files
            debug: If True, write debug CSV/summary files for each plot
            show_empty: If True, include series with no valid data points
            legend_valid: If True, append data point counts to legend labels
            annotate: If True, add small text annotations showing series counts
            line_width: Width of plot lines in points (default: 3.0)
        """
        data = self._get_time_series_data()
        if not data:
            print("Not enough data points to generate graphs.")
            return

        debug_dir = os.path.join(output_dir, "debug")
        if debug:
            # Raw dump plus plot-level CSVs/summaries will be created below
            self.write_debug_data(data, os.path.join(debug_dir, "debug_data.txt"))

        if not os.path.exists(output_dir): os.makedirs(output_dir)
        print(f"\nGenerating graphs into directory: {output_dir}...")

        timestamps = data['timestamps']
        
        def pretty_broker_label(name: str) -> str:
            """
            Convert raw broker name to human-friendly label.
            
            Examples:
            - 'hostname:9092/5' -> 'Broker #5 (g005)'
            - 'hostname:9092/bootstrap' -> 'Bootstrap'
            
            Args:
                name: Raw broker identifier from librdkafka
                
            Returns:
                Human-readable broker label
            """
            if name.endswith('/bootstrap'):
                return 'Bootstrap'
            grp_match = re.search(r'(g\d{3,})', name)
            id_match = re.search(r'/(\d+)$', name)
            grp = grp_match.group(1) if grp_match else None
            bid = id_match.group(1) if id_match else None
            if bid and grp:
                return f"Broker #{bid} ({grp})"
            if bid:
                return f"Broker #{bid}"
            return name
            
        def plot_data(ax, title, ylabel, data_map, drawstyle='default', center_y=False, 
                     name_transform=lambda s: s, show_valid=False, linewidth=3.0):
            """
            Plot a single metric across multiple series.
            
            Handles special cases like constant values, sparse data, and sentinel
            values (-1, -1001). Automatically adds markers for series with < 2
            valid points and adjusts y-axis scaling intelligently.
            
            Args:
                ax: Matplotlib axes object to plot on
                title: Plot title
                ylabel: Y-axis label
                data_map: Dictionary mapping series names to value lists
                drawstyle: Matplotlib drawstyle ('default', 'steps-post', etc.)
                center_y: If True, center y-axis around data (vs bottom at 0)
                name_transform: Function to transform series names for display
                show_valid: If True, show data point counts in legend
                linewidth: Width of plot lines
            """
            ax.clear()
            ax.set_title(title); ax.set_ylabel(ylabel)
            all_values = []
            
            for name, values in data_map.items():
                label_name = name_transform(name)
                # Filter out -1 and -1001 (Not Assigned) for valid point counting
                valid_points = [v for v in values if v is not None and not np.isnan(v) and v != -1 and v != -1001]
                # Use markers for sparse data (< 2 points won't draw a line)
                marker = 'o' if len(valid_points) < 2 else None
                markersize = 3 if marker else None
                
                # Check if all values are "Not Assigned" (-1 or -1001)
                not_assigned_count = sum(1 for v in values if v == -1 or v == -1001)
                all_not_assigned = not_assigned_count == len(values)
                
                # Build legend label with optional data point information
                if show_valid:
                    if all_not_assigned:
                        # All values are "Not Assigned"
                        label = f"{label_name} (Not Assigned)"
                    elif len(valid_points) > 0 and all(v == valid_points[0] for v in valid_points):
                        # Constant value - show it in legend with intelligent formatting
                        const_val = valid_points[0]
                        if abs(const_val) >= 1000:
                            # Large values (like offsets): show as integer with commas
                            const_str = f"{int(const_val):,}"
                        elif abs(const_val) < 0.01 and const_val != 0:
                            # Very small non-zero values: scientific notation
                            const_str = f"{const_val:.2e}"
                        else:
                            # Normal range: 2 decimal places
                            const_str = f"{const_val:.2f}"
                        label = f"{label_name} ({len(valid_points)} data points, constant={const_str})"
                    else:
                        # Varying values - just show count
                        label = f"{label_name} ({len(valid_points)} data points)"
                else:
                    label = f"{label_name}"
                
                # Replace -1 and -1001 with np.nan for plotting (won't draw line through them)
                plot_values = [np.nan if (v == -1 or v == -1001) else v for v in values]
                
                # Use linewidth and no fill to ensure clean line plots
                ax.plot(timestamps, plot_values, linestyle='-', marker=marker, markersize=markersize, 
                       label=label, drawstyle=drawstyle, linewidth=linewidth, alpha=0.8)
                all_values.extend(valid_points)  # Only add valid points to all_values for axis scaling
                
            ax.grid(True); ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize='small')
            ax.tick_params(axis='x', rotation=30, labelsize='small')
            # Friendly time axis formatting
            locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            
            valid_values = [v for v in all_values if v is not None and not np.isnan(v)]
            if not valid_values:
                ax.text(0.5, 0.5, 'No Data Available', horizontalalignment='center', 
                       verticalalignment='center', transform=ax.transAxes)
                return

            # Intelligent y-axis scaling based on data characteristics
            min_val, max_val = min(valid_values), max(valid_values)
            if center_y:
                if max_val > min_val:
                    # Values vary - use 10% margin
                    margin = (max_val - min_val) * 0.1
                else:
                    # Constant value - use percentage of absolute value or minimum visible range
                    if abs(min_val) > 10:
                        # For large values (like offsets in millions), use 0.1% margin
                        margin = abs(min_val) * 0.001
                    else:
                        # For small values near zero, use fixed small margin
                        margin = max(1.0, abs(min_val) * 0.1)
                ax.set_ylim(bottom=min_val - margin, top=max_val + margin)
            else:
                # For non-centered (like lag metrics), ensure we can see the lines
                if max_val == min_val:
                    # Constant value - add visible margin above and below
                    if min_val == 0:
                        # For zero, center it in view with equal margins above and below
                        ax.set_ylim(bottom=-0.5, top=0.5)
                    elif min_val < 10:
                        # For small values, use symmetric range around the value
                        margin = max(abs(min_val) * 0.5, 2.0)
                        ax.set_ylim(bottom=min_val - margin, top=min_val + margin)
                    else:
                        margin = max(abs(min_val) * 0.1, 1.0)
                        ax.set_ylim(bottom=max(0, min_val - margin), top=min_val + margin)
                else:
                    ax.autoscale(enable=True, axis='y')
            # Prefer integer ticks for discrete/count metrics
            if any(kw in ylabel.lower() for kw in ['count', 'epoch', 'state', 'offset', 'lag']):
                ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

        # --- BROKER GRAPHS ---
        # Define all broker plots with their configurations
        broker_plots = [
            ('Broker RTT', 'RTT (ms)', {k: v['rtt'] for k, v in data['brokers'].items()}, 'default', True),
            ('Broker Data Rate (TX)', 'MB/s', {k: v['tx_rate'] for k, v in data['brokers'].items()}),
            ('Broker Data Rate (RX)', 'MB/s', {k: v['rx_rate'] for k, v in data['brokers'].items()}),
            ('Broker Connections', 'Count', {k: v['connects'] for k, v in data['brokers'].items()}),
            ('Broker Disconnections', 'Count', {k: v['disconnects'] for k, v in data['brokers'].items()}),
            ('Broker Throttle Time', 'Throttle (ms)', {k: v['throttle'] for k, v in data['brokers'].items()}),
            ('Broker Receive Errors', 'Cumulative Errors', {k: v['rxerrs'] for k, v in data['brokers'].items()}),
            ('Broker State', 'State', {k: v['state'] for k, v in data['brokers'].items()}, 'steps-post'),
        ]
        
        # Create multi-subplot figure for all broker metrics
        fig_b, axes_b = plt.subplots(len(broker_plots), 1, figsize=(15, 6 * len(broker_plots)), sharex=True)
        if len(broker_plots) == 1: axes_b = [axes_b]
        
        for i, plot_def in enumerate(broker_plots):
            title, ylabel, d_map, *rest = plot_def
            style, center = (rest[0], rest[1]) if len(rest) > 1 else (rest[0] if rest else 'default', False)
            ax = axes_b[i]
            
            # Filter out empty series unless show_empty is True
            if not show_empty:
                d_map = {k: v for k, v in d_map.items() if any(vv is not None and not np.isnan(vv) for vv in v)}
            
            plot_data(ax, title, ylabel, d_map, drawstyle=style, center_y=center, 
                     name_transform=pretty_broker_label, show_valid=legend_valid, linewidth=line_width)
            
            # Add small annotation with series statistics
            if annotate:
                stats_display = self._series_stats(d_map)
                constants = sum(1 for s in stats_display.values() if s['valid'] > 0 and s['constant'])
                ax.text(0.01, 0.02, f"series:{len(d_map)} const:{constants}", 
                       transform=ax.transAxes, fontsize='x-small', alpha=0.7)
            
            # Write detailed debug files if requested
            if debug:
                self._write_plot_debug(title, timestamps, d_map, os.path.join(debug_dir, 'brokers'))
            
            # Set y-axis lower bound to 0 for rate/count metrics
            if not center and ('Rate' in title or 'Errors' in title or 'Count' in title or 'Throttle' in title):
                ax.set_ylim(bottom=0)
            
            # Special handling for broker state plot (discrete values)
            if title == 'Broker State':
                ax.set_yticks([-1, 0, 1])
                ax.set_yticklabels(['DOWN', 'INIT', 'UP'])
                ax.set_ylim(bottom=-1.5, top=1.5)
        
        # Save broker metrics figure
        fig_b.tight_layout(rect=[0, 0, 0.85, 0.98])
        broker_output_path = os.path.join(output_dir, "broker_metrics.png")
        fig_b.savefig(broker_output_path)
        plt.close(fig_b)
        print(f"Saved broker metrics to {broker_output_path}")

        # --- TOPIC GRAPHS (Consumer metrics only) ---
        if data['client_type'] == 'consumer':
            for topic_name, partition_data in data['topics'].items():
                if not partition_data: continue
                topic_plots = [
                    ('Committed Offset', 'Offset', {p: d['committed'] for p, d in partition_data.items()}, True),
                    ('Stored Offset', 'Offset', {p: d['stored'] for p, d in partition_data.items()}, True),
                    ('Committed Leader Epoch', 'Epoch', {p: d['leader_epoch'] for p, d in partition_data.items()}, True),
                    ('Consumer Lag', 'Lag (Messages)', {p: d['lag'] for p, d in partition_data.items()}),
                    ('Stored Consumer Lag', 'Lag (Messages)', {p: d['lag_stored'] for p, d in partition_data.items()}),
                ]
                fig_t, axes_t = plt.subplots(len(topic_plots), 1, figsize=(15, 5 * len(topic_plots)), sharex=True)
                if len(topic_plots) == 1: axes_t = [axes_t]
                for i, plot_def in enumerate(topic_plots):
                    title, ylabel, d_map, *rest = plot_def
                    center = rest[0] if rest else False
                    ax = axes_t[i]
                    # Human-friendly partition labels with leader when available
                    clean_d_map = {}
                    for k, v in d_map.items():
                        pid = k.rsplit('-', 1)[1]
                        leader = partition_data[k].get('leader_last')
                        label = f"Partition {pid}" + (f" (Leader {leader})" if leader is not None else "")
                        clean_d_map[label] = v
                    # Filter empties if requested (but keep "Not Assigned" partitions to show them)
                    full_map = clean_d_map
                    if not show_empty:
                        # Keep series that have valid data OR are "Not Assigned" (-1 or -1001)
                        clean_d_map = {k: v for k, v in full_map.items() 
                                      if any(vv is not None and not np.isnan(vv) for vv in v)}
                    plot_data(ax, f"{topic_name}: {title}", ylabel, clean_d_map, center_y=center, show_valid=legend_valid, linewidth=line_width)
                    if annotate:
                        stats_display = self._series_stats(clean_d_map)
                        constants = sum(1 for s in stats_display.values() if s['valid'] > 0 and s['constant'])
                        hidden = len(full_map) - len(clean_d_map)
                        ax.text(0.01, 0.02, f"series:{len(clean_d_map)} hidden:{hidden} const:{constants}", transform=ax.transAxes, fontsize='x-small', alpha=0.7)
                    if debug:
                        self._write_plot_debug(f"{topic_name}: {title}", timestamps, clean_d_map, os.path.join(debug_dir, 'topics'))
                    if not center: ax.set_ylim(bottom=0)
                fig_t.tight_layout(rect=[0, 0, 0.85, 0.98]); topic_output_path = os.path.join(output_dir, f"topic_{topic_name.replace('.', '_')}.png")
                fig_t.savefig(topic_output_path); plt.close(fig_t); print(f"Saved topic metrics for {topic_name} to {topic_output_path}")


def main():
    """
    Command-line entry point for the statistics parser.
    
    Parses command-line arguments and runs the parser with specified options.
    See --help for full usage information.
    """
    parser = argparse.ArgumentParser(
        description="Parse, analyze, and graph LibrdKafka statistics.",
        epilog="""
Examples:
  # Print summary of latest statistics
  python kafka_stats_parser.py stats.json
  
  # Generate graphs with default settings
  python kafka_stats_parser.py stats.json --graph
  
  # Generate graphs with debug output
  python kafka_stats_parser.py stats.json --graph --debug-data --output my_output
  
  # Customize graph appearance
  python kafka_stats_parser.py stats.json --graph --line-width 2.0 --show-empty
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("stats_file", 
                       help="Path to the file containing LibrdKafka JSON statistics.")
    parser.add_argument("--graph", action="store_true", 
                       help="Generate graphs of the statistics over time.")
    parser.add_argument("--output", default="kafka_graphs", 
                       help="Output directory name for the graphs (default: kafka_graphs).")
    parser.add_argument("--debug-data", action="store_true", 
                       help="Write the parsed time-series data and per-plot CSVs/summaries for debugging.")
    parser.add_argument("--show-empty", action="store_true", 
                       help="Include series with zero valid points in plots (default hides them).")
    parser.add_argument("--no-legend-valid", action="store_true", 
                       help="Do not append data point counts in legend labels.")
    parser.add_argument("--no-annotate", action="store_true", 
                       help="Disable small per-plot annotations (series/hidden/const counts).")
    parser.add_argument("--line-width", type=float, default=3.0, 
                       help="Line width for plots in points (default: 3.0).")
    
    args = parser.parse_args()

    # Parse the statistics file
    stats_parser = LibrdKafkaStatsParser(args.stats_file)
    if not stats_parser.stats_history: 
        return
    
    # Always print summary
    stats_parser.print_summary()
    
    # Generate graphs if requested
    if args.graph:
        stats_parser.generate_graphs(
            args.output,
            debug=args.debug_data,
            show_empty=args.show_empty,
            legend_valid=not args.no_legend_valid,
            annotate=not args.no_annotate,
            line_width=args.line_width,
        )


if __name__ == "__main__":
    main()
