#!/usr/bin/env python3
"""
GIMP Plug-in: SAM 2 Magic Selection (Offline AI).
Registers python-fu-sam2-magic-selection in <Image>/Select/Magic Selection (SAM 2)...
"""

import sys
from sam2_engine import SAM2Engine

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, GObject, GLib, Gio


class Sam2MagicSelection(Gimp.PlugIn):
    def do_query_procedures(self):
        return ['python-fu-sam2-magic-selection']

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, self.run, None
        )
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_menu_label("Magic Selection (SAM 2)...")
        procedure.add_menu_path("<Image>/Select/")
        procedure.set_documentation(
            "1-Click Local Object Selection via SAM 2 ONNX",
            "Segment objects offline using Meta SAM 2 neural network",
            name
        )
        procedure.set_attribution("GIMP Modernization Team", "GPLv3+", "2026")
        return procedure

    def run(self, procedure, run_mode, image, n_drawables, drawables, config, data):
        if n_drawables == 0:
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        drawable = drawables[0]
        width = drawable.get_width()
        height = drawable.get_height()

        engine = SAM2Engine()
        mask_bytes = engine.predict_mask_from_points(width, height, [(width / 2.0, height / 2.0, 1)])

        Gimp.displays_flush()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(Sam2MagicSelection.__gtype__, sys.argv)
