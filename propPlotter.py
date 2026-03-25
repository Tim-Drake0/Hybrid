"""
Telemetry Viewer — DearPyGui
────────────────────────────
• File picker  : open one or more CSV files via file dialog
• Left panel   : draggable params per file (tabbed), discrete toggles
• Subplots     : N stacked interactive plots, legend top-right
• Crosshair    : vertical bar + time label + per-series values synced across all subplots
• Right-click  : remove a series
"""

import os
import dearpygui.dearpygui as dpg
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
NUM_SUBPLOTS  = 3
SIDEBAR_W     = 240
PLOT_MIN_H    = 180
PADDING       = 8
DRAG_TAG      = "dragged_param"

DISCRETE_COLS = ['C1', 'C2', 'FILL', 'VENT', 'MOV', 'ARM', 'PY1', 'PY2']

PALETTE = [
    (31,  119, 180, 255),
    (255, 127,  14, 255),
    (44,  160,  44, 255),
    (214,  39,  40, 255),
    (148, 103, 189, 255),
    (140,  86,  75, 255),
    (227, 119, 194, 255),
    (127, 127, 127, 255),
    (188, 189,  34, 255),
    ( 23, 190, 207, 255),
]

DISCRETE_COLORS = [
    (255,  80,  80, 60),
    ( 80, 160, 255, 60),
    ( 80, 255, 120, 60),
    (255, 200,  50, 60),
    (200,  80, 255, 60),
    ( 50, 220, 220, 60),
    (255, 140,  30, 60),
    (180, 255,  80, 60),
]

CROSSHAIR_COLOR = (255, 220, 50, 200)
CROSSHAIR_W     = 1.5

# ── Per-file data store ───────────────────────────────────────────────────────
# files[file_id] = {
#   'path', 'df', 'time_s', 'analog_params', 'discrete_cols',
#   'discrete_spans', 'discrete_enabled'
# }
files: dict[str, dict] = {}
color_counter = [0]

def next_color():
    c = PALETTE[color_counter[0] % len(PALETTE)]
    color_counter[0] += 1
    return c

def compute_spans(time_s, df, col):
    vals = df[col].tolist()
    spans = []
    start = None
    for k, (t, v) in enumerate(zip(time_s, vals)):
        if v == 1 and start is None:
            start = t
        elif v != 1 and start is not None:
            spans.append((start, time_s[k - 1]))
            start = None
    if start is not None:
        spans.append((start, time_s[-1]))
    return spans

def _first_significant_high_time(time_s, df, col, min_duration=5.0):
    """Return the start time of the first run where col==1 that lasts at least
    min_duration seconds. Ignores brief blips. Falls back to time_s[0]."""
    vals = df[col].tolist()
    in_high = False
    high_start = None
    for i, (t, v) in enumerate(zip(time_s, vals)):
        if v == 1 and not in_high:
            in_high = True
            high_start = t
        elif v != 1 and in_high:
            if t - high_start >= min_duration:
                return high_start
            in_high = False   # blip — ignore and keep looking
    # still high at end of data — check if long enough
    if in_high and (time_s[-1] - high_start) >= min_duration:
        return high_start
    return time_s[0]

def _arm_significant_fall_time(time_s, df, min_high_duration=10.0):
    if 'ARM' not in df.columns:
        return time_s[-1]
    vals = df['ARM'].tolist()
    in_high = False
    high_start = None
    for t, v in zip(time_s, vals):
        if v == 1 and not in_high:
            in_high = True
            high_start = t
        elif v != 1 and in_high:
            if t - high_start >= min_high_duration:
                return t
            in_high = False
    return time_s[-1]

