# Chemical PPE Dataset Preparation

## Phase: C2

## Objective
Prepare the dataset pipeline and documentation for the chemical PPE model without beginning training. This document tracks source verification, normalization rules, dataset structure, custom data gaps, and validation actions required before C3.

## Dataset sources and status

| Source | Status | Access status | License status | Decision |
|---|---|---|---|---|
| SH17 PPE Dataset | Primary candidate | Accessible via public GitHub/Kaggle metadata | CC BY-NC-SA 4.0 for dataset; Pexels licensing also applies for imagery | Continue with inspection and class-mapping validation |
| CPPE-5 | Secondary candidate | Public dataset access available in principle | License status not conclusively verified in this environment | Continue with class-by-class inspection |
| Chemical PPE Detection (Roboflow) | Chemical-specific candidate | Blocked with HTTP 403 in this environment | Not verifiable until access is restored | Keep as conditional; do not include unless verified |

## Source-specific preparation plan

### SH17
- Good candidate for broad industrial PPE diversity
- Requires per-class filtering to remove non-equivalent classes
- Must be normalized to the final seven classes before training

### CPPE-5
- Good candidate for style and scene diversity
- Must be inspected for exact label names and bounding-box compatibility
- Must not be merged unless classes are clearly mapped to the final seven target classes

### Roboflow chemical PPE dataset
- Potentially valuable because of chemical context
- Not usable until access, license, and class definitions are verified
- If blocked, this is a documented blocker rather than an accepted source

## Required directory structure

The following structure is created under the repository root for the chemical PPE project:

```text
chemical_ppe_dataset/
    raw/
        sh17/
        cppe5/
        roboflow/

    processed/
        images/
            train/
            val/
            test/

        labels/
            train/
            val/
            test/

    chemical_ppe.yaml
    dataset_info.md
    class_mapping.md
    validation_reports/
    excluded_samples/
```

## Data normalization rules

All accepted images and labels must be normalized to the final YOLO dataset contract:

- class IDs must match exactly the final mapping
- bounding boxes must be normalized to YOLO format: `class_id x_center y_center width height`
- coordinates must be in normalized image-space units `(0,1)`
- invalid boxes must be rejected and recorded in `excluded_samples/`
- duplicates must be logged by image hash and source origin
- corrupt images must be excluded and recorded with reason
- source provenance must be retained in metadata or manifest files
- no original source annotation files are modified

## Custom data collection gaps

After reviewing the public datasets, the following categories are expected to require custom capture or manual annotation:

- industrial respirators
- chemical protective suits
- protective boots
- chemical-resistant gloves
- industrial goggles
- difficult lighting / occlusion / crowded-frame examples
- chemical plant worker scenarios with realistic PPE variation

These gaps should be filled with local or curated custom images and annotated using the final seven-class schema only.

## Split strategy

The initial target split is:

- 70% train
- 20% validation
- 10% test

Apply this split by source group, recording session, or original video cluster to avoid data leakage. Duplicate images and near-identical frames must not be shared across splits.

## Validation checks

The validation stage must check the following:

- seven-class mapping coverage
- valid YOLO coordinates
- missing annotations
- empty label files
- corrupt images
- duplicate images
- duplicate source records
- class imbalance
- train/validation/test leakage
- source provenance metadata

## Current preparation status

This C2 phase established the dataset framework and documentation but did not accept any source as final. No model training has started and no inference pipeline was modified.

## Acceptance gate before C3

Proceed to C3 only when:

1. all candidate sources are inspected and classified as accepted/rejected
2. mapping is documented and reviewed
3. dataset split plan is finalized
4. validation script is executed on actual dataset contents
5. custom data gaps are explicitly addressed
6. final dataset has a clean training/validation/test partition
