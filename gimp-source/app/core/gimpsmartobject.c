/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimpsmartobject.c
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

#include <gegl.h>
#include <gio/gio.h>

#include "libgimpbase/gimpbase.h"

#include "core-types.h"

#include "gimp.h"
#include "gimpsmartobject.h"

enum
{
  CHANGED,
  LAST_SIGNAL
};

static guint smart_object_signals[LAST_SIGNAL] = { 0 };

static void   gimp_smart_object_finalize (GObject *object);

G_DEFINE_TYPE (GimpSmartObject, gimp_smart_object, GIMP_TYPE_OBJECT)

#define parent_class gimp_smart_object_parent_class

static void
gimp_smart_object_class_init (GimpSmartObjectClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->finalize = gimp_smart_object_finalize;

  smart_object_signals[CHANGED] =
    g_signal_new ("changed",
                  G_TYPE_FROM_CLASS (klass),
                  G_SIGNAL_RUN_FIRST,
                  G_STRUCT_OFFSET (GimpSmartObjectClass, changed),
                  NULL, NULL, NULL,
                  G_TYPE_NONE, 0);
}

static void
gimp_smart_object_init (GimpSmartObject *so)
{
  so->gimp = NULL;
  so->type = GIMP_SMART_OBJECT_EMBEDDED;
  so->format = GIMP_SMART_OBJECT_FORMAT_RASTER;
  so->payload = NULL;
  so->original_filename = NULL;
  so->mime_type = NULL;
  so->file = NULL;
  so->monitor = NULL;
  so->master_buffer = NULL;
  so->master_width = 0;
  so->master_height = 0;
  so->is_vector = FALSE;
  so->broken = FALSE;
}

static void
gimp_smart_object_finalize (GObject *object)
{
  GimpSmartObject *so = GIMP_SMART_OBJECT (object);

  if (so->monitor)
    {
      g_file_monitor_cancel (so->monitor);
      g_object_unref (so->monitor);
      so->monitor = NULL;
    }

  g_clear_pointer (&so->payload, g_bytes_unref);
  g_clear_pointer (&so->original_filename, g_free);
  g_clear_pointer (&so->mime_type, g_free);
  g_clear_object (&so->file);
  g_clear_object (&so->master_buffer);

  G_OBJECT_CLASS (parent_class)->finalize (object);
}

GimpSmartObject *
gimp_smart_object_new_from_file (Gimp     *gimp,
                                 GFile    *file,
                                 gboolean  embed,
                                 GError  **error)
{
  GimpSmartObject *so;
  gchar           *path;

  g_return_val_if_fail (G_IS_FILE (file), NULL);

  so = g_object_new (GIMP_TYPE_SMART_OBJECT, NULL);
  so->gimp = gimp;
  so->file = g_object_ref (file);
  path = g_file_get_path (file);
  so->original_filename = g_path_get_basename (path ? path : "smart_object");
  g_free (path);

  if (embed)
    {
      so->type = GIMP_SMART_OBJECT_EMBEDDED;
      so->payload = g_file_load_bytes (file, NULL, NULL, error);
      if (! so->payload)
        {
          g_object_unref (so);
          return NULL;
        }
    }
  else
    {
      so->type = GIMP_SMART_OBJECT_LINKED;
    }

  return so;
}

GimpSmartObject *
gimp_smart_object_new_embedded (Gimp                 *gimp,
                                GBytes               *payload,
                                const gchar          *filename,
                                const gchar          *mime_type,
                                GimpSmartObjectFormat format)
{
  GimpSmartObject *so;

  g_return_val_if_fail (payload != NULL, NULL);

  so = g_object_new (GIMP_TYPE_SMART_OBJECT, NULL);
  so->gimp = gimp;
  so->type = GIMP_SMART_OBJECT_EMBEDDED;
  so->format = format;
  so->payload = g_bytes_ref (payload);
  so->original_filename = g_strdup (filename ? filename : "embedded_asset");
  so->mime_type = g_strdup (mime_type ? mime_type : "application/octet-stream");

  return so;
}

gboolean
gimp_smart_object_embed (GimpSmartObject  *so,
                         GError          **error)
{
  g_return_val_if_fail (GIMP_IS_SMART_OBJECT (so), FALSE);

  if (so->type == GIMP_SMART_OBJECT_EMBEDDED)
    return TRUE;

  if (so->file)
    {
      GBytes *bytes = g_file_load_bytes (so->file, NULL, NULL, error);
      if (! bytes)
        return FALSE;

      g_clear_pointer (&so->payload, g_bytes_unref);
      so->payload = bytes;
      so->type = GIMP_SMART_OBJECT_EMBEDDED;
      g_clear_object (&so->file);
      return TRUE;
    }

  return FALSE;
}

gboolean
gimp_smart_object_relink (GimpSmartObject  *so,
                          GFile            *new_file,
                          GError          **error)
{
  g_return_val_if_fail (GIMP_IS_SMART_OBJECT (so), FALSE);
  g_return_val_if_fail (G_IS_FILE (new_file), FALSE);

  g_set_object (&so->file, new_file);
  so->type = GIMP_SMART_OBJECT_LINKED;

  g_signal_emit (so, smart_object_signals[CHANGED], 0);

  return TRUE;
}

void
gimp_smart_object_render_at_scale (GimpSmartObject  *so,
                                   gdouble           scale_x,
                                   gdouble           scale_y,
                                   GeglBuffer      **out_buffer)
{
  g_return_if_fail (GIMP_IS_SMART_OBJECT (so));
  g_return_if_fail (out_buffer != NULL);

  if (so->master_buffer)
    *out_buffer = g_object_ref (so->master_buffer);
  else
    *out_buffer = NULL;
}
