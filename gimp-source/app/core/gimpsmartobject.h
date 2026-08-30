/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimpsmartobject.h
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

#pragma once

#include "core-types.h"
#include "gimpobject.h"

#define GIMP_TYPE_SMART_OBJECT            (gimp_smart_object_get_type ())
#define GIMP_SMART_OBJECT(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), GIMP_TYPE_SMART_OBJECT, GimpSmartObject))
#define GIMP_SMART_OBJECT_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), GIMP_TYPE_SMART_OBJECT, GimpSmartObjectClass))
#define GIMP_IS_SMART_OBJECT(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), GIMP_TYPE_SMART_OBJECT))
#define GIMP_IS_SMART_OBJECT_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), GIMP_TYPE_SMART_OBJECT))
#define GIMP_SMART_OBJECT_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), GIMP_TYPE_SMART_OBJECT, GimpSmartObjectClass))

typedef struct _GimpSmartObjectClass GimpSmartObjectClass;

typedef enum
{
  GIMP_SMART_OBJECT_EMBEDDED,
  GIMP_SMART_OBJECT_LINKED
} GimpSmartObjectType;

typedef enum
{
  GIMP_SMART_OBJECT_FORMAT_SVG,
  GIMP_SMART_OBJECT_FORMAT_PSD,
  GIMP_SMART_OBJECT_FORMAT_RAW,
  GIMP_SMART_OBJECT_FORMAT_RASTER,
  GIMP_SMART_OBJECT_FORMAT_XCF
} GimpSmartObjectFormat;

struct _GimpSmartObject
{
  GimpObject             parent_instance;

  Gimp                  *gimp;
  GimpSmartObjectType    type;
  GimpSmartObjectFormat  format;

  GBytes                *payload;
  gchar                 *original_filename;
  gchar                 *mime_type;

  GFile                 *file;
  GFileMonitor          *monitor;

  GeglBuffer            *master_buffer;
  gint                   master_width;
  gint                   master_height;
  gboolean               is_vector;

  gboolean               broken;
};

struct _GimpSmartObjectClass
{
  GimpObjectClass parent_class;

  void (* changed) (GimpSmartObject *so);
};

GType             gimp_smart_object_get_type      (void);

GimpSmartObject * gimp_smart_object_new_from_file (Gimp                 *gimp,
                                                   GFile                *file,
                                                   gboolean              embed,
                                                   GError              **error);

GimpSmartObject * gimp_smart_object_new_embedded  (Gimp                 *gimp,
                                                   GBytes               *payload,
                                                   const gchar          *filename,
                                                   const gchar          *mime_type,
                                                   GimpSmartObjectFormat format);

gboolean          gimp_smart_object_embed         (GimpSmartObject      *so,
                                                   GError              **error);

gboolean          gimp_smart_object_relink        (GimpSmartObject      *so,
                                                   GFile                *new_file,
                                                   GError              **error);

void              gimp_smart_object_render_at_scale (GimpSmartObject    *so,
                                                     gdouble             scale_x,
                                                     gdouble             scale_y,
                                                     GeglBuffer        **out_buffer);
