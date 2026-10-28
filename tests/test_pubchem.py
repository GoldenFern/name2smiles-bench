from name2smiles.pubchem import PROPERTIES, _property_url


def test_property_url_contains_cids_and_properties():
    url = _property_url([2244, 7047])
    assert "2244,7047" in url
    assert "IUPACName" in url
    assert "ConnectivitySMILES" in url
    assert PROPERTIES in url
