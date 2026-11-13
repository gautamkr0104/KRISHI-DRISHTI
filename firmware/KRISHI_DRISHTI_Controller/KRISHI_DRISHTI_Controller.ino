/*
  ==============================================================================
  KRISHI-DRISHTI (Krishi-Drishti) - Farmer-Friendly Controller Wand Firmware v2.3
  Target Hardware: ESP32 DevKit V1 + SSD1306 OLED (128x64 I2C) + DHT11
  Networking: Connects as Wi-Fi Station to SoftAP "KRISHI-DRISHTI" @ 192.168.4.1
  Author: Gautam Kumar / KRISHI-DRISHTI Project
  ==============================================================================

  Hardware Pinout:
    OLED SDA  -> GPIO 21 (I2C Data)
    OLED SCL  -> GPIO 22 (I2C Clock)
    SCAN Btn  -> GPIO 27 (to GND, INPUT_PULLUP) -> Triggers camera capture & AI flow
    NEXT Btn  -> GPIO 26 (to GND, INPUT_PULLUP) -> Cycles OLED pages
    DHT11     -> GPIO 18 (Digital Sensor, VCC to 3.3V, GND to GND)
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include "MicroclimateTracker.h"
#include <ArduinoJson.h>

// -----------------------------------------------------------------
// HARDWARE DEFINITIONS
// -----------------------------------------------------------------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define OLED_ADDRESS 0x3C

#define SCAN_BUTTON 27
#define NEXT_BUTTON 26
#define DHT_PIN 18
#define DHT_TYPE DHT11

// -----------------------------------------------------------------
// NETWORK CONFIGURATION
// -----------------------------------------------------------------
const char* AP_SSID = "KRISHI-DRISHTI";
const char* AP_PASS = "12345678";
const char* CAMERA_HOST = "192.168.4.1";

// Static IP Configuration (bypasses slow DHCP for instant 300ms connection)
const IPAddress WAND_STATIC_IP(192, 168, 4, 2);
const IPAddress WAND_GATEWAY(192, 168, 4, 1);
const IPAddress WAND_SUBNET(255, 255, 255, 0);
const IPAddress WAND_DNS(192, 168, 4, 1);

const String URL_CAPTURE     = "http://192.168.4.1/api/capture";
const String URL_DIAG_LATEST = "http://192.168.4.1/api/diagnosis/latest";
const String URL_STATUS      = "http://192.168.4.1/api/status";

// -----------------------------------------------------------------
// PERIPHERAL OBJECTS
// -----------------------------------------------------------------
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
DHT dht(DHT_PIN, DHT_TYPE);

// -----------------------------------------------------------------
// SYSTEM & DIAGNOSIS STATE
// -----------------------------------------------------------------
enum WandState {
  STATE_IDLE,
  STATE_CAPTURING,
  STATE_AWAITING_AI,
  STATE_DIAGNOSIS_RECEIVED,
  STATE_TIMEOUT,
  STATE_ERROR
};

WandState currentState = STATE_IDLE;
int activePage = 0; // 0: Ready/Home, 1: Canopy Climate, 2: Diagnosis, 3: Cure & Action, 4: Wand Status
const int TOTAL_PAGES = 5;

// Microclimate Telemetry
float currentTemp = 0.0;
float currentHum = 0.0;
bool dhtConnected = false;
unsigned long lastDhtReadMs = 0;
const unsigned long DHT_INTERVAL_MS = 2000;

// Scan & Telemetry Tracking
uint32_t activeScanId = 0;
uint32_t totalScansRecorded = 0;
String systemStatusMsg = "Wand Ready";

// Diagnosis Data (Received from Phone AI Engine via Camera Bridge)
bool hasDiagnosis = false;
uint32_t diagScanId = 0;
String diagCrop = "Potato";
String diagDisease = "Healthy Leaf";
float diagConfidence = 99.4;
String diagStatus = "OPTIMAL";
String diagOrganic = "No action needed";
String diagChemical = "Leaf is healthy";

// Non-Blocking AI Polling Timers
unsigned long aiWaitStartMs = 0;
unsigned long lastAiPollMs = 0;
const unsigned long AI_TIMEOUT_MS = 14000;
const unsigned long AI_POLL_INTERVAL_MS = 1000;

// Modular Microclimate Epidemiological Risk Tracker
MicroclimateTracker microclimateTracker(6.0f);

// Wi-Fi Status Tracking
bool wifiConnected = false;
unsigned long lastWifiCheckMs = 0;

// Button Debounce & Hold Detection
bool prevScan = HIGH;
bool prevNext = HIGH;
unsigned long lastScanMs = 0;
unsigned long lastNextMs = 0;
unsigned long scanPressStartMs = 0;
const unsigned long DEBOUNCE_MS = 250;

// Demo scan index for offline testing while camera package arrives
int demoIndex = 0;

// -----------------------------------------------------------------
// DISPLAY DRAWING PRIMITIVES (FARMER FRIENDLY)
// -----------------------------------------------------------------
void drawHeader(const char* title, const char* pageIndicator) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(title);
  
  if (pageIndicator != NULL) {
    display.setCursor(85, 0);
    display.print(pageIndicator);
  }
  display.drawLine(0, 9, 127, 9, SSD1306_WHITE);
}

void drawFooter(const char* actionPrompt = "[SCAN]Snap [NEXT]>") {
  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 55);
  display.print(actionPrompt);
  display.display();
}

// -----------------------------------------------------------------
// SCREEN 0: READY TO SCAN (FARMER HOME SCREEN)
// The wand boots directly to this screen.
// An uneducated farmer does not need to navigate anywhere to scan!
// -----------------------------------------------------------------
void renderPage0_ReadyToScan() {
  const char* badge = (WiFi.status() == WL_CONNECTED) ? "CAM:OK" : "STANDBY";
  drawHeader("KRISHI-DRISHTI", badge);

  // Big, clear "READY" text in center
  display.setTextSize(2);
  display.setCursor(34, 13);
  display.print("READY");

  display.setTextSize(1);
  display.setCursor(10, 31);
  display.print("Point Wand At Leaf");

  // Environmental summary line
  display.setCursor(0, 42);
  if (dhtConnected) {
    display.printf("%.0fC|%.0f%% ", currentTemp, currentHum);
    if (microclimateTracker.getRiskLevel() == RISK_LEVEL_HIGH_LATE) {
      display.print("RISK:HIGH!");
    } else if (microclimateTracker.getRiskLevel() == RISK_LEVEL_MODERATE_EARLY) {
      display.print("RISK:WARM");
    } else {
      display.print("Air:Safe");
    }
  } else {
    display.print("DHT11: Initializing...");
  }

  drawFooter("[PRESS SCAN BUTTON]");
}

// -----------------------------------------------------------------
// SCREEN 1: CANOPY CLIMATE (DETAILED WEATHER & EPIDEMIOLOGY)
// -----------------------------------------------------------------
void renderPage1_Canopy() {
  drawHeader("CANOPY CLIMATE", "1/5");

  if (dhtConnected) {
    display.setTextSize(1);
    display.setCursor(0, 13);
    display.printf("Temp: %.1f C", currentTemp);

    display.setCursor(0, 23);
    display.printf("Hum : %.1f %% RH", currentHum);

    display.setCursor(0, 33);
    display.print(microclimateTracker.getRiskStatusString());

    display.setCursor(0, 43);
    if (currentHum >= 85.0f && currentTemp >= 15.0f && currentTemp <= 22.0f) {
      display.print("Warn: Blight incubation");
    } else if (currentHum < 60.0f) {
      display.print("Air: Dry, low spore risk");
    } else {
      display.print("Air: Moderate condition");
    }
  } else {
    display.setTextSize(1);
    display.setCursor(0, 16);
    display.print("DHT11 Disconnected");
    display.setCursor(0, 28);
    display.print("Sensor pin: GPIO 18");
    display.setCursor(0, 40);
    display.print("Check 3.3V / Data wire");
  }

  drawFooter("[SCAN]Snap [NEXT]>");
}

// -----------------------------------------------------------------
// SCREEN 2: AI DIAGNOSIS (LEAF HEALTH RESULT)
// -----------------------------------------------------------------
void renderPage2_Diagnosis() {
  drawHeader("AI DIAGNOSIS", "2/5");

  if (hasDiagnosis) {
    display.setTextSize(1);
    display.setCursor(0, 12);
    display.printf("Crop : %s", diagCrop.c_str());

    display.setCursor(0, 22);
    display.printf("Diag : %s", diagDisease.c_str());

    display.setCursor(0, 32);
    if (diagStatus == "UNCERTAIN") {
      display.print("Conf : LOW / AMBIGUOUS");
      display.setCursor(0, 42);
      display.print("Stat : RETAKE PHOTO");
    } else {
      display.printf("Conf : %.1f%%", diagConfidence);
      display.setCursor(0, 42);
      display.printf("Stat : %s", diagStatus.c_str());
    }
  } else {
    display.setTextSize(1);
    display.setCursor(0, 18);
    display.print("No Scan Recorded Yet");
    display.setCursor(0, 30);
    display.print("Point at leaf & click");
    display.setCursor(0, 42);
    display.print("green [SCAN] button");
  }

  drawFooter("[SCAN]New  [NEXT]Cure");
}

// -----------------------------------------------------------------
// SCREEN 3: AGRONOMIC CURE & ACTION
// -----------------------------------------------------------------
void renderPage3_Cure() {
  drawHeader("ORGANIC CURE", "3/5");

  if (hasDiagnosis && diagStatus != "UNCERTAIN") {
    display.setTextSize(1);
    display.setCursor(0, 12);
    if (diagDisease.indexOf("Healthy") >= 0) {
      display.print("Status: CROP HEALTHY");
      display.setCursor(0, 23);
      display.print("No fungicide required!");
      display.setCursor(0, 34);
      display.print("Maintain regular care");
      display.setCursor(0, 44);
      display.print("and soil moisture.");
    } else {
      display.print("Action: SPRAY ORGANIC");
      display.setCursor(0, 22);
      display.print(diagOrganic.substring(0, 21));

      display.setCursor(0, 32);
      if (diagChemical.startsWith("ADVISORY") || diagChemical.startsWith("WITHHELD")) {
        display.print("Note: Low Humidity");
        display.setCursor(0, 42);
        display.print("Delay chemical spray!");
      } else {
        display.print("Alt: ");
        display.print(diagChemical.substring(0, 16));
        display.setCursor(0, 42);
        display.print("Isolate sick leaves!");
      }
    }
  } else if (diagStatus == "UNCERTAIN") {
    display.setTextSize(1);
    display.setCursor(0, 14);
    display.print("Image unclear/shadowed");
    display.setCursor(0, 26);
    display.print("1. Keep wand steady");
    display.setCursor(0, 37);
    display.print("2. Put leaf in shroud");
    display.setCursor(0, 46);
    display.print("3. Press SCAN again");
  } else {
    display.setTextSize(1);
    display.setCursor(0, 20);
    display.print("Prescription pending");
    display.setCursor(0, 34);
    display.print("Perform leaf scan");
  }

  drawFooter("[SCAN]Snap [NEXT]>");
}

// -----------------------------------------------------------------
// SCREEN 4: WAND STATUS & CONNECTIVITY
// -----------------------------------------------------------------
void renderPage4_Status() {
  drawHeader("WAND STATUS", "4/5");

  display.setTextSize(1);
  display.setCursor(0, 12);
  display.print("Firmware: v2.3 Simple");

  display.setCursor(0, 22);
  display.print("WiFi    : ");
  if (WiFi.status() == WL_CONNECTED) {
    display.printf("Linked (%ddBm)", WiFi.RSSI());
  } else {
    display.print("Searching CAM");
  }

  display.setCursor(0, 32);
  display.print("Camera  : ");
  display.print((WiFi.status() == WL_CONNECTED) ? "192.168.4.1" : "Standby");

  display.setCursor(0, 42);
  display.printf("Scans   : %u Completed", totalScansRecorded);

  drawFooter("[SCAN]Snap [NEXT]Home");
}

void renderActivePage() {
  if (activePage == 0) renderPage0_ReadyToScan();
  else if (activePage == 1) renderPage1_Canopy();
  else if (activePage == 2) renderPage2_Diagnosis();
  else if (activePage == 3) renderPage3_Cure();
  else renderPage4_Status();
}

// -----------------------------------------------------------------
// SENSOR TELEMETRY
// -----------------------------------------------------------------
void readSensors() {
  if (millis() - lastDhtReadMs > DHT_INTERVAL_MS || lastDhtReadMs == 0) {
    lastDhtReadMs = millis();
    yield();
    float h = dht.readHumidity();
    yield();
    float t = dht.readTemperature();
    yield();
    if (!isnan(h) && !isnan(t) && h > 0.0 && h <= 100.0) {
      currentHum = h;
      currentTemp = t;
      dhtConnected = true;
    } else {
      dhtConnected = false;
    }
    microclimateTracker.update(millis(), currentTemp, currentHum, dhtConnected);
  }
}

// -----------------------------------------------------------------
// WI-FI CONNECTION MANAGEMENT
// -----------------------------------------------------------------
void ensureWiFiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiConnected) {
      wifiConnected = true;
      Serial.println("[WIFI] Connected to Camera SoftAP: KRISHI-DRISHTI! IP: " + WiFi.localIP().toString());
      renderActivePage();
    }
    return;
  }

  if (wifiConnected) {
    wifiConnected = false;
    Serial.println("[WIFI] Disconnected from Camera SoftAP.");
    renderActivePage();
  }

  // Non-blocking reconnect: check every 8s without thrashing the Wi-Fi driver
  if (lastWifiCheckMs == 0 || millis() - lastWifiCheckMs > 8000) {
    lastWifiCheckMs = millis();
    Serial.println("[WIFI] Seeking Camera SoftAP: KRISHI-DRISHTI...");
    WiFi.reconnect();
  }
}

// -----------------------------------------------------------------
// OFFLINE DEMO SCAN (Allows user to test all screens while waiting for ESP32-CAM)
// -----------------------------------------------------------------
void triggerDemoScan() {
  demoIndex = (demoIndex + 1) % 3;
  totalScansRecorded++;
  activeScanId = totalScansRecorded;
  hasDiagnosis = true;

  display.clearDisplay();
  drawHeader("DEMO TEST SCAN", "..");
  display.setTextSize(1);
  display.setCursor(14, 18);
  display.print("* DEMO TESTING *");
  display.drawRect(8, 14, 112, 16, SSD1306_WHITE);
  display.setCursor(6, 36);
  display.print("Simulating AI Model...");
  display.setCursor(4, 46);
  display.print("Testing Screen Carousel");
  display.display();
  delay(1200);

  if (demoIndex == 0) {
    diagCrop = "Potato";
    diagDisease = "Healthy Leaf";
    diagConfidence = 99.8;
    diagStatus = "OPTIMAL";
    diagOrganic = "Crop is healthy";
    diagChemical = "No spray needed";
  } else if (demoIndex == 1) {
    diagCrop = "Tomato";
    diagDisease = "Early Blight";
    diagConfidence = 96.4;
    diagStatus = "WARNING";
    diagOrganic = "Neem Oil 5ml/L spray";
    diagChemical = "Mancozeb 2g/L (Bio alt)";
  } else {
    diagCrop = "Potato";
    diagDisease = "Late Blight";
    diagConfidence = 99.2;
    diagStatus = "SEVERE";
    diagOrganic = "Trichoderma viride";
    diagChemical = (currentHum < 85.0f && dhtConnected) ?
      "ADVISORY: Low humidity (<85%)" : "Copper Oxychloride (2g/L)";
  }

  systemStatusMsg = "Demo OK";
  currentState = STATE_DIAGNOSIS_RECEIVED;
  activePage = 2; // Jump directly to Diagnosis page!
  renderActivePage();
}

// -----------------------------------------------------------------
// REAL SCAN EXECUTION & AI RETRIEVAL PIPELINE
// -----------------------------------------------------------------
void pollAiDiagnosisNonBlocking() {
  HTTPClient httpDiag;
  httpDiag.begin(URL_DIAG_LATEST);
  httpDiag.setTimeout(1500);
  int diagCode = httpDiag.GET();

  if (diagCode == 200) {
    String diagPayload = httpDiag.getString();
    StaticJsonDocument<1024> diagDoc;
    DeserializationError dErr = deserializeJson(diagDoc, diagPayload);

    if (!dErr && diagDoc["ready"] == true) {
      uint32_t retScanId = diagDoc["scan_id"];
      if (retScanId == activeScanId) {
        diagCrop = diagDoc["crop"].as<String>();
        diagDisease = diagDoc["disease"].as<String>();
        diagConfidence = diagDoc["confidence"].as<float>();
        diagStatus = diagDoc["status"].as<String>();
        diagOrganic = diagDoc["organic"].as<String>();
        String rawChem = diagDoc["chemical"].as<String>();

        // Scientific microclimate cross-gating
        if ((diagDisease.indexOf("Late Blight") >= 0 || diagDisease.indexOf("Blight") >= 0) &&
            dhtConnected && currentHum < 85.0f && microclimateTracker.getRiskLevel() == RISK_LEVEL_LOW) {
          diagChemical = "ADVISORY: Low RH (" + String((int)currentHum) + "%). Unfavorable for sporulation.";
          Serial.printf("[SAFETY GATE] Low RH (%.1f%%) issued advisory for %s!\n",
                        currentHum, diagDisease.c_str());
        } else {
          diagChemical = rawChem;
        }

        diagScanId = retScanId;
        hasDiagnosis = true;
        systemStatusMsg = "Diagnosis OK";
        currentState = STATE_DIAGNOSIS_RECEIVED;
        activePage = 2; // Auto-transition to diagnosis result page
        renderActivePage();

        Serial.printf("[AI OK] Diagnosis synced for Scan #%u: %s %s (%.1f%%)\n",
                      retScanId, diagCrop.c_str(), diagDisease.c_str(), diagConfidence);
      }
    }
  }
  httpDiag.end();
}

void handleAiTimeoutNonBlocking() {
  Serial.printf("[AI TIMEOUT] No phone diagnosis for Scan #%u after %lu ms\n", activeScanId, AI_TIMEOUT_MS);
  systemStatusMsg = "AI Timeout";
  hasDiagnosis = true;
  diagScanId = activeScanId;
  diagCrop = "Tomato/Potato";
  diagDisease = "Awaiting Phone";
  diagConfidence = 0.0;
  diagStatus = "UNCERTAIN";
  diagOrganic = "Check phone browser at 192.168.4.1";
  diagChemical = "Ensure AI Server is Started";

  currentState = STATE_TIMEOUT;
  activePage = 2;
  renderActivePage();
}

void triggerRealScan() {
  if (currentState == STATE_CAPTURING || currentState == STATE_AWAITING_AI) {
    Serial.println("[SCAN] Scan already in progress. Ignoring duplicate trigger.");
    return;
  }

  // If camera is not yet connected (e.g. package not arrived or turned off)
  if (WiFi.status() != WL_CONNECTED) {
    systemStatusMsg = "Standby (No Cam)";
    display.clearDisplay();
    drawHeader("CAMERA STANDBY", "!");
    display.setTextSize(1);
    display.setCursor(0, 14);
    display.print("ESP32-CAM Not Linked");
    display.setCursor(0, 24);
    display.print("(Waiting for package)");
    display.setCursor(0, 36);
    if (dhtConnected) {
      display.printf("Canopy: %.1fC | %.0f%% RH", currentTemp, currentHum);
    } else {
      display.print("Canopy Sensor: Active");
    }
    display.setCursor(0, 46);
    display.print("Hold SCAN for Demo");
    display.display();
    delay(2200);
    renderActivePage();
    return;
  }

  currentState = STATE_CAPTURING;
  systemStatusMsg = "Capturing...";

  display.clearDisplay();
  drawHeader("LEAF CAPTURE", "..");
  display.setTextSize(1);
  display.setCursor(14, 18);
  display.print("* CAPTURING *");
  display.drawRect(8, 14, 112, 16, SSD1306_WHITE);
  display.setCursor(10, 36);
  display.print("Triggering Camera...");
  display.setCursor(10, 46);
  display.print("Hold wand steady");
  display.display();

  HTTPClient http;
  String captureUrl = URL_CAPTURE;
  if (dhtConnected && currentHum > 0.0) {
    captureUrl += "?temp=" + String(currentTemp, 1) + "&hum=" + String(currentHum, 1);
  }
  http.begin(captureUrl);
  http.setTimeout(4000);
  int httpCode = http.GET();

  if (httpCode != 200) {
    Serial.printf("[SCAN] Camera capture failed! HTTP code: %d\n", httpCode);
    systemStatusMsg = "Capture Failed";
    String errPayload = http.getString();
    http.end();

    display.clearDisplay();
    drawHeader("CAPTURE NOTICE", "!");
    display.setTextSize(1);
    display.setCursor(0, 16);
    display.printf("Camera returned %d", httpCode);
    display.setCursor(0, 28);
    if (errPayload.indexOf("sd_storage_offline") >= 0 || errPayload.indexOf("sd_offline") >= 0) {
      display.print("MicroSD Not Ready");
      display.setCursor(0, 40);
      display.print("Insert FAT32 Card");
    } else if (errPayload.indexOf("camera_offline") >= 0) {
      display.print("Sensor Offline");
      display.setCursor(0, 40);
      display.print("Check Lens Cable");
    } else {
      display.print("Check SD Card & Lens");
      display.setCursor(0, 40);
      display.print("Hold SCAN for Demo");
    }
    drawFooter("[PRESS SCAN TO RETRY]");
    delay(2000);
    currentState = STATE_IDLE;
    renderActivePage();
    return;
  }

  String payload = http.getString();
  http.end();
  Serial.printf("[SCAN] Camera response: %s\n", payload.c_str());

  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err || doc["status"] != "success") {
    Serial.println("[SCAN] Failed to parse camera JSON response!");
    systemStatusMsg = "Parse Error";
    currentState = STATE_IDLE;
    renderActivePage();
    return;
  }

  activeScanId = doc["scan_id"];
  totalScansRecorded = activeScanId;
  
  // Transition to non-blocking AWAITING_AI state
  currentState = STATE_AWAITING_AI;
  aiWaitStartMs = millis();
  lastAiPollMs = 0;
  systemStatusMsg = "AI Analyzing";

  display.clearDisplay();
  drawHeader("AI DIAGNOSIS", "..");
  display.setTextSize(1);
  display.setCursor(0, 16);
  display.printf("Scan #%u Captured", activeScanId);
  display.setCursor(0, 28);
  display.print("Phone AI Co-Processor");
  display.setCursor(0, 40);
  display.print("Running MobileNetV3...");
  display.display();
}

// -----------------------------------------------------------------
// ARDUINO SETUP
// -----------------------------------------------------------------
void setup() {
  setCpuFrequencyMhz(240);

  Serial.begin(115200);
  delay(150);

  Serial.println("\n========================================");
  Serial.println("  KRISHI-DRISHTI :: Controller Wand v2.3");
  Serial.println("  Farmer-Friendly Edge Telemetry Core");
  Serial.println("========================================");
  Serial.flush();

  pinMode(SCAN_BUTTON, INPUT_PULLUP);
  pinMode(NEXT_BUTTON, INPUT_PULLUP);

  // 1. Initialize OLED Display FIRST so user immediately sees bright live state
  Serial.println("[INIT] Step 1: I2C & OLED..."); Serial.flush();
  Wire.begin(21, 22);
  Wire.setClock(100000); // 100 kHz standard mode: rock-solid on breadboards

  bool oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) {
    Serial.println("[OLED] Address 0x3C failed, trying 0x3D..."); Serial.flush();
    oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  }

  if (oledOk) {
    Serial.println("[OLED] SSD1306 Initialized successfully."); Serial.flush();
    display.dim(false); // Bright, high-visibility contrast
    display.ssd1306_command(SSD1306_SETCONTRAST);
    display.ssd1306_command(0xCF); // Maximum contrast register value
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);

    // Centered Title Bar
    display.setTextSize(1);
    display.setCursor(22, 6);
    display.print("KRISHI-DRISHTI");
    display.drawLine(6, 17, 121, 17, SSD1306_WHITE);

    display.setCursor(13, 23);
    display.print("Plant Health Wand");

    display.setCursor(19, 36);
    display.print("Smart Wand v2.3");

    display.setCursor(10, 49);
    display.print("Linking to Cam...");
    display.display();
  } else {
    Serial.println("[OLED ERROR] Display not detected on I2C bus (Check SDA:21, SCL:22)!"); Serial.flush();
  }

  // 2. Wi-Fi Station Bringup
  Serial.println("[INIT] Step 2: Wi-Fi Radio Bringup..."); Serial.flush();
  WiFi.mode(WIFI_STA);
  WiFi.config(WAND_STATIC_IP, WAND_GATEWAY, WAND_SUBNET, WAND_DNS);
  Serial.printf("[WIFI] Connecting to SoftAP: '%s'...\n", AP_SSID); Serial.flush();
  WiFi.begin(AP_SSID, AP_PASS);

  // 3. Sensor bringup
  Serial.println("[INIT] Step 3: DHT11 Sensor..."); Serial.flush();
  dht.begin();

  // 6. Non-blocking quick link check for splash banner
  unsigned long startLinkMs = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - startLinkMs < 1500)) {
    delay(50);
    yield();
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("[WIFI] Cam Linked! IP: " + WiFi.localIP().toString()); Serial.flush();
    if (oledOk) {
      display.fillRect(0, 48, 128, 16, SSD1306_BLACK);
      display.setCursor(16, 49);
      display.print("CAM LINKED! [OK]");
      display.display();
      delay(400);
    }
  } else {
    Serial.println("[WIFI] Cam not detected yet. Starting in Standby Mode..."); Serial.flush();
    if (oledOk) {
      display.fillRect(0, 48, 128, 16, SSD1306_BLACK);
      display.setCursor(12, 49);
      display.print("STANDBY READY [OK]");
      display.display();
      delay(300);
    }
  }

  // Boot directly to the friendly READY TO SCAN home screen!
  activePage = 0;
  renderActivePage();
  lastWifiCheckMs = millis();
  Serial.println("[SYSTEM] Setup completed successfully. Wand is live."); Serial.flush();
}

// -----------------------------------------------------------------
// ARDUINO MAIN LOOP
// -----------------------------------------------------------------
void loop() {
  ensureWiFiConnected();
  readSensors();

  // Non-blocking Asynchronous AI State Machine
  if (currentState == STATE_AWAITING_AI) {
    if (millis() - lastAiPollMs >= AI_POLL_INTERVAL_MS) {
      lastAiPollMs = millis();
      pollAiDiagnosisNonBlocking();
    }
    if (currentState == STATE_AWAITING_AI && (millis() - aiWaitStartMs >= AI_TIMEOUT_MS)) {
      handleAiTimeoutNonBlocking();
    }
  }

  bool sScan = digitalRead(SCAN_BUTTON);
  bool sNext = digitalRead(NEXT_BUTTON);

  // BUTTON 1: SCAN (GPIO 27)
  // Pressing SCAN starts real capture if camera is connected.
  // If camera is offline, short press shows friendly notice, long press (>1.2s) triggers DEMO TEST!
  if (prevScan == HIGH && sScan == LOW) {
    scanPressStartMs = millis();
  } else if (prevScan == LOW && sScan == HIGH) {
    unsigned long pressDuration = millis() - scanPressStartMs;
    if (pressDuration >= DEBOUNCE_MS) {
      if (WiFi.status() != WL_CONNECTED && pressDuration >= 1200) {
        Serial.println("[USER] Long-press on SCAN detected -> Triggering DEMO TEST SCAN!");
        triggerDemoScan();
      } else {
        Serial.println("[USER] SCAN Button Pressed -> Initiating scan sequence...");
        triggerRealScan();
      }
    }
  }

  // BUTTON 2: NEXT (GPIO 26)
  // Uneducated farmer controls pages at their own pace. Zero sudden auto-flipping!
  if (prevNext == HIGH && sNext == LOW && millis() - lastNextMs > DEBOUNCE_MS) {
    lastNextMs = millis();
    activePage = (activePage + 1) % TOTAL_PAGES;
    Serial.printf("[USER] NEXT Button Pressed -> Showing Page %d/%d\n", activePage + 1, TOTAL_PAGES);
    renderActivePage();
  }

  prevScan = sScan;
  prevNext = sNext;

  // Update environmental telemetry on Screen 0 & 1 periodically without flashing
  static unsigned long lastOledRefreshMs = 0;
  if (currentState == STATE_IDLE && (activePage == 0 || activePage == 1)) {
    if (millis() - lastOledRefreshMs > 3000) {
      lastOledRefreshMs = millis();
      renderActivePage();
    }
  }

  delay(20);
}
