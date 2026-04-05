"""
dynamic_charts.py
-----------------
Drop-in strip-chart panel for the dynamic_plots_window in gui2.py.

USAGE
-----
1.  Import at the top of gui2.py:
        import dynamic_charts as dc

2.  Replace the empty child_window body:
        with dpg.child_window(..., tag="dynamic_plots_window", ...):
            dc.build_panel("dynamic_plots_window", sr.streamTelem)

3.  In the main loop call:
        dc.update(sr.streamTelem, sr.streamTelem.tsy_timestamp / 1000)
"""

import dearpygui.dearpygui as dpg
from collections import deque
import dataclasses

# ── tuneable constants ────────────────────────────────────────────────────────
WINDOW_SECS    = 30   # mutable — changed by the x-axis slider
SAMPLE_RATE_HZ = 100
MAX_POINTS     = 300 * SAMPLE_RATE_HZ  # sized for max window (300s)

DEFAULT_CHART_HEIGHT = 200
MIN_CHART_HEIGHT     = 60
MAX_CHART_HEIGHT     = 600
HEADER_H             = 22   # single compact header row height

# ── internal state ────────────────────────────────────────────────────────────
_charts:           list[dict] = []
_chart_counter     = 0
_series_counter    = 0
_parent_tag        = ""
_dropdown_tag      = ""
_height_slider_tag = ""
_window_slider_tag  = ""
_numeric_fields:   list[str] = []
_latest_time       = 0.0
_latest_telem      = None
_last_timestamp    = 0.0   # used to detect power-cycle resets

# Global history — keeps a rolling buffer of ALL telem values so new
# charts can backfill immediately instead of starting empty.
_history_x:    deque = deque(maxlen=300 * 100)  # 300s * 100Hz
_history_vals: dict  = {}   # field -> deque(maxlen=...)

# drag-resize state
_drag_active   = False
_drag_chart_id = -1
_drag_start_y  = 0
_drag_start_h  = 0

# Colors for dark backgrounds — bright and saturated
_SERIES_COLORS_DARK = [
    (100, 180, 255),   # sky blue
    (100, 255, 160),   # mint green
    (255, 180,  80),   # amber
    (255,  90,  90),   # coral red
    (200, 130, 255),   # lavender
    (255, 230,  80),   # yellow
    ( 80, 230, 230),   # cyan
]

# Colors for light backgrounds — deeper and more saturated
_SERIES_COLORS_LIGHT = [
    ( 20, 100, 200),   # strong blue
    ( 20, 160,  70),   # forest green
    (200, 100,   0),   # burnt orange
    (200,  20,  20),   # crimson
    (120,  40, 180),   # purple
    (160, 130,   0),   # dark yellow
    (  0, 140, 160),   # teal
]

_is_dark = True   # kept in sync by set_dark_mode()

def _series_color(i):
    palette = _SERIES_COLORS_DARK if _is_dark else _SERIES_COLORS_LIGHT
    return palette[i % len(palette)]


def set_dark_mode(dark: bool):
    """
    Call this whenever the app theme toggles so line colors update instantly.
    Add one line to toggle_theme() in gui2.py:

        def toggle_theme():
            ...existing code...
            dc.set_dark_mode(is_dark_theme)
    """
    global _is_dark
    _is_dark = dark
    palette = _SERIES_COLORS_DARK if dark else _SERIES_COLORS_LIGHT
    for chart in _charts:
        for idx, s in enumerate(chart["series"]):
            color = palette[idx % len(palette)]
            with dpg.theme() as _lt:
                with dpg.theme_component(dpg.mvLineSeries):
                    dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
                    dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2, category=dpg.mvThemeCat_Plots)
            if dpg.does_item_exist(s["series_tag"]):
                dpg.bind_item_theme(s["series_tag"], _lt)
            if dpg.does_item_exist(s["lbl_tag"]):
                dpg.configure_item(s["lbl_tag"], color=color)

def _get_numeric_fields(telem_obj):
    fields = []
    for f in dataclasses.fields(telem_obj):
        val = getattr(telem_obj, f.name)
        if isinstance(val, (int, float)) and f.name != "header":
            fields.append(f.name)
    return fields


# ── resize ────────────────────────────────────────────────────────────────────

