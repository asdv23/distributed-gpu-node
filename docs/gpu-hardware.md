# GPU hardware

## Tracked models

| Model | Memory (NVIDIA) | Board power (NVIDIA) | Power limit set by Vast hosts: min / median / max | Machines seen |
|---|---|---|---|---|
| RTX 3060 | 12 GB GDDR6 (an 8 GB version exists) | 170 W | 100 / 170 / 180 W | 68 |
| RTX 3090 | 24 GB GDDR6X | 350 W | 180 / 300 / 420 W | 85 |
| RTX 4090 | 24 GB GDDR6X | 450 W | 150 / 450 / 500 W | 77 |
| RTX 4090, 48 GB listings | 48 GB (no NVIDIA SKU) | — | 400 / 450 / 450 W | 26 |
| RTX 5090 | 32 GB GDDR7 | 575 W | 400 / 550 / 600 W | 139 |

- Memory and board power: **official_doc**, NVIDIA product pages for the
  [RTX 3060](https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3060-3060ti/),
  [RTX 3090](https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3090-3090ti/),
  [RTX 4090](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4090/) and
  [RTX 5090](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/), checked
  2026-11-23.
- Power limits and machine counts: **collected**, field `gpu_max_power` of the Vast.ai listings
  in the first run (2026-11-23), one value per machine. A limit is what the host allows, not what
  the card draws.
- 48 GB RTX 4090 listings are presumably memory-modified boards (**assumption**).

## For the cost model (Sprint 4)

Board power is an upper bound for the GPU alone. The cost model uses measured wall power of the
whole machine, idle and loaded, from a meter or the node agent. Specification values are only a
placeholder until a measurement exists, and are labelled as such.
