/*
  ==============================================================================
  KRISHI-DRISHTI (कृषि-दृष्टि) - Official Controller Wand Firmware v2.2
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
#include "esp_private/brownout.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

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
// CONFIGURABLE EXHIBITION DISPLAY STRINGS
// -----------------------------------------------------------------
const char* TXT_HEADER_HOME   = "KRISHI-DRISHTI";
const char* TXT_HEADER_ENV    = "CANOPY CLIMATE";
const char* TXT_HEADER_DIAG   = "AI SCREENING";
const char* TXT_HEADER_CURE   = "AGRONOMIC CURE";
const char* TXT_FOOTER_HINT   = "[SCAN]Snap [NEXT]>";

// -----------------------------------------------------------------
// NETWORK CONFIGURATION
// -----------------------------------------------------------------
const char* AP_SSID = "KRISHI-DRISHTI";
const char* AP_PASS = "12345678";
const char* CAMERA_HOST = "192.168.4.1";

const String URL_CAPTURE   = "http://192.168.4.1/api/capture";
const String URL_DIAG_LATEST = "http://192.168.4.1/api/diagnosis/latest";
const String URL_STATUS    = "http://192.168.4.1/api/status";

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
  STATE_ERROR
};

WandState currentState = STATE_IDLE;
int activePage = 0; // 0: Home, 1: Weather, 2: Diagnosis, 3: Cure
const int TOTAL_PAGES = 4;

// Microclimate Telemetry
float currentTemp = 0.0;
float currentHum = 0.0;
bool dhtConnected = false;
unsigned long lastDhtReadMs = 0;
const unsigned long DHT_INTERVAL_MS = 2500;

// Scan & Telemetry Tracking
uint32_t activeScanId = 0;
uint32_t totalScansRecorded = 0;
String systemStatusMsg = "Wand Online";

// Diagnosis Data (Received from Phone AI Engine via Camera Bridge)
bool hasDiagnosis = false;
uint32_t diagScanId = 0;
String diagCrop = "--";
String diagDisease = "No Scan Yet";
float diagConfidence = 0.0;
String diagStatus = "PENDING";
String diagOrganic = "Press [SCAN] to test";
String diagChemical = "No active prescription";

// Non-Blocking AI Polling Timers
unsigned long aiWaitStartMs = 0;
unsigned long lastAiPollMs = 0;
const unsigned long AI_TIMEOUT_MS = 14000;
const unsigned long AI_POLL_INTERVAL_MS = 1000;

// Modular Microclimate Epidemiological Risk Tracker (Duration with Drying-Decay)
MicroclimateTracker microclimateTracker(6.0f);

// Wi-Fi Status Tracking
bool wifiConnected = false;
unsigned long lastWifiCheckMs = 0;

// Button Debounce
bool prevScan = HIGH;
bool prevNext = HIGH;
unsigned long lastScanMs = 0;
unsigned long lastNextMs = 0;
const unsigned long DEBOUNCE_MS = 250;

// Auto-advance slideshow timer
unsigned long lastAutoSlideMs = 0;
const unsigned long SLIDE_INTERVAL_MS = 6000;

// -----------------------------------------------------------------
// DISPLAY DRAWING PRIMITIVES
// -----------------------------------------------------------------
void drawHeader(const char* title, const char* pageNum) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(title);
  display.setCursor(102, 0);
  display.print(pageNum);
  display.drawLine(0, 9, 127, 9, SSD1306_WHITE);
}

void drawFooter() {
  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(0, 55);
  display.print(TXT_FOOTER_HINT);
  display.display();
}

// -----------------------------------------------------------------
// PAGE RENDERING
// -----------------------------------------------------------------
void renderPage0_Home() {
  drawHeader(TXT_HEADER_HOME, "1/4");

  display.setCursor(0, 13);
  display.print("WiFi : ");
  if (WiFi.status() == WL_CONNECTED) {
    display.printf("Mesh OK (%ddBm)", WiFi.RSSI());
  } else {
    display.print("Connecting...");
  }

  display.setCursor(0, 24);
  display.print("Camera : ");
  display.print(WiFi.status() == WL_CONNECTED ? "192.168.4.1" : "Searching");

  display.setCursor(0, 35);
  display.printf("Scans  : %u Saved", totalScansRecorded);

  display.setCursor(0, 44);
  display.print("State  : ");
  display.print(systemStatusMsg);

  drawFooter();
}

void renderPage1_Canopy() {
  drawHeader(TXT_HEADER_ENV, "2/4");

  if (dhtConnected) {
    display.setCursor(0, 13);
    display.printf("Temp: %.1f C", currentTemp);

    display.setCursor(0, 24);
    display.printf("Hum : %.1f %% RH", currentHum);

    display.setCursor(0, 36);
    display.print(microclimateTracker.getRiskStatusString());
  } else {
    display.setCursor(0, 15);
    display.print("DHT11: Disconnected");
    display.setCursor(0, 27);
    display.print("Sensor pin: GPIO 18");
    display.setCursor(0, 39);
    display.print("Check cable/resistor");
  }

  drawFooter();
}

void renderPage2_Diagnosis() {
  drawHeader(TXT_HEADER_DIAG, "3/4");

  if (hasDiagnosis) {
    display.setCursor(0, 13);
    display.printf("Crop : %s", diagCrop.c_str());

    display.setCursor(0, 24);
    display.printf("Cond : %s", diagDisease.c_str());

    display.setCursor(0, 35);
    if (diagStatus == "UNCERTAIN") {
      display.print("Conf : UNCERTAIN / LOW");
      display.setCursor(0, 44);
      display.print("Stat : RETAKE PHOTO");
    } else {
      display.printf("Conf : %.1f%%", diagConfidence);
      display.setCursor(0, 44);
      display.printf("Stat : %s", diagStatus.c_str());
    }
  } else {
    display.setCursor(0, 18);
    display.print("No Active Diagnosis");
    display.setCursor(0, 30);
    display.print("Aim lens at leaf &");
    display.setCursor(0, 40);
    display.print("press [SCAN] to start");
  }

  drawFooter();
}

void renderPage3_Cure() {
  drawHeader(TXT_HEADER_CURE, "4/4");

  if (hasDiagnosis && diagStatus != "UNCERTAIN") {
    display.setCursor(0, 13);
    display.print("Org : ");
    // Truncate cleanly if too long
    display.print(diagOrganic.substring(0, 15));

    display.setCursor(0, 24);
    display.print("Chem: ");
    display.print(diagChemical.substring(0, 15));

    display.setCursor(0, 36);
    display.print("Note: Preventative bio");
    display.setCursor(0, 44);
    display.print("spray under canopy");
  } else if (diagStatus == "UNCERTAIN") {
    display.setCursor(0, 16);
    display.print("Image unclear/shadowed");
    display.setCursor(0, 28);
    display.print("1. Hold wand steady");
    display.setCursor(0, 40);
    display.print("2. 10-15cm from leaf");
  } else {
    display.setCursor(0, 20);
    display.print("Prescription pending");
    display.setCursor(0, 34);
    display.print("Perform leaf scan");
  }

  drawFooter();
}

void renderActivePage() {
  if (activePage == 0) renderPage0_Home();
  else if (activePage == 1) renderPage1_Canopy();
  else if (activePage == 2) renderPage2_Diagnosis();
  else renderPage3_Cure();
}

// -----------------------------------------------------------------
// SENSOR TELEMETRY
// -----------------------------------------------------------------
void readSensors() {
  if (millis() - lastDhtReadMs > DHT_INTERVAL_MS || lastDhtReadMs == 0) {
    lastDhtReadMs = millis();
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (!isnan(h) && !isnan(t) && h > 0.0 && h <= 100.0) {
      currentHum = h;
      currentTemp = t;
      dhtConnected = true;
    } else {
      dhtConnected = false;
    }
    // Update modular C++ microclimate duration tracker
    microclimateTracker.update(millis(), currentTemp, currentHum, dhtConnected);
  }
}

// -----------------------------------------------------------------
// WI-FI CONNECTION MANAGEMENT
// -----------------------------------------------------------------
void ensureWiFiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    return;
  }

  wifiConnected = false;
  if (millis() - lastWifiCheckMs > 5000 || lastWifiCheckMs == 0) {
    lastWifiCheckMs = millis();
    Serial.println("[WIFI] Attempting connection to KRISHI-DRISHTI...");
    WiFi.begin(AP_SSID, AP_PASS);
  }
}

// -----------------------------------------------------------------
// REAL SCAN EXECUTION & AI RETRIEVAL PIPELINE
// -----------------------------------------------------------------
// Non-blocking asynchronous AI polling routine
void pollAiDiagnosisNonBlocking() {
  HTTPClient httpDiag;
  httpDiag.begin(URL_DIAG_LATEST);
  httpDiag.setTimeout(1500); // Non-blocking quick query
  int diagCode = httpDiag.GET();

  if (diagCode == 200) {
    String diagPayload = httpDiag.getString();
    StaticJsonDocument<512> diagDoc;
    DeserializationError dErr = deserializeJson(diagDoc, diagPayload);

    if (!dErr && diagDoc["ready"] == true) {
      uint32_t retScanId = diagDoc["scan_id"];
      // Strict scan ID verification: discard stale or mismatched diagnoses
      if (retScanId == activeScanId) {
        diagCrop = diagDoc["crop"].as<String>();
        diagDisease = diagDoc["disease"].as<String>();
        diagConfidence = diagDoc["confidence"].as<float>();
        diagStatus = diagDoc["status"].as<String>();
        diagOrganic = diagDoc["organic"].as<String>();
        diagChemical = diagDoc["chemical"].as<String>();

        diagScanId = retScanId;
        hasDiagnosis = true;
        systemStatusMsg = "Diagnosis OK";
        currentState = STATE_DIAGNOSIS_RECEIVED;
        activePage = 2; // Auto-transition to diagnosis result page
        renderActivePage();
        lastAutoSlideMs = millis();

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
  diagOrganic = "Check phone browser is at 192.168.4.1";
  diagChemical = "Ensure MobileNetV3 is loaded";

  currentState = STATE_TIMEOUT;
  activePage = 2;
  renderActivePage();
  lastAutoSlideMs = millis();
}

void triggerRealScan() {
  if (WiFi.status() != WL_CONNECTED) {
    systemStatusMsg = "WiFi Offline";
    display.clearDisplay();
    drawHeader("SCAN ERROR", "!");
    display.setCursor(0, 18);
    display.print("Camera WiFi Unreachable");
    display.setCursor(0, 30);
    display.print("Check ESP32-CAM power");
    display.setCursor(0, 42);
    display.print("SSID: KRISHI-DRISHTI");
    drawFooter();
    renderActivePage();
    return;
  }

  currentState = STATE_CAPTURING;
  systemStatusMsg = "Capturing...";

  display.clearDisplay();
  drawHeader("LEAF CAPTURE", "..");
  display.setCursor(14, 18);
  display.print("* CAPTURING *");
  display.drawRect(8, 14, 112, 16, SSD1306_WHITE);
  display.setCursor(10, 36);
  display.print("Triggering Camera...");
  display.display();

  HTTPClient http;
  http.begin(URL_CAPTURE);
  http.setTimeout(4000);
  int httpCode = http.GET();

  if (httpCode != 200) {
    Serial.printf("[SCAN] Camera capture failed! HTTP code: %d\n", httpCode);
    systemStatusMsg = "Capture Failed";
    display.clearDisplay();
    drawHeader("CAPTURE ERROR", "!");
    display.setCursor(0, 20);
    display.printf("Camera returned %d", httpCode);
    display.setCursor(0, 34);
    display.print("Check SD Card & Lens");
    drawFooter();
    http.end();
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
  drawHeader("EDGE AI INFERENCE", "..");
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
  esp_brownout_disable();
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(150);

  Serial.println("\n========================================");
  Serial.println("  KRISHI-DRISHTI :: Controller Wand v2.2");
  Serial.println("  Offline Edge Telemetry Core v2.2");
  Serial.println("========================================");

  pinMode(SCAN_BUTTON, INPUT_PULLUP);
  pinMode(NEXT_BUTTON, INPUT_PULLUP);

  dht.begin();

  Wire.begin(21, 22);
  if (display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("[OLED] SSD1306 Initialized successfully.");
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(10, 15);
    display.print("KRISHI-DRISHTI");
    display.setCursor(10, 30);
    display.print("Controller Wand v2.2");
    display.setCursor(10, 45);
    display.print("Connecting WiFi...");
    display.display();
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(AP_SSID, AP_PASS);

  readSensors();
  lastAutoSlideMs = millis();
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
    // Strict race prevention: only trigger timeout if STILL in STATE_AWAITING_AI after polling
    if (currentState == STATE_AWAITING_AI && (millis() - aiWaitStartMs >= AI_TIMEOUT_MS)) {
      handleAiTimeoutNonBlocking();
    }
  }

  bool sScan = digitalRead(SCAN_BUTTON);
  bool sNext = digitalRead(NEXT_BUTTON);

  // BUTTON 1: SCAN (GPIO 27) -> Sends real HTTP capture, awaits real AI
  if (prevScan == HIGH && sScan == LOW && millis() - lastScanMs > DEBOUNCE_MS) {
    lastScanMs = millis();
    Serial.println("[USER] SCAN Button Pressed -> Initiating real capture sequence...");
    triggerRealScan();
  }

  // BUTTON 2: NEXT (GPIO 26) -> Cycles through 4 telemetry/cure pages
  if (prevNext == HIGH && sNext == LOW && millis() - lastNextMs > DEBOUNCE_MS) {
    lastNextMs = millis();
    activePage = (activePage + 1) % TOTAL_PAGES;
    Serial.printf("[USER] NEXT Button Pressed -> Showing Page %d/4\n", activePage + 1);
    renderActivePage();
    lastAutoSlideMs = millis();
  }

  prevScan = sScan;
  prevNext = sNext;

  // AUTO-SLIDESHOW FOR SCIENCE EXHIBITION JUDGES
  // When idle, smoothly advance to the next screen every 6 seconds
  if (currentState != STATE_CAPTURING && currentState != STATE_AWAITING_AI) {
    if (millis() - lastAutoSlideMs > SLIDE_INTERVAL_MS) {
      lastAutoSlideMs = millis();
      activePage = (activePage + 1) % TOTAL_PAGES;
      renderActivePage();
    }
  }

  delay(20);
}
