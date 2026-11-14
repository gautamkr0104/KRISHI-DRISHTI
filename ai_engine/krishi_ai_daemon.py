"""
KRISHI-DRISHTI: Headless Edge AI Co-Processor Daemon
-----------------------------------------------------
Author: Gautam Kumar / KRISHI-DRISHTI Project
Architecture: MobileNetV3 INT8 Quantized Interpreter Daemon
Execution Environment: Samsung Galaxy A03 (Termux / Android Python / Local Edge)
Operation: 100% Offline over Local Wi-Fi Mesh (SoftAP: KRISHI-DRISHTI @ 192.168.4.1)
"""

import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.parse
from PIL import Image
import numpy as np

# Load TFLite interpreter from tflite_runtime or tensorflow
tflite = None
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    try:
        import tensorflow.lite as tflite
    except ImportError:
        tflite = None

IMAGE_SIZE = (128, 128)
DEFAULT_CAMERA_IP = "192.168.4.1"
DEFAULT_POLL_INTERVAL = 1.0

# Uncertainty Rejection Thresholds (round-2 calibrated on 44 real ESP32-CAM SD scans)
MIN_CONFIDENCE_THRESHOLD = 0.50  # 50% minimum top-1 probability
MAX_ENTROPY_THRESHOLD = 1.20     # Maximum Shannon entropy for decisive classification
MIN_FOLIAR_RATIO = 0.21          # Reject images with virtually no leaf tissue (faces/palms/vignettes/ceilings);
                                 # round-2 calibrated: sits above face_selfie (0.204), below valid PV specimens (0.233+)
MIN_DECISION_MARGIN = 0.12       # Minimum top1-top2 probability margin (rejects ambiguous / OOD species)
MAX_DARK_FRACTION = 0.35         # Rejects frames with >35% peripheral dark void (unshielded night flash / off-center leaf)

def load_labels(labels_path):
    with open(labels_path, "r", encoding="utf-8") as f:
        return json.load(f)

