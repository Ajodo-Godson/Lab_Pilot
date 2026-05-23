---
name: eu-red
description: EU Radio Equipment Directive 2014/53/EU compliance reference.
---
# EU RED 2014/53/EU Reference

## Directive and key harmonized standards
- **2014/53/EU (RED)** — Radio Equipment Directive. Mandatory CE marking.
- **EN 300 328 v2.2.2** — Wideband transmission systems in the 2.4 GHz band.
- **EN 301 893** — 5 GHz RLAN with DFS, TPC.
- **EN 300 220** — Short-range devices in 25 MHz to 1 GHz.
- **EN 301 489-1** — EMC common requirements.
- **EN 301 489-17** — EMC for broadband data transmission systems.
- **EN 62311:2020** — Assessment of electronic and electrical equipment for human exposure to EMF (0 Hz - 300 GHz).
- **EN 50566** — SAR for handheld and body-mounted wireless devices in the 30 MHz - 6 GHz band.
- **EN 62209-1 / -2** — SAR measurement procedure (head and body-worn).
- **EN 50360 / 50364** — exposure assessment.

## SAR limit (EU)
**2.0 W/kg averaged over 10 g of tissue** (general public). Note this is different from FCC: 10 g vs 1 g, and limit is 2.0 vs 1.6.

## Required tests for a 2.4 GHz BLE/Wi-Fi portable device
1. EN 300 328: RF output power, duty cycle, adaptivity, spectrum efficiency.
2. EN 301 489-1, -17: EMC immunity and emissions.
3. EN 62311 / EN 50566 / EN 62209-2: SAR for body-worn.
4. Permanent equipment marking + DoC referencing the directives.

## Notifying body
Standard route is self-declaration with harmonized standards. A Notified Body is only required if the manufacturer deviates from harmonized standards.

## Output format
```
{
  "region": "eu",
  "summary": "<one paragraph>",
  "required_tests": ["<short name>", ...],
  "citations": ["EN 300 328 v2.2.2", "Directive 2014/53/EU", ...],
  "estimated_hours": <integer>
}
```
