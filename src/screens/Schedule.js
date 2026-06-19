import React, { useState } from 'react';
import { ScrollView, View, Text, TextInput, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Panel, Button, Badge } from '../components/UI';
import { MOCK_SCHEDULES, MED_COLORS } from '../data/mock';

export default function Schedule() {
  const [showForm, setShowForm] = useState(false);
  const [medName, setMedName] = useState('');
  const [dosage, setDosage] = useState('');
  const [time, setTime] = useState('08:00');
  const [items, setItems] = useState(MOCK_SCHEDULES);

  const addMedication = () => {
    if (!medName || !dosage) return;
    setItems((prev) => [
      ...prev,
      { id: Date.now(), medicationName: medName, dosage, dispenseTimes: [time], repeatDays: [1,1,1,1,1,1,1], gracePeriodMinutes: 15 },
    ]);
    setMedName('');
    setDosage('');
    setTime('08:00');
    setShowForm(false);
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Medication schedule</Text>
        <Text style={styles.subtitle}>Manage prescriptions and dispense times.</Text>
        <Button onPress={() => setShowForm((v) => !v)}>{showForm ? 'Hide form' : '+ Add medication'}</Button>

        {showForm && (
          <Panel style={styles.formPanel}>
            <Text style={styles.sectionTitle}>Add medication</Text>
            <TextInput value={medName} onChangeText={setMedName} placeholder="Medication name" style={styles.input} placeholderTextColor="#94A3B8" />
            <TextInput value={dosage} onChangeText={setDosage} placeholder="Dosage" style={styles.input} placeholderTextColor="#94A3B8" />
            <TextInput value={time} onChangeText={setTime} placeholder="Time" style={styles.input} placeholderTextColor="#94A3B8" />
            <Button onPress={addMedication} disabled={!medName || !dosage} style={styles.marginTop}>Save medication</Button>
          </Panel>
        )}

        <View style={styles.listHeading}>
          <Text style={styles.sectionTitle}>Scheduled meds</Text>
          <Badge>{items.length} items</Badge>
        </View>

        <View style={styles.listGrid}>
          {items.map((item, index) => (
            <Panel key={item.id} style={styles.medCard}>
              <View style={styles.medRow}>
                <Text style={styles.medName}>{item.medicationName}</Text>
                <Badge style={{ backgroundColor: MED_COLORS[index % MED_COLORS.length] + '18', color: MED_COLORS[index % MED_COLORS.length] }}>Slot {String.fromCharCode(65 + index)}</Badge>
              </View>
              <Text style={styles.medDose}>{item.dosage}</Text>
              <Text style={styles.medTime}>{item.dispenseTimes.join(', ')}</Text>
            </Panel>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFD' },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '800', color: '#0F172A' },
  subtitle: { marginTop: 6, color: '#64748B', marginBottom: 18 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#0F172A', marginBottom: 10 },
  formPanel: { marginTop: 16 },
  input: { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: '#E2E8F0', padding: 14, fontSize: 15, marginBottom: 12, color: '#0F172A' },
  marginTop: { marginTop: 12 },
  listHeading: { marginTop: 24, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  listGrid: { marginTop: 16 },
  medCard: { paddingVertical: 18, paddingHorizontal: 16, marginBottom: 14 },
  medRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  medName: { fontSize: 16, fontWeight: '700', color: '#0F172A' },
  medDose: { fontSize: 14, color: '#475569' },
  medTime: { marginTop: 10, color: '#64748B' },
});
