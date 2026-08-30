/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimpadjustmentlayer.c
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
#include "libgimpconfig/gimpconfig.h"

#include "core-types.h"

#include "gimp.h"
#include "gimpadjustmentlayer.h"
#include "gimpimage.h"
#include "gimpimage-undo.h"
#include "gimplayermask.h"
#include "gimpundostack.h"

#include "gimp-intl.h"

enum
{
  PROP_0,
  PROP_OPERATION_NAME,
  PROP_CONFIG,
  PROP_CLIPPED
};

enum
{
  CONFIG_CHANGED,
  LAST_SIGNAL
};

static guint adjustment_layer_signals[LAST_SIGNAL] = { 0 };

static void   gimp_adjustment_layer_finalize      (GObject      *object);
static void   gimp_adjustment_layer_set_property  (GObject      *object,
                                                   guint         property_id,
                                                   const GValue *value,
                                                   GParamSpec   *pspec);
static void   gimp_adjustment_layer_get_property  (GObject      *object,
                                                   guint         property_id,
                                                   GValue       *value,
                                                   GParamSpec   *pspec);

G_DEFINE_TYPE (GimpAdjustmentLayer, gimp_adjustment_layer, GIMP_TYPE_LAYER)

#define parent_class gimp_adjustment_layer_parent_class

static void
gimp_adjustment_layer_class_init (GimpAdjustmentLayerClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->finalize     = gimp_adjustment_layer_finalize;
  object_class->set_property = gimp_adjustment_layer_set_property;
  object_class->get_property = gimp_adjustment_layer_get_property;

  adjustment_layer_signals[CONFIG_CHANGED] =
    g_signal_new ("config-changed",
                  G_TYPE_FROM_CLASS (klass),
                  G_SIGNAL_RUN_FIRST,
                  G_STRUCT_OFFSET (GimpAdjustmentLayerClass, config_changed),
                  NULL, NULL, NULL,
                  G_TYPE_NONE, 0);

  g_object_class_install_property (object_class, PROP_OPERATION_NAME,
                                   g_param_spec_string ("operation-name",
                                                        NULL, NULL,
                                                        "gegl:curves",
                                                        GIMP_PARAM_READWRITE |
                                                        G_PARAM_CONSTRUCT));

  g_object_class_install_property (object_class, PROP_CONFIG,
                                   g_param_spec_object ("config",
                                                        NULL, NULL,
                                                        G_TYPE_OBJECT,
                                                        GIMP_PARAM_READWRITE));

  g_object_class_install_property (object_class, PROP_CLIPPED,
                                   g_param_spec_boolean ("clipped",
                                                         NULL, NULL,
                                                         FALSE,
                                                         GIMP_PARAM_READWRITE));
}

static void
gimp_adjustment_layer_init (GimpAdjustmentLayer *layer)
{
  layer->operation_name = g_strdup ("gegl:curves");
  layer->config = NULL;
  layer->op_node = NULL;
  layer->clipped = FALSE;
  layer->config_notify_id = 0;
}

static void
gimp_adjustment_layer_finalize (GObject *object)
{
  GimpAdjustmentLayer *layer = GIMP_ADJUSTMENT_LAYER (object);

  if (layer->config && layer->config_notify_id)
    {
      g_signal_handler_disconnect (layer->config, layer->config_notify_id);
      layer->config_notify_id = 0;
    }

  g_clear_object (&layer->config);
  g_clear_pointer (&layer->operation_name, g_free);

  G_OBJECT_CLASS (parent_class)->finalize (object);
}

static void
gimp_adjustment_layer_config_notify (GObject             *config,
                                     GParamSpec          *pspec,
                                     GimpAdjustmentLayer *layer)
{
  g_signal_emit (layer, adjustment_layer_signals[CONFIG_CHANGED], 0);
  gimp_drawable_update (GIMP_DRAWABLE (layer), 0, 0,
                        gimp_item_get_width (GIMP_ITEM (layer)),
                        gimp_item_get_height (GIMP_ITEM (layer)));
}

