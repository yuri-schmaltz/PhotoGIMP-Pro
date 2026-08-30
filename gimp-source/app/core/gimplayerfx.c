/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimplayerfx.c
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

#include <math.h>
#include <gegl.h>
#include <gdk-pixbuf/gdk-pixbuf.h>

#include "libgimpbase/gimpbase.h"
#include "libgimpcolor/gimpcolor.h"
#include "libgimpmath/gimpmath.h"

#include "core-types.h"

#include "gimplayer.h"
#include "gimplayerfx.h"
#include "gimpimage.h"

enum
{
  CHANGED,
  LAST_SIGNAL
};

static guint layer_fx_signals[LAST_SIGNAL] = { 0 };

static void   gimp_layer_fx_finalize (GObject *object);

G_DEFINE_TYPE (GimpLayerFX, gimp_layer_fx, GIMP_TYPE_OBJECT)

#define parent_class gimp_layer_fx_parent_class

static void
gimp_layer_fx_class_init (GimpLayerFXClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  object_class->finalize = gimp_layer_fx_finalize;

  layer_fx_signals[CHANGED] =
    g_signal_new ("changed",
                  G_TYPE_FROM_CLASS (klass),
                  G_SIGNAL_RUN_FIRST,
                  G_STRUCT_OFFSET (GimpLayerFXClass, changed),
                  NULL, NULL, NULL,
                  G_TYPE_NONE, 0);
}

static void
gimp_layer_fx_init (GimpLayerFX *fx)
{
  fx->layer = NULL;
  fx->fx_subgraph = NULL;

  /* Drop Shadow defaults */
  fx->drop_shadow.enabled = FALSE;
  gimp_rgba_set (&fx->drop_shadow.color, 0.0, 0.0, 0.0, 1.0);
  fx->drop_shadow.opacity = 0.75;
  fx->drop_shadow.blend_mode = GIMP_LAYER_MODE_MULTIPLY;
  fx->drop_shadow.angle = 120.0;
  fx->drop_shadow.distance = 5.0;
  fx->drop_shadow.spread = 0.0;
  fx->drop_shadow.size = 5.0;
  fx->drop_shadow.noise = 0.0;
  fx->drop_shadow.knock_out = FALSE;

  /* Stroke defaults */
  fx->stroke.enabled = FALSE;
  fx->stroke.size = 3;
  fx->stroke.position = GIMP_STROKE_POSITION_OUTSIDE;
  fx->stroke.blend_mode = GIMP_LAYER_MODE_NORMAL;
  fx->stroke.opacity = 1.0;
  fx->stroke.fill_type = GIMP_STROKE_FILL_COLOR;
  gimp_rgba_set (&fx->stroke.color, 0.0, 0.0, 0.0, 1.0);

  /* Outer Glow defaults */
  fx->outer_glow.enabled = FALSE;
  gimp_rgba_set (&fx->outer_glow.color, 1.0, 1.0, 0.75, 1.0);
  fx->outer_glow.blend_mode = GIMP_LAYER_MODE_SCREEN;
  fx->outer_glow.opacity = 0.75;
  fx->outer_glow.spread = 0.0;
  fx->outer_glow.size = 10.0;

  /* Bevel & Emboss defaults */
  fx->bevel_emboss.enabled = FALSE;
  fx->bevel_emboss.style = GIMP_BEVEL_STYLE_INNER;
  fx->bevel_emboss.technique = GIMP_BEVEL_TECHNIQUE_SMOOTH;
  fx->bevel_emboss.depth = 100.0;
  fx->bevel_emboss.direction_up = TRUE;
  fx->bevel_emboss.size = 5.0;
  fx->bevel_emboss.soften = 0.0;
  fx->bevel_emboss.angle = 120.0;
  fx->bevel_emboss.altitude = 30.0;
  fx->bevel_emboss.highlight_mode = GIMP_LAYER_MODE_SCREEN;
  gimp_rgba_set (&fx->bevel_emboss.highlight_color, 1.0, 1.0, 1.0, 1.0);
  fx->bevel_emboss.highlight_opacity = 0.75;
  fx->bevel_emboss.shadow_mode = GIMP_LAYER_MODE_MULTIPLY;
  gimp_rgba_set (&fx->bevel_emboss.shadow_color, 0.0, 0.0, 0.0, 1.0);
  fx->bevel_emboss.shadow_opacity = 0.75;

  /* Color Overlay defaults */
  fx->color_overlay.enabled = FALSE;
  gimp_rgba_set (&fx->color_overlay.color, 1.0, 0.0, 0.0, 1.0);
  fx->color_overlay.blend_mode = GIMP_LAYER_MODE_NORMAL;
  fx->color_overlay.opacity = 1.0;
}

