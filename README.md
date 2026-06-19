# PillSafe — React Native (Expo) App

This workspace was converted to an Expo-managed React Native app to support cross-platform mobile (iOS / Android) and web targets.

---

## Quick start (Expo)

Install dependencies and run the Expo dev tools:

```bash
# 1. Install (first time)
npm install

# 2. Start Expo dev tools
npm start

# 3. Open on device or emulator: choose `Run on Android device/emulator` or `Run on iOS simulator` from the Metro UI
```

If you don't have the Expo CLI globally, use `npx expo start` instead.

---

## Project structure

```
pillsafe-react/
├── App.js                 # Expo entry — cross-platform UI
├── package.json
└── src/                   # original web source (left for reference)
    └── App.jsx
```

The new React Native entry is `App.js`. The original `src/App.jsx` is kept for reference but the app now boots from `App.js`.

---

## Notes & next steps

- **Install native dependencies:** after `npm install`, run `npx expo doctor` if you see issues.
- **Run on device:** scan the QR code from the Metro UI with Expo Go, or run on emulators via the Metro controls.
- **Web support:** `npm run web` will open a browser build (not all native APIs are available on web).

---

If you'd like, I can now:

- Install and pin the exact Expo SDK versions (I can add a `yarn.lock`/`package-lock.json` suggestion),
- Migrate more of the UI from `src/App.jsx` into React Native screens and navigation, or
- Set up React Navigation and basic app routes.

Tell me which next step you want me to take.
