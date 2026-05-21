# Chrome Setup for Resell AU

One-time setup: launch a dedicated Chrome instance and log in to Facebook
Marketplace. Do this once; cookies and 2FA trust persist across runs.

## Why a dedicated Chrome, not your daily browser

- Lower blast radius if the FB account ever gets soft-flagged.
- Agent can only see tabs in the attached Chrome — your normal browsing stays
  private.
- The user-data-dir is stable across runs, so login sessions persist.

## Step 1 — Launch the dedicated Chrome

Quit any existing instance running on port 9222 first, then:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.resell-au-chrome" \
  --no-first-run \
  --no-default-browser-check
```

Keep this terminal open (or run it as a background process). The Chrome window
will open normally.

**On Windows:**

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%USERPROFILE%\.resell-au-chrome" ^
  --no-first-run
```

## Step 2 — Log in to Facebook Marketplace once

In the newly opened Chrome window (not your regular browser):

1. Go to https://www.facebook.com/marketplace and log in with your Facebook
   account. Complete any 2FA prompts. You should land on the Marketplace feed.

That's it. The session is now stored in `~/.resell-au-chrome`. You won't
need to log in again unless you clear that directory or the session expires
(Facebook sessions can last months).

## Step 3 — Verify the agent can attach

Run `/resell-au` and let Phase 0 run. It issues a `list_pages` MCP call to
port 9222. If Chrome is reachable you'll see the open tab list. If not, you'll
see the error below.

## Troubleshooting

**"Connection refused on port 9222"**
Chrome is not running with remote debugging. Launch it with the command above.

**"Multiple instances — port already in use"**
Another Chrome (or Chromium) is already on port 9222. Find and quit it:
```bash
lsof -ti :9222 | xargs kill -9
```
Then relaunch with the command above.

**"Logged out on FB"**
Open the dedicated Chrome manually (it's already launched), navigate to
Facebook Marketplace, and log in again. Sessions occasionally expire; this is
normal.

**"Chrome profile reset / can't find ~/.resell-au-chrome"**
The user-data-dir was deleted or the path changed. Relaunch Chrome with the
correct `--user-data-dir` and repeat Step 2.

## Fallback — let the MCP manage its own profile

If you don't want to manage a dedicated Chrome, the Chrome DevTools MCP can
auto-launch its own Chromium instance. The trade-off: the profile resets
between MCP restarts, so you'll need to log in each run and handle 2FA live
every time. Not recommended for regular use.

## Security note

The `--remote-debugging-port=9222` flag means any process on your machine
with localhost access can control this Chrome. Only run it when actively
listing items. Close/relaunch when done. Do not expose port 9222 beyond
localhost (don't forward it through SSH or a tunnel).
