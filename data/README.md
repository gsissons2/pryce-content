# Data bank

`lighthouse-2026.json` is Pryce Digital's own study: 12,621 Australian small-business websites, one Google Lighthouse mobile run each (May 2026). Public write-up: prycedigital.com/research/australian-small-business-websites-2026

Stat posts may only use numbers from this file. `engine/factcheck.py` checks every number in a stat spec against it and fails the render if one is missing.

Caveats that must be respected in copy:
- Lab numbers come from a simulated mid-range phone on a throttled connection. Say "Google's lab test", not "real visitors".
- Real-visitor (CrUX) numbers exist for only about 23% of sites (`core_web_vitals.field_crux_where_available`). Say so when using them.
- One run per site. Talk about medians and groups, never about a single named site.
- Platform is detected from the code with a confidence score. "Custom" means no known platform was found, not "custom-built".
- Only use industry, state or platform groups with n of 80 or more (the `by_industry_min_n80` and `by_state_min_n100` lists already apply this).
