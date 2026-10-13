# Candidate pool: Tasks 8-10 final tree (defaults) vs Task 16 tree (defaults, economic filter)

Same generator, same seeds, same switches (loops 60, screening k=1); only `LINER_REGIONAL_FILTER=auto` (-> economic) differs. A candidate is `(ports, vessel class, capacity, cycle time)`.

| seed | region | baseline pool | economic-filter pool | kept in both | dropped by economic (kept by legacy) | added by economic (cut by legacy) | classes added | classes dropped |
|---:|---|---:|---:|---:|---:|---:|---|---|
| 1 | Asia | 563 | 563 | 499 | 64 | 64 | {'Feeder_800': 64} | {'Super_panamax': 3, 'Post_panamax': 61} |
| 1 | Europe | 440 | 440 | 405 | 35 | 35 | {'Feeder_800': 35} | {'Super_panamax': 3, 'Post_panamax': 32} |
| 1 | Americas | 548 | 548 | 532 | 16 | 16 | {'Feeder_800': 16} | {'Super_panamax': 4, 'Post_panamax': 12} |
| 2 | Asia | 562 | 562 | 500 | 62 | 62 | {'Feeder_800': 62} | {'Super_panamax': 3, 'Post_panamax': 59} |
| 2 | Europe | 441 | 441 | 400 | 41 | 41 | {'Feeder_800': 41} | {'Super_panamax': 4, 'Post_panamax': 37} |
| 2 | Americas | 546 | 546 | 524 | 22 | 22 | {'Feeder_800': 22} | {'Super_panamax': 4, 'Post_panamax': 18} |
| 3 | Asia | 563 | 563 | 494 | 69 | 69 | {'Feeder_800': 69} | {'Super_panamax': 3, 'Post_panamax': 66} |
| 3 | Europe | 433 | 433 | 392 | 41 | 41 | {'Feeder_800': 41} | {'Super_panamax': 4, 'Post_panamax': 37} |
| 3 | Americas | 543 | 543 | 518 | 25 | 25 | {'Feeder_800': 25} | {'Super_panamax': 5, 'Post_panamax': 20} |
