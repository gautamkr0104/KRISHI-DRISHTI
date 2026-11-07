
/*
  KRISHI-DRISHTI - Stage 1 Camera Firmware
  Board: ESP32-CAM (ESP-32S)
  Camera: OV5640 (PID 0x5640)
  Storage: Onboard microSD, SD_MMC 1-bit mode
  PSRAM: Required for high-resolution capture

  Wi-Fi:
    SSID: KRISHI-DRISHTI
    Password: 12345678
    IP: 192.168.4.1

  Endpoints:
    GET /api/status
    GET /api/capture

  Image settings:
    Resolution: UXGA (1600 x 1200)
    Format: JPEG
    JPEG quality: 10
    Frame buffers: 1
    Frame buffer: PSRAM
*/

// --------------------------------------------------
// LIBRARIES
// --------------------------------------------------

#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"
#include <WiFi.h>
#include <WebServer.h>

// --------------------------------------------------
// CAMERA PIN MAP
// Verified working with your camera.
// --------------------------------------------------

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5

#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_LED_PIN      4  // High-power onboard Flash LED on GPIO 4

// --------------------------------------------------
// WI-FI CONFIGURATION
// --------------------------------------------------

const char* AP_SSID = "KRISHI-DRISHTI";
const char* AP_PASSWORD = "12345678";

// --------------------------------------------------
// SERVER AND GLOBAL STATE
// --------------------------------------------------

WebServer server(80);

bool cameraReady = false;
bool sdReady = false;
bool psramAvailable = false;

uint32_t scanCounter = 0;

// --------------------------------------------------
// AI DIAGNOSIS BRIDGE STATE (PHONE -> CAMERA -> CONTROLLER)
// --------------------------------------------------

bool diagnosisReady = false;
uint32_t diagScanId = 0;
String diagCrop = "Tomato";
String diagDisease = "Healthy";
float diagConfidence = 98.0;
String diagStatus = "HEALTHY";
String diagOrganic = "Maintain regular water & NPK";
String diagChemical = "No chemical spray needed";

// --------------------------------------------------
// FIND NEXT UNUSED IMAGE NUMBER
// Prevents appending to an old JPEG after reboot.
// --------------------------------------------------

void findNextScanNumber() {

  scanCounter = 0;

  if (!sdReady) return;

  while (scanCounter < 999999) {

    uint32_t nextId = scanCounter + 1;

    char filename[32];

    snprintf(
      filename,
      sizeof(filename),
      "/scan_%06lu.jpg",
      (unsigned long)nextId
    );

    if (!SD_MMC.exists(filename)) {
      break;
    }

    scanCounter = nextId;
  }

  Serial.printf(
    "Last existing scan ID: %lu\n",
    (unsigned long)scanCounter
  );
}

// --------------------------------------------------
// CAMERA INITIALISATION
// --------------------------------------------------

