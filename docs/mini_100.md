# Mini Test Set

Records: **100** selected from **1500** benchmark records.

The set is a difficulty-graded subset. Difficulty is a heuristic weighted score built from name complexity and structure complexity. It is meant for quick model comparison, not for absolute claims about model capability. The extremes of the score range are seeded first; the remaining slots are filled by coverage.

## Difficulty ladder

| Tier | Label | Score range | Quota | Offset | Selected | Score min | Score median | Score max | Heavy atoms median | Name length median |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L1 | easy | 0-<12 | 25 | 0 | 25 | 1.7 | 10.3 | 11.9 | 15 | 40 |
| L2 | moderate | 12-<24 | 30 | 25 | 30 | 14.6 | 20.05 | 23.9 | 21 | 63.5 |
| L3 | hard | 24-<38 | 20 | 55 | 20 | 24.1 | 29.45 | 37.6 | 25.5 | 82.5 |
| L4 | very_hard | 38-<52 | 15 | 75 | 15 | 38 | 42.3 | 51.4 | 30 | 115 |
| L5 | extreme | >=52 | 10 | 90 | 10 | 53.5 | 63.75 | 72.5 | 43 | 172 |

Mean difficulty: **27.1** in the mini set vs **25.8** in the full set. Median: **22.6** vs **23.0**. Score range: **1.7-72.5** in the mini set vs **1.7-72.5** in the full set.

## Score composition

| Component | Component cap | Mean contribution in mini set |
|---|---:|---:|
| name_length | 10 | 4.06 |
| name_locants | 10 | 2.98 |
| name_nesting | 8 | 1.46 |
| name_stereo | 10 | 1.68 |
| heavy_atoms | 12 | 5.07 |
| rings | 8 | 3.62 |
| stereo_centers | 8 | 2.45 |
| double_bond_stereo | 4 | 0.42 |
| fragments | 6 | 0.36 |
| charge | 6 | 0.64 |
| element_class | 12 | 1.86 |
| salt | 2 | 0.36 |
| uncommon_group | 4 | 0.32 |
| macrocycle | 6 | 0.42 |
| spiro | 4 | 0.36 |
| bridgehead | 4 | 0.24 |
| isotope | 10 | 0.70 |
| radical | 10 | 0.10 |

Component caps sum to more than 100 because the final score is clamped at 100.


## Coverage

Percentages use the full set and the mini set as their denominators.

### Element class

| Bin | Full set | Mini set |
|---|---:|---:|
| CHNO | 765 (51.0%) | 48 (48.0%) |
| halogen | 305 (20.3%) | 20 (20.0%) |
| S_P | 287 (19.1%) | 20 (20.0%) |
| B_Si_Se_As | 82 (5.5%) | 7 (7.0%) |
| metal | 61 (4.1%) | 5 (5.0%) |

### Heavy-atom bin

| Bin | Full set | Mini set |
|---|---:|---:|
| 1-10 | 121 (8.1%) | 8 (8.0%) |
| 11-20 | 453 (30.2%) | 30 (30.0%) |
| 21-30 | 551 (36.7%) | 37 (37.0%) |
| 31-50 | 300 (20.0%) | 20 (20.0%) |
| 51-100 | 70 (4.7%) | 4 (4.0%) |
| 100+ | 5 (0.3%) | 1 (1.0%) |

### Ring count

| Bin | Full set | Mini set |
|---|---:|---:|
| 0 | 250 (16.7%) | 16 (16.0%) |
| 1 | 450 (30.0%) | 30 (30.0%) |
| 2 | 400 (26.7%) | 27 (27.0%) |
| 3-4 | 300 (20.0%) | 20 (20.0%) |
| 5+ | 100 (6.7%) | 7 (7.0%) |

### Stereo bin

| Bin | Full set | Mini set |
|---|---:|---:|
| none | 550 (36.7%) | 37 (37.0%) |
| centers_1_2 | 600 (40.0%) | 40 (40.0%) |
| centers_3plus | 200 (13.3%) | 13 (13.0%) |
| double_only | 100 (6.7%) | 7 (7.0%) |
| centers_and_double | 50 (3.3%) | 3 (3.0%) |

### Charge bin

