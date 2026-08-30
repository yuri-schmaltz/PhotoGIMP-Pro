/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimpadjustmentlayer.h
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

#define GIMP_TYPE_ADJUSTMENT_LAYER            (gimp_adjustment_layer_get_type ())
#define GIMP_ADJUSTMENT_LAYER(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), GIMP_TYPE_ADJUSTMENT_LAYER, GimpAdjustmentLayer))
#define GIMP_ADJUSTMENT_LAYER_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), GIMP_TYPE_ADJUSTMENT_LAYER, GimpAdjustmentLayerClass))
#define GIMP_IS_ADJUSTMENT_LAYER(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), GIMP_TYPE_ADJUSTMENT_LAYER))
#define GIMP_IS_ADJUSTMENT_LAYER_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), GIMP_TYPE_ADJUSTMENT_LAYER))
#define GIMP_ADJUSTMENT_LAYER_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), GIMP_TYPE_ADJUSTMENT_LAYER, GimpAdjustmentLayerClass))

typedef struct _GimpAdjustmentLayerClass GimpAdjustmentLayerClass;

struct _GimpAdjustmentLayer
{
  GimpLayer   parent_instance;

  gchar      *operation_name;
  GObject    *config;
  GeglNode   *op_node;
  gboolean    clipped;
  gulong      config_notify_id;
};

struct _GimpAdjustmentLayerClass
{
  GimpLayerClass parent_class;

  void (* config_changed) (GimpAdjustmentLayer *layer);
};

GType                 gimp_adjustment_layer_get_type       (void);

GimpAdjustmentLayer * gimp_adjustment_layer_new            (GimpImage    *image,
                                                            const gchar  *operation_name,
                                                            GObject      *config);

const gchar         * gimp_adjustment_layer_get_operation  (GimpAdjustmentLayer *layer);
GObject             * gimp_adjustment_layer_get_config     (GimpAdjustmentLayer *layer);
void                  gimp_adjustment_layer_set_config     (GimpAdjustmentLayer *layer,
                                                            GObject             *config,
                                                            gboolean             push_undo);

gboolean              gimp_adjustment_layer_get_clipped    (GimpAdjustmentLayer *layer);
void                  gimp_adjustment_layer_set_clipped    (GimpAdjustmentLayer *layer,
                                                            gboolean             clipped,
                                                            gboolean             push_undo);
