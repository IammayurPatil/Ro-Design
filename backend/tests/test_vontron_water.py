"""Regression test over every captured Vontron Water Analysis case.

Cases whose Vontron values are still null are skipped, so this stays green until you capture data.
"""
import json

import pytest

from vontron_compare import compare_case, load_cases


@pytest.mark.parametrize("path", load_cases(), ids=lambda p: p.stem)
def test_vontron_water_case(path):
    checked, diffs = compare_case(path)
    if checked == 0:
        pytest.skip("Vontron values not captured yet")
    if diffs and json.loads(path.read_text(encoding="utf-8")).get("knownIssue"):
        pytest.xfail("known issue: " + json.loads(path.read_text(encoding="utf-8"))["knownIssue"])
    assert not diffs, "\n".join(f"{l}: Vontron={v} ours={o}" for l, v, o, _ in diffs)
