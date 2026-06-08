# Standalone Bundle Player Guide

For osu! players who just want to run the predictor — no Python, no setup.

## Download

1. Go to the [latest release](https://github.com/nayutalienx/osu-skill-predictor/releases/latest)
2. Download `osu-skill-predictor-web.zip`
3. Extract the ZIP anywhere (e.g. Desktop or a folder)

## Requirements

- Windows 10+ (64-bit)
- osu! (stable) running in **windowed** or **borderless** mode
- osu! API v2 Client ID and Client Secret

> **Overlay requires windowed/borderless mode.** Fullscreen overlays are not supported — the overlay window will not render on top of an exclusive fullscreen application.

### Getting osu! API Credentials

1. Go to [osu! Account Settings > OAuth](https://osu.ppy.sh/home/account/edit#oauth)
2. Scroll to "New OAuth Application" and create one
3. Copy the **Client ID** and **Client Secret**

## Quick Start

1. Double-click `osu-skill-predictor-web.exe`
2. Your browser opens automatically to the predictor UI
3. Enter your osu! API **Client ID** and **Client Secret**, then click **Save**
4. The overlay window appears with real-time predictions

That's it. The predictor detects the current beatmap from osu! and shows pass probability and predicted accuracy.

## Overlay

The overlay is a transparent window that floats on top of osu! showing:

- Beatmap title and star rating
- **Pass %** — predicted probability you'll pass the map
- **Acc %** — predicted accuracy if you pass

### Positioning

In the web UI, click the settings area to configure:

| Setting | Options |
|---------|---------|
| Position | Top-Left, Top-Right, Bottom-Left, Bottom-Right, or Custom |
| Custom X / Y | Pixel coordinates (offset from chosen corner) |
| Display | Which monitor the overlay appears on |

Changes apply within ~10 seconds to the running overlay.

### Offline Mode

If you don't have osu! API credentials or prefer not to use them:

1. Open the web UI
2. Enable **Offline Mode**
3. Enter your stats manually: PP, accuracy, playcount, rank, country
4. Optionally enter a nickname

In offline mode, predictions use your manually-entered stats instead of live API data.

## Manual Nickname

Instead of relying on automatic username detection via tosu (the bundled memory reader):

1. Type your osu! username in the **Nickname** field
2. Click **Refresh** next to it
3. Your stats are fetched from the osu! API and displayed

This is useful when:
- You have multiple osu! accounts signed into the client
- tosu auto-detection picks the wrong user
- You want predictions based on a specific account

## Manual Refresh

Click the **Refresh** button in the web UI to force-update your cached stats from the osu! API. Stats are cached for 1 day by default.

## Shutdown

- **Web UI**: click the **Shutdown** button
- **Desktop**: double-click `shutdown.bat` or `shutdown.py`

Both methods stop the server, overlay, and tosu memory reader.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Overlay not visible | Make sure osu! is in **windowed** or **borderless** mode (not fullscreen). Check the overlay position settings in the UI. |
| No predictions shown | Ensure the osu! API credentials are correct. Try clicking **Refresh**. Make sure a beatmap is active (song select or playing). |
| Blank page in browser | Wait a few seconds for the server to start. If it persists, restart the exe. |
| Wrong username detected | Use the **Nickname** field to manually set your osu! username. |
| Shutdown stuck | Run `shutdown.bat` to force-close all processes. |
