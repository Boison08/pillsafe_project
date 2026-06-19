import React from 'react';
import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Panel, Badge } from '../components/UI';
import { MOCK_USER, MOCK_SCHEDULES, MOCK_ADHERENCE, MOCK_DEVICE, slotLabel, greeting, MED_COLORS } from '../data/mock';

const todayIndex = (new Date().getDay() + 6) % 7;
const todaySchedules = MOCK_SCHEDULES.filter((schedule) => schedule.repeatDays[todayIndex]);
const takenCount = MOCK_ADHERENCE.filter((item) => item.status === 'taken').length;
const adherenceRate = MOCK_ADHERENCE.length ? Math.round((takenCount / MOCK_ADHERENCE.length) * 100) : 0;
const nextDose = todaySchedules[0];

const statusFor = (schedule, time) => {
  const [hour, minute] = time.split(':').map(Number);
  const target = new Date();
  target.setHours(hour, minute, 0, 0);
  const match = MOCK_ADHERENCE.find((entry) => entry.medicationName === schedule.medicationName);
  if (match?.status === 'taken') return 'Taken';
  if (match?.status === 'missed') return 'Missed';
  return target < new Date() ? 'Missed' : 'Pending';
};

export default function Home() {
  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>{greeting()},</Text>
        <Text style={styles.subtitle}>{MOCK_USER.fullName}</Text>

        <View style={styles.topRow}>
          <Panel style={styles.primaryCard}>
            <Text style={styles.cardLabel}>Next dose</Text>
            <Text style={styles.cardValue}>{nextDose?.dispenseTimes[0] ?? '--:--'}</Text>
            <Text style={styles.cardSub}>{nextDose?.medicationName ?? 'No scheduled doses'}</Text>
            <Badge>On time</Badge>
          </Panel>
          <Panel style={styles.smallCard}>
            <Text style={styles.statValue}>{adherenceRate}%</Text>
            <Text style={styles.statLabel}>Adherence</Text>
          </Panel>
        </View>

        <Panel>
          <Text style={styles.sectionTitle}>Today</Text>
          {todaySchedules.length ? (
            todaySchedules.map((schedule, index) => {
              const status = statusFor(schedule, schedule.dispenseTimes[0]);
              const pillColor = MED_COLORS[index % MED_COLORS.length];
              return (
                <View key={schedule.id} style={styles.medRow}>
                  <View style={[styles.medIcon, { backgroundColor: `${pillColor}22` }]}>
                    <Text style={[styles.medIconText, { color: pillColor }]}>{slotLabel(index)}</Text>
                  </View>
                  <View style={styles.medInfo}>
                    <Text style={styles.medName}>{schedule.medicationName}</Text>
                    <Text style={styles.medMeta}>{schedule.dosage} · {schedule.dispenseTimes.join(', ')}</Text>
                  </View>
                  <Badge style={status === 'Taken' ? styles.badgeTaken : status === 'Missed' ? styles.badgeMissed : styles.badgePending}>{status}</Badge>
                </View>
              );
            })
          ) : (
            <Text style={styles.emptyText}>No medications scheduled for today.</Text>
          )}
        </Panel>

        <Panel style={styles.devicePanel}>
          <Text style={styles.sectionTitle}>Device status</Text>
          <View style={styles.statusRow}>
            <View>
              <Text style={styles.statusLabel}>Connection</Text>
              <Text style={styles.statusValue}>{MOCK_DEVICE.connected ? 'Online' : 'Offline'}</Text>
            </View>
            <View>
              <Text style={styles.statusLabel}>Last dispense</Text>
              <Text style={styles.statusValue}>{MOCK_DEVICE.lastDispense}</Text>
            </View>
          </View>
        </Panel>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFD' },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '800', color: '#0F172A' },
  subtitle: { marginTop: 4, fontSize: 17, color: '#64748B', marginBottom: 20 },
  topRow: { flexDirection: 'row', justifyContent: 'space-between' },
  primaryCard: { flex: 1, marginRight: 12, paddingBottom: 20 },
  smallCard: { width: 120, justifyContent: 'center', alignItems: 'center' },
  cardLabel: { fontSize: 12, fontWeight: '700', color: '#93C5FD', marginBottom: 6 },
  cardValue: { fontSize: 32, fontWeight: '800', color: '#fff' },
  cardSub: { marginTop: 6, color: '#DBEAFE', fontSize: 13, marginBottom: 12 },
  statValue: { fontSize: 30, fontWeight: '800', color: '#0F172A' },
  statLabel: { marginTop: 8, color: '#64748B' },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#0F172A', marginBottom: 14 },
  medRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 14 },
  medIcon: { width: 46, height: 46, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  medIconText: { fontSize: 18, fontWeight: '800' },
  medInfo: { flex: 1 },
  medName: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  medMeta: { marginTop: 4, color: '#64748B' },
  emptyText: { color: '#64748B', fontSize: 14 },
  devicePanel: { marginTop: 16 },
  statusRow: { flexDirection: 'row', justifyContent: 'space-between' },
  statusLabel: { color: '#9CA3AF', marginBottom: 6 },
  statusValue: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  badgeTaken: { backgroundColor: '#D1FAE5' },
  badgeMissed: { backgroundColor: '#FEE2E2', color: '#EF4444' },
  badgePending: { backgroundColor: '#EFF6FF', color: '#1D6FE8' },
});