class KrishiAIDaemon:
    def __init__(self, model_path, labels_path, camera_ip=DEFAULT_CAMERA_IP, poll_interval=DEFAULT_POLL_INTERVAL):
        self.camera_ip = camera_ip
        self.poll_interval = poll_interval
        self.labels = load_labels(labels_path)
        
        if tflite is None:
            raise ImportError("Neither tflite_runtime nor tensorflow is installed. Install tflite-runtime or tensorflow to run KrishiAIDaemon inference.")
        print(f"\n[AI DAEMON] Loading quantized TFLite model: {model_path}...")
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        self.input_shape = self.input_details[0]['shape']
        self.input_dtype = self.input_details[0]['dtype']
        print(f"[AI DAEMON] Model initialized! Input: {self.input_shape}, Dtype: {self.input_dtype}")
        
        self.last_processed_scan = 0
        self.is_running = True

    def preprocess_image(self, pil_img):
        """
        Resizes to 128x128. Model contains internal mobilenet_v3.preprocess_input layer,
        so input contract is raw float32 in [0.0, 255.0] range (identical to browser engine).
        """
        img = pil_img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
        arr = np.array(img, dtype=np.float32)
        
        # Check foliar plausibility (reject lens cap, black frame, all-white surface)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        is_foliar = ((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))
        foliar_ratio = float(np.mean(is_foliar))
        
        # Check peripheral dark void fraction (unshielded night flash / off-center leaf)
        dark_fraction = float(np.mean((r < 35) & (g < 35) & (b < 35)))
        if dark_fraction > MAX_DARK_FRACTION:
            return None, foliar_ratio
            
        if foliar_ratio < MIN_FOLIAR_RATIO:
            return None, foliar_ratio
        
        if self.input_dtype == np.uint8:
            # Unsigned 8-bit quantized inputs: range [0, 255]
            scale, zero_point = self.input_details[0].get('quantization', (1.0, 0))
            if scale > 0:
                tensor_data = np.clip(np.round(arr / scale) + zero_point, 0, 255).astype(np.uint8)
            else:
                tensor_data = np.clip(np.round(arr), 0, 255).astype(np.uint8)
        elif self.input_dtype == np.int8:
            # Signed 8-bit quantized inputs: range [-128, 127]
            scale, zero_point = self.input_details[0].get('quantization', (1.0, 0))
            if scale > 0:
                tensor_data = np.clip(np.round(arr / scale) + zero_point, -128, 127).astype(np.int8)
            else:
                tensor_data = np.clip(np.round(arr - 128.0), -128, 127).astype(np.int8)
        else:
            # Float32 model contract: raw [0.0, 255.0] pixels
            tensor_data = arr.astype(np.float32)
            
        tensor = np.expand_dims(tensor_data, axis=0)
        return tensor, foliar_ratio

    def run_inference(self, pil_img, telemetry=None):
        """
        Runs genuine inference and returns real probabilities, confidence, and uncertainty flags.
        Zero Math.random() or simulated numbers.
        """
        t0 = time.perf_counter()
        tensor, foliar_ratio = self.preprocess_image(pil_img)
        
        if tensor is None:
            img = pil_img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
            arr = np.array(img, dtype=np.float32)
            dark_frac = float(np.mean((arr[:, :, 0] < 35) & (arr[:, :, 1] < 35) & (arr[:, :, 2] < 35)))
            if dark_frac > MAX_DARK_FRACTION:
                return {
                    "crop": "Unknown",
                    "disease": "Framing / Void Detected",
                    "pathogen": f"Excessive peripheral dark void ({dark_frac*100:.1f}%). Leaf must be centered in optical shroud.",
                    "confidence": 0.0,
                    "status": "UNCERTAIN",
                    "organic": "Center camera wand shroud directly over leaf surface",
                    "chemical": "Ensure optical shroud blocks peripheral background",
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "probabilities": []
                }
            return {
                "crop": "Unknown",
                "disease": "No Leaf Detected",
                "pathogen": "Insufficient foliar tissue in frame",
                "confidence": 0.0,
                "status": "UNCERTAIN",
                "organic": "Aim camera lens squarely at leaf surface",
                "chemical": "Ensure good ambient daylight",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "probabilities": []
            }
        
        self.interpreter.set_tensor(self.input_details[0]['index'], tensor)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        
        # Dequantize output if int8/uint8
        out_scale, out_zero = self.output_details[0].get('quantization', (1.0, 0))
        if out_scale > 0 and output_data.dtype != np.float32:
            probs = (output_data.astype(np.float32) - out_zero) * out_scale
        else:
            probs = output_data.astype(np.float32)
            
        # Ensure proper probability distribution via softmax if logits
        if np.any(probs < 0.0) or np.abs(np.sum(probs) - 1.0) > 0.05:
            exp_p = np.exp(probs - np.max(probs))
            probs = exp_p / np.sum(exp_p)
            
        latency = round((time.perf_counter() - t0) * 1000, 2)
        
        max_idx = int(np.argmax(probs))
        max_prob = float(probs[max_idx])
        conf_percent = round(max_prob * 100.0, 1)
        
        # Shannon entropy and decision margin calculation
        sorted_probs = np.sort(probs)[::-1]
        top1 = float(sorted_probs[0])
        top2 = float(sorted_probs[1]) if len(sorted_probs) > 1 else 0.0
        margin = top1 - top2
        entropy = -float(np.sum([p * np.log(p) for p in probs if p > 1e-6]))
        
        # Uncertainty and Unknown Image Gate (Confidence, Entropy, and Decision Margin)
        if max_prob < MIN_CONFIDENCE_THRESHOLD or entropy > MAX_ENTROPY_THRESHOLD or margin < MIN_DECISION_MARGIN:
            return {
                "crop": "Solanaceae",
                "disease": "Uncertain / Ambiguous",
                "pathogen": f"Low classification certainty (Entropy: {entropy:.2f}, Margin: {margin*100:.1f}%)",
                "confidence": conf_percent,
                "status": "UNCERTAIN",
                "organic": "Retake photo with steady focus and center leaf in shroud",
                "chemical": "Microclimate monitoring advised; avoid premature chemical spraying",
                "latency_ms": latency,
                "probabilities": [round(float(p), 4) for p in probs],
                "entropy": round(entropy, 3),
                "margin": round(margin, 3)
            }
            
        matched = self.labels[max_idx]
        chem_rec = matched["chemical"]

        # Microclimate-to-Diagnosis Cross-Gating:
        # Phytophthora infestans (Late Blight) physically requires high sustained
        # relative humidity (RH >= 85%) to produce viable sporangia.
        # If telemetry shows dry canopy (RH < 85%), suppress chemical fungicide recommendation.
        if "Late Blight" in matched["disease"] and telemetry:
            hum = telemetry.get("humidity", 0.0)
            if hum > 0.0 and hum < 85.0:
                chem_rec = f"ADVISORY: Low RH ({hum:.0f}%). Late Blight sporulation favors sustained high RH (>=85%). Low current microclimate risk; verify foliar symptoms before spraying."

        return {
            "crop": matched["crop"],
            "disease": matched["disease"],
            "pathogen": matched["pathogen"],
            "confidence": conf_percent,
            "status": matched["severity"],
            "organic": matched["organic"],
            "chemical": chem_rec,
            "latency_ms": latency,
            "probabilities": [round(float(p), 4) for p in probs]
        }

    def fetch_camera_status(self):
        url = f"http://{self.camera_ip}/api/status"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KRISHI-AI-Daemon"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except Exception:
            return None
        return None

    def fetch_leaf_image(self, scan_id):
        url = f"http://{self.camera_ip}/image?id={scan_id}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KRISHI-AI-Daemon"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return Image.open(resp)
        except Exception as e:
            print(f"[!] Failed to fetch image for Scan #{scan_id}: {e}")
            return None
        return None

    def post_diagnosis(self, scan_id, diag):
        url = f"http://{self.camera_ip}/api/diagnosis/set"
        params = {
            "scan_id": scan_id,
            "crop": diag["crop"],
            "disease": diag["disease"],
            "confidence": diag["confidence"],
            "status": diag["status"],
            "organic": diag["organic"],
            "chemical": diag["chemical"]
        }
        query_str = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_str}"
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "KRISHI-AI-Daemon"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[!] Failed to beam diagnosis to camera: {e}")
            return False

    def start_polling(self):
        print(f"\n[AI DAEMON] Listening for scan events from Camera SoftAP at http://{self.camera_ip}/...")
        print("  Keep phone in pocket or screen active with WakeLock.")
        
        while self.is_running:
            try:
                status = self.fetch_camera_status()
                if status and status.get("camera_ready"):
                    scan_count = status.get("scan_count", 0)
                    if scan_count > self.last_processed_scan:
                        print(f"\n[EVENT] New scan detected: #{scan_count}! Pulling image...")
                        img = self.fetch_leaf_image(scan_count)
                        if img:
                            print(f"[INFERENCE] Running TFLite on Scan #{scan_count} ({img.size[0]}x{img.size[1]})...")
                            # Extract genuine live canopy telemetry from Camera SoftAP bridge
                            live_telemetry = None
                            if status.get("telemetry_available") and "humidity" in status:
                                live_telemetry = {
                                    "humidity": float(status["humidity"]),
                                    "temperature": float(status.get("temperature", 0.0))
                                }
                                print(f"[TELEMETRY] Live wand canopy readings: {live_telemetry['temperature']}C, {live_telemetry['humidity']}% RH")
                            else:
                                print("[TELEMETRY] Sensor telemetry unavailable from wand; bypassing microclimate gate.")
                            diag = self.run_inference(img, telemetry=live_telemetry)
                            print(f"[RESULT] {diag['crop']} - {diag['disease']} ({diag['confidence']}%) in {diag['latency_ms']} ms")
                            
                            ok = self.post_diagnosis(scan_count, diag)
                            if ok:
                                print(f"[SYNC] Diagnosis successfully synced to Camera bridge for OLED wand.")
                                self.last_processed_scan = scan_count
                            else:
                                print(f"[!] Diagnosis sync failed.")
                        else:
                            print(f"[!] Could not retrieve image for Scan #{scan_count}")
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                print("\n[AI DAEMON] Shutting down...")
                break
            except Exception as e:
                time.sleep(self.poll_interval)

def main():
    parser = argparse.ArgumentParser(description="KRISHI-DRISHTI Headless AI Daemon")
    parser.add_argument("--model", type=str, default="krishi_drishti_model.tflite")
    parser.add_argument("--labels", type=str, default="labels.json")
    parser.add_argument("--camera_ip", type=str, default=DEFAULT_CAMERA_IP)
    parser.add_argument("--test_image", type=str, default=None, help="Run single test inference on an image file")
    args = parser.parse_args()

    daemon = KrishiAIDaemon(args.model, args.labels, args.camera_ip)

    if args.test_image:
        print(f"\n[TEST] Running inference on image: {args.test_image}...")
        img = Image.open(args.test_image)
        res = daemon.run_inference(img)
        print(json.dumps(res, indent=2))
        return

    daemon.start_polling()

if __name__ == "__main__":
    main()
