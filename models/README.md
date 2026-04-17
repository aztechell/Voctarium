# Voctarium Models

This directory stores local runtime models used by the desktop app.

Current supported assets:

- `models\faster-whisper-<model-id>` - local faster-whisper models managed by the app
- `models\rupunct-big` - readable-text punctuation model

Default bundled model:

- `models\faster-whisper-medium`

Models can be prepared in two ways:

- `scripts\setup_assets.ps1` installs the default runtime assets
- the dashboard model manager modal downloads, selects, and deletes faster-whisper models
