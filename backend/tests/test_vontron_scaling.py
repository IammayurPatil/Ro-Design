"""Regression test over every captured Vontron Scaling case (uncaptured cases are skipped)."""
import json

import pytest

from vontron_compare_scaling import compare_case, load_cases


@pytest.mark.parametrize("path", load_cases(), ids=lambda p: p.stem)
def test_vontron_scaling_case(path):
    checked, diffs = compare_case(path)
    if checked == 0:
        pytest.skip("Vontron values not captured yet")
    cap = json.loads(path.read_text(encoding="utf-8"))
    if diffs and cap.get("knownIssue"):
        pytest.xfail("known issue: " + cap["knownIssue"])
    assert not diffs, "\n".join(f"{l}: Vontron={v} ours={o}" for l, v, o, _ in diffs)
