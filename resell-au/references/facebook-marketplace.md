# Facebook Marketplace — Field Map & Listing Guide

## Create listing URL

```
https://www.facebook.com/marketplace/create/item
```

Log in must be active in the attached Chrome before navigating here. If you
land on a login wall, stop and surface the issue to the user (see
`browser-automation.md` stop-the-line conditions).

## Field fill order

FB Marketplace validates fields progressively — fill in this order to avoid
state errors:

1. **Photos** — upload first; the form won't let you change category until at
   least one photo is present on some variants of the form.
2. **Category** — select from the category mapping table below.
3. **Title** — from the approved ad copy.
4. **Price** — AUD, numbers only (no `$` sign — the field adds currency).
5. **Condition** — see condition mapping table below.
6. **Description** — from the approved ad copy.
7. **Location** — type suburb; select the autocomplete suggestion. Do not
   free-type the full address.
8. **"Hide from friends" toggle** — leave at user's current default (do not
   change this setting; it varies by account preference).

After filling Location, the form typically shows a preview / "Next" button
leading to the review screen. Snapshot to confirm you're on the review screen
before stopping.

## Photo rules

- Maximum **10 photos** per listing (free accounts). Do not attempt an 11th
  upload — FB may silently drop it or show an error.
- First photo uploaded becomes the **lead/cover photo** in search results.
  Upload in lexical filename order so the user controls ordering by naming
  files `01-front.jpg`, `02-side.jpg`, etc.
- Supported formats: JPEG, PNG, HEIC. Minimum resolution: 500 × 500 px.
  Maximum file size: 10 MB per photo.
- Do not upload watermarked, AI-generated, or stock photos — image similarity
  detection will flag the listing.

## Category mapping

Use the closest match. FB's category tree changes occasionally; re-snapshot
after selecting a top-level category to confirm the subcategory options.

| Item type | Top-level | Subcategory |
|---|---|---|
| Furniture (sofa, table, chair, shelf) | Home & Garden | Furniture |
| Appliances (washing machine, fridge) | Home & Garden | Appliances |
| Small appliances (blender, toaster) | Home & Garden | Household items |
| Garden / outdoor furniture | Home & Garden | Outdoor |
| TVs, monitors | Electronics | TVs & Video |
| Computers, laptops | Electronics | Computers & Tablets |
| Phones | Electronics | Phones |
| Audio (speakers, headphones) | Electronics | Audio |
| Power tools | Tools | Power Tools |
| Hand tools | Tools | Hand Tools |
| Bikes (push bikes) | Sporting Goods | Bikes |
| Exercise equipment | Sporting Goods | Exercise & Fitness |
| Kids / baby gear | Baby & Kids | Baby & Toddler Gear |
| Clothing, shoes | Clothing & Accessories | (match gender/type) |
| Books, music, games | Entertainment | Books, Movies & Music |
| Cars, utes, vans | Vehicles | Cars & Trucks |
| BBQs, outdoor cooking | Home & Garden | Outdoor |
| Camera / photography | Electronics | Cameras |

If an item doesn't fit cleanly, prefer the broader top-level category over an
incorrect subcategory — buyers search the top level more often.

## Condition mapping

| User's condition | FB condition field value |
|---|---|
| New / sealed | New |
| Like new / barely used | Used - Like New |
| Good condition | Used - Good |
| Fair / some wear | Used - Fair |
| For parts / broken | Used - For Parts |

Do not select "New" for any item that has been opened, even if unused.

## Captcha / login-wall / 2FA handling

- **Login wall on navigate**: session expired. Screenshot + stop. User must
  log in again in the browser.
- **"Confirm your identity" / checkpoint screen**: a Meta security check.
  Screenshot + stop. User must complete it. Do not retry.
- **Photo upload captcha**: rare but occurs on new accounts or burst uploads.
  Screenshot + stop.
- **"You're temporarily blocked from listing"**: rate-limit. Screenshot + stop.
  Tell the user to wait at least 1 hour (Meta's typical block window) before
  continuing.

## Ban-avoidance hygiene

These reduce (not eliminate) the risk of account action:

- **One listing at a time, 30–90 s apart.** Never post multiple items in rapid
  succession.
- **Don't list more than ~5–10 items per week from a new account.** Older
  accounts with transaction history tolerate higher volumes.
- **Real photos only.** Stock / AI-generated images trigger image classifiers.
- **No phone numbers or external URLs in the description.** FB strips them and
  the listing may be demoted or rejected.
- **Accurate category.** Miscategorised listings get flagged by other users and
  may be removed.
- **Don't relist the same item within 7 days.** Even if you delete and
  repost, FB's hashing catches it.
- **Use the pickup location accurately.** Mismatched locations (profile address
  vs. listing suburb) are a soft signal.
- **Hide from friends** — this is a per-listing toggle. Some users prefer it
  on to avoid acquaintances seeing everything they sell; leave at the user's
  existing default.

## DOM stability notes

FB Marketplace's DOM changes frequently (sometimes monthly during A/B tests).
The accessibility tree snapshot is the reliable interaction layer — never
hardcode element IDs or CSS classes.

Known volatile areas:
- The photos upload element changes between `input[type=file]` and a custom
  component; always locate it from the snapshot's file-input UID.
- The category dropdown sometimes renders as a searchable text field; if the
  snapshot shows a text input, type the category name and select from the
  autocomplete.
- The price field sometimes adds a currency prefix automatically; don't
  double-enter the `$`.

If the snapshot doesn't match expectations: stop, screenshot, ask the user to
confirm the new layout before proceeding (see `browser-automation.md` Step 2).
