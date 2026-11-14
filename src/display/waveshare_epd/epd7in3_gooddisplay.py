"""Adapt Cadre's GDEP073E01 driver to InkyPi's EPD interface."""
import numpy as np
from PIL import Image

from .good_display_gdep073e01 import GDEP073E01


class EPD:
    width = GDEP073E01.WIDTH
    height = GDEP073E01.HEIGHT

    def __init__(self):
        self.panel = GDEP073E01(dc_pin=25, reset_pin=17, busy_pin=24)
        self.palette = Image.new("P", (1, 1))
        self.palette.putpalette([
            0, 0, 0, 255, 255, 255, 255, 255, 0,
            255, 0, 0, 0, 0, 255, 0, 255, 0,
        ])

    def init(self):
        # Cadre initializes the panel when it sends an image.
        pass

    def Clear(self):
        # A full Spectra 6 refresh already replaces the previous image.
        pass

    def getbuffer(self, image):
        if image.size == (self.height, self.width):
            image = image.rotate(90, expand=True)
        return np.asarray(image.convert("RGB").quantize(palette=self.palette))

    def display(self, image):
        self.panel.buf[:] = image
        self.panel.show()

    def sleep(self):
        # Cadre puts the panel into deep sleep at the end of show().
        pass
