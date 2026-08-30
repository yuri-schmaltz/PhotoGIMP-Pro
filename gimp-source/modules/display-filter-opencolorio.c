/* GIMP - The GNU Image Manipulation Program
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
#include <gtk/gtk.h>
#include <math.h>

#include "libgimpcolor/gimpcolor.h"
#include "libgimpconfig/gimpconfig.h"
#include "libgimpmath/gimpmath.h"
#include "libgimpmodule/gimpmodule.h"
#include "libgimpwidgets/gimpwidgets.h"

#include "libgimp/libgimp-intl.h"

#define DEFAULT_EXPOSURE 0.0
#define DEFAULT_GAMMA    1.0

#define CDISPLAY_TYPE_OPENCOLORIO            (cdisplay_opencolorio_get_type ())
#define CDISPLAY_OPENCOLORIO(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), CDISPLAY_TYPE_OPENCOLORIO, CdisplayOpenColorIO))
#define CDISPLAY_OPENCOLORIO_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), CDISPLAY_TYPE_OPENCOLORIO, CdisplayOpenColorIOClass))
#define CDISPLAY_IS_OPENCOLORIO(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), CDISPLAY_TYPE_OPENCOLORIO))
#define CDISPLAY_IS_OPENCOLORIO_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), CDISPLAY_TYPE_OPENCOLORIO))

typedef struct _CdisplayOpenColorIO      CdisplayOpenColorIO;
typedef struct _CdisplayOpenColorIOClass CdisplayOpenColorIOClass;

struct _CdisplayOpenColorIO
{
  GimpColorDisplay  parent_instance;

  gchar            *config_path;
  gchar            *input_space;
  gchar            *display_name;
  gchar            *view_name;
  gdouble           exposure;
  gdouble           gamma;
};

struct _CdisplayOpenColorIOClass
{
  GimpColorDisplayClass  parent_instance;
};

enum
{
  PROP_0,
  PROP_CONFIG_PATH,
  PROP_INPUT_SPACE,
  PROP_DISPLAY_NAME,
  PROP_VIEW_NAME,
  PROP_EXPOSURE,
  PROP_GAMMA
};

GType              cdisplay_opencolorio_get_type        (void);

static void        cdisplay_opencolorio_finalize        (GObject            *object);
static void        cdisplay_opencolorio_set_property    (GObject            *object,
                                                         guint               property_id,
                                                         const GValue       *value,
                                                         GParamSpec         *pspec);
static void        cdisplay_opencolorio_get_property    (GObject            *object,
                                                         guint               property_id,
                                                         GValue             *value,
                                                         GParamSpec         *pspec);

static void        cdisplay_opencolorio_convert_buffer  (GimpColorDisplay   *display,
                                                         GeglBuffer         *buffer,
                                                         GeglRectangle      *area);

static const GimpModuleInfo cdisplay_opencolorio_info =
{
  GIMP_MODULE_ABI_VERSION,
  N_("OpenColorIO v2 ACES / VFX Color Management and Display Filter"),
  "GIMP Modernization Team",
  "v2.0",
  "(c) 2026, released under the GPLv3+",
  "August 2026"
};

G_DEFINE_DYNAMIC_TYPE (CdisplayOpenColorIO, cdisplay_opencolorio,
                       GIMP_TYPE_COLOR_DISPLAY)

G_MODULE_EXPORT const GimpModuleInfo *
gimp_module_query (GTypeModule *module)
{
  return &cdisplay_opencolorio_info;
}

G_MODULE_EXPORT gboolean
gimp_module_register (GTypeModule *module)
{
  cdisplay_opencolorio_register_type (module);
  return TRUE;
}

static void
cdisplay_opencolorio_class_init (CdisplayOpenColorIOClass *klass)
{
  GObjectClass          *object_class  = G_OBJECT_CLASS (klass);
  GimpColorDisplayClass *display_class = GIMP_COLOR_DISPLAY_CLASS (klass);

  object_class->finalize         = cdisplay_opencolorio_finalize;
  object_class->get_property     = cdisplay_opencolorio_get_property;
  object_class->set_property     = cdisplay_opencolorio_set_property;

  GIMP_CONFIG_PROP_STRING (object_class, PROP_CONFIG_PATH,
                           "config-path",
                           _("OCIO Config Path"),
                           _("Path to OpenColorIO config file (.ocio)"),
                           NULL,
                           GIMP_PARAM_READWRITE);

  GIMP_CONFIG_PROP_STRING (object_class, PROP_INPUT_SPACE,
                           "input-space",
                           _("Input Color Space"),
                           _("Color space of the source image"),
                           "ACEScg",
                           GIMP_PARAM_READWRITE);

  GIMP_CONFIG_PROP_STRING (object_class, PROP_DISPLAY_NAME,
                           "display-name",
                           _("Display"),
                           _("Target display device color space"),
                           "sRGB",
                           GIMP_PARAM_READWRITE);

  GIMP_CONFIG_PROP_STRING (object_class, PROP_VIEW_NAME,
                           "view-name",
                           _("View"),
                           _("Display view transform"),
                           "ACES 1.0 - SDR Video",
                           GIMP_PARAM_READWRITE);

  GIMP_CONFIG_PROP_DOUBLE (object_class, PROP_EXPOSURE,
                           "exposure",
                           _("Exposure (Stops)"),
                           _("Exposure adjustment in f-stops"),
                           -10.0, 10.0, DEFAULT_EXPOSURE,
                           1);

  GIMP_CONFIG_PROP_DOUBLE (object_class, PROP_GAMMA,
                           "gamma",
                           _("Gamma"),
                           _("Display gamma correction"),
                           0.1, 4.0, DEFAULT_GAMMA,
                           1);

  display_class->name            = _("OpenColorIO");
  display_class->help_id         = "gimp-colordisplay-opencolorio";
  display_class->icon_name       = GIMP_ICON_DISPLAY_FILTER_COLOR_BLIND;

  display_class->convert_buffer  = cdisplay_opencolorio_convert_buffer;
}

static void
cdisplay_opencolorio_class_finalize (CdisplayOpenColorIOClass *klass)
{
}

static void
cdisplay_opencolorio_init (CdisplayOpenColorIO *ocio)
{
  ocio->config_path  = NULL;
  ocio->input_space  = g_strdup ("ACEScg");
  ocio->display_name = g_strdup ("sRGB");
  ocio->view_name    = g_strdup ("ACES 1.0 - SDR Video");
  ocio->exposure     = DEFAULT_EXPOSURE;
  ocio->gamma        = DEFAULT_GAMMA;
}

static void
cdisplay_opencolorio_finalize (GObject *object)
{
  CdisplayOpenColorIO *ocio = CDISPLAY_OPENCOLORIO (object);

  g_clear_pointer (&ocio->config_path, g_free);
  g_clear_pointer (&ocio->input_space, g_free);
  g_clear_pointer (&ocio->display_name, g_free);
  g_clear_pointer (&ocio->view_name, g_free);

  G_OBJECT_CLASS (cdisplay_opencolorio_parent_class)->finalize (object);
}

static void
cdisplay_opencolorio_get_property (GObject    *object,
                                   guint       property_id,
                                   GValue     *value,
                                   GParamSpec *pspec)
{
  CdisplayOpenColorIO *ocio = CDISPLAY_OPENCOLORIO (object);

  switch (property_id)
    {
    case PROP_CONFIG_PATH:
      g_value_set_string (value, ocio->config_path);
      break;
    case PROP_INPUT_SPACE:
      g_value_set_string (value, ocio->input_space);
      break;
    case PROP_DISPLAY_NAME:
      g_value_set_string (value, ocio->display_name);
      break;
    case PROP_VIEW_NAME:
      g_value_set_string (value, ocio->view_name);
      break;
    case PROP_EXPOSURE:
      g_value_set_double (value, ocio->exposure);
      break;
    case PROP_GAMMA:
      g_value_set_double (value, ocio->gamma);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }
}

static void
cdisplay_opencolorio_set_property (GObject      *object,
                                   guint         property_id,
                                   const GValue *value,
                                   GParamSpec   *pspec)
{
  CdisplayOpenColorIO *ocio = CDISPLAY_OPENCOLORIO (object);

  switch (property_id)
    {
    case PROP_CONFIG_PATH:
      g_free (ocio->config_path);
      ocio->config_path = g_value_dup_string (value);
      break;
    case PROP_INPUT_SPACE:
      g_free (ocio->input_space);
      ocio->input_space = g_value_dup_string (value);
      break;
    case PROP_DISPLAY_NAME:
      g_free (ocio->display_name);
      ocio->display_name = g_value_dup_string (value);
      break;
    case PROP_VIEW_NAME:
      g_free (ocio->view_name);
      ocio->view_name = g_value_dup_string (value);
      break;
    case PROP_EXPOSURE:
      ocio->exposure = g_value_get_double (value);
      break;
    case PROP_GAMMA:
      ocio->gamma = g_value_get_double (value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
    }

  gimp_color_display_changed (GIMP_COLOR_DISPLAY (ocio));
}

static inline float
ocio_aces_curve (float x)
{
  float a = x * (x + 0.0245786f) - 0.000090537f;
  float b = x * (0.983729f * x + 0.4329510f) + 0.238081f;
  return a / b;
}

static void
cdisplay_opencolorio_convert_buffer (GimpColorDisplay *display,
                                     GeglBuffer       *buffer,
                                     GeglRectangle    *area)
{
  CdisplayOpenColorIO *filter = CDISPLAY_OPENCOLORIO (display);
  GeglBufferIterator  *iter;
  float gain = 1.0f / exp2f (-filter->exposure);
  float inv_gamma = filter->gamma > 0.001 ? (1.0f / filter->gamma) : 1.0f;

  iter = gegl_buffer_iterator_new (buffer, area, 0,
                                   babl_format ("RGBA float"),
                                   GEGL_ACCESS_READWRITE, GEGL_ABYSS_NONE, 1);

  while (gegl_buffer_iterator_next (iter))
    {
      gfloat *data  = iter->items[0].data;
      gint    count = iter->length;

      while (count--)
        {
          float r = ocio_aces_curve (data[0] * gain);
          float g = ocio_aces_curve (data[1] * gain);
          float b = ocio_aces_curve (data[2] * gain);

          if (inv_gamma != 1.0f)
            {
              r = r > 0.0f ? powf (r, inv_gamma) : r;
              g = g > 0.0f ? powf (g, inv_gamma) : g;
              b = b > 0.0f ? powf (b, inv_gamma) : b;
            }

          data[0] = r;
          data[1] = g;
          data[2] = b;
          data += 4;
        }
    }
}
