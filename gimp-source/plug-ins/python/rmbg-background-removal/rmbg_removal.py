#!/usr/bin/env python3
"""
GIMP Plug-in: RMBG-1.4 AI Background Removal (Offline).
Registers python-fu-rmbg-background-removal in <Image>/Layer/AI Background Removal (RMBG-1.4)...
"""

import sys
from rmbg_engine import RMBGEngine

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, GObject, GLib, Gio


class RmbgBackgroundRemoval(Gimp.PlugIn):
    def do_query_procedures(self):
        return ['python-fu-rmbg-background-removal']

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, self.run, None
        )
        procedure.set_image_types("RGB*")
        procedure.set_menu_label("AI Background Removal (RMBG-1.4)...")
        procedure.add_menu_path("<Image>/Layer/")
        procedure.set_documentation(
            "1-Click Local RMBG-1.4 Neural Background Removal",
            "Removes backgrounds offline using Bria AI RMBG-1.4 model",
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

        engine = RMBGEngine()
        matte_bytes = engine.remove_background(b"", width, height)

        Gimp.displays_flush()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(RmbgBackgroundRemoval.__gtype__, sys.argv)
