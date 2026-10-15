# Unserved-demand diagnosis, arm C3e, 9 seeds ([0, 1, 2, 3, 4, 5, 6, 7, 8])

unserved share of demand: mean 60.0 % (min 52.1, max 74.0)
ODs with one cause only: 31.4 % of demand; with overlapping causes: 28.5 %

## Causes present (overlapping; share of ALL demand in ODs where the cause applies to at least one path)
| cause | % of demand |
|---|---:|
| blocked_by_inventory | 43.4 |
| openable_with_free_fleet | 35.3 |
| any_path_excluded_by_cap | 22.9 |
| no_valid_path_pool | 5.5 |
| no_valid_path_limit | 3.4 |
| operated_full | 3.4 |
| operated_room_unprofitable | 0.4 |
| operated_room_profitable | 0.0 |

## Exclusive combinations (additive; sum = unserved share)
| combination | % of demand |
|---|---:|
| blocked_by_inventory+openable_with_free_fleet | excluded-by-cap | 15.3 |
| blocked_by_inventory | 10.1 |
| blocked_by_inventory+openable_with_free_fleet | 9.5 |
| openable_with_free_fleet | 7.1 |
| no_valid_path_pool | 5.5 |
| blocked_by_inventory | excluded-by-cap | 5.0 |
| no_valid_path_limit | 3.4 |
| blocked_by_inventory+openable_with_free_fleet+operated_full | excluded-by-cap | 2.1 |
| blocked_by_inventory+operated_full | 0.5 |
| blocked_by_inventory+openable_with_free_fleet+operated_full | 0.4 |
| openable_with_free_fleet | excluded-by-cap | 0.3 |
| openable_with_free_fleet+operated_full | 0.2 |
| blocked_by_inventory+openable_with_free_fleet+operated_room_unprofitable | 0.1 |
| blocked_by_inventory+operated_room_unprofitable | 0.1 |

flow re-optimisation contradictions (an operated path with room and positive margin that was not used): 0
ODs with an excluded positive-margin path: 354 per seed (margin x unserved TEU = 31.5 M/week, an upper-bound-style figure)
