
import io
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


st.set_page_config(
    page_title="知識循環ダッシュボード",
    page_icon="📚",
    layout="wide",
)

st.title("📚 知識循環ダッシュボード")
st.caption("二橋亭・TANZAN Books・一箱古本市の売上、在庫、イベント効果をまとめて確認します。")


REQUIRED_COLUMNS = [
    "商品ID",
    "書名",
    "著者",
    "ジャンル",
    "棚主",
    "仕入日",
    "仕入価格",
    "出品日",
    "販売日",
    "販売価格",
    "販売チャネル",
    "イベント名",
    "イベント日",
    "SNS紹介日",
]

COLUMN_DESCRIPTIONS = {
    "商品ID": "本ごとの重複しない番号",
    "書名": "本のタイトル",
    "著者": "著者名",
    "ジャンル": "国際政治、文学、哲学など",
    "棚主": "棚オーナー名",
    "仕入日": "仕入れた日",
    "仕入価格": "仕入れ値",
    "出品日": "棚やネットに出した日",
    "販売日": "売れた日。未販売は空欄",
    "販売価格": "売価。未販売は空欄または0",
    "販売チャネル": "二橋亭、一箱古本市、ネットなど",
    "イベント名": "関連イベント名",
    "イベント日": "関連イベントの開催日",
    "SNS紹介日": "SNSで紹介した日",
}


def load_data(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        raw = uploaded_file.getvalue()
        for enc in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("CSVの文字コードを判定できませんでした。UTF-8またはCP932で保存してください。")
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("CSV、XLSX、XLSファイルを選んでください。")


def prepare_data(df):
    df = df.copy()

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "次の列がありません: " + "、".join(missing)
        )

    date_cols = ["仕入日", "出品日", "販売日", "イベント日", "SNS紹介日"]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    number_cols = ["仕入価格", "販売価格"]
    for col in number_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    today = pd.Timestamp.today().normalize()
    df["販売済み"] = df["販売日"].notna()
    df["粗利益"] = np.where(
        df["販売済み"],
        df["販売価格"] - df["仕入価格"],
        0
    )

    df["在庫日数"] = np.where(
        df["出品日"].notna(),
        (
            df["販売日"].fillna(today) - df["出品日"]
        ).dt.days,
        np.nan
    )

    df["利益率"] = np.where(
        df["販売価格"] > 0,
        df["粗利益"] / df["販売価格"],
        np.nan
    )

    df["30日以内販売"] = (
        df["販売済み"]
        & df["在庫日数"].notna()
        & (df["在庫日数"] <= 30)
    )

    df["イベント後30日以内販売"] = (
        df["販売済み"]
        & df["イベント日"].notna()
        & ((df["販売日"] - df["イベント日"]).dt.days.between(0, 30))
    )

    df["SNS後30日以内販売"] = (
        df["販売済み"]
        & df["SNS紹介日"].notna()
        & ((df["販売日"] - df["SNS紹介日"]).dt.days.between(0, 30))
    )

    return df


def yen(value):
    if pd.isna(value):
        return "-"
    return f"¥{value:,.0f}"


def pct(value):
    if pd.isna(value):
        return "-"
    return f"{value:.1%}"


def draw_bar(series, title, ylabel):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    series.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


with st.sidebar:
    st.header("データ読込")
    uploaded = st.file_uploader(
        "CSVまたはExcelファイル",
        type=["csv", "xlsx", "xls"],
    )

    st.markdown("### 必要な列")
    for col in REQUIRED_COLUMNS:
        st.write(f"・{col}")

    st.info("販売前の本は「販売日」を空欄にしてください。")


if uploaded is None:
    st.warning("左側からデータファイルをアップロードしてください。")
    st.markdown("### このダッシュボードで確認できること")
    st.write(
        "売上、粗利益、販売率、在庫回転、棚主別成績、ジャンル別成績、"
        "イベントやSNS紹介後の販売状況を確認できます。"
    )
    st.stop()


try:
    raw_df = load_data(uploaded)
    df = prepare_data(raw_df)
except Exception as exc:
    st.error(str(exc))
    st.stop()


st.sidebar.success(f"{len(df):,}冊を読み込みました")

# 絞り込み
st.sidebar.header("絞り込み")

genres = sorted(df["ジャンル"].dropna().astype(str).unique())
owners = sorted(df["棚主"].dropna().astype(str).unique())
channels = sorted(df["販売チャネル"].dropna().astype(str).unique())

selected_genres = st.sidebar.multiselect("ジャンル", genres, default=genres)
selected_owners = st.sidebar.multiselect("棚主", owners, default=owners)
selected_channels = st.sidebar.multiselect("販売チャネル", channels, default=channels)

filtered = df.copy()

if selected_genres:
    filtered = filtered[filtered["ジャンル"].astype(str).isin(selected_genres)]
if selected_owners:
    filtered = filtered[filtered["棚主"].astype(str).isin(selected_owners)]

# 販売チャネルは未販売本が空欄の場合があるため、販売済み集計時にだけ使用
sold = filtered[filtered["販売済み"]].copy()
if selected_channels:
    sold = sold[sold["販売チャネル"].astype(str).isin(selected_channels)]


