# KRISHI-DRISHTI: Complete Wiring Schematics & Pinout Guide

## 1. Controller Wand (ESP32 DevKit V1)

| Peripheral | DevKit V1 Pin | Function / Notes |
| :--- | :--- | :--- |
| **SSD1306 OLED SDA** | **GPIO 21** | I2C Data Line (Address `0x3C`) |
| **SSD1306 OLED SCL** | **GPIO 22** | I2C Clock Line |
| **SSD1306 OLED VCC** | **3V3** or **VIN** | Power Supply (3.3V or 5V from USB) |
| **SSD1306 OLED GND** | **GND** | Ground |
| **[MULTIFUNCTION] Pushbutton** | **GPIO 27** | Terminal 1 to GPIO 27, Terminal 2 to GND (`INPUT_PULLUP`). Unified 1-Button UI: Short tap = Next screen (or scan on home); Long hold (>=800ms) = Trigger Scan from anywhere. |
| **DHT11 Data Pin** | **GPIO 18** | Digital Telemetry Pin (with 10k pull-up or 3-pin module) |
| **DHT11 VCC & GND** | **3V3 & GND** | Sensor Power |

---

## 2. Camera Unit (AI-Thinker ESP32-CAM)

When using the **ESP32-CAM-MB Programmer Shield**, no manual jumper wires are required for programming or power! The camera snaps directly onto the shield headers.

| Subsystem | Pin on ESP-32S | Hardware Assignment |
| :--- | :--- | :--- |
| **OV5640 / GC2145 D0 - D7** | GPIO 5, 18, 19, 21, 36, 39, 34, 35 | 8-bit DVP Parallel Video Bus |
| **Camera PCLK / XCLK** | GPIO 22, GPIO 0 | Pixel Clock & External Master Clock |
| **Camera VSYNC / HREF** | GPIO 25, GPIO 23 | Vertical Sync & Horizontal Reference |
| **Camera I2C (SIOC / SIOD)** | GPIO 27, GPIO 26 | Sensor Configuration SCCB Bus |
| **Camera Power Down (PWDN)**| GPIO 32 | Hardware sleep control |
| **MicroSD Slot** | GPIO 14 (CLK), GPIO 15 (CMD), GPIO 2 (DAT0) | 1-bit high-speed SD_MMC Mode |
| **High-Power Flash LED** | **GPIO 4** | Transistor-driven ultra-bright white LED |
| **Power Input** | **5V & GND** | Regulated USB 5V via AMS1117-3.3 |
