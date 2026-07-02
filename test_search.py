"""Quick search quality test script."""
from search.keyword_search import search_all, search_visa

SEP = "=" * 60

# --- Test 1 ---
print(SEP)
print('TEST 1: search_all("Kerala family trip")')
print(SEP)
r = search_all("Kerala family trip", limit=5)
print(f"Total results: {r.total}")
print(f"Packages ({len(r.packages)}):")
for p in r.packages:
    print(f"  [{p.score:.2f}] {p.title} | {p.duration_days}D | dest={p.destinations[:2]}")
print(f"Hotels ({len(r.hotels)}):")
for h in r.hotels[:3]:
    print(f"  [{h.score:.2f}] {h.name} | {h.city}")
print(f"Itineraries ({len(r.itineraries)}):")
for i in r.itineraries[:3]:
    print(f"  [{i.score:.2f}] {i.package_title} Day {i.day}: {i.title}")

print()
print(SEP)
print('TEST 2: search_all("Goa beach honeymoon")')
print(SEP)
r2 = search_all("Goa beach honeymoon", limit=5)
print(f"Total results: {r2.total}")
for p in r2.packages:
    print(f"  PKG [{p.score:.2f}] {p.title} | types={p.types[:2]}")
for h in r2.hotels[:3]:
    print(f"  HTL [{h.score:.2f}] {h.name} | {h.city}")

print()
print(SEP)
print('TEST 3: search_visa("Singapore")')
print(SEP)
r3 = search_visa("Singapore", limit=3)
for v in r3:
    print(f"  [{v.score:.2f}] {v.country}: {v.requirements[:120]}...")

print()
print(SEP)
print('TEST 4: search_all("adventure wildlife safari")')
print(SEP)
r4 = search_all("adventure wildlife safari", limit=5)
for p in r4.packages:
    print(f"  PKG [{p.score:.2f}] {p.title} | {p.category}")

print()
print(SEP)
print('TEST 5: search_all("luxury train Rajasthan palace")')
print(SEP)
r5 = search_all("luxury train Rajasthan palace", limit=5)
for p in r5.packages:
    print(f"  PKG [{p.score:.2f}] {p.title} | cat={p.category}")
for h in r5.hotels[:2]:
    print(f"  HTL [{h.score:.2f}] {h.name} | {h.city}")

print()
print("All tests done.")
