import React, { useRef, useState } from 'react';
import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Panel, Button, Badge } from '../components/UI';
import { api } from '../data/api';

const STEPS = [
  { label: 'Scanning face', detail: 'Face captured by camera' },
  { label: 'Matching embeddings', detail: 'Model comparison in progress' },
  { label: 'Rotating carousel', detail: 'Slot aligned' },
  { label: 'Waiting for pickup', detail: 'Final confirmation' },
];

export default function Verify() {
  const [state, setState] = useState('idle');
  const [stepIndex, setStepIndex] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Ready to verify. Press start to trigger Pi verification.');
  const [resultMessage, setResultMessage] = useState('');
  const timeoutRefs = useRef([]);

  const startVerification = () => {
    timeoutRefs.current.forEach(clearTimeout);
    timeoutRefs.current = [];
    setState('scanning');
    setStepIndex(0);
    setResultMessage('');
    setStatusMessage('Preparing Pi verification request...');

    timeoutRefs.current.push(setTimeout(() => {
      setStepIndex(1);
      setStatusMessage('Pi camera is being activated.');
    }, 800));

    timeoutRefs.current.push(setTimeout(() => {
      setStepIndex(2);
      setStatusMessage('Pi is matching facial embeddings.');
    }, 1600));

    timeoutRefs.current.push(setTimeout(() => {
      setStepIndex(3);
      setStatusMessage('Pi is aligning the carousel for the patient.');
    }, 2400));

    timeoutRefs.current.push(setTimeout(() => {
      finishVerification();
    }, 3200));
  };

  const finishVerification = async () => {
    setStatusMessage('Requesting verification from the Pi camera.');
    try {
      const result = await api.verifyFace();
      if (result.verified) {
        setState('success');
        setResultMessage(result.message);
      } else {
        setState('failed');
        setResultMessage(result.message);
      }
    } catch (error) {
      setState('failed');
      setResultMessage('Verification service is unavailable.');
    }
  };

  const reset = () => {
    timeoutRefs.current.forEach(clearTimeout);
    timeoutRefs.current = [];
    setState('idle');
    setStepIndex(0);
    setStatusMessage('Ready to verify. Press start to trigger Pi verification.');
    setResultMessage('');
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Facial verification</Text>
        <Text style={styles.subtitle}>Use the camera to verify the patient before dispensing medication.</Text>
        <Panel>
          <Text style={styles.sectionTitle}>Status</Text>
          {state === 'idle' && (
            <>
              <Text style={styles.bodyText}>{statusMessage}</Text>
              <Button onPress={startVerification} style={styles.marginTop}>Start verification</Button>
            </>
          )}

          {state === 'scanning' && (
            <>
              <View style={styles.cameraWrapper}>
                <View style={styles.cameraPlaceholder}>
                  <Text style={styles.cameraPlaceholderText}>Verification is performed by the Pi camera.</Text>
                  <Text style={styles.cameraPlaceholderText}>Your app is sending the request to start the Pi capture.</Text>
                </View>
              </View>
              <Text style={styles.bodyText}>{statusMessage}</Text>
              <View style={styles.statusRow}>
                <Badge>Pi camera verification</Badge>
                <Badge>{STEPS[stepIndex]?.label || 'Scanning'}</Badge>
              </View>
              <View style={styles.stepList}>
                {STEPS.map((step, index) => (
                  <View key={step.label} style={styles.stepItem}>
                    <Text style={[styles.stepBullet, index <= stepIndex ? styles.stepActive : null]}>{index <= stepIndex ? '✓' : index + 1}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.stepTitle}>{step.label}</Text>
                      <Text style={styles.stepDetail}>{step.detail}</Text>
                    </View>
                  </View>
                ))}
              </View>
            </>
          )}

          {state === 'success' && (
            <View style={styles.successBox}>
              <Text style={styles.successIcon}>✓</Text>
              <Text style={styles.successTitle}>Verification successful</Text>
              <Text style={styles.successSubtitle}>{resultMessage}</Text>
              <Badge>Identity confirmed</Badge>
              <Button onPress={reset} style={styles.marginTop}>Verify another</Button>
            </View>
          )}

          {state === 'failed' && (
            <View style={styles.failedBox}>
              <Text style={styles.failedIcon}>✕</Text>
              <Text style={styles.failedTitle}>Verification failed</Text>
              <Text style={styles.failedSubtitle}>{resultMessage}</Text>
              <Button onPress={reset} style={styles.marginTop}>Try again</Button>
            </View>
          )}
        </Panel>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFD' },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '800', color: '#0F172A' },
  subtitle: { marginTop: 6, color: '#64748B', marginBottom: 20 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: '#0F172A', marginBottom: 14 },
  bodyText: { fontSize: 15, color: '#475569' },
  marginTop: { marginTop: 12 },
  cameraWrapper: { height: 260, borderRadius: 18, overflow: 'hidden', backgroundColor: '#0F172A', marginBottom: 16, justifyContent: 'center' },
  cameraPlaceholder: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  cameraPlaceholderText: { color: '#CBD5E1', textAlign: 'center' },
  statusRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12, marginBottom: 12 },
  stepList: { marginTop: 8 },
  stepItem: { flexDirection: 'row', alignItems: 'flex-start', padding: 12, borderRadius: 14, backgroundColor: '#F8FAFD', borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  stepBullet: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#E2E8F0', color: '#64748B', textAlign: 'center', lineHeight: 32, fontWeight: '700' },
  stepActive: { backgroundColor: '#1D6FE8', color: '#fff' },
  stepTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  stepDetail: { fontSize: 13, color: '#64748B', marginTop: 4 },
  successBox: { alignItems: 'center', padding: 18, borderRadius: 16, backgroundColor: '#D1FAE5' },
  successIcon: { fontSize: 42, color: '#059669' },
  successTitle: { fontSize: 20, fontWeight: '800', color: '#059669' },
  successSubtitle: { fontSize: 14, color: '#475569', textAlign: 'center', marginTop: 8 },
  failedBox: { alignItems: 'center', padding: 18, borderRadius: 16, backgroundColor: '#FEE2E2' },
  failedIcon: { fontSize: 42, color: '#B91C1C' },
  failedTitle: { fontSize: 20, fontWeight: '800', color: '#B91C1C' },
  failedSubtitle: { fontSize: 14, color: '#475569', textAlign: 'center', marginTop: 8 },
});
