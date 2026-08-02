# Reading a Facebook group feed

The mechanics behind Phase 2 of `apartment-hunt-nl`. Read this before sweeping.

## Sort by new posts, always

A group's default feed is sorted by relevance, which surfaces whatever got the
most comments — usually a week-old thread. Housing posts get answered in hours,
so relevance sorting shows you exactly the listings that are already gone.

Two ways to get the chronological feed:

1. Append `?sorting_setting=CHRONOLOGICAL` to the group URL. Fastest, and it
   survives a reload.
2. Click the sort control in the feed header (labelled "Most relevant" or
   "Meest relevant") and choose "New posts" / "Nieuwste berichten".

Take a snapshot after either one and confirm the control now reads "New posts"
before you trust the order. If it doesn't, the feed is still relevance-sorted
and your lookback window means nothing.

## The extractor

Post bodies do not come out of the accessibility tree. One post costs roughly
150 lines of it, and the tree carries Facebook's anti-scraping decoys: the
author-and-timestamp line is split into ~55 single-character nodes reordered by
CSS, and hidden spans repeat the word "Facebook" through the post body. Reading
a busy group that way does not finish.

Run this per scroll batch instead. It returns one compact object per rendered
post:

```js
async () => {
  const isSeeMore = b => /^(See more|Meer weergeven)$/.test((b.innerText || '').trim());
  const btns = [...document.querySelectorAll('div[role="button"], span[role="button"]')].filter(isSeeMore);
  btns.forEach(b => b.click());
  await new Promise(r => setTimeout(r, 1200));

  const posts = [];
  for (const btn of document.querySelectorAll('[aria-label^="Actions for this post by"]')) {
    const author = btn.getAttribute('aria-label').replace('Actions for this post by ', '').trim();
    let box = btn, id = null;
    for (let i = 0; i < 12 && box.parentElement; i++) {
      box = box.parentElement;
      for (const a of box.querySelectorAll('a[href]')) {
        const h = a.getAttribute('href') || '';
        const m = h.match(/\/posts\/(\d+)/) || h.match(/\/permalink\/(\d+)/) || h.match(/set=pcb\.(\d+)/);
        if (m) { id = m[1]; break; }
      }
      if (id) break;
    }
    let posted = null;
    for (const a of box.querySelectorAll('a[aria-label], a[title]')) {
      const v = a.getAttribute('aria-label') || a.getAttribute('title') || '';
      if (/\d{4}/.test(v) && /(day,|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/.test(v)) { posted = v; break; }
    }
    const msg = box.querySelector('[data-ad-rendering-role="story_message"]');
    posts.push({
      post_id: id, author, posted,
      photos: box.querySelectorAll('a[href*="/photo/"]').length,
      text: msg ? msg.innerText.replace(/\nSee more$/, '').trim() : null
    });
  }
  return posts;
}
```

Why each anchor is the one it is:

- **`[aria-label^="Actions for this post by"]`** identifies a post. `role="article"`
  does not — comments carry it too, and the post container itself is unlabelled.
  The label also yields the author cleanly, which the visible header does not.
- **Climbing to the first ancestor holding a `/posts/`, `/permalink/`, or
  `set=pcb.` link** finds the post container and its ID together. Photo links
  carry `set=pcb.<post_id>`, so a post with photos yields an ID even when the
  timestamp permalink is missing.
- **`[data-ad-rendering-role="story_message"]`** is the post body. Taking
  `innerText` of the whole container instead picks up the decoy spans.
- **The `aria-label` on the timestamp link** is an absolute date
  ("Wednesday, July 29, 2026 at 12:59 PM"). Use it; the visible "3h" is
  assembled from the scrambled character nodes.

Accumulate across batches into a map keyed by `post_id` — consecutive batches
overlap, and the feed drops posts once they are far enough behind.

If a batch returns `count: 0` while posts are plainly on screen, the anchors
have changed. Stop and show the user, per hard rule 5.

## Scrolling a virtualised feed

The feed recycles DOM nodes: posts scrolled far enough off-screen are destroyed,
and their snapshot uids are reused for posts further down. Two consequences:

- **Extract as you scroll.** Read each batch into the run file before scrolling
  again. Do not scroll to the bottom and then try to read everything.
- **Never hold a uid across a scroll.** Re-snapshot after every scroll and match
  posts by permalink ID, which is stable.

Scroll one viewport at a time with `evaluate_script`
(`window.scrollBy(0, window.innerHeight)`), wait 8–15 s between scrolls per hard
rule 4, and stop when a post's timestamp is older than the lookback window.
Facebook occasionally interleaves an out-of-order post, so stop after **two
consecutive** posts past the window, not the first one.

## Expanding "See more"

Long posts are truncated at roughly 250 characters behind a "See more" / "Meer
weergeven" button. The truncation point almost always falls before the price and
the availability dates, which are what the whole sweep is for.

Click every "See more" in the current viewport before extracting. Expanding does
not reorder the feed, so the uids stay valid until the next scroll.

If a post is still truncated after the click, open its permalink in a new tab
and read it there rather than guessing at the missing half.

## Getting the permalink ID

The permalink ID is the dedup key for the whole skill, so it has to be exact.

Each post's timestamp is a link to its permalink, of the form
`https://www.facebook.com/groups/<group_id>/posts/<post_id>/`. Pull the href,
not the visible text. Some posts use the older
`/permalink/<post_id>/` or `/groups/<gid>/posts/<pid>/?comment_id=...` form —
take the `<post_id>` segment and drop any query string.

If a post has no reachable permalink (rare — usually a shared post or a poll),
record `post_id` as `null` and let the fingerprint carry the dedup. Do not
invent an ID: `triage.py` derives a stable `fp:` one from the fingerprint, which
is what the user then uses to shortlist or reject it.

## What a post looks like in the accessibility tree

Roughly, per post:

- an `article` node wrapping the whole post,
- a link with the author's name (the profile link — take the display text, not
  the URL, since profile URLs vary in form for the same person),
- a link whose text is a relative timestamp ("3h", "Yesterday", "22 July") and
  whose href is the permalink,
- a text block holding the body,
- zero or more image nodes,
- a row of Like / Comment / Share buttons.

Relative timestamps need converting to an absolute date. Hover text or the
`title`/`aria-label` on the timestamp link usually carries the full date; prefer
that over arithmetic on "3h".

**If a group's feed does not match this shape, stop.** Show the user the
snapshot and ask. Facebook reshapes the feed regularly, and a wrong guess about
which node is the body produces a table full of confident nonsense.

## Things that will interrupt a sweep

| What you see | What to do |
|---|---|
| Captcha or "confirm it's you" checkpoint | Stop. Hand control to the user (hard rule 3). |
| "You're temporarily blocked" | Stop, and tell the user how many groups were done. |
| Group asks membership questions again | Skip the group; do not answer them. |
| A login wall mid-sweep | Stop and ask the user to log in; the session expired. |
| Feed shows "No posts yet" | Confirm the sort control, then mark the group swept with zero posts. |

Pinned posts and group-rules announcements sit at the top of every feed
regardless of sort. Skip anything pinned — it is never a listing.
