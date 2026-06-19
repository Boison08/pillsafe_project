import React, { useState } from 'react';
import { ScrollView, View, Text, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Panel, Badge } from '../components/UI';
import { MOCK_NOTIFICATIONS } from '../data/mock';

const FILTERS = [
  { key: null, label: 'All' },
  { key: 'dispensed', label: 'Dispensed' },
  { key: 'missed', label: 'Missed' },
  { key: 'failedVerification', label: 'Verification' },
  { key: 'deviceAlert', label: 'Device' },
];

export default function Notifications() {
  const [filter, setFilter] = useState(null);
  const filtered = filter ? MOCK_NOTIFICATIONS.filter((item) => item.type === filter) : MOCK_NOTIFICATIONS;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Alerts & notifications</Text>
        <Text style={styles.subtitle}>Stay on top of dispense events and alerts.</Text>
        <View style={styles.filtersRow}>
          {FILTERS.map((item) => (
            <Pressable key={item.label} onPress={() => setFilter(item.key)} style={[styles.filterButton, filter === item.key && styles.filterActive]}>
              <Text style={[styles.filterText, filter === item.key && styles.filterTextActive]}>{item.label}</Text>
            </Pressable>
          ))}
        </View>

        {filtered.map((item) => (
          <Panel key={item.id} style={[styles.notificationCard, item.read ? styles.readCard : styles.unreadCard]}>
            <View style={styles.notificationTop}>
              <Text style={styles.notificationTitle}>{item.title}</Text>
              {!item.read && <Badge>New</Badge>}
            </View>
            <Text style={styles.notificationBody}>{item.detail}</Text>
            <Text style={styles.notificationTime}>{new Date(item.timestamp).toLocaleString()}</Text>
          </Panel>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFD' },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '800', color: '#0F172A' },
  subtitle: { marginTop: 6, color: '#64748B', marginBottom: 18 },
  filtersRow: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 16 },
  filterButton: { paddingVertical: 10, paddingHorizontal: 14, borderRadius: 16, borderWidth: 1, borderColor: '#E2E8F0', marginRight: 10, marginBottom: 10, backgroundColor: '#fff' },
  filterActive: { backgroundColor: '#EFF6FF', borderColor: '#1D6FE8' },
  filterText: { color: '#64748B', fontSize: 12, fontWeight: '700' },
  filterTextActive: { color: '#1D6FE8' },
  notificationCard: { marginBottom: 14, padding: 18 },
  readCard: { backgroundColor: '#fff' },
  unreadCard: { backgroundColor: '#EFF6FF' },
  notificationTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  notificationTitle: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  notificationBody: { color: '#475569', lineHeight: 20 },
  notificationTime: { marginTop: 12, color: '#94A3B8', fontSize: 12 },
});
