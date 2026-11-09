/**
 * KRISHI-DRISHTI :: Native C++ Unit Test Harness for MicroclimateTracker
 * ----------------------------------------------------------------------
 * Compiles cleanly with:
 *   g++ -Wall -Wextra -Werror -std=c++11 \
 *       tests/test_microclimate_tracker.cpp \
 *       firmware/KRISHI_DRISHTI_Controller/MicroclimateTracker.cpp \
 *       -o test_tracker
 *
 * Validates:
 * 1. Initial baseline state
 * 2. Incubation accumulation under Late Blight microclimate (RH >= 85%, 15C-22C)
 * 3. Epidemiological 6-hour threshold triggering RISK_LEVEL_HIGH_LATE
 * 4. Dual-rate drying decay when canopy RH drops below threshold
 * 5. Sensor disconnection handling and continuous timer reset
 * 6. Moderate Early Blight and canopy monitoring threshold classifications
 */

#include <iostream>
#include <cassert>
#include <cmath>
#include <cstring>
#include "../firmware/KRISHI_DRISHTI_Controller/MicroclimateTracker.h"

static int g_tests_run = 0;
static int g_tests_passed = 0;

#define ASSERT_TEST(cond, msg) \
    do { \
        g_tests_run++; \
        if (!(cond)) { \
            std::cerr << "[FAIL] Line " << __LINE__ << ": " << msg << std::endl; \
            return 1; \
        } else { \
            g_tests_passed++; \
        } \
    } while(0)

