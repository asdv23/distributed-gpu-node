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

## Clore.ai (checked 2026-11-24)

| Fact | Class | Evidence |
|---|---|---|
| The server list is public: `https://clore.ai/webapi/marketplace/servers`, no key | official_doc | [pricing guide](https://docs.clore.ai/guides/getting-started/pricing) ("The marketplace listing is public") |
| Feed prices are USD per server per day; ÷ 24 ÷ GPUs gives USD per GPU-hour | official_doc | same page |
| Each server has a `rented` flag, `gpu_array`, one memory size (`specs.gpuram`), country (`specs.net.cc`) and speed-test results; no IP addresses | collected | feed, 2851 servers, 0 IPv4-looking strings |
| 101 of 2851 servers carry no USD on-demand price; 120 mix GPU models | collected | feed |
| The feed answers Python's default user agent with 403 and a plain client name with 200 | collected | requests on 2026-11-24 |
| `rented` is per server; partial GPU rentals do not show, so it is a lower bound of occupancy | assumption | feed and [host API](https://docs.clore.ai/for-hosts/api) |
| Host fee 5% on-demand, 1.25% spot, +15% when the renter pays in BTC/USDT/USDC | official_doc | [host fees](https://docs.clore.ai/for-hosts/host-fees) |
| Hosts: Ubuntu 22.04+ or HiveOS, NVIDIA, ≥8 GB RAM; "minimum" 100/100 Mbps, but 60% of RTX 3060 listings show under 100 Mbps upload | official_doc, collected | [network requirements](https://docs.clore.ai/for-hosts/installing-clore-hosting/network-requirements) |
| The installer warns that Docker Hub, GitHub and GitLab are often blocked or throttled in China | official_doc | [installer](https://gitlab.com/cloreai-public/hosting-agent-installer/-/raw/main/install.sh) |
| Payouts in CLORE, BTC, USDT or USDC only; no fiat | official_doc | [deposit and withdrawal](https://docs.clore.ai/getting-started/deposit-withdrawal) |

## Salad (checked 2026-11-24)

| Fact | Class | Evidence |
|---|---|---|
| Host earnings per GPU class over the last 7 days (mean, p25, p75, p99, `work` = % of time with a job), idle time included: `https://cdn.salad.com/site-data/earning-rates.json`, public | collected | feed; [earning rates](https://community.salad.com/gpu-earning-rates-november-2026) |
| Demand monitor per GPU: demand tier, earning-rate range, `utilizationPct` (undocumented, range 0-400): `https://app-api.salad.com/api/v2/demand-monitor/gpu`, public | collected | feed |
| Salad's classes do not separate memory variants (an RTX 3060 8 GB and 12 GB are one class) | collected | feed |
| Hosts: Windows 10/11 with WSL2 only; no public IP or port forwarding mentioned (customer traffic enters through Salad's gateway); 20 Mbps upload recommended | official_doc | [compatibility](https://support.salad.com/faq/compatibility/is-my-machine-compatible-with-salad), [overview](https://docs.salad.com/container-engine/explanation/core-concepts/overview) |
| No jobs behind a VPN or proxy; whether salad.com is reachable from mainland China is not verified | official_doc, assumption | [unblocking Salad](https://support.salad.com/article/186-how-to-unblock-salad-with-your-isp) |
| Balance is redeemed for PayPal (USD), prepaid or gift cards; no bank withdrawal | official_doc | [withdrawals](https://support.salad.com/faq/your-account/is-there-a-withdrawal-limit) |

## Akash Network and others (checked 2026-11-24)

- **Akash:** a provider needs Kubernetes, a static public IP or DDNS with its own domain, open
  ports 80/443/8443/8444/30000-32767 and at least 100 Mbps symmetric (official_doc,
  [hardware requirements](https://akash.network/docs/providers/getting-started/hardware-requirements/)). A home
  line with 50 Mbps upload does not qualify. Payouts are in AKT. One provider rented out RTX 3060s on 2026-11-24
  (collected, [console API](https://console-api.akash.network/v1/gpu)).
- **Not open to a home RTX 3060:**
  - RunPod: community hosting is closed to new hosts.
  - TensorDock: datacenters only.
  - io.net: needs at least 75 Mbps upload.

  All official_doc, checked 2026-11-24.
- **Open to it but without public occupancy data:** Nosana and Paralon. Both pay in tokens or
  USDC on Solana.
