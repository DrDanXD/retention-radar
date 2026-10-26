# Data handling

Member activity at a clinic is protected health information. This repo contains **no real member data**. Everything in `data/` and `docs/demo.json` comes from the simulator.

How a pilot would handle real data:

* **Minimum necessary.** The engine needs dates and counts: sync days, message timestamps and sender, habit adherence, lab booking dates, call dates. It does not need lab values, diagnoses, notes or message text.
* **Runs inside the clinic's environment.** The engine is a Python package with no outbound calls, except the optional draft step.
* **Drafts and the model provider.** The draft prompt contains a first name, the coach's name, days to renewal and the reason lines (for example "Wearable has not synced in 16 days"). With real members this should only run under a business associate agreement with the model provider. Otherwise use the built-in template, which makes no external calls. Template mode is the default when no API key is set.
* **Coach in the loop.** Nothing is ever sent to a member automatically.
* **No raw data in logs.** The CLI prints names and reasons only for flagged members, for the person running it.

This is a design note, not legal advice. A clinic should run any pilot through its own compliance review.
