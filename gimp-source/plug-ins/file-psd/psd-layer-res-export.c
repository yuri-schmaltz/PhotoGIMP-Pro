/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * psd-layer-res-export.c
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

#include "config.h"

#include <libgimp/gimp.h>
#include "psd.h"
#include "psd-util.h"
#include "psd-layer-res-export.h"

gint
psd_write_layer_effects_res (GOutputStream  *output,
                             GimpLayer      *layer,
                             GError        **error)
{
  /* Write 8BIMlfx2 layer effects descriptor block */
  const gchar sig[] = "8BIM";
  const gchar key[] = "lfx2";
  guint32     len   = 0;

  if (! g_output_stream_write_all (output, sig, 4, NULL, NULL, error))
    return -1;
  if (! g_output_stream_write_all (output, key, 4, NULL, NULL, error))
    return -1;
  if (! psd_write_gint32 (output, len, error))
    return -1;

  return 12;
}

gint
psd_write_adjustment_layer_res (GOutputStream  *output,
                                GimpLayer      *layer,
                                GError        **error)
{
  /* Write 8BIMcurv / 8BIMlevl adjustment layer block */
  const gchar sig[] = "8BIM";
  const gchar key[] = "curv";
  guint32     len   = 0;

  if (! g_output_stream_write_all (output, sig, 4, NULL, NULL, error))
    return -1;
  if (! g_output_stream_write_all (output, key, 4, NULL, NULL, error))
    return -1;
  if (! psd_write_gint32 (output, len, error))
    return -1;

  return 12;
}

gint
psd_write_smart_object_res (GOutputStream  *output,
                            GimpLayer      *layer,
                            GError        **error)
{
  /* Write 8BIMSoLd smart object descriptor block */
  const gchar sig[] = "8BIM";
  const gchar key[] = "SoLd";
  guint32     len   = 0;

  if (! g_output_stream_write_all (output, sig, 4, NULL, NULL, error))
    return -1;
  if (! g_output_stream_write_all (output, key, 4, NULL, NULL, error))
    return -1;
  if (! psd_write_gint32 (output, len, error))
    return -1;

  return 12;
}
