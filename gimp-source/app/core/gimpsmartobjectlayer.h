/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimpsmartobjectlayer.h
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

#include "gimplayer.h"
#include "gimpsmartobject.h"

#define GIMP_TYPE_SMART_OBJECT_LAYER            (gimp_smart_object_layer_get_type ())
#define GIMP_SMART_OBJECT_LAYER(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), GIMP_TYPE_SMART_OBJECT_LAYER, GimpSmartObjectLayer))
#define GIMP_SMART_OBJECT_LAYER_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), GIMP_TYPE_SMART_OBJECT_LAYER, GimpSmartObjectLayerClass))
#define GIMP_IS_SMART_OBJECT_LAYER(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), GIMP_TYPE_SMART_OBJECT_LAYER))
#define GIMP_IS_SMART_OBJECT_LAYER_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), GIMP_TYPE_SMART_OBJECT_LAYER))
#define GIMP_SMART_OBJECT_LAYER_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), GIMP_TYPE_SMART_OBJECT_LAYER, GimpSmartObjectLayerClass))

typedef struct _GimpSmartObjectLayerClass GimpSmartObjectLayerClass;

struct _GimpSmartObjectLayer
{
  GimpLayer              parent_instance;

  GimpSmartObject       *smart_object;
  GimpMatrix3            transform_matrix;
  GimpInterpolationType  interpolation;
};

struct _GimpSmartObjectLayerClass
{
  GimpLayerClass parent_class;
};

GType       gimp_smart_object_layer_get_type      (void);

GimpLayer * gimp_smart_object_layer_new           (GimpImage             *image,
                                                   GimpSmartObject       *so);

gboolean    gimp_smart_object_layer_set_transform (GimpSmartObjectLayer  *layer,
                                                   const GimpMatrix3     *matrix,
                                                   GimpInterpolationType  interpolation,
                                                   gboolean               push_undo);
