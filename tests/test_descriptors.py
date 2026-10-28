from name2smiles.descriptors import describe_molecule


def test_quinoline():
    desc = describe_molecule("c1ccc2ncccc2c1")
    assert desc is not None
    assert desc["formula"] == "C9H7N"
    assert desc["heavy_atoms"] == 10
    assert desc["ring_count"] == 2
    assert desc["element_class"] == "CHNO"
    assert desc["inchi_key"] == "SMWDFEZZVXVKRB-UHFFFAOYSA-N"


def test_aspirin_functional_groups():
    desc = describe_molecule("CC(=O)Oc1ccccc1C(=O)O")
    assert desc is not None
    assert desc["formula"] == "C9H8O4"
    assert "ester" in desc["functional_groups"]
    assert "carboxylic_acid" in desc["functional_groups"]


def test_salt_and_components():
    desc = describe_molecule("CC(=O)[O-].[Na+]")
    assert desc is not None
    assert desc["num_components"] == 2
    assert desc["is_salt"] is True
    assert desc["charge"] == 0


def test_stereocenter():
    desc = describe_molecule("C[C@@H](N)C(=O)O")
    assert desc is not None
    assert desc["defined_stereo_centers"] == 1
    assert desc["stereo_bin"] in {"centers_1_2", "centers_and_double"}


def test_radical_and_isotope():
    radical = describe_molecule("CC1(C)CCCC(C)(C)N1[O]")
    assert radical is not None
    assert radical["is_radical"] is True

    isotope = describe_molecule("[2H]O[2H]")
    assert isotope is not None
    assert isotope["has_isotope"] is True


def test_invalid_smiles():
    assert describe_molecule("C1CC") is None
