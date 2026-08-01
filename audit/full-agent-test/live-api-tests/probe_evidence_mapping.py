"""Probe the configured real LLM with the latest cross-language evidence map."""

import json
from urllib.request import Request, urlopen

from research_claim_bound_script import NARRATIONS


BASE_URL = "http://127.0.0.1:8000/api"
JOB_ID = "a6e91464-7e8b-4571-9229-749f09ec5253"

job = json.load(urlopen(f"{BASE_URL}/jobs/{JOB_ID}"))["result_json"]
claim_lines = "\n".join(
    f"- {claim['id']}: {claim['statement']}" for claim in job["claims"]
)
scene_lines = "\n".join(
    f"- {index}: {narration}"
    for index, narration in enumerate(NARRATIONS, start=1)
)
prompt = f"""# Cross-language evidence mapping
Map each narration to only the claim IDs that fully entail its factual content.
Do not use background knowledge or partial keyword overlap. Return an empty list
when no claim fully supports a narration. Dates, quantities, places, companies,
and model variants must agree exactly.

Claims:
{claim_lines}

Narrations:
{scene_lines}

Return JSON only:
{{"mappings":[{{"scene_index":1,"claim_ids":["claim-1"]}}]}}
Include exactly one mapping for every scene index.
"""
data = json.dumps({"prompt": prompt, "temperature": 0, "max_tokens": 2000}).encode()
request = Request(
    f"{BASE_URL}/llm/chat",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=120) as response:
    result = json.load(response)
print(json.dumps(result, ensure_ascii=True, indent=2))
