import React from 'react';
import { ActivityIndicator, Pressable, Text, View, StyleSheet } from 'react-native';

export const Badge = ({ children, style }) => (
  <View style={[styles.badge, style]}>
    <Text style={styles.badgeText}>{children}</Text>
  </View>
);

export const Panel = ({ children, style }) => (
  <View style={[styles.panel, style]}>{children}</View>
);

export const Button = ({ children, onPress, disabled, loading, variant = 'primary', style }) => {
  const variants = {
    primary: [styles.button, styles.primary],
    secondary: [styles.button, styles.secondary],
    ghost: [styles.button, styles.ghost],
    danger: [styles.button, styles.danger],
  };
  return (
    <Pressable onPress={onPress} disabled={disabled || loading} style={({ pressed }) => [variants[variant], style, pressed && styles.pressed, (disabled || loading) && styles.disabled]}>
      {loading ? <ActivityIndicator color={variant === 'primary' ? '#fff' : '#1D6FE8'} /> : <Text style={[styles.buttonText, variant === 'ghost' && styles.ghostText]}>{children}</Text>}
    </Pressable>
  );
};

const styles = StyleSheet.create({
  panel: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 18,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  badge: {
    backgroundColor: '#1D6FE818',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    alignSelf: 'flex-start',
  },
  badgeText: {
    color: '#1D6FE8',
    fontWeight: '700',
    fontSize: 12,
  },
  button: {
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 18,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 52,
  },
  primary: {
    backgroundColor: '#1D6FE8',
  },
  secondary: {
    backgroundColor: '#EFF6FF',
  },
  danger: {
    backgroundColor: '#EF4444',
  },
  ghost: {
    backgroundColor: '#F8FAFD',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  buttonText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 15,
  },
  ghostText: {
    color: '#1D6FE8',
  },
  pressed: {
    opacity: 0.85,
  },
  disabled: {
    opacity: 0.55,
  },
});
