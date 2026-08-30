/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * gimplayerfx.h
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

#define GIMP_TYPE_LAYER_FX            (gimp_layer_fx_get_type ())
#define GIMP_LAYER_FX(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), GIMP_TYPE_LAYER_FX, GimpLayerFX))
#define GIMP_LAYER_FX_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), GIMP_TYPE_LAYER_FX, GimpLayerFXClass))
#define GIMP_IS_LAYER_FX(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), GIMP_TYPE_LAYER_FX))
#define GIMP_IS_LAYER_FX_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), GIMP_TYPE_LAYER_FX))
#define GIMP_LAYER_FX_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), GIMP_TYPE_LAYER_FX, GimpLayerFXClass))

typedef struct _GimpLayerFXClass GimpLayerFXClass;

typedef struct _GimpDropShadowFX
{
  gboolean       enabled;
  GimpRGB        color;
  gdouble        opacity;
  GimpLayerMode  blend_mode;
  gdouble        angle;
  gdouble        distance;
  gdouble        spread;
  gdouble        size;
  gdouble        noise;
  gboolean       knock_out;
} GimpDropShadowFX;

typedef enum
{
  GIMP_STROKE_POSITION_OUTSIDE,
  GIMP_STROKE_POSITION_INSIDE,
  GIMP_STROKE_POSITION_CENTER
} GimpStrokePosition;

typedef enum
{
  GIMP_STROKE_FILL_COLOR,
  GIMP_STROKE_FILL_GRADIENT,
  GIMP_STROKE_FILL_PATTERN
} GimpStrokeFillType;

typedef struct _GimpStrokeFX
{
  gboolean            enabled;
  gint                size;
  GimpStrokePosition  position;
  GimpLayerMode       blend_mode;
  gdouble             opacity;
  GimpStrokeFillType  fill_type;
  GimpRGB             color;
} GimpStrokeFX;

typedef struct _GimpOuterGlowFX
{
  gboolean       enabled;
  GimpRGB        color;
  GimpLayerMode  blend_mode;
  gdouble        opacity;
  gdouble        spread;
  gdouble        size;
} GimpOuterGlowFX;

typedef enum
{
  GIMP_BEVEL_STYLE_INNER,
  GIMP_BEVEL_STYLE_OUTER,
  GIMP_BEVEL_STYLE_EMBOSS,
  GIMP_BEVEL_STYLE_PILLOW_EMBOSS
} GimpBevelStyle;

typedef enum
{
  GIMP_BEVEL_TECHNIQUE_SMOOTH,
  GIMP_BEVEL_TECHNIQUE_CHISEL_HARD,
  GIMP_BEVEL_TECHNIQUE_CHISEL_SOFT
} GimpBevelTechnique;

typedef struct _GimpBevelEmbossFX
{
  gboolean            enabled;
  GimpBevelStyle      style;
  GimpBevelTechnique  technique;
  gdouble             depth;
  gboolean            direction_up;
  gdouble             size;
  gdouble             soften;
  gdouble             angle;
  gdouble             altitude;
  GimpLayerMode       highlight_mode;
  GimpRGB             highlight_color;
  gdouble             highlight_opacity;
  GimpLayerMode       shadow_mode;
  GimpRGB             shadow_color;
  gdouble             shadow_opacity;
} GimpBevelEmbossFX;

typedef struct _GimpColorOverlayFX
{
  gboolean       enabled;
  GimpRGB        color;
  GimpLayerMode  blend_mode;
  gdouble        opacity;
} GimpColorOverlayFX;

struct _GimpLayerFX
{
  GimpObject          parent_instance;

  GimpLayer          *layer;
  GimpDropShadowFX    drop_shadow;
  GimpStrokeFX        stroke;
  GimpOuterGlowFX     outer_glow;
  GimpBevelEmbossFX   bevel_emboss;
  GimpColorOverlayFX  color_overlay;

  GeglNode           *fx_subgraph;
};

struct _GimpLayerFXClass
{
  GimpObjectClass parent_class;

  void (* changed) (GimpLayerFX *fx);
};

GType         gimp_layer_fx_get_type       (void);
GimpLayerFX * gimp_layer_fx_new            (GimpLayer     *layer);

void          gimp_layer_fx_update_bounds  (GimpLayerFX   *fx,
                                            GeglRectangle *bounds);

GeglNode    * gimp_layer_fx_get_graph      (GimpLayerFX   *fx,
                                            GeglNode      *input_node);

gboolean      gimp_layer_fx_has_effects    (GimpLayerFX   *fx);
