/* LIBGIMP - The GIMP Library
 * Copyright (C) 1995-1997 Peter Mattis and Spencer Kimball
 *
 * gimpcurve.c
 * Copyright (C) 2026 Alx Sa
 *
 * This library is free software: you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 3 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.  If not, see
 * <https://www.gnu.org/licenses/>.
 */

#include "config.h"

#include "gimp.h"

#include "gimpcurve.h"


enum
{
  PROP_0,
  PROP_CURVE_TYPE,
  PROP_N_SAMPLES,
  N_PROPS
};
static GParamSpec *obj_props[N_PROPS] = { NULL, };

enum
{
  POINTS_CHANGED,
  SAMPLES_CHANGED,
  LAST_SIGNAL
};
static guint gimp_curve_signals[LAST_SIGNAL] = { 0 };

typedef struct
{
  gdouble           x;
  gdouble           y;

 GimpCurvePointType type;
} GimpCurvePoint;

struct _GimpCurve
{
  GObject           parent_instance;

  GimpCurveType     curve_type;

  gint              n_points;
  GimpCurvePoint   *points;

  gint              n_samples;
  gdouble          *samples;

  gboolean          identity;   /* whether the curve is an identity mapping */
};

static void          gimp_curve_finalize          (GObject          *object);
static void          gimp_curve_set_property      (GObject          *object,
                                                   guint             property_id,
                                                   const GValue     *value,
                                                   GParamSpec       *pspec);
static void          gimp_curve_get_property      (GObject          *object,
                                                   guint             property_id,
                                                   GValue           *value,
                                                   GParamSpec       *pspec);

static void          gimp_curve_build_samples     (GimpCurve        *curve);


G_DEFINE_TYPE (GimpCurve, gimp_curve, G_TYPE_OBJECT);

static void  gimp_curve_class_init (GimpCurveClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);

  /**
   * GimpCurve::points-changed:
   * @curve: the curve emitting the signal
   *
   * Emitted when any points are added, deleted, or edited in @curve.
   *
   * Since: 3.2
   */
  gimp_curve_signals[POINTS_CHANGED] =
    g_signal_new ("points-changed",
                  G_TYPE_FROM_CLASS (klass),
                  G_SIGNAL_RUN_FIRST,
                  0,
                  NULL, NULL, NULL,
                  G_TYPE_NONE, 0);

  /**
   * GimpCurve::samples-changed:
   * @curve: the curve emitting the signal
   *
   * Emitted when any sample is edited, or if the number of samples
   * changed, in @curve.
   *
   * Since: 3.2
   */
  gimp_curve_signals[SAMPLES_CHANGED] =
    g_signal_new ("samples-changed",
                  G_TYPE_FROM_CLASS (klass),
                  G_SIGNAL_RUN_FIRST,
                  0,
                  NULL, NULL, NULL,
                  G_TYPE_NONE, 0);

  object_class->finalize     = gimp_curve_finalize;
  object_class->set_property = gimp_curve_set_property;
  object_class->get_property = gimp_curve_get_property;

  /**
   * GimpCurve:curve-type:
   *
   * The curve type.
   *
   * Since: 3.2
   */
  obj_props[PROP_CURVE_TYPE] =
      g_param_spec_enum ("curve-type",
                         "Curve Type",
                         "The curve type",
                         GIMP_TYPE_CURVE_TYPE,
                         GIMP_CURVE_SMOOTH,
                         GIMP_CONFIG_PARAM_FLAGS |
                         G_PARAM_EXPLICIT_NOTIFY);

  /**
   * GimpCurve:n-samples:
   *
   * The number of samples this [enum@Gimp.CurveType.FREE] curve is
   * split into.
   *
   * Since: 3.2
   */
  obj_props[PROP_N_SAMPLES] =
      g_param_spec_int ("n-samples",
                        "Number of Samples",
                        "The number of samples",
                        256, 256, 256,
                        GIMP_CONFIG_PARAM_FLAGS |
                        G_PARAM_EXPLICIT_NOTIFY);

  g_object_class_install_properties (object_class, N_PROPS, obj_props);
}

static void
gimp_curve_init (GimpCurve *curve)
{
  curve->n_points  = 0;
  curve->points    = NULL;
  curve->n_samples = 256;
  curve->samples   = NULL;
  curve->identity  = FALSE;
}

