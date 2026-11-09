#ifndef MICROCLIMATE_TRACKER_H
#define MICROCLIMATE_TRACKER_H

#include <stdint.h>
#include <stdbool.h>

/**
 * KRISHI-DRISHTI :: Modular Microclimate Duration & Risk Tracker
 * -------------------------------------------------------------
 * Platform-independent C++ state tracker for agricultural epidemiology.
 * 
 * Accurately tracks accumulated hours of foliar disease-favorable microclimate
 * (relative humidity >= 85% and temperature 15°C to 22°C for Phytophthora infestans)
 * with proportional drying-decay to prevent false accumulation across dry intervals.
 */

enum MicroclimateRiskLevel {
  RISK_LEVEL_DISCONNECTED = 0,
  RISK_LEVEL_LOW,
  RISK_LEVEL_MONITOR,
  RISK_LEVEL_MODERATE_EARLY,
  RISK_LEVEL_INCUBATING_LATE,
  RISK_LEVEL_HIGH_LATE
};

class MicroclimateTracker {
public:
  MicroclimateTracker(float riskHoursThreshold = 6.0f);

  // Updates the tracker state with current timestamp (ms) and sensor telemetry.
  MicroclimateRiskLevel update(uint32_t nowMs, float tempC, float humPct, bool sensorConnected);

  // State management
  void reset();

  // Telemetry inspection
  MicroclimateRiskLevel getRiskLevel() const { return currentRiskLevel; }
  float getAccumulatedHours() const { return riskHoursAccumulated; }
  float getThresholdHours() const { return riskHoursThreshold; }
  bool isFavorableConditionActive() const { return highRiskContinuousStartMs > 0; }
  
  // Format human-readable status string for OLED display (fits 128x64 SSD1306)
  const char* getRiskStatusString() const;

private:
  float riskHoursThreshold;
  uint32_t highRiskContinuousStartMs;
  uint32_t highRiskAccumulatedMs;
  uint32_t lastRiskUpdateMs;
  float riskHoursAccumulated;
  MicroclimateRiskLevel currentRiskLevel;
  char statusBuffer[32];
};

#endif // MICROCLIMATE_TRACKER_H
