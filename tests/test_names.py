from name2smiles.names import name_quality


def test_plain_name_is_accepted():
    accepted, reason = name_quality("quinoline", num_components=1)
    assert accepted is True
    assert reason == "ok"


def test_simple_salt_is_accepted():
    accepted, _ = name_quality(
        "2-aminoethan-1-ol;hydrochloride", num_components=2
    )
    assert accepted is True


def test_solvate_is_rejected():
    accepted, reason = name_quality("aspirin;ethane", num_components=2)
    assert accepted is False
    assert reason == "solvent_or_gas_component"


def test_three_component_name_is_rejected():
    accepted, reason = name_quality(
        "copper;copper(1+);phosphoric acid", num_components=3
    )
    assert accepted is False
    assert reason == "more_than_two_components"
