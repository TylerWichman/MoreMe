"""MoreMe eval harness (AD-006). Standard library only.

Modules:
    common      paths, constants, analyze.py loader, split helpers, JSON writing
    tasks       task list (eval/tasks/tasks.json) and prompt rendering
    extraction  pre-registered draft extraction and invalid-unit detection
    evidence    stream-json invocation evidence and the per-call skill invariant
    leakage     scratch-dir asserts and the 12-word shingle test
    ledger      unit keys, done records, resume and torn-tail handling
    runner      the 3-arm draft runner on eval/lib/childrun.py
    scoring     attribution, delta_fw, char3_cosine, exposed_distance per draft
    stats       paired task bootstrap, stratified by persona
    validity    draft-length validity gate on dev data
    prereg      pre-registration hash gate
    report      report generator with the pre-registered README sentences
"""
