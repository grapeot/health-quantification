# First-Time iOS Developer Setup

This project uses a local FastAPI backend on your Mac and a real iPhone app that reads HealthKit data. Most first-time setup failures come from iOS signing or from the phone trying to talk to `localhost`.

## What This Setup Requires

- macOS with Xcode installed
- Python 3.11+ with the project virtualenv installed
- A real iPhone signed into your Apple ID
- Apple Watch data in Apple Health
- A network path from iPhone to Mac, preferably Tailscale

HealthKit export needs a real device. The simulator can build the app, but it is not enough for the full data export path.

## Backend Checklist

Start the backend from the repository root:

```bash
scripts/start_backend.sh
```

By default this listens on `0.0.0.0:7996`, matching `.env.example`, `config.py`, and the README. You can override it explicitly:

```bash
HEALTH_QUANT_SERVER_HOST=0.0.0.0 HEALTH_QUANT_SERVER_PORT=7996 scripts/start_backend.sh
```

Before debugging iOS, verify the backend from the Mac:

```bash
curl http://localhost:7996/health
```

If the iPhone cannot connect, check macOS firewall settings and confirm the phone and Mac are on the same LAN or Tailscale network.

## Xcode Signing Checklist

Open `HealthQuantification/HealthQuantification.xcodeproj` in Xcode and check these items before building to a real iPhone:

- Sign into Xcode under Settings -> Accounts.
- Select your own Team in Signing & Capabilities.
- Change the app target Bundle Identifier to a prefix you control, for example `dev.yourname.HealthQuantificationIOS`.
- Change test target Bundle Identifiers if Xcode asks for signing there too.
- Keep Automatically manage signing enabled unless you have a specific provisioning setup.

Bundle Identifiers are globally unique in Apple Developer systems. The repository default can be occupied by the maintainer's account, so a new developer should expect to change it.

## iPhone Checklist

Before installing from Xcode to a real phone:

- Enable Developer Mode on the iPhone under Settings -> Privacy & Security -> Developer Mode. This requires a restart.
- If iOS blocks the installed app as an untrusted developer app, trust your developer account in Settings -> General -> VPN & Device Management.
- Launch the app once from Xcode and accept HealthKit permission prompts.

## Server URL In The iOS App

Do not use `http://localhost:7996` on a real iPhone. On the phone, `localhost` means the phone itself, not your Mac.

Use one of these instead:

```text
http://192.168.x.x:7996
http://100.x.x.x:7996
```

The first form is your Mac's LAN IP. The second form is your Mac's Tailscale IP. The backend must listen on `0.0.0.0`, or on the specific interface address the iPhone can reach.

## Common Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Xcode waits for the iPhone and then fails | Developer Mode is disabled | Enable Developer Mode and restart the phone |
| `No Accounts` or missing provisioning profile | Xcode is not signed into Apple ID | Add your Apple ID in Xcode Settings -> Accounts |
| App ID cannot be registered | Bundle Identifier is already taken | Change Bundle Identifier to your own prefix |
| App installs but cannot export | Server URL points to `localhost` | Use Mac LAN IP or Tailscale IP |
| Phone connects to wrong port | Backend and app ports differ | Use `7996`, or set both sides to the same explicit port |

## Notes For Contributors

Keep machine-specific values out of committed project files. Bundle Identifier, Team, and Server URL are local setup choices. Documentation should explain how to choose them, while the repository defaults stay generic.
