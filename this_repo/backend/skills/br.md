---
name: anatel-brazil
description: ANATEL Brazil homologation reference.
---
# ANATEL Brazil Reference

## Authoritative documents
- **ANATEL Resolution 715/2019** — Homologation of telecommunications products.
- **Act 14448/2017** — Equipment categorization (Cat I, II, III).
- **Resolution 442/2006** — RF exposure limits.

## SAR limit (Brazil)
**1.6 W/kg averaged over 1 g of tissue** for general public, aligned with FCC.

## Required tests for a 2.4 GHz BLE/Wi-Fi portable device
1. Cat II testing per Resolution 715/2019: RF emissions, modulation, occupied bandwidth.
2. SAR per Resolution 442/2006 for body-worn.
3. Homologation number issuance and labeling.

## Output format
```
{
  "region": "br",
  "summary": "<one paragraph>",
  "required_tests": [...],
  "citations": ["Resolution 715/2019", "Resolution 442/2006", ...],
  "estimated_hours": <integer>
}
```
