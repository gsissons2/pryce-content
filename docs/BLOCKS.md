# Phone screen block kit

A screen file (`screens/*.json`) is `{ "business", "state", "theme", "blocks": [...] }`. The renderer draws it at 390 × 844 (an iPhone screen) and scales it into the slide. Anything past 844 px is cut off, which is how "one scroll down" content peeks in.

`theme` keys: `bg`, `ink` (main text), `muted`, `accent`, `line`, `display` (heading font, CSS name), plus `accent2` and `box` for the booking kit.

Give a block an `id` when a marker should point at it. Markers use `mark` (the id) and an optional `anchor`: `right` (default), `left`, `center`, `top-right`, or `{ "x": 0.8, "y": 0.4 }` as fractions of the block.

Fonts available: Inter, Fraunces, Archivo, DM Sans, DM Serif Display, Playfair Display (italic), Montserrat, Open Sans, Roboto. Add more by extending `assets/fonts` and `engine/kit/fonts.css`.

## Shared
| type | what it draws | main props |
|---|---|---|
| `status` | iOS status bar | `color` |
| `header` | logo + menu icon | `logo`, `logoFont`, `logoSize`, `logoWeight`, `logoItalic`, `color`, `sub` (line under the logo), `right` (text instead of the menu icon), `border`, `bg`, `height`, or `logoParts` + `logoIcon: "drop"` for a stacked trade logo |
| `group` | vertical stack of blocks | `padding`, `gap`, `bg`, `blocks` |
| `spacer` | fills space (or `h` px) | `h` |
| `photoOverlay` | full-width photo with a shade, holds other blocks on top | `photo`, `height`, `shade`, `blocks` |
| `h1`, `para` | heading, paragraph | `text`, `size`, `weight`, `font`, `color` |
| `photo` | rounded photo | `photo`, `height`, `radius` |
| `button` | full-width button with arrow | `text`, `bg`, `color`, `arrow` |

## Cafe kit
| type | | props |
|---|---|---|
| `sliderCaption`, `sliderControls` | the "Welcome to" slider text, arrows and dots (before) | `kicker`, `title`, `tag` / `dots`, `active` |
| `pdfStrip` | "View our menu (PDF)" band (before) | `text`, `color`, `bg` |
| `igLoading` | Instagram feed still loading (before) | `title`, `sub` |
| `openRow` | "Open now · until 3pm" pill + hours (after) | `pill`, `pillBg`, `dot`, `sub` |
| `menuList` | menu as text with prices (after) | `title`, `link`, `items: [[name, price]]` |
| `map` | "Find us" map (after) | `title` |

## Trades kit
| type | | props |
|---|---|---|
| `stockHero` | stock photo with blue overlay and "Learn more" (before) | `photo`, `overlay`, `title`, `sub`, `button`, `buttonBg` |
| `longForm` | long quote form (before) | `title`, `titleColor`, `intro`, `rows: [[label, label], [label]]` |
| `chip` | "Available now" pill (after) | `text`, `bg`, `dot` |
| `jobPhotos` | three real-work photos (after) | `photos` |
| `quoteForm` | 3-field quote card (after) | `title`, `sub`, `fields`, `button` |
| `stickyCall` | call button pinned to the bottom (after) | `text`, `bg`, `glass` |

## Booking kit
| type | | props |
|---|---|---|
| `steps` | 6-step booking progress bar (before) | `items`, `active`, `activeColor` |
| `engineForm` | generic booking engine form (before). Sub-ids: `<id>-card`, `<id>-button`, `<id>-note` | `title`, `rows`, `button`, `buttonBg`, `note`, `secure` |
| `caption` | line of text on a photo | `text` |
| `bookingCard` | dates, guests, rate, book button (after). Sub-ids: `dates`, `rate`, `book` | `dates`, `guests`, `room`, `roomSub`, `price`, `button`, `note` |
| `roomCards` | two room cards (after) | `title`, `link`, `rooms` |

New industry: design the before and after screens in Framer first (project "Pryce social mockups (concepts)"), then add the blocks here so they render the same.
