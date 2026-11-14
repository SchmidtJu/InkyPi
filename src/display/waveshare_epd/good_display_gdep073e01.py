import time
import warnings
import numpy
import numpy.typing

import RPi.GPIO as GPIO
import spidev



class GDEP073E01:
    DC_PIN = 22
    RESET_PIN = 27
    BUSY_PIN = 17

    BLACK = 0
    WHITE = 1
    YELLOW = 2
    RED = 3
    # Actually 4 is unused
    BLUE = 4 # Actually 5
    GREEN = 5 # Actually 6

    WIDTH = 800
    HEIGHT = 480

    _PSR = 0x00
    _PWR = 0x01
    _POF = 0x02
    _POFS = 0x03
    _PON = 0x04
    _BTST1 = 0x05
    _BTST2 = 0x06
    _DSLP = 0x07
    _BTST3 = 0x08
    _DTM = 0x10
    _DRF = 0x12
    _IPC = 0x13
    _PLL = 0x30
    _TSE = 0x41
    _CDI = 0x50
    _TCON = 0x60
    _TRES = 0x61
    _VDCS = 0x82
    _T_VDCS = 0x84
    _AGID = 0x86
    _CMDH = 0xAA
    _CCSET = 0xE0
    _PWS = 0xE3
    _TSSET = 0xE6

    _SPI_COMMAND = 0
    _SPI_DATA = 1

    buf: numpy.typing.NDArray[numpy.uint8]

    def __init__(self, *, spi_bus=0, dc_pin=DC_PIN, reset_pin=RESET_PIN, busy_pin=BUSY_PIN):
        """
        :param spi_bus: SPI bus for communication
        :param dc_pin: data/command pin
        :param reset_pin: device reset pin
        :param busy_pin: device busy/wait pin
        """
        self._gpio = None
        self._spi_bus = None

        self.buf = numpy.zeros((GDEP073E01.HEIGHT, GDEP073E01.WIDTH), dtype=numpy.uint8)

        self.spi_bus = spi_bus
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.busy_pin = busy_pin

    def show(self):
        """
        Show buffer on display.
        """
        buf = self.buf.flatten()

        # Remove invalid colors, correct for unused index 4
        buf = numpy.clip(buf, 0, 5)
        buf[buf >= 4] += 1

        buf = ((buf[::2] << 4) & 0xF0) | (buf[1::2] & 0x0F)

        self._update(buf)

    def _setup(self):
        """Set up IO if needed and reset display."""

        if self._gpio is None:
            self._gpio = GPIO
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setwarnings(False)
            self._gpio.setup(self.dc_pin, self._gpio.OUT, initial=self._gpio.LOW, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.reset_pin, self._gpio.OUT, initial=self._gpio.HIGH, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.busy_pin, self._gpio.IN, pull_up_down=self._gpio.PUD_OFF)

        if self._spi_bus is None:
            self._spi_bus = spidev.SpiDev()
            self._spi_bus.open(self.spi_bus, 0)
            self._spi_bus.max_speed_hz = 5000000

        self._gpio.output(self.reset_pin, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.HIGH)
        time.sleep(0.1)

        self._gpio.output(self.reset_pin, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.HIGH)

        self._busy_wait(1.0)

        # Sending init commands to display
        self._send_command(GDEP073E01._CMDH, [0x49, 0x55, 0x20, 0x08, 0x09, 0x18])
        self._send_command(GDEP073E01._PWR, [0x3F, 0x00, 0x32, 0x2A, 0x0E, 0x2A])
        self._send_command(GDEP073E01._PSR, [0x5F, 0x69])
        self._send_command(GDEP073E01._POFS, [0x00, 0x54, 0x00, 0x44])
        self._send_command(GDEP073E01._BTST1, [0x40, 0x1F, 0x1F, 0x2C])
        self._send_command(GDEP073E01._BTST2, [0x6F, 0x1F, 0x16, 0x25])
        self._send_command(GDEP073E01._BTST3, [0x6F, 0x1F, 0x1F, 0x22])
        self._send_command(GDEP073E01._IPC, [0x00, 0x04])
        self._send_command(GDEP073E01._PLL, 0x02)
        self._send_command(GDEP073E01._TSE, 0x00)
        self._send_command(GDEP073E01._CDI, 0x3F)
        self._send_command(GDEP073E01._TCON, [0x02, 0x00])
        self._send_command(GDEP073E01._TRES, [0x03, 0x20, 0x01, 0xE0])
        self._send_command(GDEP073E01._VDCS, 0x1E)
        self._send_command(GDEP073E01._T_VDCS, 0x01)
        self._send_command(GDEP073E01._AGID, 0x00)
        self._send_command(GDEP073E01._PWS, 0x2F)
        self._send_command(GDEP073E01._CCSET, 0x00)
        self._send_command(GDEP073E01._TSSET, 0x00)

    def _busy_wait(self, timeout):
        if self._gpio.input(self.busy_pin):
            warnings.warn(f'Busy Wait: Held high. Waiting for {timeout:0.2f}s', stacklevel=2)
            time.sleep(timeout)
            return

        t_start = time.time()
        while not self._gpio.input(self.busy_pin):
            time.sleep(0.01)
            if time.time() - t_start >= timeout:
                warnings.warn(f'Busy Wait: Timed out after {time.time() - t_start:0.2f}s', stacklevel=2)
                return

    def _update(self, buf):
        self._setup()

        self._send_command(GDEP073E01._DTM, buf)

        self._send_command(GDEP073E01._PON)
        self._busy_wait(0.4)

        self._send_command(GDEP073E01._DRF, 0x00)
        self._busy_wait(45.0)

        self._send_command(GDEP073E01._POF, 0x00)
        self._busy_wait(0.4)

        self._sleep()

    def _spi_write(self, dc, data):
        self._gpio.output(self.dc_pin, dc)
        self._spi_bus.writebytes2(data)

    def _send_command(self, command, data=None):
        self._spi_write(GDEP073E01._SPI_COMMAND, [command])
        if data is not None:
            self._send_data(data)

    def _send_data(self, data):
        try:
            _ = iter(data)
        except TypeError:
            data = [data]
        self._spi_write(GDEP073E01._SPI_DATA, data)

    def _sleep(self):
        self._send_command(GDEP073E01._DSLP, 0xA5)