def _set_chart_height(chart, new_h):
    new_h  = max(MIN_CHART_HEIGHT, min(MAX_CHART_HEIGHT, new_h))
    plot_h = max(20, new_h - HEADER_H - 6)
    chart["height"] = new_h
    if dpg.does_item_exist(chart["child_tag"]):
        dpg.set_item_height(chart["child_tag"], new_h)
    if dpg.does_item_exist(chart["plot_tag"]):
        dpg.set_item_height(chart["plot_tag"], plot_h)


def _on_handle_click(sender, app_data, user_data):
    global _drag_active, _drag_chart_id, _drag_start_y, _drag_start_h
    for chart in _charts:
        if chart["id"] == user_data:
            _drag_active   = True
            _drag_chart_id = user_data
            _drag_start_y  = dpg.get_mouse_pos(local=False)[1]
            _drag_start_h  = chart["height"]
            break


def _poll_drag():
    global _drag_active
    if not _drag_active:
        return
    if not dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
        _drag_active = False
        return
    dy = dpg.get_mouse_pos(local=False)[1] - _drag_start_y
    for chart in _charts:
        if chart["id"] == _drag_chart_id:
            _set_chart_height(chart, _drag_start_h + int(dy))
            break


# ── series / chart builders ───────────────────────────────────────────────────

def _add_series_to_chart(chart, field):
    global _series_counter
    _series_counter += 1
    sid        = _series_counter
    series_tag = f"dc_series_{sid}"
    rm_tag     = f"dc_rmbtn_{sid}"
    grp_tag    = f"dc_sergrp_{sid}"
    color      = _series_color(len(chart["series"]))

    # Inline label + tiny x inside the single header group
    with dpg.group(horizontal=True, tag=grp_tag, parent=chart["header_group"]):
        dpg.add_text(field, color=color, tag=f"dc_serlabel_{sid}")
        btn = dpg.add_button(
            label="x", tag=rm_tag, width=16, height=16,
            callback=lambda s, a, u: _remove_series(u[0], u[1]),
            user_data=(chart["id"], sid),
        )
        with dpg.theme() as _t:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button,       (110, 25, 25, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,(170, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (80,  15, 15, 255))
        dpg.bind_item_theme(btn, _t)
        dpg.add_spacer(width=6)

    with dpg.theme() as _lt:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2, category=dpg.mvThemeCat_Plots)

    # Backfill from global history so plot is full immediately
    cutoff = _latest_time - WINDOW_SECS
    hist_x = [x for x in _history_x if x >= cutoff]
    hist_y = list(_history_vals.get(field, []))[-len(hist_x):] if hist_x else []

    x_buf = deque(hist_x, maxlen=MAX_POINTS)
    y_buf = deque(hist_y, maxlen=MAX_POINTS)

    dpg.add_line_series(list(x_buf), list(y_buf), label=field, tag=series_tag, parent=chart["y_axis_tag"])
    dpg.bind_item_theme(series_tag, _lt)

    chart["series"].append({
        "id": sid, "field": field,
        "x": x_buf, "y": y_buf,
        "series_tag": series_tag, "rm_tag": rm_tag, "grp_tag": grp_tag, "lbl_tag": f"dc_serlabel_{sid}",
    })


def _remove_series(chart_id, series_id):
    for chart in _charts:
        if chart["id"] != chart_id: continue
        for i, s in enumerate(chart["series"]):
            if s["id"] != series_id: continue
            for tag in [s["series_tag"], s["grp_tag"]]:
                if dpg.does_item_exist(tag): dpg.delete_item(tag)
            chart["series"].pop(i)
            if not chart["series"]: _remove_chart(chart_id)
            return


def _remove_chart(chart_id):
    for i, chart in enumerate(_charts):
        if chart["id"] == chart_id:
            # remove child window + drag handle drawlist
            for tag in [chart["child_tag"], chart.get("handle_tag", "")]:
                if dpg.does_item_exist(tag): dpg.delete_item(tag)
            _charts.pop(i)
            return


