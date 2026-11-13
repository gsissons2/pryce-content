# Formats

## redesign-carousel / redesign-video
Same `data` for both (see SPEC.md). Carousel: hook, before (numbered problems), after (numbered fixes), side by side, call to action. Video: about 20 seconds, hook, problems one at a time with markers popping on the phone, a wipe to the redesign, fixes one at a time, end card.

## stat-carousel / stat-video
`data.slides` is a list. The last slide should be `{ "type": "cta" }`. `data.footer` is the default source line at the bottom of each slide; any slide can override it with `foot`. The video version animates the same slides (numbers count up, bars grow, dots fill) at about 3 seconds each.

| type | props |
|---|---|
| `bignum` | `kicker`, `value` (e.g. "11"), `unit` (e.g. "seconds."), `body` |
| `statement` | `kicker`, `title`, optional `facts: [{label, value}]` (two-column), optional `body` |
| `bars` | `kicker`, `title`, `bars: [{label, value, highlight}]`, `unit` (e.g. " s"), `max`, optional `marker: {value, note}` (dashed line, e.g. Google's 2.5 s bar) |
| `percent` | `kicker`, `value` ("47.2%"), `body`, `dots` (default 20) |
| `loading` | `title`, `body`, `button`, `status` (illustration of a page still loading) |
| `list` | `kicker`, `title`, `items: [{title, body}]` (up to 3) |
| `cta` | `cta`: "review" (default), "redesign", or a custom `{kicker, headline, sub, label, url}` |
