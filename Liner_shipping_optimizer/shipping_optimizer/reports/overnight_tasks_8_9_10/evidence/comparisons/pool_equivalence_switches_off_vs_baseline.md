# Candidate pool: frozen baseline vs final tree with both switches at 0

One interpreter per tree and seed (`PYTHONHASHSEED=0`, `python -I`). A candidate is `(ports, vessel class, capacity, cycle time)`; lists are compared in order.

| seed | region | baseline | final, switches 0/0 | identical (ordered) | final, defaults | added by defaults | removed by defaults |
|---:|---|---:|---:|:---:|---:|---:|---:|
| 1 | Asia | 508 | 508 | yes | 563 | 241 | 186 |
| 1 | Europe | 405 | 405 | yes | 440 | 181 | 146 |
| 1 | Americas | 499 | 499 | yes | 548 | 277 | 228 |
| 2 | Asia | 508 | 508 | yes | 562 | 242 | 188 |
| 2 | Europe | 405 | 405 | yes | 441 | 175 | 139 |
| 2 | Americas | 499 | 499 | yes | 546 | 268 | 221 |
| 3 | Asia | 508 | 508 | yes | 563 | 237 | 182 |
| 3 | Europe | 405 | 405 | yes | 433 | 168 | 140 |
| 3 | Americas | 499 | 499 | yes | 543 | 261 | 217 |

**Result: IDENTICAL for every seed and region.**