total_books = len(filtered)
sold_books = int(filtered["販売済み"].sum())
inventory_books = total_books - sold_books
sales = sold["販売価格"].sum()
gross_profit = sold["粗利益"].sum()
sell_through = sold_books / total_books if total_books else np.nan
avg_days = sold["在庫日数"].mean()
within_30 = filtered["30日以内販売"].mean() if total_books else np.nan


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["全体", "棚・ジャンル", "在庫", "イベント・SNS", "明細"]
)

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("登録冊数", f"{total_books:,}冊")
    c2.metric("販売冊数", f"{sold_books:,}冊")
    c3.metric("在庫冊数", f"{inventory_books:,}冊")
    c4.metric("販売率", pct(sell_through))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("売上", yen(sales))
    c6.metric("粗利益", yen(gross_profit))
    c7.metric("平均在庫日数", f"{avg_days:.1f}日" if pd.notna(avg_days) else "-")
    c8.metric("30日以内販売率", pct(within_30))

    st.subheader("月別売上")
    monthly = (
        sold.dropna(subset=["販売日"])
        .set_index("販売日")
        .resample("ME")["販売価格"]
        .sum()
    )
    if not monthly.empty:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        monthly.plot(ax=ax, marker="o")
        ax.set_title("月別売上推移")
        ax.set_xlabel("")
        ax.set_ylabel("売上（円）")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.info("販売日のデータがありません。")


with tab2:
    left, right = st.columns(2)

    with left:
        st.subheader("棚主別粗利益")
        owner_profit = (
            sold.groupby("棚主", dropna=False)["粗利益"]
            .sum()
            .sort_values(ascending=False)
            .head(15)
        )
        if not owner_profit.empty:
            draw_bar(owner_profit, "棚主別粗利益", "粗利益（円）")
        else:
            st.info("棚主別の販売データがありません。")

    with right:
        st.subheader("ジャンル別販売冊数")
        genre_sales = (
            sold.groupby("ジャンル", dropna=False)
            .size()
            .sort_values(ascending=False)
            .head(15)
        )
        if not genre_sales.empty:
            draw_bar(genre_sales, "ジャンル別販売冊数", "販売冊数")
        else:
            st.info("ジャンル別の販売データがありません。")

    st.subheader("棚主別成績表")
    owner_summary = (
        filtered.groupby("棚主", dropna=False)
        .agg(
            登録冊数=("商品ID", "count"),
            販売冊数=("販売済み", "sum"),
            売上=("販売価格", "sum"),
            粗利益=("粗利益", "sum"),
            平均在庫日数=("在庫日数", "mean"),
        )
        .reset_index()
    )
    owner_summary["販売率"] = (
        owner_summary["販売冊数"] / owner_summary["登録冊数"]
    )
    st.dataframe(
        owner_summary.sort_values("粗利益", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


with tab3:
    st.subheader("長期在庫")
    days_limit = st.slider("何日以上を長期在庫とするか", 30, 365, 90, 10)

    long_inventory = filtered[
        (~filtered["販売済み"])
        & (filtered["在庫日数"] >= days_limit)
    ].copy()

    c1, c2 = st.columns(2)
    c1.metric("長期在庫冊数", f"{len(long_inventory):,}冊")
    c2.metric(
        "長期在庫の仕入総額",
        yen(long_inventory["仕入価格"].sum())
    )

    show_cols = [
        "商品ID", "書名", "著者", "ジャンル", "棚主",
        "出品日", "仕入価格", "在庫日数"
    ]
    st.dataframe(
        long_inventory[show_cols].sort_values("在庫日数", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


with tab4:
    st.subheader("イベント効果")
    event_rows = filtered[filtered["イベント日"].notna()].copy()

    if len(event_rows):
        event_summary = (
            event_rows.groupby("イベント名", dropna=False)
            .agg(
                **{
                    "対象冊数": ("商品ID", "count"),
                    "30日以内販売冊数": ("イベント後30日以内販売", "sum"),
                    "売上": ("販売価格", "sum"),
                    "粗利益": ("粗利益", "sum"),
                }
            )
            .reset_index()
        )
        event_summary["イベント後30日販売率"] = (
            event_summary["30日以内販売冊数"] / event_summary["対象冊数"]
        )
        st.dataframe(
            event_summary.sort_values("イベント後30日販売率", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("イベント日のデータがありません。")

    st.subheader("SNS紹介効果")
    sns_rows = filtered[filtered["SNS紹介日"].notna()].copy()

    if len(sns_rows):
        c1, c2 = st.columns(2)
        c1.metric("SNS紹介した本", f"{len(sns_rows):,}冊")
        c2.metric(
            "紹介後30日以内販売率",
            pct(sns_rows["SNS後30日以内販売"].mean())
        )
        st.dataframe(
            sns_rows[
                [
                    "商品ID", "書名", "著者", "ジャンル",
                    "SNS紹介日", "販売日", "SNS後30日以内販売",
                    "販売価格", "粗利益"
                ]
            ].sort_values("SNS紹介日", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("SNS紹介日のデータがありません。")


with tab5:
    st.subheader("全データ")
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    export = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "分析済みデータをCSVで保存",
        data=export,
        file_name=f"知識循環分析_{datetime.now():%Y%m%d}.csv",
        mime="text/csv",
    )
