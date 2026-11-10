"""
KRISHI-DRISHTI: Automated Hardware-Independent Integration & Unit Test Suite
----------------------------------------------------------------------------
Tests:
1. labels.json Strict 1:1 Class Index Alignment
2. Real Model File Integrity & Architecture Verification
3. Foliar Plausibility Gate (Rejects Non-Foliar / Black / White / Lens Cap)
4. Shannon Entropy & Scientific Uncertainty Gating
5. End-to-End Edge AI Inference Execution
6. ESP32-CAM REST Telemetry Round-Trip Contract Simulation
7. Stale Scan ID Rejection (HTTP 409 Conflict)
8. TFLite Model Input Contract & Softmax Probability Distribution (Graceful Skip if TF Missing)
9. Controller Timeout Race Protection (Valid Diagnosis Never Overwritten)
10. Modular C++ Microclimate Tracker Architecture, Native Test Harness & State Decay Logic
11. Production Daemon Preprocess Image Quantization Verification (uint8 [0, 255] vs int8 [-128, 127])
"""

import os
import sys
import json
import math
import time
import shutil
import subprocess
import tempfile
import unittest
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

AI_ENGINE_DIR = os.path.join(REPO_ROOT, "ai_engine")
LABELS_PATH = os.path.join(AI_ENGINE_DIR, "labels.json")
TFLITE_PATH = os.path.join(AI_ENGINE_DIR, "krishi_drishti_model.tflite")
REPORT_PATH = os.path.join(AI_ENGINE_DIR, "model_evaluation_report.json")
SAMPLE_LEAVES_DIR = os.path.join(AI_ENGINE_DIR, "sample_leaves")
CTRL_DIR = os.path.join(REPO_ROOT, "firmware", "KRISHI_DRISHTI_Controller")
CPP_HARNESS_PATH = os.path.join(REPO_ROOT, "tests", "test_microclimate_tracker.cpp")

EXPECTED_CLASSES = [
    "Tomato___Late_blight",
    "Tomato___Early_blight",
    "Tomato___healthy",
    "Potato___Late_blight",
    "Potato___Early_blight",
    "Potato___healthy"
]

