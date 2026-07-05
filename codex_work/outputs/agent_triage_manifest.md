# Agent Triage Packet Manifest

Neutral export for agent document triage. No download decisions are made by the script.

## Counts

- Raw Neon document rows: 34978
- Permit packets needing review: 2561
- R2 already-downloaded doc ids: 2262
- Working pipeline downloaded/rendered doc ids: 106
- Batch size: 20
- Batch files: 129

## Permit Download Status

| status | permits |
|---|---:|
| not_started | 1535 |
| partially_downloaded | 1026 |

## Permit Types

| code | permits |
|---|---:|
| RNVS | 1379 |
| NEWC | 1140 |
| RNVN | 42 |

## Files

- `agent_triage_packets.jsonl`: all permit packets.
- `agent_triage_batches/batch_*.jsonl`: same packets split for agents.
