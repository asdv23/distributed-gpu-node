# Platform research

Each fact is tagged with its data class. Dates are when it was checked.

## Vast.ai

### Offer search API (checked 2026-11-23)

| Fact | Class | Evidence |
|---|---|---|
| Endpoint `POST https://console.vast.ai/api/v0/bundles/`; body holds filters as `{field: {op: value}}` plus `type`, `limit`, `order` | official_doc | [search offers](https://docs.vast.ai/api-reference/search/search-offers) |
| The docs say every endpoint requires `Authorization: Bearer <key>` | official_doc | same page |
| Search answers without a key; the official CLI sends a key only when one is configured | collected, verified | live requests; vastai 1.11.2 source (`api/client.py`) |
| A response without a key holds at most 64 offers; a higher `limit` is ignored and `truncated` stays `false` | collected | `limit` 100…10000 all returned 64 |
| **Responses are samples.** Six identical searches (KR, RTX 3060) returned 37 offers each but 96 distinct offers on 58 machines between them, still growing. CN RTX 4090 rentable: 27 offers each, 48 distinct offers, while machines levelled off at 18 | collected | probe log, 2026-11-23 |
| The same sampling happens with an API key and in the web console. One response held about 50% of the offers seen across the reporter's repeated searches in September 2026, and 10–30% in November | third_party | [vast-cli#536](https://github.com/vast-ai/vast-cli/issues/536), open, no reply from Vast |
| Rate-limit headers: `x-ratelimit-limit: 30`, reset 1–2 s ahead | collected | response headers |
| A daily search quota exists: HTTP 429 with `error: search_quota_exceeded`, reset at 00:00 UTC; the official client does not retry it. Its size is unknown | verified | vastai 1.11.2 `api/client.py` |
| The client retries 429/502/503/504 and connection errors with backoff | verified | same file |
| `rented` filter: "include offers where the calling user already has rented GPUs" (it describes the caller, not the market) | official_doc | search offers page |
| `rentable`: "Whether machine is rentable". Its meaning beyond that is undocumented | official_doc | search offers page |
| `gpu_frac`: ratio of the offer's GPUs to the GPUs in the machine | official_doc | CLI help (`search offers`) |
| `gpu_ram`, `cpu_ram` in MB; `duration` in seconds until the listing's end date | official_doc, collected | search offers page; responses |
| `inet_up` / `inet_down`: the CLI help says Mb/s, the API page says MB/s. Values of 500–1000 on home hosts point to Mb/s | official_doc (conflicting), assumption | both pages |
| `dph_base` is the GPU part of the price: `dph_total` = `dph_base` + `storage_total_cost` | collected | arithmetic on responses |
| `geolocation` reads "Place, CC"; the search filter takes the two-letter code | collected, official_doc | responses; search offers page |
| Offers of one machine come in several sizes (1, 2, 4 … GPUs) | collected | responses |
| `disable_bundling` is "more heavily rate limited". It did not change offer counts in three tests | official_doc, collected | CLI help; probe |
| RTX 4090 listings with 49140 MB (48 GB) exist, mostly in CN and the US, priced above the 24 GB cards. 23028 MB matches a 24 GB card with ECC on | collected, assumption | first run |

### Not yet researched

- Fee split between Vast and hosts, and how listed price maps to host payout (Sprint 4).
- Host terms of service, verification criteria, payout and withdrawal methods.
- Host-side API for own machines: listings, rentals, earnings (Sprint 4).

## Clore.ai, Salad, Akash Network

Not researched yet. Questions for each, to be answered from official sources:

1. Is there an official API or CLI exposing marketplace offers or prices? Does it need
   authentication, and what are its limits?
2. Can a host read its own rentals and earnings through an API?
3. Host requirements and terms: hardware, OS, network, verification, payouts, minimum commitments.
4. Can a GPU switch between platforms without breaking the host terms?
