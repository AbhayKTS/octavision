# Chemical PPE Dataset Information

## Project
OctaVision Chemical Factory PPE Detection Dataset

## Final class schema

| ID | Name |
|---|---|
| 0 | person |
| 1 | gloves |
| 2 | goggles |
| 3 | face_shield |
| 4 | respirator |
| 5 | chemical_suit |
| 6 | protective_boots |

## Current status
This dataset directory is created for the C2 preparation phase only. No final training dataset has been accepted yet. The source datasets are still under validation and class-mapping review.

## Sources under evaluation
- SH17 PPE Dataset (primary candidate)
- CPPE-5 (secondary candidate)
- Chemical PPE Detection (Roboflow) (conditional / blocked in current environment)

## Collection policy
- Raw source data is kept separate from processed outputs.
- No original annotation files are modified.
- Accepted annotations are converted into YOLO format only in the processed folder.
- Rejected samples are logged under `excluded_samples/` with reasons.

## Split target
- train: 70%
- val: 20%
- test: 10%

## Preparation notes
- Processed labels must be generated from accepted sources only.
- Non-equivalent classes are excluded rather than forced into the final mapping.
- Duplicate and corrupt samples are logged and excluded.
