"""Minimal Dash app for the Apartment Search Dashboard.

This file creates a small Dash app that shows:
- KAB newest-row table (sorted by `place_in_queue`)
- s.dk newest-row table (sorted by `place_in_queue`)
- Combined price-per-m2 table (cheapest first)
- KAB history multi-line chart and Top-10 ETA table

Keep the app simple and dependency-light so it's easy to run locally.
"""
from __future__ import annotations

import dash
from dash import dcc, html, Input, Output, dash_table
import plotly.express as px
import pandas as pd
from typing import Any, Dict, List, cast

from dashboard_data import load_and_prepare_all


def df_to_columns(df) -> List[Dict[str, str]]:
    """Return a list of DataTable column definitions or an empty list.

    Accepts None or an empty DataFrame safely.
    """
    if df is None or getattr(df, "columns", None) is None:
        return []
    return [{"name": c, "id": c} for c in df.columns]


def make_app(data_dir: str = "data"):
    data = load_and_prepare_all(data_dir)

    kab_latest = data.get("kab_latest", None)
    sdk_latest = data.get("sdk_latest", None)
    price_table = data.get("price_table", None)
    kab_history = data.get("kab_history", None)
    kab_history_full = data.get("kab_history_full", None)
    sdk_history = data.get("sdk_history", None)
    sdk_history_full = data.get("sdk_history_full", None)
    top10_eta = data.get("top10_eta", None)
    summary_stats = data.get("summary_stats", None)

    app = dash.Dash(__name__, title="Apartment Search Dashboard")

    # tab styles for a dark-gray appearance
    tab_style = {"backgroundColor": "#2b2b2b", "color": "#eaeaea", "padding": "6px", "border": "none"}
    tab_selected_style = {"backgroundColor": "#444444", "color": "#ffffff", "padding": "6px"}

    # build initial figure for KAB history (dark template)
    if kab_history is not None and not kab_history.empty:
        # ignore apartments with extremely large queue placements (user-specified cutoff)
        df_hist = kab_history.copy()
        if "place_in_queue" in df_hist.columns:
            df_hist["place_in_queue"] = pd.to_numeric(df_hist["place_in_queue"], errors="coerce")
            df_hist = df_hist[~(df_hist["place_in_queue"] > 5000)]

        if df_hist is not None and not df_hist.empty:
            fig_history = px.line(
                df_hist,
                x="snapshot_time",
                y="place_in_queue",
                color="apartment_id",
                hover_name="apartment_id",
                labels={"place_in_queue": "Place in queue"},
                markers=True,
            )
            fig_history.update_yaxes(autorange=True)
            fig_history.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_history.update_xaxes(tickformat="%Y-%m-%d")
        else:
            fig_history = px.line()
            fig_history.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_history.update_xaxes(tickformat="%Y-%m-%d")
    else:
        fig_history = px.line()
        fig_history.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
        fig_history.update_xaxes(tickformat="%Y-%m-%d")

    # prepare s.dk history figure (use min queue value)
    if sdk_history is not None and not sdk_history.empty:
        df_sdk_hist = sdk_history.copy()
        if "place_in_queue" in df_sdk_hist.columns:
            df_sdk_hist["place_in_queue"] = pd.to_numeric(df_sdk_hist["place_in_queue"], errors="coerce")
            df_sdk_hist = df_sdk_hist[~(df_sdk_hist["place_in_queue"] > 5000)]

        if df_sdk_hist is not None and not df_sdk_hist.empty:
            fig_sdk = px.line(
                df_sdk_hist,
                x="snapshot_time",
                y="place_in_queue",
                color="apartment_id",
                hover_name="apartment_id",
                labels={"place_in_queue": "Place in queue"},
                markers=True,
            )
            fig_sdk.update_yaxes(autorange=True)
            fig_sdk.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_sdk.update_xaxes(tickformat="%Y-%m-%d")
        else:
            fig_sdk = px.line()
            fig_sdk.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_sdk.update_xaxes(tickformat="%Y-%m-%d")
    else:
        fig_sdk = px.line()
        fig_sdk.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
        fig_sdk.update_xaxes(tickformat="%Y-%m-%d")

    # prepare KAB lowest-queue history figure (overall min + avg of lowest 10 per snapshot)
    df_for_lowest = kab_history_full if (kab_history_full is not None and not kab_history_full.empty) else kab_history
    # default table outputs
    lowest_table_columns = []
    lowest_table_data = []

    if df_for_lowest is not None and not df_for_lowest.empty:
        df_lowest = df_for_lowest.copy()
        if "snapshot_time" in df_lowest.columns:
            df_lowest["snapshot_time"] = pd.to_datetime(df_lowest["snapshot_time"], errors="coerce")
        if "place_in_queue" in df_lowest.columns:
            df_lowest["place_in_queue"] = pd.to_numeric(df_lowest["place_in_queue"], errors="coerce")
            # ignore very large queue placements (user doesn't care about them)
            df_lowest = df_lowest[~(df_lowest["place_in_queue"] > 5000)]
        try:
            # overall minimum per snapshot
            df_min = df_lowest.groupby("snapshot_time", as_index=False)["place_in_queue"].min().sort_values("snapshot_time")
            # mean of the lowest N places per snapshot (N=10)
            def _avg_lowest_n(s, n=10):
                vals = s.dropna().nsmallest(n)
                return float(vals.mean()) if not vals.empty else float("nan")

            df_avg10 = (
                df_lowest.groupby("snapshot_time")["place_in_queue"]
                .apply(lambda s: _avg_lowest_n(s, 10))
                .reset_index(name="avg_lowest_10")
                .sort_values("snapshot_time")
            )
        except Exception:
            df_min = pd.DataFrame(columns=["snapshot_time", "place_in_queue"])
            df_avg10 = pd.DataFrame(columns=["snapshot_time", "avg_lowest_10"])

        # Prepare a merged table for display (always attempt to show all snapshot times)
        try:
            if "snapshot_time" in df_min.columns:
                df_min["snapshot_time"] = pd.to_datetime(df_min["snapshot_time"], errors="coerce")
            if "snapshot_time" in df_avg10.columns:
                df_avg10["snapshot_time"] = pd.to_datetime(df_avg10["snapshot_time"], errors="coerce")

            df_min_table = df_min.rename(columns={"place_in_queue": "lowest_place_in_queue"})
            # show newest rows first in the table (newest on top)
            df_lowest_table = pd.merge(df_min_table, df_avg10, on="snapshot_time", how="outer").sort_values("snapshot_time", ascending=False)

            # if the merged table is empty but we have raw snapshot times, build rows with NaNs
            if df_lowest_table.empty and "snapshot_time" in df_lowest.columns:
                # ensure newest snapshot times are first for the table
                times = sorted(df_lowest["snapshot_time"].dropna().unique(), reverse=True)
                df_lowest_table = pd.DataFrame({"snapshot_time": times})

            # format snapshot_time for display
            if "snapshot_time" in df_lowest_table.columns:
                df_lowest_table["snapshot_time"] = pd.to_datetime(df_lowest_table["snapshot_time"], errors="coerce")
                df_lowest_table["snapshot_time"] = df_lowest_table["snapshot_time"].dt.strftime("%Y-%m-%d")

            lowest_table_columns = [{"name": c, "id": c} for c in df_lowest_table.columns]
            lowest_table_data = df_lowest_table.to_dict("records")
        except Exception:
            lowest_table_columns = []
            lowest_table_data = []

        # Build figure: prefer plotting numeric mins; show markers for visibility
        plot_min = df_min.dropna(subset=["place_in_queue"]) if not df_min.empty else pd.DataFrame()
        plot_avg = df_avg10.dropna(subset=["avg_lowest_10"]) if not df_avg10.empty else pd.DataFrame()

        if not plot_min.empty:
            fig_lowest = px.line(
                plot_min,
                x="snapshot_time",
                y="place_in_queue",
                labels={"place_in_queue": "Lowest place in queue"},
                markers=True,
            )
            if fig_lowest.data:
                fig_lowest.data[0].name = "Lowest place in queue"
                fig_lowest.data[0].showlegend = True
            if not plot_avg.empty:
                fig_lowest.add_scatter(
                    x=plot_avg["snapshot_time"],
                    y=plot_avg["avg_lowest_10"],
                    mode="lines+markers",
                    name="Avg lowest 10",
                    line=dict(dash="dash", width=2),
                )
            fig_lowest.update_yaxes(autorange=True)
            fig_lowest.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_lowest.update_xaxes(tickformat="%Y-%m-%d")
        elif not plot_avg.empty:
            fig_lowest = px.line(
                plot_avg,
                x="snapshot_time",
                y="avg_lowest_10",
                labels={"avg_lowest_10": "Avg lowest 10"},
                markers=True,
            )
            if fig_lowest.data:
                fig_lowest.data[0].name = "Avg lowest 10"
                fig_lowest.data[0].showlegend = True
            fig_lowest.update_yaxes(autorange=True)
            fig_lowest.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_lowest.update_xaxes(tickformat="%Y-%m-%d")
        else:
            fig_lowest = px.line()
            fig_lowest.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")
            fig_lowest.update_xaxes(tickformat="%Y-%m-%d")
    else:
        fig_lowest = px.line()
        fig_lowest.update_layout(template="plotly_dark", plot_bgcolor="#111111", paper_bgcolor="#111111", font_color="#eaeaea")

    page_style = {"backgroundColor": "#111111", "color": "#eaeaea", "minHeight": "100vh", "padding": "16px"}

    # Prepare table columns/data (hide technical cols and add an 'Open' action)
    # hide technical or redundant columns (urls are available via the Open action)
    # also hide addresses and intermediate price/area columns and 'source'
    exclude_cols = {"snapshot_time", "source_file", "apartment_id", "url", "building_url", "ranking", "place_in_queue_min", "place_in_queue_max", "addresses", "avg_rent", "avg_area", "source"}

    def visible_columns_for(df):
        if df is None or getattr(df, "columns", None) is None:
            return []
        return [c for c in df.columns if c not in exclude_cols]

    # KAB table data and columns
    if kab_latest is not None and not kab_latest.empty:
        kab_table_data = kab_latest.sort_values("place_in_queue").to_dict("records")
        for r in kab_table_data:
            # add a simple Open marker; the actual URL is looked up from row['building_url']
            r.setdefault("open_url", "open link")
        # hide internal numeric price columns from the KAB table — we keep only the human-friendly range
        kab_visible = visible_columns_for(kab_latest)
        kab_visible = [c for c in kab_visible if c not in {"price_per_m2_min", "price_per_m2_max", "price_per_m2"}]

        # keep place_in_queue first and place_change_30d immediately after it
        if "place_in_queue" in kab_visible:
            kab_visible.remove("place_in_queue")
            if "place_change_30d" in kab_visible:
                kab_visible.remove("place_change_30d")
            kab_visible = ["place_in_queue", "place_change_30d"] + kab_visible

        kab_table_columns = [{"name": c, "id": c} for c in kab_visible]
        kab_table_columns.append({"name": "Open", "id": "open_url"})
    else:
        kab_table_data = []
        kab_table_columns = []

    # s.dk table data and columns
    if sdk_latest is not None and not sdk_latest.empty:
        sdk_table_data = sdk_latest.sort_values("place_in_queue").to_dict("records")
        for r in sdk_table_data:
            r.setdefault("open_url", "open link")
        # ensure `place_in_queue` is the left-most column for quick scanning
        sdk_cols = visible_columns_for(sdk_latest)
        if "place_in_queue" in sdk_cols:
            sdk_cols = ["place_in_queue"] + [c for c in sdk_cols if c != "place_in_queue"]
        sdk_table_columns = [{"name": c, "id": c} for c in sdk_cols]
        sdk_table_columns.append({"name": "Open", "id": "open_url"})
    else:
        sdk_table_data = []
        sdk_table_columns = []

    # Price table: ensure an 'url' field exists (dashboard_data populates it when available)
    if price_table is not None and not price_table.empty:
        price_table_data = price_table.to_dict("records")
        for r in price_table_data:
            r.setdefault("open_url", "open link")
        # include the `source` column in the price table; hide internal apartment_id and url
        price_cols = [c for c in price_table.columns if c not in ("apartment_id", "url")]
        # ensure `place_in_queue` is visible and placed right after `price_per_m2` for quick scanning
        if "price_per_m2" in price_cols and "place_in_queue" in price_cols:
            price_cols.remove("place_in_queue")
            try:
                idx = price_cols.index("price_per_m2")
            except ValueError:
                idx = len(price_cols) - 1
            price_cols.insert(idx + 1, "place_in_queue")
        price_table_columns = [{"name": c, "id": c} for c in price_cols]
        price_table_columns.append({"name": "Open", "id": "open_url"})
    else:
        price_table_data = []
        price_table_columns = []

    # Summary columns
    summary_columns = df_to_columns(summary_stats)

    # top10 ETA columns (use the prepared order from dashboard_data)
    if top10_eta is not None and not top10_eta.empty:
        top10_df = top10_eta.copy()
        if "last_snapshot" in top10_df.columns:
            top10_df["last_snapshot"] = pd.to_datetime(top10_df["last_snapshot"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        if "eta" in top10_df.columns:
            top10_df["eta"] = pd.to_datetime(top10_df["eta"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        top10_columns = [{"name": c, "id": c} for c in top10_df.columns if c != "apartment_id"]
        top10_data = top10_df.to_dict("records")
    else:
        top10_columns = []
        top10_data = []

    app.layout = html.Div([
        html.H1("Apartment Search Dashboard"),
        html.Div(f"Data directory: {data_dir}"),
        dcc.Tabs([
            dcc.Tab(label="Summary", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("Summary Statistics"),
                dash_table.DataTable(
                    id="summary-table",
                    columns=cast(List[Dict[str, Any]], summary_columns),
                    data=cast(List[Dict[str, Any]], (summary_stats.to_dict("records") if (summary_stats is not None and not summary_stats.empty) else [])),
                    page_size=10,
                    style_table={"overflowX": "auto", "maxWidth": "100%"},
                    style_data_conditional=[
                        {"if": {"state": "active"}, "backgroundColor": "#111111", "border": "1px solid #333333"},
                        {"if": {"state": "selected"}, "backgroundColor": "#111111", "border": "1px solid #333333"},
                    ],
                    style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "120px", "maxWidth": "360px", "backgroundColor": "#111111", "color": "#eaeaea", "border": "1px solid #333333"},
                    style_header={"backgroundColor": "#222222", "color": "#eaeaea"},
                ),
            ]),
            dcc.Tab(label="Price / m²", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("Cheapest by price per m²"),
                dash_table.DataTable(
                    id="price-table",
                    columns=cast(List[Dict[str, Any]], price_table_columns),
                    data=cast(List[Dict[str, Any]], price_table_data),
                    page_action='none',
                    style_table={"overflowX": "auto", "maxWidth": "100%"},
                    style_data_conditional=[
                        {"if": {"column_id": "open_url"}, "color": "#1e90ff", "textDecoration": "underline", "cursor": "pointer", "textAlign": "center"},
                        {"if": {"state": "active"}, "backgroundColor": "#111111", "border": "1px solid #333333"},
                        {"if": {"state": "selected"}, "backgroundColor": "#111111", "border": "1px solid #333333"},
                    ],
                    style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "100px", "maxWidth": "300px", "backgroundColor": "#111111", "color": "#eaeaea", "border": "1px solid #333333"},
                    style_header={"backgroundColor": "#222222", "color": "#eaeaea"},
                ),
            ]),
            dcc.Tab(label="KAB History", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("KAB queue history (all apartments)"),
                dcc.Checklist(id='kab-show-all', options=[{'label': 'Show all data', 'value': 'all'}], value=[], inline=True),
                dcc.Graph(id="kab-history", figure=fig_history, style={"height": "600px"}),
                html.H3("Top-10 ETA to queue = 0 (KAB)"),
                dash_table.DataTable(
                    id="top10-eta",
                    columns=cast(List[Dict[str, Any]], top10_columns),
                    data=cast(List[Dict[str, Any]], top10_data),
                    page_action='none',
                    style_table={"overflowX": "auto", "maxWidth": "100%"},
                    style_data_conditional=[
                        {"if": {"state": "active"}, "backgroundColor": "transparent", "border": "none"},
                        {"if": {"state": "selected"}, "backgroundColor": "transparent", "border": "none"},
                    ],
                    style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "120px", "maxWidth": "360px", "backgroundColor": "#111111", "color": "#eaeaea", "border": "1px solid #222222"},
                    style_header={"backgroundColor": "#222222", "color": "#eaeaea"},
                ),
            ]),
            dcc.Tab(label="KAB Lowest Queue", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("KAB - Lowest queue position over time"),
                dcc.Graph(id="kab-lowest-queue", figure=fig_lowest, style={"height": "450px"}),
                html.H3("Lowest and avg lowest 10 per snapshot"),
                dash_table.DataTable(
                    id="kab-lowest-table",
                    columns=cast(List[Dict[str, Any]], lowest_table_columns),
                    data=cast(List[Dict[str, Any]], lowest_table_data),
                    page_action='none',
                    page_size=10,
                    style_table={"overflowX": "auto", "maxWidth": "100%"},
                    style_data_conditional=[
                        {"if": {"state": "active"}, "backgroundColor": "transparent", "border": "none"},
                        {"if": {"state": "selected"}, "backgroundColor": "transparent", "border": "none"},
                    ],
                    style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "120px", "maxWidth": "360px", "backgroundColor": "#111111", "color": "#eaeaea", "border": "1px solid #222222"},
                    style_header={"backgroundColor": "#222222", "color": "#eaeaea"},
                ),
            ]),
            dcc.Tab(label="s.dk History", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("s.dk queue history (min queue)"),
                dcc.Checklist(id='sdk-show-all', options=[{'label': 'Show all data', 'value': 'all'}], value=[], inline=True),
                dcc.Graph(id="sdk-history", figure=fig_sdk, style={"height": "600px"}),
            ]),
            dcc.Tab(label="KAB Data", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("KAB - Latest (one row per apartment, newest)"),
                html.Div(id="kab-table-container", children=[
                    dash_table.DataTable(
                        id="kab-table",
                        columns=cast(List[Dict[str, Any]], kab_table_columns),
                        data=cast(List[Dict[str, Any]], kab_table_data),
                        page_action='none',
                        style_table={"overflowX": "auto", "maxWidth": "100%"},
                        style_data_conditional=[
                                {"if": {"column_id": "open_url"}, "color": "#1e90ff", "textDecoration": "underline", "cursor": "pointer", "textAlign": "center"},
                                {"if": {"state": "active"}, "backgroundColor": "#111111", "border": "1px solid #333333"},
                                {"if": {"state": "selected"}, "backgroundColor": "#111111", "border": "1px solid #333333"},
                            ],
                            style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "100px", "maxWidth": "300px", "backgroundColor": "#111111", "color": "#eaeaea", "border": "1px solid #333333"},
                        style_header={"backgroundColor": "#222222", "color": "#eaeaea"},
                    )
                ]),
            ]),
            dcc.Tab(label="S_DK Data", style=tab_style, selected_style=tab_selected_style, children=[
                html.H2("s.dk - Latest (one row per apartment, newest)"),
                html.Div(id="sdk-table-container", children=[
                    dash_table.DataTable(
                        id="sdk-table",
                        columns=cast(List[Dict[str, Any]], sdk_table_columns),
                        data=cast(List[Dict[str, Any]], sdk_table_data),
                        page_action='none',
                        style_table={"overflowX": "auto", "maxWidth": "100%"},
                        style_data_conditional=[
                            {"if": {"column_id": "open_url"}, "color": "#1e90ff", "textDecoration": "underline", "cursor": "pointer", "textAlign": "center"},
                            {"if": {"state": "active"}, "backgroundColor": "transparent", "border": "none"},
                            {"if": {"state": "selected"}, "backgroundColor": "transparent", "border": "none"},
                        ],
                        style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "100px", "maxWidth": "300px", "backgroundColor": "#111111", "color": "#eaeaea", "border": "1px solid #222222"},
                        style_header={"backgroundColor": "#222222", "color": "#eaeaea"},
                    )
                ]),
            ]),
        ], style={"backgroundColor": "#222222", "color": "#eaeaea"}),
        html.Div(id='open-url-kab', style={'display': 'none'}),
        html.Div(id='open-url-sdk', style={'display': 'none'}),
        html.Div(id='open-url-price', style={'display': 'none'}),
    ], style=page_style)

    # callback: highlight selected apartment(s) from kab table in the history chart
    @app.callback(
        Output("kab-history", "figure"),
        [Input("kab-table", "active_cell"), Input("kab-table", "data"), Input("kab-show-all", "value")],
    )
    def update_history(active_cell, kab_table_data, show_all_values):
        # choose full history when toggle is set, else use the filtered (changing) view
        current_history = kab_history_full if (show_all_values and 'all' in show_all_values and kab_history_full is not None) else kab_history
        # always ignore apartments with extremely large queue placements
        if current_history is None or current_history.empty:
            empty_fig = px.line()
            empty_fig.update_layout(template='plotly_dark', plot_bgcolor='#111111', paper_bgcolor='#111111', font_color='#eaeaea')
            return empty_fig
        current_history = current_history.copy()
        if "place_in_queue" in current_history.columns:
            current_history["place_in_queue"] = pd.to_numeric(current_history["place_in_queue"], errors="coerce")
            current_history = current_history[~(current_history["place_in_queue"] > 5000)]

        selected_id = None
        if active_cell and kab_table_data:
            try:
                r = kab_table_data[active_cell.get('row')]
                selected_id = r.get('apartment_id') if isinstance(r, dict) else None
            except Exception:
                selected_id = None

        if selected_id:
            df_plot = current_history[current_history["apartment_id"] == selected_id]
        else:
            df_plot = current_history

        fig = px.line(
            df_plot,
            x="snapshot_time",
            y="place_in_queue",
            color="apartment_id",
            hover_name="apartment_id",
            markers=True,
        )
        fig.update_yaxes(autorange=True)
        fig.update_layout(template='plotly_dark', plot_bgcolor='#111111', paper_bgcolor='#111111', font_color='#eaeaea')
        fig.update_xaxes(tickformat="%Y-%m-%d")

        return fig
    # callback: update s.dk history (separate function, not nested)
    @app.callback(
        Output("sdk-history", "figure"),
        [Input("sdk-show-all", "value")],
    )
    def update_sdk_history(show_all_values):
        current_history = sdk_history_full if (show_all_values and 'all' in show_all_values and sdk_history_full is not None) else sdk_history
        # ignore apartments with extremely large queue placements
        if current_history is None or current_history.empty:
            empty_fig = px.line()
            empty_fig.update_layout(template='plotly_dark', plot_bgcolor='#111111', paper_bgcolor='#111111', font_color='#eaeaea')
            return empty_fig
        current_history = current_history.copy()
        if "place_in_queue" in current_history.columns:
            current_history["place_in_queue"] = pd.to_numeric(current_history["place_in_queue"], errors="coerce")
            current_history = current_history[~(current_history["place_in_queue"] > 5000)]

        fig = px.line(
            current_history,
            x="snapshot_time",
            y="place_in_queue",
            color="apartment_id",
            hover_name="apartment_id",
            markers=True,
        )
        fig.update_yaxes(autorange=True)
        fig.update_layout(template='plotly_dark', plot_bgcolor='#111111', paper_bgcolor='#111111', font_color='#eaeaea')
        fig.update_xaxes(tickformat="%Y-%m-%d")
        return fig

    # clientside callbacks to open external URLs when user clicks the 'Open' cell
    app.clientside_callback(
        """
        function(active_cell, table_data) {
            if(!active_cell || !table_data) { return ''; }
            var row = table_data[active_cell.row];
            if(!row) { return ''; }
            var col = active_cell.column_id;
            if(col === 'open_url') {
                var url = row['building_url'] || row['url'] || null;
                if(url) { window.open(url, '_blank'); }
            }
            return '';
        }
        """,
        Output('open-url-kab', 'children'),
        [Input('kab-table', 'active_cell'), Input('kab-table', 'data')]
    )

    app.clientside_callback(
        """
        function(active_cell, table_data) {
            if(!active_cell || !table_data) { return ''; }
            var row = table_data[active_cell.row];
            if(!row) { return ''; }
            var col = active_cell.column_id;
            if(col === 'open_url') {
                var url = row['url'] || row['building_url'] || null;
                if(url) { window.open(url, '_blank'); }
            }
            return '';
        }
        """,
        Output('open-url-sdk', 'children'),
        [Input('sdk-table', 'active_cell'), Input('sdk-table', 'data')]
    )

    app.clientside_callback(
        """
        function(active_cell, table_data) {
            if(!active_cell || !table_data) { return ''; }
            var row = table_data[active_cell.row];
            if(!row) { return ''; }
            var col = active_cell.column_id;
            if(col === 'open_url') {
                var url = row['url'] || row['building_url'] || null;
                if(url) { window.open(url, '_blank'); }
            }
            return '';
        }
        """,
        Output('open-url-price', 'children'),
        [Input('price-table', 'active_cell'), Input('price-table', 'data')]
    )

    return app


if __name__ == "__main__":
    app = make_app()
    app.run(host="0.0.0.0", debug=False)
