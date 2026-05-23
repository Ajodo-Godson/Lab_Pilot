---
name: fcc-part-15
description: FCC Part 15 + KDB regulatory knowledge for unlicensed wireless devices.
---
# FCC Part 15 + RF Exposure Reference

## Authoritative parts
- **47 CFR Part 15.247** — Operation in 902-928, 2400-2483.5, 5725-5850 MHz under digital modulation rules.
- **47 CFR Part 15.249** — Operation in 2400-2483.5 MHz at lower transmit power (no SAR if all conditions met).
- **47 CFR Part 2.1093** — RF exposure rules for portable devices. SAR limit **1.6 W/kg averaged over 1 g of tissue.**
- **47 CFR Part 2.925** — FCC ID labeling.
- **OET-65** — RF human exposure evaluation guidelines.
- **KDB 447498 D01** — SAR measurement procedures for portable devices used within 20 cm of the body.
- **KDB 616217** — RF exposure compliance for mobile and portable devices.
- **KDB 558074** — DTS (Digital Transmission System) measurement guidance.
- **KDB 789033** — Software Defined Radio considerations.

## Required tests for a 2.4 GHz BLE/Wi-Fi portable device
1. RF Output Power, EIRP, Spectral Density (Part 15.247(b)).
2. Bandwidth (6 dB BW), Number of Hopping Channels (15.247(a)).
3. Out-of-Band Emissions, Restricted Band Edge (15.205, 15.209).
4. Conducted Emissions on AC mains (15.207) if mains-powered.
5. Antenna requirement (15.203) — fixed/permanently attached.
6. Receiver spurious emissions (15.109).
7. **SAR per KDB 447498** — for body-worn or held within 20 cm (1.6 W/kg, 1 g).
8. EMC ANSI C63.10 measurement procedure.

## Body-worn classification
A device is **portable** (SAR required) if it can be used within 20 cm of the body during normal operation. Wearables, smartwatches, fitness bands, smartphones, AirPods are portable. Smart speakers, gateways, and TV peripherals are typically **mobile** (MPE evaluation, no SAR).

## Estimating lab hours
- RF testing (Part 15.247 + 15.205 + 15.207): ~24-32 hours per radio/band.
- SAR per KDB 447498: ~16-24 hours per body position per radio.
- EMC: ~8 hours.

## Output format
When asked to analyze a device, respond with strict JSON matching:
```
{
  "region": "fcc",
  "summary": "<one paragraph>",
  "required_tests": ["<short test name>", ...],
  "citations": ["47 CFR 15.247(b)", "KDB 447498", ...],
  "estimated_hours": <integer>
}
```
