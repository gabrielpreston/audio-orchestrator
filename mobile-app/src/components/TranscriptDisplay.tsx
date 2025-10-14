/**
 * Transcript display component
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { WordTiming } from '../types';

interface TranscriptDisplayProps {
  transcript: string;
  isFinal: boolean;
  words?: WordTiming[];
  style?: any;
}

export const TranscriptDisplay: React.FC<TranscriptDisplayProps> = ({
  transcript,
  isFinal,
  words = [],
  style,
}) => {
  const [displayText, setDisplayText] = useState('');
  const [currentWordIndex, setCurrentWordIndex] = useState(0);
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;

  // Animate text changes
  useEffect(() => {
    if (transcript !== displayText) {
      // Fade out
      Animated.sequence([
        Animated.timing(fadeAnim, {
          toValue: 0.3,
          duration: 150,
          useNativeDriver: true,
        }),
        Animated.timing(scaleAnim, {
          toValue: 0.95,
          duration: 150,
          useNativeDriver: true,
        }),
      ]).start(() => {
        // Update text
        setDisplayText(transcript);
        setCurrentWordIndex(0);
        
        // Fade in
        Animated.parallel([
          Animated.timing(fadeAnim, {
            toValue: 1,
            duration: 150,
            useNativeDriver: true,
          }),
          Animated.timing(scaleAnim, {
            toValue: 1,
            duration: 150,
            useNativeDriver: true,
          }),
        ]).start();
      });
    }
  }, [transcript, displayText, fadeAnim, scaleAnim]);

  // Animate word highlighting
  useEffect(() => {
    if (words.length > 0 && !isFinal) {
      const interval = setInterval(() => {
        setCurrentWordIndex(prev => (prev + 1) % words.length);
      }, 200);

      return () => clearInterval(interval);
    }
  }, [words, isFinal]);

  const renderWords = () => {
    if (words.length === 0) {
      return (
        <Text style={[styles.text, isFinal ? styles.finalText : styles.partialText]}>
          {displayText}
        </Text>
      );
    }

    return (
      <View style={styles.wordsContainer}>
        {words.map((word, index) => {
          const isCurrentWord = index === currentWordIndex && !isFinal;
          const isSpoken = index < currentWordIndex || isFinal;
          
          return (
            <Text
              key={index}
              style={[
                styles.word,
                isCurrentWord && styles.currentWord,
                isSpoken && styles.spokenWord,
                isFinal && styles.finalWord,
              ]}
            >
              {word.word}
            </Text>
          );
        })}
      </View>
    );
  };

  const getStatusText = () => {
    if (!transcript) return 'Listening...';
    if (isFinal) return 'Final';
    return 'Processing...';
  };

  const getStatusColor = () => {
    if (isFinal) return '#4ECDC4';
    if (transcript) return '#FFE66D';
    return '#BDC3C7';
  };

  return (
    <Animated.View
      style={[
        styles.container,
        {
          opacity: fadeAnim,
          transform: [{ scale: scaleAnim }],
        },
        style,
      ]}
    >
      {/* Status indicator */}
      <View style={styles.statusContainer}>
        <View style={[styles.statusDot, { backgroundColor: getStatusColor() }]} />
        <Text style={[styles.statusText, { color: getStatusColor() }]}>
          {getStatusText()}
        </Text>
      </View>

      {/* Transcript content */}
      <View style={styles.contentContainer}>
        {transcript ? (
          renderWords()
        ) : (
          <Text style={styles.placeholderText}>
            {isFinal ? 'No speech detected' : 'Listening for speech...'}
          </Text>
        )}
      </View>

      {/* Confidence indicator */}
      {words.length > 0 && (
        <View style={styles.confidenceContainer}>
          <Text style={styles.confidenceText}>
            Confidence: {Math.round(words[0]?.confidence * 100 || 0)}%
          </Text>
        </View>
      )}
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 15,
    padding: 20,
    minHeight: 100,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 15,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  contentContainer: {
    flex: 1,
  },
  text: {
    fontSize: 18,
    lineHeight: 26,
    color: '#FFFFFF',
  },
  partialText: {
    opacity: 0.7,
    fontStyle: 'italic',
  },
  finalText: {
    opacity: 1,
    fontWeight: '500',
  },
  wordsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  word: {
    fontSize: 18,
    lineHeight: 26,
    color: '#FFFFFF',
    marginRight: 8,
    marginBottom: 4,
    paddingHorizontal: 4,
    paddingVertical: 2,
    borderRadius: 4,
  },
  currentWord: {
    backgroundColor: 'rgba(255, 230, 109, 0.3)',
    fontWeight: '600',
  },
  spokenWord: {
    opacity: 0.8,
  },
  finalWord: {
    opacity: 1,
    fontWeight: '500',
  },
  placeholderText: {
    fontSize: 16,
    color: '#BDC3C7',
    fontStyle: 'italic',
    textAlign: 'center',
  },
  confidenceContainer: {
    marginTop: 10,
    alignItems: 'flex-end',
  },
  confidenceText: {
    fontSize: 12,
    color: '#BDC3C7',
    opacity: 0.8,
  },
});