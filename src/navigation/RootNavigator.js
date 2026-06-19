import React from 'react';
import { Text } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import Home from '../screens/Home';
import Register from '../screens/Register';
import Verify from '../screens/Verify';
import Schedule from '../screens/Schedule';
import Monitor from '../screens/Monitor';
import Notifications from '../screens/Notifications';

const Tab = createBottomTabNavigator();

const ICONS = {
  Home: '🏠',
  Register: '👤',
  Verify: '🪪',
  Schedule: '📅',
  Monitor: '📊',
  Notifications: '🔔',
};

export default function RootNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: '#1D6FE8',
        tabBarInactiveTintColor: '#64748B',
        tabBarLabelStyle: { fontSize: 11, paddingBottom: 2 },
        tabBarIcon: ({ color }) => <Text style={{ fontSize: 18, color }}>{ICONS[route.name]}</Text>,
      })}
    >
      <Tab.Screen name="Home" component={Home} />
      <Tab.Screen name="Register" component={Register} />
      <Tab.Screen name="Verify" component={Verify} />
      <Tab.Screen name="Schedule" component={Schedule} />
      <Tab.Screen name="Monitor" component={Monitor} />
      <Tab.Screen name="Notifications" component={Notifications} />
    </Tab.Navigator>
  );
}
