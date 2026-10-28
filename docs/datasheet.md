# Name2SMILES Dataset Datasheet

## Dataset name

Name2SMILES Dataset, version 0.

## Purpose

Support evaluation of language models on open-ended name-to-SMILES
generation. Each item pairs a molecule name with a reference structure,
descriptor metadata, 2D depictions, and coordinate files. The same records
can later support image-to-SMILES experiments.

## Collection

- Source: PubChem PUG REST.
- Candidate pool: 20,000 random CIDs in the range 1 to 180,000,000.
- Filtering: valid RDKit structure, non-empty IUPAC name, at most 120 heavy
  atoms, at most four fragments, no radioactive elements, no polymers.
- Selection: coverage-aware greedy selection across element class,
  heavy-atom count, ring count, stereochemistry, charge, functional groups,
  and a small set of structural flags.
- Target size: 1,500 records.
- Collection date: 2026-10-28.
- Result: 1,500 unique records, 1,500 unique InChIKeys, 968 non-empty Murcko
  scaffolds, and 250 acyclic records.

## Coverage summary

- Element classes: 765 CHNO, 305 halogen, 287 S/P, 82 B/Si/Se/As, 61 metal.
- Heavy atoms: 121 records with 1-10, 453 with 11-20, 551 with 21-30, 300
  with 31-50, 70 with 51-100, and 5 with more than 100.
- Rings: 250 acyclic, 450 monocyclic, 400 bicyclic, 300 with 3-4 rings, 100
  with 5 or more.
- Stereochemistry: 550 without stereo, 600 with 1-2 centers, 200 with 3 or
  more centers, 100 with double-bond stereo only, 50 with both.
- Charge: 1245 neutral, 100 positive, 100 negative, 55 zwitterionic.
- Flags: 156 multi-component, 150 salts, 77 bridgehead, 70 spiro, 62
  macrocyclic, 61 metal-containing, 41 isotope-labeled, 3 radical.
- Functional groups include ether, amide, alcohol, alkene, ester, carboxylic
  acid, lactam, sulfone, thioether, carbamate, amidine, nitrile, silane,
  boronate ester, allene, and others. See `coverage.md` for the full table.
- Images: 1500 records have all six 2D variants.
- Coordinates: 1500 2D SDF, 1068 PubChem 3D SDF, 365 RDKit ETKDG 3D SDF.
  67 records have no 3D file, mostly large or metal-containing structures.

## Mini test set

A 100-record subset is available in `data/mini_100.jsonl` for quick,
low-cost evaluation. Records keep their original IDs, images, and coordinate
paths.

- Difficulty score: a weighted sum of name length, numeric locants, bracket
  nesting, stereo descriptors, heavy atoms, rings, stereo centers,
  double-bond stereo, fragments, charge, element class, salt, uncommon
  functional groups, macrocycle, spiro, bridgehead, isotope, and radical
  flags.
- Tiers: L1 easy 25, L2 moderate 30, L3 hard 20, L4 very hard 15, L5
  extreme 10. Score bounds are 12, 24, 38, and 52.
- Coverage: all 53 functional groups present in v0 are represented. The
  element, heavy-atom, ring, stereo, and charge distributions closely follow
  the full set, with slight enrichment of the rarest element classes. The
  set has 84 unique non-empty Murcko scaffolds and 16 acyclic records.
- Selection: the two easiest and two hardest records are seeded first, then
  a coverage-aware greedy pass fills the tier quotas with a scaffold cap.
- Regenerate with `python scripts/select_mini_dataset.py --n 100`.
- Report: `docs/mini_100.md`.

The score is a heuristic, not a calibrated difficulty measure. It is meant
to make quick tests cover a range of expected difficulty, not to predict
model failure.

## Name policy

Version 0 uses PubChem `IUPACName`. Names with more than two semicolon-
separated components are removed. Solvates and gas components such as
ethane, methane, water, and molecular hydrogen are removed. Simple
two-component salts with common counterions are retained.

## Structure processing

- Reference SMILES: PubChem `SMILES`, parsed and canonicalized by RDKit.
- Connectivity SMILES: RDKit canonical SMILES after removing stereochemistry.
- Identity: InChIKey.
- Descriptors: RDKit 2025.09.1.
- Functional groups: a curated SMARTS library. This is a coverage aid, not a
  definitive chemical classification.

## Depictions

- RDKit clean: 512 x 512 PNG and SVG, with stereochemistry annotations.
- RDKit no-stereo: 512 x 512 PNG with stereochemistry removed.
- RDKit atom-index: 512 x 512 PNG with atom indices.
- RDKit low-resolution: 128 x 128 PNG.
- PubChem: 500 x 500 PNG from PUG REST.

## Coordinate files

- RDKit 2D SDF generated from the reference SMILES.
- PubChem 3D SDF when available.
- RDKit ETKDG 3D SDF as a fallback for molecules with at most 80 heavy
  atoms when PubChem has no 3D record.

## Known limitations

- Version 0 contains IUPAC-style names only. Common names and trade names are
  not yet included. A synonym-based heuristic was tested but not applied,
  because it selected incorrect salt forms for a few records.
- Names have not been round-tripped through OPSIN. Some PubChem names may be
  non-preferred or ambiguous.
- No negative controls or post-cutoff contamination-resistant subset yet.
- The mini-set difficulty score is a heuristic based on name and structure
  complexity. It has not been calibrated against model accuracy.
- The mini set inherits all v0 name and structure limitations. It is a
  subset, not a separate curation pass.
- No manual review of all 1,500 records yet.
- Some multi-component salts and organometallic records may be difficult to
  depict or embed in 3D.
- The benchmark split is not defined yet.

## Licensing

PubChem computed structure and descriptor data is free to use. Some PubChem
annotations come from third-party sources with separate licenses; version 0
does not redistribute those annotations. The dataset license for this project
is not decided yet.

## Safety

The dataset contains molecular structures and names. It does not contain
synthesis routes, dosages, or experimental procedures. Hazardous or
controlled compounds should be reviewed before public release.