static void
gimp_curve_finalize (GObject *object)
{
  GimpCurve *curve = GIMP_CURVE (object);

  g_clear_pointer (&curve->points,  g_free);
  curve->n_points = 0;

  g_clear_pointer (&curve->samples, g_free);
  curve->n_samples = 0;
}

static void
gimp_curve_set_property (GObject      *object,
                         guint         property_id,
                         const GValue *value,
                         GParamSpec   *pspec)
{
  GimpCurve *curve = GIMP_CURVE (object);

  switch (property_id)
    {
    case PROP_CURVE_TYPE:
      gimp_curve_set_curve_type (curve, g_value_get_enum (value));
      break;

    case PROP_N_SAMPLES:
      if (curve->curve_type == GIMP_CURVE_FREE)
        gimp_curve_set_n_samples (curve, g_value_get_int (value));
      else
        curve->n_samples = g_value_get_int (value);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

static void
gimp_curve_get_property (GObject    *object,
                         guint       property_id,
                         GValue     *value,
                         GParamSpec *pspec)
{
  GimpCurve *curve = GIMP_CURVE (object);

  switch (property_id)
    {
    case PROP_CURVE_TYPE:
      g_value_set_enum (value, curve->curve_type);
      break;

    case PROP_N_SAMPLES:
      g_value_set_int (value, curve->n_samples);
      break;

    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

/* Public Functions */

/**
 * gimp_curve_new:
 *
 * Creates a new #GimpCurve object, of type
 * [enum@Gimp.CurveType.SMOOTH], with 0 points initially.
 *
 * Returns: (transfer full): a new curve.
 *
 * Since: 3.2
 */
GimpCurve *
gimp_curve_new (void)
{
  return g_object_new (GIMP_TYPE_CURVE, NULL);
}

/**
 * gimp_curve_get_curve_type:
 * @curve: the #GimpCurve.
 *
 * Returns: the @curve type.
 *
 * Since: 3.2
 */
GimpCurveType
gimp_curve_get_curve_type (GimpCurve *curve)
{
  g_return_val_if_fail (GIMP_IS_CURVE (curve), GIMP_CURVE_SMOOTH);

  return curve->curve_type;
}

/**
 * gimp_curve_set_curve_type:
 * @curve: the #GimpCurve.
 * @curve_type: the new curve type.
 *
 * Sets the curve type of @curve, as follows:
 *
 * - Nothing happens if the curve type is unchanged.
 * - If you change to [enum@Gimp.CurveType.SMOOTH], it will create a
 *   non-specified number of points and will approximate their position
 *   along the freehand curve. All default points will be
 *   [enum@Gimp.CurvePointType.SMOOTH].
 * - If you change to [enum@Gimp.CurveType.FREE], all existing points
 *   will be cleared.
 *
 * Since: 3.2
 */
void
gimp_curve_set_curve_type (GimpCurve     *curve,
                           GimpCurveType  curve_type)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));

  if (curve->curve_type != curve_type)
    {
      g_object_freeze_notify (G_OBJECT (curve));

      if (curve_type == GIMP_CURVE_SMOOTH)
        {
          gint i;

          curve->curve_type = curve_type;

          g_free (curve->points);

          /*  pick some points from the curve and make them control
           *  points
           */
          curve->n_points = 9;
          curve->points   = g_new0 (GimpCurvePoint, 9);

          for (i = 0; i < curve->n_points; i++)
            {
              gint sample = i * (curve->n_samples - 1) / (curve->n_points - 1);

              curve->points[i].x    = (gdouble) sample /
                                      (gdouble) (curve->n_samples - 1);
              curve->points[i].y    = curve->samples[sample];
              curve->points[i].type = GIMP_CURVE_POINT_SMOOTH;
            }

          g_signal_emit (G_OBJECT (curve), gimp_curve_signals[POINTS_CHANGED], 0);
        }
      else
        {
          gimp_curve_clear_points (curve);
          curve->curve_type = curve_type;
          gimp_curve_build_samples (curve);
        }

      g_object_notify_by_pspec (G_OBJECT (curve), obj_props[PROP_CURVE_TYPE]);

      g_object_thaw_notify (G_OBJECT (curve));
    }
}

/**
 * gimp_curve_get_n_points:
 * @curve: the #GimpCurve.
 *
 * Gets the number of points in a [enum@Gimp.CurveType.SMOOTH] curve. Note that it will always
 * be 0 for a [enum@Gimp.CurveType.FREE] curve.
 *
 * This can later be used e.g. in [method@Gimp.Curve.get_point] as points
 * are numbered from 0 (included) to the returned number (excluded).
 *
 * Note that the #GimpCurve API is not thread-safe. So be careful that
 * the information on the number of points is still valid when you use
 * it (you may have added or removed points in particular).
 *
 * Returns: the number of points in a smooth curve.
 *
 * Since: 3.2
 */
gint
gimp_curve_get_n_points (GimpCurve *curve)
{
  g_return_val_if_fail (GIMP_IS_CURVE (curve), 0);
  g_return_val_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH, 0);

  return curve->n_points;
}

