/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
 *
 * layer-styles-dialog.c
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

#include "libgimpwidgets/gimpwidgets.h"

#include "core-types.h"

#include "core/gimp.h"
#include "core/gimpcontext.h"
#include "core/gimpimage.h"
#include "core/gimplayer.h"
#include "core/gimplayerfx.h"

#include "widgets/gimpdialogfactory.h"
#include "widgets/gimpviewabledialog.h"

#include "layer-styles-dialog.h"

#include "gimp-intl.h"

typedef struct
{
  GimpLayer   *layer;
  GimpContext *context;
  GtkWidget   *dialog;
  GtkWidget   *ds_check;
  GtkWidget   *stroke_check;
  GtkWidget   *glow_check;
  GtkWidget   *bevel_check;
} LayerStylesDialogData;

static void
layer_styles_dialog_response (GtkWidget             *widget,
                              gint                   response_id,
                              LayerStylesDialogData *data)
{
  if (response_id == GTK_RESPONSE_OK)
    {
      /* Commit styles changes */
      gimp_drawable_update (GIMP_DRAWABLE (data->layer), 0, 0,
                            gimp_item_get_width (GIMP_ITEM (data->layer)),
                            gimp_item_get_height (GIMP_ITEM (data->layer)));
    }

  gtk_window_destroy (GTK_WINDOW (data->dialog));
  g_slice_free (LayerStylesDialogData, data);
}

GtkWidget *
layer_styles_dialog_new (GimpLayer   *layer,
                         GimpContext *context)
{
  LayerStylesDialogData *data;
  GtkWidget             *dialog;
  GtkWidget             *vbox;
  GtkWidget             *frame;
  GtkWidget             *grid;

  g_return_val_if_fail (GIMP_IS_LAYER (layer), NULL);

  data = g_slice_new0 (LayerStylesDialogData);
  data->layer   = layer;
  data->context = context;

  dialog = gimp_dialog_new (_("Layer Styles (FX)"),
                            "gimp-layer-styles-dialog",
                            NULL, 0,
                            gimp_standard_help_func, NULL,
                            _("_Cancel"), GTK_RESPONSE_CANCEL,
                            _("_OK"),     GTK_RESPONSE_OK,
                            NULL);

  data->dialog = dialog;

  g_signal_connect (dialog, "response",
                    G_CALLBACK (layer_styles_dialog_response),
                    data);

  vbox = gtk_box_new (GTK_ORIENTATION_VERTICAL, 12);
  gtk_widget_set_margin_start (vbox, 12);
  gtk_widget_set_margin_end (vbox, 12);
  gtk_widget_set_margin_top (vbox, 12);
  gtk_widget_set_margin_bottom (vbox, 12);
  gtk_box_append (GTK_BOX (gtk_dialog_get_content_area (GTK_DIALOG (dialog))), vbox);

  frame = gimp_frame_new (_("Real-Time Layer Effects"));
  gtk_box_append (GTK_BOX (vbox), frame);

  grid = gtk_grid_new ();
  gtk_grid_set_row_spacing (GTK_GRID (grid), 6);
  gtk_grid_set_column_spacing (GTK_GRID (grid), 6);
  gtk_frame_set_child (GTK_FRAME (frame), grid);

  data->ds_check = gtk_check_button_new_with_mnemonic (_("Drop _Shadow"));
  gtk_grid_attach (GTK_GRID (grid), data->ds_check, 0, 0, 1, 1);

  data->stroke_check = gtk_check_button_new_with_mnemonic (_("Stro_ke"));
  gtk_grid_attach (GTK_GRID (grid), data->stroke_check, 0, 1, 1, 1);

  data->glow_check = gtk_check_button_new_with_mnemonic (_("Outer _Glow"));
  gtk_grid_attach (GTK_GRID (grid), data->glow_check, 0, 2, 1, 1);

  data->bevel_check = gtk_check_button_new_with_mnemonic (_("_Bevel & Emboss"));
  gtk_grid_attach (GTK_GRID (grid), data->bevel_check, 0, 3, 1, 1);

  return dialog;
}
