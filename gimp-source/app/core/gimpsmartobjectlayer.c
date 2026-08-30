/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimpsmartobjectlayer.c
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
#include <gdk-pixbuf/gdk-pixbuf.h>

#include "libgimpbase/gimpbase.h"
#include "libgimpmath/gimpmath.h"

#include "core-types.h"

#include "gimpimage.h"
#include "gimplayer.h"
#include "gimpsmartobject.h"
#include "gimpsmartobjectlayer.h"

enum
{
  PROP_0,
  PROP_SMART_OBJECT
};

static void   gimp_smart_object_layer_finalize      (GObject      *object);
static void   gimp_smart_object_layer_set_property  (GObject      *object,
                                                     guint         property_id,
                                                     const GValue *value,
                                                     GParamSpec   *pspec);
static void   gimp_smart_object_layer_get_property  (GObject      *object,
                                                     guint         property_id,
                                                     GValue       *value,
                                                     GParamSpec   *pspec);

G_DEFINE_TYPE (GimpSmartObjectLayer, gimp_smart_object_layer, GIMP_TYPE_LAYER)

#define parent_class gimp_smart_object_layer_parent_class

static void
gimp_smart_object_layer_class_init (GimpSmartObjectLayerClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->finalize     = gimp_smart_object_layer_finalize;
  object_class->set_property = gimp_smart_object_layer_set_property;
  object_class->get_property = gimp_smart_object_layer_get_property;

  g_object_class_install_property (object_class, PROP_SMART_OBJECT,
                                   g_param_spec_object ("smart-object",
                                                        NULL, NULL,
                                                        GIMP_TYPE_SMART_OBJECT,
                                                        GIMP_PARAM_READWRITE));
}

static void
gimp_smart_object_layer_init (GimpSmartObjectLayer *layer)
{
  layer->smart_object = NULL;
  gimp_matrix3_identity (&layer->transform_matrix);
  layer->interpolation = GIMP_INTERPOLATION_NOHALO;
}

static void
gimp_smart_object_layer_finalize (GObject *object)
{
  GimpSmartObjectLayer *layer = GIMP_SMART_OBJECT_LAYER (object);

  g_clear_object (&layer->smart_object);

  G_OBJECT_CLASS (parent_class)->finalize (object);
}

static void
gimp_smart_object_layer_set_property (GObject      *object,
                                      guint         property_id,
                                      const GValue *value,
                                      GParamSpec   *pspec)
{
  GimpSmartObjectLayer *layer = GIMP_SMART_OBJECT_LAYER (object);

  switch (property_id)
    {
    case PROP_SMART_OBJECT:
      g_set_object (&layer->smart_object, g_value_get_object (value));
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

static void
gimp_smart_object_layer_get_property (GObject    *object,
                                      guint       property_id,
                                      GValue     *value,
                                      GParamSpec *pspec)
{
  GimpSmartObjectLayer *layer = GIMP_SMART_OBJECT_LAYER (object);

  switch (property_id)
    {
    case PROP_SMART_OBJECT:
      g_value_set_object (value, layer->smart_object);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

GimpLayer *
gimp_smart_object_layer_new (GimpImage       *image,
                             GimpSmartObject *so)
{
  GimpSmartObjectLayer *layer;

  g_return_val_if_fail (GIMP_IS_IMAGE (image), NULL);
  g_return_val_if_fail (GIMP_IS_SMART_OBJECT (so), NULL);

  layer = g_object_new (GIMP_TYPE_SMART_OBJECT_LAYER,
                        "image",        image,
                        "name",         so->original_filename ? so->original_filename : "Smart Object",
                        "smart-object", so,
                        NULL);

  return GIMP_LAYER (layer);
}

gboolean
gimp_smart_object_layer_set_transform (GimpSmartObjectLayer  *layer,
                                       const GimpMatrix3     *matrix,
                                       GimpInterpolationType  interpolation,
                                       gboolean               push_undo)
{
  g_return_val_if_fail (GIMP_IS_SMART_OBJECT_LAYER (layer), FALSE);
  g_return_val_if_fail (matrix != NULL, FALSE);

  layer->transform_matrix = *matrix;
  layer->interpolation = interpolation;

  gimp_drawable_update (GIMP_DRAWABLE (layer), 0, 0,
                        gimp_item_get_width (GIMP_ITEM (layer)),
                        gimp_item_get_height (GIMP_ITEM (layer)));

  return TRUE;
}
