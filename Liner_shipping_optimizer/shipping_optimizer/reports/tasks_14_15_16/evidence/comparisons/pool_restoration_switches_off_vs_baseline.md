# Candidate pool: frozen baseline vs final tree with both switches at 0

One interpreter per tree and seed (`PYTHONHASHSEED=0`, `python -I`). A candidate is `(ports, vessel class, capacity, cycle time)`; lists are compared in order.

| seed | region | baseline | final, switches 0/0 | identical (ordered) | final, defaults | added by defaults | removed by defaults |
|---:|---|---:|---:|:---:|---:|---:|---:|
| 1 | Asia | 508 | 508 | yes | 563 | 305 | 250 |
| 1 | Europe | 405 | 405 | yes | 440 | 216 | 181 |
| 1 | Americas | 499 | 499 | yes | 548 | 293 | 244 |
| 2 | Asia | 508 | 508 | yes | 562 | 304 | 250 |
| 2 | Europe | 405 | 405 | yes | 441 | 216 | 180 |
| 2 | Americas | 499 | 499 | yes | 546 | 290 | 243 |
| 3 | Asia | 508 | 508 | yes | 563 | 306 | 251 |
| 3 | Europe | 405 | 405 | yes | 433 | 209 | 181 |
| 3 | Americas | 499 | 499 | yes | 543 | 286 | 242 |

**Result: IDENTICAL for every seed and region.**