static void
gimp_adjustment_layer_set_property (GObject      *object,
                                    guint         property_id,
                                    const GValue *value,
                                    GParamSpec   *pspec)
{
  GimpAdjustmentLayer *layer = GIMP_ADJUSTMENT_LAYER (object);

  switch (property_id)
    {
    case PROP_OPERATION_NAME:
      g_free (layer->operation_name);
      layer->operation_name = g_value_dup_string (value);
      break;

    case PROP_CONFIG:
      gimp_adjustment_layer_set_config (layer, g_value_get_object (value), FALSE);
      break;

    case PROP_CLIPPED:
      layer->clipped = g_value_get_boolean (value);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

static void
gimp_adjustment_layer_get_property (GObject    *object,
                                    guint       property_id,
                                    GValue     *value,
                                    GParamSpec *pspec)
{
  GimpAdjustmentLayer *layer = GIMP_ADJUSTMENT_LAYER (object);

  switch (property_id)
    {
    case PROP_OPERATION_NAME:
      g_value_set_string (value, layer->operation_name);
      break;

    case PROP_CONFIG:
      g_value_set_object (value, layer->config);
      break;

    case PROP_CLIPPED:
      g_value_set_boolean (value, layer->clipped);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

GimpAdjustmentLayer *
gimp_adjustment_layer_new (GimpImage   *image,
                           const gchar *operation_name,
                           GObject     *config)
{
  GimpAdjustmentLayer *layer;

  g_return_val_if_fail (GIMP_IS_IMAGE (image), NULL);
  g_return_val_if_fail (operation_name != NULL, NULL);

  layer = g_object_new (GIMP_TYPE_ADJUSTMENT_LAYER,
                        "image",          image,
                        "name",           operation_name,
                        "operation-name", operation_name,
                        NULL);

  if (config)
    gimp_adjustment_layer_set_config (layer, config, FALSE);

  return layer;
}

const gchar *
gimp_adjustment_layer_get_operation (GimpAdjustmentLayer *layer)
{
  g_return_val_if_fail (GIMP_IS_ADJUSTMENT_LAYER (layer), NULL);
  return layer->operation_name;
}

GObject *
gimp_adjustment_layer_get_config (GimpAdjustmentLayer *layer)
{
  g_return_val_if_fail (GIMP_IS_ADJUSTMENT_LAYER (layer), NULL);
  return layer->config;
}

void
gimp_adjustment_layer_set_config (GimpAdjustmentLayer *layer,
                                  GObject             *config,
                                  gboolean             push_undo)
{
  g_return_if_fail (GIMP_IS_ADJUSTMENT_LAYER (layer));

  if (layer->config == config)
    return;

  if (layer->config && layer->config_notify_id)
    {
      g_signal_handler_disconnect (layer->config, layer->config_notify_id);
      layer->config_notify_id = 0;
    }

  g_set_object (&layer->config, config);

  if (layer->config)
    {
      layer->config_notify_id = g_signal_connect (layer->config, "notify",
                                                  G_CALLBACK (gimp_adjustment_layer_config_notify),
                                                  layer);
    }

  g_signal_emit (layer, adjustment_layer_signals[CONFIG_CHANGED], 0);
  g_object_notify (G_OBJECT (layer), "config");
}

gboolean
gimp_adjustment_layer_get_clipped (GimpAdjustmentLayer *layer)
{
  g_return_val_if_fail (GIMP_IS_ADJUSTMENT_LAYER (layer), FALSE);
  return layer->clipped;
}

void
gimp_adjustment_layer_set_clipped (GimpAdjustmentLayer *layer,
                                   gboolean             clipped,
                                   gboolean             push_undo)
{
  g_return_if_fail (GIMP_IS_ADJUSTMENT_LAYER (layer));

  if (layer->clipped != clipped)
    {
      layer->clipped = clipped;
      g_object_notify (G_OBJECT (layer), "clipped");
    }
}
