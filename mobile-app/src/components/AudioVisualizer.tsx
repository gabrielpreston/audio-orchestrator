/**
 * Audio visualizer component
 */

import React, { useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

interface AudioVisualizerProps {
  isActive: boolean;
  level: number; // 0-1
  color?: string;
  size?: number;
  style?: any;
}

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({
  isActive,
  level,
  color = '#4ECDC4',
  size = 200,
  style,
}) => {
  const [bars, setBars] = useState<number[]>([]);
  const animatedValues = useRef<Animated.Value[]>([]);
  const animationRef = useRef<Animated.CompositeAnimation | null>(null);

  // Initialize bars
  useEffect(() => {
    const numBars = 32;
    const initialBars = Array(numBars).fill(0);
    setBars(initialBars);
    
    // Initialize animated values
    animatedValues.current = Array(numBars).fill(0).map(() => new Animated.Value(0));
  }, []);

  // Update visualization
  useEffect(() => {
    if (!isActive) {
      // Reset all bars to 0
      const resetBars = Array(bars.length).fill(0);
      setBars(resetBars);
      
      // Stop animation
      if (animationRef.current) {
        animationRef.current.stop();
        animationRef.current = null;
      }
      return;
    }

    // Generate random bar heights based on level
    const newBars = bars.map(() => {
      const baseHeight = level * 0.8;
      const variation = (Math.random() - 0.5) * 0.4;
      return Math.max(0, Math.min(1, baseHeight + variation));
    });
    
    setBars(newBars);

    // Animate bars
    const animations = animatedValues.current.map((animatedValue, index) => {
      return Animated.timing(animatedValue, {
        toValue: newBars[index],
        duration: 100,
        useNativeDriver: false,
      });
    });

    animationRef.current = Animated.parallel(animations);
    animationRef.current.start();

  }, [isActive, level, bars.length]);

  // Cleanup animation on unmount
  useEffect(() => {
    return () => {
      if (animationRef.current) {
        animationRef.current.stop();
      }
    };
  }, []);

  const renderBars = () => {
    const numBars = bars.length;
    const barWidth = size / numBars;
    const maxHeight = size * 0.8;

    return bars.map((barHeight, index) => {
      const height = barHeight * maxHeight;
      const x = index * barWidth;
      const y = (size - height) / 2;

      return (
        <Animated.View
          key={index}
          style={[
            styles.bar,
            {
              width: barWidth * 0.8,
              height: animatedValues.current[index] || new Animated.Value(0),
              backgroundColor: color,
              left: x + barWidth * 0.1,
              top: y,
            },
          ]}
        />
      );
    });
  };

  const renderCircularVisualizer = () => {
    const radius = size * 0.3;
    const centerX = size / 2;
    const centerY = size / 2;
    const numPoints = 64;
    const points = [];

    for (let i = 0; i < numPoints; i++) {
      const angle = (i / numPoints) * 2 * Math.PI;
      const barIndex = Math.floor((i / numPoints) * bars.length);
      const barHeight = bars[barIndex] || 0;
      const distance = radius + (barHeight * radius * 0.5);
      const x = centerX + Math.cos(angle) * distance;
      const y = centerY + Math.sin(angle) * distance;
      points.push(`${x},${y}`);
    }

    const pathData = `M ${points.join(' L ')} Z`;

    return (
      <Svg width={size} height={size} style={styles.svg}>
        <Circle
          cx={centerX}
          cy={centerY}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="2"
          opacity="0.3"
        />
        <Path
          d={pathData}
          fill={color}
          opacity="0.6"
        />
      </Svg>
    );
  };

  return (
    <View style={[styles.container, { width: size, height: size }, style]}>
      {isActive ? (
        <View style={styles.barsContainer}>
          {renderBars()}
        </View>
      ) : (
        <View style={styles.idleContainer}>
          <View style={[styles.idleCircle, { backgroundColor: color }]} />
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  barsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
  },
  bar: {
    position: 'absolute',
    borderRadius: 2,
  },
  idleContainer: {
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
  },
  idleCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    opacity: 0.6,
  },
  svg: {
    position: 'absolute',
  },
});