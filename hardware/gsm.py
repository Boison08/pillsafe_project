"""
PillSafe — GSM SMS Module (SIM800L via USB-to-serial)
Connection: USB-to-Serial adapter → Pi USB port (/dev/ttyUSB0)
SIM800L VCC → 3.7V LiPo (separate power), GND → shared with Pi.
"""

import time
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.gsm")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.warning("pyserial not available — SMS in simulation mode")


class GSMModule:
    def __init__(self):
        cfg = get_config()
        self.port = cfg.alerts.serial_port
        self.baud_rate = cfg.alerts.baud_rate
        self.timeout = cfg.alerts.sms_timeout
        self.max_sms_per_event = cfg.alerts.max_sms_per_event
        self._serial = None
        self._initialised = False
        self._connect()

    def _connect(self):
        if not SERIAL_AVAILABLE:
            logger.info("GSM simulated on %s", self.port)
            return
        try:
            self._serial = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            time.sleep(2)
            self._initialised = self._check_module()
        except serial.SerialException as e:
            logger.error("Serial port %s error: %s", self.port, e)

    def _send_at(self, command: str, expected: str = "OK",
                 timeout: float | None = None) -> tuple[bool, str]:
        if self._serial is None:
            return True, "OK"
        self._serial.write((command + "\r\n").encode())
        time.sleep(0.5)
        response = ""
        end_time = time.time() + (timeout or self.timeout)
        while time.time() < end_time:
            if self._serial.in_waiting:
                response += self._serial.read(self._serial.in_waiting).decode(errors="ignore")
                if expected in response or "ERROR" in response:
                    break
            time.sleep(0.1)
        return expected in response, response

    def _check_module(self) -> bool:
        ok, _ = self._send_at("AT")
        if ok:
            self._send_at("AT+CMGF=1")
            logger.info("SIM800L responsive")
        return ok

    def send_sms(self, phone_number: str, message: str) -> bool:
        logger.info("SMS to %s: %s", phone_number, message[:50])
        if not SERIAL_AVAILABLE or self._serial is None:
            logger.info("[SIM] SMS sent to %s", phone_number)
            return True
        ok, _ = self._send_at("AT+CMGF=1")
        if not ok:
            return False
        ok, _ = self._send_at(f'AT+CMGS="{phone_number}"', expected=">")
        if not ok:
            return False
        self._serial.write((message + chr(26)).encode())
        time.sleep(3)
        response = ""
        end_time = time.time() + self.timeout
        while time.time() < end_time:
            if self._serial.in_waiting:
                response += self._serial.read(self._serial.in_waiting).decode(errors="ignore")
                if "+CMGS" in response:
                    return True
                if "ERROR" in response:
                    return False
            time.sleep(0.1)
        return False

    def send_missed_dose_alert(self, patient_name: str, medication_name: str,
                                scheduled_time: str, caregiver_phone: str) -> bool:
        message = (
            f"[PillSafe ALERT] Missed Dose\n"
            f"Patient: {patient_name}\nMedication: {medication_name}\n"
            f"Scheduled: {scheduled_time}\nReply '1' or 'ACK' to acknowledge."
        )
        return self.send_sms(caregiver_phone, message)

    def send_unauthorized_alert(self, caregiver_phone: str, scheduled_time: str) -> bool:
        message = (
            f"[PillSafe ALERT] Unauthorized Access at {scheduled_time}.\n"
            f"Dispensing sequence locked."
        )
        return self.send_sms(caregiver_phone, message)

    def check_signal(self) -> int | None:
        ok, response = self._send_at("AT+CSQ")
        if ok and "+CSQ:" in response:
            try:
                return int(response.split("+CSQ:")[1].split(",")[0].strip())
            except (ValueError, IndexError):
                pass
        return None

    @property
    def is_available(self) -> bool:
        return self._initialised or not SERIAL_AVAILABLE

    def cleanup(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