/**
 * gimp_curve_add_point:
 * @curve: the #GimpCurve.
 * @x: the point abscissa on a `[0.0, 1.0]` range.
 * @y: the point ordinate on a `[0.0, 1.0]` range.
 *
 * Add a new point in a [enum@Gimp.CurveType.SMOOTH] @curve, with
 * coordinates `(x, y)`. Any value outside the `[0.0, 1.0]` range will
 * be silently clamped.
 *
 * The returned identifier can later be used e.g. in
 * [method@Gimp.Curve.get_point] or other functions taking a @point number
 * as argument.
 *
 * Calling this may change identifiers for other points and the total
 * number of points in this @curve. Any such information you currently
 * hold should be considered invalid once the curve is changed.
 *
 * Returns: a point identifier to be used in other functions.
 *
 * Since: 3.2
 */
gint
gimp_curve_add_point (GimpCurve *curve,
                      gdouble    x,
                      gdouble    y)
{
  GimpCurvePoint *points;
  gint            point;

  g_return_val_if_fail (GIMP_IS_CURVE (curve), -1);
  g_return_val_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH, -1);

  x = CLAMP (x, 0.0, 1.0);
  y = CLAMP (y, 0.0, 1.0);

  for (point = 0; point < curve->n_points; point++)
    {
      if (curve->points[point].x > x)
        break;
    }

  points = g_new0 (GimpCurvePoint, curve->n_points + 1);

  memcpy (points,         curve->points,
          point * sizeof (GimpCurvePoint));
  memcpy (points + point + 1, curve->points + point,
          (curve->n_points - point) * sizeof (GimpCurvePoint));

  points[point].x    = x;
  points[point].y    = y;
  points[point].type = GIMP_CURVE_POINT_SMOOTH;

  g_free (curve->points);

  curve->n_points++;
  curve->points = points;

  g_signal_emit (G_OBJECT (curve), gimp_curve_signals[POINTS_CHANGED], 0);

  return point;
}

/**
 * gimp_curve_get_point:
 * @curve: the #GimpCurve.
 * @point: a point identifier.
 * @x: (out) (nullable): the point abscissa on a `[0.0, 1.0]` range.
 * @y: (out) (nullable): the point ordinate on a `[0.0, 1.0]` range.
 *
 * Gets the @point coordinates for a [enum@Gimp.CurveType.SMOOTH] @curve.
 *
 * The @point identifier must be between 0 and the value returned by
 * [method@Gimp.Curve.get_n_points].
 *
 * You may also use a point identifier as returned by
 * [method@Gimp.Curve.add_point], which will correspond to the same
 * point, unless you modified the @curve since (e.g. by calling
 * `gimp_curve_add_point` again, or by deleting or modifying a point).
 *
 * Since: 3.2
 */
void
gimp_curve_get_point (GimpCurve *curve,
                      gint       point,
                      gdouble   *x,
                      gdouble   *y)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH);
  g_return_if_fail (point >= 0 && point < curve->n_points);

  if (x) *x = curve->points[point].x;
  if (y) *y = curve->points[point].y;
}

/**
 * gimp_curve_set_point_type:
 * @curve: the #GimpCurve.
 * @point: a point identifier.
 * @type: a point type.
 *
 * Sets the @point type in a [enum@Gimp.CurveType.SMOOTH] @curve.
 *
 * Since: 3.2
 */
void
gimp_curve_set_point_type (GimpCurve          *curve,
                           gint                point,
                           GimpCurvePointType  type)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH);
  g_return_if_fail (point >= 0 && point < curve->n_points);

  curve->points[point].type = type;

  g_signal_emit (G_OBJECT (curve), gimp_curve_signals[POINTS_CHANGED], 0);
}

