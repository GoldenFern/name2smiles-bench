"""Name quality rules for the name-to-SMILES dataset."""

from __future__ import annotations

SOLVENTS_AND_GASES = {
    "water",
    "hydrate",
    "molecular hydrogen",
    "hydrogen",
    "ethane",
    "methane",
    "propane",
    "butane",
    "pentane",
    "hexane",
    "heptane",
    "benzene",
    "toluene",
    "xylene",
    "methanol",
    "ethanol",
    "propan-2-ol",
    "acetone",
    "dichloromethane",
    "chloroform",
    "oxolane",
    "tetrahydrofuran",
    "acetonitrile",
    "dimethyl sulfoxide",
    "diethyl ether",
    "ethyl acetate",
    "carbon monoxide",
    "carbon dioxide",
}

COMMON_COUNTERIONS = {
    "hydrochloride",
    "hydrobromide",
    "hydroiodide",
    "sodium",
    "potassium",
    "calcium",
    "magnesium",
    "ammonium",
    "acetate",
    "citrate",
    "fumarate",
    "maleate",
    "tartrate",
    "sulfate",
    "phosphate",
    "nitrate",
    "chloride",
    "bromide",
    "iodide",
    "mesylate",
    "tosylate",
    "trifluoroacetate",
}


def _components(name: str) -> list[str]:
    return [part.strip().casefold() for part in name.split(";")]


def name_quality(name: str, *, num_components: int) -> tuple[bool, str]:
    """Return (accepted, reason) for a PubChem IUPAC-style name."""
    if not name or not (3 <= len(name) <= 200):
        return False, "length"
    if any(character in name for character in "?~|<>"):
        return False, "bad_character"
    if "\n" in name or "\r" in name:
        return False, "newline"
    if ";" not in name:
        return True, "ok"

    parts = _components(name)
    if len(parts) > 2:
        return False, "more_than_two_components"
    if any(part in SOLVENTS_AND_GASES for part in parts):
        return False, "solvent_or_gas_component"
    if parts[1] not in COMMON_COUNTERIONS:
        return False, "unknown_counterion"
    if num_components > 4:
        return False, "too_many_fragments"
    return True, "ok"