bool initialiseCamera() {

  Serial.println();
  Serial.println("Initialising OV5640 camera...");

  psramAvailable = psramFound();

  Serial.printf(
    "PSRAM detected: %s\n",
    psramAvailable ? "YES" : "NO"
  );

  if (!psramAvailable) {
    Serial.println(
      "WARNING: High-resolution capture requires PSRAM."
    );
    return false;
  }

  camera_config_t config = {};

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  // Camera data pins
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  // Clock and synchronisation
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  // SCCB
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  // Power and reset
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;

  // Image format
  config.pixel_format = PIXFORMAT_JPEG;

  // HIGH-RESOLUTION DATASET CAPTURE
  config.frame_size = FRAMESIZE_UXGA;  // 1600 x 1200
  config.jpeg_quality = 10;            // Lower number = higher quality

  // Keep one buffer to control memory use.
  config.fb_count = 1;

  // Avoid queuing old frames.
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  // OV5640 high-resolution buffer in PSRAM.
  config.fb_location = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {

    Serial.printf(
      "Camera initialisation FAILED: 0x%x\n",
      err
    );

    return false;
  }

  Serial.println("Camera driver initialised.");

  sensor_t* sensor = esp_camera_sensor_get();

  if (sensor != nullptr) {

    Serial.printf(
      "Camera sensor PID: 0x%04X\n",
      sensor->id.PID
    );

    Serial.printf(
      "Camera sensor VER: 0x%04X\n",
      sensor->id.VER
    );

    sensor->set_brightness(sensor, 0);
    sensor->set_contrast(sensor, 0);
    sensor->set_saturation(sensor, 0);
  }

  // Test one actual UXGA frame.
  Serial.println("Testing UXGA frame capture...");

  camera_fb_t* fb = esp_camera_fb_get();

  if (fb == nullptr) {

    Serial.println("UXGA frame capture FAILED.");

    return false;
  }

  Serial.printf(
    "Test frame: %u x %u | %u bytes | format=%d\n",
    fb->width,
    fb->height,
    (unsigned int)fb->len,
    fb->format
  );

  bool validFrame =
    fb->format == PIXFORMAT_JPEG &&
    fb->width == 1600 &&
    fb->height == 1200 &&
    fb->len > 0;

  esp_camera_fb_return(fb);

  if (!validFrame) {

    Serial.println(
      "WARNING: Frame is not the expected UXGA JPEG."
    );

    return false;
  }

  Serial.println("UXGA camera test PASSED.");

  return true;
}

// --------------------------------------------------
// MICROSD INITIALISATION
// --------------------------------------------------

bool initialiseSD() {

  Serial.println();
  Serial.println("Initialising microSD...");

  if (!SD_MMC.begin("/sdcard", true)) {

    Serial.println("microSD mount FAILED.");

    return false;
  }

  uint8_t cardType = SD_MMC.cardType();

  if (cardType == CARD_NONE) {

    Serial.println("No microSD card detected.");

    SD_MMC.end();

    return false;
  }

  uint64_t cardSizeMB =
    SD_MMC.cardSize() / (1024ULL * 1024ULL);

  Serial.printf(
    "microSD ready. Size: %llu MB\n",
    cardSizeMB
  );

  return true;
}

// --------------------------------------------------
// STATUS ENDPOINT
// GET /api/status
// --------------------------------------------------

void handleStatus() {

  String body = "{";

  body += "\"device\":\"KRISHI-DRISHTI-CAM\",";
  body += "\"camera_ready\":";
  body += cameraReady ? "true" : "false";

  body += ",\"sd_ready\":";
  body += sdReady ? "true" : "false";

  body += ",\"psram_available\":";
  body += psramAvailable ? "true" : "false";

  body += ",\"sensor\":\"OV5640\",";
  body += "\"resolution\":\"1600x1200\",";
  body += "\"pixel_format\":\"JPEG\",";
  body += "\"jpeg_quality\":10,";
  body += "\"sd_mode\":\"1-bit\",";

  body += "\"last_scan_id\":";
  body += String(scanCounter);

  body += "}";

  server.send(200, "application/json", body);
}

// --------------------------------------------------
// CAPTURE ENDPOINT
// GET /api/capture
// --------------------------------------------------

