"""
PillSafe — DS3231 Real-Time Clock Interface (I2C)
GPIO: SDA → GPIO 2 / Pin 3, SCL → GPIO 3 / Pin 5
VCC → 3.3V (Pin 1), GND → GND (Pin 14)
"""

from datetime import datetime
from utils.config import get_config
from utils.logger import setup_logger

logger = setup_logger("pillsafe.rtc")

try:
    import smbus2
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    logger.warning("smbus2 not available — RTC using system clock fallback")


def _bcd_to_dec(bcd: int) -> int:
    return (bcd >> 4) * 10 + (bcd & 0x0F)


def _dec_to_bcd(dec: int) -> int:
    return ((dec // 10) << 4) | (dec % 10)


class RealTimeClock:
    REG_SECONDS = 0x00

    def __init__(self):
        cfg = get_config()
        self.bus_num = cfg.rtc.i2c_bus
        self.address = cfg.rtc.i2c_address
        self._bus = None
        if SMBUS_AVAILABLE:
            try:
                self._bus = smbus2.SMBus(self.bus_num)
                logger.info("DS3231 RTC on I2C bus %d, addr 0x%02X", self.bus_num, self.address)
            except Exception as e:
                logger.error("Failed to open I2C: %s", e)

    def get_time(self) -> datetime:
        if self._bus is None:
            return datetime.now()
        try:
            data = self._bus.read_i2c_block_data(self.address, self.REG_SECONDS, 7)
            return datetime(
                2000 + _bcd_to_dec(data[6]),
                _bcd_to_dec(data[5] & 0x1F),
                _bcd_to_dec(data[4]),
                _bcd_to_dec(data[2] & 0x3F),
                _bcd_to_dec(data[1]),
                _bcd_to_dec(data[0] & 0x7F),
            )
        except Exception as e:
            logger.error("RTC read failed: %s", e)
            return datetime.now()

    def set_time(self, dt: datetime) -> bool:
        if self._bus is None:
            return False
        try:
            self._bus.write_i2c_block_data(self.address, self.REG_SECONDS, [
                _dec_to_bcd(dt.second), _dec_to_bcd(dt.minute),
                _dec_to_bcd(dt.hour), _dec_to_bcd(dt.isoweekday()),
                _dec_to_bcd(dt.day), _dec_to_bcd(dt.month),
                _dec_to_bcd(dt.year - 2000),
            ])
            logger.info("RTC set to %s", dt.strftime("%Y-%m-%d %H:%M:%S"))
            return True
        except Exception as e:
            logger.error("RTC write failed: %s", e)
            return False

    def get_time_string(self, fmt: str = "%H:%M") -> str:
        return self.get_time().strftime(fmt)

    @property
    def is_available(self) -> bool:
        return self._bus is not None

    def cleanup(self):
        if self._bus:
            self._bus.close()
