/*
  ==============================================================================
  KRISHI-DRISHTI (कृषि-दृष्टि) - Official Camera Unit Firmware v2.2
  Target Hardware: AI-Thinker ESP32-CAM (ESP-32S) + ESP32-CAM-MB Programmer Shield
  Optics: OV5640 / OV2640 Dual-Support Auto-Detection (UXGA 1600x1200)
  Storage: Onboard MicroSD in SD_MMC 1-Bit Mode (DMA Accelerated)
  Networking: SoftAP "KRISHI-DRISHTI" @ 192.168.4.1 (100% Offline Mesh)
  Author: Gautam Kumar / KRISHI-DRISHTI Project
  ==============================================================================
*/

#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"
#include <WiFi.h>
#include <WebServer.h>

// --------------------------------------------------
// CAMERA HARDWARE PIN DEFINITIONS (AI-Thinker)
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

#define FLASH_LED_PIN      4  // High-power onboard illumination LED

// --------------------------------------------------
// WI-FI SOFTAP CREDENTIALS
// --------------------------------------------------
const char* AP_SSID = "KRISHI-DRISHTI";
const char* AP_PASSWORD = "12345678";

// --------------------------------------------------
// SERVER AND GLOBAL TELEMETRY STATE
// --------------------------------------------------
WebServer server(80);

bool cameraReady = false;
bool sdReady = false;
bool psramAvailable = false;
String sensorModel = "Unknown";

uint32_t scanCounter = 0;
float lastCanopyTemp = 0.0;
float lastCanopyHum = 0.0;
bool canopyTelemetryPresent = false;
unsigned long lastWandActivityMs = 0;
static bool isStreaming = false;

// AI Diagnosis Bridge State (Phone AI Daemon <-> Camera <-> Controller Wand)
bool diagnosisReady = false;
uint32_t diagScanId = 0;
String diagCrop = "Tomato";
String diagDisease = "Healthy";
float diagConfidence = 98.0;
String diagStatus = "HEALTHY";
String diagOrganic = "Maintain balanced irrigation & NPK";
String diagChemical = "No chemical intervention needed";

// --------------------------------------------------
// EMBEDDED EDGE AI SERVER DAEMON (SERVED AT /)
// --------------------------------------------------
const char AI_SERVER_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>KRISHI-DRISHTI :: Edge AI Co-Processor Daemon</title>
  
  <!-- Bundled Offline TensorFlow.js & TFLite WASM Runtimes -->
  <script src="/vendor/tf.min.js"></script>
  <script src="/vendor/tf-tflite.min.js"></script>

  <style>
    :root {
      --bg-dark: #0a0e14;
      --card-bg: #111722;
      --card-border: #1e293b;
      --accent-green: #10b981;
      --accent-green-dim: rgba(16, 185, 129, 0.15);
      --accent-cyan: #06b6d4;
      --accent-amber: #f59e0b;
      --accent-red: #ef4444;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --font-mono: "SF Mono", Monaco, Consolas, "Liberation Mono", Menlo, Courier, monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: var(--font-sans);
      padding: 14px;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      gap: 12px;
      -webkit-font-smoothing: antialiased;
    }

    /* Top Brand Card */
    .brand-card {
      background: linear-gradient(135deg, #111927 0%, #162032 100%);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 14px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }
    .brand-title {
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 0.8px;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand-title .badge-tag {
      background: var(--accent-green-dim);
      color: var(--accent-green);
      font-size: 10px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 6px;
      border: 1px solid rgba(16, 185, 129, 0.3);
      font-family: var(--font-mono);
    }
    .brand-subtitle {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 3px;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 700;
      padding: 5px 11px;
      border-radius: 20px;
      font-family: var(--font-mono);
      letter-spacing: 0.5px;
      transition: all 0.25s ease;
    }
    .pill-active {
      background: rgba(16, 185, 129, 0.18);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .pill-stopped {
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .pulsing-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: currentColor;
      box-shadow: 0 0 8px currentColor;
      animation: pulse 1.6s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    /* Grid of Telemetry Metrics */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
      gap: 8px;
    }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 8px 10px;
      text-align: left;
    }
    .metric-label {
      font-size: 9px;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 2px;
    }
    .metric-value {
      font-size: 12px;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text-main);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* MicroSD Hardware Health Card */
    .sd-audit-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.3s ease;
    }
    .sd-status-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }
    .sd-indicator-box {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .sd-badge-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--accent-amber);
      display: inline-block;
      flex-shrink: 0;
    }
    .sd-badge-dot.sd-ok {
      background: var(--accent-green);
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.4);
    }
    .sd-badge-dot.sd-alert {
      background: var(--accent-red);
      box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
      animation: pulse 1s infinite;
    }
    .sd-title-text {
      font-size: 13px;
      font-weight: 700;
      color: var(--text-main);
    }
    .sd-detail-text {
      font-size: 11px;
      line-height: 1.4;
      color: var(--text-dim);
    }
    .btn-check-sd {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--card-border);
      color: var(--text-main);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
      font-family: var(--font-sans);
      transition: background 0.2s;
    }
    .btn-check-sd:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    /* Diagnosis Visualizer Box */
    .diagnosis-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .card-header-label {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--accent-cyan);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .diagnosis-body {
      display: flex;
      gap: 14px;
      align-items: center;
    }
    .leaf-thumb-wrap {
      width: 76px;
      height: 76px;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      background: #000;
      position: relative;
      overflow: hidden;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .leaf-thumb-wrap img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .leaf-thumb-wrap .placeholder-text {
      font-size: 9px;
      color: var(--text-dim);
      text-align: center;
      padding: 4px;
      font-family: var(--font-mono);
    }
    .diag-details {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .diag-primary {
      font-size: 15px;
      font-weight: 700;
      color: #ffffff;
    }
    .diag-pathogen {
      font-size: 11px;
      font-style: italic;
      color: var(--text-muted);
    }
    .diag-confidence {
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--accent-green);
      font-weight: 600;
      margin-top: 2px;
    }

    /* Prescription Drawer */
    .prescription-box {
      background: #0d131d;
      border-left: 3px solid var(--accent-green);
      border-radius: 4px 8px 8px 4px;
      padding: 10px 12px;
      font-size: 11px;
      line-height: 1.5;
    }
    .rx-label {
      font-weight: 700;
      color: var(--accent-green);
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0.5px;
      margin-bottom: 2px;
    }
    .rx-text {
      color: var(--text-main);
    }
    .rx-chem {
      color: var(--text-muted);
      margin-top: 4px;
      font-size: 10px;
    }

    /* Terminal Console */
    .terminal-container {
      flex: 1;
      background: #090d13;
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 12px;
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1.55;
      overflow-y: auto;
      max-height: 260px;
      min-height: 140px;
      display: flex;
      flex-direction: column;
      box-shadow: inset 0 2px 8px rgba(0,0,0,0.5);
    }
    .log-line {
      margin-bottom: 2px;
      word-break: break-all;
    }
    .log-t { color: var(--text-dim); }
    .log-tag-info { color: var(--accent-cyan); }
    .log-tag-ok { color: var(--accent-green); font-weight: bold; }
    .log-tag-warn { color: var(--accent-amber); }
    .log-tag-err { color: var(--accent-red); font-weight: bold; }

    /* Action Controls */
    .controls-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 10px;
      margin-top: 4px;
    }
    .btn {
      padding: 14px 16px;
      font-size: 13px;
      font-weight: 700;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: var(--font-sans);
      transition: all 0.2s ease;
      letter-spacing: 0.3px;
    }
    .btn-primary {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
    }
    .btn-stop {
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35);
    }
    .btn-secondary {
      background: #1e293b;
      color: var(--text-main);
      border: 1px solid var(--card-border);
    }
    .btn:active {
      transform: scale(0.98);
    }

    /* Sample Real Leaf Palette */
    .sample-btn-row {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
      margin-top: 2px;
    }
    .btn-sample {
      padding: 10px 4px;
      font-size: 11px;
      font-weight: 700;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      text-align: center;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      background: #141b27;
      color: var(--text-main);
      font-family: var(--font-sans);
      transition: all 0.2s ease;
      text-decoration: none;
    }
    .btn-sample:active {
      transform: scale(0.96);
    }
    .btn-sample-blight {
      border-color: rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }
    .btn-sample-healthy {
      border-color: rgba(16, 185, 129, 0.4);
      color: #6ee7b7;
    }
    .btn-sample-upload {
      border-color: rgba(6, 182, 212, 0.4);
      color: #67e8f9;
    }

    .footer-note {
      text-align: center;
      font-size: 10px;
      color: var(--text-dim);
      font-family: var(--font-mono);
      padding-top: 4px;
    }

    canvas { display: none; }
  </style>
