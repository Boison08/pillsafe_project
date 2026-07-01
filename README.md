# PillSafe — Smart Pill Dispenser with Facial Recognition

A Raspberry Pi 4B-based smart medication dispensing system that uses facial recognition (FaceNet embeddings), IR-confirmed dispensing, and GSM SMS alerts to ensure safe, verified, and logged medication delivery.

**KNUST — Department of Computer Engineering | BSc Final Year Project**
**Authors:** Boison, Simeon A.A. | Donkor, Maxwell J.
**Supervisor:** Dr Bright Yeboah-Akowuah

---

## Project Structure

```
pillsafe/
│
├── main.py                        # Entry point — initialises and runs everything
├── config.yaml                    # Central configuration (all tuneable parameters)
├── requirements.txt               # Python dependencies
│
├── core/                          # Facial recognition pipeline
│   ├── camera.py                  # Pi Camera v2 capture (Picamera2)
│   ├── detector.py                # Haar Cascade face detection + preprocessing
│   ├── facenet_recogniser.py      # FaceNet embedding-based recognition
│   └── decision.py                # Orchestrates detection → FaceNet recognition
│
├── hardware/                      # Physical component interfaces
│   ├── dispenser.py               # Per-compartment servo control (6 servos × 9 slots)
│   ├── ir_sensor.py               # FC-51 IR sensors (pill detect + pickup)
│   ├── buzzer.py                  # Active buzzer for audio feedback
│   ├── rtc.py                     # DS3231 RTC via I2C
│   └── gsm.py                     # SIM800L SMS via USB-to-serial
│
├── scheduler/                     # Time-based dispensing triggers
│   └── schedule_controller.py     # RTC polling + DispenseEvent generation
│
├── database/                      # SQLite data layer
│   ├── schema.sql                 # Tables (Users, Schedules, Inventory, AdherenceLog, Notifications)
│   └── db_manager.py              # Thread-safe CRUD helpers
│
├── api/                           # Flask REST API for mobile app
│   └── routes.py                  # All endpoints (users, schedules, adherence, health)
│
├── alerts/                        # SMS notification service
│   └── alert_service.py           # Background thread monitoring missed-dose events
│
├── enrollment/                    # User facial enrolment
│   └── enrol_user.py              # Sample capture + model retraining (CLI + API)
│
├── utils/                         # Shared utilities
│   ├── config.py                  # YAML config loader with dot-notation access
│   └── logger.py                  # Project-wide logging setup
│
├── data/                          # Runtime data (auto-created)
│   ├── dataset/                   # Facial samples and embeddings: dataset/{user_id}/
│   │                              # embeddings.npy, embeddings_metadata.txt
│   ├── pillsafe.db                # SQLite database
│   └── pillsafe.log               # Application log
│
└── services/
    └── pillsafe.service           # systemd unit file for auto-start on boot
```

---

## Hardware Wiring Guide

### GPIO Pin Assignment (BCM Numbering)

| Component           | Signal   | GPIO (BCM) | Physical Pin | Notes                       |
|---------------------|----------|------------|--------------|-----------------------------|
| Servo — compartment 0 | PWM    | GPIO 12    | Pin 32       | One servo per compartment   |
| Servo — compartment 1 | PWM    | GPIO 13    | Pin 33       |                             |
| Servo — compartment 2 | PWM    | GPIO 16    | Pin 36       |                             |
| Servo — compartment 3 | PWM    | GPIO 17    | Pin 11       |                             |
| Servo — compartment 4 | PWM    | GPIO 26    | Pin 37       |                             |
| Servo — compartment 5 | PWM    | GPIO 27    | Pin 13       |                             |
| Servos              | VCC      | —          | 5V rail      | Servos need 5V (shared)     |
| Servos              | GND      | —          | GND          | Common ground               |
| FC-51 IR (pill det) | OUT      | GPIO 23    | Pin 16       | At discharge chute          |
| FC-51 IR (pickup)   | OUT      | GPIO 24    | Pin 18       | At delivery tray            |
| FC-51 IR sensors    | VCC      | —          | Pin 1 (3.3V) | Both sensors                |
| FC-51 IR sensors    | GND      | —          | Pin 9        | Both sensors                |
| Active Buzzer       | Signal   | GPIO 25    | Pin 22       |                             |
| Active Buzzer       | VCC      | —          | Pin 17 (3.3V)|                             |
| Active Buzzer       | GND      | —          | Pin 20       |                             |
| DS3231 RTC          | SDA      | GPIO 2     | Pin 3        | I2C data (fixed)            |
| DS3231 RTC          | SCL      | GPIO 3     | Pin 5        | I2C clock (fixed)           |
| DS3231 RTC          | VCC      | —          | Pin 1 (3.3V) |                             |
| DS3231 RTC          | GND      | —          | Pin 14       |                             |
| Pi Camera v2        | CSI      | —          | CSI port     | Ribbon cable to CSI slot    |
| SIM800L GSM         | TX/RX    | —          | USB port     | Via USB-to-serial adapter   |
| SIM800L GSM         | VCC      | —          | —            | 3.7V LiPo (separate power) |
| SIM800L GSM         | GND      | —          | Common GND   | Share ground with Pi        |