int main() {
    std::cout << "=== Running KRISHI-DRISHTI MicroclimateTracker Native C++ Tests ===" << std::endl;

    // 1. Initial Baseline Test
    {
        MicroclimateTracker tracker(6.0f);
        ASSERT_TEST(tracker.getRiskLevel() == RISK_LEVEL_LOW, "Initial risk level must be LOW");
        ASSERT_TEST(tracker.getAccumulatedHours() == 0.0f, "Initial accumulated hours must be 0.0");
        ASSERT_TEST(tracker.getThresholdHours() == 6.0f, "Threshold hours must be 6.0");
        ASSERT_TEST(!tracker.isFavorableConditionActive(), "Favorable condition must not be active initially");
    }

    // 2. Incubation and Accumulation Test
    {
        MicroclimateTracker tracker(6.0f);
        uint32_t t = 1000;

        // First tick under Late Blight microclimate: 18C, 90% RH
        MicroclimateRiskLevel r1 = tracker.update(t, 18.0f, 90.0f, true);
        ASSERT_TEST(r1 == RISK_LEVEL_INCUBATING_LATE, "First tick in favorable conditions must enter INCUBATING_LATE");
        ASSERT_TEST(tracker.isFavorableConditionActive(), "Favorable condition must be active");

        // Advance 2 hours (2 * 3600 * 1000 = 7,200,000 ms)
        t += 7200000;
        MicroclimateRiskLevel r2 = tracker.update(t, 18.0f, 90.0f, true);
        ASSERT_TEST(r2 == RISK_LEVEL_INCUBATING_LATE, "2 hours in favorable conditions must still be INCUBATING_LATE");
        float hours = tracker.getAccumulatedHours();
        ASSERT_TEST(std::fabs(hours - 2.0f) < 0.01f, "Accumulated hours after 2 hours must be ~2.0h");
        ASSERT_TEST(strstr(tracker.getRiskStatusString(), "Risk: Incubation 2.0h/6h") != nullptr,
                    "Status string must format incubation progress");

        // Advance another 4 hours (total 6 hours accumulated)
        t += 14400000;
        MicroclimateRiskLevel r3 = tracker.update(t, 18.0f, 90.0f, true);
        ASSERT_TEST(r3 == RISK_LEVEL_HIGH_LATE, "6 hours continuous accumulated exposure must trigger HIGH_LATE");
        ASSERT_TEST(std::fabs(tracker.getAccumulatedHours() - 6.0f) < 0.01f, "Accumulated hours must be ~6.0h");
        ASSERT_TEST(strcmp(tracker.getRiskStatusString(), "Risk: HIGH (>6h LateBlight)") == 0,
                    "Status string must state 'Risk: HIGH (>6h LateBlight)'");
    }

    // 3. Proportional Drying Decay Test (Canopy drying out)
    {
        MicroclimateTracker tracker(6.0f);
        uint32_t t = 1000;
        tracker.update(t, 18.0f, 90.0f, true);
        // Accumulate 2 hours
        t += 7200000;
        tracker.update(t, 18.0f, 90.0f, true);
        ASSERT_TEST(std::fabs(tracker.getAccumulatedHours() - 2.0f) < 0.01f, "Must have 2.0h accumulated");

        // Canopy dries out: 28C, 50% RH.
        // Drying decay rate is 2x elapsed duration.
        // 1 hour dry interval should decay 2 hours of accumulation to 0.
        t += 3600000;
        MicroclimateRiskLevel r_dry = tracker.update(t, 28.0f, 50.0f, true);
        ASSERT_TEST(r_dry == RISK_LEVEL_LOW, "After 1 hour drying at 2x decay, 2h accumulation decays to 0 -> LOW");
        ASSERT_TEST(tracker.getAccumulatedHours() == 0.0f, "Accumulated hours must decay to 0.0");
        ASSERT_TEST(!tracker.isFavorableConditionActive(), "Favorable condition must be inactive after drying");
    }

    // 4. Sensor Disconnection Handling Test
    {
        MicroclimateTracker tracker(6.0f);
        uint32_t t = 1000;
        tracker.update(t, 18.0f, 90.0f, true);
        t += 3600000; // 1 hour accumulated
        tracker.update(t, 18.0f, 90.0f, true);

        // Sensor disconnects
        t += 1000;
        MicroclimateRiskLevel r_disc = tracker.update(t, 0.0f, 0.0f, false);
        ASSERT_TEST(r_disc == RISK_LEVEL_DISCONNECTED, "Disconnected sensor must return RISK_LEVEL_DISCONNECTED");
        ASSERT_TEST(strcmp(tracker.getRiskStatusString(), "DHT11: Disconnected") == 0,
                    "Status string must indicate 'DHT11: Disconnected'");
        ASSERT_TEST(!tracker.isFavorableConditionActive(), "Continuous start must be reset upon disconnection");
    }

    // 5. Early Blight Moderate Condition (22C-30C, RH >= 70%)
    {
        MicroclimateTracker tracker(6.0f);
        MicroclimateRiskLevel r_early = tracker.update(1000, 26.0f, 75.0f, true);
        ASSERT_TEST(r_early == RISK_LEVEL_MODERATE_EARLY, "26C and 75% RH must trigger MODERATE_EARLY");
        ASSERT_TEST(strcmp(tracker.getRiskStatusString(), "Risk: MODERATE (EarlyBlight)") == 0,
                    "Status string must state 'Risk: MODERATE (EarlyBlight)'");
    }

    // 6. Canopy Monitoring Condition (RH >= 60%)
    {
        MicroclimateTracker tracker(6.0f);
        MicroclimateRiskLevel r_mon = tracker.update(1000, 28.0f, 65.0f, true);
        ASSERT_TEST(r_mon == RISK_LEVEL_MONITOR, "28C and 65% RH must trigger MONITOR");
        ASSERT_TEST(strcmp(tracker.getRiskStatusString(), "Risk: MONITOR CANOPY") == 0,
                    "Status string must state 'Risk: MONITOR CANOPY'");
    }

    std::cout << "[PASS] All " << g_tests_passed << "/" << g_tests_run
              << " native C++ MicroclimateTracker tests passed successfully!" << std::endl;
    return 0;
}
