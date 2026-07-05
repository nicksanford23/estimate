# Agent Triage Calibration Comparison

Two agents reviewed the same 20 neutral permit packets.

## Agent A

- Permit decisions: {'target_now': 9, 'maybe_later': 4, 'pass_now': 7}
- Document decisions listed: {'download_now': 14, 'pass_now': 49, 'maybe_download': 8}

## Agent B

- Permit decisions: {'target_now': 8, 'pass_now': 8, 'maybe_later': 4}
- Document decisions listed: {'download_now': 13, 'pass_now': 30, 'maybe_download': 7}

## Permit Agreement

| permit | agent_a | agent_b | agree |
|---|---|---|---|
| 14-27328-NEWC | target_now | target_now | yes |
| 16-17098-NEWC | pass_now | pass_now | yes |
| 19-09618-RNVS | target_now | target_now | yes |
| 19-17650-RNVS | target_now | target_now | yes |
| 19-27088-NEWC | maybe_later | maybe_later | yes |
| 19-32012-RNVS | pass_now | pass_now | yes |
| 19-33426-NEWC | pass_now | pass_now | yes |
| 21-10517-RNVS | target_now | target_now | yes |
| 22-19111-RNVS | target_now | maybe_later | no |
| 23-12861-NEWC | target_now | target_now | yes |
| 23-17882-RNVS | pass_now | pass_now | yes |
| 23-35090-RNVN | target_now | target_now | yes |
| 24-31391-RNVS | maybe_later | pass_now | no |
| 24-37443-NEWC | maybe_later | maybe_later | yes |
| 25-09195-RNVN | target_now | target_now | yes |
| 25-12276-NEWC | pass_now | pass_now | yes |
| 26-09624-RNVS | pass_now | pass_now | yes |
| 26-10912-RNVN | maybe_later | maybe_later | yes |
| 26-11301-RNVS | target_now | target_now | yes |
| 26-12298-NEWC | pass_now | pass_now | yes |

## Download-Now Agreement

- Agent A download_now docs: 14
- Agent B download_now docs: 13
- Consensus download_now docs: 9
- Agent A only: 5
- Agent B only: 4

### Consensus Queue

| doc_id | permit | already_downloaded | filename |
|---:|---|---|---|
| 1462752 | 14-27328-NEWC | False | charbonnets place 7211 regent street.pdf |
| 3911288 | 19-09618-RNVS | False | Construction Drawings.pdf |
| 4079564 | 19-17650-RNVS | False | 3034 a2 sp.pdf |
| 4079565 | 19-17650-RNVS | False | 3034 a1 sp.pdf |
| 5021275 | 21-10517-RNVS | False | 204 S Saratoga - RCC Stamped.pdf |
| 6440202 | 23-12861-NEWC | False | 2023.10.17_202822_1723HenrietteDelille_DD5-compressed.pdf |
| 6855543 | 23-35090-RNVN | False | 2801 Magazine 23-35090 SP RCC.pdf |
| 8260959 | 25-09195-RNVN | False | 2025.06.13 - 621 St Louis VCC approved rooftop lights, finishes.pdf |
| 9090685 | 26-11301-RNVS | False | 04.02.26_Sexy Eleven_ FLOORS PLAN.pdf |

### Agent A Only Download-Now

| doc_id | permit | already_downloaded | filename |
|---:|---|---|---|
| 6126328 | 22-19111-RNVS | False | 838 Canal - HDLC and RCC Stamped.pdf |
| 8260951 | 25-09195-RNVN | False | 2025.04.25 - 621 St Louis VCC approved arch 1of4 (VCC).pdf |
| 8260953 | 25-09195-RNVN | False | 2025.04.25 - 621 St Louis VCC approved arch 2of4 (RCC).pdf |
| 8260955 | 25-09195-RNVN | False | 2025.04.25 - 621 St Louis VCC approved arch 3of4 (RCC).pdf |
| 8260957 | 25-09195-RNVN | False | 2025.04.25 - 621 St Louis VCC approved arch 4of4 (RCC).pdf |

### Agent B Only Download-Now

| doc_id | permit | already_downloaded | filename |
|---:|---|---|---|
| 8021831 | 25-09195-RNVN | False | 250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECTURE 1 OF 4.pdf |
| 8021832 | 25-09195-RNVN | False | 250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECTURE 2 OF 4.pdf |
| 8021833 | 25-09195-RNVN | False | 250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECTURE 3 OF 4.pdf |
| 8021835 | 25-09195-RNVN | False | 250307_OMNI ROYAL ORLEANS_100 REVISED CONSTRUCTION DOCUMENTS_ARCHITECTURE 4 OF 4.pdf |
