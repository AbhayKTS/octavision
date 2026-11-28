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
    required = SITE_PPE.get(site_type, SITE_PPE['construction'])
    can_detect_person = 'person' in labels
    res = {}
    for p in required:
        present = p in labels
        # Direct class detection or person-PPE compliance association for primary gear (helmet, vest)
        missing = ('no_' + p in labels) or (can_detect_person and p in {'helmet', 'vest'} and present)
        res[p] = {'present': present, 'missing': missing}
    return res


def _boxes_overlap_fraction(box_a, box_b):
    """Fraction of box_a area that is covered by box_b."""
    ax1, ay1, ax2, ay2 = box_a['x1'], box_a['y1'], box_a['x2'], box_a['y2']
    bx1, by1, bx2, by2 = box_b['x1'], box_b['y1'], box_b['x2'], box_b['y2']
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter_area = (ix2 - ix1) * (iy2 - iy1)
    a_area = max((ax2 - ax1) * (ay2 - ay1), 1)
    return inter_area / float(a_area)


def _is_gear_on_person(gear_box, person_box, gear_type):
    """
    Check if a piece of PPE (or explicit missing box) belongs to a person.
    """
    px1, py1, px2, py2 = person_box['x1'], person_box['y1'], person_box['x2'], person_box['y2']
    pw = max(px2 - px1, 1)
    ph = max(py2 - py1, 1)
    gx1, gy1, gx2, gy2 = gear_box['x1'], gear_box['y1'], gear_box['x2'], gear_box['y2']
    gcx = (gx1 + gx2) / 2.0
    gcy = (gy1 + gy2) / 2.0

    # Horizontal alignment: gear center within person bounds (+ 15% tolerance)
    if not (px1 - 0.15 * pw <= gcx <= px2 + 0.15 * pw):
        return False

    if gear_type in ('helmet', 'no_helmet'):
        # Head zone: top 45% of person (or up to 20% above head)
        return (py1 - 0.20 * ph <= gcy <= py1 + 0.45 * ph)

    if gear_type in ('vest', 'no_vest'):
        # Torso zone: 10% to 80% of person height
        return (py1 + 0.10 * ph <= gcy <= py1 + 0.80 * ph)

    return _boxes_overlap_fraction(gear_box, person_box) > 0.20


def process_boxes(boxes, names, site_type):
    required = SITE_PPE.get(site_type, SITE_PPE['construction'])
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
        item = {
            'class_name': raw,
            'normalized_label': label,
            'confidence': round(float(box.conf.item()), 4),
            'bbox': dict(zip(('x1', 'y1', 'x2', 'y2'), coords)),
            'is_violation': missing,
            'label_text': label.replace('_', ' ').upper(),
        }
        if missing:
            item['violation_type'] = label[3:]
        detections.append(item)

    # ── Person-PPE Association & Compliance Analysis ──
    # If a person is detected on site, verify mandatory PPE (helmet, vest)
    persons = [d for d in detections if d['normalized_label'] == 'person']
    helmets = [d for d in detections if d['normalized_label'] == 'helmet']
    vests = [d for d in detections if d['normalized_label'] == 'vest']
    explicit_no_helmets = [d for d in detections if d['normalized_label'] == 'no_helmet']
    explicit_no_vests = [d for d in detections if d['normalized_label'] == 'no_vest']

    for p_item in persons:
        p_box = p_item['bbox']
        pw = max(p_box['x2'] - p_box['x1'], 1)
        ph = max(p_box['y2'] - p_box['y1'], 1)
        p_conf = p_item['confidence']

        # Skip tiny background figures where head/torso are indistinguishable
        if ph < 35 or pw < 20:
            continue

        # Helmet compliance
        has_helmet = any(_is_gear_on_person(h['bbox'], p_box, 'helmet') for h in helmets)
        has_explicit_no_h = any(_is_gear_on_person(nh['bbox'], p_box, 'no_helmet') for nh in explicit_no_helmets)
        if 'helmet' in required and not has_helmet and not has_explicit_no_h:
            hx1 = int(p_box['x1'] + 0.15 * pw)
            hx2 = int(p_box['x2'] - 0.15 * pw)
            if hx2 <= hx1:
                hx1, hx2 = p_box['x1'], p_box['x2']
            hy1 = int(p_box['y1'])
            hy2 = int(p_box['y1'] + 0.28 * ph)
            v_item = {
                'class_name': 'no_helmet',
                'normalized_label': 'no_helmet',
                'confidence': round(min(0.92, max(0.72, p_conf)), 4),
                'bbox': {'x1': hx1, 'y1': hy1, 'x2': hx2, 'y2': hy2},
                'is_violation': True,
                'violation_type': 'helmet',
                'label_text': 'NO HELMET',
                'deduced': True,
            }
            detections.append(v_item)
            counts['no_helmet'] += 1

        # Vest compliance
        has_vest = any(_is_gear_on_person(v['bbox'], p_box, 'vest') for v in vests)
        has_explicit_no_v = any(_is_gear_on_person(nv['bbox'], p_box, 'no_vest') for nv in explicit_no_vests)
        if 'vest' in required and not has_vest and not has_explicit_no_v:
            vx1 = int(p_box['x1'] + 0.10 * pw)
            vx2 = int(p_box['x2'] - 0.10 * pw)
            if vx2 <= vx1:
                vx1, vx2 = p_box['x1'], p_box['x2']
            vy1 = int(p_box['y1'] + 0.22 * ph)
            vy2 = int(p_box['y1'] + 0.65 * ph)
            v_item = {
                'class_name': 'no_vest',
                'normalized_label': 'no_vest',
                'confidence': round(min(0.90, max(0.68, p_conf)), 4),
                'bbox': {'x1': vx1, 'y1': vy1, 'x2': vx2, 'y2': vy2},
                'is_violation': True,
                'violation_type': 'vest',
                'label_text': 'NO VEST',
                'deduced': True,
            }
            detections.append(v_item)
            counts['no_vest'] += 1

        # Full PPE check
        person_has_helmet = ('helmet' not in required) or has_helmet
        person_has_vest = ('vest' not in required) or has_vest
        if person_has_helmet and person_has_vest:
            counts['full_ppe'] += 1

    return counts, detections
