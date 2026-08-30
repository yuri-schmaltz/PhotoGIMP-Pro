/* GIMP - The GNU Image Manipulation Program
 * Copyright (C) 1995 Spencer Kimball and Peter Mattis
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


gboolean   gimp_display_shell_events                  (GtkWidget        *widget,
                                                       GdkEvent         *event,
                                                       GimpDisplayShell *shell);

gboolean   gimp_display_shell_canvas_tool_events      (GtkWidget        *widget,
                                                       GdkEvent         *event,
                                                       GimpDisplayShell *shell);
void       gimp_display_shell_canvas_grab_notify      (GtkWidget        *widget,
                                                       gboolean          was_grabbed,
                                                       GimpDisplayShell *shell);

void       gimp_display_shell_zoom_gesture_begin      (GtkGestureZoom   *gesture,
                                                       GdkEventSequence *sequence,
                                                       GimpDisplayShell *shell);
void       gimp_display_shell_zoom_gesture_update     (GtkGestureZoom   *gesture,
                                                       GdkEventSequence *sequence,
                                                       GimpDisplayShell *shell);
void       gimp_display_shell_zoom_gesture_end        (GtkGestureZoom   *gesture,
                                                       GdkEventSequence *sequence,
                                                       GimpDisplayShell *shell);

void       gimp_display_shell_rotate_gesture_begin    (GtkGestureRotate *gesture,
                                                       GdkEventSequence *sequence,
                                                       GimpDisplayShell *shell);
void       gimp_display_shell_rotate_gesture_update   (GtkGestureRotate *gesture,
                                                       GdkEventSequence *sequence,
                                                       GimpDisplayShell *shell);
void       gimp_display_shell_rotate_gesture_end      (GtkGestureRotate *gesture,
                                                       GdkEventSequence *sequence,
                                                       GimpDisplayShell *shell);

void       gimp_display_shell_buffer_stroke           (GimpMotionBuffer *buffer,
                                                       const GimpCoords *coords,
                                                       guint32           time,
                                                       GdkModifierType   state,
                                                       GimpDisplayShell *shell);
void       gimp_display_shell_buffer_hover            (GimpMotionBuffer *buffer,
                                                       const GimpCoords *coords,
                                                       GdkModifierType   state,
                                                       gboolean          proximity,
                                                       GimpDisplayShell *shell);

gboolean   gimp_display_shell_hruler_button_press     (GtkWidget        *widget,
                                                       GdkEventButton   *bevent,
                                                       GimpDisplayShell *shell);
gboolean   gimp_display_shell_vruler_button_press     (GtkWidget        *widget,
                                                       GdkEventButton   *bevent,
                                                       GimpDisplayShell *shell);

gboolean   gimp_display_shell_scroll_controller_scroll       (GtkEventControllerScroll *controller,
                                                              gdouble                   dx,
                                                              gdouble                   dy,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_scroll_controller_scroll_begin (GtkEventControllerScroll *controller,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_scroll_controller_scroll_end   (GtkEventControllerScroll *controller,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_scroll_controller_decelerate   (GtkEventControllerScroll *controller,
                                                              gdouble                   initial_vel_x,
                                                              gdouble                   initial_vel_y,
                                                              GimpDisplayShell         *shell);

void       gimp_display_shell_tool_events_init               (GimpDisplayShell         *shell);

void       gimp_display_shell_click_gesture_pressed          (GtkGestureClick          *gesture,
                                                              gint                      n_press,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_click_gesture_released         (GtkGestureClick          *gesture,
                                                              gint                      n_press,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_click_gesture_stopped          (GtkGestureClick          *gesture,
                                                              GimpDisplayShell         *shell);

void       gimp_display_shell_drag_gesture_begin             (GtkGestureDrag           *gesture,
                                                              gdouble                   start_x,
                                                              gdouble                   start_y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_drag_gesture_update            (GtkGestureDrag           *gesture,
                                                              gdouble                   offset_x,
                                                              gdouble                   offset_y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_drag_gesture_end               (GtkGestureDrag           *gesture,
                                                              gdouble                   offset_x,
                                                              gdouble                   offset_y,
                                                              GimpDisplayShell         *shell);

void       gimp_display_shell_stylus_gesture_down            (GtkGestureStylus         *gesture,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_stylus_gesture_motion          (GtkGestureStylus         *gesture,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_stylus_gesture_up              (GtkGestureStylus         *gesture,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_stylus_gesture_proximity       (GtkGestureStylus         *gesture,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);

void       gimp_display_shell_motion_controller_enter        (GtkEventControllerMotion *controller,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_motion_controller_leave        (GtkEventControllerMotion *controller,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_motion_controller_motion       (GtkEventControllerMotion *controller,
                                                              gdouble                   x,
                                                              gdouble                   y,
                                                              GimpDisplayShell         *shell);

gboolean   gimp_display_shell_key_controller_key_pressed     (GtkEventControllerKey    *controller,
                                                              guint                     keyval,
                                                              guint                     keycode,
                                                              GdkModifierType           state,
                                                              GimpDisplayShell         *shell);
void       gimp_display_shell_key_controller_key_released    (GtkEventControllerKey    *controller,
                                                              guint                     keyval,
                                                              guint                     keycode,
                                                              GdkModifierType           state,
                                                              GimpDisplayShell         *shell);
gboolean   gimp_display_shell_key_controller_modifiers       (GtkEventControllerKey    *controller,
                                                              GdkModifierType           state,
                                                              GimpDisplayShell         *shell);