/**
 * gimp_curve_get_point_type:
 * @curve: the #GimpCurve.
 * @point: a point identifier.
 *
 * Returns: the @point type of a [enum@Gimp.CurveType.SMOOTH] @curve.
 *
 * Since: 3.2
 */
GimpCurvePointType
gimp_curve_get_point_type (GimpCurve *curve,
                           gint       point)
{
  g_return_val_if_fail (GIMP_IS_CURVE (curve), GIMP_CURVE_POINT_SMOOTH);
  g_return_val_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH, GIMP_CURVE_POINT_SMOOTH);
  g_return_val_if_fail (point >= 0 && point < curve->n_points, GIMP_CURVE_POINT_SMOOTH);

  return curve->points[point].type;
}

/**
 * gimp_curve_delete_point:
 * @curve: the #GimpCurve.
 * @point: a point identifier.
 *
 * Deletes a specific @point from a [enum@Gimp.CurveType.SMOOTH] @curve.
 *
 * The @point identifier must be between 0 and the value returned by
 * [method@Gimp.Curve.get_n_points].
 *
 * You may also use a point identifier as returned by
 * [method@Gimp.Curve.add_point], which will correspond to the same
 * point, unless you modified the @curve since (e.g. by calling
 * `gimp_curve_add_point` again, or by deleting or modifying a point).
 *
 * Since: 3.2
 */
void
gimp_curve_delete_point (GimpCurve *curve,
                         gint       point)
{
  GimpCurvePoint *points;

  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH);
  g_return_if_fail (point >= 0 && point < curve->n_points);

  points = g_new0 (GimpCurvePoint, curve->n_points - 1);

  memcpy (points,         curve->points,
          point * sizeof (GimpCurvePoint));
  memcpy (points + point, curve->points + point + 1,
          (curve->n_points - point - 1) * sizeof (GimpCurvePoint));

  g_free (curve->points);

  curve->n_points--;
  curve->points = points;

  g_signal_emit (G_OBJECT (curve), gimp_curve_signals[POINTS_CHANGED], 0);
}

/**
 * gimp_curve_set_point:
 * @curve: the #GimpCurve.
 * @point: a point identifier.
 * @x: the point abscissa on a `[0.0, 1.0]` range.
 * @y: the point ordinate on a `[0.0, 1.0]` range.
 *
 * Sets the @point coordinates in a [enum@Gimp.CurveType.SMOOTH] @curve.
 * Any value outside the `[0.0, 1.0]` range will be silently clamped.
 *
 * Since: 3.2
 */
void
gimp_curve_set_point (GimpCurve *curve,
                      gint       point,
                      gdouble    x,
                      gdouble    y)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH);
  g_return_if_fail (point >= 0 && point < curve->n_points);

  curve->points[point].x = CLAMP (x, 0.0, 1.0);
  curve->points[point].y = CLAMP (y, 0.0, 1.0);

  if (point > 0)
    curve->points[point].x = MAX (x, curve->points[point - 1].x);

  if (point < curve->n_points - 1)
    curve->points[point].x = MIN (x, curve->points[point + 1].x);

  g_signal_emit (G_OBJECT (curve), gimp_curve_signals[POINTS_CHANGED], 0);
}

/**
 * gimp_curve_clear_points:
 * @curve: the #GimpCurve.
 *
 * Deletes all points from a [enum@Gimp.CurveType.SMOOTH] @curve.
 *
 * A subsequent call to [method@Gimp.Curve.get_n_points] will return 0.
 *
 * Since: 3.2
 */
void
gimp_curve_clear_points (GimpCurve *curve)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_SMOOTH);

  if (curve->points)
    {
      g_clear_pointer (&curve->points, g_free);
      curve->n_points = 0;

      g_signal_emit (G_OBJECT (curve), gimp_curve_signals[POINTS_CHANGED], 0);
    }
}

/**
 * gimp_curve_get_n_samples:
 * @curve: the #GimpCurve.
 *
 * Gets the number of samples in a [enum@Gimp.CurveType.FREE] curve.
 *
 * Returns: the number of samples in a freehand curve.
 *
 * Since: 3.2
 */
gint
gimp_curve_get_n_samples (GimpCurve *curve)
{
  g_return_val_if_fail (GIMP_IS_CURVE (curve), 0);
  g_return_val_if_fail (curve->curve_type == GIMP_CURVE_FREE, 0);

  return curve->n_samples;
}

