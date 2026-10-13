# Task 16 - candidate-filter decisions by vessel class

Variants: ['legacy']; seeds: [0, 1, 2, 3, 4].  Counts are summed over the three regional problems and averaged over seeds.  `legacy_pass` = the production margin guess and corridor test; `exempt` = demand-coherent loops (exempt in production); `kept` = survives the variant (including the cap).

## Variant `legacy`

| class | generated | exempt loops | legacy pass | legacy reject: margin guess | legacy reject: no corridor | feasible (canonical) | stand-alone profitable | stand-alone profit mean USD/wk (non-loop) | kept by this variant |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Feeder_450 | 24.8 | 24.8 | 0.0 | 0.0 | 0.0 | 24.8 | 0.0 | nan | 24.8 |
| Feeder_800 | 1319.4 | 46.4 | 1272.8 | 0.0 | 0.2 | 1319.4 | 32.0 | -736,368 | 1199.2 |
| Panamax_1200 | 23.6 | 16.8 | 6.8 | 0.0 | 0.0 | 23.6 | 18.0 | 177,385 | 23.6 |
| Panamax_2400 | 47.0 | 24.2 | 22.8 | 0.0 | 0.0 | 47.0 | 27.8 | -483,855 | 47.0 |
| Post_panamax | 230.0 | 18.4 | 207.4 | 0.0 | 4.2 | 230.0 | 22.2 | -5,004,157 | 225.8 |
| Super_panamax | 53.4 | 4.2 | 22.2 | 0.0 | 27.0 | 53.4 | 4.4 | -2,444,041 | 26.4 |