void handleCapture() {

  if (!cameraReady) {

    server.send(
      503,
      "application/json",
      "{\"status\":\"error\",\"message\":\"camera_not_ready\"}"
    );

    return;
  }

  if (!sdReady) {

    server.send(
      503,
      "application/json",
      "{\"status\":\"error\",\"message\":\"sd_not_ready\"}"
    );

    return;
  }

  Serial.println();
  Serial.println("================================");
  Serial.println("Starting high-resolution capture");
  Serial.println("================================");

  diagnosisReady = false; // Reset diagnosis flag for new scan

  // 1. Activate high-power Flash LED on GPIO 4
  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(120); // Allow OV5640 auto-exposure (AEC/AGC) to stabilize under flash

  camera_fb_t* fb = esp_camera_fb_get();

  // 2. Turn off Flash LED immediately to prevent heat buildup and conserve power
  digitalWrite(FLASH_LED_PIN, LOW);

  if (fb == nullptr) {

    Serial.println("Capture failed: no frame.");

    server.send(
      500,
      "application/json",
      "{\"status\":\"error\",\"message\":\"capture_failed\"}"
    );

    return;
  }

  if (
    fb->format != PIXFORMAT_JPEG ||
    fb->len == 0 ||
    fb->width != 1600 ||
    fb->height != 1200
  ) {

    Serial.println("Invalid or unexpected camera frame.");

    esp_camera_fb_return(fb);

    server.send(
      500,
      "application/json",
      "{\"status\":\"error\",\"message\":\"invalid_frame\"}"
    );

    return;
  }

  Serial.printf(
    "Captured: %u x %u\n",
    fb->width,
    fb->height
  );

  Serial.printf(
    "JPEG size: %u bytes\n",
    (unsigned int)fb->len
  );

  uint32_t nextId = scanCounter + 1;

  char filename[32];

  snprintf(
    filename,
    sizeof(filename),
    "/scan_%06lu.jpg",
    (unsigned long)nextId
  );

  File file = SD_MMC.open(filename, FILE_WRITE);

  if (!file) {

    esp_camera_fb_return(fb);

    Serial.println("SD file open failed.");

    server.send(
      500,
      "application/json",
      "{\"status\":\"error\",\"message\":\"file_open_failed\"}"
    );

    return;
  }

  size_t imageSize = fb->len;

  size_t written = file.write(
    fb->buf,
    imageSize
  );

  file.close();

  esp_camera_fb_return(fb);

  if (written != imageSize) {

    SD_MMC.remove(filename);

    Serial.println("Incomplete SD write.");

    server.send(
      500,
      "application/json",
      "{\"status\":\"error\",\"message\":\"sd_write_incomplete\"}"
    );

    return;
  }

  scanCounter = nextId;

  Serial.printf(
    "Saved: %s\n",
    filename
  );

  Serial.printf(
    "Bytes written: %u\n",
    (unsigned int)written
  );

  String body = "{\"status\":\"saved\",\"scan_id\":";

  body += String(scanCounter);

  body += ",\"filename\":\"";
  body += filename;

  body += "\",\"width\":1600";
  body += ",\"height\":1200";

  body += ",\"bytes\":";
  body += String(imageSize);

  body += "}";

  server.send(
    200,
    "application/json",
    body
  );

  Serial.println("Capture completed successfully.");
}

// --------------------------------------------------
// ROOT ENDPOINT
// --------------------------------------------------

// --------------------------------------------------
// ROOT HTML DASHBOARD (MODERN JUDGE-READY UI)
// --------------------------------------------------

