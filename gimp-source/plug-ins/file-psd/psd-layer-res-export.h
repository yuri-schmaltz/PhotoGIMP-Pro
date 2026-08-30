/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * psd-layer-res-export.h
 * Copyright (C) 2026 GIMP Modernization Team
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#ifndef __PSD_LAYER_RES_EXPORT_H__
#define __PSD_LAYER_RES_EXPORT_H__

#include <gio/gio.h>
#include <libgimp/gimp.h>
#include "psd.h"

gint psd_write_layer_effects_res    (GOutputStream  *output,
                                     GimpLayer      *layer,
                                     GError        **error);

gint psd_write_adjustment_layer_res (GOutputStream  *output,
                                     GimpLayer      *layer,
                                     GError        **error);

gint psd_write_smart_object_res     (GOutputStream  *output,
                                     GimpLayer      *layer,
                                     GError        **error);

#endif /* __PSD_LAYER_RES_EXPORT_H__ */
