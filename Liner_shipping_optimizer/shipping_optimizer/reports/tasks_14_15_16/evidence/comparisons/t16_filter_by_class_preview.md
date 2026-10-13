# Task 16 - candidate-filter decisions by vessel class

Variants: ['legacy']; seeds: [2, 3].  Counts are summed over the three regional problems and averaged over seeds.  `legacy_pass` = the production margin guess and corridor test; `exempt` = demand-coherent loops (exempt in production); `kept` = survives the variant (including the cap).

## Variant `legacy`

| class | generated | exempt loops | legacy pass | legacy reject: margin guess | legacy reject: no corridor | feasible (canonical) | stand-alone profitable | stand-alone profit mean USD/wk (non-loop) | kept by this variant |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Feeder_450 | 25.0 | 25.0 | 0.0 | 0.0 | 0.0 | 25.0 | 0.0 | nan | 25.0 |
| Feeder_800 | 1319.0 | 46.5 | 1272.5 | 0.0 | 0.0 | 1319.0 | 31.0 | -736,714 | 1189.0 |
| Panamax_1200 | 23.0 | 16.0 | 7.0 | 0.0 | 0.0 | 23.0 | 17.5 | 179,934 | 23.0 |
| Panamax_2400 | 45.5 | 23.0 | 22.5 | 0.0 | 0.0 | 45.5 | 27.0 | -485,271 | 45.5 |
| Post_panamax | 239.0 | 17.0 | 218.0 | 0.0 | 4.0 | 239.0 | 21.0 | -4,920,275 | 235.0 |
| Super_panamax | 53.5 | 4.5 | 22.0 | 0.0 | 27.0 | 53.5 | 4.5 | -2,456,943 | 26.5 |

