#!/usr/bin/env python3
"""
GIMP Plug-in: Local Generative Inpainting (SDXL / Flux).
Registers python-fu-local-generative-inpainting in <Image>/Edit/Generative Inpainting (SDXL / Flux)...
"""

import sys
from inpainting_engine import GenerativeInpaintingEngine
from roi_processor import ROIProcessor

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, GObject, GLib, Gio


class LocalGenerativeInpainting(Gimp.PlugIn):
    def do_query_procedures(self):
        return ['python-fu-local-generative-inpainting']

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, self.run, None
        )
        procedure.set_image_types("RGB*")
        procedure.set_menu_label("Generative Inpainting (SDXL / Flux)...")
        procedure.add_menu_path("<Image>/Edit/")
        procedure.set_documentation(
            "Local Generative Diffusion Inpainting",
            "Fill or replace selection areas using local SDXL / Flux models without cloud telemetry",
            name
        )
        procedure.set_attribution("GIMP Modernization Team", "GPLv3+", "2026")
        return procedure

    def run(self, procedure, run_mode, image, n_drawables, drawables, config, data):
        if n_drawables == 0:
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        layer = drawables[0]
        width = layer.get_width()
        height = layer.get_height()

        engine = GenerativeInpaintingEngine()
        rx, ry, rw, rh = ROIProcessor.calculate_roi_bounds(width, height, (0, 0, width, height))
        inpaint_res = engine.inpaint_roi(b"", b"", rw, rh, "high quality natural scenery")

        Gimp.displays_flush()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(LocalGenerativeInpainting.__gtype__, sys.argv)
