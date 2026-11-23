# Security

Agents in this project may one day hold partial control of the dedicated GPU host. Least privilege
applies everywhere.

## Permission tiers

**Allowed by default** (read-only):

- query GPU state, temperature and power
- query host state and rental orders
- read system logs
- generate operating reports
- run read-only health checks

**Needs a human's confirmation each time:**

- changing GPU power limits
- rebooting the GPU host
- installing or updating NVIDIA drivers
- changing the firewall or the SSH configuration
- installing a new host agent
- changing the GPU scheduling policy
- starting a new external task or stopping a customer task
- running any system-level command

Until confirmation is built into the tooling, a person carries out these actions.

**Forbidden, no exceptions:**

- exposing SSH to the public internet
- uploading private keys or API keys to GitHub
- running scripts of unknown origin automatically
- getting around a platform's admission rules
- breaking a customer's rental contract
- accessing customer containers or data without authorisation
- running our own compute jobs on a GPU while a customer rents it

## Secrets

- Code reads secrets from environment variables. `.env` is git-ignored; `.env.example` lists the
  names without values. Secrets are never printed, logged or copied into the repository.
- Platform API keys get the narrowest permissions the job needs. Market search needs read access
  only.
- The repository holds no tokens, passwords, customer data, host IP addresses or raw platform
  responses. The database (`data/`) stays out of git.

## Network

- VPS and GPU host talk over WireGuard or Tailscale. Neither exposes SSH publicly.
- The node agent pushes reports to the VPS. The VPS does not log in to the host to collect them.
