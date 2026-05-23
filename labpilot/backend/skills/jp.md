---
name: japan-mic
description: Japan MIC / ARIB radio certification reference.
---
# Japan MIC / ARIB Reference

## Authoritative documents
- **MIC Ordinance 88** — Technical standards for specified radio equipment.
- **ARIB STD-T66** — 2.4 GHz band BLE / Wi-Fi standard.
- **ARIB STD-T108** — 920 MHz band wireless.
- **MIC Notice 173** — RF exposure evaluation.
- **Giteki mark** required for Japan market certification (Technical Conformity Mark).

## SAR limit (Japan)
**2.0 W/kg averaged over 10 g of tissue** for general public (head/body). Aligns with EU.

## Required tests for a 2.4 GHz BLE/Wi-Fi portable device
1. ARIB STD-T66: RF power, occupied bandwidth, spurious.
2. MIC Notice 173 / IEC 62209: SAR.
3. Application via a Registered Certification Body for Giteki mark.

## Output format
```
{
  "region": "jp",
  "summary": "<one paragraph>",
  "required_tests": [...],
  "citations": ["ARIB STD-T66", "MIC Ordinance 88", ...],
  "estimated_hours": <integer>
}
```
