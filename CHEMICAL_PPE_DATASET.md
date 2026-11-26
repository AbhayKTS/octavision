# Chemical PPE Dataset Discovery

## Phase: C1 — Dataset Discovery

## Scope
This document inventories the candidate public datasets for the OctaVision Chemical Factory PPE model and records what is verified, what remains unverified, and which sources are viable to pursue for C2 preparation.

## Repository baseline
The current workspace contains only the construction PPE dataset under `datasets/construction-ppe` and no chemical PPE dataset folder yet. No chemical dataset files, labels, or YAML were present before this audit.

## Candidate A — Chemical PPE Detection (Roboflow Universe)

### Source
- Roboflow Universe candidate: "Chemical PPE Detection"
- User-provided size estimate: approximately 384 images

### Verified status
- Direct fetch from the public Roboflow site was attempted from this environment, but the site returned HTTP 403 and did not allow a reliable public metadata fetch.
- This means we cannot claim exact class names, download status, license, or dataset quality from direct verification in this environment.

### Candidate assessment
- Potential value: good chemical-industry specificity
- Risk: unverified class mapping and licensing
- Decision: keep as a candidate only until direct access or a trusted mirror is available

### Conclusion
This source is relevant, but not yet accepted as a verified dataset source.

## Candidate B — SH17 PPE Dataset

### Source
- GitHub: https://github.com/ahmadmughees/SH17dataset
- Dataset page: Kaggle dataset release

### Verified facts from public repository metadata
- 8,099 annotated images
- 75,994 annotated object instances
- 17 object classes
- Industrial PPE-focused dataset
- Paper and benchmark are published; repository includes YOLO training reference and evaluation pipeline
- License: CC BY-NC-SA 4.0
- Image source note: dataset uses Pexels imagery; users must comply with the Pexels license and responsible-use restrictions

### Class list from repository
1. Person
2. Head
3. Face
4. Glasses
5. Face-mask-medical
6. Face-guard
7. Ear
8. Earmuffs
9. Hands
10. Gloves
11. Foot
12. Shoes
13. Safety-vest
14. Tools
15. Helmet
16. Medical-suit
17. Safety-suit

### Mapping assessment to the finalized chemical model
This dataset is a strong industrial PPE foundation, but it is not a direct 1:1 match for the finalized chemical PPE classes:
- `gloves` is available and usable
- `glasses` may be mapped to `goggles` only if visual equivalence is established
- `face-guard` may be relevant to `face_shield` but must be checked carefully
- `safety-suit`/`medical-suit` are not automatically equivalent to `chemical_suit`
- `safety-vest` is not the same as `chemical_suit`
- `helmet` and `person` are present but relevant only if the target class definition matches the site-specific goal

### Conclusion
SH17 is a viable broad PPE foundation, but it requires careful class normalization and exclusions before use in the final chemical dataset.

## Candidate C — CPPE-5

### Source
- Hugging Face dataset: rishitdagli/cppe-5
- dataset size category: 1K-10K images
- task category: object detection
- modality: image

### Verified status
- Public dataset card confirms the dataset exists and is categorized as PPE/object-detection on Hugging Face.
- The accessible metadata confirms the dataset is a PPE dataset and the file bundle is present, but the exact class names and license details were not fully verifiable from the accessible public metadata in this environment.

### Candidate assessment
- Potential value: PPE visual diversity and additional worker scenarios
- Risk: exact class semantics and label compatibility are not fully confirmed from accessible metadata
- Decision: keep as a secondary candidate pending actual download and inspection

### Conclusion
CPPE-5 remains promising as a diversity source, but it is not yet accepted as a verified chemical dataset component.

## Final weighted assessment

### Accepted for further investigation
- SH17: strong candidate to provide broad industrial PPE diversity and training scale
- CPPE-5: secondary candidate for visual diversity, pending full class verification
- Chemical PPE Detection (Roboflow): relevant but currently unverified due access restrictions

### Not accepted yet
- None of the three sources is accepted as a final definitive chemical dataset component without direct inspection of class semantics, licenses, and image/annotation quality.

## Recommended C1 outcome
The next step should be to download and inspect the candidate data sources in a controlled way and produce a formal dataset inventory with:
- number of images
- number of annotations
- class distribution
- license status
- excluded classes
- duplicate detection
- image quality review
- train/validation/test split plan
- final list of accepted and rejected classes

## Decision gate before C2
Do not proceed to dataset preparation until each source is inspected for:
1. licensing and terms of use
2. actual class names and semantics
3. image quality and annotation consistency
4. class overlap with the required final chemical classes
5. exclusion of non-equivalent labels

## Final C1 recommendation
The best practical path is:
- start with SH17 as the primary foundation dataset
- keep CPPE-5 as a diversity supplement
- treat the Roboflow chemical PPE dataset as a promising but currently unverified source
- do not mix classes automatically without explicit equivalence checks

## Status
C1 dataset discovery is complete in this audit phase: the three candidate sources have been inventoried and assessed, but no source has been accepted as final yet.
