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
│   ├── dispenser.py               # SG90 servo carousel controller (6 compartments)
│   ├── ir_sensor.py               # FC-51 IR sensors (pill detect + pickup)
│   ├── buzzer.py                  # Active buzzer for audio feedback
│   ├── rtc.py                     # DS3231 RTC via I2C
│   └── gsm.py                     # SIM800L SMS via USB-to-serial
│
├── scheduler/                     # Time-based dispensing triggers
│   └── schedule_controller.py     # RTC polling + DispenseEvent generation
│
├── database/                      # SQLite data layer
│   ├── schema.sql                 # Table definitions (Users, Schedules, AdherenceLog)
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
Raspberry Pi 4B GPIO Header (40-pin)
═══════════════════════════════════════════════
 Pin 1  (3.3V)  ──── IR sensors VCC, RTC VCC, Buzzer VCC
 Pin 2  (5V)    ──── Servo VCC
 Pin 3  (SDA)   ──── DS3231 SDA
 Pin 5  (SCL)   ──── DS3231 SCL
 Pin 6  (GND)   ──── Servo GND
 Pin 9  (GND)   ──── IR sensors GND
 Pin 12 (GPIO18)──── Servo signal (orange wire)
 Pin 14 (GND)   ──── DS3231 GND
 Pin 16 (GPIO23)──── IR sensor 1 OUT (discharge chute)
 Pin 17 (3.3V)  ──── Buzzer VCC
 Pin 18 (GPIO24)──── IR sensor 2 OUT (delivery tray)
 Pin 20 (GND)   ──── Buzzer GND
 Pin 22 (GPIO25)──── Buzzer signal
 USB port       ──── USB-to-Serial → SIM800L TX/RX
 CSI port       ──── Pi Camera v2 ribbon cable
═══════════════════════════════════════════════
 SIM800L: powered by separate 3.7V LiPo battery.
 Share GND with Pi for signal reference.
```

### Important Notes

1. **SIM800L Power**: Must be powered by a separate 3.7V LiPo battery (NOT from the Pi's 3.3V or 5V rail). The SIM800L draws up to 2A during transmission bursts.
2. **Common Ground**: The SIM800L's GND must be connected to the Pi's GND for serial communication to work.
3. **I2C Setup**: Enable I2C on the Pi via `sudo raspi-config → Interface Options → I2C → Enable`. Verify with `sudo i2cdetect -y 1`.
4. **Camera**: Enable via `sudo raspi-config → Interface Options → Camera → Enable`.
5. **IR Sensor Orientation**: Mount the FC-51 at the discharge chute pointing into the pill path, and the second at the delivery tray opening.

---

## Setup & Installation

### 1. System Prerequisites (Raspberry Pi OS Bookworm 64-bit)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-opencv python3-picamera2 i2c-tools
```

### 2. Enable Interfaces

```bash
sudo raspi-config
# → Interface Options → Camera → Enable
# → Interface Options → I2C  → Enable
# → Interface Options → Serial Port → Login shell: No, Serial hardware: Yes
```

### 3. Install Python Dependencies

```bash
cd ~/pillsafe
pip install -r requirements.txt --break-system-packages
```

### 4. Configure the System

Edit `config.yaml` to set:
- `api.token` — change from `CHANGE_ME_ON_FIRST_SETUP` to a secure token (or set the `PILLSAFE_API_TOKEN` environment variable, which overrides the config). The server logs a warning while the default is in use.
- `alerts.serial_port` — verify your USB-to-serial port (`ls /dev/ttyUSB*`)
- Adjust `face.confidence_threshold` if needed (lower = stricter)

### 5. Initial User Enrolment

```bash
# Run the CLI enrolment tool
python3 -m enrollment.enrol_user
```

### 6. Run the System

```bash
# Direct execution
python3 main.py

# Or install as a system service (auto-start on boot)
sudo cp services/pillsafe.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pillsafe
sudo systemctl start pillsafe
```

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

Dispensing is **rotation-only**. Each compartment has its own servo. When a dose is due, that compartment's servo rotates so the target slot aligns with the compartment's fixed **drop hole**; the pill falls by **gravity through a delivery tube to the collection base**. The IR sensors confirm the **drop** and the **pickup**. There is no gate and no gate servo.

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
