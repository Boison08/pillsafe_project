import React, { useEffect, useRef, useState } from 'react';
import { ScrollView, View, Text, TextInput, StyleSheet, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Camera } from 'expo-camera';
import { Panel, Button, Badge } from '../components/UI';
import { api } from '../data/api';

const STEPS = ['Personal details', 'Slot assignment', 'Face enrolment'];
const SLOT_OPTIONS = [0, 1, 2, 3, 4, 5];

export default function Register() {
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [selectedSlot, setSelectedSlot] = useState(-1);
  const [userId, setUserId] = useState(null);
  const [hasPermission, setHasPermission] = useState(null);
  const [samples, setSamples] = useState(0);
  const [isCapturing, setIsCapturing] = useState(false);
  const [enrolled, setEnrolled] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const captureRef = useRef(null);

  useEffect(() => {
    if (step === 2 && hasPermission === null) {
      requestPermission();
    }
  }, [step]);

  useEffect(() => {
    if (step === 2 && hasPermission === 'granted' && !isCapturing && !enrolled) {
      beginCapture();
    }
  }, [step, hasPermission]);

  useEffect(() => {
    if (samples >= 30) {
      clearCaptureInterval();
      setIsCapturing(false);
      setEnrolled(true);
      setStatusMessage('Face enrollment complete — 30 samples captured.');
      if (userId) {
        api.finaliseEnrolment(userId).catch(() => {
          setStatusMessage('Enrollment complete locally, but finalization failed.');
        });
      }
    }
  }, [samples, userId]);

  useEffect(() => {
    return () => clearCaptureInterval();
  }, []);

  const clearCaptureInterval = () => {
    if (captureRef.current) {
      clearInterval(captureRef.current);
      captureRef.current = null;
    }
  };

  const requestPermission = async () => {
    const { status } = await Camera.requestCameraPermissionsAsync();
    setHasPermission(status);
    if (status !== 'granted') {
      setStatusMessage('Camera permission is required to capture face samples.');
    }
  };

  const handleCreateUser = async () => {
    try {
      const user = await api.createUser({ name, phone });
      setUserId(user.user_id);
      setStep(1);
      setStatusMessage('User created. Choose a slot and continue to enrollment.');
    } catch (error) {
      setStatusMessage('Could not create user. Try again.');
    }
  };

  const handleStartEnrolment = async () => {
    if (!userId) {
      setStatusMessage('User information is missing. Please go back and re-enter details.');
      return;
    }

    setStatusMessage('Starting face enrollment on the Pi backend. Please look at the camera.');
    try {
      await api.startEnrolment(userId);
      setStep(2);
      setSamples(0);
      setEnrolled(false);
    } catch (error) {
      setStatusMessage('Failed to start enrollment. Check backend connection.');
    }
  };

  const beginCapture = () => {
    setIsCapturing(true);
    setStatusMessage('Capturing 30 face samples. Keep facing the camera.');
    setSamples(0);

    captureRef.current = setInterval(() => {
      setSamples((current) => Math.min(current + 1, 30));
    }, 250);
  };

  const resetFlow = () => {
    clearCaptureInterval();
    setStep(0);
    setName('');
    setPhone('');
    setSelectedSlot(-1);
    setUserId(null);
    setHasPermission(null);
    setSamples(0);
    setIsCapturing(false);
    setEnrolled(false);
    setStatusMessage('');
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Register patient</Text>
        <Text style={styles.subtitle}>Create a new user and enroll their face with PillSafe.</Text>
        <View style={styles.stepRow}>
          {STEPS.map((label, index) => (
            <View key={label} style={[styles.stepItem, index === step && styles.stepActive]}>
              <Text style={[styles.stepLabel, index === step && styles.stepLabelActive]}>{label}</Text>
            </View>
          ))}
        </View>

        {step === 0 && (
          <Panel>
            <Text style={styles.sectionTitle}>Personal details</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Full name"
              style={styles.input}
              placeholderTextColor="#94A3B8"
            />
            <TextInput
              value={phone}
              onChangeText={setPhone}
              placeholder="Caregiver phone"
              keyboardType="phone-pad"
              style={styles.input}
              placeholderTextColor="#94A3B8"
            />
            <Button disabled={!name || !phone} onPress={handleCreateUser}>Continue</Button>
          </Panel>
        )}

        {step === 1 && (
          <Panel>
            <Text style={styles.sectionTitle}>Choose a slot</Text>
            <Text style={styles.helpText}>Pick a carousel slot for this patient.</Text>
            <View style={styles.slotGrid}>
              {SLOT_OPTIONS.map((slot) => (
                <Button
                  key={slot}
                  variant={selectedSlot === slot ? 'secondary' : 'ghost'}
                  onPress={() => setSelectedSlot(slot)}
                  style={styles.slotButton}
                >
                  Slot {String.fromCharCode(65 + slot)}
                </Button>
              ))}
            </View>
            <Button onPress={() => setStep(0)} variant="ghost" style={styles.marginTop}>Back</Button>
            <Button onPress={handleStartEnrolment} disabled={selectedSlot < 0} style={styles.marginTop}>Enroll face</Button>
          </Panel>
        )}

        {step === 2 && (
          <Panel>
            <Text style={styles.sectionTitle}>Face enrollment</Text>
            <Text style={styles.helpText}>Your phone camera will capture 30 face samples during registration. Keep your full face inside the frame.</Text>
            <View style={styles.cameraWrapper}>
              {hasPermission === 'granted' ? (
                <Camera style={styles.camera} type={Camera.Constants.Type.front} ratio="4:3" />
              ) : (
                <View style={styles.cameraPlaceholder}>
                  <Text style={styles.cameraPlaceholderText}>Camera preview unavailable</Text>
                  <Text style={styles.cameraPlaceholderText}>Please grant camera access.</Text>
                </View>
              )}
            </View>
            <View style={styles.enrolCard}>
              <Text style={styles.enrolIcon}>{enrolled ? '✓' : '📷'}</Text>
              <Text style={styles.enrolText}>{enrolled ? 'Enrollment complete' : 'Capturing face samples'}</Text>
              <Badge>{samples} / 30 samples</Badge>
              <Text style={styles.helpText}>{statusMessage}</Text>
              {hasPermission !== 'granted' && (
                <Button onPress={requestPermission} variant="ghost" style={styles.marginTop}>Allow camera access</Button>
              )}
            </View>
            <Button onPress={resetFlow} variant="ghost">Start over</Button>
            <Button onPress={() => setStep(0)} disabled={!enrolled} style={styles.marginTop}>Finish registration</Button>
          </Panel>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFD' },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '800', color: '#0F172A' },
  subtitle: { marginTop: 6, color: '#64748B', marginBottom: 20 },
  stepRow: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 20 },
  stepItem: { paddingVertical: 10, paddingHorizontal: 12, backgroundColor: '#F1F5F9', borderRadius: 14, marginRight: 8, marginBottom: 8 },
  stepActive: { backgroundColor: '#1D6FE8' },
  stepLabel: { fontSize: 11, color: '#64748B', fontWeight: '700' },
  stepLabelActive: { color: '#fff' },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: '#0F172A', marginBottom: 12 },
  helpText: { fontSize: 13, color: '#64748B', marginBottom: 14 },
  input: { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: '#E2E8F0', padding: 14, fontSize: 15, marginBottom: 14, color: '#0F172A' },
  slotGrid: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 10 },
  slotButton: { minWidth: 100, marginRight: 10, marginBottom: 10 },
  cameraWrapper: { height: 360, borderRadius: 18, overflow: 'hidden', backgroundColor: '#0F172A', marginBottom: 16 },
  camera: { flex: 1 },
  cameraPlaceholder: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  cameraPlaceholderText: { color: '#CBD5E1', textAlign: 'center', marginBottom: 6 },
  enrolCard: { marginTop: 16, borderRadius: 16, backgroundColor: '#EFF6FF', padding: 22, alignItems: 'center' },
  enrolIcon: { fontSize: 50 },
  enrolText: { fontSize: 16, fontWeight: '700', color: '#0F172A', marginBottom: 8 },
  marginTop: { marginTop: 12 },
});
