"""Same protocol vectors are committed in the source and legacy patch repositories."""
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
from core.providers.answers import _number

class ProtocolVectors(unittest.TestCase):
    def test_shared_numeric_vectors(self):
        for case in json.loads((ROOT/'tests/fixtures/decision-numbers-v1.json').read_text()):
            with self.subTest(value=str(case['input'])[:50]):
                self.assertEqual(_number(case['input']),case['expected'])