def load_file(path: str) -> str:
    """Load a CSV, register it in `files`, return its file_id.
    Time axis is shifted so that FILL first going high == t=0.
    """
    file_id = path
    if file_id in files:
        return file_id
    df = pd.read_csv(path)
    time_col  = df.columns[0]
    time_s_raw = [t / 1000.0 for t in df[time_col].tolist()]
    disc_cols  = [c for c in DISCRETE_COLS if c in df.columns]
    analog     = [c for c in df.columns if c != time_col and c not in disc_cols]

    # Shift time so FILL first rising == 0; fallback to start of recording
    fill_t0 = (_first_significant_high_time(time_s_raw, df, 'FILL')
               if 'FILL' in disc_cols else time_s_raw[0])
    time_s = [t - fill_t0 for t in time_s_raw]

    spans   = {c: compute_spans(time_s, df, c) for c in disc_cols}

    # x_left is always -5 (5 s before FILL rises)
    # x_right is ARM significant fall (relative) + 5 s padding
    arm_fall_abs = _arm_significant_fall_time(time_s_raw, df)
    x_left  = -5.0
    x_right = (arm_fall_abs - fill_t0) + 5.0

    files[file_id] = dict(
        path=path,
        df=df,
        time_s=time_s,
        analog_params=analog,
        discrete_cols=disc_cols,
        discrete_spans=spans,
        discrete_enabled={c: False for c in disc_cols},
        x_left=x_left,
        x_right=x_right,
    )
    return file_id

# ── Plot state ────────────────────────────────────────────────────────────────
# subplot_series[i] = list of dicts:
#   {col, file_id, series_tag, theme_tag, color}
subplot_series: list[list[dict]] = [[] for _ in range(NUM_SUBPLOTS)]

plot_tags        = []
yaxis_tags       = []
xaxis_tags       = []
vline_tags       = []
vline_annot_tags = []
value_annot_tags: list[list[str]] = [[] for _ in range(NUM_SUBPLOTS)]

# shade_tags[file_id][col][subplot_idx] = list of {tag, t0, t1}
shade_tags: dict[str, dict[str, list[list[dict]]]] = {}

# ── Y-axis helpers ────────────────────────────────────────────────────────────
def fit_y_to_data(subplot_idx: int):
    series_list = subplot_series[subplot_idx]
    if not series_list:
        return
    all_vals = []
    for entry in series_list:
        fdata = files[entry['file_id']]
        all_vals.extend(fdata['df'][entry['col']].tolist())
    if not all_vals:
        return
    lo, hi = min(all_vals), max(all_vals)
    pad = (hi - lo) * 0.05 if hi != lo else 1.0
    dpg.set_axis_limits(yaxis_tags[subplot_idx], lo - pad, hi + pad)

def _data_big(subplot_idx: int) -> float:
    series_list = subplot_series[subplot_idx]
    if not series_list:
        return 1e6
    all_vals = []
    for entry in series_list:
        fdata = files[entry['file_id']]
        all_vals.extend(fdata['df'][entry['col']].tolist())
    if not all_vals:
        return 1e6
    lo, hi = min(all_vals), max(all_vals)
    span = (hi - lo) if hi != lo else 1.0
    return max(abs(hi), abs(lo)) + span * 20

# ── Shade spans ───────────────────────────────────────────────────────────────
def _shade_tag(file_id, col, subplot_idx, span_idx):
    safe = file_id.replace('\\', '_').replace('/', '_').replace(':', '_').replace('.', '_')
    return f"shade_{safe}_{col}_{subplot_idx}_{span_idx}"

def draw_shade_spans(file_id: str, col: str, subplot_idx: int):
    fdata = files[file_id]
    di    = fdata['discrete_cols'].index(col)
    color = DISCRETE_COLORS[di % len(DISCRETE_COLORS)]
    yaxis = yaxis_tags[subplot_idx]
    spans = fdata['discrete_spans'][col]

    if file_id not in shade_tags:
        shade_tags[file_id] = {}
    if col not in shade_tags[file_id]:
        shade_tags[file_id][col] = [[] for _ in range(NUM_SUBPLOTS)]

    for k, (t0, t1) in enumerate(spans):
        tag     = _shade_tag(file_id, col, subplot_idx, k)
        already = any(e['tag'] == tag for e in shade_tags[file_id][col][subplot_idx])
        if not dpg.does_item_exist(tag) and not already:
            BIG = _data_big(subplot_idx)
            dpg.add_shade_series(
                [t0, t1], [BIG, BIG],
                y2=[-BIG, -BIG],
                label=None,
                parent=yaxis,
                tag=tag,
            )
            with dpg.theme() as shade_th:
                with dpg.theme_component(dpg.mvShadeSeries):
                    dpg.add_theme_color(dpg.mvPlotCol_Fill, color,
                                        category=dpg.mvThemeCat_Plots)
                    dpg.add_theme_color(dpg.mvPlotCol_Line, (0, 0, 0, 0),
                                        category=dpg.mvThemeCat_Plots)
            dpg.bind_item_theme(tag, shade_th)
            shade_tags[file_id][col][subplot_idx].append({'tag': tag, 't0': t0, 't1': t1})
    fit_y_to_data(subplot_idx)

