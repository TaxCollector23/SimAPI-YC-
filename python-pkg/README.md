# simapi (Python SDK + CLI)

Validate simulation results before they reach production, from Python or the terminal.
Zero runtime dependencies (stdlib only). Python 3.9+.

## Install

```bash
pip install simapi
```

## SDK

```python
from simapi import SimAPI

client = SimAPI(api_key="sk_live_...")            # or set SIMAPI_API_KEY
result = client.validate("simulation.json", simulation_type="aerodynamics")
print(result["status"], result["all_checks"])
```

## CLI

```bash
simapi login                     # opens the browser, paste your API key
simapi init                      # write a sample simapi.json
simapi validate simulation.json
simapi watch simulation.json     # re-validate on change
simapi usage                     # requests today/month, quota, avg time
simapi api-key show|rotate|delete
simapi config [set <key> <value>]
simapi whoami
simapi version
simapi help
simapi <command> --help
```

`SIMAPI_API_KEY` overrides the saved key; `SIMAPI_BASE_URL` overrides the endpoint
(default `https://sim-api.vercel.app/api`).
