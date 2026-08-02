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

## Offer, wanted, or neither

`post_kind` comes first, because everything else is wasted effort on a post that
isn't a listing. Most groups run about one wanted post in four.

| Reads like | `post_kind` |
|---|---|
| "For rent", "te huur", "available from 1 September", a price with an address | `offer` |
| "Looking for a room", "op zoek naar", "we are a quiet couple", "my budget is €1,500", a self-introduction with a move-in date | `wanted` |
| "Anyone have an apartment? Comment below", a link farm, a general question | `other` |

The tell is who is offering what. A wanted post describes **the poster** — their
job, their income, how tidy they are, how long they've searched. An offer
describes **the property** — where it is, how big, what it costs.

Two traps:

- A wanted post often quotes a budget in euros per month. That is not a rent.
  Scored as a listing it looks like a bargain with no address.
- A tenant leaving mid-contract, looking for someone to take over, is an
  `offer` — they are offering the place even though the post opens by talking
  about themselves.

## Price

| Dutch / English | Means | `price_basis` |
|---|---|---|
| `all-in`, `alles inbegrepen`, `incl. G/W/L` | rent covers gas, water, electricity | `all-in` |
| `excl. servicekosten`, `kale huur`, `+ servicekosten` | utilities and service charge on top | `excl` |
| `€1500 p/m`, `1500 per maand` with nothing further | not stated | `unknown` |

`price_eur` is the number as written — no currency symbol, no thousands
separator. `1.750` in a Dutch post is one thousand seven hundred and fifty, not
1.75.

**`price_period` says what that number buys**, and getting it wrong is the most
expensive mistake in this file:

| The post says | `price_period` |
|---|---|
| "€1,750 per month", "p/m", "per maand", or nothing at all | `month` |
| "€800 for the period", "€800 for the two weeks", a lump sum next to a date range | `total` |

A short let quoted as a lump sum and recorded as `month` looks like a 75 m²
Amsterdam flat going for €800 a month — which is the exact shape of the fraud in
these groups. A real bargain then gets flagged as a scam and buried. When a post
gives a date range and one price with no "per month" anywhere, it is `total`.

Add `nights` when the post states a night count but no end date. When it gives
both dates, leave `nights` out — the dates are exact.

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

Do not force a short let into months. A fortnight is not `0.5` — leave the month
fields `null` and let the dates carry it. Only `min_months` can fail a listing;
a short maximum term is just a short let, and the date check already reports how
much of the window it covers.

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
