"""Self-check: skill files resolve and the app wires up. No API key needed."""
from main import ANALYZE_SCRIPT, PROMPT_FILES, SKILL_DIR, app, health, skill_prompt

assert ANALYZE_SCRIPT.exists(), f"missing {ANALYZE_SCRIPT}"
for rel in PROMPT_FILES:
    assert (SKILL_DIR / rel).exists(), f"missing {rel}"
assert "scoring_rubric" in skill_prompt()
assert health()["skill_found"]
assert {r.path for r in app.routes} >= {"/health", "/analyze"}
print("ok")
