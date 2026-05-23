---
name: ised-canada
description: ISED Canada radio certification reference (RSS standards).
---
# ISED Canada Reference

## Authoritative standards
- **RSS-Gen Issue 5** — General requirements for compliance of radio apparatus.
- **RSS-247 Issue 2** — Digital transmission systems, frequency hopping, and licence-exempt LANs.
- **RSS-210** — Licence-exempt radio apparatus.
- **RSS-102 Issue 6** — RF exposure compliance of radio apparatus (3 kHz - 300 GHz).
- **ICES-003** — ITE EMC standard.

## SAR limit (Canada)
**1.6 W/kg averaged over 1 g of tissue** — same numeric limit as the FCC. Applies to portable devices used within 20 cm of body.

## Required tests for a 2.4 GHz BLE/Wi-Fi portable device
1. RSS-247: RF output power, bandwidth, transmit duty cycle.
2. RSS-Gen: spurious, antenna, marking.
3. RSS-102: routine SAR evaluation.
4. ICES-003: EMC.
5. ISED Certification Number issuance via TCB.

## Output format
```
{
  "region": "ca",
  "summary": "<one paragraph>",
  "required_tests": [...],
  "citations": ["RSS-247 Issue 2", "RSS-102 Issue 6", ...],
  "estimated_hours": <integer>
}
```