/**
 * gimp_curve_set_n_samples:
 * @curve: the #GimpCurve.
 * @n_samples: the number of samples.
 *
 * Sets the number of sample in a [enum@Gimp.CurveType.FREE] @curve.
 *
 * Samples will be positioned on the curve abscissa at regular interval.
 * The more samples, the more your curve will have details. Currently,
 * the value of @n_samples is limited and must be between `2^8` and `2^12`.
 *
 * Note that changing the number of samples will reset the curve to an
 * identity curve.
 *
 * Since: 3.2
 */
void
gimp_curve_set_n_samples (GimpCurve *curve,
                          gint       n_samples)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_FREE);
  g_return_if_fail (n_samples >= 256);
  g_return_if_fail (n_samples <= 4096);

  if (n_samples != curve->n_samples)
    {
      g_object_freeze_notify (G_OBJECT (curve));
      curve->n_samples = n_samples;
      gimp_curve_build_samples (curve);
      g_object_thaw_notify (G_OBJECT (curve));

      g_object_notify_by_pspec (G_OBJECT (curve), obj_props[PROP_N_SAMPLES]);
      g_signal_emit (G_OBJECT (curve), gimp_curve_signals[SAMPLES_CHANGED], 0);
    }
}

/**
 * gimp_curve_get_sample:
 * @curve: the #GimpCurve.
 * @x: an abscissa on a `[0.0, 1.0]` range.
 *
 * Gets the ordinate @y value corresponding to the passed @x abscissa
 * value, in a [enum@Gimp.CurveType.FREE] @curve.
 *
 * Note that while the @y coordinate will be stored exactly, the @x
 * coordinate will be rounded to the closest curve sample on the
 * abscissa. The more sample was set with
 * [method@Gimp.Curve.set_n_samples], the more precise the rounding will
 * be.
 *
 * Since: 3.2
 */
gdouble
gimp_curve_get_sample (GimpCurve *curve,
                       gdouble    x)
{
  g_return_val_if_fail (GIMP_IS_CURVE (curve), 0);
  g_return_val_if_fail (curve->curve_type == GIMP_CURVE_FREE, 0);
  g_return_val_if_fail (x >= 0 && x <= 1.0, 0);

  return curve->samples[ROUND (x * (gdouble) (curve->n_samples - 1))];
}

/**
 * gimp_curve_set_sample:
 * @curve: the #GimpCurve.
 * @x: the point abscissa on a `[0.0, 1.0]` range.
 * @y: the point ordinate on a `[0.0, 1.0]` range.
 *
 * Sets a sample in a [enum@Gimp.CurveType.FREE] @curve, with
 * coordinates `(x, y)`.
 *
 * Note that while the @y coordinate will be stored exactly, the @x
 * coordinate will be rounded to the closest curve sample on the
 * abscissa. The more sample was set with
 * [method@Gimp.Curve.set_n_samples], the more precise the rounding will
 * be.
 *
 * Since: 3.2
 */
void
gimp_curve_set_sample (GimpCurve *curve,
                       gdouble    x,
                       gdouble    y)
{
  g_return_if_fail (GIMP_IS_CURVE (curve));
  g_return_if_fail (curve->curve_type == GIMP_CURVE_FREE);
  g_return_if_fail (x >= 0 && x <= 1.0);
  g_return_if_fail (y >= 0 && y <= 1.0);

  curve->samples[ROUND (x * (gdouble) (curve->n_samples - 1))] = y;

  g_signal_emit (G_OBJECT (curve), gimp_curve_signals[SAMPLES_CHANGED], 0);
}

/**
 * gimp_curve_is_identity:
 * @curve: a #GimpCurve object
 *
 * If this function returns %TRUE, then the curve maps each value to
 * itself. If it returns %FALSE, then this assumption can not be made.
 *
 * Returns: %TRUE if the curve is an identity mapping, %FALSE otherwise.
 *
 * Since: 3.2
 **/
gboolean
gimp_curve_is_identity (GimpCurve *curve)
{
  g_return_val_if_fail (GIMP_IS_CURVE (curve), FALSE);

  return curve->identity;
}


/* Private functions */

static void
gimp_curve_build_samples (GimpCurve *curve)
{
  curve->samples = g_renew (gdouble, curve->samples, curve->n_samples);

  for (gint i = 0; i < curve->n_samples; i++)
    curve->samples[i] = (gdouble) i / (gdouble) (curve->n_samples - 1);

  if (curve->curve_type == GIMP_CURVE_FREE)
    curve->identity = TRUE;
}
