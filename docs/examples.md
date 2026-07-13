# SimAPI — Examples

All examples assume the API is running on `http://localhost:8000`. Add
`-H "X-API-Key: $SIMAPI_API_KEY"` when auth is enabled.

## Health & metrics

```bash
curl http://localhost:8000/v1/health
curl http://localhost:8000/v1/metrics
```

## Validate a JSON batch

```bash
curl -X POST http://localhost:8000/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_type": "aerodynamics",
    "conditions": {"velocity": 15.0, "altitude": 120.0},
    "data": [
      {"cd": 0.312, "cl": 0.847, "re": 415000, "ma": 0.044},
      {"cd": 0.315, "cl": 0.851, "re": 418000, "ma": 0.044}
    ]
  }'
```

## Physics-only (skip the AI layer)

```bash
curl -X POST http://localhost:8000/v1/validate/physics-only \
  -H "Content-Type: application/json" \
  -d '{"simulation_type":"structural","data":[{"stress":250,"yield_stress":355,"safety_factor":1.4}]}'
```

## Upload a file

```bash
curl -X POST http://localhost:8000/v1/validate/upload \
  -F "file=@cfd_output.csv" \
  -F "simulation_type=aerodynamics" \
  -F 'conditions={"velocity":15.0}'
```

## Poll for the async AI result

```bash
JOB=$(curl -s -X POST http://localhost:8000/v1/demo | jq -r .job_id)
curl "http://localhost:8000/v1/job/$JOB/ai"
```

## Python SDK

```python
import simapi

result = simapi.demo()
print(result.summary())
print(result.failed_checks())
result.download_csv("stats.csv")
```

## Artifacts in this folder

- `openapi.json` — the full OpenAPI 3 schema (also served live at `/openapi.json`).
- `SimAPI.postman_collection.json` — import into Postman; set the `base_url` and
  `api_key` collection variables.
