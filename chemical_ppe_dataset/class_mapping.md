# Chemical PPE Dataset Class Mapping

This document defines the final accepted class mapping and the source-level mapping decisions used during C2 preparation.

## Final mapping

| Final ID | Final Name |
|---|---|
| 0 | person |
| 1 | gloves |
| 2 | goggles |
| 3 | face_shield |
| 4 | respirator |
| 5 | chemical_suit |
| 6 | protective_boots |

## Source mapping decisions

See the separate document [CHEMICAL_PPE_CLASS_MAPPING.md](../CHEMICAL_PPE_CLASS_MAPPING.md) for the full mapping table and acceptance rules.

## Important constraints

- No automatic mapping from medical PPE to industrial chemical PPE.
- No automatic mapping from ordinary footwear to protective boots.
- No automatic mapping from generic face coverings to respirators.
- No acceptance of non-equivalent labels simply to increase dataset size.

## Current status
- SH17 is under class validity review.
- CPPE-5 is under class validity review.
- Roboflow is blocked in this environment and remains conditional only.
