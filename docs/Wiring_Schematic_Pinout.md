# KRISHI-DRISHTI: Complete Wiring Schematics & Pinout Guide

## 1. Controller Wand (ESP32 DevKit V1)

| Peripheral | DevKit V1 Pin | Function / Notes |
| :--- | :--- | :--- |
| **SSD1306 OLED SDA** | **GPIO 21** | I2C Data Line (Address `0x3C`) |
| **SSD1306 OLED SCL** | **GPIO 22** | I2C Clock Line |
| **SSD1306 OLED VCC** | **3V3** or **VIN** | Power Supply (3.3V or 5V from USB) |
| **SSD1306 OLED GND** | **GND** | Ground |
| **[SCAN] Pushbutton** | **GPIO 27** | Terminal 1 to GPIO 27, Terminal 2 to GND (`INPUT_PULLUP`) |
| **[NEXT] Pushbutton** | **GPIO 26** | Terminal 1 to GPIO 26, Terminal 2 to GND (`INPUT_PULLUP`) |
| **DHT11 Data Pin** | **GPIO 18** | Digital Telemetry Pin (with 10k pull-up or 3-pin module) |
| **DHT11 VCC & GND** | **3V3 & GND** | Sensor Power |

---

## 2. Camera Unit (AI-Thinker ESP32-CAM + OV2640)

When using the **ESP32-CAM-MB Programmer Shield**, no manual jumper wires are required for programming or power. The camera snaps directly onto the shield headers.

> **Camera sensor:** OV2640 (standard on AI-Thinker ESP32-CAM)
> **XCLK frequency:** 16 MHz (deliberately set below default 20 MHz to eliminate DMA frame-buffer overflow / `cam_hal: FB-OVF`)

| Subsystem | Pin on ESP32-CAM | Hardware Assignment |
| :--- | :--- | :--- |
| **OV2640 D0-D7 (Y2-Y9)** | GPIO 5, 18, 19, 21, 36, 39, 34, 35 | 8-bit DVP Parallel Video Bus |
| **Camera XCLK** | GPIO 0 | External Master Clock (16 MHz set in firmware) |
| **Camera PCLK** | GPIO 22 | Pixel Clock |
| **Camera VSYNC** | GPIO 25 | Vertical Sync |
| **Camera HREF** | GPIO 23 | Horizontal Reference |
| **Camera I2C SIOD** | GPIO 26 | Sensor SCCB Data |
| **Camera I2C SIOC** | GPIO 27 | Sensor SCCB Clock |
| **Camera Power Down (PWDN)** | GPIO 32 | Hardware sleep control |
| **Camera RESET** | -1 (not used) | Software reset only |
| **MicroSD Slot** | GPIO 14 (CLK), GPIO 15 (CMD), GPIO 2 (DAT0) | 1-bit SD_MMC Mode (FAT32, up to 8 GB) |
| **High-Power Flash LED** | **GPIO 4** | Transistor-driven ultra-bright white LED |
| **Power Input** | **5V & GND** | Regulated USB 5V via AMS1117-3.3 |

---

## 3. Programming Notes

### Controller Wand
- Connect via USB — auto-resets into bootloader (no manual GPIO bridging needed on DevKit V1).

### ESP32-CAM
- **To flash:** Bridge **IO0 to GND**, then press **RST** to enter bootloader mode.
- **To run:** Disconnect IO0 from GND, press **RST** again.
- Using the ESP32-CAM-MB shield handles this automatically via the onboard DTR/RTS lines.
