"""API endpoint smoke tests."""
import urllib.request
import json
import time

time.sleep(2)

BASE = "http://localhost:8000"

TESTS = [
    "/",
    "/search?q=Kerala+family+trip",
    "/packages?limit=3",
    "/packages/1",
    "/hotels?city=Goa&limit=3",
    "/visa/Singapore",
]

for path in TESTS:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            print(f"OK   {path}")
            if "search" in path:
                pkgs = len(data.get("packages", []))
                htls = len(data.get("hotels", []))
                itns = len(data.get("itineraries", []))
                print(f"     packages={pkgs}  hotels={htls}  itineraries={itns}")
            elif path == "/packages/1":
                title = data.get("title", "?")
                itins = len(data.get("itineraries", []))
                hotels = len(data.get("hotels", []))
                print(f"     title={title!r}  itineraries={itins}  hotels={hotels}")
            elif "Singapore" in path:
                country = data.get("country", "?")
                req_len = len(data.get("requirements", ""))
                print(f"     country={country}  requirements_len={req_len}")
    except Exception as exc:
        print(f"ERR  {path}: {exc}")

print("\nAll endpoint tests complete.")
