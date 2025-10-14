/**
 * Telemetry display component
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { TelemetryData } from '../types';

interface TelemetryDisplayProps {
  data: TelemetryData;
  style?: any;
}

export const TelemetryDisplay: React.FC<TelemetryDisplayProps> = ({
  data,
  style,
}) => {
  const formatValue = (value: number, unit: string, decimals: number = 1) => {
    return `${value.toFixed(decimals)}${unit}`;
  };

  const getQualityColor = (value: number, thresholds: { good: number; warning: number }) => {
    if (value <= thresholds.good) return '#27AE60';
    if (value <= thresholds.warning) return '#F39C12';
    return '#E74C3C';
  };

  const getRTTColor = (rtt: number) => {
    return getQualityColor(rtt, { good: 200, warning: 400 });
  };

  const getPacketLossColor = (loss: number) => {
    return getQualityColor(loss, { good: 1, warning: 5 });
  };

  const getJitterColor = (jitter: number) => {
    return getQualityColor(jitter, { good: 20, warning: 50 });
  };

  const getBatteryColor = (level: number) => {
    if (level > 50) return '#27AE60';
    if (level > 20) return '#F39C12';
    return '#E74C3C';
  };

  const getThermalColor = (state: string) => {
    switch (state) {
      case 'normal': return '#27AE60';
      case 'fair': return '#F39C12';
      case 'serious': return '#E74C3C';
      case 'critical': return '#8E44AD';
      default: return '#95A5A6';
    }
  };

  return (
    <View style={[styles.container, style]}>
      <Text style={styles.title}>Telemetry</Text>
      
      <View style={styles.grid}>
        {/* Network metrics */}
        <View style={styles.metricGroup}>
          <Text style={styles.groupTitle}>Network</Text>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>RTT</Text>
            <Text style={[styles.metricValue, { color: getRTTColor(data.rttMs) }]}>
              {formatValue(data.rttMs, 'ms')}
            </Text>
          </View>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Packet Loss</Text>
            <Text style={[styles.metricValue, { color: getPacketLossColor(data.packetLossPercent) }]}>
              {formatValue(data.packetLossPercent, '%')}
            </Text>
          </View>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Jitter</Text>
            <Text style={[styles.metricValue, { color: getJitterColor(data.jitterMs) }]}>
              {formatValue(data.jitterMs, 'ms')}
            </Text>
          </View>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Bitrate</Text>
            <Text style={styles.metricValue}>
              {formatValue(data.bitrate, 'kbps')}
            </Text>
          </View>
        </View>

        {/* Device metrics */}
        <View style={styles.metricGroup}>
          <Text style={styles.groupTitle}>Device</Text>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Battery</Text>
            <Text style={[styles.metricValue, { color: getBatteryColor(data.batteryLevel) }]}>
              {formatValue(data.batteryLevel, '%', 0)}
            </Text>
          </View>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Thermal</Text>
            <Text style={[styles.metricValue, { color: getThermalColor(data.thermalState) }]}>
              {data.thermalState}
            </Text>
          </View>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>Memory</Text>
            <Text style={styles.metricValue}>
              {formatValue(data.memoryUsage, 'MB', 0)}
            </Text>
          </View>
          
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>CPU</Text>
            <Text style={styles.metricValue}>
              {formatValue(data.cpuUsage, '%', 1)}
            </Text>
          </View>
        </View>
      </View>

      {/* Quality indicator */}
      <View style={styles.qualityIndicator}>
        <Text style={styles.qualityLabel}>Connection Quality:</Text>
        <View style={styles.qualityBar}>
          <View
            style={[
              styles.qualityFill,
              {
                width: `${Math.max(0, Math.min(100, 100 - (data.rttMs / 10) - (data.packetLossPercent * 2)))}%`,
                backgroundColor: getRTTColor(data.rttMs),
              },
            ]}
          />
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    borderRadius: 10,
    padding: 15,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
    marginBottom: 15,
    textAlign: 'center',
  },
  grid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metricGroup: {
    flex: 1,
    marginHorizontal: 5,
  },
  groupTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#BDC3C7',
    marginBottom: 10,
    textAlign: 'center',
  },
  metric: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  metricLabel: {
    fontSize: 12,
    color: '#BDC3C7',
    flex: 1,
  },
  metricValue: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
    textAlign: 'right',
    minWidth: 50,
  },
  qualityIndicator: {
    marginTop: 15,
    paddingTop: 15,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  qualityLabel: {
    fontSize: 12,
    color: '#BDC3C7',
    marginBottom: 8,
  },
  qualityBar: {
    height: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 3,
    overflow: 'hidden',
  },
  qualityFill: {
    height: '100%',
    borderRadius: 3,
  },
});