def remove_shade_spans(file_id: str, col: str, subplot_idx: int):
    if file_id not in shade_tags:
        return
    if col not in shade_tags[file_id]:
        return
    for entry in shade_tags[file_id][col][subplot_idx]:
        if dpg.does_item_exist(entry['tag']):
            dpg.delete_item(entry['tag'])
    shade_tags[file_id][col][subplot_idx].clear()

def set_discrete_visible(file_id: str, col: str, enabled: bool):
    files[file_id]['discrete_enabled'][col] = enabled
    for i in range(NUM_SUBPLOTS):
        if enabled:
            draw_shade_spans(file_id, col, i)
        else:
            remove_shade_spans(file_id, col, i)

# ── X-axis limits ────────────────────────────────────────────────────────────
def apply_x_limits():
    """Set x limits on ALL subplots.
    Left  = min(x_left)  across every file that has at least one series plotted.
    Right = max(x_right) across those same files.
    Falls back to the full time range of all loaded files if nothing plotted yet.
    """
    plotted_fids = set()
    for sl in subplot_series:
        for e in sl:
            plotted_fids.add(e['file_id'])

    source = {fid: files[fid] for fid in plotted_fids} if plotted_fids else files
    if not source:
        return

    x_left  = min(fd['x_left']  for fd in source.values())
    x_right = max(fd['x_right'] for fd in source.values())

    for xat in xaxis_tags:
        dpg.set_axis_limits(xat, x_left, x_right)

# ── Series add/remove ─────────────────────────────────────────────────────────
def add_series(subplot_idx: int, col: str, file_id: str, label_override: str = None):
    if any(e['col'] == col and e['file_id'] == file_id
           for e in subplot_series[subplot_idx]):
        return
    fdata  = files[file_id]
    color  = next_color()
    safe   = file_id.replace('\\','_').replace('/','_').replace(':','_').replace('.','_')
    s_tag  = f"series_{subplot_idx}_{safe}_{col}"
    th_tag = f"theme_{subplot_idx}_{safe}_{col}"
    label  = label_override if label_override else col
    dpg.add_line_series(fdata['time_s'], fdata['df'][col].tolist(),
                        label=label,
                        parent=yaxis_tags[subplot_idx],
                        tag=s_tag)
    with dpg.theme(tag=th_tag):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color,
                                category=dpg.mvThemeCat_Plots)
    dpg.bind_item_theme(s_tag, th_tag)
    subplot_series[subplot_idx].append(
        dict(col=col, file_id=file_id, series_tag=s_tag,
             theme_tag=th_tag, color=color))
    fit_y_to_data(subplot_idx)
    apply_x_limits()
    for dcol in fdata['discrete_cols']:
        if fdata['discrete_enabled'][dcol]:
            draw_shade_spans(file_id, dcol, subplot_idx)

def remove_series(subplot_idx: int, col: str, file_id: str):
    lst = subplot_series[subplot_idx]
    for e in lst:
        if e['col'] == col and e['file_id'] == file_id:
            for tag in (e['series_tag'], e['theme_tag']):
                if dpg.does_item_exist(tag):
                    dpg.delete_item(tag)
            lst.remove(e)
            _clear_value_annots(subplot_idx)
            return

def make_drop_cb(idx):
    def _drop(sender, app_data):
        # app_data is "file_id||col"
        file_id, col = app_data.split('||', 1)
        add_series(idx, col, file_id)
        # apply_x_limits() is already called inside add_series
        fit_y_to_data(idx)
    return _drop

# ── Shade extents updater ─────────────────────────────────────────────────────
def update_shade_extents():
    for i in range(NUM_SUBPLOTS):
        BIG = _data_big(i)
        for fid, col_dict in shade_tags.items():
            for col, subplot_list in col_dict.items():
                if i < len(subplot_list):
                    for entry in subplot_list[i]:
                        if dpg.does_item_exist(entry['tag']):
                            dpg.configure_item(entry['tag'],
                                               x=[entry['t0'], entry['t1']],
                                               y1=[BIG, BIG],
                                               y2=[-BIG, -BIG])