</head>
<body>

  <!-- Brand & Status Header -->
  <div class="brand-card">
    <div>
      <div class="brand-title">
        KRISHI-DRISHTI
        <span class="badge-tag">v2.2 EDGE</span>
      </div>
      <div class="brand-subtitle">Headless Neural Co-Processor &bull; MobileNetV3 TFLite</div>
    </div>
    <div id="statusPill" class="status-pill pill-stopped">
      <span class="pulsing-dot"></span>
      <span id="statusText">STANDBY</span>
    </div>
  </div>

  <!-- Telemetry Metrics Bar (5 Core Parameters) -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-label">Cam Gateway</div>
      <div class="metric-value" id="valCameraLink" style="color: var(--text-dim)">SEARCHING...</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">MicroSD Slot</div>
      <div class="metric-value" id="valSdStatus" style="color: var(--accent-amber)">CHECKING...</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Wand Link</div>
      <div class="metric-value" id="valWandLink" style="color: var(--text-dim)">WAND OFF</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">TFLite Engine</div>
      <div class="metric-value" id="valEngine" style="color: var(--accent-amber)">LOADING...</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Scans Synced</div>
      <div class="metric-value" id="valScanCount">0</div>
    </div>
  </div>

  <!-- MicroSD Hardware Presence & Health Section -->
  <div class="sd-audit-card" id="sdAuditCard" style="border-color: rgba(245, 158, 11, 0.3);">
    <div class="sd-status-row">
      <div class="sd-indicator-box">
        <span class="sd-badge-dot" id="sdBadgeDot"></span>
        <span class="sd-title-text" id="sdTitleText">Checking MicroSD Card Slot...</span>
      </div>
      <button class="btn-check-sd" onclick="pollMeshNow()">RE-CHECK HARDWARE</button>
    </div>
    <div class="sd-detail-text" id="sdDetailText">
      Querying camera slot for Class 10 FAT32 card and offline model weights...
    </div>
  </div>

  <!-- Live Diagnosis Result Box -->
  <div class="diagnosis-card">
    <div class="card-header-label">
      <span>Latest Edge AI Diagnosis</span>
      <span id="scanTimestamp" style="font-family: var(--font-mono); font-size: 10px; color: var(--text-dim);">AWAITING SCAN</span>
    </div>

    <div class="diagnosis-body">
      <div class="leaf-thumb-wrap" id="leafThumbWrap">
        <span class="placeholder-text" id="thumbPlaceholder">LEAF FRAME</span>
        <img id="leafImg" style="display: none;" alt="Leaf Scan" />
      </div>

      <div class="diag-details">
        <div class="diag-primary" id="diagPrimary">Waiting for Wand [SCAN]</div>
        <div class="diag-pathogen" id="diagPathogen">Mesh SoftAP: KRISHI-DRISHTI (192.168.4.1)</div>
        <div class="diag-confidence" id="diagConfidence">MobileNetV3 Edge Core: 2.01 MB TFLite</div>
      </div>
    </div>

    <div class="prescription-box" id="prescBox">
      <div class="rx-label" id="rxLabel">Agronomic Advisory & Treatment</div>
      <div class="rx-text" id="rxBio">Keep phone in pocket. When you press SCAN on the wand, results sync here and to the SSD1306 OLED automatically.</div>
      <div class="rx-chem" id="rxChem">Chemical: Integrated Pest Management (IPM) guidelines.</div>
    </div>
  </div>

  <!-- Live Terminal Console -->
  <div class="terminal-container" id="terminal">
    <div class="log-line"><span class="log-t">[SYSTEM]</span> <span class="log-tag-info">INIT</span> KRISHI-DRISHTI Edge AI Server daemon loaded.</div>
    <div class="log-line"><span class="log-t">[SYSTEM]</span> <span class="log-tag-info">MESH</span> SoftAP gateway target: http://192.168.4.1</div>
  </div>

  <!-- Action Controls -->
  <div class="controls-grid">
    <button class="btn btn-primary" id="btnToggle" onclick="toggleServer()">
      START AI SERVER
    </button>
    <button class="btn btn-secondary" onclick="simulateFieldScan()">
      TEST DEMO
    </button>
  </div>

  <!-- Real Leaf Exhibition Test Palette -->
  <div class="sample-btn-row">
    <button class="btn-sample btn-sample-blight" onclick="testRealLeaf('/sample_leaves/late_blight_512.jpg', 'Real Tomato Late Blight')">
      🍂 Real Blight
    </button>
    <button class="btn-sample btn-sample-healthy" onclick="testRealLeaf('/sample_leaves/healthy_512.jpg', 'Real Tomato Healthy')">
      🌿 Real Healthy
    </button>
    <label class="btn-sample btn-sample-upload">
      📷 Upload Photo
      <input type="file" id="leafFileInput" accept="image/*" style="display: none;" onchange="handleLeafUpload(event)">
    </label>
  </div>

  <div class="footer-note">
    KRISHI-DRISHTI &bull; Offline Edge AI Plant Telemetry &bull; Source Available
  </div>

  <canvas id="offscreenCanvas" width="128" height="128"></canvas>

  <script>
    let isRunning = false;
    let pollInterval = null;
    let lastProcessedScanId = 0;
    let wakeLock = null;
    let keepAliveAudio = null;
    let totalScansProcessed = 0;

    let tfliteModel = null;
    let modelReady = false;
    let isModelLoading = false;
    let currentTelemetry = null;

    const CAMERA_STATUS_URL   = "http://192.168.4.1/api/status";
    const CAMERA_IMAGE_URL    = "http://192.168.4.1/image?id=";
    const CAMERA_DIAG_SET_URL = "http://192.168.4.1/api/diagnosis/set";

    // STRICT CLASS ORDERING - 100% IDENTICAL 1:1 MATCH WITH labels.json & MODEL OUTPUT
    const KB_CLASSES = [
      {
        id: 0,
        name: "Tomato___Late_blight",
        crop: "Tomato",
        disease: "Late Blight",
        pathogen: "Phytophthora infestans (Oomycete)",
        status: "INFECTED",
        organic: "Neem Oil 5ml/L + Trichoderma viride. Prune lower canopy.",
        chemical: "Cymoxanil 8% + Mancozeb 64% WP @ 2.5g/L or Ridomil Gold @ 2g/L"
      },
      {
        id: 1,
        name: "Tomato___Early_blight",
        crop: "Tomato",
        disease: "Early Blight",
        pathogen: "Alternaria solani (Fungus)",
        status: "WARNING",
        organic: "Baking soda 5g/L + compost tea. Mulch soil to prevent rain splash.",
        chemical: "Chlorothalonil 75% WP @ 2g/L or Copper Oxychloride 3g/L"
      },
      {
        id: 2,
        name: "Tomato___healthy",
        crop: "Tomato",
        disease: "Healthy",
        pathogen: "Optimal (Zero Pathogen)",
        status: "HEALTHY",
        organic: "Maintain drip irrigation schedule & balanced 19:19:19 NPK.",
        chemical: "No chemical fungicides required."
      },
      {
        id: 3,
        name: "Potato___Late_blight",
        crop: "Potato",
        disease: "Late Blight",
        pathogen: "Phytophthora infestans (Oomycete)",
        status: "INFECTED",
        organic: "Copper soap spray + haulm destruction 10 days pre-harvest.",
        chemical: "Cymoxanil 8% + Mancozeb 64% WP @ 2.5g/L"
      },
      {
        id: 4,
        name: "Potato___Early_blight",
        crop: "Potato",
        disease: "Early Blight",
        pathogen: "Alternaria solani (Fungus)",
        status: "WARNING",
        organic: "Crop rotation with non-solanaceous crops + Neem cake soil drench.",
        chemical: "Azoxystrobin 23% SC @ 1.0ml/L"
      },
      {
        id: 5,
        name: "Potato___healthy",
        crop: "Potato",
        disease: "Healthy",
        pathogen: "Optimal (Zero Pathogen)",
        status: "HEALTHY",
        organic: "Regular earthing-up and balanced potassium application.",
        chemical: "No chemical fungicides required."
      }
    ];

    function log(msg, type = "info") {
      const term = document.getElementById("terminal");
      const d = new Date();
      const timeStr = d.toTimeString().split(' ')[0];

      let tagClass = "log-tag-info";
      let tagLabel = "INFO";

      if (type === "ok") {
        tagClass = "log-tag-ok";
        tagLabel = "SUCCESS";
      } else if (type === "warn") {
        tagClass = "log-tag-warn";
        tagLabel = "WARN";
      } else if (type === "err") {
        tagClass = "log-tag-err";
        tagLabel = "ERROR";
      } else if (type === "ai") {
        tagClass = "log-tag-ok";
        tagLabel = "NEURAL";
      }

      const line = document.createElement("div");
      line.className = "log-line";
      line.innerHTML = `<span class="log-t">[${timeStr}]</span> <span class="${tagClass}">${tagLabel}</span> ${msg}`;
      term.appendChild(line);
      term.scrollTop = term.scrollHeight;
    }

    // INITIALIZE OFFLINE TFLITE WASM RUNTIME
    async function initTFLite(retryCount = 0) {
      if (modelReady || isModelLoading) return;
      isModelLoading = true;
      try {
        if (typeof tflite === 'undefined') {
          if (retryCount < 20) {
            document.getElementById("valEngine").innerText = "INITIALIZING...";
            document.getElementById("valEngine").style.color = "var(--accent-amber)";
            setTimeout(() => {
              isModelLoading = false;
              initTFLite(retryCount + 1);
            }, 300);
            return;
          }
          throw new Error("tflite WASM backend not found in vendor/");
        }
        document.getElementById("valEngine").innerText = "LOADING MODEL...";
        document.getElementById("valEngine").style.color = "var(--accent-amber)";
        log("Booting bundled WASM TFLite co-processor engine...", "ai");
        tflite.setWasmPath('/vendor/');
        tfliteModel = await tflite.loadTFLiteModel('/krishi_drishti_model.tflite');
        modelReady = true;
        document.getElementById("valEngine").innerText = "TFLITE ACTIVE";
        document.getElementById("valEngine").style.color = "var(--accent-green)";
        log("MobileNetV3 Edge TFLite core loaded 100% offline.", "ok");
      } catch (err) {
        modelReady = false;
        document.getElementById("valEngine").innerText = "AI OFFLINE";
        document.getElementById("valEngine").style.color = "var(--accent-red)";
        log(`TFLite load error: ${err.message}. Inference paused until model available.`, "err");
      } finally {
        isModelLoading = false;
      }
    }

    async function requestWakeLock() {
      try {
        if ('wakeLock' in navigator) {
          wakeLock = await navigator.wakeLock.request('screen');
          wakeLock.addEventListener('release', () => {
            log("Screen WakeLock released by OS power management.", "ai");
            wakeLock = null;
          });
          log("Hardware Screen WakeLock active across mobile browser.", "ok");
        }
      } catch (err) {
        log(`WakeLock notice (${err.name || 'unsupported'}): using audio-thread keep-alive.`, "warn");
      }
      startKeepAliveAudio();
    }

    function startKeepAliveAudio() {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          if (!keepAliveAudio) {
            keepAliveAudio = new AudioCtx();
            const osc = keepAliveAudio.createOscillator();
            const gain = keepAliveAudio.createGain();
            gain.gain.value = 0.00001; // Inaudible buffer keeps mobile event loop unthrottled in pocket
            osc.connect(gain);
            gain.connect(keepAliveAudio.destination);
            osc.start();
          } else if (keepAliveAudio.state === 'suspended') {
            keepAliveAudio.resume();
          }
        }
      } catch (e) {}
    }

    function stopKeepAliveAudio() {
      try {
        if (keepAliveAudio) {
          keepAliveAudio.close();
          keepAliveAudio = null;
        }
      } catch (e) {}
    }

    // Auto re-acquire WakeLock whenever phone is unlocked or screen wakes
    document.addEventListener("visibilitychange", async () => {
      if (document.visibilityState === "visible" && isRunning) {
        log("Screen restored to foreground — re-asserting WakeLock...", "ai");
        await requestWakeLock();
      }
    });

    function toggleServer() {
      if (!isRunning) startServer();
      else stopServer();
    }

    function startServer() {
      isRunning = true;
      requestWakeLock();

      const pill = document.getElementById("statusPill");
      pill.className = "status-pill pill-active";
      document.getElementById("statusText").innerText = "INFERENCE ACTIVE";

      const btn = document.getElementById("btnToggle");
      btn.innerText = "STOP AI SERVER";
      btn.className = "btn btn-stop";

      log("Edge AI Co-Processor started. Polling softAP mesh...", "ok");
      pollInterval = setInterval(checkCameraForNewScan, 600);
    }

    function stopServer() {
      isRunning = false;
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
      if (wakeLock) {
        try { wakeLock.release(); } catch(e) {}
        wakeLock = null;
      }
      stopKeepAliveAudio();

      const pill = document.getElementById("statusPill");
      pill.className = "status-pill pill-stopped";
      document.getElementById("statusText").innerText = "STANDBY";

      const btn = document.getElementById("btnToggle");
      btn.innerText = "START AI SERVER";
      btn.className = "btn btn-primary";

      const camEl = document.getElementById("valCameraLink");
      if (camEl) {
        camEl.innerText = "STANDBY";
        camEl.style.color = "var(--text-dim)";
      }
      const wandEl = document.getElementById("valWandLink");
      if (wandEl) {
        wandEl.innerText = "STANDBY";
        wandEl.style.color = "var(--text-dim)";
      }
      log("AI Server stopped by operator.", "warn");
    }

    async function pollMeshNow() {
      log("Manually auditing ESP32-CAM hardware & SD slot...", "ai");
      await checkCameraForNewScan();
    }

    async function checkCameraForNewScan() {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 750);

        const res = await fetch(CAMERA_STATUS_URL, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!res.ok) return;
        const status = await res.json();

        // 1. Camera Gateway Link
        const camEl = document.getElementById("valCameraLink");
        if (camEl) {
          camEl.innerText = "ONLINE (AP)";
          camEl.style.color = "var(--accent-green)";
        }

        // 2. MicroSD Card Detection & Verification
        const sdEl = document.getElementById("valSdStatus");
        const sdCard = document.getElementById("sdAuditCard");
        const sdDot = document.getElementById("sdBadgeDot");
        const sdTitle = document.getElementById("sdTitleText");
        const sdDetail = document.getElementById("sdDetailText");

        if (status.sd_ready) {
          const capText = status.sd_capacity_mb ? `${Math.round(status.sd_capacity_mb/1024*10)/10} GB` : "FAT32";
          if (sdEl) {
            sdEl.innerText = `READY (${capText})`;
            sdEl.style.color = "var(--accent-green)";
          }
          if (sdCard) sdCard.style.borderColor = "rgba(34, 197, 94, 0.3)";
          if (sdDot) { sdDot.className = "sd-badge-dot sd-ok"; }
          if (sdTitle) { sdTitle.innerText = `MicroSD Card: Detected & Mounted (${capText})`; }
          if (sdDetail) {
            sdDetail.innerText = "Camera filesystem active. Offline MobileNetV3 TFLite weights & WASM assets available. All shutter scans saved to /scans/.";
          }
          // If model was not loaded due to previous missing SD card, initialize it now!
          if (!modelReady && !isModelLoading) {
            initTFLite(0);
          }
        } else {
          if (sdEl) {
            sdEl.innerText = "NOT DETECTED";
            sdEl.style.color = "var(--accent-red)";
          }
          if (sdCard) sdCard.style.borderColor = "rgba(239, 68, 68, 0.4)";
          if (sdDot) { sdDot.className = "sd-badge-dot sd-alert"; }
          if (sdTitle) { sdTitle.innerText = "⚠️ MicroSD Card NOT DETECTED in ESP32-CAM Slot!"; }
          if (sdDetail) {
            sdDetail.innerHTML = "<b style='color: var(--accent-red)'>Card missing in camera.</b> If inserted in PC (Drive E:), unplug it and firmly push it into the TF slot on the ESP32-CAM board, then tap RE-CHECK HARDWARE.";
          }
        }

        // 3. Wand Controller Connectivity
        const wandEl = document.getElementById("valWandLink");
        if (wandEl) {
          if (status.wand_connected) {
            wandEl.innerText = "CONNECTED";
            wandEl.style.color = "var(--accent-green)";
          } else {
            wandEl.innerText = "WAND OFF";
            wandEl.style.color = "var(--text-dim)";
          }
        }

        // 4. Microclimate Canopy Telemetry
        if (status.telemetry_available && status.humidity > 0) {
          currentTelemetry = {
            humidity: status.humidity,
            temperature: status.temperature
          };
        } else {
          currentTelemetry = null;
        }

        // 5. Automatic Shutter Sync
        const latestScanId = status.scan_count || 0;
        if (latestScanId > lastProcessedScanId && latestScanId > 0) {
          log(`New leaf captured by Wand! Scan #${latestScanId}`, "ai");
          lastProcessedScanId = latestScanId;
          await processScanAndRespond(latestScanId);
        }
      } catch (e) {
        const camEl = document.getElementById("valCameraLink");
        if (camEl) {
          camEl.innerText = "SEARCHING...";
          camEl.style.color = "var(--accent-amber)";
        }
        const sdEl = document.getElementById("valSdStatus");
        if (sdEl) {
          sdEl.innerText = "STANDBY";
          sdEl.style.color = "var(--text-dim)";
        }
        const wandEl = document.getElementById("valWandLink");
        if (wandEl) {
          wandEl.innerText = "STANDBY";
          wandEl.style.color = "var(--text-dim)";
        }
      }
    }

    async function processScanAndRespond(scanId) {
      const t0 = performance.now();
      log(`Retrieving Scan #${scanId} frame over 2.4GHz softAP...`);

      try {
        const img = new Image();
        img.crossOrigin = "anonymous";
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          setTimeout(reject, 4000);
          img.src = `${CAMERA_IMAGE_URL}${scanId}&t=${Date.now()}`;
        });

        const leafImg = document.getElementById("leafImg");
        const placeholder = document.getElementById("thumbPlaceholder");
        leafImg.src = img.src;
        leafImg.style.display = "block";
        placeholder.style.display = "none";

        log(`Scan #${scanId} loaded into RAM. Running genuine neural inference...`, "ai");
        const diag = await runEdgeInference(img);
        const elapsed = Math.round(performance.now() - t0);

        updateMetricsAndUI(diag, elapsed, scanId);
        playAudioChime();

        log(`Diagnosis: ${diag.crop} - ${diag.disease} (${diag.confidence}%, H=${diag.entropy}) in ${elapsed}ms`, "ok");
        log(`Advisory: ${diag.organic}`);

        // Post back to ESP32-CAM bridge for Wand OLED via standard CORS with response checking
        const setUrl = `${CAMERA_DIAG_SET_URL}?scan_id=${scanId}&crop=${encodeURIComponent(diag.crop)}&disease=${encodeURIComponent(diag.disease)}&confidence=${diag.confidence}&status=${encodeURIComponent(diag.status)}&organic=${encodeURIComponent(diag.organic)}&chemical=${encodeURIComponent(diag.chemical)}`;

        try {
          const syncRes = await fetch(setUrl);
          if (syncRes.ok) {
            log(`>> TELEMETRY SYNCED TO CONTROLLER WAND OLED [Scan #${scanId}] <<`, "ok");
          } else if (syncRes.status === 409) {
            const errJson = await syncRes.json().catch(() => ({}));
            log(`[SYNC REJECTED] Camera rejected stale diagnosis for Scan #${scanId} (Active: ${errJson.active_scan || 'Newer'})`, "warn");
          } else {
            log(`[SYNC FAILED] Camera returned HTTP ${syncRes.status}`, "warn");
          }
        } catch (syncErr) {
          log(`[SYNC ERROR] Could not reach camera bridge: ${syncErr.message}`, "warn");
        }

      } catch (err) {
        log(`Inference exception on Scan #${scanId}: ${err.message || 'Timeout'}`, "err");
      }
    }

    // GENUINE NEURAL INFERENCE (ZERO MATH.RANDOM, STRICT UNCERTAINTY GATING)
    async function runEdgeInference(img) {
      const cvs = document.getElementById("offscreenCanvas");
      const ctx = cvs.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, 128, 128);

      const frame = ctx.getImageData(0, 0, 128, 128);
      const data = frame.data;
      let foliarCount = 0;
      let necroticCount = 0;
      let chloroticCount = 0;
      const total = 128 * 128;

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i], g = data[i+1], b = data[i+2];
        // Green chlorophyll foliar tissue
        if (g > r * 0.95 && g > b * 1.05) {
          foliarCount++;
        }
        // Lesions / necrotic tissue
        else if (r > 60 && g > 50 && b < 80) {
          foliarCount++;
          necroticCount++;
        }
        // Yellow chlorosis
        else if (r > 130 && g > 120 && b < 90) {
          chloroticCount++;
        }
      }

      const foliarRatio = foliarCount / total;

      // 1. Peripheral dark void check: Reject unshielded night flash / off-center leaf
      let darkCount = 0;
      for (let i = 0; i < total; i++) {
        const r = data[i * 4];
        const g = data[i * 4 + 1];
        const b = data[i * 4 + 2];
        if (r < 35 && g < 35 && b < 35) darkCount++;
      }
      if (darkCount / total > 0.45) {
        return {
          crop: "Uncertain",
          disease: "Framing / Void Detected",
          pathogen: `Excessive peripheral dark void (${((darkCount/total)*100).toFixed(1)}%). Leaf must be centered in optical shroud.`,
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Center camera wand shroud directly over leaf surface.",
          chemical: "Ensure optical shroud blocks peripheral night darkness.",
          entropy: "0.00"
        };
      }

      // Plausibility check: Reject lens cap, blank white surface, non-leaf background
      if (foliarRatio < 0.12) {
        return {
          crop: "Invalid",
          disease: "No Leaf Detected",
          pathogen: "Insufficient foliar tissue in frame",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Aim camera wand directly at target leaf surface.",
          chemical: "Maintain 8-15cm focal distance in daylight.",
          entropy: "0.00"
        };
      }

      let probs = [];

      // 2. TFLite Model Execution (Zero Fake Fallbacks)
      if (modelReady && tfliteModel && typeof tf !== 'undefined') {
        let tfImg = null;
        let inputTensor = null;
        let output = null;
        try {
          tfImg = tf.browser.fromPixels(cvs);
          // MobileNetV3 model architecture already contains internal mobilenet_v3.preprocess_input layer
          // Input contract: [1, 128, 128, 3] float32 in range [0.0, 255.0]
          inputTensor = tfImg.toFloat().expandDims(0);
          output = tfliteModel.predict(inputTensor);
          // Output layer is already Softmax activation from training — no double softmax
          probs = Array.from(output.dataSync());
        } finally {
          if (tfImg) tfImg.dispose();
          if (inputTensor) inputTensor.dispose();
          if (output) output.dispose();
        }
      } else {
        // TFLite model is not loaded — strictly refuse to produce fake heuristic diagnosis
        return {
          crop: "System Notice",
          disease: "AI Engine Unavailable",
          pathogen: "MobileNetV3 TFLite model is not ready in browser",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Ensure phone is connected to wand Wi-Fi and model is loaded.",
          chemical: "Consult local Krishi Vigyan Kendra (KVK) agronomist.",
          entropy: "0.00"
        };
      }

      // 3. Shannon Entropy Calculation: H = -sum(p * ln(p))
      let entropy = 0.0;
      for (const p of probs) {
        if (p > 1e-6) entropy -= p * Math.log(p);
      }

      // 4. Argmax
      let maxIdx = 0;
      let maxProb = probs[0];
      for (let i = 1; i < probs.length; i++) {
        if (probs[i] > maxProb) {
          maxProb = probs[i];
          maxIdx = i;
        }
      }
      const confPercent = (maxProb * 100).toFixed(1);

      // Decision margin calculation (top1 - top2)
      const sortedProbs = probs.slice().sort((a, b) => b - a);
      const margin = sortedProbs[0] - (sortedProbs.length > 1 ? sortedProbs[1] : 0.0);

      // 5. Scientific Uncertainty Gating: Rejection of ambiguous samples and OOD species
      if (maxProb < 0.50 || entropy > 1.45 || margin < 0.12) {
        return {
          crop: "Uncertain",
          disease: "Low Confidence / Ambiguous",
          pathogen: "Ambiguous foliar pattern or non-target species",
          confidence: confPercent,
          status: "UNCERTAIN",
          organic: "Hold wand steady at 10cm distance from leaf.",
          chemical: "Ensure uniform solar illumination without shadow.",
          entropy: entropy.toFixed(2)
        };
      }

      const match = KB_CLASSES[maxIdx];
      let chemRec = match.chemical;
      // Microclimate-to-Diagnosis Cross-Gating
      if (match.disease.includes("Late Blight") && currentTelemetry && currentTelemetry.humidity > 0 && currentTelemetry.humidity < 85.0) {
        chemRec = `WITHHELD: Low RH (${Math.round(currentTelemetry.humidity)}%). Spores dormant under dry canopy (requires RH >= 85%). Suppressing fungicide; inspect for abiotic chlorosis.`;
      }
      return {
        crop: match.crop,
        disease: match.disease,
        pathogen: match.pathogen,
        confidence: confPercent,
        status: match.status,
        organic: match.organic,
        chemical: chemRec,
        entropy: entropy.toFixed(2)
      };
    }

    function updateMetricsAndUI(diag, latency, scanId) {
      totalScansProcessed++;
      document.getElementById("valScanCount").innerText = totalScansProcessed;
      document.getElementById("valLatency").innerText = `${latency} ms`;
      document.getElementById("scanTimestamp").innerHTML = `SCAN #${scanId} &bull; ${new Date().toLocaleTimeString()}`;

      document.getElementById("diagPrimary").innerText = `${diag.crop}: ${diag.disease}`;
      document.getElementById("diagPathogen").innerText = `Pathogen: ${diag.pathogen}`;
      
      const confEl = document.getElementById("diagConfidence");
      confEl.innerText = `Confidence: ${diag.confidence}% | Entropy: ${diag.entropy} | Status: ${diag.status}`;
      if (diag.status === "INFECTED") {
        confEl.style.color = "var(--accent-red)";
      } else if (diag.status === "WARNING") {
        confEl.style.color = "var(--accent-amber)";
      } else if (diag.status === "UNCERTAIN") {
        confEl.style.color = "var(--accent-cyan)";
      } else {
        confEl.style.color = "var(--accent-green)";
      }

      document.getElementById("rxBio").innerText = diag.organic;
      document.getElementById("rxChem").innerText = `Chemical: ${diag.chemical}`;
    }

    async function simulateFieldScan() {
      const demoScanId = (lastProcessedScanId || 0) + 1;
      lastProcessedScanId = demoScanId;
      log(`[DEMO] Triggering test scan #${demoScanId} on sample leaf...`, "ai");
      await testRealLeaf('/sample_leaves/late_blight_512.jpg', 'Field Demo Sample: Late Blight');
    }

    async function testRealLeaf(url, labelName) {
      const demoScanId = (lastProcessedScanId || 0) + 1;
      lastProcessedScanId = demoScanId;
      log(`[EXHIBITION] Loading real leaf image: ${labelName}...`, "ai");

      try {
        const img = new Image();
        img.crossOrigin = "anonymous";
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = (e) => reject(new Error("Could not load " + url));
          img.src = `${url}?t=${Date.now()}`;
        });

        const leafImg = document.getElementById("leafImg");
        const placeholder = document.getElementById("thumbPlaceholder");
        leafImg.src = img.src;
        leafImg.style.display = "block";
        placeholder.style.display = "none";

        const t0 = performance.now();
        const diag = await runEdgeInference(img);
        const latency = Math.round(performance.now() - t0);

        updateMetricsAndUI(diag, latency, demoScanId);
        playAudioChime();
        log(`[NEURAL VERIFIED] ${diag.crop}: ${diag.disease} (${diag.confidence}%, H=${diag.entropy}) in ${latency}ms`, "ok");
        return diag;
      } catch (err) {
        log(`Could not load sample image from ${url}: ${err.message}`, "err");
        return null;
      }
    }

    function handleLeafUpload(event) {
      const file = event.target.files[0];
      if (!file) return;

      const demoScanId = (lastProcessedScanId || 0) + 1;
      lastProcessedScanId = demoScanId;
      log(`[CUSTOM PHOTO] Loading: ${file.name} (${Math.round(file.size/1024)} KB)...`, "ai");

      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const img = new Image();
          img.onload = async () => {
            const leafImg = document.getElementById("leafImg");
            const placeholder = document.getElementById("thumbPlaceholder");
            leafImg.src = img.src;
            leafImg.style.display = "block";
            placeholder.style.display = "none";

            const t0 = performance.now();
            const diag = await runEdgeInference(img);
            const latency = Math.round(performance.now() - t0);

            updateMetricsAndUI(diag, latency, demoScanId);
            playAudioChime();
            log(`[CUSTOM DIAGNOSIS] ${diag.crop}: ${diag.disease} (${diag.confidence}%, H=${diag.entropy}) in ${latency}ms`, "ok");
          };
          img.onerror = () => {
            log(`Failed to decode uploaded image: ${file.name}`, "err");
          };
          img.src = e.target.result;
        } catch (err) {
          log(`Error processing uploaded photo: ${err.message}`, "err");
        }
      };
      reader.onerror = () => {
        log(`Failed to read file from disk: ${file.name}`, "err");
      };
      reader.readAsDataURL(file);
    }

    function playAudioChime() {
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
        osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.12); // A5
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.18);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.2);
      } catch (e) {}
    }

    // Auto-initialize TFLite on page load
    if (document.readyState === 'loading') {
      window.addEventListener("DOMContentLoaded", () => initTFLite(0));
    } else {
      initTFLite(0);
    }
    window.addEventListener("load", () => {
      if (!modelReady && typeof tflite !== 'undefined') initTFLite(0);
    });
  </script>
