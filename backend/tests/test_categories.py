import numpy as np
import pytest

from echotrace import config
from echotrace.tagging.categories import CategoryMap, load_labels, top_k

needs_csv = pytest.mark.skipif(not config.LABELS_FILE.exists(), reason="AudioSet label CSV not downloaded")

FAKE = ["Speech", "Walk, footsteps", "Run", "Thump, thud", "Screaming", "Glass"]


@needs_csv
def test_all_configured_category_names_resolve():
    labels = load_labels()
    assert len(labels) == 527
    cmap = CategoryMap(labels)
    for cat, names in config.CATEGORIES.items():
        assert len(cmap.indices[cat]) == len(names), cat


def test_per_category_thresholds_are_sane():
    for cat in config.CATEGORIES:
        on, off = config.thresholds(cat)
        assert 0 < off < on < 1, cat
    assert config.thresholds("IMPACT") == config.CATEGORY_THRESHOLDS["IMPACT"]
    assert config.thresholds("GLASS") == (config.ON_THRESHOLD, config.OFF_THRESHOLD)
    assert set(config.CATEGORY_THRESHOLDS) <= set(config.CATEGORIES)


def test_typo_fails_loudly_with_suggestion():
    with pytest.raises(ValueError) as e:
        CategoryMap(FAKE, {"FOOTSTEPS": ["Walk, footstep"]})
    msg = str(e.value)
    assert "Walk, footstep" in msg and "did you mean" in msg and "Walk, footsteps" in msg


def test_category_score_is_max_over_members():
    cmap = CategoryMap(FAKE, {"FOOTSTEPS": ["Walk, footsteps", "Run"], "GLASS": ["Glass"]})
    p = np.array([0.9, 0.2, 0.6, 0.0, 0.0, 0.05])
    assert cmap.scores(p) == pytest.approx({"FOOTSTEPS": 0.6, "GLASS": 0.05})
    assert cmap.best_label(p, "FOOTSTEPS") == ("Run", pytest.approx(0.6))


def test_top_k_sorted():
    p = np.array([0.1, 0.5, 0.3, 0.9, 0.0, 0.2])
    assert [l for l, _ in top_k(p, FAKE, 3)] == ["Thump, thud", "Walk, footsteps", "Run"]
