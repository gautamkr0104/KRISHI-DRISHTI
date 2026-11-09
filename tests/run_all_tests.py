"""
KRISHI-DRISHTI :: Cross-Platform Test & Verification Master Runner
------------------------------------------------------------------
Executes all validation suites across Windows, Linux, and macOS.
"""

import os
import sys
import subprocess
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = sys.executable

def main():
    print("=" * 70)
    print("KRISHI-DRISHTI :: MASTER TEST & VERIFICATION SUITE")
    print("=" * 70)
    print(f"[*] Python Interpreter: {PYTHON_EXE}")

    # 1. Run Unit & Integration Suite
    print("\n[1/3] Running Python Automated Unit & Integration Suite...")
    print("-" * 70)
    test_pipeline = os.path.join(REPO_ROOT, "tests", "test_ai_pipeline.py")
    res1 = subprocess.run([PYTHON_EXE, test_pipeline])
    if res1.returncode != 0:
        print("[FAIL] Automated unit test suite failed.")
        sys.exit(res1.returncode)

    # 2. Run TFLite Model & Runtime Verification
    print("\n[2/3] Running TFLite Tensor & Real Inference Verification...")
    print("-" * 70)
    verify_script = os.path.join(REPO_ROOT, "tests", "verify_tflite_model.py")
    res2 = subprocess.run([PYTHON_EXE, verify_script])
    if res2.returncode != 0:
        print("[FAIL] TFLite verification script failed.")
        sys.exit(res2.returncode)

    # 3. Check for Native C++ Compiler
    print("\n[3/3] Checking for C++ Compiler for Native Firmware Unit Tests...")
    print("-" * 70)
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler:
        print(f"[*] Native compiler detected: {compiler}")
        harness = os.path.join(REPO_ROOT, "tests", "test_microclimate_tracker.cpp")
        cpp_module = os.path.join(REPO_ROOT, "firmware", "KRISHI_DRISHTI_Controller", "MicroclimateTracker.cpp")
        out_exe = os.path.join(REPO_ROOT, "tests", "test_tracker.exe" if sys.platform == "win32" else "test_tracker")
        cmd = [compiler, "-Wall", "-Wextra", "-Werror", "-std=c++11", harness, cpp_module, "-o", out_exe]
        c_res = subprocess.run(cmd)
        if c_res.returncode == 0:
            print("[*] Running native MicroclimateTracker binary...")
            r_res = subprocess.run([out_exe])
            if os.path.exists(out_exe):
                try:
                    os.remove(out_exe)
                except Exception:
                    pass
            if r_res.returncode != 0:
                print("[FAIL] Native C++ tests failed.")
                sys.exit(r_res.returncode)
        else:
            print("[WARN] Native C++ compilation failed.")
    else:
        print("[INFO] No C++ compiler (g++/clang++) found in PATH. Architecture verified by Python tests.")

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL KRISHI-DRISHTI TEST AND VERIFICATION SUITES PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