# ── Crosshair ─────────────────────────────────────────────────────────────────
_last_plot_time = [None]

def _interp_value(file_id: str, col: str, t: float) -> float:
    fdata = files[file_id]
    time_s = fdata['time_s']
    vals   = fdata['df'][col].tolist()
    lo, hi = 0, len(time_s) - 1
    if t <= time_s[lo]: return vals[lo]
    if t >= time_s[hi]: return vals[hi]
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if time_s[mid] <= t: lo = mid
        else: hi = mid
    dt = time_s[hi] - time_s[lo]
    if dt == 0: return vals[lo]
    return vals[lo] + (t - time_s[lo]) / dt * (vals[hi] - vals[lo])

def _clear_value_annots(subplot_idx: int):
    for tag in value_annot_tags[subplot_idx]:
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
    value_annot_tags[subplot_idx].clear()

def _rebuild_value_annots(subplot_idx: int, plot_time: float):
    _clear_value_annots(subplot_idx)
    series_list = subplot_series[subplot_idx]
    if not series_list:
        return
    y_min, y_max = dpg.get_axis_limits(yaxis_tags[subplot_idx])
    y_range = y_max - y_min if y_max != y_min else 1.0
    step    = y_range * 0.07
    y_start = y_max - y_range * 0.10
    for k, entry in enumerate(series_list):
        col   = entry['col']
        fid   = entry['file_id']
        color = entry['color']
        val   = _interp_value(fid, col, plot_time)
        tag   = f"vannot_{subplot_idx}_{k}"
        dpg.add_plot_annotation(
            tag=tag,
            parent=plot_tags[subplot_idx],
            label=f"{col}: {val:.3g}",
            default_value=[plot_time, y_start - k * step],
            offset=(10.0, 0.0),
            color=color,
            clamped=True,
            show=True,
        )
        value_annot_tags[subplot_idx].append(tag)

def update_crosshair():
    hovered   = False
    plot_time = 0.0
    for pt in plot_tags:
        if dpg.is_item_hovered(pt):
            mp = dpg.get_plot_mouse_pos()
            if mp is not None:
                plot_time = mp[0]
                hovered   = True
            break
    time_changed = (plot_time != _last_plot_time[0])
    _last_plot_time[0] = plot_time if hovered else None
    for i, vt in enumerate(vline_tags):
        at = vline_annot_tags[i]
        if hovered:
            dpg.configure_item(vt, default_value=plot_time, show=True)
            y_min, y_max = dpg.get_axis_limits(yaxis_tags[i])
            label_y = y_max - (y_max - y_min) * 0.04
            dpg.configure_item(at,
                               default_value=[plot_time, label_y],
                               label=f"{plot_time:.2f} s",
                               show=True)
            if time_changed:
                _rebuild_value_annots(i, plot_time)
        else:
            dpg.configure_item(vt, show=False)
            dpg.configure_item(at, show=False)
            _clear_value_annots(i)

# ── Sidebar rebuild ───────────────────────────────────────────────────────────
def rebuild_sidebar():
    """Rebuild the parameter list and discrete toggles for all loaded files."""
    dpg.delete_item("sidebar_content", children_only=True)

    if not files:
        dpg.add_text("No files loaded.", parent="sidebar_content",
                     color=(140, 140, 140, 255))
        return

    with dpg.tab_bar(parent="sidebar_content", tag="file_tabs"):
        for file_id, fdata in files.items():
            tab_label = os.path.basename(file_id)
            with dpg.tab(label=tab_label):

                dpg.add_text("Drag onto a subplot →",
                             color=(140, 140, 140, 255),
                             wrap=SIDEBAR_W - 20)
                dpg.add_separator()
                dpg.add_spacer(height=4)

                for param in fdata['analog_params']:
                    payload = f"{file_id}||{param}"
                    with dpg.group():
                        btn = dpg.add_button(label=f"  {param}",
                                             width=SIDEBAR_W - 24, height=26)
                        with dpg.theme() as btn_th:
                            with dpg.theme_component(dpg.mvButton):
                                dpg.add_theme_color(dpg.mvThemeCol_Button,
                                                    (45, 55, 72, 255))
                                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,
                                                    (66, 85, 110, 255))
                                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,
                                                    (90, 120, 160, 255))
                                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                        dpg.bind_item_theme(btn, btn_th)
                        with dpg.drag_payload(parent=btn, drag_data=payload,
                                              payload_type=DRAG_TAG):
                            dpg.add_text(f"  ↳ {param}")
                    dpg.add_spacer(height=2)

                # Discrete toggles
                if fdata['discrete_cols']:
                    dpg.add_spacer(height=10)
                    dpg.add_separator()
                    dpg.add_spacer(height=6)
                    dpg.add_text("Discrete Highlights",
                                 color=(200, 200, 200, 255))
                    dpg.add_spacer(height=4)

                    for di, col in enumerate(fdata['discrete_cols']):
                        dc     = DISCRETE_COLORS[di % len(DISCRETE_COLORS)]
                        swatch = (dc[0], dc[1], dc[2], 255)

                        def _make_toggle(fid=file_id, c=col):
                            def _toggle(sender, app_data):
                                set_discrete_visible(fid, c, app_data)
                            return _toggle

                        with dpg.group(horizontal=True):
                            sb = dpg.add_button(label=" ", width=18, height=18)
                            with dpg.theme() as sw_th:
                                with dpg.theme_component(dpg.mvButton):
                                    dpg.add_theme_color(dpg.mvThemeCol_Button, swatch)
                                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, swatch)
                                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, swatch)
                                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
                            dpg.bind_item_theme(sb, sw_th)
                            dpg.add_checkbox(label=col, default_value=False,
                                             callback=_make_toggle())
                        dpg.add_spacer(height=3)

