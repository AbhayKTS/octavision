import unittest
from site_profiles import process_boxes, supported

class Value:
    def __init__(self, value): self.value = value
    def item(self): return self.value
    def tolist(self): return self.value

class Box:
    def __init__(self, index):
        self.cls = Value(index)
        self.conf = Value(.9)
        self.xyxy = [Value([0, 0, 20, 20])]

class SiteProfileTests(unittest.TestCase):
    def test_road_filters_chemical_and_keeps_explicit_missing_gloves(self):
        counts, detections = process_boxes([Box(0), Box(1), Box(2)], {0: 'person', 1: 'chemical_suit', 2: 'no-gloves'}, 'road')
        self.assertEqual([x['normalized_label'] for x in detections], ['person', 'no_gloves'])
        self.assertTrue(detections[1]['is_violation'])
        self.assertEqual(counts['no_gloves'], 1)

    def test_person_alone_does_not_create_a_violation(self):
        _, detections = process_boxes([Box(0)], {0: 'person'}, 'construction')
        self.assertFalse(detections[0]['is_violation'])

    def test_public_model_class_aliases(self):
        caps = supported({0: 'Hard_hat', 1: 'No-Helmet', 2: 'Glove', 3: 'No-Glove', 4: 'Vest', 5: 'No-Vest', 6: 'Worker'}, 'road')
        for item in ('helmet', 'vest', 'gloves'):
            self.assertEqual(caps[item], {'present': True, 'missing': True})

    def test_positive_only_model_does_not_claim_missing_support(self):
        capabilities = supported({0: 'person', 1: 'gloves'}, 'chemical')
        self.assertTrue(capabilities['gloves']['present'])
        self.assertFalse(capabilities['gloves']['missing'])
        self.assertFalse(capabilities['respirator']['present'])

if __name__ == '__main__': unittest.main()
