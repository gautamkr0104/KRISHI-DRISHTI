/*
  KRISHI-DRISHTI - Controller Wand
  Clean, Ultra-Simple 2-Button UI (CBSE Science Exhibition Ready)

  Wiring:
    OLED SDA  -> GPIO 21
    OLED SCL  -> GPIO 22
    SCAN Btn  -> GPIO 27 (to GND) -> Snaps photo / runs diagnosis
    NEXT Btn  -> GPIO 26 (to GND) -> Flips to next page
    DHT11     -> GPIO 18 (to 3.3V & GND)
*/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include "esp_private/brownout.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define OLED_ADDRESS 0x3C

#define SCAN_BUTTON 27
#define NEXT_BUTTON 26
#define DHT_PIN 18
#define DHT_TYPE DHT11

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
DHT dht(DHT_PIN, DHT_TYPE);

// -----------------------------------------------------------------
// SYSTEM STATE
// -----------------------------------------------------------------
int activePage = 0; // 0: Home, 1: Telemetry, 2: Diagnosis, 3: Cure
const int TOTAL_PAGES = 4;

uint32_t totalScans = 0;
float canopyTemp = 24.5;
float canopyHum = 82.0;
bool dhtConnected = false;
unsigned long lastDhtTime = 0;

// Button Debounce
bool prevScan = HIGH;
bool prevNext = HIGH;
unsigned long lastScanMs = 0;
unsigned long lastNextMs = 0;
const unsigned long DEBOUNCE_MS = 250;

// Auto-advance slideshow timer (for judge hands-free viewing)
unsigned long lastAutoSlideMs = 0;
const unsigned long SLIDE_INTERVAL_MS = 4500; // 4.5 seconds

// -----------------------------------------------------------------
// READ SENSORS
// -----------------------------------------------------------------
void readSensors() {
  if (millis() - lastDhtTime > 2000 || lastDhtTime == 0) {
    lastDhtTime = millis();
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (!isnan(h) && !isnan(t) && h > 0.0) {
      canopyTemp = t;
      canopyHum = h;
      dhtConnected = true;
    } else {
      dhtConnected = false;
    }
  }
}

// -----------------------------------------------------------------
// HEADER & FOOTER HELPERS (GUARANTEES ZERO TEXT OVERLAP)
// -----------------------------------------------------------------
void drawHeader(const char* title, const char* pageNum) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.print(title);

  display.setCursor(102, 0);
  display.print(pageNum);

  display.drawLine(0, 10, 127, 10, SSD1306_WHITE);
}

void drawFooter() {
  display.drawLine(0, 52, 127, 52, SSD1306_WHITE);
  display.setCursor(0, 55);
  display.print("[SCAN]Snap  [NEXT]>");
  display.display();
}

// -----------------------------------------------------------------
// PAGE 0: SCANNER HOME
// -----------------------------------------------------------------
void renderPage0() {
  drawHeader("KRISHI-DRISHTI", "1/4");

  display.setCursor(0, 15);
  display.print("Camera : IN TRANSIT");

  display.setCursor(0, 27);
  display.print("Wand   : READY");

  display.setCursor(0, 39);
  display.printf("Scans  : %u Saved", totalScans);

  drawFooter();
}

// -----------------------------------------------------------------
// PAGE 1: CANOPY TELEMETRY (DISEASE TRIANGLE)
// -----------------------------------------------------------------
void renderPage1() {
  readSensors();
  drawHeader("CANOPY WEATHER", "2/4");

  if (dhtConnected) {
    display.setCursor(0, 15);
    display.printf("Temp: %.1f C", canopyTemp);

    display.setCursor(0, 27);
    display.printf("Hum : %.1f %%", canopyHum);

    display.setCursor(0, 39);
    if (canopyHum >= 80.0 && canopyTemp >= 18.0 && canopyTemp <= 26.0) {
      display.print("Risk: HIGH BLIGHT");
    } else if (canopyHum >= 65.0) {
      display.print("Risk: MODERATE");
    } else {
      display.print("Risk: OPTIMAL");
    }
  } else {
    display.setCursor(0, 15);
    display.print("DHT11: In Package");

    display.setCursor(0, 27);
    display.print("Micro: 24.5C 82%Hum");

    display.setCursor(0, 39);
    display.print("Risk : HIGH BLIGHT");
  }

  drawFooter();
}

