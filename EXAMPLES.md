# Example LibrdKafka Statistics Format

This file shows examples of what librdkafka statistics look like.

## How to Capture Statistics

### Enabling Statistics in librdkafka

To capture statistics from your Kafka client, configure librdkafka with:

```python
# Python (confluent-kafka)
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'mygroup',
    'statistics.interval.ms': 5000,  # Emit stats every 5 seconds
    'stats_cb': my_stats_callback
}

def my_stats_callback(stats_json_str):
    with open('kafka_stats.json', 'a') as f:
        f.write(stats_json_str + '\n')
```

```java
// Java
Properties props = new Properties();
props.put("statistics.interval.ms", "5000");
```

## Minimal Example Structure

### Producer Statistics
```json
{
  "name": "my-producer",
  "type": "producer",
  "ts": 1234567890123456,
  "time": 1234567890,
  "brokers": {
    "localhost:9092/1": {
      "name": "localhost:9092/1",
      "source": "learned",
      "state": "UP",
      "connects": 1,
      "disconnects": 0,
      "rxbytes": 1234567,
      "txbytes": 9876543,
      "rxerrs": 0,
      "txerrs": 0,
      "req_timeouts": 0,
      "rtt": {
        "avg": 5432
      },
      "throttle": {
        "avg": 0
      }
    }
  },
  "topics": {
    "my-topic": {
      "topic": "my-topic",
      "partitions": {
        "0": {
          "partition": 0,
          "leader": 1
        }
      }
    }
  }
}
```

### Consumer Statistics
```json
{
  "name": "my-consumer",
  "type": "consumer",
  "ts": 1234567890123456,
  "time": 1234567890,
  "brokers": {
    "localhost:9092/1": {
      "name": "localhost:9092/1",
      "source": "learned",
      "state": "UP",
      "connects": 1,
      "disconnects": 0,
      "rxbytes": 9876543,
      "txbytes": 1234567,
      "rxerrs": 0,
      "txerrs": 0,
      "req_timeouts": 0,
      "rtt": {
        "avg": 4321
      },
      "throttle": {
        "avg": 0
      }
    }
  },
  "topics": {
    "my-topic": {
      "topic": "my-topic",
      "partitions": {
        "0": {
          "partition": 0,
          "leader": 1,
          "consumer_lag": 42,
          "consumer_lag_stored": 42,
          "committed_offset": 12345678,
          "stored_offset": 12345678,
          "committed_leader_epoch": 5
        },
        "1": {
          "partition": 1,
          "leader": 2,
          "consumer_lag": 0,
          "consumer_lag_stored": 0,
          "committed_offset": 23456789,
          "stored_offset": 23456789,
          "committed_leader_epoch": 3
        }
      }
    }
  }
}
```

## Key Fields Explained

### Top Level
- **name**: Client identifier
- **type**: "producer" or "consumer"
- **ts**: Timestamp in microseconds since epoch
- **time**: Timestamp in seconds since epoch (used for time-series)

### Broker Fields
- **name**: Broker identifier (host:port/id)
- **source**: "learned" (discovered) or "logical" (bootstrap)
- **state**: Connection state - "UP", "DOWN", or "INIT"
- **connects/disconnects**: Connection event counters
- **rxbytes/txbytes**: Cumulative bytes received/transmitted
- **rxerrs/txerrs**: Cumulative receive/transmit errors
- **rtt.avg**: Average round-trip time in microseconds
- **throttle.avg**: Average broker throttle time in microseconds

### Partition Fields (Consumer)
- **partition**: Partition number (-1 if not assigned)
- **leader**: Broker ID of partition leader
- **consumer_lag**: Messages behind high water mark (-1 if not assigned)
- **consumer_lag_stored**: Lag based on stored offset
- **committed_offset**: Last committed offset (-1001 if none)
- **stored_offset**: Last stored offset (-1001 if none)
- **committed_leader_epoch**: Leader epoch at commit time (-1 if unknown)

## Collecting Statistics Over Time

To collect useful time-series data, capture statistics at regular intervals:

```bash
# Your application should append stats to a file
# Example output file with multiple statistics snapshots:
cat kafka_stats.json
{"ts": 1234567890000000, "time": 1234567890, "type": "consumer", ...}
{"ts": 1234567895000000, "time": 1234567895, "type": "consumer", ...}
{"ts": 1234567900000000, "time": 1234567900, "type": "consumer", ...}
```

The parser can handle all three formats:
1. Single JSON object
2. JSON array: `[{...}, {...}]`
3. Multiple concatenated objects (shown above)

## Testing the Parser

1. Save one of the examples above to `test_stats.json`
2. Run: `python kafka_stats_parser.py test_stats.json`
3. For graphs (requires multiple timestamps):
   - Add more entries with different `time` values
   - Run: `python kafka_stats_parser.py test_stats.json --graph`

## Full Statistics Structure

For complete documentation of all available fields in librdkafka statistics:
- [librdkafka Statistics Documentation](https://github.com/confluentinc/librdkafka/blob/master/STATISTICS.md)

The parser focuses on the most operationally relevant metrics but can be extended to graph additional fields from the statistics JSON.
