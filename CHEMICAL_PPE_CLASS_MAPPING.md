# Chemical PPE Class Mapping

## Final required classes

The final chemical PPE dataset must use exactly seven classes and keep the IDs stable across the whole project.

| Class ID | Final Class Name |
|---|---|
| 0 | person |
| 1 | gloves |
| 2 | goggles |
| 3 | face_shield |
| 4 | respirator |
| 5 | chemical_suit |
| 6 | protective_boots |

## Mapping rules

The following rules are enforced for every candidate source:

- `person` is accepted only for actual human person detections.
- `gloves` is accepted only when the glove object is visually identifiable as hand PPE.
- `goggles` are accepted only when the object is eyewear used as safety goggles, not generic glasses or face shields.
- `face_shield` is accepted only when the annotation is an actual face shield.
- `respirator` is accepted only when the object is industrial/chemical respirator equipment, not ordinary masks.
- `chemical_suit` is accepted only when the object is a protective suit or coverall consistent with chemical PPE.
- `protective_boots` are accepted only when the object is protective footwear, not ordinary shoes.

## Source-to-final mapping table

| Source dataset | Original class | Accepted final class | Status | Notes |
|---|---|---|---|---|
| SH17 | Person | person | Accepted | Direct visual match |
| SH17 | Gloves | gloves | Accepted | Direct visual match |
| SH17 | Glasses | goggles | Conditional | Accept only when the annotation is protective safety goggles, not ordinary glasses |
| SH17 | Face-guard | face_shield | Conditional | Accept only when visually equivalent to a face shield |
| SH17 | Face-mask-medical | respirator | Rejected by default | Medical mask is not automatically equivalent to industrial respirator |
| SH17 | Safety-suit | chemical_suit | Conditional | Accept only if visual meaning matches chemical protective suit |
| SH17 | Medical-suit | chemical_suit | Conditional | Accept only if visual meaning matches chemical protective suit |
| SH17 | Helmet | none | Rejected | Not part of the final seven-class chemical model |
| SH17 | Safety-vest | none | Rejected | Not part of final class set |
| SH17 | Shoes | protective_boots | Rejected by default | Ordinary footwear cannot be assumed to be protective boots |
| CPPE-5 | Coveralls | chemical_suit | Conditional | Accept only if they visually match chemical protective suits |
| CPPE-5 | Face shields | face_shield | Accepted | likely direct visual match |
| CPPE-5 | Gloves | gloves | Accepted | likely direct visual match |
| CPPE-5 | Masks | respirator | Rejected by default | medical masks are not equivalent to industrial respirators |
| CPPE-5 | Goggles | goggles | Accepted | likely direct visual match |
| Roboflow chemical PPE | Person | person | Accepted if verified | pending access |
| Roboflow chemical PPE | Boots | protective_boots | Conditional | only if actually protective boots |
| Roboflow chemical PPE | Chemical gloves | gloves | Conditional | likely direct visual match |
| Roboflow chemical PPE | Face shield | face_shield | Conditional | likely direct visual match |
| Roboflow chemical PPE | Masks | respirator | Rejected by default unless verified | mask type must match industrial respirator |

## Exclusion policy

The following classes are excluded unless direct visual evidence proves equivalence:

- ordinary glasses -> goggles
- ordinary shoes -> protective_boots
- medical masks -> respirator
- general coveralls -> chemical_suit
- general face visors -> face_shield when not clear

## Mapping validation criteria

A class mapping is accepted only if all of the following are true:

1. The original object is clearly the same PPE category.
2. The annotation semantics are equivalent.
3. The image evidence is consistent with the final class definition.
4. There is no obvious confusion with a different object type.
5. The mapping does not inflate dataset size with incorrect or generic PPE.

## Decision summary

At the time of this C2 audit, SH17 remains the strongest accessible candidate, but it still requires class-by-class verification before final acceptance. CPPE-5 and Roboflow remain in conditional status pending direct annotation inspection.