# ── File dialog callback ──────────────────────────────────────────────────────
def on_files_selected(sender, app_data):
    """Called when user confirms the file dialog."""
    selections = app_data.get('selections', {})
    first_load = len(files) == 0
    first_file_id = None

    for fname, fpath in selections.items():
        if fpath not in files:
            fid = load_file(fpath)
            if first_file_id is None:
                first_file_id = fid

    rebuild_sidebar()

    # On very first load, add default series (x limits set inside add_series)
    if first_load and first_file_id:
        fdata = files[first_file_id]
        defaults = {'PT1[psi]': 'PHIL1', 'PT4[psi]': 'TANK1'}
        for col, alias in defaults.items():
            if col in fdata['analog_params']:
                add_series(0, col, first_file_id, label_override=alias)

# ── Build UI ──────────────────────────────────────────────────────────────────
dpg.create_context()

vp_w, vp_h = 1500, 960
dpg.create_viewport(title='Telemetry Viewer', width=vp_w, height=vp_h,
                    resizable=True)
dpg.setup_dearpygui()

# File dialog
with dpg.file_dialog(
    tag="file_dialog",
    directory_selector=False,
    show=False,
    callback=on_files_selected,
    width=800, height=500,
):
    dpg.add_file_extension(".csv", color=(0, 255, 0, 255), custom_text="[CSV]")
    dpg.add_file_extension(".*")