const char ROOT_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KRISHI-DRISHTI | Agro-Vision</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #090d16; color: #f1f5f9; padding: 14px; min-height: 100vh; }
    .header { text-align: center; padding: 18px 0 12px; border-bottom: 1px solid rgba(16,185,129,0.25); margin-bottom: 14px; }
    .title { font-size: 24px; font-weight: 800; color: #10b981; letter-spacing: 1.5px; text-transform: uppercase; }
    .subtitle { font-size: 12px; color: #94a3b8; margin-top: 4px; letter-spacing: 0.5px; }
    .badges { display: flex; justify-content: center; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
    .badge { font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-green { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
    .badge-blue { background: rgba(56,189,248,0.15); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .badge-purple { background: rgba(168,85,247,0.15); color: #c084fc; border: 1px solid rgba(168,85,247,0.3); }
    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
    .stat-card { background: #131c2e; border-radius: 10px; padding: 10px 6px; text-align: center; border: 1px solid #1e293b; }
    .stat-val { font-size: 16px; font-weight: 800; color: #f8fafc; }
    .stat-lbl { font-size: 10px; color: #64748b; margin-top: 2px; text-transform: uppercase; }
    .actions { display: flex; gap: 8px; margin-bottom: 16px; }
    .btn { padding: 12px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; border: none; text-align: center; text-decoration: none; transition: 0.2s; }
    .btn-scan { flex: 2; background: linear-gradient(135deg, #10b981, #059669); color: #042f1a; box-shadow: 0 4px 12px rgba(16,185,129,0.25); }
    .btn-scan:disabled { opacity: 0.5; }
    .btn-refresh { flex: 1; background: #1e293b; color: #f1f5f9; border: 1px solid #334155; }
    .btn-clear { background: transparent; color: #f43f5e; border: 1px solid rgba(244,63,94,0.3); padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; }
    .gallery-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 0 2px; }
    .gallery-title { font-size: 14px; font-weight: 700; color: #cbd5e1; text-transform: uppercase; letter-spacing: 0.5px; }
    .gallery { display: flex; flex-direction: column; gap: 10px; }
    .card { background: #131c2e; border-radius: 10px; padding: 12px 14px; border: 1px solid #1e293b; display: flex; justify-content: space-between; align-items: center; }
    .card-info { font-size: 14px; font-weight: 700; color: #f1f5f9; }
    .card-sub { font-size: 11px; color: #64748b; margin-top: 2px; }
    .card-actions { display: flex; gap: 6px; align-items: center; }
    .btn-view { background: #0284c7; color: white; padding: 6px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; text-decoration: none; }
    .btn-dl { background: #10b981; color: #042f1a; padding: 6px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; text-decoration: none; }
    .btn-del { background: rgba(244,63,94,0.15); color: #f43f5e; border: 1px solid rgba(244,63,94,0.3); padding: 6px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; }
    #toast { display: none; background: #10b981; color: #042f1a; padding: 10px; border-radius: 8px; margin-bottom: 12px; text-align: center; font-size: 13px; font-weight: 700; }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">KRISHI-DRISHTI</div>
    <div class="subtitle">AI-Assisted Offline Agro-Vision System</div>
    <div class="badges">
      <span class="badge badge-green">&#9679; OV5640 5MP</span>
      <span class="badge badge-blue">&#9679; 1600x1200 UXGA</span>
      <span class="badge badge-purple">&#9679; OFFLINE EDGE</span>
    </div>
  </div>

  <div id="toast"></div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-val" id="totalScans">-</div>
      <div class="stat-lbl">Photos</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">UXGA</div>
      <div class="stat-lbl">Quality</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:#10b981;">ONLINE</div>
      <div class="stat-lbl">SD Card</div>
    </div>
  </div>

  <div class="actions">
    <button class="btn btn-scan" id="scanBtn" onclick="triggerScan()">📸 CAPTURE LEAF</button>
    <button class="btn btn-refresh" onclick="loadGallery()">🔄 REFRESH</button>
  </div>

  <div class="actions" style="margin-bottom:12px;">
    <button class="btn" id="vfToggleBtn" onclick="toggleViewfinder()" style="flex:1; background:#1e293b; color:#38bdf8; border:1px solid #334155;">📹 VIEWFINDER</button>
    <button class="btn" id="autoSenseBtn" onclick="toggleAutoSense()" style="flex:1; background:#1e293b; color:#f59e0b; border:1px solid #334155;">⚡ AUTO-SENSE: OFF</button>
  </div>

  <div id="vfCard" style="display:none; margin-bottom:14px; background:#131c2e; border:1px solid #1e293b; border-radius:10px; overflow:hidden;">
    <div style="position:relative; width:100%; height:230px; background:#000;">
      <img id="vfImg" style="width:100%; height:100%; object-fit:cover; display:block;" src="" alt="Live Viewfinder">
      <div id="reticle" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:120px; height:120px; border:2px dashed #10b981; border-radius:12px; pointer-events:none; display:flex; align-items:center; justify-content:center; transition:0.2s;">
        <span id="vfTargetText" style="font-size:10px; font-weight:800; color:#10b981; background:rgba(0,0,0,0.6); padding:2px 6px; border-radius:4px;">LEAF TARGET</span>
      </div>
    </div>
    <div style="padding:10px 14px; display:flex; justify-content:space-between; align-items:center; font-size:11px;">
      <span id="vfStatus" style="color:#94a3b8;">🎯 Aim center reticle at plant leaf</span>
      <span id="vfGreenIndex" style="color:#10b981; font-weight:700;">Green: 0%</span>
    </div>
  </div>

  <div class="gallery-header">
    <span class="gallery-title">Stored Plant Scans</span>
    <button class="btn-clear" onclick="clearAllScans()">Clear All</button>
  </div>

  <div class="gallery" id="galleryList">
    <div style="text-align:center;padding:25px;color:#64748b;font-size:13px;">Loading scans...</div>
  </div>

  <script>
    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3000);
    }

    async function loadGallery() {
      try {
        const res = await fetch('/api/scans?t=' + Date.now());
        const data = await res.json();
        document.getElementById('totalScans').innerText = data.scans ? data.scans.length : 0;
        const list = document.getElementById('galleryList');
        if (!data.scans || data.scans.length === 0) {
          list.innerHTML = '<div style="text-align:center;padding:25px;color:#64748b;font-size:13px;">No scans stored on SD. Point at a leaf and tap 📸 CAPTURE LEAF or press controller button!</div>';
          return;
        }
        list.innerHTML = data.scans.map(s => `
          <div class="card">
            <div>
              <div class="card-info">🌿 Scan #${s.id}</div>
              <div class="card-sub">1600x1200 &bull; UXGA JPEG</div>
            </div>
            <div class="card-actions">
              <a class="btn-view" href="/image?id=${s.id}" target="_blank">View</a>
              <a class="btn-dl" href="/image?id=${s.id}&download=1" download>Save</a>
              <button class="btn-del" onclick="deleteScan(${s.id})">&#10005;</button>
            </div>
          </div>
        `).join('');
      } catch (e) {
        document.getElementById('galleryList').innerHTML = '<div style="text-align:center;color:#f43f5e;padding:15px;font-size:13px;">Error fetching scans. Tap 🔄 REFRESH.</div>';
      }
    }

    async function triggerScan() {
      const btn = document.getElementById('scanBtn');
      btn.disabled = true;
      btn.innerText = 'Capturing Leaf...';
      try {
        const res = await fetch('/api/capture');
        const data = await res.json();
        if (data.status === 'saved') {
          showToast('Leaf Scan #' + data.scan_id + ' Saved to SD!');
          await loadGallery();
        } else {
          alert('Capture failed: ' + (data.message || 'Error'));
        }
      } catch (e) {
        alert('Network error while capturing');
      } finally {
        btn.disabled = false;
        btn.innerText = '📸 CAPTURE LEAF';
      }
    }

    async function deleteScan(id) {
      if (!confirm('Delete Scan #' + id + ' from SD card?')) return;
      try {
        const res = await fetch('/api/delete?id=' + id);
        const data = await res.json();
        if (data.status === 'deleted') {
          showToast('Deleted Scan #' + id);
          loadGallery();
        } else {
          alert('Delete failed');
        }
      } catch(e) {
        alert('Error deleting scan');
      }
    }

    async function clearAllScans() {
      if (!confirm('Clear ALL plant scans from SD card?')) return;
      try {
        const res = await fetch('/api/delete?all=1');
        const data = await res.json();
        if (data.status === 'deleted_all') {
          showToast('All scans cleared from SD card');
          loadGallery();
        }
      } catch(e) {
        alert('Error clearing scans');
      }
    }

    let vfActive = false;
    let autoSenseActive = false;
    let vfTimer = null;
    let lastAutoCapture = 0;
    const probeCanvas = document.createElement('canvas');
    const pCtx = probeCanvas.getContext('2d');
    probeCanvas.width = 160;
    probeCanvas.height = 120;

    function toggleViewfinder() {
      vfActive = !vfActive;
      document.getElementById('vfCard').style.display = vfActive ? 'block' : 'none';
      const btn = document.getElementById('vfToggleBtn');
      btn.style.background = vfActive ? '#0284c7' : '#1e293b';
      btn.style.color = vfActive ? '#ffffff' : '#38bdf8';
      if (vfActive) {
        runVfLoop();
      } else {
        clearTimeout(vfTimer);
      }
    }

    function toggleAutoSense() {
      autoSenseActive = !autoSenseActive;
      const btn = document.getElementById('autoSenseBtn');
      btn.style.background = autoSenseActive ? 'linear-gradient(135deg, #f59e0b, #d97706)' : '#1e293b';
      btn.style.color = autoSenseActive ? '#000000' : '#f59e0b';
      btn.innerText = autoSenseActive ? '⚡ AUTO-SENSE: ON' : '⚡ AUTO-SENSE: OFF';
      if (autoSenseActive && !vfActive) {
        toggleViewfinder();
      }
    }

    function runVfLoop() {
      if (!vfActive) return;
      const img = document.getElementById('vfImg');
      const probe = new Image();
      const pUrl = '/api/preview?t=' + Date.now();

      probe.onload = function() {
        img.src = pUrl;

        if (autoSenseActive) {
          pCtx.drawImage(probe, 0, 0, 160, 120);
          const frame = pCtx.getImageData(50, 30, 60, 60);
          const d = frame.data;
          let greenHits = 0;
          let samples = d.length / 4;

          for (let i = 0; i < d.length; i += 4) {
            let r = d[i], g = d[i+1], b = d[i+2];
            if (g > 1.25 * r && g > 1.15 * b && g > 45) {
              greenHits++;
            }
          }

          let pct = Math.round((greenHits / samples) * 100);
          document.getElementById('vfGreenIndex').innerText = 'Green: ' + pct + '%';

          if (pct >= 35) {
            document.getElementById('reticle').style.borderColor = '#22c55e';
            document.getElementById('reticle').style.boxShadow = '0 0 16px #22c55e';
            document.getElementById('vfStatus').innerHTML = '✅ <b style="color:#22c55e">LEAF LOCKED! AUTO-FLASH...</b>';

            if (Date.now() - lastAutoCapture > 6000) {
              lastAutoCapture = Date.now();
              triggerScan();
            }
          } else {
            document.getElementById('reticle').style.borderColor = '#10b981';
            document.getElementById('reticle').style.boxShadow = 'none';
            document.getElementById('vfStatus').innerText = '🎯 Aim center reticle at plant leaf';
          }
        }

        if (vfActive) vfTimer = setTimeout(runVfLoop, 300);
      };

      probe.onerror = function() {
        if (vfActive) vfTimer = setTimeout(runVfLoop, 600);
      };

      probe.src = pUrl;
    }

    loadGallery();
  </script>
</body>
</html>)rawliteral";

void handleRoot() {
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.send_P(200, "text/html", ROOT_HTML);
}

// --------------------------------------------------
// STREAM IMAGE FROM SD CARD (CONCURRENCY-PROTECTED)
// --------------------------------------------------

static bool isStreaming = false;

void handleGetImage() {
  if (!sdReady) {
    server.send(503, "text/plain", "SD card not ready");
    return;
  }

  if (isStreaming) {
    server.send(429, "text/plain", "Camera busy streaming another photo, please wait 1 second");
    return;
  }

  isStreaming = true;

  String filename = "";
  if (server.hasArg("id")) {
    char buf[32];
    snprintf(buf, sizeof(buf), "/scan_%06lu.jpg", (unsigned long)server.arg("id").toInt());
    filename = String(buf);
  } else if (server.hasArg("file")) {
    filename = server.arg("file");
    if (!filename.startsWith("/")) {
      filename = "/" + filename;
    }
  } else {
    isStreaming = false;
    server.send(400, "text/plain", "Missing 'id' or 'file' query parameter");
    return;
  }

  if (!SD_MMC.exists(filename.c_str())) {
    isStreaming = false;
    server.send(404, "text/plain", "File not found: " + filename);
    return;
  }

  File f = SD_MMC.open(filename.c_str(), FILE_READ);
  if (!f) {
    isStreaming = false;
    server.send(500, "text/plain", "Failed to open file for reading");
    return;
  }

  if (server.hasArg("download")) {
    server.sendHeader("Content-Disposition", "attachment; filename=\"" + filename.substring(1) + "\"");
  }

  server.streamFile(f, "image/jpeg");
  f.close();

  isStreaming = false;
}

// --------------------------------------------------
// LIST SCANS (FAST - CACHE-BUSTED & ACCURATE)
// --------------------------------------------------

void handleListScans() {
  if (!sdReady) {
    server.send(503, "application/json", "{\"status\":\"error\",\"message\":\"sd_not_ready\"}");
    return;
  }

  String json = "{\"total\":";
  json += String(scanCounter);
  json += ",\"scans\":[";

  bool first = true;
  for (int32_t i = scanCounter; i >= 1; i--) {
    char buf[32];
    snprintf(buf, sizeof(buf), "/scan_%06lu.jpg", (unsigned long)i);
    if (SD_MMC.exists(buf)) {
      if (!first) json += ",";
      json += "{\"id\":";
      json += String(i);
      json += ",\"file\":\"";
      json += String(buf);
      json += "\"}";
      first = false;
    }
  }
  json += "]}";

  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.send(200, "application/json", json);
}

// --------------------------------------------------
// DELETE SCAN(S) FROM SD CARD
// --------------------------------------------------

void handleDelete() {
  if (!sdReady) {
    server.send(503, "application/json", "{\"status\":\"error\",\"message\":\"sd_not_ready\"}");
    return;
  }

  if (server.hasArg("all")) {
    for (uint32_t i = 1; i <= scanCounter; i++) {
      char buf[32];
      snprintf(buf, sizeof(buf), "/scan_%06lu.jpg", (unsigned long)i);
      if (SD_MMC.exists(buf)) {
        SD_MMC.remove(buf);
      }
    }
    scanCounter = 0;
    server.send(200, "application/json", "{\"status\":\"deleted_all\"}");
    return;
  }

  if (!server.hasArg("id")) {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"missing_id\"}");
    return;
  }

  uint32_t id = server.arg("id").toInt();
  char buf[32];
  snprintf(buf, sizeof(buf), "/scan_%06lu.jpg", (unsigned long)id);

  if (SD_MMC.exists(buf)) {
    SD_MMC.remove(buf);
    server.send(200, "application/json", "{\"status\":\"deleted\",\"id\":" + String(id) + "}");
  } else {
    server.send(404, "application/json", "{\"status\":\"error\",\"message\":\"not_found\"}");
  }
}

// --------------------------------------------------
// AI DIAGNOSIS BRIDGE (PHONE -> CAMERA -> CONTROLLER)
// --------------------------------------------------

void handleGetDiagnosis() {
  String json = "{\"ready\":";
  json += (diagnosisReady ? "true" : "false");
  json += ",\"scan_id\":";
  json += String(diagScanId);
  json += ",\"crop\":\"";
  json += diagCrop;
  json += "\",\"disease\":\"";
  json += diagDisease;
  json += "\",\"confidence\":";
  json += String(diagConfidence, 1);
  json += ",\"status\":\"";
  json += diagStatus;
  json += "\",\"organic\":\"";
  json += diagOrganic;
  json += "\",\"chemical\":\"";
  json += diagChemical;
  json += "\"}";

  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.send(200, "application/json", json);
}

void handleSetDiagnosis() {
  if (server.hasArg("scan_id")) diagScanId = server.arg("scan_id").toInt();
  if (server.hasArg("crop")) diagCrop = server.arg("crop");
  if (server.hasArg("disease")) diagDisease = server.arg("disease");
  if (server.hasArg("confidence")) diagConfidence = server.arg("confidence").toFloat();
  if (server.hasArg("status")) diagStatus = server.arg("status");
  if (server.hasArg("organic")) diagOrganic = server.arg("organic");
  if (server.hasArg("chemical")) diagChemical = server.arg("chemical");

  diagnosisReady = true;

  Serial.println();
  Serial.println("========================================");
  Serial.println("    AI DIAGNOSIS RECEIVED FROM PHONE");
  Serial.println("========================================");
  Serial.printf("Crop: %s | Disease: %s | Conf: %.1f%%\n", diagCrop.c_str(), diagDisease.c_str(), diagConfidence);
  Serial.printf("Status: %s\n", diagStatus.c_str());
  Serial.printf("Organic: %s\n", diagOrganic.c_str());
  Serial.printf("Chemical: %s\n", diagChemical.c_str());
  Serial.println("========================================");

  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"diagnosis_stored\"}");
}

// --------------------------------------------------
// LIVE VIEWFINDER PREVIEW (MEMORY-STREAMED FROM PSRAM)
// --------------------------------------------------

void handlePreview() {
  if (!cameraReady) {
    server.send(503, "text/plain", "Camera offline");
    return;
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Frame error");
    return;
  }

  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// --------------------------------------------------
// 404 NOT FOUND (FALLBACK TO DIRECT SD JPG LOOKUP)
// --------------------------------------------------

void handleNotFound() {
  String uri = server.uri();
  if (sdReady && uri.endsWith(".jpg") && SD_MMC.exists(uri.c_str())) {
    File f = SD_MMC.open(uri.c_str(), FILE_READ);
    if (f) {
      server.streamFile(f, "image/jpeg");
      f.close();
      return;
    }
  }
  server.send(404, "text/plain", "404: Not Found");
}

// --------------------------------------------------
// SETUP
// --------------------------------------------------

void setup() {

  Serial.begin(115200);
  setCpuFrequencyMhz(240); // Lock ESP32-CAM to full 240MHz for max Wi-Fi & SD performance

  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("     KRISHI-DRISHTI CAMERA");
  Serial.println("================================");

  Serial.printf(
    "Free heap at boot: %u bytes\n",
    ESP.getFreeHeap()
  );

  // Initialize Flash LED on GPIO 4
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW); // Flash LED off by default

  // 1. Camera
  cameraReady = initialiseCamera();

  // 2. SD card
  sdReady = initialiseSD();

  // 3. Recover next available scan number.
  if (sdReady) {
    findNextScanNumber();
  }

  // 4. Wi-Fi AP
  Serial.println();
  Serial.println("Starting Wi-Fi access point...");

  WiFi.mode(WIFI_AP);

  bool apStarted = WiFi.softAP(
    AP_SSID,
    AP_PASSWORD
  );

  Serial.printf(
    "Wi-Fi AP: %s\n",
    apStarted ? "STARTED" : "FAILED"
  );

  Serial.print("Camera IP: ");
  Serial.println(WiFi.softAPIP());

  // 5. HTTP endpoints
  server.on(
    "/",
    HTTP_GET,
    handleRoot
  );

  server.on(
    "/api/status",
    HTTP_GET,
    handleStatus
  );

  server.on(
    "/api/capture",
    HTTP_GET,
    handleCapture
  );

  server.on(
    "/api/scans",
    HTTP_GET,
    handleListScans
  );

  server.on(
    "/image",
    HTTP_GET,
    handleGetImage
  );

  server.on(
    "/api/delete",
    HTTP_GET,
    handleDelete
  );

  server.on(
    "/api/diagnosis",
    HTTP_GET,
    handleGetDiagnosis
  );

  server.on(
    "/api/diagnosis/set",
    HTTP_GET,
    handleSetDiagnosis
  );

  server.on(
    "/api/diagnosis/set",
    HTTP_POST,
    handleSetDiagnosis
  );

  server.on(
    "/api/preview",
    HTTP_GET,
    handlePreview
  );

  server.onNotFound(
    handleNotFound
  );

  server.begin();

  Serial.println();
  Serial.println("HTTP server started.");

  Serial.println("--------------------------------");

  Serial.printf(
    "Camera ready: %s\n",
    cameraReady ? "YES" : "NO"
  );

  Serial.printf(
    "SD ready: %s\n",
    sdReady ? "YES" : "NO"
  );

  Serial.printf(
    "PSRAM: %s\n",
    psramAvailable ? "YES" : "NO"
  );

  Serial.println("Resolution: UXGA 1600x1200");
  Serial.println("JPEG quality: 10");

  Serial.println("--------------------------------");
  Serial.println("KRISHI-DRISHTI startup complete.");
}

// --------------------------------------------------
// MAIN LOOP
// --------------------------------------------------

void loop() {

  server.handleClient();

  delay(2);
}
