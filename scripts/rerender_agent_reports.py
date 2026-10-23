"""Re-render agent search reports with the release verdict - only when machine-verifiably
compatible.

An agent report attaches the verdict of an eligible estimation campaign of the same release
when it is written. If the agent ran before that estimation existed, this script re-renders
the report from the agent's evidence bundle (`results/evidence_<campaign>.json`, verified
against its hash) and the stored runs, attaching the verdict - but ONLY if
`avval.compat.is_compatible` holds: the campaign was recorded under the current release and
runtime IDs, or a replay of every one of its runs under the current release reproduced every
stored column (`python -m avval.cli verify-compat <campaign>`). Prose claims of
compatibility are never accepted. Incompatible campaigns are refused and listed.

    PYTHONPATH=. python scripts/rerender_agent_reports.py agent_s0 agent_s1 ...
"""
from __future__ import annotations

import json
import sys

from avval import RESULTS_DIR
from avval.compat import is_compatible
from avval.config import Release
from avval.estimation import release_verdict
from avval.frozen import canonical_json, sha256_text
from avval.policy import LearnedACC
from avval.report import write_search_report
from avval.store import Store


def load_bundle(campaign: str) -> dict:
    b = json.loads((RESULTS_DIR / f"evidence_{campaign}.json").read_text(encoding="utf-8"))
    body = {k: v for k, v in b.items() if k != "bundle_sha256"}
    if sha256_text(canonical_json(body)) != b["bundle_sha256"]:
        raise SystemExit(f"{campaign}: evidence bundle does not match its hash")
    return b


def main(campaigns: list[str]) -> int:
    store, policy = Store(), LearnedACC.load()
    release = Release.build(policy)
    verdict = release_verdict(store, release=release)  # raises if no eligible estimation
    refused = []
    for campaign in campaigns:
        ok, why = is_compatible(store, campaign, release)
        if not ok:
            refused.append(f"{campaign}: {why}")
            continue
        b = load_bundle(campaign)
        path = write_search_report(store, campaign, summary=b["summary"], author=b["author"],
                                   bundle=b, verdict=verdict, include_verdict=True)
        text = path.read_text(encoding="utf-8").replace(
            "\n## Summary\n", f"\n> **Re-rendered** by `scripts/rerender_agent_reports.py` to "
            f"attach the release verdict. Compatibility: {why}. The summary and conditions are "
            f"the agent's own (evidence bundle `{b['bundle_sha256'][:16]}…`).\n\n## Summary\n", 1)
        path.write_text(text, encoding="utf-8")
        print(path)
    for r in refused:
        print("REFUSED", r, file=sys.stderr)
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