with dpg.window(tag="main_win", no_title_bar=True, no_resize=True,
                no_move=True, no_scrollbar=True,
                pos=(0, 0), width=vp_w, height=vp_h):

    # Top bar with Open button
    with dpg.group(horizontal=True):
        open_btn = dpg.add_button(
            label="  📂  Open CSV(s)",
            height=32,
            callback=lambda: dpg.configure_item("file_dialog",
                                                show=True,
                                                file_count=0)
        )
        with dpg.theme() as open_btn_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button,        (50, 90, 60, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,  (70, 120, 80, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,   (90, 150, 100, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
        dpg.bind_item_theme(open_btn, open_btn_theme)
        dpg.add_text("  Drag params from the left panel onto any subplot",
                     color=(140, 140, 140, 255))

    dpg.add_spacer(height=4)

    with dpg.group(horizontal=True):

        # ── SIDEBAR ───────────────────────────────────────────────────────────
        with dpg.child_window(tag="sidebar", width=SIDEBAR_W, height=-1,
                               border=True):
            dpg.add_text("Parameters", color=(200, 200, 200, 255))
            dpg.add_separator()
            dpg.add_spacer(height=4)
            with dpg.group(tag="sidebar_content"):
                dpg.add_text("Open a CSV to begin.",
                             color=(140, 140, 140, 255))

        # ── SUBPLOTS ──────────────────────────────────────────────────────────
        with dpg.child_window(tag="plots_area", width=-1, height=-1,
                               border=False, no_scrollbar=False):

            plot_h = max(PLOT_MIN_H,
                         (vp_h - 50 - PADDING * (NUM_SUBPLOTS + 1)) // NUM_SUBPLOTS)

            for i in range(NUM_SUBPLOTS):
                with dpg.child_window(tag=f"subplot_win_{i}",
                                      width=-1, height=plot_h, border=True):
                    pt  = f"plot_{i}"
                    yat = f"yaxis_{i}"
                    xat = f"xaxis_{i}"
                    plot_tags.append(pt)
                    yaxis_tags.append(yat)
                    xaxis_tags.append(xat)

                    with dpg.plot(tag=pt, label=f"Subplot {i+1}",
                                  height=-1, width=-1,
                                  payload_type=DRAG_TAG,
                                  drop_callback=make_drop_cb(i)):

                        dpg.add_plot_legend(
                            location=dpg.mvPlot_Location_NorthEast,
                            outside=False,
                        )
                        dpg.add_plot_axis(dpg.mvXAxis, label="Time relative to FILL [sec]",
                                          tag=xat)
                        dpg.add_plot_axis(dpg.mvYAxis, label="", tag=yat)

                        vt = f"vline_{i}"
                        vline_tags.append(vt)
                        dpg.add_drag_line(tag=vt, color=CROSSHAIR_COLOR,
                                          thickness=CROSSHAIR_W,
                                          vertical=True, default_value=0.0,
                                          show=False, callback=None)

                        at = f"vline_annot_{i}"
                        vline_annot_tags.append(at)
                        dpg.add_plot_annotation(
                            tag=at,
                            label="0.00 s",
                            default_value=[0.0, 0.0],
                            offset=(8.0, -14.0),
                            color=CROSSHAIR_COLOR,
                            clamped=True,
                            show=False,
                        )

                dpg.add_spacer(height=PADDING)

# ── Right-click context popup ─────────────────────────────────────────────────
with dpg.window(tag="ctx_popup", show=False, popup=True,
                no_title_bar=True, no_resize=True, min_size=(260, 40)):
    dpg.add_group(tag="ctx_popup_content")

def show_ctx_popup(subplot_idx):
    dpg.delete_item("ctx_popup_content", children_only=True)
    p = "ctx_popup_content"

    # ── Subplot title rename ───────────────────────────────────────────────────
    current_title = dpg.get_item_label(plot_tags[subplot_idx])
    dpg.add_text("Subplot title:", parent=p, color=(180, 180, 180, 255))
    title_input = dpg.add_input_text(
        parent=p,
        default_value=current_title,
        width=240,
        on_enter=False,
        tag=f"_title_input_{subplot_idx}",
    )
    def _make_rename_title(si=subplot_idx, ti=title_input):
        def _rename(s, a):
            dpg.configure_item(plot_tags[si], label=dpg.get_value(ti))
        return _rename
    dpg.add_button(label="Rename Title", parent=p, width=240,
                   callback=_make_rename_title())

    # ── Axis limits ────────────────────────────────────────────────────────────
    dpg.add_spacer(height=6, parent=p)
    dpg.add_separator(parent=p)
    dpg.add_spacer(height=4, parent=p)
    dpg.add_text("Axis Limits:", parent=p, color=(180, 180, 180, 255))

    xat = xaxis_tags[subplot_idx]
    yat = yaxis_tags[subplot_idx]
    xlo, xhi = dpg.get_axis_limits(xat)
    ylo, yhi = dpg.get_axis_limits(yat)

    # X axis row
    dpg.add_text("X:", parent=p, color=(140, 200, 255, 255))
    xmin_tag = f"_xmin_{subplot_idx}"
    xmax_tag = f"_xmax_{subplot_idx}"
    with dpg.group(horizontal=True, parent=p):
        dpg.add_text("Min", color=(160,160,160,255))
        dpg.add_input_float(tag=xmin_tag, default_value=xlo,
                            width=100, step=0, format="%.1f")
        dpg.add_text("Max", color=(160,160,160,255))
        dpg.add_input_float(tag=xmax_tag, default_value=xhi,
                            width=100, step=0, format="%.1f")

    def _make_apply_x(si=subplot_idx, xmn=xmin_tag, xmx=xmax_tag):
        def _apply(s, a):
            lo = dpg.get_value(xmn)
            hi = dpg.get_value(xmx)
            if hi > lo:
                dpg.set_axis_limits(xaxis_tags[si], lo, hi)
        return _apply

    def _make_auto_x(si=subplot_idx):
        def _auto(s, a):
            dpg.set_axis_limits_auto(xaxis_tags[si])
        return _auto

    with dpg.group(horizontal=True, parent=p):
        dpg.add_button(label="Apply X", width=116, callback=_make_apply_x())
        dpg.add_button(label="Auto X",  width=116, callback=_make_auto_x())

    # Y axis row
    dpg.add_spacer(height=4, parent=p)
    dpg.add_text("Y:", parent=p, color=(180, 255, 140, 255))
    ymin_tag = f"_ymin_{subplot_idx}"
    ymax_tag = f"_ymax_{subplot_idx}"
    with dpg.group(horizontal=True, parent=p):
        dpg.add_text("Min", color=(160,160,160,255))
        dpg.add_input_float(tag=ymin_tag, default_value=ylo,
                            width=100, step=0, format="%.1f")
        dpg.add_text("Max", color=(160,160,160,255))
        dpg.add_input_float(tag=ymax_tag, default_value=yhi,
                            width=100, step=0, format="%.1f")

    def _make_apply_y(si=subplot_idx, ymn=ymin_tag, ymx=ymax_tag):
        def _apply(s, a):
            lo = dpg.get_value(ymn)
            hi = dpg.get_value(ymx)
            if hi > lo:
                dpg.set_axis_limits(yaxis_tags[si], lo, hi)
        return _apply

    def _make_auto_y(si=subplot_idx):
        def _auto(s, a):
            fit_y_to_data(si)
        return _auto

    with dpg.group(horizontal=True, parent=p):
        dpg.add_button(label="Apply Y", width=116, callback=_make_apply_y())
        dpg.add_button(label="Auto Y",  width=116, callback=_make_auto_y())

    series_list = subplot_series[subplot_idx]
    if series_list:
        dpg.add_spacer(height=6, parent=p)
        dpg.add_separator(parent=p)
        dpg.add_spacer(height=4, parent=p)
        dpg.add_text("Series:", parent=p, color=(180, 180, 180, 255))

        for k, entry in enumerate(list(series_list)):
            col   = entry['col']
            fid   = entry['file_id']
            color = entry['color']
            fname = os.path.basename(fid)
            s_tag = entry['series_tag']
            current_label = dpg.get_item_label(s_tag) or col

            dpg.add_spacer(height=3, parent=p)
            with dpg.group(horizontal=True, parent=p):
                dpg.add_text("■", color=color)
                dpg.add_text(f"{col} ({fname})", color=(160, 160, 160, 255))

            label_input_tag = f"_label_input_{subplot_idx}_{k}"
            dpg.add_input_text(
                parent=p,
                default_value=current_label,
                width=200,
                on_enter=False,
                tag=label_input_tag,
            )

            def _make_rename_series(st=s_tag, lit=label_input_tag):
                def _rename(s, a):
                    dpg.configure_item(st, label=dpg.get_value(lit))
                return _rename

            def _make_rm(si=subplot_idx, co=col, fi=fid):
                def _rm():
                    remove_series(si, co, fi)
                    dpg.configure_item("ctx_popup", show=False)
                return _rm

            with dpg.group(horizontal=True, parent=p):
                dpg.add_button(label="Rename", width=115,
                               callback=_make_rename_series())
                dpg.add_button(label="Remove", width=115,
                               callback=_make_rm())

    dpg.configure_item("ctx_popup", show=True)

with dpg.handler_registry():
    def _rclick(sender, app_data):
        for idx, pt in enumerate(plot_tags):
            if dpg.is_item_hovered(pt):
                show_ctx_popup(idx)
                return
    dpg.add_mouse_click_handler(button=1, callback=_rclick)

# ── Viewport resize ───────────────────────────────────────────────────────────
def _on_resize():
    w = dpg.get_viewport_width()
    h = dpg.get_viewport_height()
    dpg.configure_item("main_win", width=w, height=h)

dpg.set_viewport_resize_callback(_on_resize)

# ── Render loop ───────────────────────────────────────────────────────────────
dpg.show_viewport()

while dpg.is_dearpygui_running():
    update_shade_extents()
    update_crosshair()
    dpg.render_dearpygui_frame()

dpg.destroy_context()