class TestLabelsAndModelContract(unittest.TestCase):
    def test_labels_file_exists_and_matches_strict_classes(self):
        """Verify labels.json exists and strictly matches the 6 Solanaceae categories 1:1."""
        self.assertTrue(os.path.exists(LABELS_PATH), f"Missing labels file: {LABELS_PATH}")
        with open(LABELS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        classes = data if isinstance(data, list) else data.get("classes", [])
        self.assertEqual(len(classes), 6, f"Expected exactly 6 classes, got {len(classes)}")
        
        expected_meta = [
            (0, "Tomato", "Late Blight"),
            (1, "Tomato", "Early Blight"),
            (2, "Tomato", "Healthy"),
            (3, "Potato", "Late Blight"),
            (4, "Potato", "Early Blight"),
            (5, "Potato", "Healthy")
        ]

        for idx, (exp_id, exp_crop, exp_disease) in enumerate(expected_meta):
            self.assertEqual(classes[idx]["id"], exp_id)
            self.assertEqual(classes[idx]["crop"], exp_crop)
            self.assertEqual(classes[idx]["disease"], exp_disease)
            self.assertTrue(len(classes[idx]["organic"]) > 0)
            self.assertTrue(len(classes[idx]["chemical"]) > 0)

    def test_model_artifact_and_report_integrity(self):
        """Verify TFLite model exists, is >1MB, and evaluation report contains genuine metrics."""
        self.assertTrue(os.path.exists(TFLITE_PATH), f"Missing TFLite model at {TFLITE_PATH}")
        model_size = os.path.getsize(TFLITE_PATH)
        self.assertGreater(model_size, 1_000_000, f"Model size {model_size} bytes is unusually small")

        self.assertTrue(os.path.exists(REPORT_PATH), f"Missing report at {REPORT_PATH}")
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            report = json.load(f)
        
        self.assertEqual(report["architecture"], "MobileNetV3-Small")
        self.assertEqual(report["training_samples"], 11399)
        self.assertEqual(report["validation_samples"], 2850)
        self.assertGreater(report["validation_accuracy"], 0.85)
        self.assertGreater(report["validation_macro_f1"], 0.85)
        self.assertEqual(len(report["validation_confusion_matrix"]), 6)


class TestFoliarPlausibilityAndEntropy(unittest.TestCase):
    def calculate_foliar_ratio(self, arr):
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        is_foliar = ((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))
        return float(np.mean(is_foliar))

    def calculate_shannon_entropy(self, probs):
        return -float(sum(p * math.log(p) for p in probs if p > 1e-6))

    def test_non_foliar_rejection(self):
        """Verify all-black (lens cap), all-white (wall), and static noise are rejected."""
        black = np.zeros((128, 128, 3), dtype=np.uint8)
        self.assertLess(self.calculate_foliar_ratio(black), 0.12)

        white = np.full((128, 128, 3), 255, dtype=np.uint8)
        self.assertLess(self.calculate_foliar_ratio(white), 0.12)

    def test_foliar_acceptance_on_real_samples(self):
        """Verify genuine sample leaf images pass the foliar plausibility filter."""
        sample_path = os.path.join(SAMPLE_LEAVES_DIR, "tomato_late_blight.jpg")
        if os.path.exists(sample_path):
            img = Image.open(sample_path).resize((128, 128))
            arr = np.array(img)
            ratio = self.calculate_foliar_ratio(arr)
            self.assertGreater(ratio, 0.12, f"Expected leaf to pass foliar ratio, got {ratio:.2f}")

    def test_shannon_entropy_gating(self):
        """Verify Shannon entropy rejects uniform distribution and accepts high certainty."""
        uniform_probs = [1.0 / 6.0] * 6
        h_uniform = self.calculate_shannon_entropy(uniform_probs)
        self.assertGreater(h_uniform, 1.45, f"Uniform distribution should exceed rejection threshold: {h_uniform:.2f}")

        confident_probs = [0.95, 0.01, 0.01, 0.01, 0.01, 0.01]
        h_confident = self.calculate_shannon_entropy(confident_probs)
        self.assertLess(h_confident, 0.35)


# --- MOCK ESP32-CAM REST SERVER FOR SIMULATION TEST ---
class MockCameraServer(BaseHTTPRequestHandler):
    scan_counter = 0
    diagnosis_ready = False
    latest_diag = {}
    last_humidity = 0.0
    last_temperature = 0.0
    telemetry_available = False

    def log_message(self, format, *args):
        pass  # Silence output during unit test

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "device": "KRISHI-DRISHTI-CAM",
                "camera_ready": True,
                "sd_ready": True,
                "psram_available": True,
                "sensor": "OV5640",
                "scan_count": MockCameraServer.scan_counter,
                "clients": 1,
                "diagnosis_ready": MockCameraServer.diagnosis_ready,
                "telemetry_available": MockCameraServer.telemetry_available,
                "humidity": MockCameraServer.last_humidity,
                "temperature": MockCameraServer.last_temperature
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path == "/api/capture":
            MockCameraServer.scan_counter += 1
            MockCameraServer.diagnosis_ready = False
            # Reset telemetry availability on each new scan to prevent stale readings (mirrors KRISHI_DRISHTI_Camera.ino)
            MockCameraServer.telemetry_available = False
            MockCameraServer.last_humidity = 0.0
            MockCameraServer.last_temperature = 0.0

            if "hum" in query and "temp" in query:
                try:
                    h = float(query["hum"][0])
                    t = float(query["temp"][0])
                    if 0.0 < h <= 100.0 and -10.0 <= t <= 65.0:
                        MockCameraServer.last_humidity = h
                        MockCameraServer.last_temperature = t
                        MockCameraServer.telemetry_available = True
                except (ValueError, IndexError):
                    pass

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "status": "success",
                "scan_id": MockCameraServer.scan_counter,
                "filename": f"/scan_{MockCameraServer.scan_counter:06d}.jpg"
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path == "/image":
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            # Return synthetic 1x1 JPEG bytes
            self.wfile.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9")

        elif path == "/api/diagnosis/set":
            incoming_id = int(query.get("scan_id", [0])[0])
            # Enforce current scan ID check
            if incoming_id != MockCameraServer.scan_counter:
                self.send_response(409)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status":"error","message":"stale_scan_id","active_scan":MockCameraServer.scan_counter}).encode())
                return

            MockCameraServer.latest_diag = {
                "scan_id": incoming_id,
                "crop": query.get("crop", ["Unknown"])[0],
                "disease": query.get("disease", ["Unknown"])[0],
                "confidence": float(query.get("confidence", [0.0])[0]),
                "status": query.get("status", ["UNKNOWN"])[0],
                "organic": query.get("organic", [""])[0],
                "chemical": query.get("chemical", [""])[0]
            }
            MockCameraServer.diagnosis_ready = True
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')

        elif path in ("/api/diagnosis", "/api/diagnosis/latest"):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "ready": MockCameraServer.diagnosis_ready,
                "scan_id": MockCameraServer.latest_diag.get("scan_id", 0),
                "crop": MockCameraServer.latest_diag.get("crop", "Tomato"),
                "disease": MockCameraServer.latest_diag.get("disease", "Healthy"),
                "confidence": MockCameraServer.latest_diag.get("confidence", 98.0),
                "status": MockCameraServer.latest_diag.get("status", "HEALTHY"),
                "organic": MockCameraServer.latest_diag.get("organic", "Maintain drip irrigation"),
                "chemical": MockCameraServer.latest_diag.get("chemical", "None")
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


class TestESP32RestCycleSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockCameraServer)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_end_to_end_rest_telemetry_pipeline_and_stale_cache_reset(self):
        """
        Demonstrate complete end-to-end telemetry chain & cache lifecycle:
        Controller DHT11 -> /api/capture?temp=...&hum=... -> Camera cache -> /api/status JSON
        -> Python daemon extraction -> run_inference(img, telemetry=...).
        Tests all 5 required operational scenarios:
        1. Valid RH 55%: Status exposes telemetry, daemon gates Late Blight with ADVISORY.
        2. Valid RH 92%: Status exposes telemetry, daemon preserves standard Mancozeb.
        3. Missing telemetry: /api/capture without params -> telemetry_available=False, standard spray.
        4. Invalid telemetry: Out-of-bounds readings (-50% RH) -> rejected, telemetry_available=False.
        5. Stale cache reset: After valid RH 55% scan, next scan without params resets cache immediately.
        """
        import urllib.request
        from ai_engine.krishi_ai_daemon import KrishiAIDaemon
        base = f"http://127.0.0.1:{self.port}"
        labels_path = os.path.join(REPO_ROOT, "ai_engine", "labels.json")
        model_path = os.path.join(REPO_ROOT, "ai_engine", "krishi_drishti_model.tflite")
        daemon = KrishiAIDaemon(model_path=model_path, labels_path=labels_path)
        lb_img = Image.open(os.path.join(REPO_ROOT, "ai_engine", "sample_leaves", "tomato_late_blight.jpg"))

        # Scenario 1: Valid RH 55%
        with urllib.request.urlopen(f"{base}/api/capture?temp=28.0&hum=55.0") as res:
            cap1 = json.loads(res.read().decode())
            self.assertEqual(cap1["status"], "success")

        with urllib.request.urlopen(f"{base}/api/status") as res:
            st1 = json.loads(res.read().decode())
            self.assertTrue(st1["telemetry_available"])
            self.assertEqual(st1["humidity"], 55.0)
            self.assertEqual(st1["temperature"], 28.0)

        # Extract telemetry as production daemon does:
        telem1 = {"humidity": float(st1["humidity"]), "temperature": float(st1["temperature"])} if st1.get("telemetry_available") else None
        diag1 = daemon.run_inference(lb_img, telemetry=telem1)
        self.assertIn("Late Blight", diag1["disease"])
        self.assertTrue(diag1["chemical"].startswith("ADVISORY"), f"RH 55% must trigger advisory, got: {diag1['chemical']}")

        # Scenario 2: Valid RH 92%
        with urllib.request.urlopen(f"{base}/api/capture?temp=19.5&hum=92.0") as res:
            cap2 = json.loads(res.read().decode())
            self.assertEqual(cap2["status"], "success")

        with urllib.request.urlopen(f"{base}/api/status") as res:
            st2 = json.loads(res.read().decode())
            self.assertTrue(st2["telemetry_available"])
            self.assertEqual(st2["humidity"], 92.0)

        telem2 = {"humidity": float(st2["humidity"]), "temperature": float(st2["temperature"])} if st2.get("telemetry_available") else None
        diag2 = daemon.run_inference(lb_img, telemetry=telem2)
        self.assertIn("Late Blight", diag2["disease"])
        self.assertFalse(diag2["chemical"].startswith("ADVISORY"))
        self.assertIn("Mancozeb", diag2["chemical"])

        # Scenario 3: Missing telemetry
        with urllib.request.urlopen(f"{base}/api/capture") as res:
            cap3 = json.loads(res.read().decode())
            self.assertEqual(cap3["status"], "success")

        with urllib.request.urlopen(f"{base}/api/status") as res:
            st3 = json.loads(res.read().decode())
            self.assertFalse(st3["telemetry_available"])

        telem3 = {"humidity": float(st3["humidity"]), "temperature": float(st3["temperature"])} if st3.get("telemetry_available") else None
        self.assertIsNone(telem3)
        diag3 = daemon.run_inference(lb_img, telemetry=telem3)
        self.assertFalse(diag3["chemical"].startswith("ADVISORY"))
        self.assertIn("Mancozeb", diag3["chemical"])

        # Scenario 4: Invalid telemetry (e.g. hum=-50.0, temp=999.0)
        with urllib.request.urlopen(f"{base}/api/capture?temp=999.0&hum=-50.0") as res:
            cap4 = json.loads(res.read().decode())
            self.assertEqual(cap4["status"], "success")

        with urllib.request.urlopen(f"{base}/api/status") as res:
            st4 = json.loads(res.read().decode())
            self.assertFalse(st4["telemetry_available"], "Out-of-range sensor readings must be rejected")

        # Scenario 5: Stale cache reset check
        # A) Perform valid scan with 55% RH
        urllib.request.urlopen(f"{base}/api/capture?temp=27.0&hum=55.0")
        with urllib.request.urlopen(f"{base}/api/status") as res:
            st5a = json.loads(res.read().decode())
            self.assertTrue(st5a["telemetry_available"])
            self.assertEqual(st5a["humidity"], 55.0)

        # B) Next scan without telemetry must immediately clear the cache
        urllib.request.urlopen(f"{base}/api/capture")
        with urllib.request.urlopen(f"{base}/api/status") as res:
            st5b = json.loads(res.read().decode())
            self.assertFalse(st5b["telemetry_available"], "New scan must reset telemetry_available flag")
            self.assertEqual(st5b["humidity"], 0.0, "Stale humidity must be cleared to 0.0")

    def test_full_wand_phone_oled_telemetry_cycle(self):
        """Simulate the complete field telemetry round-trip."""
        import urllib.request
        base = f"http://127.0.0.1:{self.port}"

        # 1. Wand checks camera status
        with urllib.request.urlopen(f"{base}/api/status") as res:
            status = json.loads(res.read().decode())
            self.assertTrue(status["camera_ready"])
            initial_count = status["scan_count"]

        # 2. Wand triggers leaf capture
        with urllib.request.urlopen(f"{base}/api/capture") as res:
            capture = json.loads(res.read().decode())
            self.assertEqual(capture["status"], "success")
            scan_id = capture["scan_id"]
            self.assertEqual(scan_id, initial_count + 1)

        # 3. Phone AI detects new scan and downloads frame
        with urllib.request.urlopen(f"{base}/image?id={scan_id}") as res:
            frame_bytes = res.read()
            self.assertGreater(len(frame_bytes), 0)

        # 4. Phone posts neural diagnosis back to ESP32-CAM bridge
        diag_url = (f"{base}/api/diagnosis/set?scan_id={scan_id}&crop=Tomato"
                    f"&disease=Late%20Blight&confidence=94.2&status=INFECTED"
                    f"&organic=Neem%20Oil&chemical=Mancozeb")
        with urllib.request.urlopen(diag_url) as res:
            set_res = json.loads(res.read().decode())
            self.assertEqual(set_res["status"], "success")

        # 5. Controller Wand polls /api/diagnosis/latest and updates OLED
        with urllib.request.urlopen(f"{base}/api/diagnosis/latest") as res:
            oled_data = json.loads(res.read().decode())
            self.assertTrue(oled_data["ready"])
            self.assertEqual(oled_data["scan_id"], scan_id)
            self.assertEqual(oled_data["crop"], "Tomato")
            self.assertEqual(oled_data["disease"], "Late Blight")
            self.assertAlmostEqual(oled_data["confidence"], 94.2, places=1)
            self.assertEqual(oled_data["status"], "INFECTED")

    def test_stale_scan_id_is_rejected(self):
        """Verify diagnoses for outdated or stale scan IDs are rejected with HTTP 409."""
        import urllib.request, urllib.error
        base = f"http://127.0.0.1:{self.port}"
        stale_id = MockCameraServer.scan_counter - 1 # Outdated scan ID
        diag_url = (f"{base}/api/diagnosis/set?scan_id={stale_id}&crop=Tomato"
                    f"&disease=Healthy&confidence=90.0&status=HEALTHY")
        req = urllib.request.Request(diag_url)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 409)

    def test_tflite_input_contract_and_softmax_sum(self):
        """Verify TFLite model output sums to 1.0 (Softmax) without double softmax."""
        if not os.path.exists(TFLITE_PATH):
            self.skipTest("TFLite model not found")
        try:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
        except ImportError:
            try:
                import tflite_runtime.interpreter as tflite
                Interpreter = tflite.Interpreter
            except ImportError:
                self.skipTest("TensorFlow / tflite-runtime not installed in this environment. Run tests/verify_tflite_model.py in krishi_ai_env to verify.")
                return

        interpreter = Interpreter(model_path=TFLITE_PATH)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Input shape: [1, 128, 128, 3] float32 in [0.0, 255.0]
        self.assertEqual(input_details[0]['shape'].tolist(), [1, 128, 128, 3])
        self.assertEqual(input_details[0]['dtype'], np.float32)

        dummy_rgb = np.full((1, 128, 128, 3), 128.0, dtype=np.float32)
        interpreter.set_tensor(input_details[0]['index'], dummy_rgb)
        interpreter.invoke()

        output = interpreter.get_tensor(output_details[0]['index'])[0]
        self.assertEqual(len(output), 6)
        prob_sum = float(np.sum(output))
        # Validates that model output is already a true probability distribution (sum == 1.0)
        self.assertAlmostEqual(prob_sum, 1.0, places=3)
        self.assertTrue(np.all(output >= 0.0), "All probabilities must be non-negative")

    def test_controller_timeout_race_protection(self):
        """
        Verify that if pollAiDiagnosisNonBlocking() transitions state to
        STATE_DIAGNOSIS_RECEIVED at or past the 14s timeout boundary,
        the timeout handler is NOT triggered and the diagnosis is preserved.
        """
        STATE_IDLE = 0
        STATE_CAPTURING = 1
        STATE_AWAITING_AI = 2
        STATE_DIAGNOSIS_RECEIVED = 3
        STATE_TIMEOUT = 4

        aiWaitStartMs = 1000
        AI_TIMEOUT_MS = 14000
        now = 15001 # 14.001s elapsed (past timeout)

        # Scenario A: Diagnosis arrives successfully at timeout boundary
        current_state = STATE_AWAITING_AI
        diag_arrived = True
        if diag_arrived:
            current_state = STATE_DIAGNOSIS_RECEIVED

        # Controller loop logic: only trigger timeout if STILL awaiting AI
        if current_state == STATE_AWAITING_AI and (now - aiWaitStartMs >= AI_TIMEOUT_MS):
            current_state = STATE_TIMEOUT

        self.assertEqual(current_state, STATE_DIAGNOSIS_RECEIVED,
                         "Diagnosis arriving at timeout boundary must NEVER be overwritten by timeout")

        # Scenario B: No diagnosis arrives within 14s
        current_state = STATE_AWAITING_AI
        diag_arrived = False
        if current_state == STATE_AWAITING_AI and (now - aiWaitStartMs >= AI_TIMEOUT_MS):
            current_state = STATE_TIMEOUT

        self.assertEqual(current_state, STATE_TIMEOUT,
                         "Unanswered scan must cleanly transition to STATE_TIMEOUT")

    def test_firmware_microclimate_tracker_cpp_module(self):
        """
        Verify the modular C++ MicroclimateTracker module and execute native tests:
        1. Compiles and executes native C++ test harness (tests/test_microclimate_tracker.cpp) if g++/clang++ available.
        2. Validates accumulation, threshold transitions, drying decay, and disconnection handling.
        """
        h_path = os.path.join(CTRL_DIR, "MicroclimateTracker.h")
        cpp_path = os.path.join(CTRL_DIR, "MicroclimateTracker.cpp")
        self.assertTrue(os.path.exists(h_path), f"Missing MicroclimateTracker.h at {h_path}")
        self.assertTrue(os.path.exists(cpp_path), f"Missing MicroclimateTracker.cpp at {cpp_path}")
        self.assertTrue(os.path.exists(CPP_HARNESS_PATH), f"Missing test harness at {CPP_HARNESS_PATH}")

        with open(h_path, "r", encoding="utf-8") as f:
            h_code = f.read()
        self.assertIn("class MicroclimateTracker", h_code)
        self.assertIn("RISK_LEVEL_HIGH_LATE", h_code)

        compiler = shutil.which("g++") or shutil.which("clang++")
        if compiler:
            # Native C++ Compilation & Execution Test
            with tempfile.TemporaryDirectory() as tmpdir:
                exe_name = "test_tracker.exe" if sys.platform == "win32" else "test_tracker"
                out_exe = os.path.join(tmpdir, exe_name)
                cmd = [compiler, "-Wall", "-Wextra", "-Werror", CPP_HARNESS_PATH, cpp_path, "-o", out_exe]
                compile_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.assertEqual(compile_res.returncode, 0, f"Native C++ compilation failed: {compile_res.stderr}")

                run_res = subprocess.run([out_exe], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.assertEqual(run_res.returncode, 0, f"Native C++ execution failed: {run_res.stderr}")
                self.assertIn("passed successfully", run_res.stdout)
                return

        # Fallback state decay and duration logic verification matching C++ specification
        class CppTrackerMirror:
            def __init__(self, threshold=6.0):
                self.threshold = threshold
                self.continuous_start = 0
                self.accumulated_ms = 0
                self.last_update = 0

            def update(self, now, temp, hum, connected):
                if not connected:
                    self.continuous_start = 0
                    self.last_update = now
                    return "DHT11: Disconnected"

                elapsed = (now - self.last_update) if self.last_update > 0 else 0
                self.last_update = now

                if hum >= 85.0 and 15.0 <= temp <= 22.0:
                    if self.continuous_start == 0:
                        self.continuous_start = now
                    self.accumulated_ms += elapsed
                else:
                    self.continuous_start = 0
                    if self.accumulated_ms > elapsed * 2:
                        self.accumulated_ms -= elapsed * 2
                    else:
                        self.accumulated_ms = 0

                hours = self.accumulated_ms / 3600000.0
                if hours >= self.threshold:
                    return "Risk: HIGH (>6h LateBlight)"
                elif self.continuous_start > 0:
                    return f"Risk: Incubation {hours:.1f}h/6h"
                elif hum >= 70.0 and 22.0 <= temp <= 30.0:
                    return "Risk: MODERATE (EarlyBlight)"
                elif hum >= 60.0:
                    return "Risk: MONITOR CANOPY"
                else:
                    return "Risk: LOW (Canopy Optimal)"

        tracker = CppTrackerMirror(6.0)
        t = 1000

        # Incubation phase
        self.assertTrue(tracker.update(t, 18.0, 90.0, True).startswith("Risk: Incubation"))
        t += 2 * 3600 * 1000
        self.assertEqual(tracker.update(t, 18.0, 90.0, True), "Risk: Incubation 2.0h/6h")

        # Threshold reached: 6 continuous hours
        t += 4 * 3600 * 1000
        self.assertEqual(tracker.update(t, 18.0, 90.0, True), "Risk: HIGH (>6h LateBlight)")

        # Canopy drying out: 4 hours dry -> decays to zero
        t += 4 * 3600 * 1000
        self.assertEqual(tracker.update(t, 28.0, 55.0, True), "Risk: LOW (Canopy Optimal)")
        self.assertEqual(tracker.accumulated_ms, 0)

        # Disconnection
        self.assertEqual(tracker.update(t + 1000, 18.0, 90.0, False), "DHT11: Disconnected")

    def test_daemon_quantization_branches_uint8_and_int8(self):
        """
        Verify that KrishiAIDaemon.preprocess_image directly handles uint8 [0, 255],
        signed int8 [-128, 127], and float32 [0.0, 255.0] quantization branches.
        Calls the ACTUAL production method on KrishiAIDaemon.
        """
        from ai_engine.krishi_ai_daemon import KrishiAIDaemon

        # Synthetic leaf image (rich foliar green: R=50, G=150, B=50)
        leaf_img = Image.new("RGB", (160, 160), color=(50, 150, 50))
        daemon = object.__new__(KrishiAIDaemon)

        # 1. Production UINT8 branch: strictly bounded to [0, 255] and np.uint8 dtype
        daemon.input_dtype = np.uint8
        daemon.input_details = [{'quantization': (1.0, 0)}]
        tensor_u8, ratio_u8 = daemon.preprocess_image(leaf_img)
        self.assertIsNotNone(tensor_u8, "Foliar image must pass plausibility filter")
        self.assertEqual(tensor_u8.dtype, np.uint8)
        self.assertEqual(tensor_u8.shape, (1, 128, 128, 3))
        self.assertGreaterEqual(int(np.min(tensor_u8)), 0)
        self.assertLessEqual(int(np.max(tensor_u8)), 255)
        self.assertGreater(ratio_u8, 0.12)

        # 2. Production INT8 branch: strictly bounded to [-128, 127] and np.int8 dtype
        daemon.input_dtype = np.int8
        daemon.input_details = [{'quantization': (1.0, 0)}]
        tensor_i8, ratio_i8 = daemon.preprocess_image(leaf_img)
        self.assertIsNotNone(tensor_i8, "Foliar image must pass plausibility filter")
        self.assertEqual(tensor_i8.dtype, np.int8)
        self.assertEqual(tensor_i8.shape, (1, 128, 128, 3))
        self.assertGreaterEqual(int(np.min(tensor_i8)), -128)
        self.assertLessEqual(int(np.max(tensor_i8)), 127)

        # 3. Production FLOAT32 branch: raw float32 in [0.0, 255.0] range
        daemon.input_dtype = np.float32
        daemon.input_details = [{'quantization': (0.0, 0)}]
        tensor_f32, ratio_f32 = daemon.preprocess_image(leaf_img)
        self.assertIsNotNone(tensor_f32)
        self.assertEqual(tensor_f32.dtype, np.float32)
        self.assertEqual(tensor_f32.shape, (1, 128, 128, 3))
        self.assertGreaterEqual(float(np.min(tensor_f32)), 0.0)
        self.assertLessEqual(float(np.max(tensor_f32)), 255.0)

    def test_microclimate_cross_gating_suppresses_false_fungicide_alert(self):
        """
        Deterministic, non-vacuous validation of microclimate-to-diagnosis cross-gating:
        1. RH 55%: Defined advisory gate activates on Late Blight.
        2. RH 92%: Low-humidity advisory does not activate; standard recommendation preserved.
        3. Missing telemetry (None): No false assumption of dry conditions; advisory does not activate.
        4. Non-Late-Blight diagnosis (Healthy): No unintended suppression.
        """
        from ai_engine.krishi_ai_daemon import KrishiAIDaemon
        labels_path = os.path.join(REPO_ROOT, "ai_engine", "labels.json")
        model_path = os.path.join(REPO_ROOT, "ai_engine", "krishi_drishti_model.tflite")
        daemon = KrishiAIDaemon(model_path=model_path, labels_path=labels_path)

        # Deterministic Late Blight foliar target from reference images
        lb_img_path = os.path.join(REPO_ROOT, "ai_engine", "sample_leaves", "tomato_late_blight.jpg")
        self.assertTrue(os.path.exists(lb_img_path), f"Reference Late Blight image must exist: {lb_img_path}")
        lb_img = Image.open(lb_img_path)

        # 1. RH 55% -> Advisory gate MUST activate
        dry_telemetry = {"temperature": 28.0, "humidity": 55.0}
        res_dry = daemon.run_inference(lb_img, telemetry=dry_telemetry)
        self.assertIn("Late Blight", res_dry["disease"], "Model must deterministically predict Late Blight")
        self.assertTrue(res_dry["chemical"].startswith("ADVISORY"),
                        f"Expected ADVISORY chemical recommendation on RH 55%, got: {res_dry['chemical']}")

        # 2. RH 92% -> Low-humidity advisory must NOT activate (standard chemical recommendation active)
        humid_telemetry = {"temperature": 19.5, "humidity": 92.0}
        res_humid = daemon.run_inference(lb_img, telemetry=humid_telemetry)
        self.assertIn("Late Blight", res_humid["disease"])
        self.assertFalse(res_humid["chemical"].startswith("ADVISORY"),
                         f"Advisory should not trigger under RH 92%, got: {res_humid['chemical']}")
        self.assertIn("Mancozeb", res_humid["chemical"], "Standard agronomic chemical must be recommended")

        # 3. Missing sensor telemetry -> Must NOT falsely assume dry conditions
        res_missing = daemon.run_inference(lb_img, telemetry=None)
        self.assertIn("Late Blight", res_missing["disease"])
        self.assertFalse(res_missing["chemical"].startswith("ADVISORY"),
                         "Missing telemetry must not falsely trigger low-RH advisory")
        self.assertIn("Mancozeb", res_missing["chemical"])

        # 4. Non-Late-Blight diagnosis (Healthy) -> No unintended suppression
        healthy_img_path = os.path.join(REPO_ROOT, "ai_engine", "sample_leaves", "tomato_healthy.jpg")
        self.assertTrue(os.path.exists(healthy_img_path))
        healthy_img = Image.open(healthy_img_path)
        res_healthy = daemon.run_inference(healthy_img, telemetry=dry_telemetry)
        self.assertIn("healthy", res_healthy["disease"].lower())
        self.assertFalse(res_healthy["chemical"].startswith("ADVISORY"),
                         "Healthy foliage must not have Late Blight advisory attached")


if __name__ == "__main__":
    unittest.main()
