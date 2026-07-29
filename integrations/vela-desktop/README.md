# VELA Desktop

VELA Desktop is the native Windows interface for OpenClaw-Ultimate. It is an Electron
application that connects to the local OpenClaw Gateway and therefore keeps existing
sessions, DeepSeek model configuration, tools, attachments and ComfyUI integration.

## Development

```powershell
npm ci
npm start
```

## Build

```powershell
npm run build
```

The portable executable is written to `dist/VELA-Desktop.exe`.

Do not commit `node_modules/` or `dist/`.