| Bin | Full set | Mini set |
|---|---:|---:|
| neutral | 1245 (83.0%) | 82 (82.0%) |
| negative | 100 (6.7%) | 7 (7.0%) |
| positive | 100 (6.7%) | 7 (7.0%) |
| zwitterion | 55 (3.7%) | 4 (4.0%) |

### Structural flags

| Flag | Full set | Mini set |
|---|---:|---:|
| Multi-component | 156 (10.4%) | 18 (18.0%) |
| Salt | 150 (10.0%) | 18 (18.0%) |
| Metal-containing | 61 (4.1%) | 5 (5.0%) |
| Zwitterion | 55 (3.7%) | 4 (4.0%) |
| Radical | 3 (0.2%) | 1 (1.0%) |
| Isotope-labeled | 41 (2.7%) | 7 (7.0%) |
| Macrocycle | 62 (4.1%) | 7 (7.0%) |
| Spiro | 70 (4.7%) | 9 (9.0%) |
| Bridgehead | 77 (5.1%) | 6 (6.0%) |

### Functional groups

The floor is a minimum coverage target; counts can exceed it.

| Group | Full set | Mini set | Floor |
|---|---:|---:|---:|
| ether | 719 (47.9%) | 53 | 2 |
| amine_secondary | 598 (39.9%) | 28 | 2 |
| amide | 525 (35.0%) | 21 | 2 |
| alcohol | 457 (30.5%) | 38 | 2 |
| amine_tertiary | 445 (29.7%) | 27 | 2 |
| alkene | 424 (28.3%) | 32 | 2 |
| aniline | 310 (20.7%) | 20 | 2 |
| ester | 278 (18.5%) | 23 | 2 |
| amine_primary | 218 (14.5%) | 15 | 2 |
| aryl_halide | 195 (13.0%) | 8 | 2 |
| imine | 169 (11.3%) | 13 | 2 |
| carboxylic_acid | 151 (10.1%) | 10 | 2 |
| lactam | 150 (10.0%) | 5 | 2 |
| alkyl_halide | 148 (9.9%) | 9 | 2 |
| ketone | 145 (9.7%) | 11 | 2 |
| sulfone | 98 (6.5%) | 8 | 1 |
| thioether | 95 (6.3%) | 4 | 1 |
| carbamate | 84 (5.6%) | 8 | 1 |
| amidine | 83 (5.5%) | 9 | 1 |
| trifluoromethyl | 77 (5.1%) | 5 | 1 |
| urea | 64 (4.3%) | 2 | 1 |
| nitrile | 62 (4.1%) | 3 | 1 |
| quaternary_ammonium | 61 (4.1%) | 2 | 1 |
| silane | 54 (3.6%) | 5 | 1 |
| guanidine | 52 (3.5%) | 6 | 1 |
| sulfonamide | 49 (3.3%) | 5 | 1 |
| lactone | 45 (3.0%) | 6 | 1 |
| phenol | 45 (3.0%) | 1 | 1 |
| hydrazine | 40 (2.7%) | 5 | 1 |
| alkyne | 34 (2.3%) | 5 | 1 |
| hydrazone | 32 (2.1%) | 2 | 1 |
| phosphine_oxide | 31 (2.1%) | 3 | 1 |
| aldehyde | 30 (2.0%) | 2 | 1 |
| epoxide | 20 (1.3%) | 2 | 1 |
| thiol | 20 (1.3%) | 1 | 1 |
| boronate_ester | 20 (1.3%) | 2 | 1 |
| phosphate | 19 (1.3%) | 1 | 1 |
| sulfonate | 18 (1.2%) | 4 | 1 |
| sulfoxide | 17 (1.1%) | 1 | 1 |
| oxime | 16 (1.1%) | 2 | 1 |
| phosphine | 16 (1.1%) | 2 | 1 |
| anhydride | 15 (1.0%) | 1 | 1 |
| disulfide | 15 (1.0%) | 1 | 1 |
| nitroso | 15 (1.0%) | 1 | 1 |
| n_oxide | 15 (1.0%) | 1 | 1 |
| nitro | 15 (1.0%) | 1 | 1 |
| carbonate | 15 (1.0%) | 1 | 1 |
| boronic_acid | 13 (0.9%) | 2 | 1 |
| acid_halide | 9 (0.6%) | 1 | 1 |
| isocyanate | 9 (0.6%) | 1 | 1 |
| allene | 5 (0.3%) | 1 | 1 |
| siloxane | 4 (0.3%) | 1 | 1 |
| isothiocyanate | 3 (0.2%) | 1 | 1 |

