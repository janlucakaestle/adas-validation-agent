"""Re-render the agent search reports so they carry the release verdict.

An agent report attaches the verdict of the estimation campaign that matches the release at
the time it is written. The three agent campaigns were written before the final code, so
their reports said no verdict was available. This script rebuilds each report from:

- the campaign's stored runs (discovery, preventability, coverage, triggering-condition
  evidence are recomputed from them, exactly as the agent's own report did);
- the agent's logged submission and hypothesis tests in `results/transcript_<campaign>.json`
  (the summary and conditions are the agent's own; `test_predicate` results are the logged
  ones, computed on the runs the agent had at the time).

It refuses to run unless an estimation matching the current release exists, and it adds a
note saying the report was re-rendered and under which source hash the agent ran. It lives
outside `avval/` so that it doesn't change the release's source hash.

    PYTHONPATH=. python scripts/rerender_agent_reports.py [agent_s0 agent_s1 agent_s2]
"""
from __future__ import annotations

import json
import sys
from datetime import date

from avval import RESULTS_DIR
from avval.estimation import find_estimation
from avval.policy import LearnedACC
from avval.provenance import provenance
from avval.report import write_search_report
from avval.store import Store


def logged_submission(campaign: str) -> tuple[dict, list[dict]]:
    """The agent's final `submit_report` input and its successful `test_predicate` results."""
    transcript = json.loads((RESULTS_DIR / f"transcript_{campaign}.json")
                            .read_text(encoding="utf-8"))
    submit = [e["input"] for e in transcript if e.get("tool") == "submit_report"]
    if not submit:
        raise SystemExit(f"{campaign}: no submit_report in the transcript")
    tests = []
    for e in transcript:
        if e.get("tool") == "test_predicate":
            out = json.loads(e["output"])  # failed calls return {"error": ...} and were not logged
            if "error" not in out:
                tests.append(out)
    return submit[-1], tests


def main(campaigns: list[str]) -> None:
    store, policy = Store(), LearnedACC.load()
    estimation = find_estimation(store, policy)
    if estimation is None:
        raise SystemExit("No estimation campaign matches the current release; run estimate first.")
    current = provenance(policy)["code_sha256"]
    for campaign in campaigns:
        submission, tests = logged_submission(campaign)
        model = json.loads((RESULTS_DIR / f"usage_{campaign}.json")
                           .read_text(encoding="utf-8"))["model"]
        recorded = store.campaign_info(campaign)[0]["provenance"]["code_sha256"]
        path = write_search_report(
            store, campaign, summary=submission["summary"],
            triggering_conditions=submission["triggering_conditions"],
            author=f"agent ({model})", estimation=estimation, include_verdict=True,
            predicate_tests=tests)
        note = (f"> **Re-rendered on {date.today()}** by `scripts/rerender_agent_reports.py`, to "
                f"attach the release verdict. The agent ran under source hash `{recorded[:12]}`; "
                f"this release's is `{current[:12]}`. The policy and the parsed configuration "
                f"are identical and no simulation module changed (`docs/agent.md`). The "
                f"summary, triggering conditions and hypothesis tests are the agent's own, from "
                f"its logged submission; everything else is recomputed from the stored runs.")
        text = path.read_text(encoding="utf-8")
        text = text.replace("\n## Summary\n", f"\n{note}\n\n## Summary\n", 1)
        path.write_text(text, encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main(sys.argv[1:] or ["agent_s0", "agent_s1", "agent_s2"])
