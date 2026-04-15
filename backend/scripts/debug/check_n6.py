import json
import urllib.request

req = urllib.request.Request("http://localhost:8000/api/executions/153")
with urllib.request.urlopen(req) as resp:
    d = json.loads(resp.read())

for s in d.get("steps", []):
    if s["node_id"] == "n6":
        result = s.get("output_data", {}).get("result", [])
        if isinstance(result, list) and len(result) > 0:
            uye = result[0]
            for k in sorted(uye.keys()):
                v = uye[k]
                if v is not None and v != "" and v != [] and v != {}:
                    print(f"  {k} = {str(v)[:100]}")
        else:
            print("Empty result")
