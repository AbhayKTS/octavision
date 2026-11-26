"""Site policies and conservative detector-label normalization.

Policies are examples and must be configured for the actual site and model.
A missing detection alone never proves that equipment is absent.
"""
SITE_PPE = {
    'general': ('helmet', 'vest'),
    'construction': ('helmet', 'vest', 'gloves'),
    'road': ('helmet', 'vest', 'gloves'),
    'chemical': ('gloves', 'goggles', 'face_shield', 'respirator', 'chemical_suit', 'protective_boots'),
    'mining': ('helmet', 'vest', 'gloves', 'protective_boots', 'respirator'),
}
ALIASES = {
    'person': 'person', 'human': 'person', 'worker': 'person',
    'hardhat': 'helmet', 'hard_hat': 'helmet', 'with_helmet': 'helmet',
    'safety_helmet': 'helmet', 'safety_vest': 'vest', 'with_vest': 'vest',
    'glove': 'gloves', 'safety_gloves': 'gloves',
    'goggle': 'goggles', 'safety_goggles': 'goggles',
    'boots': 'protective_boots', 'safety_boots': 'protective_boots',
    'suit': 'chemical_suit', 'no_hardhat': 'no_helmet', 'no_hard_hat': 'no_helmet',
    'without_helmet': 'no_helmet', 'helmet_missing': 'no_helmet',
    'without_vest': 'no_vest', 'vest_missing': 'no_vest',
    'no_glove': 'no_gloves', 'without_gloves': 'no_gloves',
    'no_boots': 'no_protective_boots',
}

def normalize(label):
    key = str(label).strip().lower().replace(' ', '_').replace('-', '_')
    return ALIASES.get(key, key)

def supported(names, site_type):
    labels = {normalize(n) for n in (names.values() if isinstance(names, dict) else names)}
    required = SITE_PPE[site_type]
    return {p: {'present': p in labels, 'missing': 'no_' + p in labels} for p in required}

def process_boxes(boxes, names, site_type):
    required = SITE_PPE[site_type]
    counts = {p: 0 for p in required}
    counts.update({'no_' + p: 0 for p in required})
    counts.update({'person': 0, 'full_ppe': 0})
    detections = []
    for box in boxes or []:
        raw = str(names[int(box.cls.item())])
        label = normalize(raw)
        missing = label.startswith('no_') and label[3:] in required
        if label != 'person' and label not in required and not missing:
            continue
        coords = [int(v) for v in box.xyxy[0].tolist()]
        counts[label] += 1
        item = {'class_name': raw, 'normalized_label': label,
                'confidence': round(float(box.conf.item()), 4),
                'bbox': dict(zip(('x1', 'y1', 'x2', 'y2'), coords)),
                'is_violation': missing,
                'label_text': label.replace('_', ' ').upper()}
        if missing:
            item['violation_type'] = label[3:]
        detections.append(item)
    return counts, detections
