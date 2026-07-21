# First-Time iOS Developer Setup

This guide details the setup required to run the local FastAPI backend on macOS and deploy the iOS HealthKit exporter app to a physical iPhone.

## Prerequisites

- macOS with Xcode installed (Xcode project deployment target set to iOS 26.2)
- Python 3.11+ with the project virtual environment
- A physical iPhone running a supported iOS version signed into an Apple ID
- Apple Watch data recorded in Apple Health
- iPhone and Mac joined to the same Tailnet, with ACLs allowing the iPhone to reach the Mac

*Note: HealthKit data export requires a physical iOS device. The iOS Simulator can be used for UI and contract testing, but cannot perform real HealthKit data sync.*

## Backend Setup

Start the backend from the repository root:

```bash
scripts/start_backend.sh
```

By default, the server listens on `0.0.0.0:7996`. Environment overrides are supported:

```bash
HEALTH_QUANT_SERVER_HOST=0.0.0.0 HEALTH_QUANT_SERVER_PORT=7996 scripts/start_backend.sh
```

Verify backend health from your Mac (example command using synthetic local address):

```bash
curl http://localhost:7996/health
```

FastAPI exposes unauthenticated raw endpoints (`GET`, `POST`, `DELETE`). The supported deployment model is a single Tailnet: the iPhone reaches the Mac only through its Tailscale address, while device identity, transport encryption, and access control come from Tailscale and its ACLs. Do not expose this service on a public or ordinary LAN address. If the endpoint fails to respond, verify the Tailscale connection, ACL policy, macOS firewall, and service port.

## Xcode Configuration & Signing

Open `HealthQuantification/HealthQuantification.xcodeproj` in Xcode:

1. Sign into Xcode via **Settings -> Accounts**.
2. Select your Developer Team under **Signing & Capabilities**.
3. Change the App target **Bundle Identifier** to a unique prefix under your control (e.g., synthetic placeholder `com.example.HealthQuantificationIOS`).
4. Update the test target Bundle Identifiers if required by Xcode.
5. Keep **Automatically manage signing** enabled.

*Bundle Identifiers must be globally unique in Apple's developer system. Update the default placeholder before building.*

## iPhone Setup

Before deploying from Xcode to a physical device:

1. Enable Developer Mode on the iPhone (**Settings -> Privacy & Security -> Developer Mode**), then restart the device.
2. If iOS displays an untrusted developer prompt upon launching the app, trust your account under **Settings -> General -> VPN & Device Management**.
3. Launch the app and approve the HealthKit permission prompts.

## Server URL Configuration

Do not set `http://localhost:7996` inside the iOS app UI. On iOS, `localhost` resolves to the iPhone itself.

Set the Server URL in the iOS app to your Mac's Tailscale IP (the following synthetic IP demonstrates the format):

```text
http://100.x.x.x:7996
```

The backend server must be listening on `0.0.0.0` or on the specific network interface address accessible by the iPhone.

## Common Failure Modes

| Symptom | Cause | Resolution |
|---|---|---|
| Xcode deployment fails or hangs | Developer Mode disabled on iPhone | Enable Developer Mode in Settings and restart phone |
| Provisioning profile error | Missing Apple ID in Xcode | Add Apple ID in Xcode Settings -> Accounts |
| App ID registration error | Bundle Identifier collision | Change Bundle Identifier to a custom namespace |
| App installed but export fails | Server URL set to `localhost` or a LAN IP | Update Server URL to Mac Tailscale IP |
| Connection refused on export | Port mismatch or backend down | Ensure backend is running and port matches `7996` |

## Contribution Guidelines

Do not commit machine-specific credentials, Team IDs, or local network IP addresses to Git. Keep configuration parameters and examples synthetic and generic in committed documentation.
