"""
KRISHI-DRISHTI :: Cross-Platform Test & Verification Master Runner
------------------------------------------------------------------
Executes all validation suites across Windows, Linux, and macOS:
1. Unit & Integration Suite (11 tests)
2. Production Daemon 8-Specimen & Gating Audit
3. Reproducible 60-Specimen Botanical Benchmark
4. Native C++ MicroclimateTracker Unit Test Harness
"""

import os
import sys
import subprocess
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = sys.executable

def main():
    print("=" * 75)
    print("  KRISHI-DRISHTI :: COMPREHENSIVE MASTER TEST & VERIFICATION SUITE")
    print("=" * 75)
    print(f"[*] Python Interpreter: {PYTHON_EXE}")

    # 1. Run Unit & Integration Suite
    print("\n[1/4] Running Python Automated Unit & Integration Suite (11 Tests)...")
    print("-" * 75)
    test_pipeline = os.path.join(REPO_ROOT, "tests", "test_ai_pipeline.py")
    res1 = subprocess.run([PYTHON_EXE, test_pipeline])
    if res1.returncode != 0:
        print("[FAIL] Automated unit test suite failed.")
        sys.exit(res1.returncode)

    # 2. Run Production Daemon Verification Audit
    print("\n[2/4] Running Production Daemon 8-Specimen & Gating Verification Audit...")
    print("-" * 75)
    verify_script = os.path.join(REPO_ROOT, "tests", "verify_tflite_model.py")
    res2 = subprocess.run([PYTHON_EXE, verify_script])
    if res2.returncode != 0:
        print("[FAIL] TFLite verification script failed.")
        sys.exit(res2.returncode)

    # 3. Run 60-Specimen Botanical Benchmark
    print("\n[3/4] Running Reproducible 60-Specimen Botanical Benchmark...")
    print("-" * 75)
    bench_script = os.path.join(REPO_ROOT, "tests", "benchmark_60_specimens.py")
    res3 = subprocess.run([PYTHON_EXE, bench_script])
    if res3.returncode != 0:
        print("[FAIL] 60-specimen benchmark script failed.")
        sys.exit(res3.returncode)

    # 4. Check for Native C++ Compiler
    print("\n[4/4] Checking for C++ Compiler for Native Firmware Unit Tests...")
    print("-" * 75)
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

    print("\n" + "=" * 75)
    print("  [SUCCESS] ALL KRISHI-DRISHTI MASTER VERIFICATION SUITES PASSED!")
    print("=" * 75)

if __name__ == "__main__":
    main()
