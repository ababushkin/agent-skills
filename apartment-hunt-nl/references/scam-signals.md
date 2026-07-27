# Scam signals in Facebook housing groups

Read this in Phase 3, alongside `listing-fields.md`. Anything you spot goes into
the post's `scam_signals` array and comes out in the table's Flags column.

Dutch rental groups carry a steady volume of advance-fee fraud: a plausible
listing, an urgent story, and a deposit request before anyone sees the place.
The point of flagging is not to decide for the user — it is to make sure nobody
wires money to a listing that never existed.

## Flag these

| Signal | Write in `scam_signals` | Why |
|---|---|---|
| Deposit, first month, or "reservation fee" asked before a viewing | `deposit before viewing` | The core of the scam. No legitimate Dutch landlord takes money before a viewing and a signed contract. |
| Contact only via WhatsApp, Telegram, or email, "don't comment, DM me" | `WhatsApp only, off-platform` | Moves the conversation somewhere Facebook cannot moderate or record. |
| Landlord is abroad and cannot show the place | `landlord abroad, no viewing` | The classic pretext for keys-by-courier. |
| Viewing refused or endlessly deferred | `no viewing offered` | Same thing, stated differently. |
| Rent far below the going rate for that area and size | `rent well below market` | Bait. Note the figure you compared against, or say the comparison is a rough sense rather than a measurement. |
| Photos look like a catalogue or listing site | `stock photos` | Reverse-image-check is out of scope; flag and say why it looks staged. |
| Account created recently, no history, few friends | `new account` | Visible on the profile without contacting anyone. |
| Identical text posted by different account names | `duplicate text, different poster` | One template worked through several stolen accounts. Cross-post collapse will not catch it, since the author differs. |
| Asks for passport, BSN, or payslips before a viewing | `documents requested up front` | Identity theft, separate from the rent. |
| Pushes for a decision "today, five people are interested" | `urgency pressure` | Standard advance-fee pressure. |
| Deposit above two months' rent | `deposit above two months` | Legal maximum in the Netherlands is two months for most contracts. |

## Flag, but it is not fraud

Some things are worth showing the user without calling them scams:

- **`anti-kraak`** — property guardianship. Real, legal, cheap, and comes with
  roughly two weeks' notice and almost no tenant protection.
- **Agency fee (`bemiddelingskosten`)** — charging a tenant a mediation fee is
  generally not allowed when the agency also acts for the landlord. Flag it as
  `agency fee charged` so the user can push back.
- **`geen inschrijving`** — already a hard-requirement fail, so it does not need
  a scam flag too. Do not double-report it.

## How to phrase it

Keep each entry short and literal — it has to fit a table cell. Say what the
post did, not how it made you feel: `deposit before viewing`, not `suspicious
behaviour`.

Never assert fraud as fact. In the Phase 5 summary, write "asks for the deposit
before a viewing — I would not contact this one", not "this is a scammer". You
are reporting what the post says.

One signal is worth a look; three is worth skipping. Say which listings you
would not contact and why, and leave the decision with the user.
