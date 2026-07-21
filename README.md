# Mac Watermark Automation

This package creates a local watched-folder workflow on macOS.

## What it does

1. Watches `~/WatermarkAutomation/Incoming`.
2. Waits until Finder finishes copying each image.
3. Adds a watermark.
4. Saves the result in `~/WatermarkAutomation/Watermarked`.
5. Moves the untouched source into `~/WatermarkAutomation/Originals`.
6. Moves unreadable files into `~/WatermarkAutomation/Failed`.
7. Starts automatically whenever you log in.

Supported inputs include JPG, JPEG, PNG, WebP, TIFF, BMP, HEIC/HEIF, and
AVIF when the installed image libraries can decode the file.

## Install

1. Double-click `install.command`.
2. macOS may require **Control-click → Open** the first time.
3. The installer opens `~/WatermarkAutomation` and `config.json`.
4. Save any setting changes.
5. Double-click `restart.command` after changing settings.

## Use a logo watermark

Create a transparent PNG logo and name it:

`watermark.png`

Place it here:

`~/WatermarkAutomation/watermark.png`

Keep `"mode": "auto"` in `config.json`. The logo will automatically be used.
When no logo exists, the configured text watermark is used.

To force logo mode, set:

```json
"mode": "logo"
```

## Use a text watermark

Set these values in `config.json`:

```json
"mode": "text",
"text": "Your Business Name"
```

## Common settings

```json
"position": "bottom-right",
"opacity": 0.55,
"logo_width_percent": 0.20,
"text_size_percent": 0.045,
"output_suffix": "_watermarked",
"jpeg_quality": 92
```

Available positions:

- `top-left`, `top-center`, `top-right`
- `center-left`, `center`, `center-right`
- `bottom-left`, `bottom-center`, `bottom-right`
- `center`

Opacity is between `0.0` and `1.0`.

## Folder layout

```text
~/WatermarkAutomation/
├── Incoming/
├── Watermarked/
├── Originals/
├── Failed/
├── Logs/
├── config.json
├── watermark.png          # optional
└── watermark_watcher.py
```

## Control files

- `status.command` — shows whether the watcher is running and recent logs.
- `restart.command` — reloads settings and restarts the watcher.
- `process-existing-files-once.command` — processes files already in Incoming.
- `uninstall.command` — removes the background service but keeps all images.

## Troubleshooting

### Nothing happens

Run `status.command` and check:

`~/WatermarkAutomation/Logs/watermark.log`

Also confirm the image was placed directly inside `Incoming`, not in a
subfolder.

### Settings do not change

Run `restart.command` after editing `config.json`.

### HEIC fails

The installer adds HEIC/HEIF support through `pillow-heif`. Check the error log
in `Failed` and reinstall if the Python environment was interrupted.

### macOS blocks a command file

Control-click the `.command` file, choose **Open**, and approve it.

## Uninstall completely

First run `uninstall.command`. After confirming that you no longer need the
images, manually delete:

`~/WatermarkAutomation`