### Wiring Diagram (Text)

```
Raspberry Pi 4B GPIO Header (40-pin) — signal pins in BCM numbering
══════════════════════════════════════════════════════════════════
 Power / Ground
   Pin 1  (3.3V) ─── IR VCC, RTC VCC, Buzzer VCC, I2S mic VDD
   Pin 2/4 (5V)  ─── Servo VCC ×6  (better: external 5V supply, see note)
   Pin 6/9/14/20/25/30/34/39 (GND) ─── common ground for ALL modules
 Servos (one rotating cylinder per compartment)
   GPIO12 (Pin 32) ─── Compartment 0 servo signal
   GPIO13 (Pin 33) ─── Compartment 1 servo signal
   GPIO16 (Pin 36) ─── Compartment 2 servo signal
   GPIO17 (Pin 11) ─── Compartment 3 servo signal
   GPIO26 (Pin 37) ─── Compartment 4 servo signal
   GPIO27 (Pin 13) ─── Compartment 5 servo signal
 Sensors / feedback
   GPIO23 (Pin 16) ─── IR sensor 1 OUT (discharge chute — drop confirm)
   GPIO24 (Pin 18) ─── IR sensor 2 OUT (delivery base — pickup confirm)
   GPIO25 (Pin 22) ─── Buzzer signal
 I2C — DS3231 RTC
   GPIO2  (Pin 3, SDA) ─── DS3231 SDA
   GPIO3  (Pin 5, SCL) ─── DS3231 SCL
 Voice mic — INMP441 I2S (optional; only if voice.enabled)
   GPIO18 (Pin 12, BCLK) ─── mic SCK
   GPIO19 (Pin 35, LRCLK)─── mic WS
   GPIO20 (Pin 38, DIN)  ─── mic SD     (mic L/R → GND = left channel)
 Camera / GSM
   CSI port ─── Pi Camera v2 ribbon cable
   USB port ─── USB-to-Serial adapter → SIM800L TX/RX
══════════════════════════════════════════════════════════════════
 SIM800L: powered by a separate 3.7V LiPo; share GND with the Pi.
 POWER NOTE: six servos can exceed the Pi's onboard 5V current limit.
 Drive the servos from an external 5V supply and tie that supply's
 GND to a Pi GND pin (common ground) — do NOT power 6 servos from the Pi.
```

### Important Notes