Functional-group coverage: **53/53** groups.

## Scaffold diversity

- Unique non-empty Murcko scaffolds: **84** across 84 records.
- Acyclic records (empty scaffold): **16**.

## Selected records

Names longer than 90 characters are truncated here. Full names and SMILES are in the JSONL and CSV files.

| Mini ID | Tier | Score | Dataset ID | Name | Formula | Heavy atoms | Rings | Element class |
|---|---|---:|---|---|---|---:|---:|---|
| M2S-000001 | L1 | 1.7 | N2S-000002 | propan-2-yl pent-3-enoate | C8H14O2 | 10 | 0 | CHNO |
| M2S-000002 | L1 | 1.9 | N2S-001017 | 3-hydroxyhept-3-en-2-one | C7H12O2 | 9 | 0 | CHNO |
| M2S-000003 | L1 | 5.6 | N2S-000653 | N,N',N",N"'-tetrabutylmethanetetramine | C17H40N4 | 21 | 0 | CHNO |
| M2S-000004 | L1 | 6.7 | N2S-000201 | 2-methoxy-3,3-dimethyloxetane | C6H12O2 | 8 | 1 | CHNO |
| M2S-000005 | L1 | 6.9 | N2S-001216 | nonadecyl decanoate | C29H58O2 | 31 | 0 | CHNO |
| M2S-000006 | L1 | 7.3 | N2S-001004 | 1-(2-fluoroethyl)cyclooctane-1-carbaldehyde | C11H19FO | 13 | 1 | halogen |
| M2S-000007 | L1 | 8.2 | N2S-001351 | 6-(oxiran-2-yloxy)hex-2-yn-1-ol | C8H12O3 | 11 | 1 | CHNO |
| M2S-000008 | L1 | 8.3 | N2S-000999 | 2-(2-propan-2-ylidenecyclopentyl)ethanol | C10H18O | 11 | 1 | CHNO |
| M2S-000009 | L1 | 8.6 | N2S-001381 | 6-methoxy-3-methylpyrazolo[1,5-a]pyrimidine | C8H9N3O | 12 | 2 | CHNO |
| M2S-000010 | L1 | 9.1 | N2S-001284 | 1,3-dimethylurea cyanide | C4H8N3O- | 8 | 0 | CHNO |
| M2S-000011 | L1 | 9.8 | N2S-001133 | 2-but-3-enylthiolan-2-ol | C8H14OS | 10 | 1 | S_P |
| M2S-000012 | L1 | 10.1 | N2S-000555 | N'-hydroxy-2-quinolin-6-ylethanimidamide | C11H11N3O | 15 | 2 | CHNO |
| M2S-000013 | L1 | 10.3 | N2S-000519 | 5-acetyl-2-(2-methoxyanilino)benzoic acid | C16H15NO4 | 21 | 2 | CHNO |
| M2S-000014 | L1 | 10.7 | N2S-001253 | 3-methyl-4-(6-methylheptoxy)-4-oxobut-2-enoate | C13H21O4- | 17 | 0 | CHNO |
| M2S-000015 | L1 | 10.8 | N2S-000006 | (3S)-icos-4-en-1-yn-3-ol | C20H36O | 21 | 0 | CHNO |
| M2S-000016 | L1 | 10.8 | N2S-001369 | 8-carbonochloridoyloxy-7-methyloct-2-ynoic acid | C10H13ClO4 | 15 | 0 | halogen |
| M2S-000017 | L1 | 11.1 | N2S-000901 | 4-butyl-2-methyl-3,5-dioxo-1,2,4-triazine-6-carboxylic acid | C9H13N3O4 | 16 | 1 | CHNO |
| M2S-000018 | L1 | 11.3 | N2S-000899 | 2-(1-isocyanatocyclobutyl)benzene-1,4-diol | C11H11NO3 | 15 | 2 | CHNO |
| M2S-000019 | L1 | 11.3 | N2S-001201 | 4-prop-2-enoyloxy-4-sulfanylbutane-1-sulfonic acid | C7H12O5S2 | 14 | 0 | S_P |
| M2S-000020 | L1 | 11.3 | N2S-001220 | N-(6-decoxypyridazin-3-yl)carbamate | C15H24N3O3- | 21 | 1 | CHNO |
| M2S-000021 | L1 | 11.5 | N2S-000722 | ethyl 2-cyano-2-[1-(2-hydroxyethyl)pyrimidin-4-ylidene]acetate | C11H13N3O3 | 17 | 1 | CHNO |
| M2S-000022 | L1 | 11.6 | N2S-000833 | ethyl 4-acetyl-2-(2-ethylbutanoylamino)-5-methylfuran-3-carboxylate | C16H23NO5 | 22 | 1 | CHNO |
| M2S-000023 | L1 | 11.6 | N2S-001344 | 3,3-dimethyldithian-4-ol | C6H12OS2 | 9 | 1 | S_P |
| M2S-000024 | L1 | 11.7 | N2S-000964 | 5,7,7-trimethyl-2,3,4,8-tetrahydrooxocin-3-ol | C10H18O2 | 12 | 1 | CHNO |
| M2S-000025 | L1 | 11.9 | N2S-001496 | 2-(didodecylamino)ethyl imidazole-1-carboxylate | C30H57N3O2 | 35 | 1 | CHNO |
| M2S-000026 | L2 | 14.6 | N2S-000857 | 1-(2-ethylhexyl)-2-methyl-3-(4-morpholin-4-ylbutyl)guanidine | C18H38N4O | 23 | 1 | CHNO |
| M2S-000027 | L2 | 15.1 | N2S-000643 | trimethyl(1,1,2,2,2-pentafluoroethyl)plumbane | C5H9F5Pb | 11 | 0 | metal |
| M2S-000028 | L2 | 16.2 | N2S-000179 | (4-nitrophenyl)methyl N-aminocarbamate;hydrochloride | C8H10ClN3O4 | 16 | 1 | halogen |
| M2S-000029 | L2 | 16.2 | N2S-001463 | (4E)-4-(fluoromethylidene)-3-methylpiperidine-3-carboxylic acid | C8H12FNO2 | 12 | 1 | halogen |
| M2S-000030 | L2 | 17 | N2S-000923 | N-(1-amino-2,4-dimethylpentan-2-yl)-2-(1,3,5-trimethylpyrazol-4-yl)oxyacetamide | C15H28N4O2 | 21 | 1 | CHNO |
| M2S-000031 | L2 | 17.5 | N2S-000830 | 3-anilino-1-propan-2-yl-4-(4-propoxyphenyl)pyrrole-2,5-dione | C22H24N2O3 | 27 | 3 | CHNO |
| M2S-000032 | L2 | 17.6 | N2S-001422 | 2-chloro-6-deuterio-5-fluoropyridine-3-carbaldehyde | C6H3ClFNO | 10 | 1 | halogen |
| M2S-000033 | L2 | 18.5 | N2S-001377 | bis(2-cyclohexylethynoxy)-bis(ethenyl)silane | C20H28O2Si | 23 | 2 | B_Si_Se_As |
| M2S-000034 | L2 | 18.6 | N2S-001202 | 4-[dimethyl(trimethylsilyloxy)silyl]butylboronic acid | C9H25BO3Si2 | 15 | 0 | B_Si_Se_As |
| M2S-000035 | L2 | 19.1 | N2S-000377 | N-(2-fluorophenyl)-N'-(furan-2-ylmethyl)-N'-(oxolan-2-ylmethyl)oxamide | C18H19FN2O4 | 25 | 3 | halogen |
| M2S-000036 | L2 | 19.1 | N2S-000443 | (1S,5S)-3-ethylidenebicyclo[3.2.0]heptane | C9H14 | 9 | 2 | CHNO |
| M2S-000037 | L2 | 19.2 | N2S-000936 | N-(3-aminopropyl)-N-benzyl-4-fluorobenzenesulfonamide;hydrochloride | C16H20ClFN2O2S | 23 | 2 | S_P |
| M2S-000038 | L2 | 19.7 | N2S-000199 | methyl 4-[[[4-(7-methoxyheptoxy)benzoyl]amino]carbamoyl]benzoate | C24H30N2O6 | 32 | 2 | CHNO |
| M2S-000039 | L2 | 19.9 | N2S-001035 | [(E)-4-isothiocyanatobut-1-enyl]sulfinylcyclopropane | C8H11NOS2 | 12 | 1 | S_P |
| M2S-000040 | L2 | 19.9 | N2S-001076 | 3-[hexadecyl-(4-methoxy-6-methyl-1,3,5-triazin-2-yl)amino]butanoic acid | C25H46N4O3 | 32 | 1 | CHNO |
| M2S-000041 | L2 | 20.2 | N2S-001322 | 4-(3-aminopyrrolidin-1-yl)-2-(trifluoromethyl)benzonitrile;hydrochloride | C12H13ClF3N3 | 19 | 2 | halogen |
| M2S-000042 | L2 | 20.3 | N2S-000355 | 2-methyl-2-[(4-methyl-2-oxo-3H-1,3-thiazol-5-yl)sulfonylamino]pentanoic acid | C10H16N2O5S2 | 19 | 1 | S_P |
| M2S-000043 | L2 | 20.7 | N2S-000408 | 2-[(E)-[1-amino-2-(azepan-1-yl)ethylidene]amino]oxy-N-(2-methylbutan-2-yl)acetamide | C15H30N4O2 | 21 | 1 | CHNO |
| M2S-000044 | L2 | 21.1 | N2S-000661 | [(3S)-2,5-dioxo-3-pyrrolidin-1-yloxolan-3-yl] hydrogen carbonate | C9H11NO6 | 16 | 2 | CHNO |
| M2S-000045 | L2 | 21.7 | N2S-000183 | dimethoxy-(methoxymethoxy)-[2-(2-methyloxasilinan-2-yl)ethyl]silane | C11H26O5Si2 | 18 | 1 | B_Si_Se_As |
| M2S-000046 | L2 | 21.7 | N2S-000702 | [(Z)-[1-methyl-3-(3-methylbutoxymethyl)imidazol-2-ylidene]methyl]-oxoazanium | C11H20N3O2+ | 16 | 1 | CHNO |
| M2S-000047 | L2 | 21.8 | N2S-000203 | (5-phenyl-1,3,4-thiadiazol-2-yl)boronic acid | C8H7BN2O2S | 14 | 2 | B_Si_Se_As |
| M2S-000048 | L2 | 22.4 | N2S-000763 | didodecyl 2,5-bis(4-aminophenoxy)benzene-1,4-dicarboxylate | C44H64N2O6 | 52 | 3 | CHNO |
| M2S-000049 | L2 | 22.4 | N2S-000846 | 1-(3-butoxypropyl)-3-ethyl-2-[[1-(2-methoxyethyl)cyclobutyl]methyl]guanidine;hydroiodide | C18H38IN3O2 | 24 | 1 | halogen |
| M2S-000050 | L2 | 22.5 | N2S-000110 | methyl N-(3-methyl-2-tributylstannylbutan-2-yl)oxysulfonylcarbamate | C19H41NO5SSn | 27 | 0 | metal |
| M2S-000051 | L2 | 22.7 | N2S-000067 | 1,4-dioxaspiro[4.21]hexacosan-16-one | C24H44O3 | 27 | 2 | CHNO |
| M2S-000052 | L2 | 23.3 | N2S-000362 | sodium N-oxido-N-piperidin-1-ylnitrous amide | C5H10N3NaO2 | 11 | 1 | metal |
| M2S-000053 | L2 | 23.6 | N2S-000868 | 2-[(5-cyano-2-fluorophenyl)methyl]-1-(2-thiophen-2-ylethyl)guanidine;hydroiodide | C15H16FIN4S | 22 | 2 | S_P |
| M2S-000054 | L2 | 23.7 | N2S-001062 | [[tert-butyl(2-methoxyethyl)amino]-hydroxyamino]-(3-carboxycyclopentyl)oxy-oxoazanium | C13H26N3O6+ | 22 | 1 | CHNO |
| M2S-000055 | L2 | 23.9 | N2S-001296 | benzo[a]phenazin-7-ium-10-sulfonic acid hydroxide | C16H12N2O4S | 23 | 4 | S_P |
| M2S-000056 | L3 | 24.1 | N2S-001234 | [(Z)-3-hydroxy-3-(oxan-4-yl)-1-(phenoxycarbonylamino)prop-2-enylidene]azanium | C15H19N2O4+ | 21 | 2 | CHNO |
| M2S-000057 | L3 | 24.2 | N2S-000498 | trans-(1S,2S)-3,3-difluorocyclohexane-1,2-diamine;hydrochloride | C6H13ClF2N2 | 11 | 1 | halogen |
| M2S-000058 | L3 | 24.7 | N2S-000864 | tert-butyl N-[1-[N-(3,3-dimethylbutyl)-N'-methylcarbamimidoyl]pyrrolidin-3-yl]carbamate... | C17H35IN4O2 | 24 | 1 | halogen |
| M2S-000059 | L3 | 25.1 | N2S-000357 | N-(4-ethoxy-1,3-benzothiazol-2-yl)-N-(oxolan-2-ylmethyl)cyclopentanecarboxamide | C20H26N2O3S | 26 | 4 | S_P |
| M2S-000060 | L3 | 25.5 | N2S-001274 | 2-acetamido-4-[hydroxy(trideuteriomethyl)phosphoryl]butanoic acid | C7H14NO5P | 14 | 0 | S_P |
| M2S-000061 | L3 | 26 | N2S-001230 | 1-methyl-3-(24-tetradecyloctatriacont-9-en-19-yl)imidazol-1-ium | C56H109N2+ | 58 | 1 | CHNO |
| M2S-000062 | L3 | 26.6 | N2S-000855 | 2-[[4-(4-methoxyphenyl)oxan-4-yl]methyl]-1-(4-methylphenyl)guanidine;hydroiodide | C21H28IN3O2 | 27 | 3 | halogen |
| M2S-000063 | L3 | 27.3 | N2S-001415 | 4-bromo-2,5-dideuterio-1-[2,3,5,6-tetradeuterio-4-(trideuteriomethyl)phenyl]imidazole | C10H9BrN2 | 13 | 2 | halogen |
| M2S-000064 | L3 | 28.6 | N2S-001297 | N-[1-[(2-acetamido-2-chloro-2-formamidoacetyl)amino]-1-bromo-2-[(butanoylamino)-(propan... | C19H29BrClN7O7 | 35 | 0 | halogen |
| M2S-000065 | L3 | 29.2 | N2S-000177 | 2-[3-amino-4-oxo-7-(trifluoromethyl)-2,3-dihydro-1,5-benzothiazepin-5-yl]acetic acid;hy... | C12H12BrF3N2O3S | 22 | 2 | S_P |
| M2S-000066 | L3 | 29.7 | N2S-000070 | methyl N-[(Z)-(2-oxo-1,2-diphenylethylidene)amino]carbamate | C16H14N2O3 | 21 | 2 | CHNO |
| M2S-000067 | L3 | 29.8 | N2S-000359 | 5-methyl-4-oxo-1,6-diphenyl-3-(2,4,5-trichlorophenyl)sulfanylpyridin-2-olate | C24H15Cl3NO2S- | 31 | 4 | S_P |
| M2S-000068 | L3 | 31.2 | N2S-001424 | 2-(5-iodopentyl)-1,4-diazabicyclo[2.2.2]octane;hydroiodide | C11H22I2N2 | 15 | 3 | halogen |
| M2S-000069 | L3 | 34.5 | N2S-000873 | 4-acetyl-N-(3-ethoxyspiro[3.3]heptan-1-yl)-N'-ethylpiperazine-1-carboximidamide;hydroio... | C18H33IN4O2 | 25 | 3 | halogen |
| M2S-000070 | L3 | 35.1 | N2S-000246 | (2R)-N-(2-methylpropylcarbamoyl)-2-[4-[2-(trifluoromethyl)phenyl]sulfonylpiperazin-1-iu... | C19H28F3N4O4S+ | 31 | 2 | S_P |
| M2S-000071 | L3 | 36 | N2S-000129 | [(4R)-7-[tert-butyl(diphenyl)silyl]-2,5-dimethylocta-5,6-dien-4-yl] acetate | C28H38O2Si | 31 | 2 | B_Si_Se_As |
| M2S-000072 | L3 | 36.1 | N2S-000755 | (2S)-2-[[2-(3-bromo-N-(4-methylphenyl)sulfonylanilino)acetyl]-[(4-bromophenyl)methyl]am... | C27H29Br2N3O4S | 37 | 3 | S_P |
| M2S-000073 | L3 | 36.2 | N2S-000566 | 2-[3-(3,4-dihydroisoquinolin-1-ylmethyl)-1-(thiophene-2-carbonyl)piperidin-4-yl]acetate | C22H23N2O3S- | 28 | 4 | S_P |
| M2S-000074 | L3 | 37.5 | N2S-001288 | 4-(7-amino-5-azaspiro[2.4]heptan-5-yl)-N-methyl-2-pyridin-3-ylsulfanyl-9H-indeno[2,1-d]... | C23H24N6S | 30 | 6 | S_P |
| M2S-000075 | L3 | 37.6 | N2S-000106 | 9,10,11,12,18,19,20,21-octazatetracyclo[16.2.1.02,7.08,12]henicosa-1(21),2,4,6,8,10,19-... | C13H14N8 | 21 | 4 | CHNO |
| M2S-000076 | L4 | 38 | N2S-000679 | phosphanylmethyl N-hydroxy-N-[[(5'R)-5'-hydroxy-2',5',7'-trimethyl-4'-oxospiro[cyclopro... | C17H22NO5P | 24 | 3 | S_P |
| M2S-000077 | L4 | 38.2 | N2S-000236 | methyl 4-[[[(2R,3R)-4-[3-(dipropylcarbamoyl)anilino]-2,3-dihydroxy-4-oxobutanoyl]amino]... | C26H33N3O7 | 36 | 2 | CHNO |
| M2S-000078 | L4 | 38.4 | N2S-000310 | [(2S)-1-oxo-1-(2,2,2-trifluoroethylamino)propan-2-yl] 2-[[(1S)-1,7-dimethyl-3-oxo-1,2-d... | C18H20F3NO5 | 27 | 2 | halogen |
| M2S-000079 | L4 | 40.7 | N2S-001200 | (2R,4R,5S,6S)-6-(1-hydroxyethyl)-4-methyl-3,7-dioxo-1-azabicyclo[3.2.0]heptane-2-carbox... | C10H12NO5- | 16 | 2 | CHNO |
| M2S-000080 | L4 | 41.9 | N2S-000198 | 2-methyl-4-[3-[3-(3-trimethylsilylpropyl)-2H-imidazol-1-yl]pyrrolidin-1-yl]aniline chlo... | C20H34ClN4Si- | 26 | 3 | B_Si_Se_As |
| M2S-000081 | L4 | 42 | N2S-000572 | (2R,5R)-2-propan-2-yl-4,6,13-trioxa-3-azoniadispiro[4.1.57.25]tetradecan-14-one chloride | C13H22ClNO4 | 19 | 3 | halogen |
| M2S-000082 | L4 | 42.1 | N2S-001425 | tetramethyl 22,23-dimethoxytetracyclo[18.4.0.04,9.012,17]tetracosa-1(24),4,6,8,12,14,16... | C34H36O10 | 44 | 4 | CHNO |
| M2S-000083 | L4 | 42.3 | N2S-000993 | bis[[(Z)-docos-13-enoyl]oxy]lead | C44H82O4Pb | 49 | 0 | metal |
| M2S-000084 | L4 | 42.4 | N2S-001286 | 1,1,2,3,3,5,5,6,6-nonadeuterio-1-(2,3,4,6-tetradeuterio-5-methylphenoxy)-6-[2,3,6-tride... | C21H28O4 | 25 | 2 | CHNO |
| M2S-000085 | L4 | 43.6 | N2S-001442 | 1-methyl-2-[(9Z)-18-methyl-11-methylidene-15-oxatetracyclo[12.7.0.03,8.016,21]henicosa-... | C28H24NO+ | 30 | 5 | CHNO |
| M2S-000086 | L4 | 44.1 | N2S-000085 | 5',6'-dimethoxyspiro[1-azabicyclo[2.2.2]octane-3,3'-2H-indene]-1'-one;hydrochloride | C17H22ClNO3 | 22 | 5 | halogen |
| M2S-000087 | L4 | 44.4 | N2S-001258 | 3,10-diazahexacyclo[15.8.0.02,10.04,9.011,16.019,24]pentacosa-1(17),2,4,6,8,11,13,15,18... | C35H23N2PSe | 39 | 8 | B_Si_Se_As |
| M2S-000088 | L4 | 44.5 | N2S-001051 | (NE)-N-[phenyl-[4-[(5S)-1',3',3'-trimethylspiro[4H-1,2-oxazole-5,2'-indole]-3-yl]phenyl... | C26H25N3O2 | 31 | 5 | CHNO |
| M2S-000089 | L4 | 45.3 | N2S-001395 | methyl 2-[6-[[4-[1-(tert-butylamino)ethenylamino]phenyl]methyl]-4,7,10-tris(2-methoxy-2... | C33H54N6O8 | 47 | 2 | CHNO |
| M2S-000090 | L4 | 51.4 | N2S-001171 | (3R,4'S,6'R)-6-chloro-4'-phenyl-1'-(3-piperidin-1-ylpropyl)-6'-prop-1-en-2-ylspiro[1H-i... | C29H34ClN3O2 | 35 | 5 | halogen |
| M2S-000091 | L5 | 53.5 | N2S-001279 | [(2R)-1-[[(2S)-3-[[(2R)-2,3-bis(18-methylicosanoyloxy)propoxy]-hydroxyphosphoryl]oxy-2-... | C88H172O17P2 | 107 | 0 | S_P |
| M2S-000092 | L5 | 54.4 | N2S-000371 | sodium (3E)-6-amino-3-[[2-[(2-methoxyphenyl)diazenyl]phenyl]hydrazinylidene]-4-oxonapht... | C23H19N5NaO5S+ | 35 | 4 | metal |
| M2S-000093 | L5 | 59 | N2S-000953 | trans-(1R,3S,5Z)-5-[(E)-3-[3-(2,3-dideuterio-6-hydroxyheptyl)phenyl]hept-2-enylidene]-4... | C27H40O3 | 30 | 2 | CHNO |
| M2S-000094 | L5 | 61.7 | N2S-000103 | [(1S,2R,4S,10R,11S,12R)-11-acetyloxy-4,10-dihydroxy-1,5-dimethylspiro[8-oxatricyclo[7.2... | C19H26O8 | 27 | 4 | CHNO |
| M2S-000095 | L5 | 63.1 | N2S-001135 | [(1Z,6E)-7-chloro-1-[[2-[[(2Z,4Z,6E)-8-(5-methoxy-6-oxo-2,3-dihydropyran-2-yl)-6-methyl... | C31H43ClIN3O7 | 43 | 1 | halogen |
| M2S-000096 | L5 | 64.4 | N2S-001340 | [1-[(9Z,12Z,15Z)-octadeca-9,12,15-trienoxy]-3-[3,4,5-trihydroxy-6-[[3,4,5-trihydroxy-6-... | C50H88O14 | 64 | 2 | CHNO |
| M2S-000097 | L5 | 65.9 | N2S-000386 | tert-butyl (5E)-5-[(3aS,4R,5R,6aS)-4-[(E,3S)-5,5-dideuterio-3-hydroxy-4-methyloct-1-en-... | C26H40O4 | 30 | 2 | CHNO |
| M2S-000098 | L5 | 68.6 | N2S-001232 | (2R,3S,4R,5R,8R,10R,11R,12S,13S,14R)-6-[14-(4-diphenylphosphanylphenyl)tetradecanoyl]-2... | C53H80NO8P | 63 | 4 | S_P |
| M2S-000099 | L5 | 71.3 | N2S-000772 | [(1S,5S,7S,9S,11S,13R)-7-methoxy-9-methyl-3-oxo-5-propyl-4,15-dioxabicyclo[9.3.1]pentad... | C33H48N2O8 | 43 | 3 | CHNO |
| M2S-000100 | L5 | 72.5 | N2S-000451 | [1-[2-[(3R,5S,8S)-8-cyclopentyl-18-methoxy-7,10-dioxo-2,11-dioxa-6,23-diazatetracyclo[1... | C35H45N2O9P | 47 | 6 | S_P |

## Usage

```powershell
python scripts/evaluate_name2smiles.py --data data/mini_100.jsonl --limit 100 --models "deepseek-flash,qwen3.8-flash"
```

The file is sorted by tier, so `--offset` and `--limit` can select a single tier. Use the offset column in the ladder table.

The records keep the original dataset IDs, image paths, and coordinate paths. The mini file is a view over the full set, not a copy of the generated assets.
