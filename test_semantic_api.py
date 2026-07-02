"""API smoke test for the new /search/semantic endpoint."""
import urllib.request
import json
import time

time.sleep(3)

BASE = "http://localhost:8000"

SEMANTIC_TESTS = [
    ("/search/semantic?q=romantic+beach+holiday+for+couples&n=5",
     "romantic beach holiday for couples"),
    ("/search/semantic?q=ancient+temples+spiritual+journey&n=5",
     "ancient temples spiritual journey"),
    ("/search/semantic?q=five+star+luxury+resort+spa&n=5&types=hotels",
     "luxury hotels only"),
    ("/search/semantic?q=passport+visa+documents&n=5&types=visa",
     "visa only"),
    ("/search/semantic?q=trekking+himalaya+snow&n=5&types=packages,itineraries",
     "trekking packages + itineraries"),
]

print("=" * 60)
print("Semantic API Endpoint Tests")
print("=" * 60)

for path, label in SEMANTIC_TESTS:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = json.loads(resp.read())
            pkgs  = len(data.get("packages", []))
            htls  = len(data.get("hotels", []))
            itns  = len(data.get("itineraries", []))
            visa  = len(data.get("visa", []))
            total = data.get("total", 0)
            print(f"\nOK  [{label}]")
            print(f"    total={total}  packages={pkgs}  hotels={htls}  itin={itns}  visa={visa}")
            # Show top package result if any
            if data.get("packages"):
                p = data["packages"][0]
                print(f"    Top pkg: [{p['distance']:.3f}] {p['title']}")
            if data.get("hotels"):
                h = data["hotels"][0]
                print(f"    Top htl: [{h['distance']:.3f}] {h['name']}, {h['city']}")
            if data.get("visa"):
                v = data["visa"][0]
                print(f"    Top vis: [{v['distance']:.3f}] {v['country']}")
    except Exception as exc:
        print(f"\nERR [{label}]: {exc}")

print("\n" + "=" * 60)
print("All semantic API tests complete.")
