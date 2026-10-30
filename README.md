# Presenter View

Present a poster on the big screen while your speaking notes stay on your laptop only.

- **Poster** (PDF, PNG, JPG, …) goes full screen on the HDMI / second display.
- **Notes** stay on your laptop and are hidden from screen sharing (Zoom, Meet, Teams).
- Sections, next-section preview, timer, clock, black-out screen, adjustable text size.

## Download

Open the **Actions** tab → latest **Build apps** run → download
**Presenter-View-Windows** (`.exe`) or **Presenter-View-Mac** (`.zip`, Apple Silicon).

- **Windows:** if SmartScreen warns, click *More info → Run anyway*.
- **Mac:** first time, right-click the app → *Open* → *Open*.

## Presenting with HDMI

Set the display to **Extend**, not Mirror/Duplicate, or the audience will see your notes.

- Mac: *System Settings → Displays → Extended display*
- Windows: press **Win + P → Extend**

Then click **Start presenting**.

| Key | Action |
|---|---|
| → ↓ Space Page Down (clicker) | Next section |
| ← ↑ Page Up | Previous section |
| B | Black out the audience screen |
| Esc | Stop presenting |

## Notes format

Click **Edit notes** and start each section with `# Title`:

```
# Introduction
Greet everyone.

# Results
Lead with the biggest number.
```

## Run from source

```
pip install -r requirements.txt
python presenter_notes.py
```
