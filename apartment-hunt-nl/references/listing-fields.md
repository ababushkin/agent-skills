# Turning a Dutch rental post into fields

Read this in Phase 3, before extracting anything. Posts are a mix of Dutch and
English, often in the same post.

## The rule that outranks the rest

**If the post does not say it, the field says nothing.** Not the market average,
not what's typical for the area, not what the photos suggest. A blank prompts
the user to ask the poster; a guessed number quietly decides against a flat that
might have been right.

Which blank to write:

| Field kind | Fields | Write |
|---|---|---|
| Text | `city`, `area`, `price_basis`, `furnished`, `registration`, `self_contained` | `"unknown"` |
| Number | `price_eur`, `size_m2`, `rooms`, `min_months`, `max_months` | `null` |
| Date | `available_from`, `available_until` | `null` |
| List | `scam_signals` | `[]` |

`"unknown"` in a number field and the string `"unknown"` in `scam_signals` are
both wrong — the first loses the value, the second turns into eight one-letter
flags in the table.

## Price

| Dutch / English | Means | `price_basis` |
|---|---|---|
| `all-in`, `alles inbegrepen`, `incl. G/W/L` | rent covers gas, water, electricity | `all-in` |
| `excl. servicekosten`, `kale huur`, `+ servicekosten` | utilities and service charge on top | `excl` |
| `€1500 p/m`, `1500 per maand` with nothing further | not stated | `unknown` |

`price_eur` is the monthly rent as a plain number — no currency symbol, no
thousands separator. `1.750` in a Dutch post is one thousand seven hundred and
fifty, not 1.75.

When a post gives a rent **and** a separate service charge ("1400 + 150
servicekosten"), record `price_eur: 1400` and `price_basis: "excl"`. Do not add
them together — the table shows the basis, and adding hides it.

Deposit ("borg", "waarborgsom") is not the rent. A deposit above two months'
rent is a scam signal, not a price field.

## Furnishing

Three Dutch terms, and only one of them means furnished:

| Term | Means | `furnished` |
|---|---|---|
| `gemeubileerd`, `furnished`, `fully furnished` | furniture included | `yes` |
| `gestoffeerd` | floors, curtains, and fittings only — **no furniture** | `no` |
| `kaal`, `ongemeubileerd`, `unfurnished` | bare shell | `no` |
| not mentioned | — | `unknown` |

`gestoffeerd` is the one that catches people out. It is not partly furnished; it
means carpet and curtains. Photos showing furniture do not override the word —
landlords photograph the previous tenant's things.

## Registration

`registration` is `yes` only when the post says registration is possible:
`inschrijving mogelijk`, `registration possible`, `you can register at the
address`, `BRP inschrijving`, `GBA`.

It is `no` for `geen inschrijving`, `inschrijving niet mogelijk`, `no
registration`, `zonder inschrijving`. Anything else is `unknown`.

This matters more than it looks: without registration the user cannot register
with the gemeente at that address, which affects health insurance, banking, and
the BSN.

## Self-contained

`self_contained` is `yes` for an `appartement`, `studio`, `woning`, `huis`, or
anything stating `eigen keuken en badkamer` / `own kitchen and bathroom`.

It is `no` for a `kamer` (room in a shared house), `gedeelde keuken`, `gedeelde
badkamer`, `shared facilities`, `hospita`, or a stated number of housemates.

`anti-kraak` (property guardianship) is usually self-contained but comes with a
two-week notice period and no tenant protection — record `self_contained` from
what the post says and add `anti-kraak` as a scam-adjacent note in
`scam_signals` so it shows in the Flags column. It is not a scam; it is a risk
the user should see.

## Size and rooms

`size_m2` is the floor area as a number: `55 m2`, `55m²`, `55 vierkante meter`.

`rooms` follows the Dutch convention, where the count **includes the living
room**: a `2-kamerappartement` is one bedroom plus a living room. Record the
number as stated; the table shows rooms, not bedrooms. A `studio` is `1`.

## Dates and stay length

`available_from` and `available_until` are ISO dates (`2026-09-01`). Resolve
relative and partial phrasing against the run date:

| Phrase | Becomes |
|---|---|
| `per direct`, `immediately`, `z.s.m.` | the run date |
| `per 1 september`, `from 1 Sept` | that date in the next occurrence of that month |
| `begin oktober` | the 1st of that month |
| `eind februari` | the last day of that month |
| `oktober tot maart` | from the 1st of October, until the 1st of March |

`min_months` and `max_months` are the stay the **landlord** will accept, from
`minimaal 6 maanden`, `max 1 jaar`, `3 tot 6 maanden`, `short stay`. A post
saying only "tijdelijk" (temporary) gives you neither — leave both `null`.

Watch the difference between the availability window and the stay length. "Available
September to March, minimum three months" is
`available_from 2026-09-01`, `available_until 2027-03-01`, `min_months 3`,
`max_months null` — the six-month window is not a maximum.

## City and area

`city` must be exactly `Haarlem` or `Amsterdam` when it is one of those, since
the triage script compares it against the target list as a string. Anything else
goes in as written — `Haarlemmermeer`, `Zandvoort`, `Amstelveen` — and the
script flags it as out of area rather than dropping it.

Neighbourhoods that identify the city when the post never names it:

| Area | City |
|---|---|
| Centrum, Schalkwijk, Haarlem-Noord, Zuiderpolder, Ramplaankwartier, Spaarndam | Haarlem |
| De Pijp, Oud-West, Oud-Zuid, Jordaan, Oost, Noord, Nieuw-West, Bos en Lommer, Zeeburg, Sloterdijk, Watergraafsmeer | Amsterdam |

`Centrum` is ambiguous — both cities have one. Use it only with corroborating
evidence in the post (a street name, a station, the group's own city). If
neither the post nor the group settles it, `city` is `unknown`.

A group named for one city routinely carries posts for the other. Read the city
off the post, never off the group.
