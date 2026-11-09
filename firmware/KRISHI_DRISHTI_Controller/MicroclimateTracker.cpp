#include "MicroclimateTracker.h"
#include <stdio.h>

MicroclimateTracker::MicroclimateTracker(float riskHoursThreshold)
  : riskHoursThreshold(riskHoursThreshold),
    highRiskContinuousStartMs(0),
    highRiskAccumulatedMs(0),
    lastRiskUpdateMs(0),
    riskHoursAccumulated(0.0f),
    currentRiskLevel(RISK_LEVEL_LOW) {
  statusBuffer[0] = '\0';
}

void MicroclimateTracker::reset() {
  highRiskContinuousStartMs = 0;
  highRiskAccumulatedMs = 0;
  lastRiskUpdateMs = 0;
  riskHoursAccumulated = 0.0f;
  currentRiskLevel = RISK_LEVEL_LOW;
  statusBuffer[0] = '\0';
}

MicroclimateRiskLevel MicroclimateTracker::update(uint32_t nowMs, float tempC, float humPct, bool sensorConnected) {
  if (!sensorConnected) {
    highRiskContinuousStartMs = 0;
    lastRiskUpdateMs = nowMs;
    currentRiskLevel = RISK_LEVEL_DISCONNECTED;
    snprintf(statusBuffer, sizeof(statusBuffer), "DHT11: Disconnected");
    return currentRiskLevel;
  }

  uint32_t elapsed = (lastRiskUpdateMs > 0 && nowMs >= lastRiskUpdateMs) ? (nowMs - lastRiskUpdateMs) : 0;
  lastRiskUpdateMs = nowMs;

  // Epidemiological Microclimate Rule for Late Blight (Phytophthora infestans):
  // Favorable foliar sporulation requires relative humidity >= 85% and temperature 15°C to 22°C.
  if (humPct >= 85.0f && tempC >= 15.0f && tempC <= 22.0f) {
    if (highRiskContinuousStartMs == 0) {
      highRiskContinuousStartMs = nowMs;
    }
    highRiskAccumulatedMs += elapsed;
  } else {
    // Favorable conditions broken: canopy is drying out
    highRiskContinuousStartMs = 0;
    // Gradual decay (drying rate): decays accumulated exposure twice as fast as accumulation
    if (highRiskAccumulatedMs > elapsed * 2) {
      highRiskAccumulatedMs -= elapsed * 2;
    } else {
      highRiskAccumulatedMs = 0;
    }
  }

  riskHoursAccumulated = (float)highRiskAccumulatedMs / 3600000.0f;

  if (riskHoursAccumulated >= riskHoursThreshold) {
    currentRiskLevel = RISK_LEVEL_HIGH_LATE;
    snprintf(statusBuffer, sizeof(statusBuffer), "Risk: HIGH (>6h LateBlight)");
  } else if (highRiskContinuousStartMs > 0) {
    currentRiskLevel = RISK_LEVEL_INCUBATING_LATE;
    snprintf(statusBuffer, sizeof(statusBuffer), "Risk: Incubation %.1fh/6h", riskHoursAccumulated);
  } else if (humPct >= 70.0f && tempC >= 22.0f && tempC <= 30.0f) {
    currentRiskLevel = RISK_LEVEL_MODERATE_EARLY;
    snprintf(statusBuffer, sizeof(statusBuffer), "Risk: MODERATE (EarlyBlight)");
  } else if (humPct >= 60.0f) {
    currentRiskLevel = RISK_LEVEL_MONITOR;
    snprintf(statusBuffer, sizeof(statusBuffer), "Risk: MONITOR CANOPY");
  } else {
    currentRiskLevel = RISK_LEVEL_LOW;
    snprintf(statusBuffer, sizeof(statusBuffer), "Risk: LOW (Canopy Optimal)");
  }

  return currentRiskLevel;
}

const char* MicroclimateTracker::getRiskStatusString() const {
  return statusBuffer;
}
