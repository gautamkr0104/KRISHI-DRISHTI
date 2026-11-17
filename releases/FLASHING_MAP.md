# KRISHI-DRISHTI v2.5 EDGE :: Firmware Binary Flashing Map

This guide outlines the exact memory offsets and flashing commands for both the **ESP32-CAM** optical gateway and the **ESP32 Controller Wand**.

---

## 1. ESP32-CAM (Optical Neural Gateway)

* **Chip:** ESP32-D0WD-V3 (Revision 3.1)
* **Flash Size:** 4MB
* **Flash Mode:** `dio` | **Baud Rate:** `460800`

### Binary Flash Address Allocation Table:
| Binary File | Flash Address | Partition / Purpose | Description |
| :--- | :--- | :--- | :--- |
| `KRISHI_DRISHTI_Camera.ino.bootloader.bin` | `0x1000` | Bootloader | Second-stage hardware bootloader |
| `KRISHI_DRISHTI_Camera.ino.partitions.bin` | `0x8000` | Partition Table | Memory layout (Huge APP / Minimal SPIFFS) |
| `boot_app0.bin` | `0xe000` | Otadata | Boot slot descriptor / OTA selector |
| `KRISHI_DRISHTI_Camera.ino.bin` | `0x10000` | `app0` (Application) | Main ESP32-CAM firmware & Web Daemon |
| **`KRISHI_DRISHTI_Camera.ino.merged.bin`** | **`0x0000`** | **Full Flash Image** | **Unified all-in-one image (Recommended)** |

### Flashing Commands (ESP32-CAM):
```bash
# Option A: Single Unified Image (Easiest & Recommended)
esptool.py --chip esp32 --port COM_PORT --baud 460800 write_flash -z 0x0000 KRISHI_DRISHTI_Camera.ino.merged.bin

# Option B: Multi-File Flashing
esptool.py --chip esp32 --port COM_PORT --baud 460800 --before default_reset --after hard_reset write_flash -z \
  0x1000  KRISHI_DRISHTI_Camera.ino.bootloader.bin \
  0x8000  KRISHI_DRISHTI_Camera.ino.partitions.bin \
  0xe000  boot_app0.bin \
  0x10000 KRISHI_DRISHTI_Camera.ino.bin
```

> **Note for Flashing ESP32-CAM:** Connect **GPIO 0 to GND** and momentarily press the **RST** button to enter download mode before flashing. After flashing completes, disconnect GPIO 0 from GND and press RST once more.

---

## 2. ESP32 Controller Wand (Telemetry & OLED Wand)

* **Chip:** ESP32-WROOM-32
* **Flash Size:** 4MB
* **Flash Mode:** `dio` | **Baud Rate:** `460800`

### Binary Flash Address Allocation Table:
| Binary File | Flash Address | Partition / Purpose | Description |
| :--- | :--- | :--- | :--- |
| `KRISHI_DRISHTI_Controller.ino.bootloader.bin` | `0x1000` | Bootloader | Second-stage bootloader |
| `KRISHI_DRISHTI_Controller.ino.partitions.bin` | `0x8000` | Partition Table | Memory layout |
| `boot_app0.bin` | `0xe000` | Otadata | Boot slot descriptor |
| `KRISHI_DRISHTI_Controller.ino.bin` | `0x10000` | `app0` (Application) | Main Wand firmware (DHT22, SSD1306, ESP-NOW) |
| **`KRISHI_DRISHTI_Controller.ino.merged.bin`** | **`0x0000`** | **Full Flash Image** | **Unified all-in-one image (Recommended)** |

### Flashing Commands (Controller Wand):
```bash
# Option A: Single Unified Image (Recommended)
esptool.py --chip esp32 --port COM_PORT --baud 460800 write_flash -z 0x0000 KRISHI_DRISHTI_Controller.ino.merged.bin

# Option B: Multi-File Flashing
esptool.py --chip esp32 --port COM_PORT --baud 460800 --before default_reset --after hard_reset write_flash -z \
  0x1000  KRISHI_DRISHTI_Controller.ino.bootloader.bin \
  0x8000  KRISHI_DRISHTI_Controller.ino.partitions.bin \
  0xe000  boot_app0.bin \
  0x10000 KRISHI_DRISHTI_Controller.ino.bin
```

---

## 3. MicroSD Card Setup (100% Plug-and-Play)

1. Format any standard MicroSD card (4GB to 32GB) as **FAT32**.
2. Download and extract **`SD_CARD_KRISHI_DRISHTI_READY.zip`** directly to the root of the card.
3. Card root directory should contain:
   ```text
   E:\
   ├── index.html
   ├── krishi_ai_server.html
   ├── krishi_drishti_model.tflite
   ├── labels.json
   ├── README_SD_CARD.txt
   ├── vendor\
   ├── sample_leaves\
   └── scans\
   ```
4. Insert the card into the ESP32-CAM slot. The camera will automatically detect the card in under 1 second on boot!

> **Model build:** `krishi_drishti_model.tflite` sha256 prefix `a2a4c9f6134ec0de` (round-9 mined-hard-negative OE, 2026-11-17: look-alike leakage 224→157, adversarial rings 22/30 withheld, blur 75/75 robust). Previous build: `f48fc157cfe31c5b` (round-8), archived as `krishi_drishti_model_round8_prev.tflite`.

### SD Card Recovery (corruption / RAW filesystem / SD FAIL on boot)

If the card ever shows an unrecognized filesystem (a USB bus drop during a write corrupts the FAT) or the camera reports `SD FAIL`, rebuild it with one command from an **elevated** PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File releases\REBUILD_SD_CARD.ps1 -DriveLetter E
```

The script reformats the card FAT32, re-extracts `SD_CARD_KRISHI_DRISHTI_READY.zip`, and verifies the model SHA-256 against the deployed build. It refuses to touch any disk that is not a small (≤32GB) USB removable device, so it cannot format your hard drives.

**Preventing corruption — always follow these rules:**
1. **Never unplug the card while a write is in progress.** This is the only realistic way the FAT gets corrupted; a clean unplug never damages a healthy card.
2. Use **Safely Remove Hardware** (system tray) or close all Explorer windows on the card before pulling it.
3. If the PC ever reports the card read-only or asks you to scan/fix, stop and run the recovery script instead of clicking through disk repair dialogs.
4. The card image in `SD_CARD_KRISHI_DRISHTI_READY.zip` is always the source of truth — the physical card is disposable and rebuildable in under a minute.
>
> **v2.5 firmware changes:** camera — dashboard pre-filter no longer rejects terminal necrotic blight as "human skin" (brown dying tissue satisfies the skin chromaticity rule; a lesion-texture + darkness + necrosis-dominance exemption now lets genuine haulm frames reach the OE-trained model); wand — reconnect polling window halved to 4 s (worst-case OLED freeze after a camera reboot cut from ~16 s to ~8 s).