static void
gimp_layer_fx_finalize (GObject *object)
{
  GimpLayerFX *fx = GIMP_LAYER_FX (object);

  if (fx->fx_subgraph)
    {
      g_object_unref (fx->fx_subgraph);
      fx->fx_subgraph = NULL;
    }

  G_OBJECT_CLASS (parent_class)->finalize (object);
}

GimpLayerFX *
gimp_layer_fx_new (GimpLayer *layer)
{
  GimpLayerFX *fx;

  g_return_val_if_fail (layer == NULL || GIMP_IS_LAYER (layer), NULL);

  fx = g_object_new (GIMP_TYPE_LAYER_FX, NULL);
  fx->layer = layer;

  return fx;
}

gboolean
gimp_layer_fx_has_effects (GimpLayerFX *fx)
{
  if (! fx)
    return FALSE;

  return (fx->drop_shadow.enabled   ||
          fx->stroke.enabled        ||
          fx->outer_glow.enabled     ||
          fx->bevel_emboss.enabled  ||
          fx->color_overlay.enabled);
}

void
gimp_layer_fx_update_bounds (GimpLayerFX   *fx,
                             GeglRectangle *bounds)
{
  gdouble expand_left   = 0.0;
  gdouble expand_right  = 0.0;
  gdouble expand_top    = 0.0;
  gdouble expand_bottom = 0.0;

  g_return_if_fail (GIMP_IS_LAYER_FX (fx));
  g_return_if_fail (bounds != NULL);

  if (fx->drop_shadow.enabled)
    {
      gdouble rad = fx->drop_shadow.angle * (G_PI / 180.0);
      gdouble dx  = cos (rad) * fx->drop_shadow.distance;
      gdouble dy  = sin (rad) * fx->drop_shadow.distance;
      gdouble pad = fx->drop_shadow.size * 2.0;

      expand_left   = MAX (expand_left,   -dx + pad);
      expand_right  = MAX (expand_right,   dx + pad);
      expand_top    = MAX (expand_top,    -dy + pad);
      expand_bottom = MAX (expand_bottom,  dy + pad);
    }

  if (fx->outer_glow.enabled)
    {
      gdouble pad = fx->outer_glow.size;
      expand_left   = MAX (expand_left,   pad);
      expand_right  = MAX (expand_right,  pad);
      expand_top    = MAX (expand_top,    pad);
      expand_bottom = MAX (expand_bottom, pad);
    }

  if (fx->stroke.enabled && fx->stroke.position == GIMP_STROKE_POSITION_OUTSIDE)
    {
      gdouble pad = fx->stroke.size;
      expand_left   = MAX (expand_left,   pad);
      expand_right  = MAX (expand_right,  pad);
      expand_top    = MAX (expand_top,    pad);
      expand_bottom = MAX (expand_bottom, pad);
    }

  bounds->x      -= (gint) ceil (expand_left);
  bounds->y      -= (gint) ceil (expand_top);
  bounds->width  += (gint) ceil (expand_left + expand_right);
  bounds->height += (gint) ceil (expand_top + expand_bottom);
}

GeglNode *
gimp_layer_fx_get_graph (GimpLayerFX *fx,
                         GeglNode    *input_node)
{
  g_return_val_if_fail (GIMP_IS_LAYER_FX (fx), NULL);
  g_return_val_if_fail (GEGL_IS_NODE (input_node), NULL);

  if (! gimp_layer_fx_has_effects (fx))
    return input_node;

  /* Return input_node for transparent pipeline or generate dynamic GEGL subgraph */
  return input_node;
}
