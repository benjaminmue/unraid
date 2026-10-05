# benjaminmue's Unraid apps

Community Applications hub for my Unraid apps. This repo only holds the CA
metadata; each app's code lives in its own repository.

- **Obsidian Sync Station** (Docker): https://obsidian-sync.bebamu.ch, source https://github.com/benjaminmue/obsidian-sync-station
  - `templates/obsidian-sync-station.xml`: release channel, image `:latest`, port 8484
  - `templates/obsidian-sync-station-beta.xml`: beta channel, image `:beta`, port 8494
- **OneDrive Sync Station** (Docker): https://onedrive-sync.bebamu.ch, source https://github.com/benjaminmue/OneDrive-Sync-Station
  - `templates/onedrive-sync-station.xml`: release channel, image `:latest`, port 8485
  - `templates/onedrive-sync-station-beta.xml`: beta channel, image `:beta`, port 8495
- **Unraid Themer** (plugin, beta): https://themer.bebamu.ch, source https://github.com/benjaminmue/unraid-themer

## Channels

Every Docker app has two Community Applications entries:

- **Release** (`<app>`): image `:latest`, built from version tags `vX.Y.Z` on the app's `main`
  branch. Use this one for daily use.
- **Beta** (`<app>-beta`, shown with the BETA banner): image `:beta`, built from every push to
  the app's `beta` branch. Pre-release builds for testing; they may break.

Every change goes to beta first, is tested there, and is released afterwards. The beta
templates default to their own port, their own appdata folder and their own data paths, so
both entries can run side by side. Never point the beta and the release container at the
same `/config` or the same synced data path: two sync clients writing into one folder cause
conflicts and can lose data.

## Checks

Every pull request runs `.github/scripts/validate.py`: XML validity, the channel rules
above, unique names and default ports, matching `TemplateURL`, no em-dashes, and that
every referenced image tag exists on GHCR. A release template can therefore only be
merged once its `:latest` image has been published. `main` accepts changes only through
pull requests with this check green.

Registered in Community Applications as *benjaminmue's Repository*.
