# Home Assistant on the E drive

VELA uses Home Assistant OS as the local smart-home control plane. On Windows,
Home Assistant OS runs in a Generation 2 Hyper-V virtual machine. Its virtual
disk, database, add-ons, backups, and configuration remain under
`E:\HomeAssistant`.

## Host allocation

- 2 virtual CPUs
- 2 GB startup memory
- 1-3 GB dynamic memory
- External bridged network for local device discovery
- Automatic start with Windows
- Secure Boot disabled, as required by the HAOS image

## Installation

1. Enable **SVM Mode** or **AMD-V** in the motherboard UEFI/BIOS.
2. Start Windows and run `E:\HomeAssistant\Install-HomeAssistant.ps1`.
3. Accept the Windows administrator prompt.
4. If Windows asks for one restart after enabling Hyper-V, restart and run the
   same script again.
5. Open `http://homeassistant.local:8123` and finish onboarding.

## Connect VELA

In Home Assistant, open the user profile and create a **Long-Lived Access
Token**. Run `E:\HomeAssistant\Connect-Vela.ps1`; paste the token into the
masked prompt. The token is written only to the ignored local `.env` file.

The first connection is deliberately read-only. After checking all discovered
entities, change `OCU_HOME_ASSISTANT_READ_ONLY=false` to expose governed control
actions. Every state-changing VELA action still requires a single-use
confirmation.

## Xiaomi and Huawei devices

- Add Xiaomi devices through Home Assistant's Xiaomi Home integration.
- Prefer Matter for compatible Xiaomi and Huawei devices.
- Huawei cloud partner APIs require separate partner credentials; do not use
  personal-account cookies or browser-session extraction.
