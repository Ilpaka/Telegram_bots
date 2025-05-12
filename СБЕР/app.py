import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
from plotly.subplots import make_subplots

# --- Функции экспорта графиков и в Excel ---
def download_chart_xlsx_native(fig, key):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        workbook = writer.book

        for trace in fig.data:
            sheet = (trace.name or "series")[:31]

            # 1) Pie
            if hasattr(trace, 'labels') and hasattr(trace, 'values'):
                df = pd.DataFrame({'label': trace.labels, 'value': trace.values})
                df.to_excel(writer, sheet_name=sheet, index=False)
                worksheet = writer.sheets.get(sheet) or workbook.worksheets[-1]
                chart = workbook.add_chart({"type": "pie"})
                chart.add_series({
                    "name":       trace.name or "pie",
                    "categories": [sheet, 1, 0, len(df), 0],
                    "values":     [sheet, 1, 1, len(df), 1],
                })
                worksheet.insert_chart("D2", chart, {"x_scale": 1.2, "y_scale": 1.2})

            # 2) Candlestick 
            elif all(hasattr(trace, attr) for attr in ('open','high','low','close')):
                df = pd.DataFrame({
                    'timestamp': trace.x,
                    'open':      trace.open,
                    'high':      trace.high,
                    'low':       trace.low,
                    'close':     trace.close
                })
                df.to_excel(writer, sheet_name=sheet, index=False)
                worksheet = writer.sheets.get(sheet) or workbook.worksheets[-1]
                chart = workbook.add_chart({"type": "line"})
                for i, col in enumerate(['open','high','low','close'], start=1):
                    chart.add_series({
                        "name":       col,
                        "categories": [sheet, 1, 0, len(df), 0],
                        "values":     [sheet, 1, i, len(df), i],
                    })
                chart.set_x_axis({"name": "Timestamp"})
                chart.set_y_axis({"name": "Price"})
                worksheet.insert_chart("G2", chart, {"x_scale": 1.5, "y_scale": 1.5})

            # 3) Все остальные
            else:
                x = list(trace.x)
                y = list(trace.y)
                df = pd.DataFrame({"timestamp": x, trace.name: y})
                df.to_excel(writer, sheet_name=sheet, index=False)
                worksheet = writer.sheets.get(sheet) or workbook.worksheets[-1]
                chart = workbook.add_chart({"type": "line"})
                chart.add_series({
                    "name":       trace.name,
                    "categories": [sheet, 1, 0, len(df), 0],
                    "values":     [sheet, 1, 1, len(df), 1],
                })
                chart.set_x_axis({"name": "Timestamp"})
                chart.set_y_axis({"name": trace.name})
                worksheet.insert_chart("D2", chart, {"x_scale": 1.5, "y_scale": 1.5})

    output.seek(0)
    st.download_button(
        label=f"Скачать график в Excel: {fig.layout.title.text or 'chart'}",
        data=output.read(),
        file_name=f"{fig.layout.title.text or 'chart'}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )

# Загружаем данные
@st.cache_data
def load_data():
    df = pd.read_csv('Bitcoin Pulse  Hourly Dataset from Markets Trends and Fear.csv', parse_dates=['timestamp'])
    df = df.sort_values('timestamp')
    return df

data = load_data()

grafics, bid_value, funds, fgi, corr, table_data = st.tabs(['📈 Цены','😱 Объём торгов','💲 Фонды','☄️ Индекс Страха и Жадности','🔗 Корреляция','📄 Данные'])

with grafics:
    st.title('📊 График цен')

    st.sidebar.header('Фильтры')

    min_date = data['timestamp'].min().date()
    max_date = data['timestamp'].max().date()
    date_range = st.sidebar.date_input(
        'Диапазон дат', [min_date, max_date], min_value=min_date, max_value=max_date
    )
    if not (isinstance(date_range, (list, tuple)) and len(date_range) == 2):
        st.sidebar.warning("Выберите конечную дату")
        st.stop()
    start_date, end_date = date_range
    data_filtered = data[(data['timestamp'].dt.date >= start_date) & (data['timestamp'].dt.date <= end_date)]

    close_cols = [col for col in data.columns if col.endswith('_close')]
    asset = st.sidebar.selectbox('Выберите актив', close_cols)

    # Расчет ключевых метрик
    series = data_filtered.set_index('timestamp')[asset]
    mean_val = series.mean()
    median_val = series.median()
    std_val = series.std()
    change_pct = (series.iloc[-1] - series.iloc[0]) / series.iloc[0] * 100

    mean_val = series.mean()
    min_val = series.min()
    max_val = series.max()
    median_val = series.median()
    std_val = series.std()
    change_pct = (series.iloc[-1] - series.iloc[0]) / series.iloc[0] * 100

    mean_val, min_val, max_val = series.mean(), series.min(), series.max()
    median_val, std_val, change_pct = series.median(), series.std(), (series.iloc[-1] - series.iloc[0]) / series.iloc[0] * 100

    row1 = st.columns(3)
    row1[0].metric('Среднее', f"{mean_val:,.2f}", help='Средняя цена за выбранный период')
    row1[1].metric('Минимум', f"{min_val:,.2f}", help='Минимальная цена за период')
    row1[2].metric('Максимум', f"{max_val:,.2f}", help='Максимальная цена за период')

    row2 = st.columns(3)
    row2[0].metric('Медиана', f"{median_val:,.2f}", help='Медиана цен за период')
    row2[1].metric('Std Dev', f"{std_val:,.2f}", help='Стандартное отклонение цены')
    row2[2].metric('Изм., %', f"{change_pct:.2f}%", help='Процентное изменение цены')

    st.markdown('---')

    # График цен
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=data_filtered['timestamp'],
        y=data_filtered[asset],
        mode='lines',
        name=asset
    ))

    compare_assets = st.sidebar.multiselect(
        'Сравнение активов (отдельный график)',
        options=close_cols,
        default=[asset],
        help='Выберите несколько активов, чтобы сравнить их нормированную динамику на отдельном графике'
    )
    if len(compare_assets) >= 2:
        comp_df = data_filtered[['timestamp'] + compare_assets].copy()
        for col in compare_assets:
            mn, mx = comp_df[col].min(), comp_df[col].max()
            comp_df[col] = (comp_df[col] - mn) / (mx - mn) if mx != mn else 0.0

        comp_long = comp_df.melt(
            id_vars='timestamp',
            value_vars=compare_assets,
            var_name='Asset',
            value_name='Normalized Price'
        )

        fig_compare = px.line(
            comp_long,
            x='timestamp',
            y='Normalized Price',
            color='Asset',
            title='Сравнение нормализованных активов'
        )
        fig_compare.update_yaxes(title='Нормализованная цена')

        st.subheader('📊 Сравнительный график активов')
        st.plotly_chart(fig_compare, use_container_width=True, key='compare_chart')
        download_chart_xlsx_native(fig_compare, key='dl_compare_chart')

    #скользящая средняя
    show_ma = st.sidebar.checkbox('Показать MA (скользящую среднюю)', value=False)
    if show_ma:
        window = st.sidebar.slider('Период MA (часов)', min_value=2, max_value=72, value=24)
        ma_series = data_filtered[asset].ewm(span=window, adjust=False).mean()
        fig_line.add_trace(go.Scatter(
            x=data_filtered['timestamp'],
            y=ma_series,
            mode='lines',
            name=f'MA {window}'
        ))
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
            df_price = pd.DataFrame({'timestamp': fig_line.data[0].x})
            for trace in fig_line.data:
                df_price[trace.name] = trace.y
            df_price.to_excel(writer, sheet_name='Price', index=False)
            workbook  = writer.book
            worksheet = writer.sheets['Price']
            chart = workbook.add_chart({'type': 'line'})
            n = len(df_price)
            for i, col in enumerate(df_price.columns[1:], start=1):
                chart.add_series({
                'name':       col,
                'categories': ['Price', 1, 0, n, 0],  
                'values':     ['Price', 1, i, n, i],  
                })

            chart.set_title ({'name': 'График цен с MA и сравнением'})
            chart.set_x_axis({'name': 'Timestamp'})
            chart.set_y_axis({'name': 'Normalized Price / Price'})

            worksheet.insert_chart('G2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

        buf.seek(0)
        st.download_button(
            label='Скачать график цен с MA в XLSX',
            data=buf.read(),
            file_name='price_with_MA.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            key='dl_price_ma'
        )       

    show_candle = st.sidebar.checkbox('Показать свечной график', value=False)
    if show_candle:
        prefix = asset.replace('_close', '')
        fig_candle = go.Figure(data=[go.Candlestick(
            x=data_filtered['timestamp'],
            open=data_filtered[f'{prefix}_open'],
            high=data_filtered[f'{prefix}_high'],
            low=data_filtered[f'{prefix}_low'],
            close=data_filtered[f'{prefix}_close'],
        )])
        fig_candle.update_layout(
            title=f'Свечной график {prefix}',
            xaxis_title='Timestamp',
            yaxis_title='Price'
        )
        st.plotly_chart(fig_candle, use_container_width=True, key='candle_chart')
        download_chart_xlsx_native(fig_candle, key='dl_candle_chart')


    #прогнозирование цен (Advanced ML)
    forecast = st.sidebar.checkbox('Прогнозирование цены', value=False)
    if forecast:
        method = st.sidebar.selectbox(
            'Метод прогнозирования', ['Holt-Winters', 'Prophet', 'SARIMAX'], key='forecast_method'
        )
        horizon_option = st.sidebar.selectbox(
            'Горизонт прогноза', ['1 день (24 часа)', '1 неделя (168 часов)'], key='horizon'
        )
        horizon = 24 if '1 день' in horizon_option else 168
        if method == 'Holt-Winters':
            seasonal = st.sidebar.checkbox('Использовать сезонность (24ч)', value=True, key='hw_seasonal')
            try:
                from statsmodels.tsa.holtwinters import ExponentialSmoothing
                model = ExponentialSmoothing(
                    series,
                    trend='add',
                    seasonal='add' if seasonal else None,
                    seasonal_periods=24 if seasonal else None
                ).fit(optimized=True)
                forecast_values = model.forecast(horizon)
            except Exception as e:
                st.sidebar.error(f"Ошибка Holt-Winters: {e}")
                forecast_values = [series.iloc[-1]] * horizon
        elif method == 'Prophet':
            try:
                from prophet import Prophet
                df_prophet = data_filtered[['timestamp', asset]].rename(columns={'timestamp':'ds', asset:'y'})
                m = Prophet(seasonality_mode='multiplicative')
                m.add_seasonality(name='hourly', period=24, fourier_order=5)
                m.fit(df_prophet)
                future = m.make_future_dataframe(periods=horizon, freq='H')
                fc = m.predict(future)
                forecast_values = fc['yhat'].values[-horizon:]
            except Exception as e:
                st.sidebar.error(f"Ошибка Prophet: {e}")
                forecast_values = [series.iloc[-1]] * horizon
        else:  # SARIMAX
            try:
                from statsmodels.tsa.statespace.sarimax import SARIMAX
                model = SARIMAX(
                    series,
                    order=(1,1,1),
                    seasonal_order=(1,1,1,24),
                    enforce_stationarity=False,
                    enforce_invertibility=False
                ).fit(disp=False)
                forecast_values = model.get_forecast(steps=horizon).predicted_mean.values
            except Exception as e:
                st.sidebar.error(f"Ошибка SARIMAX: {e}")
                forecast_values = [series.iloc[-1]] * horizon
        last_timestamp = data_filtered['timestamp'].iloc[-1]
        future_index = pd.date_range(
            start=last_timestamp + pd.Timedelta(hours=1),
            periods=horizon,
            freq='H'
        )
        fig_line.add_trace(go.Scatter(
            x=future_index,
            y=forecast_values,
            mode='lines',
            name=f'Forecast ({method})'
        ))

    st.plotly_chart(fig_line, use_container_width=True, key='line_chart')
    download_chart_xlsx_native(fig_line, key='dl_line_chart')
    st.subheader('Цена vs Объём')
    prefix = asset.replace('_close', '')
    vol_col = f'{prefix}_volume'

    scatter_df = data_filtered.copy()
    scatter_df['direction'] = np.where(
        scatter_df[asset] > scatter_df[f'{prefix}_open'], 
        'Up', 
        'Down'
    )

    fig_scatter = px.scatter(
        scatter_df,
        x=asset,
        y=vol_col,
        color='direction',
        title=f'Цена vs Объём: {asset}',
        hover_data=['timestamp']
    )
    st.plotly_chart(fig_scatter, use_container_width=True, key='scatter_chart')
    export_df = scatter_df[[asset, vol_col]].rename(
    columns={asset: 'Price', vol_col: 'Volume'}
    )      
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        export_df.to_excel(writer, sheet_name='PriceVsVol', index=False)
        workbook  = writer.book
        worksheet = writer.sheets['PriceVsVol']
        n = export_df.shape[0]

        chart = workbook.add_chart({'type': 'scatter', 'subtype': 'straight_with_markers'})
        chart.add_series({
            'name':       f'Цена vs Объём: {asset}',
            'categories': ['PriceVsVol', 1, 0, n, 0],  
            'values':     ['PriceVsVol', 1, 1, n, 1],  
            'marker':     {'type': 'circle', 'size': 5},
        })
        chart.set_x_axis({'name': 'Цена'})
        chart.set_y_axis({'name': 'Объём'})
        chart.set_title({'name': f'Цена vs Объём: {asset}'})

        worksheet.insert_chart('D2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

    buf.seek(0)
    st.download_button(
        label=f'Скачать Price vs Vol XLSX: {asset}',
        data=buf.read(),
        file_name=f'price_vs_vol_{asset}.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key='dl_price_vol_table')
    

with bid_value:
    st.title('😱 Объём торгов')

    vol_cols = [col for col in data_filtered.columns if col.endswith('_volume')]
    labels = [col.replace('_volume', '') for col in vol_cols]
    values = [data_filtered[col].sum() for col in vol_cols]

    st.subheader('График покупок и продаж')

    selected_asset = st.selectbox(
        'Выберите актив для графика покупок/продаж',
        labels
    )
    prefix2 = selected_asset
    open_col = f'{prefix2}_open'
    close_col = f'{prefix2}_close'
    vol_col = f'{prefix2}_volume'
    trade_df = data_filtered[['timestamp', open_col, close_col, vol_col]].copy()

    trade_df['buy_volume'] = trade_df.apply(lambda row: row[vol_col] if row[close_col] > row[open_col] else 0, axis=1)
    trade_df['sell_volume'] = trade_df.apply(lambda row: row[vol_col] if row[close_col] <= row[open_col] else 0, axis=1)
    # Линейный график объема покупок и продаж
    fig_trade = go.Figure()

    fig_trade.add_trace(go.Scatter(
        x=trade_df['timestamp'],
        y=trade_df['buy_volume'],
        mode='lines',
        name='Покупки',
        hovertemplate='Buy: %{y}<br>%{x}'
    ))

    fig_trade.add_trace(go.Scatter(
        x=trade_df['timestamp'],
        y=trade_df['sell_volume'],
        mode='lines',
        name='Продажи',
        hovertemplate='Sell: %{y}<br>%{x}',
        line=dict(dash ='dash')
    ))

    fig_trade.update_layout(
        title=f'Объем покупок и продаж: {selected_asset}',
        xaxis_title='Timestamp',
        yaxis_title='Объем',
        legend_title='Тип сделки'
    )

    st.plotly_chart(fig_trade, use_container_width=True)
    buf = io.BytesIO()
    export_df = trade_df[['timestamp', 'buy_volume', 'sell_volume']]
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        export_df.to_excel(writer, sheet_name='Объёмы', index=False)
        workbook  = writer.book
        worksheet = writer.sheets['Объёмы']

        n_rows = export_df.shape[0]

        chart = workbook.add_chart({'type': 'line'})

        chart.add_series({
            'name':       'Покупки',
            'categories': ['Объёмы', 1, 0, n_rows, 0], 
            'values':     ['Объёмы', 1, 1, n_rows, 1],  
        })

        chart.add_series({
            'name':       'Продажи',
            'categories': ['Объёмы', 1, 0, n_rows, 0],
            'values':     ['Объёмы', 1, 2, n_rows, 2], 
        })

        chart.set_title ({'name': f'Объем покупок и продаж: {selected_asset}'})
        chart.set_x_axis({'name': 'Timestamp'})
        chart.set_y_axis({'name': 'Объем'})

        worksheet.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

    buf.seek(0)
    st.download_button(
        label=f'Скачать объёмы и график: {selected_asset}.xlsx',
        data=buf.read(),
        file_name=f'volume_{selected_asset}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        key='dl_trade_table'
    )

    fig_pie = px.pie(
        names=labels,
        values=values,
        title='Объём торгов по криптовалютам за выбранный период'
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    download_chart_xlsx_native(fig_pie, key='dl_crypto_pie')

    st.subheader('Объём торгов по фондам')

    fund_vol_cols = [col for col in data_filtered.columns if col in [f'Volume_{f}' for f in [
        'sp500', 'nasdaq', 'russell_2000', 'vix', 'cac_40', 'euro_stoxx_50', 'dow_jones', 'ftse_100', 'sptsx'
    ]]]
    fund_labels = [col.replace('Volume_', '') for col in fund_vol_cols]
    fund_values = [data_filtered[col].sum() for col in fund_vol_cols]
    fig_fund_pie = px.pie(
        names=fund_labels,
        values=fund_values,
        title='Объём торгов по фондам за выбранный период'
    )
    st.plotly_chart(fig_fund_pie, use_container_width=True)
    download_chart_xlsx_native(fig_fund_pie, key='dl_funds_pie')
with funds:
    st.title('💲 Фонды')
    st.markdown('Выберите индекс рынка для анализа:')

    fund_list = [
        'sp500', 'nasdaq', 'russell_2000', 'vix',
        'cac_40', 'euro_stoxx_50', 'dow_jones', 'ftse_100', 'sptsx',
        'ibovespa', 'ipc_mexico', 'dax'
    ]
    selected_fund = st.selectbox('Индекс/фонд', fund_list)
    fund_close_col = f'Close_{selected_fund}'

    fund_series = data_filtered.set_index('timestamp')[fund_close_col]
    fund_mean = fund_series.mean()
    fund_min = fund_series.min()
    fund_max = fund_series.max()
    fund_median = fund_series.median()
    fund_std = fund_series.std()
    fund_change = (fund_series.iloc[-1] - fund_series.iloc[0]) / fund_series.iloc[0] * 100

    row1 = st.columns(3)
    row1[0].metric('Среднее', f"{fund_mean:,.2f}", help='Средняя цена за выбранный период')
    row1[1].metric('Минимум', f"{fund_min:,.2f}", help='Минимальная цена за период')
    row1[2].metric('Максимум', f"{fund_max:,.2f}", help='Максимальная цена за период')

    row2 = st.columns(3)
    row2[0].metric('Медиана', f"{fund_median:,.2f}", help='Медиана цен за период')
    row2[1].metric('Std Dev', f"{fund_std:,.2f}", help='Стандартное отклонение цены')
    row2[2].metric('Изм., %', f"{fund_change:.2f}%", help='Процентное изменение цены')

    st.markdown('---')
    fig_fund = px.line(
        data_filtered,
        x='timestamp',
        y=fund_close_col,
        title=f'Динамика индекса {selected_fund.upper()}'
    )
    st.plotly_chart(fig_fund, use_container_width=True)
    download_chart_xlsx_native(fig_fund, key='dl_fund_chart')
with fgi:
    st.title('☄️ Индекс Страха и Жадности (FGI)')

    fgi_series = data_filtered.set_index('timestamp')['fear_greed_index']
    st.subheader('Динамика FGI')

    current_fgi = fgi_series.iloc[-1]
    avg_fgi = fgi_series.mean()
    mfcol1, mfcol2 = st.columns(2)
    mfcol1.metric('Текущий FGI', f"{current_fgi:.0f}")
    mfcol2.metric('Средний FGI', f"{avg_fgi:.0f}")
    fig_fgi = px.line(
        data_filtered,
        x='timestamp',
        y='fear_greed_index',
        title='Индекс Страха и Жадности'
    )
    st.plotly_chart(fig_fgi, use_container_width=True)
    download_chart_xlsx_native(fig_fgi, key='dl_fgi_chart')

    st.markdown('---')
    st.subheader('Покупательская способность vs FGI')

    close_cols = [col for col in data.columns if col.endswith('_close')]
    default_pp = 'BTC_USDT_1h_close' if 'BTC_USDT_1h_close' in close_cols else close_cols[0]
    asset_pp = st.selectbox(
        'Актив для расчёта покупательской способности',
        options=close_cols,
        index=close_cols.index(default_pp),
    )

    fgi_series = data_filtered.set_index('timestamp')['fear_greed_index']
    pp_series = data_filtered.set_index('timestamp')[asset_pp].rsub(0).rdiv(1)  # 1/price

    fig_pp = make_subplots(specs=[[{"secondary_y": True}]])
    fig_pp.add_trace(
        go.Scatter(x=data_filtered['timestamp'], y=fgi_series, name='FGI'),
        secondary_y=False
    )
    fig_pp.add_trace(
        go.Scatter(x=data_filtered['timestamp'], y=pp_series, name=f'Покуп. способность {asset_pp}'),
        secondary_y=True
    )
    fig_pp.update_layout(title='Индекс FGI и покупательская способность')
    fig_pp.update_yaxes(exponentformat="none",tickformat=".2f", secondary_y=False)

    st.plotly_chart(fig_pp, use_container_width=True, key='pp_chart')

    export_df = pd.DataFrame({
        'timestamp': data_filtered['timestamp'],
        'FGI':        fgi_series.values,
        'PP':         pp_series.values
    })

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        export_df.to_excel(writer, sheet_name='FGI_vs_PP', index=False)
        wb  = writer.book
        ws  = writer.sheets['FGI_vs_PP']
        n   = len(export_df)

        chart = wb.add_chart({'type': 'line'})

        chart.add_series({
            'name':       'FGI',
            'categories': ['FGI_vs_PP', 1, 0, n, 0],  
            'values':     ['FGI_vs_PP', 1, 1, n, 1],  
            'y2_axis':    False,
        })
        chart.add_series({
            'name':       'Покупательская способность',
            'categories': ['FGI_vs_PP', 1, 0, n, 0],
            'values':     ['FGI_vs_PP', 1, 2, n, 2], 
            'y2_axis':    True,                      
            'line':       {'dash': 'dash'},
        })

        chart.set_title ({'name': 'FGI и Покупательская способность'})
        chart.set_x_axis({'name': 'Timestamp'})
        chart.set_y_axis({'name': 'FGI'})
        chart.set_y2_axis({'name': 'Покупательская способность', 'major_gridlines': {'visible': False}})

        ws.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

    buf.seek(0)
    st.download_button(
        label='Скачать FGI vs PP',
        data=buf.read(),
        file_name='fgi_vs_pp_two_axes.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key='dl_pp_fgi_two_axes'
    )

    st.markdown('---')
    st.subheader('Сравнение фондов и индекса Страха и Жадности')

    fund_list = [
        'sp500', 'nasdaq', 'russell_2000', 'vix',
        'cac_40', 'euro_stoxx_50', 'dow_jones', 'ftse_100', 'sptsx'
    ]
    selected_fund = st.selectbox(
        'Выберите фонд для сравнения с FGI',
        options=fund_list,
        index=fund_list.index('sp500')
    )
    fund_col = f'Close_{selected_fund}'

    fgi_series = data_filtered.set_index('timestamp')['fear_greed_index']
    fund_series = data_filtered.set_index('timestamp')[fund_col]

    fig_fund_fgi = make_subplots(specs=[[{"secondary_y": True}]])

    fig_fund_fgi.add_trace(
        go.Scatter(x=data_filtered['timestamp'], y=fgi_series, name='FGI'),
        secondary_y=False
    )
    fig_fund_fgi.add_trace(
        go.Scatter(x=data_filtered['timestamp'], y=fund_series, name=selected_fund.upper()),
        secondary_y=True
    )

    fig_fund_fgi.update_layout(title=f'Индекс FGI и {selected_fund.upper()}')
    fig_fund_fgi.update_yaxes(
        title_text='Индекс FGI',
        exponentformat="none",
        tickformat=".0f",
        secondary_y=False
    )
    fig_fund_fgi.update_yaxes(
        title_text=f'Цена {selected_fund.upper()}',
        exponentformat="none",
        tickformat=".2f",
        secondary_y=True
    )

    st.plotly_chart(fig_fund_fgi, use_container_width=True, key='fund_fgi_chart')

    export_df = pd.DataFrame({
    'timestamp': data_filtered['timestamp'],
    'FGI':        fgi_series.values,
    selected_fund.upper(): fund_series.values
})

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        export_df.to_excel(writer, sheet_name='FGI_vs_Fund', index=False)
        wb  = writer.book
        ws  = writer.sheets['FGI_vs_Fund']
        n   = len(export_df)

        chart = wb.add_chart({'type': 'line'})

        chart.add_series({
            'name':       'FGI',
            'categories': ['FGI_vs_Fund', 1, 0, n, 0],  
            'values':     ['FGI_vs_Fund', 1, 1, n, 1],  
            'y2_axis':    False,
        })

        chart.add_series({
            'name':       selected_fund.upper(),
            'categories': ['FGI_vs_Fund', 1, 0, n, 0],  
            'values':     ['FGI_vs_Fund', 1, 2, n, 2], 
            'y2_axis':    True,
            'line':       {'dash': 'dash'},
        })

        chart.set_title ({'name': f'FGI и {selected_fund.upper()}'})
        chart.set_x_axis({'name': 'Timestamp'})
        chart.set_y_axis({'name': 'FGI'})
        chart.set_y2_axis({'name': selected_fund.upper(), 'major_gridlines': {'visible': False}})

        ws.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

    buf.seek(0)
    st.download_button(
        label=f'Скачать FGI vs {selected_fund.upper()} в XLSX',
        data=buf.read(),
        file_name=f'fgi_vs_{selected_fund}.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key='dl_fund_fgi_two_axes'
    )


with corr:
    st.title('🔗 Корреляция активов')
    st.markdown('Корреляционная матрица для цен закрытия выбранных активов.')

    corr_assets = st.multiselect(
        'Выберите активы (цены закрытия)',
        options=close_cols,
        default=close_cols[:5],
        key='corr_select'
    )

    if len(corr_assets) >= 2:
        corr_df = data_filtered.set_index('timestamp')[corr_assets].corr()
        fig_corr = px.imshow(
            corr_df,
            text_auto=True,
            aspect='auto',
            title='Корреляционная матрица'
        )
        st.plotly_chart(fig_corr, use_container_width=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
            corr_df.to_excel(writer, sheet_name='Correlation', index=True)
            ws = writer.sheets['Correlation']
            for i, col in enumerate(corr_df.columns, start=1):
                ws.set_column(i, i, 12)
        buf.seek(0)
        st.download_button(
            label='Скачать корреляционную матрицу в XLSX',
            data=buf.read(),
            file_name='correlation_matrix.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            key='dl_corr_matrix'
        )

        download_chart_xlsx_native(fig_corr, key='dl_corr_chart')


with table_data:
    st.title('📊 Таблицы данных и метрик')

    close_cols = [col for col in data.columns if col.endswith('_close')]

    fund_list = [
        'sp500', 'nasdaq', 'russell_2000', 'vix',
        'cac_40', 'euro_stoxx_50', 'dow_jones', 'ftse_100', 'sptsx'
    ]
    fund_close_cols = [f'Close_{f}' for f in fund_list if f'Close_{f}' in data.columns]

    fgi_col = ['fear_greed_index']

    metrics_options = close_cols + fund_close_cols + fgi_col

    selected_metrics = st.multiselect(
        'Выберите серии для расчёта метрик',
        options=metrics_options,
        default=close_cols[:3] + fgi_col, 
        help='Для каждой выбранной серии будут рассчитаны Mean/Median/Std Dev/Change%'
    )

    if selected_metrics:
        metrics = []
        for col in selected_metrics:
            ser = data_filtered.set_index('timestamp')[col]
            metrics.append({
                'Series': col,
                'Mean': round(ser.mean(), 4),
                'Min': round(ser.min(), 4),
                'Max': round(ser.max(), 4),
                'Median': round(ser.median(), 4),
                'Std Dev': round(ser.std(), 4),
                'Change %': round((ser.iloc[-1] - ser.iloc[0]) / ser.iloc[0] * 100, 2)
            })
        metrics_df = pd.DataFrame(metrics)
        st.data_editor(metrics_df, num_rows='dynamic', key='metrics_table')

    st.markdown('---')
    st.subheader('Данные (интерактивная таблица)')

    if selected_metrics:
        cols_to_show = ['timestamp'] + selected_metrics
    else:
        cols_to_show = data_filtered.columns.tolist()

    st.data_editor(
        data_filtered[cols_to_show].reset_index(drop=True),
        num_rows='dynamic',
        key='data_editor'
    )