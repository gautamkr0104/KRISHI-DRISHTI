/*
  ==============================================================================
  KRISHI-DRISHTI (कृषि-दृष्टि) - Official Camera Unit Firmware v2.5.1
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
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#0e1210">
  <title>KRISHI-DRISHTI</title>

  <!-- Early boot error logger -->
  <script>
    window._bootLogs = [];
    window._earlyLog = function(msg, kind = 'info') {
      if (typeof window.log === 'function') {
        window.log(msg, kind);
      } else {
        window._bootLogs.push({ msg, kind, time: new Date().toLocaleTimeString() });
      }
    };
    window.onerror = function(msg, src, lin, col, err) {
      const srcName = src ? src.split('/').pop() : 'inline';
      window._earlyLog(`Script error: ${msg} (${srcName}:${lin})`, 'err');
    };
  </script>

  <!-- Bundled offline TensorFlow.js and TFLite WASM runtimes with defer for clean streaming -->
  <script defer src="/vendor/tf.min.js" onerror="window._earlyLog('Failed to download /vendor/tf.min.js over Wi-Fi', 'err');"></script>
  <script defer src="/vendor/tf-tflite.min.js" onerror="window._earlyLog('Failed to download /vendor/tf-tflite.min.js over Wi-Fi', 'err');"></script>

  <style>
    :root {
      --bg: #0e1210;
      --surface: rgba(21, 26, 23, 0.55);
      --surface-2: rgba(30, 38, 34, 0.62);
      --inset: rgba(11, 15, 13, 0.88);
      --line: #262d29;
      --line-strong: #333c36;

      --ink: #e9e7e0;
      --muted: #a3a89f;
      --faint: #6e756d;

      --accent: #46a758;
      --accent-strong: #3e9450;
      --accent-soft: rgba(70, 167, 88, 0.14);

      --ok: #4cc38a;
      --bad: #e5484d;
      --warn: #f0a13e;
      --mid: #8d99a6;
      --bar: #3e9b52;

      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;

      --radius: 14px;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.02);
      --glass-blur: 18px;
      --glass-blur-soft: 12px;
      --glass-edge:
        inset 0 1px 0 rgba(220, 255, 235, 0.10),
        inset 0 0 0 1px rgba(126, 208, 154, 0.04),
        0 8px 32px rgba(0, 0, 0, 0.35);
      --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    /* glass fallback: engines without backdrop-filter get the original solid surfaces */
    @supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
      :root {
        --surface: #151a17;
        --surface-2: #1a201d;
        --inset: #0b0f0d;
      }
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    ::selection { background: rgba(70, 167, 88, 0.35); }

    body {
      background: var(--bg);
      color: var(--ink);
      font-family: var(--font-sans);
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      -webkit-text-size-adjust: 100%;
      overflow-x: hidden;
    }

    /* ambient backdrop: gives the glass panels something to blur (palette hues only) */
    body::before {
      content: "";
      position: fixed;
      inset: -12%;
      z-index: -1;
      pointer-events: none;
      background:
        radial-gradient(640px 440px at 12% -6%, rgba(70, 167, 88, 0.40), transparent 66%),
        radial-gradient(720px 480px at 92% 2%, rgba(76, 195, 138, 0.32), transparent 66%),
        radial-gradient(560px 420px at -4% 42%, rgba(43, 110, 60, 0.36), transparent 68%),
        radial-gradient(600px 460px at 104% 52%, rgba(58, 150, 74, 0.30), transparent 68%),
        radial-gradient(760px 520px at 24% 108%, rgba(39, 122, 60, 0.36), transparent 68%),
        radial-gradient(680px 500px at 78% 104%, rgba(24, 82, 44, 0.32), transparent 70%),
        radial-gradient(520px 360px at 50% 44%, rgba(52, 138, 66, 0.22), transparent 72%),
        radial-gradient(380px 260px at 66% 76%, rgba(76, 195, 138, 0.18), transparent 72%);
      animation: aurora 42s ease-in-out infinite alternate;
    }

    @keyframes aurora {
      from { transform: translate3d(-1.5%, -1%, 0) scale(1); }
      to   { transform: translate3d(1.5%, 1.5%, 0) scale(1.06); }
    }

    /* faint tech grid + vignette: the HUD layer */
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      z-index: -1;
      pointer-events: none;
      background:
        linear-gradient(rgba(126, 208, 154, 0.030) 1px, transparent 1px),
        linear-gradient(90deg, rgba(126, 208, 154, 0.030) 1px, transparent 1px);
      background-size: 44px 44px;
      -webkit-mask-image: radial-gradient(ellipse 90% 80% at 50% 30%, black 30%, transparent 78%);
      mask-image: radial-gradient(ellipse 90% 80% at 50% 30%, black 30%, transparent 78%);
    }

    @media (prefers-reduced-motion: reduce) {
      body::before { animation: none; }
    }

    .shell {
      max-width: 1080px;
      margin: 0 auto;
      padding: 14px 16px 18px;
    }

    /* ---------- header ---------- */
    .masthead {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px 16px;
      padding-bottom: 10px;
      animation: rise 560ms var(--spring) both;
    }

    .brand { display: flex; align-items: center; gap: 12px; }

    .brand-mark {
      width: 34px;
      height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #1d3a28, #16301f);
      border: 1px solid rgba(126, 208, 154, 0.35);
      box-shadow:
        0 0 0 1px rgba(70, 167, 88, 0.10),
        0 0 18px rgba(70, 167, 88, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.10);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #7ed09a;
      flex: none;
    }

    .brand h1 {
      font-size: 17px;
      font-weight: 800;
      letter-spacing: 0.04em;
      background: linear-gradient(100deg, #d9f2e0 0%, #7ed09a 45%, #46a758 90%);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
      color: #7ed09a;
      filter: drop-shadow(0 0 14px rgba(70, 167, 88, 0.35));
    }

    .brand .sub {
      font-size: 12px;
      color: var(--muted);
      margin-top: 1px;
    }

    .server-state {
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: var(--font-mono);
      font-size: 11.5px;
      letter-spacing: 0.05em;
      color: var(--faint);
      background: var(--surface);
      -webkit-backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      border: 1px solid rgba(255, 255, 255, 0.09);
      border-radius: 6px;
      padding: 6px 12px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.07);
    }

    .server-state .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--faint);
      flex: none;
    }

    .server-state.running { color: var(--ok); border-color: rgba(76, 195, 138, 0.45); box-shadow: 0 0 14px rgba(76, 195, 138, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.07); }
    .server-state.running .dot { background: var(--ok); box-shadow: 0 0 8px rgba(76, 195, 138, 0.8); animation: dotpulse 2s ease-in-out infinite; }

    @keyframes dotpulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.45; }
    }

    @media (prefers-reduced-motion: reduce) {
      .server-state.running .dot { animation: none; }
    }

    /* ---------- fact strip ---------- */
    .facts {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      background: var(--surface);
      -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(1.5);
      backdrop-filter: blur(var(--glass-blur)) saturate(1.5);
      border: 1px solid rgba(126, 208, 154, 0.10);
      border-radius: var(--radius);
      box-shadow: var(--glass-edge);
      overflow: hidden;
      animation: rise 560ms var(--spring) both;
      animation-delay: 70ms;
    }

    .fact {
      padding: 8px 12px 9px;
      border-left: 1px solid rgba(255, 255, 255, 0.07);
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
      transition: background-color 140ms ease;
    }

    .fact:first-child { border-left: none; }
    .fact:hover { background: rgba(255, 255, 255, 0.045); }

    .fact .k {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--faint);
    }

    .fact .k svg { color: var(--faint); flex: none; }

    .fact .v {
      font-family: var(--font-mono);
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .fact .v.good { color: var(--ok); }
    .fact .v.bad { color: var(--bad); }
    .fact .v.warn { color: var(--warn); }

    /* ---------- layout ---------- */
    .columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 10px;
      align-items: start;
    }

    @media (max-width: 880px) {
      .columns { grid-template-columns: 1fr; }
      .facts { grid-template-columns: repeat(3, 1fr); }
      .fact:nth-child(4) { border-left: none; }
      .fact:nth-child(n+4) { border-top: 1px solid var(--line); }
    }

    @media (max-width: 560px) {
      .facts { grid-template-columns: repeat(2, 1fr); }
      .fact:nth-child(odd) { border-left: none; }
      .fact:nth-child(n+3) { border-top: 1px solid var(--line); }
      .shell { padding: 10px 10px 16px; }
      .columns { gap: 10px; margin-top: 10px; }
      .panel-body { padding: 10px; }
      .image-ops { grid-template-columns: 1fr; }
      .frame { width: 100%; height: 210px; margin: 0 auto; }
      .btn { padding: 9px 14px; font-size: 13.5px; }
      .btn-small { padding: 7px 11px; font-size: 12px; }
      .diag-row { grid-template-columns: 96px 1fr; }
      .terminal { height: 110px; }
      .foot { font-size: 11px; }
    }

    .panel {
      background: var(--surface);
      -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(1.5);
      backdrop-filter: blur(var(--glass-blur)) saturate(1.5);
      border: 1px solid rgba(126, 208, 154, 0.10);
      border-radius: var(--radius);
      box-shadow: var(--glass-edge);
      min-width: 0;
      overflow: hidden;
      transition: transform 300ms var(--spring), border-color 300ms ease, box-shadow 300ms ease;
      animation: rise 560ms var(--spring) both;
      animation-delay: var(--rise-delay, 120ms);
    }

    .panel:hover {
      border-color: rgba(126, 208, 154, 0.30);
      box-shadow:
        inset 0 1px 0 rgba(220, 255, 235, 0.12),
        inset 0 0 0 1px rgba(126, 208, 154, 0.06),
        0 12px 44px rgba(0, 0, 0, 0.40),
        0 0 30px rgba(70, 167, 88, 0.14);
    }

    @keyframes rise {
      from { opacity: 0; transform: translateY(14px) scale(0.985); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    @media (prefers-reduced-motion: reduce) {
      .panel, .facts, .masthead { animation: none !important; }
    }

    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.07);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent);
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }

    .panel-head .right {
      font-size: 10.5px;
      font-weight: 400;
      letter-spacing: 0.02em;
      text-transform: none;
      color: var(--faint);
      font-family: var(--font-mono);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      min-width: 0;
    }

    .panel-body { padding: 12px; }

    /* ---------- image area ---------- */
    .frame {
      position: relative;
      border: 1px solid rgba(126, 208, 154, 0.22);
      border-radius: 10px;
      background:
        repeating-conic-gradient(#131715 0% 25%, #101412 0% 50%) 0 0 / 24px 24px;
      box-shadow:
        0 0 22px rgba(70, 167, 88, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.06);
      height: 200px;
      width: 267px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    .frame::after {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: 10px;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
      pointer-events: none;
    }

    /* scan sweep: a faint laser line rides the frame */
    .frame::before {
      content: "";
      position: absolute;
      left: 6px;
      right: 6px;
      height: 2px;
      top: 8%;
      border-radius: 2px;
      background: linear-gradient(90deg, transparent, rgba(126, 208, 154, 0.55), transparent);
      box-shadow: 0 0 14px rgba(70, 167, 88, 0.45);
      opacity: 0.55;
      animation: sweep 7s ease-in-out infinite;
      pointer-events: none;
      z-index: 1;
    }

    @keyframes sweep {
      0%, 62% { top: 8%; opacity: 0.55; }
      86%, 100% { top: 90%; opacity: 0; }
    }

    @media (prefers-reduced-motion: reduce) {
      .frame::before { animation: none; opacity: 0; }
    }

    .frame .placeholder {
      color: var(--faint);
      font-size: 12px;
      text-align: center;
      padding: 0 18px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }

    .frame .placeholder svg { color: #3a423c; }

    .frame img {
      display: none;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    /* ---------- buttons ---------- */
    .btn {
      appearance: none;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 6px 12px;
      font: 600 12.5px var(--font-sans);
      color: var(--ink);
      background: rgba(255, 255, 255, 0.07);
      -webkit-backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      border: 1px solid rgba(255, 255, 255, 0.16);
      border-radius: 7px;
      cursor: pointer;
      transition: background-color 120ms ease, border-color 200ms ease, transform 260ms var(--spring), box-shadow 260ms ease;
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.12),
        0 2px 8px rgba(0, 0, 0, 0.22);
    }

    .btn:hover { background: rgba(255, 255, 255, 0.12); border-color: rgba(126, 208, 154, 0.35); transform: translateY(-1px); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14), 0 3px 12px rgba(0, 0, 0, 0.28); }
    .btn:active { background: rgba(255, 255, 255, 0.05); transform: translateY(0); }

    .btn:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    .btn-primary {
      background: linear-gradient(160deg, rgba(70, 167, 88, 0.50), rgba(43, 110, 60, 0.55));
      border-color: rgba(126, 208, 154, 0.45);
      color: #f2fbf4;
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.18),
        0 3px 14px rgba(70, 167, 88, 0.30);
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
    }

    .btn-primary:hover {
      background: linear-gradient(160deg, rgba(70, 167, 88, 0.64), rgba(50, 125, 70, 0.62));
      border-color: rgba(126, 208, 154, 0.62);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.20),
        0 4px 20px rgba(70, 167, 88, 0.42);
      transform: translateY(-1px);
    }

    .btn-primary:active { background: linear-gradient(160deg, rgba(55, 132, 71, 0.60), rgba(39, 97, 54, 0.62)); transform: translateY(0); }

    .btn-paused {
      background: rgba(240, 161, 62, 0.30);
      border-color: rgba(240, 161, 62, 0.45);
      color: #fdf6e9;
    }

    .btn-paused:hover { background: rgba(240, 161, 62, 0.42); }
    .btn-paused:active { background: rgba(125, 84, 22, 0.55); }

    .btn-small {
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 500;
      border-radius: 5px;
    }

    .image-ops {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }

    .ops-col { min-width: 0; }

    .controls { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 2px; }

    .samples { margin-top: 10px; border-top: 1px solid var(--line); padding-top: 9px; }

    .samples .label {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--faint);
      margin-bottom: 5px;
    }

    .sample-row { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 6px; }

    /* ---------- diagnosis ---------- */
    .diag-rows {
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 6px;
      overflow: hidden;
      background: var(--inset);
      -webkit-backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }

    .diag-row {
      display: grid;
      grid-template-columns: 116px 1fr;
      border-top: 1px solid var(--line);
      font-size: 13.5px;
    }

    .diag-row:first-child { border-top: none; }

    .diag-row .k {
      padding: 5px 10px;
      background: rgba(17, 22, 19, 0.60);
      border-right: 1px solid rgba(255, 255, 255, 0.07);
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: var(--faint);
      display: flex;
      align-items: center;
    }

    .diag-row .v {
      padding: 5px 10px;
      min-width: 0;
      overflow-wrap: break-word;
      color: var(--ink);
      font-size: 12.5px;
    }

    .diag-row .v.dim { color: var(--muted); }
    .diag-row .v.mono { font-family: var(--font-mono); font-size: 12.5px; }

    .gate {
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding: 2px 8px;
      border-radius: 4px;
      border: 1px solid;
    }

    .gate-infected  { color: var(--bad);  background: rgba(229, 72, 77, 0.12);  border-color: rgba(229, 72, 77, 0.4);  box-shadow: 0 0 12px rgba(229, 72, 77, 0.15); }
    .gate-warning   { color: var(--warn); background: rgba(240, 161, 62, 0.12); border-color: rgba(240, 161, 62, 0.4); box-shadow: 0 0 12px rgba(240, 161, 62, 0.15); }
    .gate-healthy   { color: var(--ok);   background: rgba(76, 195, 138, 0.12); border-color: rgba(76, 195, 138, 0.4); box-shadow: 0 0 12px rgba(76, 195, 138, 0.15); }
    .gate-uncertain { color: var(--mid);  background: rgba(141, 153, 166, 0.12); border-color: rgba(141, 153, 166, 0.4); }

    /* ---------- advisory ---------- */
    .advisory {
      margin-top: 10px;
      border-top: 1px solid var(--line);
      padding-top: 9px;
    }

    .advisory h3 {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--faint);
      margin-bottom: 4px;
    }

    .advisory p {
      font-size: 12.5px;
      color: var(--ink);
      margin-bottom: 8px;
      padding-left: 10px;
      border-left: 2px solid var(--line-strong);
    }

    /* ---------- hardware ---------- */
    .hardware {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 6px;
      background: var(--inset);
      -webkit-backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      padding: 9px 12px;
      margin-top: 10px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }

    .hardware .hw-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
    }

    .hardware .hw-title .dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--faint); flex: none;
    }

    .hardware .hw-desc {
      font-size: 12.5px;
      color: var(--muted);
      margin-top: 4px;
      line-height: 1.5;
    }

    /* ---------- log ---------- */
    .terminal {
      height: 118px;
      overflow-y: auto;
      padding: 8px 12px;
      background: var(--inset);
      -webkit-backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      backdrop-filter: blur(var(--glass-blur-soft)) saturate(1.4);
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1.55;
    }

    .terminal::-webkit-scrollbar { width: 10px; }
    .terminal::-webkit-scrollbar-thumb { background: #2c332e; border-radius: 5px; border: 2px solid var(--inset); }

    .log-line { display: flex; gap: 8px; align-items: baseline; }

    .log-t { color: #525a53; flex: none; }

    .log-tag { flex: none; font-weight: 700; font-size: 10px; letter-spacing: 0.06em; }
    .log-tag-info { color: var(--muted); }
    .log-tag-ok   { color: var(--ok); }
    .log-tag-err  { color: var(--bad); }
    .log-tag-ai   { color: #5aa9e6; }
    .log-tag-warn { color: var(--warn); }

    .log-line > span:last-child { color: #c9cdd2; }

    /* ---------- footer removed ---------- */
  </style>
</head>
<body>

  <div class="shell">

    <!-- Header -->
    <header class="masthead">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
            <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
          </svg>
        </div>
        <div>
          <h1>KRISHI-DRISHTI</h1>
          <div class="sub">Leaf disease scanner for tomato and potato. Runs offline in this browser.</div>
        </div>
      </div>
      <div class="server-state stopped" id="statusPill">
        <span class="dot"></span>
        <span id="statusText">STANDBY</span>
      </div>
    </header>

    <!-- Live facts -->
    <section class="facts" aria-label="Status">
      <div class="fact">
        <span class="k"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>Camera link</span>
        <span class="v" id="valCameraLink">Not connected</span>
      </div>
      <div class="fact">
        <span class="k"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="14" rx="2"/><path d="M6 2h12v4H6z"/></svg>SD card</span>
        <span class="v" id="valSdStatus">Checking</span>
      </div>
      <div class="fact">
        <span class="k"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a3 3 0 1 0-6 0v8a3 3 0 1 0 6 0V8Z"/><path d="M12 8a3 3 0 1 0-6 0v8a3 3 0 1 0 6 0V8Z"/></svg>Wand</span>
        <span class="v" id="valWandLink">Off</span>
      </div>
      <div class="fact">
        <span class="k"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/></svg>Engine</span>
        <span class="v" id="valEngine">Loading model</span>
      </div>
      <div class="fact">
        <span class="k"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>Last latency</span>
        <span class="v" id="valLatency">No scan yet</span>
      </div>
      <div class="fact">
        <span class="k"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></svg>Scans processed</span>
        <span class="v" id="valScanCount">0</span>
      </div>
    </section>

    <div class="columns">

      <!-- Left: image and controls -->
      <section class="panel">
        <div class="panel-head">
          <span>Leaf image</span>
          <span class="right" id="scanTimestamp">No scan</span>
        </div>
        <div class="panel-body">
          <div class="image-ops">
            <div class="frame" id="leafThumbWrap">
              <div class="placeholder" id="thumbPlaceholder">
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
                  <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                </svg>
                <span>No scan yet. Connect to the wand Wi-Fi (KRISHI-DRISHTI), or load a sample or upload a photo.</span>
              </div>
              <img id="leafImg" alt="Captured leaf image" />
            </div>

            <div class="ops-col">
              <div class="controls">
                <button class="btn btn-primary" id="btnToggle" onclick="toggleServer()">Start scanning</button>
                <button class="btn" onclick="pollMeshNow()">Check hardware</button>
              </div>

              <div class="samples">
                <div class="label">Samples</div>
                <div class="sample-row">
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/tomato_late_blight.jpg', 'Tomato late blight')">Tomato late blight</button>
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/tomato_early_blight.jpg', 'Tomato early blight')">Tomato early blight</button>
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/tomato_healthy.jpg', 'Tomato healthy')">Tomato healthy</button>
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/potato_late_blight.jpg', 'Potato late blight')">Potato late blight</button>
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/potato_early_blight.jpg', 'Potato early blight')">Potato early blight</button>
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/potato_healthy.jpg', 'Potato healthy')">Potato healthy</button>
                </div>
                <div class="label">Rejection cases</div>
                <div class="sample-row">
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/test_edge_lens_cap.jpg', 'Lens cap')">Lens cap</button>
                  <button class="btn btn-small" onclick="testRealLeaf('/sample_leaves/test_edge_ambient_surface.jpg', 'Ambient surface')">Ambient surface</button>
                </div>
                <div class="label">Own photo</div>
                <div class="sample-row">
                  <label class="btn btn-small">Upload photo
                    <input type="file" id="leafFileInput" accept="image/*" style="display: none;" onchange="handleLeafUpload(event)">
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Right: diagnosis -->
      <section class="panel" style="--rise-delay: 190ms">
        <div class="panel-head">
          <span>Diagnosis</span>
          <span class="right">krishi_drishti_model.tflite</span>
        </div>
        <div class="panel-body">

          <div class="diag-rows">
            <div class="diag-row"><span class="k">Result</span><span class="v" id="diagPrimary">No scan yet</span></div>
            <div class="diag-row"><span class="k">Detail</span><span class="v dim" id="diagPathogen">Run a scan to see the diagnosis.</span></div>
            <div class="diag-row"><span class="k">Verdict</span><span class="v" id="diagGate">None</span></div>
            <div class="diag-row"><span class="k">Stats</span><span class="v mono"><span id="diagConf">-</span><span style="color: var(--faint);"> &middot; </span>H=<span id="diagEntropy">-</span></span></div>
          </div>

          <div class="advisory">
            <h3>Non-chemical steps</h3>
            <p id="rxBio">Advisory appears here after a scan completes.</p>
            <h3>Chemical (ICAR / KVK reference)</h3>
            <p id="rxChem">Advisory appears here after a scan completes.</p>
          </div>

          <div class="hardware" id="sdAuditCard">
            <div>
              <div class="hw-title"><span class="dot" id="sdBadgeDot"></span><span id="sdTitleText">SD card: checking</span></div>
              <div class="hw-desc" id="sdDetailText">Querying the camera slot on the wand gateway at 192.168.4.1.</div>
            </div>
            <button class="btn btn-small" onclick="pollMeshNow()">Re-check</button>
          </div>

        </div>
      </section>

    </div>

    <!-- System log -->
    <section class="panel" style="margin-top: 12px;">
      <div class="panel-head"><span>System log</span><span class="right">newest last</span></div>
      <div class="terminal" id="terminal">
        <div class="log-line"><span class="log-t">[--:--:--]</span> <span class="log-tag log-tag-info">INFO</span> <span>Dashboard loaded. All inference runs locally in this browser; no data leaves the device.</span></div>
        <div class="log-line"><span class="log-t">[--:--:--]</span> <span class="log-tag log-tag-info">INFO</span> <span>Wand gateway: http://192.168.4.1 (connect to the wand Wi-Fi to link hardware).</span></div>
      </div>
    </section>

  </div>

  <!-- Hidden canvas for neural preprocessing -->
  <canvas id="offscreenCanvas" width="128" height="128" style="display: none;"></canvas>

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

    // Strict class ordering, identical to labels.json and the model output
    const KB_CLASSES = [
      {
        id: 0,
        name: "Tomato___Late_blight",
        crop: "Tomato",
        disease: "Late Blight",
        pathogen: "Phytophthora infestans (Oomycete)",
        status: "INFECTED",
        organic: "Neem Oil 5ml/L + Trichoderma viride. Prune lower canopy to enhance aeration.",
        chemical: "Cymoxanil 8% + Mancozeb 64% WP @ 2.5g/L or Ridomil Gold @ 2g/L"
      },
      {
        id: 1,
        name: "Tomato___Early_blight",
        crop: "Tomato",
        disease: "Early Blight",
        pathogen: "Alternaria solani (Fungus)",
        status: "WARNING",
        organic: "Baking soda 5g/L + compost tea. Mulch soil to prevent rain splash dispersal.",
        chemical: "Chlorothalonil 75% WP @ 2g/L or Copper Oxychloride 3g/L"
      },
      {
        id: 2,
        name: "Tomato___healthy",
        crop: "Tomato",
        disease: "Healthy",
        pathogen: "No pathogen detected",
        status: "HEALTHY",
        organic: "Maintain drip irrigation schedule and balanced 19:19:19 NPK foliar nutrition.",
        chemical: "No chemical fungicides required."
      },
      {
        id: 3,
        name: "Potato___Late_blight",
        crop: "Potato",
        disease: "Late Blight",
        pathogen: "Phytophthora infestans (Oomycete)",
        status: "INFECTED",
        organic: "Copper soap spray + haulm destruction 10 days pre-harvest to protect tubers.",
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
        pathogen: "No pathogen detected",
        status: "HEALTHY",
        organic: "Maintain uniform soil hilling to prevent tuber greening and solar exposure.",
        chemical: "No chemical intervention needed."
      }
    ];

    let modelLoadAttempts = 0;
    let modelInitScheduled = false;

    function _appendLog(msg, type = "info", customTime = null) {
      const term = document.getElementById("terminal");
      if (!term) return;
      const d = document.createElement("div");
      d.className = "log-line";
      const timeStr = customTime || new Date().toLocaleTimeString();
      let tagHtml = `<span class="log-tag log-tag-info">INFO</span>`;
      if (type === "ok")   tagHtml = `<span class="log-tag log-tag-ok">OK</span>`;
      if (type === "err")  tagHtml = `<span class="log-tag log-tag-err">ERROR</span>`;
      if (type === "ai")   tagHtml = `<span class="log-tag log-tag-ai">INFER</span>`;
      if (type === "warn") tagHtml = `<span class="log-tag log-tag-warn">WARN</span>`;
      d.innerHTML = `<span class="log-t">[${timeStr}]</span> ${tagHtml} <span>${msg}</span>`;
      term.appendChild(d);
      term.scrollTop = term.scrollHeight;
    }

    function log(msg, type = "info") {
      // Drain early boot logs if any queued before DOM ready
      if (window._bootLogs && window._bootLogs.length > 0) {
        const queue = window._bootLogs.splice(0);
        for (const item of queue) {
          _appendLog(item.msg, item.kind, item.time);
        }
      }
      _appendLog(msg, type);
    }

    function ensureScriptLoaded(src, checkFn, timeoutMs = 25000) {
      return new Promise((resolve, reject) => {
        if (checkFn()) {
          resolve();
          return;
        }

        const t0 = Date.now();
        const checkInterval = setInterval(() => {
          if (checkFn()) {
            clearInterval(checkInterval);
            resolve();
          } else if (Date.now() - t0 > timeoutMs) {
            clearInterval(checkInterval);
            // If still missing after timeout, attempt direct script injection
            log(`Script wait timeout for ${src}. Attempting direct script injection...`, "warn");
            const s = document.createElement("script");
            s.src = src + (src.includes("?") ? "&" : "?") + "t=" + Date.now();
            s.onload = () => {
              if (checkFn()) resolve();
              else reject(new Error(`Script ${src} loaded but namespace export check failed`));
            };
            s.onerror = () => reject(new Error(`Failed to load ${src} over Wi-Fi`));
            document.head.appendChild(s);
          }
        }, 300);
      });
    }

    async function initTFLite(retryCount = 0) {
      if (modelReady || isModelLoading) return;
      isModelLoading = true;
      modelInitScheduled = false;
      modelLoadAttempts = retryCount;

      const engineEl = document.getElementById("valEngine");
      if (engineEl) {
        engineEl.innerText = "Loading runtime";
        engineEl.className = "v warn";
      }

      try {
        log("Checking TensorFlow.js & TFLite WebAssembly runtimes...", "ai");

        // Wait for tf.min.js
        await ensureScriptLoaded("/vendor/tf.min.js", () => typeof tf !== "undefined", 20000);

        // Wait for tf-tflite.min.js
        await ensureScriptLoaded("/vendor/tf-tflite.min.js", () => {
          return (typeof tflite !== "undefined" && tflite.setWasmPath) ||
                 (typeof tf !== "undefined" && tf.tflite && tf.tflite.setWasmPath);
        }, 20000);

        // Resolve TFLite API
        let tfliteApi = null;
        if (typeof tflite !== 'undefined' && tflite.setWasmPath) {
          tfliteApi = tflite;
        } else if (typeof tf !== 'undefined' && tf.tflite && tf.tflite.setWasmPath) {
          tfliteApi = tf.tflite;
          await tf.setBackend('wasm');
          await tf.ready();
        } else {
          throw new Error("TFLite runtime not loaded. Verify /vendor/tf-tflite.min.js");
        }

        tfliteApi.setWasmPath('/vendor/');
        log("TFLite WASM runtime initialized.", "ok");

        if (engineEl) {
          engineEl.innerText = "Loading model";
          engineEl.className = "v warn";
        }

        log("Streaming model weights: /krishi_drishti_model.tflite...", "ai");
        const modelRes = await fetch('/krishi_drishti_model.tflite?v=round9', { cache: 'no-cache' });
        if (!modelRes.ok) throw new Error(`HTTP ${modelRes.status} (${modelRes.statusText}) loading model file`);
        const modelBuffer = await modelRes.arrayBuffer();

        // Validate FlatBuffer magic header ('TFL3' at offset 4)
        if (modelBuffer.byteLength < 8) {
          throw new Error(`Corrupted model payload: only ${modelBuffer.byteLength} bytes received`);
        }
        const bView = new Uint8Array(modelBuffer);
        const magic = String.fromCharCode(bView[4], bView[5], bView[6], bView[7]);
        if (magic !== 'TFL3') {
          throw new Error(`Invalid model header: expected 'TFL3', got '${magic}' (${modelBuffer.byteLength} bytes). Payload was not uncompressed FlatBuffer.`);
        }

        tfliteModel = await tfliteApi.loadTFLiteModel(modelBuffer);
        modelReady = true;
        isModelLoading = false;
        modelInitScheduled = false;

        if (engineEl) {
          engineEl.innerText = "Ready";
          engineEl.className = "v good";
        }
        log("Neural engine ready for offline leaf diagnosis.", "ok");
      } catch (err) {
        if (engineEl) {
          engineEl.innerText = "Unavailable";
          engineEl.className = "v bad";
        }
        log(`Model load failed: ${err.message}`, "err");

        if (retryCount < 3) {
          const delaySec = (retryCount + 1) * 4;
          log(`Retrying engine initialization in ${delaySec}s (attempt ${retryCount + 2}/4)...`, "warn");
          modelInitScheduled = true;
          setTimeout(() => {
            isModelLoading = false;
            initTFLite(retryCount + 1);
          }, delaySec * 1000);
        } else {
          isModelLoading = false;
          log("Automated retries exhausted. Check Wi-Fi connection to KRISHI-DRISHTI, then tap Re-check.", "err");
        }
      }
    }

    async function requestWakeLock() {
      try {
        if ('wakeLock' in navigator) {
          wakeLock = await navigator.wakeLock.request('screen');
          document.addEventListener('visibilitychange', async () => {
            if (wakeLock !== null && document.visibilityState === 'visible') {
              wakeLock = await navigator.wakeLock.request('screen');
            }
          });
        }
      } catch (err) {}
    }

    function startKeepAliveAudio() {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        keepAliveAudio = new AudioContext();
        const buffer = keepAliveAudio.createBuffer(1, keepAliveAudio.sampleRate * 1, keepAliveAudio.sampleRate);
        const source = keepAliveAudio.createBufferSource();
        source.buffer = buffer;
        source.loop = true;
        source.connect(keepAliveAudio.destination);
        source.start();
      } catch (e) {}
    }

    function stopKeepAliveAudio() {
      if (keepAliveAudio) {
        try { keepAliveAudio.close(); } catch (e) {}
        keepAliveAudio = null;
      }
    }

    function toggleServer() {
      if (isRunning) {
        stopServer();
      } else {
        startServer();
      }
    }

    function startServer() {
      if (isRunning) return;
      isRunning = true;

      requestWakeLock();
      startKeepAliveAudio();

      const pill = document.getElementById("statusPill");
      if (pill) pill.className = "server-state running";
      safeSetText("statusText", "SCANNING");

      const btn = document.getElementById("btnToggle");
      if (btn) {
        btn.textContent = "Pause scanning";
        btn.className = "btn btn-paused";
      }

      log("Scanning started. Polling wand gateway every 600 ms.", "ok");
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
      if (pill) pill.className = "server-state stopped";
      safeSetText("statusText", "STANDBY");

      const btn = document.getElementById("btnToggle");
      if (btn) {
        btn.textContent = "Start scanning";
        btn.className = "btn btn-primary";
      }

      safeSetText("valCameraLink", "Standby");
      safeSetStyle("valCameraLink", "color", "var(--muted)");
      safeSetText("valWandLink", "Off");
      safeSetStyle("valWandLink", "color", "var(--muted)");

      log("Scanning paused.", "warn");
    }

    async function pollMeshNow() {
      log("Checking ESP32-CAM hardware and SD slot...");
      if (!modelReady && !isModelLoading) {
        log("Manual trigger: resetting model load sequence...", "ai");
        modelLoadAttempts = 0;
        modelInitScheduled = false;
        initTFLite(0);
      }
      await checkCameraForNewScan();
    }

    async function checkCameraForNewScan() {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);

        const res = await fetch(CAMERA_STATUS_URL, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!res.ok) return;
        const status = await res.json();

        // 1. Camera gateway link
        const camEl = document.getElementById("valCameraLink");
        if (camEl) {
          camEl.innerText = "Online (AP)";
          camEl.className = "v good";
        }

        // 2. MicroSD card detection and verification
        const sdEl = document.getElementById("valSdStatus");
        const sdCard = document.getElementById("sdAuditCard");
        const sdDot = document.getElementById("sdBadgeDot");
        const sdTitle = document.getElementById("sdTitleText");
        const sdDetail = document.getElementById("sdDetailText");

        if (status.sd_ready) {
          const capText = status.sd_capacity_mb ? `${Math.round(status.sd_capacity_mb/1024*10)/10} GB` : "FAT32";
          if (sdEl) {
            sdEl.innerText = `Ready (${capText})`;
            sdEl.className = "v good";
          }
          if (sdCard) sdCard.style.borderColor = "rgba(76, 195, 138, 0.4)";
          if (sdDot) { sdDot.style.background = "var(--ok)"; }
          if (sdTitle) { sdTitle.innerText = `SD card: detected and mounted (${capText})`; }
          if (sdDetail) {
            sdDetail.innerText = "Camera filesystem active. Shutter scans are saved to /scans/ on the card.";
          }
          if (!modelReady && !isModelLoading && !modelInitScheduled && modelLoadAttempts < 3) {
            initTFLite(0);
          }
        } else {
          if (sdEl) {
            sdEl.innerText = "Not detected";
            sdEl.className = "v bad";
          }
          if (sdCard) sdCard.style.borderColor = "rgba(229, 72, 77, 0.4)";
          if (sdDot) { sdDot.style.background = "var(--bad)"; }
          if (sdTitle) { sdTitle.innerText = "SD card: not detected in camera slot"; }
          if (sdDetail) {
            sdDetail.innerText = "No card in the camera slot. Insert a FAT32 Class-10 TF card, then tap Re-check.";
          }
        }

        // 3. Wand controller connectivity
        const wandEl = document.getElementById("valWandLink");
        if (wandEl) {
          if (status.wand_connected) {
            wandEl.innerText = "Connected";
            wandEl.className = "v good";
          } else {
            wandEl.innerText = "Off";
            wandEl.className = "v";
          }
        }

        // 4. Ingest ambient telemetry
        if (status.telemetry_available) {
          currentTelemetry = {
            humidity: status.humidity,
            temperature: status.temperature
          };
        } else {
          currentTelemetry = null;
        }

        // 5. New shutter scan discovery
        if (status.scan_count && status.scan_count > lastProcessedScanId) {
          if (isRunning) {
            await processScanAndRespond(status.scan_count);
          }
        }
      } catch (err) {
        if (!isRunning) {
          safeSetText("valCameraLink", "Not connected");
          safeSetStyle("valCameraLink", "color", "var(--muted)");
        }
      }
    }

    async function processScanAndRespond(scanId) {
      lastProcessedScanId = scanId;
      log(`New shutter capture: scan #${scanId}`, "ai");

      const t0 = performance.now();

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
        if (leafImg) {
          leafImg.src = img.src;
          leafImg.style.display = "block";
        }
        if (placeholder) {
          placeholder.style.display = "none";
        }

        log(`Scan #${scanId} loaded. Running inference...`, "ai");
        const diag = await runEdgeInference(img);
        const elapsed = Math.round(performance.now() - t0);

        updateMetricsAndUI(diag, elapsed, scanId);
        playAudioChime();

        log(`Diagnosis: ${diag.crop} - ${diag.disease} (${diag.confidence}%, H=${diag.entropy}) in ${elapsed} ms`, "ok");
        log(`Advisory: ${diag.organic}`);

        const setUrl = `${CAMERA_DIAG_SET_URL}?scan_id=${scanId}&crop=${encodeURIComponent(diag.crop)}&disease=${encodeURIComponent(diag.disease)}&confidence=${diag.confidence}&status=${encodeURIComponent(diag.status)}&organic=${encodeURIComponent(diag.organic)}&chemical=${encodeURIComponent(diag.chemical)}`;

        try {
          const syncRes = await fetch(setUrl);
          if (syncRes.ok) {
            log(`Result synced to wand display (scan #${scanId}).`, "ok");
          } else {
            log(`Wand sync rejected: HTTP ${syncRes.status}`, "warn");
          }
        } catch (syncErr) {
          log(`Failed to sync to wand: ${syncErr.message}`, "err");
        }

      } catch (err) {
        log(`Failed to process scan #${scanId}: ${err.message}`, "err");
      }
    }

    async function runEdgeInference(imgElement) {
      const cvs = document.getElementById("offscreenCanvas");
      const ctx = cvs.getContext("2d", { willReadFrequently: true });

      // 1. Aspect-ratio preserving center-square crop to 128x128
      // Keeps leaf geometry consistent with how the model was trained.
      const nw = imgElement.naturalWidth || imgElement.width || 128;
      const nh = imgElement.naturalHeight || imgElement.height || 128;
      const side = Math.min(nw, nh);
      const sx = Math.floor((nw - side) / 2);
      const sy = Math.floor((nh - side) / 2);
      ctx.clearRect(0, 0, 128, 128);
      ctx.drawImage(imgElement, sx, sy, side, side, 0, 0, 128, 128);

      // 2. Foliar screening and glare rejection gate
      const frameData = ctx.getImageData(0, 0, 128, 128);
      const data = frameData.data;
      let totalPixels = 128 * 128;
      let greenChlorophyllPixels = 0;
      let necroticLesionPixels = 0;
      let humanSkinPixels = 0;
      let darkVoidPixels = 0;
      let glarePixels = 0;
      let neutralPixels = 0;

      // Luminance plane for the brown-tissue texture metric (used by the
      // skin filter to distinguish smooth human skin from shriveled,
      // lesion-textured terminal necrosis - which satisfies the skin
      // chromaticity rule but is genuine plant tissue).
      const lumArr = new Float32Array(totalPixels);
      for (let p = 0; p < totalPixels; p++) {
        const q = p * 4;
        lumArr[p] = (data[q] + data[q + 1] + data[q + 2]) / 3.0;
      }
      let brownPixels = 0;
      let brownGradSum = 0.0;
      let brownLumSum = 0.0;

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        // A. True foliar chlorophyll (green dominant and elevated above blue)
        if (g > 35 && g > r && g > b) {
          greenChlorophyllPixels++;
        }
        // B. Fungal necrotic tissue (dark brown/olive blight lesion)
        else if (r > 40 && g > 30 && b < 110 && r >= g && (r - g) < 45 && (r + g) > (2.2 * b)) {
          necroticLesionPixels++;
        }

        // C. Human skin tone filter
        if (r > 95 && g > 40 && b > 20 && r > g && g > b && (r - g) > 12 && (r - b) > 20) {
          humanSkinPixels++;
        }

        // Brown-tissue texture accumulation (necrotic OR skin chromaticity):
        // smooth skin has low local luminance gradient; shriveled necrotic
        // blight tissue has high gradient from lesions and vein collapse.
        if ((r > 95 && g > 40 && b > 20 && r > g && g > b && (r - g) > 12 && (r - b) > 20) ||
            (r > 40 && g > 30 && b < 110 && r >= g && (r - g) < 45 && (r + g) > (2.2 * b))) {
          const px = i / 4;
          const row = (px / 128) | 0;
          const col = px % 128;
          let gsum = 0.0;
          if (col > 0) gsum += Math.abs(lumArr[px] - lumArr[px - 1]);
          if (row > 0) gsum += Math.abs(lumArr[px] - lumArr[px - 128]);
          brownGradSum += gsum;
          brownLumSum += lumArr[px];
          brownPixels++;
        }

        // D. Peripheral dark void / lens cap
        if (r < 30 && g < 30 && b < 30) {
          darkVoidPixels++;
        }

        // E. Flash glare / overexposure
        if (r > 225 && g > 225 && b > 225) {
          glarePixels++;
        }

        // F. Neutral grey indoor surface (table, wall, floor)
        if (Math.abs(r - g) < 18 && Math.abs(g - b) < 18 && Math.abs(r - b) < 22) {
          neutralPixels++;
        }
      }

      const greenRatio = greenChlorophyllPixels / totalPixels;
      const skinRatio = humanSkinPixels / totalPixels;
      const voidRatio = darkVoidPixels / totalPixels;
      const glareRatio = glarePixels / totalPixels;
      const neutralRatio = neutralPixels / totalPixels;
      const totalFoliarRatio = (greenChlorophyllPixels + necroticLesionPixels) / totalPixels;
      const necRatio = necroticLesionPixels / totalPixels;
      const brownGradMean = brownPixels > 100 ? brownGradSum / brownPixels : 0.0;
      const brownLumMean = brownPixels > 100 ? brownLumSum / brownPixels : 255.0;

      // A frame dominated by textured, dark, necrotic plant tissue is a
      // genuine (possibly terminal) blight haulm: brown tissue satisfies the
      // skin chromaticity rule, but smooth human skin does not show the
      // lesion/vein texture. Exempt such frames from the skin reject and let
      // the OE-trained model decide (it withholds genuinely unknown frames).
      // v2.5.1: threshold lowered 0.30 -> 0.25 (calibrated: people seeds stay
      // 100% rejected because smooth skin fails grad>18 & lum<135; blight
      // frames 40/40 pass; partial-necrosis field frames at nec 0.267-0.285
      // that were missed at 0.30 now reach the model).
      const necroticDominant = necRatio > 0.25 && brownGradMean > 18 && brownLumMean < 135;

      // Filter 1: reject human skin
      if (skinRatio > 0.12 && greenRatio < 0.08 && !necroticDominant) {
        return {
          crop: "Invalid",
          disease: "No Leaf Detected",
          pathogen: "Human skin or hand detected in frame",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "This scanner is calibrated only for tomato and potato leaves.",
          chemical: "Position the shroud over a tomato or potato crop leaf.",
          entropy: "0.00"
        };
      }

      // Filter 2: reject lens cap / complete darkness
      if (voidRatio > 0.75) {
        return {
          crop: "Invalid",
          disease: "No Leaf Detected",
          pathogen: "Frame too dark (lens cap or closed shroud)",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Remove the lens cap and make sure the leaf is lit.",
          chemical: "Hold the wand about 10 cm from the leaf and re-scan.",
          entropy: "0.00"
        };
      }

      // Filter 3: reject severe overexposure / flash glare
      if (glareRatio > 0.30) {
        return {
          crop: "Invalid",
          disease: "No Leaf Detected",
          pathogen: "Frame overexposed by flash or reflection",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Avoid aiming at reflective surfaces or close-range white objects.",
          chemical: "Keep the shroud 8 to 10 cm from the leaf and re-scan.",
          entropy: "0.00"
        };
      }

      // Filter 4: reject non-plant surfaces and backgrounds
      if (totalFoliarRatio < 0.15 || (neutralRatio > 0.50 && greenRatio < 0.15)) {
        return {
          crop: "Invalid",
          disease: "No Leaf Detected",
          pathogen: "No plant foliage found in frame",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Aim the camera at tomato or potato foliage.",
          chemical: "Hold the wand about 10 cm from the leaf and re-scan.",
          entropy: "0.00"
        };
      }

      // 3. MobileNetV3 float16 WASM inference
      let probs = [];
      if (modelReady && tfliteModel) {
        let tfImg = null;
        let inputTensor = null;
        let output = null;
        try {
          tfImg = tf.browser.fromPixels(cvs);
          inputTensor = tfImg.toFloat().expandDims(0);
          output = tfliteModel.predict(inputTensor);
          probs = Array.from(output.dataSync());
        } finally {
          if (tfImg) tfImg.dispose();
          if (inputTensor) inputTensor.dispose();
          if (output) output.dispose();
        }
      } else {
        return {
          crop: "System Notice",
          disease: "AI Engine Unavailable",
          pathogen: "The TFLite model is not ready in the browser",
          confidence: "0.0",
          status: "UNCERTAIN",
          organic: "Make sure this device is connected to the wand Wi-Fi and the model has loaded.",
          chemical: "Consult a local Krishi Vigyan Kendra (KVK) agronomist.",
          entropy: "0.00"
        };
      }

      // 4. Shannon entropy: H = -sum(p * ln(p))
      let entropy = 0.0;
      for (const p of probs) {
        if (p > 1e-6) entropy -= p * Math.log(p);
      }

      // 5. Argmax
      let maxIdx = 0;
      let maxProb = probs[0];
      for (let i = 1; i < probs.length; i++) {
        if (probs[i] > maxProb) {
          maxProb = probs[i];
          maxIdx = i;
        }
      }
      const confPercent = (maxProb * 100).toFixed(1);

      // Decision margin (top1 - top2)
      const sortedProbs = probs.slice().sort((a, b) => b - a);
      const margin = sortedProbs[0] - (sortedProbs.length > 1 ? sortedProbs[1] : 0.0);

      // 6. Gating and advisory
      const match = KB_CLASSES[maxIdx];
      let chemRec = match.chemical;
      // Microclimate cross-gating: late blight spores need high humidity
      if (match.disease.includes("Late Blight") && currentTelemetry && currentTelemetry.humidity > 0 && currentTelemetry.humidity < 85.0) {
        chemRec = `Withheld: relative humidity is ${Math.round(currentTelemetry.humidity)}%. Late blight spores stay dormant below 85% RH. Fungicide suppressed; inspect for abiotic chlorosis instead.`;
      }

      // Tier 1: high-confidence diagnosis
      if (maxProb >= 0.50 && entropy <= 1.45 && margin >= 0.12) {
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

      // Tier 2: suspected diagnosis, chemical withheld
      if (maxProb >= 0.30 || margin >= 0.05) {
        return {
          crop: match.crop,
          disease: match.disease,
          pathogen: `${match.pathogen} (early lesion or low contrast sample)`,
          confidence: confPercent,
          status: "UNCERTAIN",
          organic: `Symptoms suggest possible ${match.crop} ${match.disease} (${confPercent}%). Prune isolated symptomatic leaflets and keep the canopy ventilated.`,
          chemical: `Withheld (low confidence, ${confPercent}%). Do not spray without a second confirming symptom or an agronomist review. Retake the photo in direct sunlight at 10 cm.`,
          entropy: entropy.toFixed(2)
        };
      }

      // Tier 3: out-of-distribution or non-target rejection
      return {
        crop: "Uncertain",
        disease: "Low Confidence",
        pathogen: "Ambiguous foliar pattern or non-target species",
        confidence: confPercent,
        status: "UNCERTAIN",
        organic: "Hold the wand steady about 10 cm from the leaf.",
        chemical: "Retake under uniform sunlight without shadow or blur.",
        entropy: entropy.toFixed(2)
      };
    }

    function safeSetText(id, text) {
      const el = document.getElementById(id);
      if (el) el.innerText = text;
    }

    function safeSetHTML(id, html) {
      const el = document.getElementById(id);
      if (el) el.innerHTML = html;
    }

    function safeSetStyle(id, prop, val) {
      const el = document.getElementById(id);
      if (el && el.style) el.style[prop] = val;
    }

    function updateMetricsAndUI(diag, latency, scanId) {
      totalScansProcessed++;
      safeSetText("valScanCount", String(totalScansProcessed));
      safeSetText("valLatency", `${latency} ms`);
      safeSetHTML("scanTimestamp", `Scan #${scanId} &middot; ${new Date().toLocaleTimeString()} &middot; ${latency} ms`);

      safeSetText("diagPrimary", `${diag.crop}: ${diag.disease}`);
      safeSetText("diagPathogen", diag.pathogen);

      const gateEl = document.getElementById("diagGate");
      if (gateEl) {
        const s = diag.status;
        if (s === "INFECTED")       gateEl.innerHTML = `<span class="gate gate-infected">INFECTED</span>`;
        else if (s === "WARNING")   gateEl.innerHTML = `<span class="gate gate-warning">WARNING</span>`;
        else if (s === "HEALTHY")   gateEl.innerHTML = `<span class="gate gate-healthy">HEALTHY</span>`;
        else                        gateEl.innerHTML = `<span class="gate gate-uncertain">${s}</span>`;
      }

      safeSetText("diagConf", `${diag.confidence}%`);
      safeSetText("diagEntropy", diag.entropy);

      safeSetText("rxBio", diag.organic);
      safeSetText("rxChem", diag.chemical);
    }

    async function simulateFieldScan() {
      const demoScanId = (lastProcessedScanId || 0) + 1;
      lastProcessedScanId = demoScanId;
      log(`Demo: running scan #${demoScanId} on the bundled late blight sample.`, "ai");
      await testRealLeaf('/sample_leaves/late_blight_512.jpg', 'Bundled late blight sample');
    }

    async function testRealLeaf(url, labelName) {
      const demoScanId = (lastProcessedScanId || 0) + 1;
      lastProcessedScanId = demoScanId;
      log(`Loading sample: ${labelName}`, "ai");

      try {
        const img = new Image();
        img.crossOrigin = "anonymous";
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = () => reject(new Error("Could not load " + url));
          img.src = `${url}?t=${Date.now()}`;
        });

        const leafImg = document.getElementById("leafImg");
        const placeholder = document.getElementById("thumbPlaceholder");
        if (leafImg) {
          leafImg.src = img.src;
          leafImg.style.display = "block";
        }
        if (placeholder) {
          placeholder.style.display = "none";
        }

        const t0 = performance.now();
        const diag = await runEdgeInference(img);
        const latency = Math.round(performance.now() - t0);

        updateMetricsAndUI(diag, latency, demoScanId);
        playAudioChime();
        log(`Diagnosis: ${diag.crop}: ${diag.disease} (${diag.confidence}%, H=${diag.entropy}) in ${latency} ms`, "ok");
        return diag;
      } catch (err) {
        log(`Error diagnosing ${labelName}: ${err.message}`, "err");
        console.error(err);
        return null;
      }
    }

    function handleLeafUpload(event) {
      const file = event.target.files[0];
      if (!file) return;

      const demoScanId = (lastProcessedScanId || 0) + 1;
      lastProcessedScanId = demoScanId;
      log(`Loading uploaded photo: ${file.name} (${Math.round(file.size/1024)} KB)`, "ai");

      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const img = new Image();
          img.onload = async () => {
            const leafImg = document.getElementById("leafImg");
            const placeholder = document.getElementById("thumbPlaceholder");
            if (leafImg) {
              leafImg.src = img.src;
              leafImg.style.display = "block";
            }
            if (placeholder) {
              placeholder.style.display = "none";
            }

            const t0 = performance.now();
            const diag = await runEdgeInference(img);
            const latency = Math.round(performance.now() - t0);

            updateMetricsAndUI(diag, latency, demoScanId);
            playAudioChime();
            log(`Diagnosis: ${diag.crop}: ${diag.disease} (${diag.confidence}%, H=${diag.entropy}) in ${latency} ms`, "ok");
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
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const audioCtx = new AudioContext();
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

    // Auto-initialize TFLite and the hardware watchdog on page load
    function initHardwareWatchdog() {
      checkCameraForNewScan();
      // Continuous background hardware polling every 1500 ms while in standby
      setInterval(() => {
        if (!isRunning) {
          // If model or runtime is currently streaming over Wi-Fi, back off to avoid TCP contention
          if (isModelLoading) return;
          checkCameraForNewScan();
        }
      }, 1500);
    }

    if (document.readyState === 'loading') {
      window.addEventListener("DOMContentLoaded", () => {
        initHardwareWatchdog();
        initTFLite(0);
      });
    } else {
      initHardwareWatchdog();
      initTFLite(0);
    }
    window.addEventListener("load", () => {
      if (!modelReady && !isModelLoading && !modelInitScheduled) {
        initTFLite(0);
      }
      checkCameraForNewScan();
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
  if (!sdReady) return;
  if (scanCounter > 0) return;
  scanCounter = 0;

  while (scanCounter < 10000) {
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
  config.xclk_freq_hz = 16000000; // 16MHz XCLK reduces DMA pressure, eliminates FB-OVF
  config.pixel_format = PIXFORMAT_JPEG;
  if (psramAvailable) {
    config.frame_size   = FRAMESIZE_SXGA;  // 1280 x 1024 - reliable with PSRAM, no FB-OVF
    config.jpeg_quality = 10;
    config.fb_count     = 1;              // 1 buffer prevents DMA overflow (FB-OVF)
    config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY; // Safer than GRAB_LATEST on marginal PSRAM
    config.fb_location  = CAMERA_FB_IN_PSRAM;
  } else {
    Serial.println("[CAM WARN] No PSRAM detected. Falling back to SVGA (800x600)");
    config.frame_size   = FRAMESIZE_SVGA;  // 800 x 600
    config.jpeg_quality = 12;
    config.fb_count     = 1;
    config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location  = CAMERA_FB_IN_DRAM;
  }

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
static uint64_t cachedSdCardSizeMB = 0;
static uint8_t* lastRamFrameBuf = nullptr;
static size_t lastRamFrameLen = 0;

bool tryMountSD(bool quiet) {
  if (sdReady && cachedSdCardSizeMB > 0) return true;
  SD_MMC.end();
  delay(10);
  if (!quiet) Serial.println("[SD] Mounting MicroSD in 1-bit mode (20MHz)...");
  if (!SD_MMC.begin("/sdcard", true, false, 20000, 5)) {
    if (!quiet) Serial.println("[SD] 20MHz mount failed, retrying at 10MHz...");
    SD_MMC.end();
    delay(10);
    if (!SD_MMC.begin("/sdcard", true, false, 10000, 5)) {
      if (!quiet) Serial.println("[SD WARN] MicroSD card not mounted (insert Class 10 card)");
      return false;
    }
  }
  uint8_t cardType = SD_MMC.cardType();
  if (cardType == CARD_NONE) {
    if (!quiet) Serial.println("[SD] No card in slot");
    SD_MMC.end();
    return false;
  }
  cachedSdCardSizeMB = SD_MMC.cardSize() / (1024ULL * 1024ULL);
  Serial.printf("[SD] MicroSD Fast Mounted! Capacity: %llu MB\n", cachedSdCardSizeMB);
  return true;
}

bool initialiseSD() {
  return tryMountSD(false);
}

// --------------------------------------------------
// SD HOT-PLUG: detect a card inserted after boot
// --------------------------------------------------
static const uint32_t SD_HOTPLUG_RETRY_MS = 5000;
static uint32_t lastSdRetryMs = 0;

void pollSdHotplug() {
  if (sdReady) return;
  uint32_t now = millis();
  if (now - lastSdRetryMs < SD_HOTPLUG_RETRY_MS) return;
  lastSdRetryMs = now;
  if (tryMountSD(true)) {
    sdReady = true;
    findNextScanNumber();
    Serial.println("[SD HOTPLUG] Card detected at runtime, mounted without reset");
  }
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
  uint64_t sizeMB = sdReady ? cachedSdCardSizeMB : 0;
  int clientCount = WiFi.softAPgetStationNum();
  bool wandConnected = (clientCount >= 1) || (lastWandActivityMs > 0 && (millis() - lastWandActivityMs < 30000));

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

  // 1. Dynamic Sensor Reconnect Check
  if (!cameraReady) {
    Serial.println("[CAPTURE] Camera sensor offline, attempting runtime re-init...");
    cameraReady = initialiseCamera();
  }
  if (!cameraReady) {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(503, "application/json", "{\"status\":\"error\",\"message\":\"camera_offline\",\"detail\":\"Check OV2640 ribbon\"}");
    return;
  }

  // 2. Dynamic MicroSD Mount Check
  if (!sdReady) {
    Serial.println("[CAPTURE] SD card unmounted, attempting runtime mount...");
    sdReady = initialiseSD();
    if (sdReady) {
      findNextScanNumber();
    }
  }

  diagnosisReady = false; // Reset diagnosis flag for newly captured leaf

  // 3. Timed Flash Illumination & Capture Sequence (Optimized pulse: ~200ms settling, immediate cutoff to prevent thermal/brownout stress)
  digitalWrite(FLASH_LED_PIN, HIGH);
  Serial.println("[CAPTURE] Flash illuminated. Settling sensor exposure (200 ms)...");
  delay(200);

  // Flush any pre-exposure frame so sensor AEC/AGC adapts to full flash illumination
  camera_fb_t* stale_fb = esp_camera_fb_get();
  if (stale_fb) esp_camera_fb_return(stale_fb);

  camera_fb_t* fb = esp_camera_fb_get();
  // Turn flash OFF immediately after capture to eliminate thermal & power rail stress
  digitalWrite(FLASH_LED_PIN, LOW);
  Serial.println("[CAPTURE] Frame captured. Flash turned OFF.");

  if (!fb) {
    digitalWrite(FLASH_LED_PIN, LOW);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(500, "application/json", "{\"status\":\"error\",\"message\":\"capture_failed\"}");
    return;
  }

  // 4. Mirror Frame to Dedicated RAM/PSRAM Buffer for Instant Web/AI Streaming
  if (lastRamFrameBuf != nullptr) {
    free(lastRamFrameBuf);
    lastRamFrameBuf = nullptr;
    lastRamFrameLen = 0;
  }
  if (psramAvailable) {
    lastRamFrameBuf = (uint8_t*)ps_malloc(fb->len);
  } else {
    lastRamFrameBuf = (uint8_t*)malloc(fb->len);
  }
  if (lastRamFrameBuf != nullptr) {
    memcpy(lastRamFrameBuf, fb->buf, fb->len);
    lastRamFrameLen = fb->len;
  }

  uint32_t nextId = scanCounter + 1;
  char filename[32];
  snprintf(filename, sizeof(filename), "/scan_%06lu.jpg", (unsigned long)nextId);
  size_t written = 0;

  // 5. If SD card is ready, persist frame to SDMMC
  if (sdReady) {
    File file = SD_MMC.open(filename, FILE_WRITE);
    if (file) {
      written = file.write(fb->buf, fb->len);
      file.close();
    }
    if (written >= 512 && written == fb->len) {
      scanCounter = nextId;
      Serial.printf("[CAPTURE] Scan #%lu saved to SD (%u bytes)\n", (unsigned long)scanCounter, (unsigned int)written);
    } else {
      Serial.printf("[SD WARN] Frame write partial (%u / %u bytes). Retained in RAM.\n", 
                    (unsigned int)written, (unsigned int)fb->len);
      scanCounter = nextId;
    }
  } else {
    // RAM Mode fallback: AI diagnosis works perfectly without physical SD card!
    scanCounter = nextId;
    Serial.printf("[CAPTURE] Scan #%lu captured in RAM buffer (%u bytes) [SD Offline]\n", 
                  (unsigned long)scanCounter, (unsigned int)fb->len);
  }

  esp_camera_fb_return(fb);

  // Flash cycle completed during capture - no post-capture delay needed

  String body = "{\"status\":\"success\",\"scan_id\":" + String(scanCounter);
  body += ",\"filename\":\"" + String(filename) + "\",\"bytes\":" + String(lastRamFrameLen);
  body += ",\"storage\":\"" + String(sdReady ? "sd" : "ram") + "\"}";

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", body);
}

void handleGetImage() {
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

  // 1. Try streaming from MicroSD if mounted & file exists
  if (sdReady && SD_MMC.exists(filename.c_str())) {
    File f = SD_MMC.open(filename.c_str(), FILE_READ);
    if (server.hasArg("download")) {
      server.sendHeader("Content-Disposition", "attachment; filename=\"" + filename.substring(1) + "\"");
    }
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.streamFile(f, "image/jpeg");
    f.close();
    isStreaming = false;
    return;
  }

  // 2. Fallback: Stream latest captured frame from RAM buffer
  if (lastRamFrameBuf != nullptr && lastRamFrameLen > 0) {
    if (server.hasArg("download")) {
      server.sendHeader("Content-Disposition", "attachment; filename=\"scan_latest.jpg\"");
    }
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send_P(200, "image/jpeg", (const char*)lastRamFrameBuf, lastRamFrameLen);
    isStreaming = false;
    return;
  }

  isStreaming = false;
  server.send(404, "text/plain", "Not found");
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

  if (!sdReady) {
    server.send(503, "text/plain", "SD offline - Insert MicroSD card in ESP32-CAM slot");
    return;
  }

  // Fast transparent GZIP acceleration ONLY for scripts, wasm, and text (never for raw binary tflite model)
  bool allowGz = path.endsWith(".js") || path.endsWith(".wasm") || path.endsWith(".json") || path.endsWith(".html") || path.endsWith(".css");
  String pathGz = path + ".gz";
  if (allowGz && server.hasHeader("Accept-Encoding") && server.header("Accept-Encoding").indexOf("gzip") >= 0 && SD_MMC.exists(pathGz.c_str())) {
    File f = SD_MMC.open(pathGz.c_str(), FILE_READ);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Cache-Control", "public, max-age=86400");
    // Note: streamFile() detects .gz extension on f.name() and sends Content-Encoding: gzip automatically.
    // Do NOT call server.sendHeader("Content-Encoding", "gzip") here to prevent duplicate headers in Chrome.
    server.streamFile(f, contentType);
    f.close();
    Serial.printf("[HTTP] Served GZIP: %s\n", pathGz.c_str());
    return;
  }

  if (SD_MMC.exists(path.c_str())) {
    File f = SD_MMC.open(path.c_str(), FILE_READ);
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Cache-Control", "public, max-age=86400");
    server.streamFile(f, contentType);
    f.close();
    Serial.printf("[HTTP] Served RAW: %s\n", path.c_str());
    return;
  }
  Serial.printf("[HTTP 404] Not Found: %s\n", path.c_str());
  server.send(404, "text/plain", "404 Not Found");
}

void setup() {
  Serial.begin(115200);
  setCpuFrequencyMhz(240); // 240MHz performance lock

  // Keep the task watchdog (TG1) out of the boot path: RF calibration during
  // radio bringup can stall the loop long enough to trip TG1WDT_SYS_RESET on
  // marginal USB power. The app loop below is cooperative; a hardware hang
  // still resets via the ROM watchdog, so safety is preserved.
  disableCore1WDT();
  disableLoopWDT();

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  Serial.println("\n========================================");
  Serial.println("  KRISHI-DRISHTI :: ESP32-CAM v2.5.1");
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
  const char *headerKeys[] = {"Accept-Encoding", "User-Agent"};
  server.collectHeaders(headerKeys, 2);

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
  pollSdHotplug();
  delay(2);
}
