from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / "cases"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]


def score_fixture_case(case: dict) -> dict:
    """Offline check: fixture must cover must_call_tools; keyword heuristic on fixture text."""
    fixture_path = FIXTURES / f"{case['id']}.json"
    if not fixture_path.exists():
        return {"id": case["id"], "ok": False, "reason": "missing fixture"}

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    called = set(fixture.keys())
    must = set(case.get("must_call_tools") or [])
    missing = sorted(must - called)
    blob = " ".join(
        (fixture[t].get("stdout") or "") + " " + (fixture[t].get("stderr") or "")
        for t in fixture
    ).lower()
    keywords = [k.lower() for k in case.get("expected_root_cause_keywords") or []]
    hit = any(k in blob for k in keywords) if keywords else True
    ok = not missing and hit
    return {
        "id": case["id"],
        "ok": ok,
        "missing_tools": missing,
        "keyword_hit": hit,
        "called_tools": sorted(called),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SRE agent eval runner")
    parser.add_argument("--fixture", action="store_true", help="Run offline fixture checks only")
    args = parser.parse_args()
    cases = load_cases()
    if not args.fixture:
        print("Live LLM+SSH eval not wired yet; use --fixture for offline checks.", file=sys.stderr)
        return 2

    results = [score_fixture_case(c) for c in cases]
    passed = sum(1 for r in results if r["ok"])
    print(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
