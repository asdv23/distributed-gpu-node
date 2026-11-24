# Compliance

## Collecting market data

- Use official APIs, official CLIs and public market data only. Never get around a login, captcha,
  access control, quota or result limit.
- **Sampled searches are taken as they come.** Vast.ai returns a varying subset of matching
  offers. The collector sends each search once per run and does not repeat it to rebuild the full
  list. Coverage improves only through the regular hourly schedule. Narrow searches (for example
  mainland China, or the nearby countries) answer the operator's research questions and are not
  used to enumerate the global market around the result limit.
- Respect rate limits and quotas: requests at least 2 s apart, bounded retries with backoff, and
  an immediate stop on Vast.ai's `search_quota_exceeded`.
- Clore.ai's server list and Salad's earning rates and demand monitor are public feeds that need
  no login (Clore's docs call the listing public). Each is downloaded once per hour, under the
  plain client name `gpu-market-collector/0.1`. That name identifies no project or person and
  imitates no browser. A feed is stored only if it has its expected shape and holds nothing that
  looks like an IP address. Clore owner IDs stay in the local database, like Vast host IDs.
- Vast.ai's docs say every endpoint needs an API key. Search works without one, as it does in the
  official CLI, and the first batch was collected that way. Once a key exists, the collector sends
  it (`VAST_API_KEY`).

## Privacy

- IP addresses, hostnames, host web pages and geocodes are removed before anything is stored.
- Host and machine IDs stay in the local database, which never leaves the operator's machines.
  Reports and committed files contain aggregates only.

## Platform terms and contracts

| Platform | Host or API terms reviewed | Note |
|---|---|---|
| Vast.ai | no | review before listing our host (Sprint 4) |
| Clore.ai | no | |
| Salad | no | |
| Akash | no | |

- A rental stays with the customer until it ends. A better price elsewhere never interrupts it.
- No own jobs run on a GPU while a customer rents it.
- Switching a GPU between platforms follows each platform's current host terms and API rules.

## Publishing results

- Each figure states its data class. Estimates are never shown as revenue, and listing counts
  never as occupancy or rental rates.
- Simulated data is marked SIMULATED wherever it appears.
