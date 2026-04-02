import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


def _try_convert_dates(df: pd.DataFrame) -> pd.DataFrame:
    working_df = df.copy()

    for col in working_df.columns:
        if working_df[col].dtype == "object":
            try:
                converted = pd.to_datetime(working_df[col], errors="raise")
                if converted.notna().sum() == len(working_df[col]):
                    working_df[col] = converted
            except Exception:
                pass

    return working_df


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _date_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]


def _categorical_cols(df: pd.DataFrame) -> list[str]:
    numeric = set(_numeric_cols(df))
    dates = set(_date_cols(df))
    return [c for c in df.columns if c not in numeric and c not in dates]


def _looks_like_correlation_question(question: str) -> bool:
    q = (question or "").lower()
    phrases = [
        "correlate",
        "correlation",
        "relationship",
        "related to",
        "compare",
        "against",
        "versus",
        "vs",
    ]
    return any(p in q for p in phrases)


def _looks_like_trend_question(question: str) -> bool:
    q = (question or "").lower()
    phrases = [
        "trend",
        "trend over time",
        "over time",
        "across time",
        "time series",
        "by month",
        "by week",
        "by day",
        "month over month",
        "week over week",
        "daily trend",
        "weekly trend",
        "monthly trend",
        "over the last",
        "through time",
    ]
    return any(p in q for p in phrases)


def _looks_time_like_column_name(col_name: str) -> bool:
    c = (col_name or "").lower()
    keywords = [
        "date",
        "day",
        "week",
        "month",
        "year",
        "quarter",
        "time",
        "year_month",
        "month_name",
        "day_of_week",
        "week_of_month",
    ]
    return any(k in c for k in keywords)


def _find_time_like_column(df: pd.DataFrame) -> str | None:
    # First prefer real datetime columns
    date_cols = _date_cols(df)
    if date_cols:
        return date_cols[0]

    # Then use semantic-ish time bucket names
    for col in df.columns:
        if _looks_time_like_column_name(col):
            return col

    return None


def detect_chart_spec(df: pd.DataFrame, question: str = "") -> dict:
    if df is None or df.empty:
        return {"type": None}

    working_df = _try_convert_dates(df)

    cols = list(working_df.columns)
    if len(cols) < 2:
        return {"type": None}

    numeric_cols = _numeric_cols(working_df)
    date_cols = _date_cols(working_df)
    categorical_cols = _categorical_cols(working_df)

    if len(cols) == 1 and len(numeric_cols) == 1:
        return {"type": None}

    # Correlation / relationship: one category + two numeric columns
    if len(categorical_cols) >= 1 and len(numeric_cols) >= 2:
        if _looks_like_correlation_question(question) or len(cols) == 3:
            return {
                "type": "scatter",
                "label": categorical_cols[0],
                "x": numeric_cols[0],
                "y": numeric_cols[1],
            }

    # Strong trend preference from question language
    if _looks_like_trend_question(question):
        time_col = _find_time_like_column(working_df)
        if time_col and numeric_cols:
            y_col = next((c for c in numeric_cols if c != time_col), numeric_cols[0])
            return {"type": "line", "x": time_col, "y": y_col}

    if len(cols) == 2:
        c1, c2 = cols[0], cols[1]

        if c1 in date_cols and c2 in numeric_cols:
            return {"type": "line", "x": c1, "y": c2}

        if c2 in date_cols and c1 in numeric_cols:
            return {"type": "line", "x": c2, "y": c1}

        # Time-like string/integer buckets should also prefer line when question suggests trend
        if _looks_like_trend_question(question):
            if _looks_time_like_column_name(c1) and c2 in numeric_cols:
                return {"type": "line", "x": c1, "y": c2}
            if _looks_time_like_column_name(c2) and c1 in numeric_cols:
                return {"type": "line", "x": c2, "y": c1}

        if c1 in categorical_cols and c2 in numeric_cols:
            return {"type": "bar", "x": c1, "y": c2}

        if c2 in categorical_cols and c1 in numeric_cols:
            return {"type": "bar", "x": c2, "y": c1}

    # One time-like + one numeric among multiple columns
    time_col = _find_time_like_column(working_df)
    if time_col and len(numeric_cols) >= 1:
        y_col = next((c for c in numeric_cols if c != time_col), numeric_cols[0])
        if _looks_like_trend_question(question) or time_col in date_cols:
            return {"type": "line", "x": time_col, "y": y_col}

    if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
        return {"type": "bar", "x": categorical_cols[0], "y": numeric_cols[0]}

    return {"type": None}


def compute_correlation_insight(df: pd.DataFrame, x: str, y: str):
    if df is None or df.empty:
        return None

    working_df = df[[x, y]].dropna().copy()
    if len(working_df) < 2:
        return None

    corr = working_df[x].corr(working_df[y])
    if pd.isna(corr):
        return None

    strength = abs(corr)
    if strength >= 0.7:
        strength_text = "strong"
    elif strength >= 0.4:
        strength_text = "moderate"
    elif strength >= 0.2:
        strength_text = "weak"
    else:
        strength_text = "little to no"

    if corr > 0.1:
        direction = "positive"
    elif corr < -0.1:
        direction = "negative"
    else:
        direction = "no clear linear"

    return f"Correlation between {x} and {y}: {corr:.2f} ({strength_text} {direction} relationship)."


def render_chart(df: pd.DataFrame, question: str = ""):
    if df is None or df.empty:
        return

    working_df = _try_convert_dates(df)
    spec = detect_chart_spec(working_df, question=question)

    if not spec.get("type"):
        return

    st.subheader("Chart")

    chart_type = spec["type"]

    if chart_type == "line":
        x = spec["x"]
        y = spec["y"]
        chart_df = working_df[[x, y]].copy().sort_values(by=x)
        st.line_chart(chart_df.set_index(x))
        return

    if chart_type == "bar":
        x = spec["x"]
        y = spec["y"]
        chart_df = working_df[[x, y]].copy()
        st.bar_chart(chart_df.set_index(x))
        return

    if chart_type == "scatter":
        label_col = spec["label"]
        x = spec["x"]
        y = spec["y"]

        plot_df = working_df[[label_col, x, y]].dropna().copy()

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(plot_df[x], plot_df[y])

        for _, row in plot_df.iterrows():
            ax.annotate(
                str(row[label_col]),
                (row[x], row[y]),
                fontsize=8,
                alpha=0.8,
            )

        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(f"{y} vs {x}")
        st.pyplot(fig)

        corr_text = compute_correlation_insight(plot_df, x, y)
        if corr_text:
            st.caption(corr_text)