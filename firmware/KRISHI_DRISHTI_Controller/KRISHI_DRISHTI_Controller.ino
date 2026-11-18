/*
  ==============================================================================
  KRISHI-DRISHTI (Krishi-Drishti) - Farmer-Friendly Controller Wand Firmware v2.5.1
  Target Hardware: ESP32 DevKit V1 + SSD1306 OLED (128x64 I2C) + DHT11
  Networking: Connects as Wi-Fi Station to SoftAP "KRISHI-DRISHTI" @ 192.168.4.1
  Author: Gautam Kumar / KRISHI-DRISHTI Project
  ==============================================================================

  Hardware Pinout:
    OLED SDA  -> GPIO 21 (I2C Data)
    OLED SCL  -> GPIO 22 (I2C Clock)
    SCAN Btn  -> GPIO 27 (to GND, INPUT_PULLUP) -> Triggers camera capture & AI flow
    NEXT Btn  -> GPIO 26 (to GND, INPUT_PULLUP) -> Cycles OLED pages (optional)
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
#include "esp_private/brownout.h"

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
int wifiRetryCount = 0;

// Button Debounce & Hold Detection
bool prevScan = HIGH;
bool prevNext = HIGH;
unsigned long lastScanMs = 0;
unsigned long lastNextMs = 0;
unsigned long scanPressStartMs = 0;
const unsigned long DEBOUNCE_MS = 250;

// Demo scan index for offline testing
int demoIndex = 0;

// -----------------------------------------------------------------
// CERTAINTY GATE FOR FARMER SAFETY
// If confidence is low, ambiguous, or no leaf detected, NEVER display
// a detailed crop or disease name that could mislead an uneducated farmer!
// -----------------------------------------------------------------
bool isDiagnosisConfident() {
  if (!hasDiagnosis) return false;
  if (currentState == STATE_TIMEOUT) return false;
  if (diagStatus == "UNCERTAIN") return false;
  if (diagConfidence < 65.0f) return false;
  if (diagCrop == "Invalid" || diagCrop == "Uncertain" || diagCrop == "Tomato/Potato") return false;
  if (diagDisease.indexOf("No Leaf") >= 0 || diagDisease.indexOf("Low Confidence") >= 0 || diagDisease.indexOf("Awaiting") >= 0) return false;
  return true;
}

// -----------------------------------------------------------------
// DISPLAY DRAWING PRIMITIVES (FARMER FRIENDLY & ANTI-OVERLAP)
// -----------------------------------------------------------------
void drawHeader(const char* title, const char* pageIndicator) {
  display.clearDisplay();
  display.setTextWrap(false);
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(title);
  
  if (pageIndicator != NULL) {
    int bLen = strlen(pageIndicator);
    int bx = 128 - (bLen * 6);
    display.setCursor(bx, 0);
    display.print(pageIndicator);
  }
  display.drawLine(0, 9, 127, 9, SSD1306_WHITE);
}

void drawFooter(const char* actionPrompt = "[TAP] Next   [SCAN]") {
  display.setTextWrap(false);
  display.drawLine(0, 53, 127, 53, SSD1306_WHITE);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  int pLen = strlen(actionPrompt);
  int px = max(0, (128 - (pLen * 6)) / 2);
  display.setCursor(px, 55);
  display.print(actionPrompt);
  display.display();
}

// -----------------------------------------------------------------
// SCREEN 0: READY TO SCAN (FARMER HOME SCREEN)
// -----------------------------------------------------------------
void renderPage0_ReadyToScan() {
  display.clearDisplay();
  display.setTextWrap(false);

  const char* badge = (WiFi.status() == WL_CONNECTED) ? "CAM:OK" : "STANDBY";
  drawHeader("KRISHI-DRISHTI", badge);

  // Dedicated centered "READY" card with clean borders
  display.drawRoundRect(26, 12, 76, 19, 3, SSD1306_WHITE);
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(34, 14);
  display.print("READY");

  // Instructions outside box, ample margins, zero border touching
  display.setTextSize(1);
  display.setCursor(10, 34);
  display.print("Point Wand At Leaf");

  // Environmental summary line
  display.setCursor(10, 44);
  if (dhtConnected) {
    char envBuf[24];
    const char* rStr = "Safe";
    if (microclimateTracker.getRiskLevel() == RISK_LEVEL_HIGH_LATE) rStr = "Blight!";
    else if (microclimateTracker.getRiskLevel() == RISK_LEVEL_MODERATE_EARLY) rStr = "Warm";
    snprintf(envBuf, sizeof(envBuf), "%.0fC | %.0f%%RH [%s]", currentTemp, currentHum, rStr);
    display.print(envBuf);
  } else {
    display.print("Canopy: Sensor Ready");
  }

  drawFooter("[PRESS TO SCAN]");
}

// -----------------------------------------------------------------
// SCREEN 1: CANOPY CLIMATE (DETAILED WEATHER & EPIDEMIOLOGY)
// -----------------------------------------------------------------
void renderPage1_Canopy() {
  display.clearDisplay();
  display.setTextWrap(false);
  drawHeader("CANOPY CLIMATE", "1/5");

  if (dhtConnected) {
    display.setTextSize(1);
    char buf[24];

    snprintf(buf, sizeof(buf), "Temp: %.1f C", currentTemp);
    display.setCursor(4, 13);
    display.print(buf);

    snprintf(buf, sizeof(buf), "Hum : %.1f %% RH", currentHum);
    display.setCursor(4, 23);
    display.print(buf);

    String riskStr = microclimateTracker.getRiskStatusString();
    if (riskStr.length() > 20) riskStr = riskStr.substring(0, 20);
    display.setCursor(4, 33);
    display.print(riskStr);

    display.setCursor(4, 43);
    if (currentHum >= 85.0f && currentTemp >= 15.0f && currentTemp <= 22.0f) {
      display.print("Warn: Blight Spores!");
    } else if (currentHum < 60.0f) {
      display.print("Air : Dry (Low Spores)");
    } else {
      display.print("Air : Normal Canopy");
    }
  } else {
    display.setTextSize(1);
    display.setCursor(4, 16);
    display.print("DHT11 Disconnected");
    display.setCursor(4, 28);
    display.print("Sensor pin: GPIO 18");
    display.setCursor(4, 40);
    display.print("Check 3.3V / Wire");
  }

  drawFooter("[TAP] Next   [SCAN]");
}

// -----------------------------------------------------------------
// SCREEN 2: AI DIAGNOSIS (FARMER SAFETY & CERTAINTY GATED)
// -----------------------------------------------------------------
void renderPage2_Diagnosis() {
  display.clearDisplay();
  display.setTextWrap(false);

  if (!hasDiagnosis) {
    drawHeader("AI DIAGNOSIS", "2/5");
    display.setTextSize(1);
    display.setCursor(4, 16);
    display.print("No Scan Recorded Yet");
    display.setCursor(4, 28);
    display.print("Point wand at leaf");
    display.setCursor(4, 40);
    display.print("& click scan button");
    drawFooter("[PRESS TO SCAN]");
    return;
  }

  // CASE 1: UNCERTAIN / LOW CONFIDENCE (<65% or UNCERTAIN status)
  // An uneducated farmer must NEVER see a misleading 'Healthy' on an ambiguous frame!
  if (!isDiagnosisConfident()) {
    // Inverted high-contrast alert header
    display.fillRect(0, 0, 128, 10, SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(4, 1);
    display.print("! SCAN UNCLEAR ! 2/5");

    // Big bold RETAKE notification box
    display.setTextColor(SSD1306_WHITE, SSD1306_BLACK);
    display.drawRoundRect(4, 13, 120, 37, 3, SSD1306_WHITE);

    display.setTextSize(2);
    display.setCursor(28, 17);
    display.print("RETAKE");

    display.setTextSize(1);
    display.setCursor(16, 36);
    display.print("Hold Wand Steady");

    drawFooter("[PRESS SCAN TO RETRY]");
    return;
  }

  // CASE 2: CONFIRMED HEALTHY FOLIAGE (High confidence >= 65%)
  bool isHealthy = (diagDisease.indexOf("Healthy") >= 0);
  if (isHealthy) {
    drawHeader("CROP HEALTHY", "2/5");

    display.setTextSize(1);
    display.setCursor(4, 13);
    char cropBuf[22];
    snprintf(cropBuf, sizeof(cropBuf), "%s Foliage", diagCrop.c_str());
    display.print(cropBuf);

    // Big bold HEALTHY banner
    display.setTextSize(2);
    display.setCursor(22, 24);
    display.print("HEALTHY");

    display.setTextSize(1);
    display.setCursor(4, 43);
    char confBuf[22];
    snprintf(confBuf, sizeof(confBuf), "Conf: %.0f%% [SAFE]", diagConfidence);
    display.print(confBuf);

    drawFooter("[TAP] Cure   [SCAN]");
    return;
  }

  // CASE 3: DISEASE DETECTED (High confidence >= 65% blight or infection)
  // Inverted Alert Header
  display.fillRect(0, 0, 128, 10, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(2, 1);
  display.print("! DISEASE FOUND ! 2/5");

  display.setTextColor(SSD1306_WHITE, SSD1306_BLACK);
  display.setTextSize(1);
  display.setCursor(4, 13);
  char cropLine[22];
  snprintf(cropLine, sizeof(cropLine), "Crop: %s", diagCrop.c_str());
  display.print(cropLine);

  String dName = diagDisease;
  dName.replace(" (Suspected / Ambiguous)", "");
  dName.replace(" (Suspected)", "");
  dName.trim();

  display.setCursor(4, 24);
  if (dName.length() <= 10) {
    display.setTextSize(2);
    display.print(dName);
  } else {
    display.setTextSize(1);
    display.drawRect(2, 23, 124, 14, SSD1306_WHITE);
    display.setCursor(6, 26);
    display.print(dName.substring(0, 19));
  }

  display.setTextSize(1);
  display.setCursor(4, 43);
  char statLine[22];
  snprintf(statLine, sizeof(statLine), "Conf: %.0f%% [SPRAY!]", diagConfidence);
  display.print(statLine);

  drawFooter("[TAP] Cure   [SCAN]");
}

// -----------------------------------------------------------------
// SCREEN 3: AGRONOMIC CURE & ACTION
// -----------------------------------------------------------------
void renderPage3_Cure() {
  display.clearDisplay();
  display.setTextWrap(false);
  drawHeader("ORGANIC CURE", "3/5");

  if (!hasDiagnosis || !isDiagnosisConfident()) {
    display.setTextSize(1);
    display.setCursor(4, 14);
    display.print("Diagnosis Pending:");
    display.setCursor(4, 26);
    display.print("No spray needed yet.");
    display.setCursor(4, 38);
    display.print("Take a clear scan");
    drawFooter("[PRESS SCAN TO RETRY]");
    return;
  }

  bool isHealthy = (diagDisease.indexOf("Healthy") >= 0);
  if (isHealthy) {
    display.setTextSize(1);
    display.setCursor(4, 13);
    display.print("Status: ALL CLEAR");
    display.setCursor(4, 23);
    display.print("No chemical needed!");
    display.setCursor(4, 33);
    display.print("Maintain regular care");
    display.setCursor(4, 43);
    display.print("and balanced water.");
  } else {
    display.setTextSize(1);
    display.setCursor(4, 13);
    display.print("Organic Treatment:");

    display.setCursor(4, 23);
    String orgStr = diagOrganic;
    if (orgStr.length() > 20) orgStr = orgStr.substring(0, 20);
    display.print(orgStr);

    display.setCursor(4, 33);
    if (diagChemical.startsWith("ADVISORY") || diagChemical.startsWith("WITHHELD")) {
      display.print("Air Dry: Delay spray");
    } else {
      display.print("Neem Oil 5ml/L spray");
    }

    display.setCursor(4, 43);
    display.print("Isolate sick foliage");
  }

  drawFooter("[TAP] Status [SCAN]");
}

// -----------------------------------------------------------------
// SCREEN 4: WAND STATUS (PERMANENTLY ANTI-OVERWRITE)
// -----------------------------------------------------------------
void renderPage4_Status() {
  display.clearDisplay();
  display.setTextWrap(false);
  drawHeader("SYSTEM STATUS", "4/5");

  display.setTextSize(1);

  // Line 1: Firmware version
  display.setCursor(4, 13);
  display.print("FW   : v2.5.1 Edge");

  // Line 2: Wi-Fi status
  display.setCursor(4, 24);
  if (WiFi.status() == WL_CONNECTED) {
    char wifiBuf[22];
    snprintf(wifiBuf, sizeof(wifiBuf), "WiFi : OK (%ddBm)", WiFi.RSSI());
    display.print(wifiBuf);
  } else {
    display.print("WiFi : Searching...");
  }

  // Line 3: Camera status
  display.setCursor(4, 35);
  if (WiFi.status() == WL_CONNECTED) {
    display.print("Cam  : 192.168.4.1");
  } else {
    display.print("Cam  : Standby Ready");
  }

  // Line 4: Completed scans
  display.setCursor(4, 46);
  char scanBuf[22];
  snprintf(scanBuf, sizeof(scanBuf), "Scans: %u Completed", totalScansRecorded);
  display.print(scanBuf);

  drawFooter("[TAP] Home   [SCAN]");
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
      wifiRetryCount = 0;
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

  // Non-blocking reconnect: check every 4s without thrashing Wi-Fi driver
  if (lastWifiCheckMs == 0 || millis() - lastWifiCheckMs > 4000) {
    lastWifiCheckMs = millis();
    wifiRetryCount++;
    if (wifiRetryCount >= 3) {
      Serial.println("[WIFI] Reconnect failed 3x - restarting Wi-Fi state machine...");
      WiFi.disconnect(false);
      WiFi.mode(WIFI_OFF);
      delay(100);
      WiFi.mode(WIFI_STA);
      WiFi.begin(AP_SSID, AP_PASS);
      WiFi.setTxPower(WIFI_POWER_8_5dBm);
      wifiRetryCount = 0;
    } else {
      Serial.println("[WIFI] Seeking Camera SoftAP: KRISHI-DRISHTI...");
      WiFi.reconnect();
    }
  }
}

// -----------------------------------------------------------------
// OFFLINE DEMO SCAN (Allows immediate testing of all 3 farmer display states)
// -----------------------------------------------------------------
void triggerDemoScan() {
  demoIndex = (demoIndex + 1) % 3;
  totalScansRecorded++;
  activeScanId = totalScansRecorded;
  hasDiagnosis = true;

  display.clearDisplay();
  display.setTextWrap(false);
  drawHeader("DEMO TEST SCAN", "..");
  display.drawRoundRect(8, 14, 112, 18, 3, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(18, 19);
  display.print("* DEMO TESTING *");
  display.setCursor(10, 36);
  display.print("Simulating Edge AI...");
  display.setCursor(6, 46);
  display.print("Testing Farmer Display");
  display.display();
  delay(1000);

  if (demoIndex == 0) {
    // Demo 0: Confirmed Disease (Late Blight)
    diagCrop = "Potato";
    diagDisease = "Late Blight";
    diagConfidence = 97.4;
    diagStatus = "SEVERE";
    diagOrganic = "Trichoderma viride";
    diagChemical = (currentHum < 85.0f && dhtConnected) ?
      "ADVISORY: Low RH (<85%)" : "Copper Oxychloride";
  } else if (demoIndex == 1) {
    // Demo 1: Confirmed Healthy Crop
    diagCrop = "Potato";
    diagDisease = "Healthy Leaf";
    diagConfidence = 99.4;
    diagStatus = "OPTIMAL";
    diagOrganic = "Crop is healthy";
    diagChemical = "No spray needed";
  } else {
    // Demo 2: Uncertain / Retake Case (Simulates 34.7% low confidence / unclear photo)
    diagCrop = "Tomato";
    diagDisease = "Uncertain Folia";
    diagConfidence = 34.7;
    diagStatus = "UNCERTAIN";
    diagOrganic = "Retake photo in sunlight";
    diagChemical = "Hold wand steady at 10cm";
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
  diagCrop = "Uncertain";
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

  // If camera is not yet connected (e.g. turned off or out of range)
  if (WiFi.status() != WL_CONNECTED) {
    systemStatusMsg = "Standby (No Cam)";
    display.clearDisplay();
    display.setTextWrap(false);
    drawHeader("CAMERA STANDBY", "!");
    display.setTextSize(1);
    display.setCursor(4, 14);
    display.print("ESP32-CAM Not Linked");
    display.setCursor(4, 25);
    display.print("Connect to CAM Wi-Fi");
    display.setCursor(4, 36);
    if (dhtConnected) {
      char dhtBuf[24];
      snprintf(dhtBuf, sizeof(dhtBuf), "Air: %.0fC | %.0f%% RH", currentTemp, currentHum);
      display.print(dhtBuf);
    } else {
      display.print("Canopy Sensor: Ready");
    }
    display.setCursor(4, 47);
    display.print("Hold SCAN for Demo");
    display.display();
    delay(2000);
    renderActivePage();
    return;
  }

  currentState = STATE_CAPTURING;
  systemStatusMsg = "Capturing...";

  display.clearDisplay();
  display.setTextWrap(false);
  drawHeader("LEAF CAPTURE", "..");
  display.drawRoundRect(8, 14, 112, 18, 3, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(18, 19);
  display.print("* CAPTURING *");
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
  http.setTimeout(8000);
  int httpCode = http.GET();

  if (httpCode != 200) {
    Serial.printf("[SCAN] Camera capture failed! HTTP code: %d\n", httpCode);
    systemStatusMsg = "Capture Failed";
    String errPayload = http.getString();
    http.end();

    display.clearDisplay();
    display.setTextWrap(false);
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
    drawFooter("[TAP TO RETRY]");
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
  display.setTextWrap(false);
  drawHeader("AI DIAGNOSIS", "..");
  display.drawRoundRect(8, 14, 112, 18, 3, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(16, 19);
  display.print("* AI ANALYZING *");
  char sBuf[22];
  snprintf(sBuf, sizeof(sBuf), "Leaf Scan #%u", activeScanId);
  display.setCursor(14, 36);
  display.print(sBuf);
  display.setCursor(10, 46);
  display.print("Testing with Edge AI");
  display.display();
}

// -----------------------------------------------------------------
// ARDUINO SETUP
// -----------------------------------------------------------------
void setup() {
  // 1. Hardware Brownout Suppression (ESP-IDF 5.x official API)
  esp_brownout_disable();

  // 2. Stable 160MHz CPU clock (low power, APB locked to 80MHz for reliable Wi-Fi)
  setCpuFrequencyMhz(160);

  Serial.begin(115200);
  delay(150);

  Serial.println("\n========================================");
  Serial.println("  KRISHI-DRISHTI :: Controller Wand v2.5.1");
  Serial.println("  Farmer-Friendly Edge Telemetry Core");
  Serial.println("========================================");
  Serial.flush();

  pinMode(SCAN_BUTTON, INPUT_PULLUP);
  pinMode(NEXT_BUTTON, INPUT_PULLUP);

  // 3. Initialize OLED Display FIRST so user immediately sees bright live state
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

    Wire.beginTransmission(OLED_ADDRESS);
    Wire.write(0x00);       // command stream
    Wire.write(0x81);       // Set Contrast Control command
    Wire.write(0xFF);       // Maximum contrast
    Wire.endTransmission();

    display.dim(false);     // Full brightness
    display.clearDisplay();
    display.setTextWrap(false);
    display.setTextColor(SSD1306_WHITE);

    // Splash screen
    display.fillRect(0, 0, 128, 64, SSD1306_BLACK);
    display.setTextSize(1);
    display.setCursor(22, 6);
    display.print("KRISHI-DRISHTI");
    display.drawLine(6, 17, 121, 17, SSD1306_WHITE);

    display.setCursor(14, 23);
    display.print("Handheld AI Wand");

    display.setCursor(18, 36);
    display.print("Firmware v2.5.1");

    display.setCursor(10, 49);
    display.print("Linking to Cam...");
    display.display();
    delay(50);
  } else {
    Serial.println("[OLED ERROR] Display not detected on I2C bus (Check SDA:21, SCL:22)!"); Serial.flush();
  }

  // 4. Wi-Fi Station Bringup with power cap to eliminate USB brownout sag
  Serial.println("[INIT] Step 2: Wi-Fi Radio Bringup..."); Serial.flush();
  WiFi.mode(WIFI_STA);
  Serial.println("[INIT] Wi-Fi Mode: STA initialized."); Serial.flush();
  Serial.printf("[WIFI] Connecting to SoftAP: '%s'...\n", AP_SSID); Serial.flush();
  WiFi.begin(AP_SSID, AP_PASS);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);
  Serial.println("[INIT] Wi-Fi begin dispatched."); Serial.flush();

  // 5. Sensor bringup
  Serial.println("[INIT] Step 3: DHT11 Sensor..."); Serial.flush();
  dht.begin();

  // 6. Fast instant boot: don't freeze for 3 seconds if camera is off!
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("[WIFI] Cam Linked! IP: " + WiFi.localIP().toString()); Serial.flush();
    if (oledOk) {
      display.fillRect(0, 48, 128, 16, SSD1306_BLACK);
      display.setCursor(16, 49);
      display.print("CAM LINKED! [OK]");
      display.display();
      delay(200);
    }
  } else {
    Serial.println("[WIFI] Cam in standby mode. Wand is live."); Serial.flush();
    if (oledOk) {
      display.fillRect(0, 48, 128, 16, SSD1306_BLACK);
      display.setCursor(12, 49);
      display.print("STANDBY READY [OK]");
      display.display();
      delay(200);
    }
  }

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

  // UNIFIED BUTTON CONTROLS:
  // - SCAN Button (GPIO 27):
  //     * Short Press:
  //         - On Home (Screen 0): Trigger leaf scan!
  //         - On Other Screens: Cycle to next page
  //     * Long Press (>= 800ms):
  //         - Triggers scan from any screen
  //         - If Camera offline and press >= 1.5s: Cycles Demo Mode
  // - NEXT Button (GPIO 26):
  //     * Optional second button: cycles to next page immediately
  bool sScan = digitalRead(SCAN_BUTTON);
  if (prevScan == HIGH && sScan == LOW) {
    scanPressStartMs = millis();
  } else if (prevScan == LOW && sScan == HIGH) {
    unsigned long pressDuration = millis() - scanPressStartMs;
    if (pressDuration >= DEBOUNCE_MS) {
      if (pressDuration >= 800) {
        if (WiFi.status() != WL_CONNECTED && pressDuration >= 1500) {
          Serial.println("[USER] Long Press -> Triggering DEMO TEST SCAN!");
          triggerDemoScan();
        } else {
          Serial.println("[USER] Long Press -> Initiating leaf scan...");
          triggerRealScan();
        }
      } else {
        if (activePage == 0) {
          Serial.println("[USER] Tap on Home -> Initiating leaf scan...");
          triggerRealScan();
        } else {
          activePage = (activePage + 1) % TOTAL_PAGES;
          Serial.printf("[USER] Tap Button -> Showing Page %d/%d\n", activePage + 1, TOTAL_PAGES);
          renderActivePage();
        }
      }
    }
  }
  prevScan = sScan;

  // Optional dedicated NEXT button (GPIO 26)
  bool sNext = digitalRead(NEXT_BUTTON);
  if (prevNext == HIGH && sNext == LOW) {
    if (millis() - lastNextMs >= DEBOUNCE_MS) {
      lastNextMs = millis();
      activePage = (activePage + 1) % TOTAL_PAGES;
      Serial.printf("[USER] Next Button -> Showing Page %d/%d\n", activePage + 1, TOTAL_PAGES);
      renderActivePage();
    }
  }
  prevNext = sNext;

  // Periodic Telemetry Refresh on Screen 0 & 1
  static unsigned long lastOledRefreshMs = 0;
  if (currentState == STATE_IDLE && (activePage == 0 || activePage == 1)) {
    if (millis() - lastOledRefreshMs > 3000) {
      lastOledRefreshMs = millis();
      renderActivePage();
    }
  }

  delay(20);
}
