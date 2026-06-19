import React from 'react';
import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Panel, Badge } from '../components/UI';
import { MOCK_USER, MOCK_ADHERENCE, MOCK_DEVICE } from '../data/mock';

const stats = [
  { label: 'Adherence', value: '84%', color: '#1D6FE8' },
  { label: 'Taken', value: '4', color: '#0EA472' },
  { label: 'Missed', value: '1', color: '#F59E0B' },
  { label: 'Failed', value: '0', color: '#EF4444' },
];

export default function Monitor() {
  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Caregiver monitor</Text>
        <Text style={styles.subtitle}>Device status and adherence summaries.</Text>

        <View style={styles.statsRow}>
          {stats.map((stat) => (
            <Panel key={stat.label} style={[styles.statCard, { borderColor: stat.color + '33' }]}> 
              <Text style={[styles.statValue, { color: stat.color }]}>{stat.value}</Text>
              <Text style={styles.statLabel}>{stat.label}</Text>
            </Panel>
          ))}
        </View>

        <Panel style={styles.devicePanel}>
          <View style={styles.row}>
            <Text style={styles.sectionTitle}>Device telemetry</Text>
            <Badge>Online</Badge>
          </View>
          <View style={styles.detailRow}><Text style={styles.detailLabel}>RTC time</Text><Text style={styles.detailValue}>{MOCK_DEVICE.rtcTime}</Text></View>
          <View style={styles.detailRow}><Text style={styles.detailLabel}>GSM signal</Text><Text style={styles.detailValue}>{MOCK_DEVICE.gsmSignal}</Text></View>
          <View style={styles.detailRow}><Text style={styles.detailLabel}>Slots loaded</Text><Text style={styles.detailValue}>{MOCK_DEVICE.slotsLoaded}/6</Text></View>
          <View style={styles.detailRow}><Text style={styles.detailLabel}>Last dispense</Text><Text style={styles.detailValue}>{MOCK_DEVICE.lastDispense}</Text></View>
        </Panel>

        <Panel>
          <Text style={styles.sectionTitle}>Recent events</Text>
          {MOCK_ADHERENCE.slice(0, 4).map((item) => (
            <View key={item.scheduledAt} style={styles.eventRow}>
              <View style={styles.eventDot} />
              <View style={{ flex: 1 }}>
                <Text style={styles.eventTitle}>{item.medicationName}</Text>
                <Text style={styles.eventSubtitle}>{item.status === 'taken' ? 'Taken' : 'Missed'} · {new Date(item.scheduledAt).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}</Text>
              </View>
              <Text style={[styles.eventBadge, { backgroundColor: item.status === 'taken' ? '#D1FAE5' : '#FEE2E2', color: item.status === 'taken' ? '#059669' : '#EF4444' }]}>{item.status}</Text>
            </View>
          ))}
        </Panel>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFD' },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '800', color: '#0F172A' },
  subtitle: { marginTop: 6, color: '#64748B', marginBottom: 18 },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap' },
  statCard: { flex: 1, borderWidth: 1, padding: 18, minWidth: 140, marginBottom: 12, marginRight: 12 },
  statValue: { fontSize: 24, fontWeight: '800', marginBottom: 6 },
  statLabel: { fontSize: 13, color: '#64748B' },
  devicePanel: { marginTop: 16 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#0F172A' },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  detailLabel: { color: '#64748B' },
  detailValue: { fontWeight: '700', color: '#0F172A' },
  eventRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  eventDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#1D6FE8' },
  eventTitle: { fontWeight: '700', color: '#0F172A' },
  eventSubtitle: { fontSize: 12, color: '#64748B', marginTop: 4 },
  eventBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, fontSize: 12, fontWeight: '700' },
});