def _add_chart(field):
    global _chart_counter
    _chart_counter += 1
    cid          = _chart_counter
    child_tag    = f"dc_child_{cid}"
    plot_tag     = f"dc_plot_{cid}"
    x_axis_tag   = f"dc_xaxis_{cid}"
    y_axis_tag   = f"dc_yaxis_{cid}"
    header_group = f"dc_hdrgrp_{cid}"
    close_tag    = f"dc_close_{cid}"
    handle_tag   = f"dc_handle_{cid}"

    h      = int(dpg.get_value(_height_slider_tag)) if dpg.does_item_exist(_height_slider_tag) else DEFAULT_CHART_HEIGHT
    plot_h = max(20, h - HEADER_H - 6)

    chart = {
        "id": cid, "child_tag": child_tag, "plot_tag": plot_tag,
        "x_axis_tag": x_axis_tag, "y_axis_tag": y_axis_tag,
        "header_group": header_group, "handle_tag": handle_tag,
        "series": [], "t_start": _latest_time, "height": h,
    }
    _charts.append(chart)

    with dpg.child_window(tag=child_tag, parent=_parent_tag,
                          width=-1, height=h, border=True, no_scrollbar=True):

        # ── single compact header: [✕ chart] [series label x] [series label x] ──
        with dpg.group(horizontal=True, tag=header_group):
            # Close button comes first (leftmost), clearly separated
            btn = dpg.add_button(
                label="✕", tag=close_tag, height=18, width=20,
                callback=lambda s, a, u: _remove_chart(u), user_data=cid,
            )
            with dpg.theme() as _xt:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button,       (130, 25, 25, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,(190, 45, 45, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (95,  15, 15, 255))
            dpg.bind_item_theme(btn, _xt)
            dpg.add_spacer(width=6)
            # series labels+x buttons are appended here by _add_series_to_chart

        # ── plot fills all remaining space ───────────────────────────────
        with dpg.plot(tag=plot_tag, width=-1, height=plot_h, no_title=True):
            dpg.add_plot_legend(outside=False, location=dpg.mvPlot_Location_NorthWest)
            with dpg.plot_axis(dpg.mvXAxis, tag=x_axis_tag):
                dpg.set_axis_limits(x_axis_tag, _latest_time, _latest_time + WINDOW_SECS)
            with dpg.plot_axis(dpg.mvYAxis, tag=y_axis_tag):
                pass

    # ── drag handle: 6px bar between charts ─────────────────────────────
    with dpg.drawlist(tag=handle_tag, parent=_parent_tag, width=-1, height=6):
        dpg.draw_rectangle([0, 1], [4000, 5],
                           color=(80, 80, 80, 160), fill=(80, 80, 80, 60),
                           tag=f"dc_hrect_{cid}")

    with dpg.item_handler_registry(tag=f"dc_hhr_{cid}"):
        dpg.add_item_hover_handler(
            callback=lambda s, a, u: (
                dpg.configure_item(f"dc_hrect_{u}", color=(200, 200, 60, 200), fill=(200, 200, 60, 80))
                if dpg.does_item_exist(f"dc_hrect_{u}") else None
            ), user_data=cid,
        )
        dpg.add_item_clicked_handler(
            button=dpg.mvMouseButton_Left,
            callback=_on_handle_click, user_data=cid,
        )
    dpg.bind_item_handler_registry(handle_tag, f"dc_hhr_{cid}")

    _add_series_to_chart(chart, field)


# ── toolbar callbacks ─────────────────────────────────────────────────────────

def _on_add_new_chart(s, a, u):
    field = dpg.get_value(_dropdown_tag)
    if field: _add_chart(field)

def _on_add_to_last(s, a, u):
    field = dpg.get_value(_dropdown_tag)
    if not field: return
    (_add_series_to_chart(_charts[-1], field) if _charts else _add_chart(field))

def _on_height_slider(s, app_data, u):
    for chart in _charts:
        _set_chart_height(chart, int(app_data))

def _on_window_slider(s, app_data, u):
    global WINDOW_SECS
    WINDOW_SECS = int(app_data)
    # reset each chart's t_start so the window rebuilds cleanly
    for chart in _charts:
        chart["t_start"] = _latest_time - WINDOW_SECS


# ── public API ────────────────────────────────────────────────────────────────

def build_panel(parent_tag, telem_obj=None):
    global _parent_tag, _dropdown_tag, _height_slider_tag, _window_slider_tag, _numeric_fields
    _parent_tag = parent_tag

    _numeric_fields = _get_numeric_fields(telem_obj) if telem_obj else [
        "ctrl_timestamp","ctrl_RSSI","ctrl_looptime","ctrl_sendtime","ctrl_waittime",
        "daq_timestamp","daq_looptime","tsy_timestamp","tsy_looptime",
        "valve_states","pyro_states","arm_states","sensor_states",
        "pt1","pt2","pt3","pt4","pt5","pt6",
        "loadCell","battVolts","battCurrent","tc1","tc2","RSSI",
        "fill_state","vent_state","mov_state","py1_state","py2_state",
        "arm_state","c1_state","c2_state","sd_state",
    ]

    with dpg.group(horizontal=True, parent=parent_tag):
        _dropdown_tag = dpg.add_combo(
            items=_numeric_fields,
            default_value=_numeric_fields[0] if _numeric_fields else "",
            width=160,
        )
        dpg.add_button(label="New chart",   callback=_on_add_new_chart, width=85)
        dpg.add_button(label="Add to last", callback=_on_add_to_last,   width=85)
        dpg.add_spacer(width=16)
        dpg.add_text("H:", color=(160, 160, 160))
        _height_slider_tag = dpg.add_slider_int(
            min_value=MIN_CHART_HEIGHT, max_value=MAX_CHART_HEIGHT,
            default_value=DEFAULT_CHART_HEIGHT,
            width=120, callback=_on_height_slider, format="%dpx",
        )
        dpg.add_spacer(width=16)
        dpg.add_text("T:", color=(160, 160, 160))
        _window_slider_tag = dpg.add_slider_int(
            min_value=5, max_value=300,
            default_value=WINDOW_SECS,
            width=120, callback=_on_window_slider, format="%ds",
        )

    # Pre-create history deques for every numeric field
    for f in _numeric_fields:
        if f not in _history_vals:
            _history_vals[f] = deque(maxlen=300 * 100)

    dpg.add_separator(parent=parent_tag)


def set_telem_fields(telem_obj):
    global _numeric_fields
    _numeric_fields = _get_numeric_fields(telem_obj)
    if dpg.does_item_exist(_dropdown_tag):
        dpg.configure_item(_dropdown_tag, items=_numeric_fields)


def _clear_all_buffers():
    """Wipe all series data and history — called on DAQ power-cycle detection."""
    global _last_timestamp
    _last_timestamp = 0.0
    _history_x.clear()
    for buf in _history_vals.values():
        buf.clear()
    for chart in _charts:
        chart["t_start"] = _latest_time
        for s in chart["series"]:
            s["x"].clear()
            s["y"].clear()
            if dpg.does_item_exist(s["series_tag"]):
                dpg.set_value(s["series_tag"], [[], []])


def update(telem_obj, timestamp):
    global _latest_time, _latest_telem
    global _last_timestamp
    _latest_time  = timestamp
    _latest_telem = telem_obj
    _poll_drag()

    # Detect DAQ power-cycle: timestamp jumped backwards or reset near zero
    if _last_timestamp > 0 and (timestamp < _last_timestamp - 1.0 or (timestamp < 5.0 and _last_timestamp > 10.0)):
        _clear_all_buffers()
    _last_timestamp = timestamp

    # Always record history regardless of whether charts exist
    _history_x.append(timestamp)
    for field in _numeric_fields:
        if field not in _history_vals:
            _history_vals[field] = deque(maxlen=300 * 100)
        _history_vals[field].append(float(getattr(telem_obj, field, 0.0)))

    if not _charts:
        return

    for chart in _charts:
        all_y = []
        for s in chart["series"]:
            val = float(getattr(telem_obj, s["field"], 0.0))
            s["x"].append(timestamp)
            s["y"].append(val)
            all_y.extend(s["y"])
            if dpg.does_item_exist(s["series_tag"]):
                dpg.set_value(s["series_tag"], [list(s["x"]), list(s["y"])])

        if not dpg.does_item_exist(chart["x_axis_tag"]):
            continue

        elapsed = timestamp - chart["t_start"]
        if elapsed < WINDOW_SECS:
            x_lo, x_hi = chart["t_start"], chart["t_start"] + WINDOW_SECS
        else:
            x_lo, x_hi = timestamp - WINDOW_SECS, timestamp

        dpg.set_axis_limits(chart["x_axis_tag"], x_lo, x_hi)

        if dpg.does_item_exist(chart["y_axis_tag"]) and all_y:
            visible_y = [y for s in chart["series"]
                         for x, y in zip(s["x"], s["y"]) if x >= x_lo]
            if visible_y:
                lo, hi = min(visible_y), max(visible_y)
                pad = (hi - lo) * 0.1 if hi != lo else abs(lo) * 0.05 or 1.0
                dpg.set_axis_limits(chart["y_axis_tag"], lo - pad, hi + pad)