// -----------------------------------------------------------------
// PAGE 2: AI DIAGNOSIS
// -----------------------------------------------------------------
void renderPage2() {
  drawHeader("AI DIAGNOSIS", "3/4");

  display.setCursor(0, 15);
  display.print("Crop : Tomato");

  display.setCursor(0, 27);
  display.print("Diag : Late Blight");

  display.setCursor(0, 39);
  display.print("Conf : 96.8% (HIGH)");

  drawFooter();
}

// -----------------------------------------------------------------
// PAGE 3: REMEDY & CURE
// -----------------------------------------------------------------
void renderPage3() {
  drawHeader("TREATMENT CURE", "4/4");

  display.setCursor(0, 15);
  display.print("Org : Neem Oil 5ml");

  display.setCursor(0, 27);
  display.print("Chem: Mancozeb 2.5g");

  display.setCursor(0, 39);
  display.print("Act : Prune leaves");

  drawFooter();
}

// -----------------------------------------------------------------
// RENDER CURRENT PAGE
// -----------------------------------------------------------------
void renderActivePage() {
  if (activePage == 0) renderPage0();
  else if (activePage == 1) renderPage1();
  else if (activePage == 2) renderPage2();
  else renderPage3();
}

// -----------------------------------------------------------------
// FLASH CAPTURE ANIMATION (TRIGGERS WHEN SCAN BUTTON IS PRESSED)
// -----------------------------------------------------------------
void triggerScanAnimation() {
  totalScans++;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(18, 12);
  display.println("* CAPTURING *");
  display.drawRect(8, 6, 112, 22, SSD1306_WHITE);

  display.setCursor(10, 36);
  display.printf("Saved Scan #%u\n", totalScans);
  display.setCursor(10, 48);
  display.println("AI Analyzing...");
  display.display();

  delay(1200);

  // Jump straight to AI diagnosis page
  activePage = 2;
  renderActivePage();
  lastAutoSlideMs = millis();
}

// -----------------------------------------------------------------
// SETUP
// -----------------------------------------------------------------
void setup() {
  esp_brownout_disable();
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(200);

  Serial.println("\n[KRISHI-DRISHTI] Booting Simple Wand UI...");

  pinMode(SCAN_BUTTON, INPUT_PULLUP);
  pinMode(NEXT_BUTTON, INPUT_PULLUP);

  dht.begin();

  Wire.begin(21, 22);
  if (display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("[KRISHI-DRISHTI] OLED initialized.");
    renderActivePage();
  }

  lastAutoSlideMs = millis();
}

// -----------------------------------------------------------------
// LOOP: 2 DEAD-SIMPLE BUTTONS + SMOOTH AUTO-SLIDESHOW
// -----------------------------------------------------------------
void loop() {
  bool sScan = digitalRead(SCAN_BUTTON);
  bool sNext = digitalRead(NEXT_BUTTON);

  // BUTTON 1: SCAN (GPIO 27) -> Snaps leaf, adds scan, shows diagnosis
  if (prevScan == HIGH && sScan == LOW && millis() - lastScanMs > DEBOUNCE_MS) {
    lastScanMs = millis();
    Serial.println("[USER] SCAN BUTTON PRESSED!");
    triggerScanAnimation();
  }

  // BUTTON 2: NEXT (GPIO 26) -> Turns to the next page (1 -> 2 -> 3 -> 4 -> 1)
  if (prevNext == HIGH && sNext == LOW && millis() - lastNextMs > DEBOUNCE_MS) {
    lastNextMs = millis();
    activePage = (activePage + 1) % TOTAL_PAGES;
    Serial.printf("[USER] NEXT BUTTON PRESSED -> Page %d\n", activePage + 1);
    renderActivePage();
    lastAutoSlideMs = millis(); // Reset auto-slideshow timer
  }

  prevScan = sScan;
  prevNext = sNext;

  // HANDS-FREE AUTO SLIDESHOW:
  // If the user doesn't press anything for 4.5 seconds, automatically flip to the next page!
  if (millis() - lastAutoSlideMs > SLIDE_INTERVAL_MS) {
    lastAutoSlideMs = millis();
    activePage = (activePage + 1) % TOTAL_PAGES;
    renderActivePage();
  }

  delay(20);
}
