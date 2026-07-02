"""
test_semantic.py
----------------
Quality comparison: keyword search vs semantic search.

Demonstrates the semantic advantage with queries that have
NO exact keyword overlap with the data.

Run after: python run_ingest.py
"""
from search.keyword_search import search_all as keyword_search
from search.semantic_search import semantic_search_all as semantic_search

SEP = "=" * 65


def show_packages(label, results, attr="packages"):
    items = getattr(results, attr)
    print(f"  {label} ({len(items)} results):")
    for p in items[:4]:
        score = getattr(p, "score", None) or getattr(p, "distance", None)
        score_label = "dist" if hasattr(p, "distance") else "score"
        title = getattr(p, "title", getattr(p, "name", getattr(p, "country", "?")))
        dest = getattr(p, "destinations", None)
        extra = f" | {dest[:1]}" if dest else ""
        print(f"    [{score_label}={score:.3f}] {title}{extra}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Semantic-only query (no literal keyword match in data)
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("TEST 1: 'romantic getaway for couples by the ocean'")
print("(No exact keywords — tests semantic understanding)")
print(SEP)

kw = keyword_search("romantic getaway for couples by the ocean", limit=5)
sem = semantic_search("romantic getaway for couples by the ocean", n_results=5)

show_packages("KEYWORD packages", kw)
show_packages("SEMANTIC packages", sem)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: Cultural / spiritual travel
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("TEST 2: 'ancient temples monasteries spiritual journey'")
print(SEP)

kw2 = keyword_search("ancient temples monasteries spiritual journey", limit=5)
sem2 = semantic_search("ancient temples monasteries spiritual journey", n_results=5)

show_packages("KEYWORD packages", kw2)
show_packages("SEMANTIC packages", sem2)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Visa — natural language query
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("TEST 3: 'what documents do I need for international travel'")
print(SEP)

sem3 = semantic_search(
    "what documents do I need for international travel",
    n_results=5,
    include_types={"visa"},
)
show_packages("SEMANTIC visa", sem3, attr="visa")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Luxury resort / pampering holiday
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("TEST 4: 'five star resort spa pampering luxury escape'")
print(SEP)

sem4 = semantic_search("five star resort spa pampering luxury escape", n_results=6)
show_packages("SEMANTIC packages", sem4)
show_packages("SEMANTIC hotels", sem4, attr="hotels")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Adventure / trekking
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("TEST 5: 'high altitude trekking snow peaks challenging hike'")
print(SEP)

sem5 = semantic_search("high altitude trekking snow peaks challenging hike", n_results=5)
show_packages("SEMANTIC packages", sem5)
show_packages("SEMANTIC itineraries", sem5, attr="itineraries")

print()
print("All semantic tests complete.")
