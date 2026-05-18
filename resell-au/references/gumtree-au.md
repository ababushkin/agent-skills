# Gumtree AU — Field Map & Listing Guide

## Create listing URL

```
https://www.gumtree.com.au/p-post-ad.html
```

Log in must be active in the attached Chrome before navigating here. If you
land on a login wall, stop and surface the issue to the user.

## Field fill order

Gumtree's form is wizard-style — the category tree must be selected first
before the remaining fields appear:

1. **Category tree** — required first; all other fields render after selection.
2. **Title** — from the approved ad copy.
3. **Photos** — upload after title (Gumtree loads the photo widget after the
   category/title step).
4. **Price** — AUD, numbers only.
5. **Condition** — see condition mapping table below.
6. **Description** — from the approved ad copy.
7. **Location** — postcode or suburb; select autocomplete.
8. **Contact preferences** — leave at the account's existing defaults (email /
   phone). Do not change these settings.

After filling all fields a summary/preview page appears. Snapshot to confirm
you're on the review screen before stopping.

## Photo rules

- Maximum **10 photos** for free accounts; **20 with premium** (Gumtree Plus).
  Default to 10 unless the user has confirmed a premium account.
- First photo uploaded becomes the **lead/cover photo**.
  Upload in lexical filename order.
- Supported formats: JPEG, PNG. Maximum file size: 10 MB per photo.
  Minimum resolution: 400 × 300 px.

## Category tree

Gumtree requires both a **category** and a **subcategory** (and sometimes a
third level). Navigate the tree in the snapshot — don't try to jump directly
to a subcategory. After selecting the top-level category, re-snapshot to see
available subcategories.

Common mappings:

| Item type | Category | Subcategory |
|---|---|---|
| Sofa, table, chair | Home & Garden | Furniture |
| Washing machine, fridge, dryer | Home & Garden | Home Appliances |
| Small kitchen appliances | Home & Garden | Kitchen & Dining |
| Garden tools, outdoor furniture | Home & Garden | Garden |
| Laptop, desktop, tablet | Technology | Computers |
| Phone | Technology | Mobile Phones |
| TV, monitor | Technology | TVs |
| Audio (speakers, headphones) | Technology | Audio |
| Camera | Technology | Cameras |
| Power tools | Home & Garden | Tools |
| Push bike | Sport, Fitness & Outdoors | Bikes, Bicycles |
| Exercise equipment | Sport, Fitness & Outdoors | Fitness |
| Baby gear (pram, cot) | Baby & Child | Baby Gear |
| Kids clothing | Baby & Child | Baby Clothing |
| Adult clothing | Fashion | Women's Clothing / Men's Clothing |
| Books | Books, Music & Games | Books |
| Board games, toys | Baby & Child | Toys |
| BBQ / outdoor cooking | Home & Garden | Garden |
| Car | Cars, Vans & Utes | Cars |

If an item maps ambiguously, prefer the more populated parent category — check
comps to see where similar items appear most often.

## Condition mapping

| User's condition | Gumtree condition field value |
|---|---|
| New / sealed | Brand New |
| Like new / barely used | Near New |
| Good condition | Good Condition |
| Fair / some wear | Fair Condition |
| For parts / broken | Parts Only |

## hCaptcha behaviour

Gumtree AU uses hCaptcha on the listing form (especially on new accounts or
after posting several items). hCaptcha presents image-selection challenges.

**Do not attempt to solve hCaptcha.** When it appears:

1. Take a screenshot.
2. Tell the user: *"hCaptcha appeared on Gumtree. Please solve it in the
   browser, then reply `continue`."*
3. Wait. On `continue`, re-snapshot and resume from Step 3 of the loop.

## Location

Gumtree shows location as a text field with postcode/suburb autocomplete.
Type the suburb name or postcode and select the matching suggestion. Do not
free-type the full address — Gumtree geocodes from the selected suggestion.

If the user specified a suburb in their item info, use it. Otherwise use the
user's default Melbourne suburb.

## Contact preferences

Gumtree offers "Show phone number" and "Chat" options. Leave these at whatever
the account's existing defaults are — do not change contact settings on the
user's behalf.

## Pricing

- Gumtree supports both a fixed price and "please contact" (no price).
  Always set a price — "please contact" attracts fewer responses.
- "Negotiable" checkbox: tick it when the ad copy says "ono"; leave unticked
  when "firm".

## Listing duration and relisting

- Standard listings run for 60 days (free). They do not auto-relist.
- After 60 days the listing expires — Gumtree sends an email prompt to relist.
  Relisting resets the clock but counts as a new listing (new timestamp in
  search).
- Note this to the user in the Phase 5 summary: *"Gumtree listings expire in
  60 days; you'll get an email to relist if the item hasn't sold."*

## DOM stability notes

Gumtree's wizard-style form is relatively stable compared to Facebook, but
the category tree nesting occasionally changes as new categories are added.

Snapshot after every category selection — subcategory options render
dynamically and the snapshot must be refreshed to see them.

Known volatile areas:
- The photos widget sometimes appears as a drag-and-drop zone (no standard
  file input). Locate the `upload_file`-compatible input from the snapshot.
  If the snapshot shows only a drag zone, use `evaluate_script` to trigger the
  underlying file-input element. Ask the user if this fails.
- The "Negotiable" checkbox is sometimes replaced by a "Price type" dropdown
  with "Fixed" / "Negotiable" options. Read the snapshot to determine which
  variant is present.

If the snapshot doesn't match expectations: stop, screenshot, ask the user to
confirm the new layout before proceeding (see `browser-automation.md` Step 2).