1. **SIM800L Power**: Must be powered by a separate 3.7V LiPo battery (NOT from the Pi's 3.3V or 5V rail). The SIM800L draws up to 2A during transmission bursts.
2. **Common Ground**: The SIM800L's GND must be connected to the Pi's GND for serial communication to work.
3. **I2C Setup**: Enable I2C on the Pi via `sudo raspi-config → Interface Options → I2C → Enable`. Verify with `sudo i2cdetect -y 1`.
4. **Camera**: Enable via `sudo raspi-config → Interface Options → Camera → Enable`.
5. **IR Sensor Orientation**: Mount the FC-51 at the discharge chute pointing into the pill path, and the second at the delivery tray opening.

---

## Raspberry Pi 4B — Step-by-Step Deployment

Follow these steps in order once you have the hardware. Commands assume
Raspberry Pi OS **Bookworm 64-bit** and the default username `pi`. If your
username is different, substitute it everywhere (and in
`services/pillsafe.service`). The guide installs into `/home/pi/pillsafe`.

### What you need
- Raspberry Pi 4B + quality USB-C power supply + microSD card (16 GB+)
- Pi Camera v2 (CSI ribbon), DS3231 RTC (+ CR2032 backup cell), active buzzer
- 2× FC-51 IR sensors, 6× 360°/continuous-rotation servos + **external 5V supply**
- SIM800L GSM + USB-to-serial adapter + 3.7V LiPo (with a live SIM)
- (Optional, for voice) INMP441 I2S microphone
- Jumper wires / breadboard or a wiring harness

### Step 1 — Flash Raspberry Pi OS
1. Install **Raspberry Pi Imager** on your PC.
2. Choose *Raspberry Pi OS (64-bit)* → your microSD card.
3. Click the gear / *Edit Settings* and pre-configure:
   - Hostname (e.g. `pillsafe`), enable **SSH**, set username `pi` + a password.
   - Wi-Fi SSID/password (so the first boot has internet) and your locale/timezone.
4. Write the card, insert it into the Pi, and boot.

### Step 2 — First boot, update, correct clock
SSH in (`ssh pi@pillsafe.local`) or use a monitor, then:
```bash
sudo apt update && sudo apt full-upgrade -y
timedatectl        # confirm the system time/date is correct (needed to seed the RTC later)
```

### Step 3 — Enable the hardware interfaces
```bash
sudo raspi-config
#  Interface Options → Camera      → Enable
#  Interface Options → I2C         → Enable
#  Interface Options → Serial Port → login shell over serial: NO, serial hardware: YES
```
For the **optional voice mic**, enable I2S by adding this line to
`/boot/firmware/config.txt` (Bookworm path) and reboot:
```bash
echo "dtparam=i2s=on" | sudo tee -a /boot/firmware/config.txt
# Then add the overlay for your INMP441 board per its datasheet, and reboot.
sudo reboot
```

### Step 4 — Install system packages
```bash
sudo apt install -y python3-pip python3-opencv python3-picamera2 \
                    i2c-tools git wget libportaudio2 libsndfile1
```

### Step 5 — Get the PillSafe code onto the Pi
```bash
cd /home/pi
git clone <your-repo-url> pillsafe        # or copy the project folder here via scp
cd /home/pi/pillsafe
```
> If you copy instead of clone, make sure the folder ends up at exactly
> `/home/pi/pillsafe` so it matches the service file in Step 14.

### Step 6 — Install the Python dependencies
```bash
cd /home/pi/pillsafe
pip install -r requirements.txt --break-system-packages

# FaceNet needs a TFLite runtime (ARM64). Try tflite-runtime first;
# fall back to ai-edge-litert if no wheel is available for your Python:
pip install tflite-runtime --break-system-packages || \
pip install ai-edge-litert --break-system-packages
```
> The voice deps (`sounddevice`, `librosa`) are heavy. If you are **not** using
> voice auth, set `voice.enabled: false` in `config.yaml` — the system runs
> fine without them.

### Step 7 — Download the face-recognition model
```bash
bash scripts/download_model.sh          # saves data/models/mobilefacenet.tflite
```

### Step 8 — Wire the hardware and verify each part
Wire everything per the **Hardware Wiring Guide** above (mind the servo power
note). Then verify:
```bash
i2cdetect -y 1          # DS3231 should appear at address 0x68
ls /dev/ttyUSB*         # the SIM800L USB-serial adapter, e.g. /dev/ttyUSB0
libcamera-hello -t 2000 # camera preview (or 'rpicam-hello' on newer OS)
arecord -l              # (voice only) the INMP441 should be listed
```

### Step 9 — Configure `config.yaml`
Edit `config.yaml` and set at minimum:
- `api.token` — replace `CHANGE_ME_ON_FIRST_SETUP` with a strong token (or export
  `PILLSAFE_API_TOKEN` instead; it overrides the file).
- `alerts.serial_port` — match Step 8 (e.g. `/dev/ttyUSB0`).
- `servo.pins` — confirm they match how you wired the six servos.
- `hotspot.ssid` / `hotspot.password` — your access-point name and WPA2 passphrase.
- `voice.enabled` (+ `voice.device_index` from `arecord -l`) if using voice.

### Step 10 — Set the DS3231 RTC time
With the system clock correct (Step 2), write it into the RTC once:
```bash
cd /home/pi/pillsafe
python3 -c "from utils.config import load_config; load_config(); \
from hardware.rtc import RealTimeClock; from datetime import datetime; \
print('RTC set:', RealTimeClock().set_time(datetime.now()))"
```
The DS3231's backup cell keeps time across power loss, so schedules fire
correctly even offline.

### Step 11 — (Optional) Turn the Pi into a Wi-Fi hotspot
So a caregiver's phone can connect directly with no router:
```bash
sudo bash services/setup_hotspot.sh
# Phone connects to SSID 'PillSafe-AP'; the API is then at http://192.168.4.1:5000
# To undo:  sudo bash services/setup_hotspot.sh --disable
```

### Step 12 — Enrol users and stock the slots
Register + capture faces (and voice). For a **headless** Pi use the CLI tool;
if a monitor is attached you can use the live-preview tool instead:
```bash
python3 -m enrollment.enrol_user      # headless-friendly
# or, with a screen attached:
python3 enroll_new_user.py            # live camera preview + progress bar
```
Then load the initial pill counts per slot (optional but enables low-stock
alerts) via the API — see Step 15, or POST to `/inventory`.

### Step 13 — Test run (foreground)
```bash
cd /home/pi/pillsafe
python3 main.py
```
Watch the log. In another terminal, confirm the API answers:
```bash
curl http://localhost:5000/health
```
Press `Ctrl+C` to stop once it looks healthy.

### Step 14 — Install as a boot service (auto-start)
```bash
sudo cp services/pillsafe.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pillsafe      # start automatically on every boot
sudo systemctl start pillsafe
sudo systemctl status pillsafe      # should show 'active (running)'
journalctl -u pillsafe -f           # live logs
```
> If your username isn't `pi`, edit `User=` and the paths in
> `/etc/systemd/system/pillsafe.service`, then `daemon-reload` and restart.

### Step 15 — Connect the mobile app
1. Connect the phone to the Pi's Wi-Fi (`PillSafe-AP`) or the same LAN.
2. In the app settings, set the API base URL (`http://192.168.4.1:5000` for the
   hotspot) and the Bearer token from Step 9.
3. Create users/schedules, trigger enrolment, and use **Verify Now** at dose time.

### Troubleshooting

| Symptom | Check |
|---------|-------|
| RTC not found | `i2cdetect -y 1` shows nothing at 0x68 → re-check SDA/SCL/power; is I2C enabled? |
| "TFLite model not loaded" | Run Step 7; confirm `data/models/mobilefacenet.tflite` exists |
| Camera errors | `libcamera-hello`; ensure the CSI ribbon is seated and Camera is enabled |
| No SMS sent | `ls /dev/ttyUSB*` matches `alerts.serial_port`; SIM800L has its own 3.7V power + shared GND + signal |
| Servos jitter / brown-out | Use the external 5V supply (not the Pi) for the servos; share GND |
| Voice disabled at start | Install `sounddevice`/`librosa`, check `arecord -l`, set `voice.device_index` |
| Service won't start | `journalctl -u pillsafe -e`; verify `User=`/paths in the unit file |
| API returns 401 | Send `Authorization: Bearer <token>` matching `api.token` / `PILLSAFE_API_TOKEN` |

---

## API Reference

All endpoints (except `/health`) require `Authorization: Bearer <token>` header.

| Method | Endpoint               | Description                                |
|--------|------------------------|--------------------------------------------|
| GET    | /health                | System status (no auth)                    |
| GET    | /users                 | List all users                             |
| POST   | /users                 | Create user (full_name, caregiver_phone, compartment_index) |
| PUT    | /users/{id}            | Update user                                |
| DELETE | /users/{id}            | Delete user + facial data                  |
| POST   | /users/{id}/enrol      | Trigger facial enrolment                   |
| GET    | /schedules             | List schedules (?user_id= filter)          |
| POST   | /schedules             | Create schedule (user_id, medication_name, dose_time, [slot_index, dosage, pills_per_dose, repeat_days]) |
| PUT    | /schedules/{id}        | Update schedule (incl. slot_index, dosage, pills_per_dose, repeat_days) |
| DELETE | /schedules/{id}        | Delete schedule                            |
| GET    | /adherence             | Get logs (?user_id=&date= filters)         |
| POST   | /adherence/{id}/ack    | Acknowledge a missed-dose event            |
| POST   | /dispense/request      | "Verify Now" — submit user_id, [schedule_id], auth_mode (face/voice) |
| GET    | /inventory             | List inventory (?compartment_index= filter)|
| POST   | /inventory             | Set/update a slot's count (compartment_index, slot_index, pill_count, [medication_name, low_threshold]) |
| GET    | /inventory/low         | List slots at/below their low threshold     |
| GET    | /notifications         | Event feed (?user_id=&unread=true)          |
| POST   | /notifications/{id}/read | Mark a notification read                  |
| GET    | /voice/challenge       | Random voice passphrase to speak            |
| GET    | /users/{id}/enrol/status | Face + voice enrolment flags              |

> `repeat_days` is a CSV of weekday integers (`0`=Mon … `6`=Sun); empty/omitted means every day. `auth_mode` selects face or voice for that dose.

---

## Medication Storage (Compartments & Slots)

- **6 compartments**, each permanently assigned to one patient (`Users.compartment_index`, 0–5).
- Each compartment is a rotating cylinder with **9 angular slots** (~40° apart). A slot holds one medication / scheduled dose (`Schedules.slot_index`, 0–8).
- Each slot can be **inventory-tracked** (`Inventory` table): a pill count with a low-stock threshold that triggers a `LOW_INVENTORY` notification + SMS.

## Dispensing Mechanism (no gate)

Dispensing is **rotation-only**. Each compartment has its own servo. When a dose is due, that compartment's servo rotates so the target slot aligns with the compartment's fixed **drop hole**; the pill falls by **gravity through a delivery tube to the collection base**. The IR sensors confirm the **drop** and the **pickup**.

## Operational Workflow

```
RTC polls every 60s → Schedule match (time + repeat-day)? → REMINDER notif + buzzer → Camera ON
  → App sends "Verify Now" (POST /dispense/request) → FaceNet/voice verify the SCHEDULED patient
    → ACCEPTED: rotate compartment→slot → IR confirm drop → IR confirm pickup
               → Log TAKEN → decrement inventory → DISPENSED notif (+ LOW_INVENTORY if needed)
    → REJECTED: Log REJECTED → REJECTED notif → SMS to caregiver
    → No Verify Now before grace deadline: Log MISSED → MISSED notif → SMS
```

> Set `dispense.require_verify_request: false` in `config.yaml` for fully autonomous, timer-driven verification (no app handshake).

---

## Key Configuration Parameters

| Parameter                       | Default | Description                                  |
|---------------------------------|---------|----------------------------------------------|
| face.confidence_threshold       | 60      | FaceNet match score 0–100 = (1−cosine_dist)×100 (higher = stricter) |
| face.distance_threshold         | 0.6     | Max cosine distance for a valid match         |
| face.max_retries                | 8       | Verification attempts before lockout         |
| face.sample_count               | 50      | Images captured during enrolment             |
| schedule.grace_period_minutes   | 15      | Window before marking dose as MISSED         |
| schedule.poll_interval_seconds  | 60      | How often the scheduler checks the RTC       |
| dispense.require_verify_request | true    | Wait for the app's "Verify Now" before auth   |
| alerts.max_sms_per_event        | 2       | Maximum SMS alerts per missed dose           |
| alerts.retry_interval_minutes   | 60      | Wait time before sending 2nd SMS             |
| servo.num_compartments          | 6       | Number of compartments (one per patient)     |
| servo.num_slots                 | 9       | Angular slots per compartment (~40° each)    |
| servo.pins                      | [12,13,16,17,26,27] | One PWM signal pin per compartment |