</body>
</html>
)rawliteral";

// --------------------------------------------------
// EMBEDDED LEAF PHOTO GALLERY & VIEWFINDER (SERVED AT /gallery)
// --------------------------------------------------
const char GALLERY_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KRISHI-DRISHTI | Leaf Photo Gallery</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0a0e17; color: #f1f5f9; padding: 14px; min-height: 100vh; }
    .header { text-align: center; padding: 14px 0 10px; border-bottom: 1px solid #1e293b; margin-bottom: 14px; }
    .title { font-size: 20px; font-weight: 800; color: #10b981; letter-spacing: 1px; }
    .subtitle { font-size: 11px; color: #94a3b8; margin-top: 3px; }
    .nav-bar { display: flex; gap: 8px; margin-bottom: 14px; }
    .nav-btn { flex: 1; padding: 10px; border-radius: 8px; font-size: 12px; font-weight: 700; text-align: center; text-decoration: none; border: 1px solid #1e293b; color: #f1f5f9; background: #131c2e; }
    .nav-btn-active { background: rgba(16,185,129,0.2); border-color: #10b981; color: #34d399; }
    .stats-bar { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
    .stat-box { background: #131c2e; border: 1px solid #1e293b; border-radius: 8px; padding: 8px; text-align: center; }
    .stat-val { font-size: 14px; font-weight: 800; color: #fff; }
    .stat-lbl { font-size: 9px; color: #64748b; text-transform: uppercase; margin-top: 2px; }
    .actions { display: flex; gap: 8px; margin-bottom: 14px; }
    .btn { padding: 12px; border-radius: 8px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; text-align: center; flex: 1; }
    .btn-capture { background: #10b981; color: #042f1a; }
    .btn-viewfinder { background: #0284c7; color: #fff; }
    .vf-box { display: none; margin-bottom: 14px; border-radius: 10px; overflow: hidden; border: 1px solid #1e293b; background: #000; text-align: center; }
    .vf-box img { width: 100%; height: auto; display: block; }
    .gallery-list { display: flex; flex-direction: column; gap: 8px; }
    .card { background: #131c2e; border: 1px solid #1e293b; border-radius: 8px; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; }
    .card-name { font-size: 13px; font-weight: 700; color: #f1f5f9; }
    .card-sub { font-size: 10px; color: #64748b; margin-top: 2px; }
    .card-actions { display: flex; gap: 6px; }
    .btn-sm { padding: 5px 8px; border-radius: 5px; font-size: 11px; font-weight: 600; text-decoration: none; border: none; cursor: pointer; }
    .btn-view { background: #0284c7; color: #fff; }
    .btn-dl { background: #10b981; color: #042f1a; }
    .btn-del { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">KRISHI-DRISHTI</div>
    <div class="subtitle">MicroSD High-Resolution Leaf Gallery</div>
  </div>

  <div class="nav-bar">
    <a href="/" class="nav-btn">🧠 AI Server Daemon</a>
    <a href="/gallery" class="nav-btn nav-btn-active">📷 Stored Scans</a>
  </div>

  <div class="stats-bar">
    <div class="stat-box"><div class="stat-val" id="scansCount">-</div><div class="stat-lbl">Photos</div></div>
    <div class="stat-box"><div class="stat-val">UXGA</div><div class="stat-lbl">1600x1200</div></div>
    <div class="stat-box"><div class="stat-val" style="color:#10b981;">1-BIT SD</div><div class="stat-lbl">DMA Safe</div></div>
  </div>

  <div class="actions">
    <button class="btn btn-capture" onclick="manualCapture()">📸 SNAP LEAF</button>
    <button class="btn btn-viewfinder" id="btnVf" onclick="toggleViewfinder()">📹 LIVE VIEWFINDER</button>
  </div>

  <div class="vf-box" id="vfBox">
    <img id="vfImg" src="" alt="Live Viewfinder Stream">
    <div style="padding: 6px; font-size: 10px; color: #94a3b8;">Center leaf inside camera field of view</div>
  </div>

  <div class="gallery-list" id="galleryList">
    <div style="text-align:center; padding: 20px; color: #64748b; font-size: 12px;">Loading scans from MicroSD...</div>
  </div>

  <script>
    let vfActive = false;
    let vfTimer = null;

    async function loadScans() {
      try {
        const res = await fetch('/api/scans?t=' + Date.now());
        const data = await res.json();
        document.getElementById('scansCount').innerText = data.scans ? data.scans.length : 0;
        const list = document.getElementById('galleryList');
        if (!data.scans || data.scans.length === 0) {
          list.innerHTML = '<div style="text-align:center; padding: 20px; color: #64748b; font-size: 12px;">No leaf scans stored on MicroSD card yet.</div>';
          return;
        }
        let html = '';
        data.scans.forEach(s => {
          html += `<div class="card">
            <div>
              <div class="card-name">Scan #${s.id}</div>
              <div class="card-sub">${s.file}</div>
            </div>
            <div class="card-actions">
              <a href="/image?id=${s.id}" target="_blank" class="btn-sm btn-view">View</a>
              <a href="/image?id=${s.id}&download=1" class="btn-sm btn-dl">Save</a>
              <button onclick="deleteScan(${s.id})" class="btn-sm btn-del">X</button>
            </div>
          </div>`;
        });
        list.innerHTML = html;
      } catch (e) {
        document.getElementById('galleryList').innerHTML = '<div style="text-align:center; color:#f87171; font-size:12px;">Error contacting camera SD card.</div>';
      }
    }

    async function manualCapture() {
      const btn = document.querySelector('.btn-capture');
      btn.innerText = '📸 FLASHING & CAPTURING...';
      btn.disabled = true;
      try {
        const res = await fetch('/api/capture');
        const data = await res.json();
        alert('Scan #' + data.scan_id + ' captured and saved to SD card!');
        loadScans();
      } catch (e) {
        alert('Capture failed: ' + e.message);
      }
      btn.innerText = '📸 SNAP LEAF';
      btn.disabled = false;
    }

    async function deleteScan(id) {
      if (!confirm('Delete Scan #' + id + '?')) return;
      await fetch('/api/delete?id=' + id);
      loadScans();
    }

    function toggleViewfinder() {
      vfActive = !vfActive;
      const box = document.getElementById('vfBox');
      const btn = document.getElementById('btnVf');
      if (vfActive) {
        box.style.display = 'block';
        btn.innerText = '⏹ STOP VIEWFINDER';
        runVf();
      } else {
        box.style.display = 'none';
        btn.innerText = '📹 LIVE VIEWFINDER';
        clearTimeout(vfTimer);
      }
    }

    function runVf() {
      if (!vfActive) return;
      const img = document.getElementById('vfImg');
      img.src = '/api/preview?t=' + Date.now();
      vfTimer = setTimeout(runVf, 400);
    }

    loadScans();
  </script>
</body>
</html>)rawliteral";

// --------------------------------------------------
// SCAN NUMBER RECOVERY ON BOOT
// --------------------------------------------------
void findNextScanNumber() {
  scanCounter = 0;
  if (!sdReady) return;

  while (scanCounter < 999999) {
    uint32_t nextId = scanCounter + 1;
    char filename[32];
    snprintf(filename, sizeof(filename), "/scan_%06lu.jpg", (unsigned long)nextId);
    if (!SD_MMC.exists(filename)) break;
    scanCounter = nextId;
  }
  Serial.printf("[SD] Recovered next scan ID: %lu\n", (unsigned long)(scanCounter + 1));
}

// --------------------------------------------------
// CAMERA DRIVER INITIALISATION (OV5640 / OV2640 DUAL)
// --------------------------------------------------
bool initialiseCamera() {
  Serial.println("[CAM] Initialising image sensor...");
  psramAvailable = psramFound();
  Serial.printf("[CAM] PSRAM available: %s\n", psramAvailable ? "YES" : "NO");

  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_UXGA;  // 1600 x 1200
  config.jpeg_quality = 10;
  config.fb_count     = 1;
  config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location  = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAM ERROR] esp_camera_init failed: 0x%x\n", err);
    return false;
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s != nullptr) {
    if (s->id.PID == 0x5640) sensorModel = "OV5640 (5MP)";
    else if (s->id.PID == 0x2640) sensorModel = "OV2640 (2MP)";
    else sensorModel = "OmniVision 0x" + String(s->id.PID, HEX);

    Serial.printf("[CAM] Sensor Identified: %s (PID: 0x%04X)\n", sensorModel.c_str(), s->id.PID);
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
  }

  // Warmup test frame
  camera_fb_t* fb = esp_camera_fb_get();
  if (fb) {
    Serial.printf("[CAM] Test frame OK: %u x %u (%u bytes)\n", fb->width, fb->height, fb->len);
    esp_camera_fb_return(fb);
    return true;
  }
  return false;
}

// --------------------------------------------------
// MICROSD IN 1-BIT MODE (DMA-PROTECTED)
// --------------------------------------------------
bool initialiseSD() {
  Serial.println("[SD] Mounting MicroSD in 1-bit mode (20MHz)...");
  if (!SD_MMC.begin("/sdcard", true, false, 20000, 5)) {
    Serial.println("[SD] 20MHz mount failed, retrying at 10MHz...");
    if (!SD_MMC.begin("/sdcard", true, false, 10000, 5)) {
      Serial.println("[SD WARN] MicroSD card not mounted (insert Class 10 card)");
      return false;
    }
  }
  uint8_t cardType = SD_MMC.cardType();
  if (cardType == CARD_NONE) {
    Serial.println("[SD] No card in slot");
    SD_MMC.end();
    return false;
  }
  uint64_t sizeMB = SD_MMC.cardSize() / (1024ULL * 1024ULL);
  Serial.printf("[SD] MicroSD Mounted Successfully! Capacity: %llu MB\n", sizeMB);
  return true;
}

// --------------------------------------------------
// HTTP HANDLERS
// --------------------------------------------------
void handleRoot() {
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  if (sdReady && SD_MMC.exists("/index.html")) {
    File f = SD_MMC.open("/index.html", FILE_READ);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.streamFile(f, "text/html");
    f.close();
    return;
  }
  if (sdReady && SD_MMC.exists("/krishi_ai_server.html")) {
    File f = SD_MMC.open("/krishi_ai_server.html", FILE_READ);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.streamFile(f, "text/html");
    f.close();
    return;
  }
  server.send_P(200, "text/html", AI_SERVER_HTML);
}

void handleGallery() {
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.send_P(200, "text/html", GALLERY_HTML);
}

void handleStatus() {
  if (!sdReady) {
    sdReady = initialiseSD();
    if (sdReady) findNextScanNumber();
  }
  uint64_t sizeMB = 0;
  if (sdReady) {
    sizeMB = SD_MMC.cardSize() / (1024ULL * 1024ULL);
  }
  int clientCount = WiFi.softAPgetStationNum();
  bool wandConnected = (clientCount >= 2) || (lastWandActivityMs > 0 && (millis() - lastWandActivityMs < 30000));

  String json = "{";
  json += "\"device\":\"KRISHI-DRISHTI-CAM\",";
  json += "\"camera_ready\":" + String(cameraReady ? "true" : "false") + ",";
  json += "\"sd_ready\":" + String(sdReady ? "true" : "false") + ",";
  json += "\"sd_capacity_mb\":" + String((unsigned long)sizeMB) + ",";
  json += "\"wand_connected\":" + String(wandConnected ? "true" : "false") + ",";
  json += "\"psram_available\":" + String(psramAvailable ? "true" : "false") + ",";
  json += "\"sensor\":\"" + sensorModel + "\",";
  json += "\"scan_count\":" + String(scanCounter) + ",";
  json += "\"clients\":" + String(clientCount) + ",";
  json += "\"diagnosis_ready\":" + String(diagnosisReady ? "true" : "false") + ",";
  json += "\"telemetry_available\":" + String(canopyTelemetryPresent ? "true" : "false") + ",";
  json += "\"humidity\":" + String(lastCanopyHum, 1) + ",";
  json += "\"temperature\":" + String(lastCanopyTemp, 1);
  json += "}";
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleCapture() {
  lastWandActivityMs = millis();
  // Reset telemetry availability for each new scan to prevent stale readings
  canopyTelemetryPresent = false;
  lastCanopyHum = 0.0f;
  lastCanopyTemp = 0.0f;

  if (server.hasArg("hum") && server.hasArg("temp")) {
    float h = server.arg("hum").toFloat();
    float t = server.arg("temp").toFloat();
    if (h > 0.0f && h <= 100.0f && t >= -10.0f && t <= 65.0f) {
      lastCanopyHum = h;
      lastCanopyTemp = t;
      canopyTelemetryPresent = true;
    }
  }
  if (!cameraReady) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(503, "application/json", "{\"status\":\"error\",\"message\":\"camera_offline\"}");
    return;
  }

  if (!sdReady) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(503, "application/json", "{\"status\":\"error\",\"message\":\"sd_storage_offline\"}");
    return;
  }

  diagnosisReady = false; // Reset diagnosis flag for newly captured leaf

  // Pulse Flash LED for 120ms to allow AEC/AGC to adapt
  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(120);
  camera_fb_t* fb = esp_camera_fb_get();
  digitalWrite(FLASH_LED_PIN, LOW); // Shut off LED immediately

  if (!fb) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(500, "application/json", "{\"status\":\"error\",\"message\":\"capture_failed\"}");
    return;
  }

  uint32_t nextId = scanCounter + 1;
  char filename[32];
  snprintf(filename, sizeof(filename), "/scan_%06lu.jpg", (unsigned long)nextId);

  size_t written = 0;
  File file = SD_MMC.open(filename, FILE_WRITE);
  if (file) {
    written = file.write(fb->buf, fb->len);
    file.close();
  } else {
    Serial.printf("[SD ERROR] Failed to open %s for write!\n", filename);
    esp_camera_fb_return(fb);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(500, "application/json", "{\"status\":\"error\",\"message\":\"sd_open_failed\"}");
    return;
  }

  // Write verification: reject empty or truncated files
  if (written < 512 || written != fb->len) {
    Serial.printf("[SD ERROR] Frame write incomplete! Expected %u bytes, wrote %u bytes\n", 
                  (unsigned int)fb->len, (unsigned int)written);
    esp_camera_fb_return(fb);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(500, "application/json", "{\"status\":\"error\",\"message\":\"sd_write_truncated\"}");
    return;
  }

  scanCounter = nextId;
  esp_camera_fb_return(fb);

  String body = "{\"status\":\"success\",\"scan_id\":" + String(scanCounter);
  body += ",\"filename\":\"" + String(filename) + "\",\"bytes\":" + String(written) + "}";

  Serial.printf("[CAPTURE] Scan #%lu saved (%u bytes)\n", (unsigned long)scanCounter, (unsigned int)written);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", body);
}

void handleGetImage() {
  if (!sdReady) {
    server.send(503, "text/plain", "SD offline");
    return;
  }
  if (isStreaming) {
    server.send(429, "text/plain", "Bus busy");
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
    if (!filename.startsWith("/")) filename = "/" + filename;
  } else {
    isStreaming = false;
    server.send(400, "text/plain", "Missing id");
    return;
  }

  if (!SD_MMC.exists(filename.c_str())) {
    isStreaming = false;
    server.send(404, "text/plain", "Not found");
    return;
  }

  File f = SD_MMC.open(filename.c_str(), FILE_READ);
  if (server.hasArg("download")) {
    server.sendHeader("Content-Disposition", "attachment; filename=\"" + filename.substring(1) + "\"");
  }
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.streamFile(f, "image/jpeg");
  f.close();
  isStreaming = false;
}

void handleListScans() {
  if (!sdReady) {
    server.send(503, "application/json", "{\"status\":\"error\",\"message\":\"sd_offline\"}");
    return;
  }
  String json = "{\"total\":" + String(scanCounter) + ",\"scans\":[";
  bool first = true;
  for (int32_t i = scanCounter; i >= 1; i--) {
    char buf[32];
    snprintf(buf, sizeof(buf), "/scan_%06lu.jpg", (unsigned long)i);
    if (SD_MMC.exists(buf)) {
      if (!first) json += ",";
      json += "{\"id\":" + String(i) + ",\"file\":\"" + String(buf) + "\"}";
      first = false;
    }
  }
  json += "]}";
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleDelete() {
  if (!sdReady) {
    server.send(503, "application/json", "{\"status\":\"error\"}");
    return;
  }
  if (server.hasArg("id")) {
    uint32_t id = server.arg("id").toInt();
    char buf[32];
    snprintf(buf, sizeof(buf), "/scan_%06lu.jpg", (unsigned long)id);
    if (SD_MMC.exists(buf)) SD_MMC.remove(buf);
    server.send(200, "application/json", "{\"status\":\"deleted\"}");
  } else {
    server.send(400, "application/json", "{\"status\":\"bad_request\"}");
  }
}

void handleGetDiagnosis() {
  String json = "{";
  json += "\"ready\":" + String(diagnosisReady ? "true" : "false") + ",";
  json += "\"scan_id\":" + String(diagScanId) + ",";
  json += "\"crop\":\"" + diagCrop + "\",";
  json += "\"disease\":\"" + diagDisease + "\",";
  json += "\"confidence\":" + String(diagConfidence, 1) + ",";
  json += "\"status\":\"" + diagStatus + "\",";
  json += "\"organic\":\"" + diagOrganic + "\",";
  json += "\"chemical\":\"" + diagChemical + "\"";
  json += "}";
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleSetDiagnosis() {
  uint32_t incomingScanId = 0;
  if (server.hasArg("scan_id")) {
    incomingScanId = server.arg("scan_id").toInt();
  }

  // Reject stale diagnosis payloads to guarantee diagnosis matches active scan
  if (incomingScanId != scanCounter) {
    Serial.printf("[AI WARNING] Rejected stale diagnosis for Scan #%lu (Active scan is #%lu)\n",
                  (unsigned long)incomingScanId, (unsigned long)scanCounter);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(409, "application/json", "{\"status\":\"error\",\"message\":\"stale_scan_id\",\"active_scan\":" + String(scanCounter) + "}");
    return;
  }

  diagScanId = incomingScanId;
  if (server.hasArg("crop")) diagCrop = server.arg("crop");
  if (server.hasArg("disease")) diagDisease = server.arg("disease");
  if (server.hasArg("confidence")) diagConfidence = server.arg("confidence").toFloat();
  if (server.hasArg("status")) diagStatus = server.arg("status");
  if (server.hasArg("organic")) diagOrganic = server.arg("organic");
  if (server.hasArg("chemical")) diagChemical = server.arg("chemical");

  diagnosisReady = true;

  Serial.println("\n[AI DIAGNOSIS SYNCED FROM POCKET]");
  Serial.printf(" - Scan #%lu | Crop: %s | Condition: %s (%.1f%%)\n", 
                (unsigned long)diagScanId, diagCrop.c_str(), diagDisease.c_str(), diagConfidence);
  Serial.printf(" - Organic Remedy: %s\n", diagOrganic.c_str());
  Serial.printf(" - Chemical Cure: %s\n", diagChemical.c_str());

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", "{\"status\":\"success\"}");
}

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
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void handleFlashToggle() {
  if (server.hasArg("state")) {
    int s = server.arg("state").toInt();
    digitalWrite(FLASH_LED_PIN, s ? HIGH : LOW);
    server.send(200, "text/plain", s ? "FLASH_ON" : "FLASH_OFF");
  } else {
    server.send(400, "text/plain", "Missing state");
  }
}

// --------------------------------------------------
// SETUP
// --------------------------------------------------
// --------------------------------------------------
// STATIC FILE STREAMER (SERVES OFFLINE TFLITE & ASSETS FROM SDMMC)
// --------------------------------------------------
void handleStaticFile() {
  if (!sdReady) {
    sdReady = initialiseSD();
    if (sdReady) findNextScanNumber();
  }
  if (!sdReady) {
    server.send(503, "text/plain", "SD offline - Insert MicroSD card in ESP32-CAM slot");
    return;
  }
  String path = server.uri();
  if (path.endsWith("/")) path += "index.html";

  String contentType = "text/plain";
  if (path.endsWith(".html")) contentType = "text/html";
  else if (path.endsWith(".css")) contentType = "text/css";
  else if (path.endsWith(".js")) contentType = "application/javascript";
  else if (path.endsWith(".wasm")) contentType = "application/wasm";
  else if (path.endsWith(".tflite")) contentType = "application/octet-stream";
  else if (path.endsWith(".json")) contentType = "application/json";
  else if (path.endsWith(".png")) contentType = "image/png";
  else if (path.endsWith(".jpg") || path.endsWith(".jpeg")) contentType = "image/jpeg";
  else if (path.endsWith(".svg")) contentType = "image/svg+xml";

  if (SD_MMC.exists(path.c_str())) {
    File f = SD_MMC.open(path.c_str(), FILE_READ);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Cache-Control", "public, max-age=86400");
    server.streamFile(f, contentType);
    f.close();
    return;
  }
  server.send(404, "text/plain", "404 Not Found");
}

void setup() {
  Serial.begin(115200);
  setCpuFrequencyMhz(240); // 240MHz performance lock

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  Serial.println("\n========================================");
  Serial.println("  KRISHI-DRISHTI :: ESP32-CAM v2.2");
  Serial.println("  Offline-First Edge Agritech Platform");
  Serial.println("========================================");

  cameraReady = initialiseCamera();
  sdReady     = initialiseSD();

  if (sdReady) findNextScanNumber();

  Serial.println("\n[WIFI] Broadcasting SoftAP: KRISHI-DRISHTI...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);

  Serial.print("[WIFI] Gateway IP: ");
  Serial.println(WiFi.softAPIP());

  // Web routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/ai", HTTP_GET, handleRoot);
  server.on("/gallery", HTTP_GET, handleGallery);
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/capture", HTTP_GET, handleCapture);
  server.on("/image", HTTP_GET, handleGetImage);
  server.on("/api/scans", HTTP_GET, handleListScans);
  server.on("/api/delete", HTTP_GET, handleDelete);
  server.on("/api/diagnosis", HTTP_GET, handleGetDiagnosis);
  server.on("/api/diagnosis/latest", HTTP_GET, handleGetDiagnosis);
  server.on("/api/diagnosis/set", HTTP_GET, handleSetDiagnosis);
  server.on("/api/diagnosis/set", HTTP_POST, handleSetDiagnosis);
  server.on("/api/preview", HTTP_GET, handlePreview);
  server.on("/api/flash", HTTP_GET, handleFlashToggle);

    server.onNotFound(handleStaticFile);
  server.begin();
  Serial.println("[HTTP] Server listening on http://192.168.4.1/\n");
}

// --------------------------------------------------
// MAIN LOOP
// --------------------------------------------------
void loop() {
  server.handleClient();
  delay(2);
}
