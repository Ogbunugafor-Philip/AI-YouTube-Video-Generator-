# VidGen Studio — Android App (React Native + Expo)

Mobile interface for the AI YouTube Video Generator. All production runs on the
existing backend at **https://vidgen.store**; this app is the phone client.

Package name: `com.vidgen.studio` · Firebase project: `vidgen-store`

## Features
- Full production pipeline (Topic / Write-Up → style → voice → scene editor → live progress → result)
- One-tap **Publish to YouTube**
- **FCM push**: breaking-news alerts (YES/NO actions) + draft-ready (Preview)
- **Offline drafting** with auto-sync (AsyncStorage + NetInfo)
- **Video History** with live YouTube stats

## Prerequisites
- Node 18–20, JDK 17, Android SDK (`ANDROID_HOME` set)
- `mobile/google-services.json` present (Firebase Android config — already included)

## Install JS dependencies
```bash
cd mobile
npm install
```

## Build a standalone APK (local, no Expo account)
```bash
cd mobile

# 1. Generate the native Android project (wires google-services.json + FCM)
npx expo prebuild --platform android --clean

# 2. (One time) create a signing keystore — keep this file safe & private
keytool -genkeypair -v -keystore vidgen-release.keystore \
  -alias vidgen -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass vidgen123 -keypass vidgen123 \
  -dname "CN=VidGen Studio, O=VidGen, C=US"

# 3. Build the release APK
cd android
./gradlew assembleRelease

# APK output:
#   mobile/android/app/build/outputs/apk/release/app-release.apk
```

A debug APK (also directly installable) can be built with `./gradlew assembleDebug`
→ `app/build/outputs/apk/debug/app-debug.apk`.

## Build via Expo cloud (alternative — needs a free Expo account)
```bash
cd mobile
npm install -g eas-cli
eas login
eas build --platform android --profile preview   # produces an installable APK
```

## Install on an Android phone (no Play Store)
1. Copy `app-release.apk` to the phone (USB, email, or a download link).
2. On the phone: **Settings → Apps → Special access → Install unknown apps**
   (or you'll be prompted on first install) and allow your file manager / browser.
3. Tap the APK and **Install**.
4. Open **VidGen Studio**, allow the **Notifications** permission so push works.

## Configuration
- Backend URL: `app.json → expo.extra.apiBaseUrl` (default `https://vidgen.store`).
- Push: `google-services.json` (FCM project `vidgen-store`). The backend sends via
  the Firebase Admin SDK using `firebase-service-account.json` (server-side only).

## Notes
- No secrets are stored in the app source. `google-services.json` contains only the
  non-secret FCM/Firebase client config.
- Notification action buttons (YES/NO) fire when the app is foregrounded or
  backgrounded; full killed-state background triggering is limited by Expo.
