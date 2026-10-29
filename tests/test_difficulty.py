from __future__ import annotations

from name2smiles.difficulty import (
    TIER_KEYS,
    name_locant_count,
    name_nesting_depth,
    name_stereo_descriptors,
    score_record,
    tier_for_score,
)


def make_record(**overrides):
    record = {
        "name": "ethanol",
        "heavy_atoms": 3,
        "rings": {
            "count": 0,
            "macrocycle": False,
            "spiro_atoms": 0,
            "bridgehead_atoms": 0,
        },
        "stereo": {"centers": 0, "double_bonds": 0},
        "fragments": ["CCO"],
        "charge": 0,
        "element_class": "CHNO",
        "functional_groups": ["alcohol"],
        "is_salt": False,
        "is_zwitterion": False,
        "is_radical": False,
        "has_isotope": False,
    }
    record.update(overrides)
    return record


def test_name_stereo_descriptors():
    assert name_stereo_descriptors("ethanol") == 0
    assert name_stereo_descriptors("(2S)-2-aminopropanoic acid") == 1
    assert name_stereo_descriptors("(2R,3S)-butane-2,3-diol") == 2
    assert name_stereo_descriptors("(2E,4E)-hexa-2,4-dienoic acid") == 2
    assert (
        name_stereo_descriptors("N-[(Z)-(4-ethylphenyl)methylideneamino]acetamide") == 1
    )


def test_name_nesting_depth():
    assert name_nesting_depth("ethanol") == 0
    assert name_nesting_depth("2-methylpropan-1-ol") == 0
    assert name_nesting_depth("2-[4-[(2S)-2-aminopropanoyl]oxyphenyl]acetic acid") == 3


def test_name_locant_count():
    assert name_locant_count("ethanol") == 0
    assert name_locant_count("2,3-dimethylbutane") == 2
    assert name_locant_count("(2R,3S)-butane-2,3-diol") == 4


def test_tier_boundaries():
    assert tier_for_score(0.0) == "L1"
    assert tier_for_score(11.9) == "L1"
    assert tier_for_score(12.0) == "L2"
    assert tier_for_score(23.9) == "L2"
    assert tier_for_score(24.0) == "L3"
    assert tier_for_score(37.9) == "L3"
    assert tier_for_score(38.0) == "L4"
    assert tier_for_score(51.9) == "L4"
    assert tier_for_score(52.0) == "L5"
    assert tier_for_score(100.0) == "L5"


def test_complex_record_scores_higher():
    simple = score_record(make_record())
    complex_record = score_record(
        make_record(
            name=(
                "(2S,3R,4S)-2,3,4-trihydroxy-5-[4-[(2E)-3-phenylprop-2-"
                "enoyl]oxyphenyl]pentanoic acid"
            ),
            heavy_atoms=40,
            rings={
                "count": 3,
                "macrocycle": False,
                "spiro_atoms": 1,
                "bridgehead_atoms": 1,
            },
            stereo={"centers": 3, "double_bonds": 2},
            fragments=["CCO", "CCN", "CCCl"],
            charge=1,
            element_class="metal",
            functional_groups=["azide", "isocyanate"],
            is_salt=True,
            is_zwitterion=True,
            is_radical=True,
            has_isotope=True,
        )
    )
    assert complex_record.score > simple.score
    assert complex_record.score <= 100.0
    assert complex_record.tier in TIER_KEYS


def test_isotope_bonus():
    plain = score_record(make_record(heavy_atoms=20))
    labeled = score_record(make_record(heavy_atoms=20, has_isotope=True))
    assert labeled.score == plain.score + 10.0


def test_score_rounding_at_half_tenth():
    record = make_record(
        name="1-(2-ethylhexyl)-2-methyl-3-(4-morpholin-4-ylbutyl)guanidine",
        heavy_atoms=23,
        rings={"count": 1},
        stereo={"centers": 1, "double_bonds": 0},
    )
    assert score_record(record).score == 14.6


def test_score_is_capped():
    record = score_record(
        make_record(
            name="(2S,3R,4S,5R,6E,8E)-" + "2,3,4,5,6,7,8,9-" * 8 + "nonanol",
            heavy_atoms=200,
            rings={
                "count": 10,
                "macrocycle": True,
                "spiro_atoms": 3,
                "bridgehead_atoms": 3,
            },
            stereo={"centers": 10, "double_bonds": 10},
            fragments=["CCO", "CCN", "CCCl", "CCBr"],
            charge=2,
            element_class="radioactive",
            functional_groups=[
                "azide",
                "isocyanate",
                "isothiocyanate",
                "allene",
            ],
            is_salt=True,
            is_zwitterion=True,
            is_radical=True,
            has_isotope=True,
        )
    )
    assert record.score == 100.0
    assert record.tier == "L5"


def test_to_dict():
    data = score_record(make_record()).to_dict()
    assert set(data) == {"score", "tier", "label", "components"}
    assert data["tier"] == "L1"
    assert data["label"] == "easy"
    assert "heavy_atoms" in data["components"]
