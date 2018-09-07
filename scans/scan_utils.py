import sys
import operator
from collections import OrderedDict

import numpy as np
import pandas as pd
from pprint import pprint
from tqdm import tqdm

import matplotlib.pyplot as plt

def get_TAs(trades_1d, source='ib'):
    """
    intended for daily data; for different frequencies, the periods of TAs should maybe be adjusted

    takes a 1d data dataframe
    source is either 'ib' or 'quandl', determines the col names for ohlcv_cols
    """
    import talib
    import sys
    sys.path.append('../../stock_prediction/code')
    sys.path.append('../stock_prediction/code')
    import calculate_ta_signals as cts

    keep_tas = ['atr_5',
    'atr_14',
    'atr_20',
    'atr_65',
    'natr_5',
    'natr_14',
    'obv_cl',
    'obv_cl_ema_14',
    'rsi_cl_5',
    'rsi_cl_14',
    'adx_14',
    'adx_5',
    'ppo_cl',
    'ppo_cl_signal',
    'trix_cl_12',
    'trix_cl_12_signal',
    'mdi',
    'pldi']

    if source == 'ib':
        trades_1d_ta = cts.create_tas(trades_1d.copy(), ohlcv_cols=['open', 'high', 'low', 'close', 'volume'], return_df=True, tp=False)
        keep_tas.extend('close')  # add close for calculating stop
    elif source == 'quandl':
        trades_1d_ta = cts.create_tas(trades_1d.copy(), ohlcv_cols=['Adj_Open', 'Adj_High', 'Adj_Low', 'Adj_Close', 'Adj_Volume'], return_df=True, tp=False)
        keep_tas.extend(['Adj_Close'])  # add close for calculating stop

    trades_1d_tas = trades_1d_ta.loc[:, keep_tas]

    trades_1d_tas['obv_cl_ema_14_diff'] = trades_1d_tas.loc[:, 'obv_cl_ema_14'].diff()
    # second derivative, if positive, it is increasing
    trades_1d_tas['obv_cl_ema_14_diff2'] = trades_1d_tas.loc[:, 'obv_cl_ema_14_diff'].diff()
    trades_1d_tas.bfill(inplace=True)
    trades_1d_tas['obv_cl_ema_14_diff_ema9'] = talib.EMA(trades_1d_tas['obv_cl_ema_14_diff'].values, timeperiod=9)
    trades_1d_tas['obv_cl_ema_14_diff2_ema9'] = talib.EMA(trades_1d_tas['obv_cl_ema_14_diff2'].values, timeperiod=9)

    # adx trends
    trades_1d_tas['adx_14_diff'] = trades_1d_tas.loc[:, 'adx_14'].diff()
    trades_1d_tas['adx_5_diff'] = trades_1d_tas.loc[:, 'adx_5'].diff()
    trades_1d_tas.bfill(inplace=True)
    trades_1d_tas['adx_14_diff_ema'] = talib.EMA(trades_1d_tas['adx_14_diff'].values, timeperiod=9)
    trades_1d_tas['adx_5_diff_ema'] = talib.EMA(trades_1d_tas['adx_5_diff'].values, timeperiod=3)

    # gets indices of zero crossings with particular signs
    def crossings_nonzero_pos2neg(data):
        pos = data > 0
        return (pos[:-1] & ~pos[1:]).nonzero()[0]


    def crossings_nonzero_neg2pos(data):
        neg = data < 0
        return (neg[:-1] & ~neg[1:]).nonzero()[0]


    # PPO
    trades_1d_tas['ppo_diff'] = trades_1d_tas.loc[:, 'ppo_cl'] - trades_1d_tas.loc[:, 'ppo_cl_signal']
    # from negative to positive is a buy signal, especially if the PPO values are negative
    neg2pos_crossings = crossings_nonzero_neg2pos(trades_1d_tas['ppo_diff'].values)
    trades_1d_tas['ppo_buy_signal'] = 0
    indices = trades_1d_tas.index[neg2pos_crossings]
    trades_1d_tas.loc[indices, 'ppo_buy_signal'] = 1
    # from positive to negative is sell signal, especially if PPO values positive
    pos2neg_crossings = crossings_nonzero_pos2neg(trades_1d_tas['ppo_diff'].values)
    trades_1d_tas['ppo_sell_signal'] = 0
    indices = trades_1d_tas.index[pos2neg_crossings]
    trades_1d_tas.loc[indices, 'ppo_sell_signal'] = 1

    # TRIX
    trades_1d_tas['trix_diff'] = trades_1d_tas.loc[:, 'trix_cl_12'] - trades_1d_tas.loc[:, 'trix_cl_12_signal']
    # from negative to positive is a buy signal, especially if the PPO values are negative
    neg2pos_crossings = crossings_nonzero_neg2pos(trades_1d_tas['trix_diff'].values)
    trades_1d_tas['trix_buy_signal'] = 0
    indices = trades_1d_tas.index[neg2pos_crossings]
    trades_1d_tas.loc[indices, 'trix_buy_signal'] = 1
    # from positive to negative is sell signal, especially if PPO values positive
    pos2neg_crossings = crossings_nonzero_pos2neg(trades_1d_tas['trix_diff'].values)
    trades_1d_tas['trix_sell_signal'] = 0
    indices = trades_1d_tas.index[pos2neg_crossings]
    trades_1d_tas.loc[indices, 'trix_sell_signal'] = 1


    # RSI crossings
    trades_1d_tas['rsi_5_diff'] = trades_1d_tas.loc[:, 'rsi_cl_5'] - 50
    trades_1d_tas['rsi_14_diff'] = trades_1d_tas.loc[:, 'rsi_cl_14'] - 50
    # from negative to positive is a buy signal, especially if the PPO values are negative
    for rsi in ['rsi_5', 'rsi_14']:
        neg2pos_crossings = crossings_nonzero_neg2pos(trades_1d_tas[rsi + '_diff'].values)
        trades_1d_tas[rsi + '_buy_signal'] = 0
        indices = trades_1d_tas.index[neg2pos_crossings]
        trades_1d_tas.loc[indices, rsi + '_buy_signal'] = 1
        # from positive to negative is sell signal, especially if PPO values positive
        pos2neg_crossings = crossings_nonzero_pos2neg(trades_1d_tas[rsi + '_diff'].values)
        trades_1d_tas[rsi + '_sell_signal'] = 0
        indices = trades_1d_tas.index[pos2neg_crossings]
        trades_1d_tas.loc[indices, rsi + '_sell_signal'] = 1

    return trades_1d_tas


def get_bullish_bearish_signals(trades_1d_tas, market_is=None, verbose=True):
    # initialize all as 0s
    bullish_signals = OrderedDict({
                        'bull_OBV': 0,
                        'bull_short-term_RSI': 0,
                        'bull_mid-term_RSI': 0,
                        'bull_midterm_ADX': 0,
                        'bull_midterm_ADX_strong_trend': 0,
                        'bull_shortterm_ADX_strong_trend': 0,
                        'bull_PPO_trend': 0,
                        'bull_TRIX_trend': 0
                        })

    bullish_buy_signals = OrderedDict({
                                        'PPO_buy': 0,
                                        'TRIX_buy': 0,
                                        'shortterm_RSI_buy': 0,
                                        'midterm_RSI_buy': 0
                                        })

    bearish_signals = OrderedDict({
                        'bear_OBV': 0,
                        'bear_shortterm_RSI': 0,
                        'bear_midterm_RSI': 0,
                        'bear_midterm_ADX': 0,
                        'bear_midterm_ADX_strong_trend': 0,
                        'bear_shortterm_ADX_strong_trend': 0,
                        'bear_PPO_trend': 0,
                        'bear_TRIX_trend': 0
                        })

    bearish_sell_signals = OrderedDict({
                                        'PPO_sell': 0,
                                        'TRIX_sell': 0,
                                        'shortterm_RSI_sell': 0,
                                        'midterm_RSI_sell': 0
                                        })

    latest_point = trades_1d_tas.iloc[-1].to_frame().T

    if market_is is None:
        # test for both bearish and bullish signals
        # this is mainly intended for getting trends of the market/sector/related stocks, etc

        # obv rising or falling
        if latest_point['obv_cl_ema_14_diff_ema9'][0] > trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            if verbose:
                print('OBV is showing sign of bullish trend')
            bullish_signals['bull_OBV'] = 1
        elif latest_point['obv_cl_ema_14_diff_ema9'][0] < trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            if verbose:
                print('OBV is showing sign of bearish trend')
            bearish_signals['bear_OBV'] = 1

        # RSI
        if latest_point['rsi_cl_5'][0] > 50:
            if verbose:
                print('short-term RSI bullish signal')
            bullish_signals['bull_shortterm_RSI'] = 1
        else:
            if verbose:
                print('short-term RSI bearish signal')
                bearish_signals['bear_shortterm_RSI'] = 1
        if latest_point['rsi_cl_14'][0] > 50:
            if verbose:
                print('mid-term RSI bullish signal')
            bullish_signals['bull_midterm_RSI'] = 1
        else:
            if verbose:
                print('mid-term RSI bearish signal')
            bearish_signals['bear_midterm_RSI'] = 1

        # buy signals
        if latest_point['rsi_5_buy_signal'][0] == 1:
            if verbose:
                print('RSI short-term buy signal!')
            bullish_buy_signals['bull_shortterm_RSI_buy'] = 1
        if latest_point['rsi_14_buy_signal'][0] == 1:
            if verbose:
                print('RSI mid-term buy signal!')
                bullish_buy_signals['bull_midterm_RSI_buy'] = 1

        # sell signals
        if latest_point['rsi_5_sell_signal'][0] == 1:
            if verbose:
                print('RSI short-term sell signal!')
            bearish_buy_signals['shortterm_RSI_sell'] = 1
        if latest_point['rsi_14_sell_signal'][0] == 1:
            if verbose:
                print('RSI mid-term sell signal!')
            bearish_buy_signals['midterm_RSI_sell'] = 1

        # ADX
        if latest_point['pldi'][0] > latest_point['mdi'][0]:
            if latest_point['adx_14_diff_ema'][0] > 0:
                if verbose:
                    print('mid-term adx EMA bullish signal')
                bullish_signals['bull_midterm_ADX'] = 1
            if latest_point['adx_14'][0] > 25:
                if verbose:
                    print('mid-term adx strong trend signal')
                bullish_signals['bull_midterm_ADX_strong_trend'] = 1
            if latest_point['adx_5'][0] > 25:
                if verbose:
                    print('adx short-term strong bullish signal')
                bullish_signals['bull_shortterm_ADX_strong_trend'] = 1
        else:
            if latest_point['adx_14_diff_ema'][0] > 0:
                if verbose:
                    print('mid-term adx EMA bearish signal')
                bearish_signals['bear_midterm_ADX'] = 1
            if latest_point['adx_14'][0] > 25:
                if verbose:
                    print('mid-term adx strong trend signal')
                bearish_signals['bear_midterm_ADX_strong_trend'] = 1
            if latest_point['adx_5'][0] > 25:
                if verbose:
                    print('adx short-term strong bullish signal')
                bearish_signals['bear_shortterm_ADX_strong_trend'] = 1


        # PPO/TRIX
        # if ppo_cl is above signal line (ppo_cl_signal), then bullish sign, especially if both below 0
        # ppo_cl crossing signal line below zero is a buy signal, or bullish signal
        if latest_point['ppo_buy_signal'][0] == 1:
            if verbose:
                print('PPO buy signal!')
            bullish_buy_signals['PPO_buy'] = 1
        if latest_point['trix_buy_signal'][0] == 1:
            if verbose:
                print('TRIX buy signal!')
            bullish_buy_signals['TRIX_buy'] = 1
        if latest_point['ppo_diff'][0] > 0:
            if verbose:
                print('ppo trend is bullish')
            bullish_signals['bull_PPO_trend'] = 1
        if latest_point['trix_diff'][0] > 0:
            if verbose:
                print('trix trend is bullish')
            bullish_signals['bull_TRIX_trend'] = 1

        if latest_point['ppo_sell_signal'][0] == 1:
            if verbose:
                print('PPO sell signal!')
            bearish_buy_signals['PPO_sell'] = 1
        if latest_point['trix_sell_signal'][0] == 1:
            if verbose:
                print('TRIX sell signal!')
            bullish_buy_signals['TRIX_sell'] = 1
        if latest_point['ppo_diff'][0] < 0:
            if verbose:
                print('ppo trend is bearish')
            bearish_signals['bear_PPO_trend'] = 1
        if latest_point['trix_diff'][0] < 0:
            if verbose:
                print('trix trend is bearish')
            bearish_signals['bear_TRIX_trend'] = 1

        return bearish_signals, bullish_signals, bearish_sell_signals, bullish_buy_signals


def get_bearish_bullish_full_df(df):
    # test for both bearish and bullish signals
    # this is mainly intended for getting trends of the market/sector/related stocks, etc
    new_columns = ['OBV_bear_bull',
                    'shortterm_RSI_bear_bull',
                    'midterm_RSI_bear_bull',
                    'midterm_ADX_bear_bull',
                    'midterm_ADX_strong_trend_bear_bull',
                    'shortterm_ADX_strong_trend_bear_bull',
                    'PPO_trend_bear_bull',
                    'TRIX_trend_bear_bull']
    for c in new_columns:
        df[c] = 0

    for idx, latest_point in df.iterrows():
        # obv rising or falling
        if latest_point['obv_cl_ema_14_diff_ema9'][0] > trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            df.loc[idx, 'OBV_bear_bull'] = 1
        elif latest_point['obv_cl_ema_14_diff_ema9'][0] < trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            df.loc[idx, 'OBV_bear_bull'] = -1

        # RSI
        if latest_point['rsi_cl_5'][0] > 50:
            df.loc[idx, 'shortterm_RSI_bear_bull'] = 1
        else:
            df.loc[idx, 'shortterm_RSI_bear_bull'] = -1
        if latest_point['rsi_cl_14'][0] > 50:
            df.loc[idx, 'midterm_RSI_bear_bull'] = 1
        else:

            df.loc[idx, 'midterm_RSI_bear_bull'] = -1

        # ADX
        if latest_point['pldi'][0] > latest_point['mdi'][0]:
            if latest_point['adx_14_diff_ema'][0] > 0:
                df.loc[idx, 'midterm_ADX_bear_bull'] = 1
            if latest_point['adx_14'][0] > 25:
                df.loc[idx, 'midterm_ADX_strong_trend_bear_bull'] = 1
            if latest_point['adx_5'][0] > 25:
                df.loc[idx, 'short-term_ADX_strong_trend_bear_bull'] = 1
        else:
            if latest_point['adx_14_diff_ema'][0] > 0:
                df.loc[idx, 'midterm_ADX_bear_bull'] = -1
            if latest_point['adx_14'][0] > 25:
                df.loc[idx, 'midterm_ADX_strong_trend_bear_bull'] = -1
            if latest_point['adx_5'][0] > 25:
                df.loc[idx, 'shortterm_ADX_strong_trend_bear_bull'] = -1


        # PPO/TRIX
        # if ppo_cl is above signal line (ppo_cl_signal), then bullish sign, especially if both below 0
        # ppo_cl crossing signal line below zero is a buy signal, or bullish signal
        if latest_point['ppo_diff'][0] > 0:
            df.loc[idx, 'PPO_trend_bear_bull'] = 1
        if latest_point['trix_diff'][0] > 0:
            df.loc[idx, 'TRIX_trend_bear_bull'] = 1
        if latest_point['ppo_diff'][0] < 0:
            df.loc[idx, 'PPO_trend_bear_bull'] = -1
        if latest_point['trix_diff'][0] < 0:
            df.loc[idx, 'TRIX_trend_bear_bull'] = -1

    return df


def get_market_status_quandl(dfs):
    """
    gets if the market is bearish, bullish, or neutral
    for QQQ, DIA, SPY, IJR, IJH
    nasdaq, dow, and sp indexes

    also checks for buy/sell signals

    uses quandl data source
    """
    # TODO: use list of tickers and make it an argument so can scan sectors as well
    qqq_1day = dfs['QQQ']
    qqq_1day_tas = get_TAs(qqq_1day, source='quandl')
    bearish_signals_qqq, bullish_signals_qqq, bearish_sell_signals_qqq, bullish_buy_signals_qqq = get_bullish_bearish_signals(qqq_1day_tas, verbose=False)
    spy_1day = dfs['SPY']
    spy_1day_tas = get_TAs(spy_1day, source='quandl')
    bearish_signals_spy, bullish_signals_spy, bearish_sell_signals_spy, bullish_buy_signals_spy = get_bullish_bearish_signals(spy_1day_tas, verbose=False)
    dia_1day = dfs['DIA']
    dia_1day_tas = get_TAs(dia_1day, source='quandl')
    bearish_signals_dia, bullish_signals_dia, bearish_sell_signals_dia, bullish_buy_signals_dia = get_bullish_bearish_signals(dia_1day_tas, verbose=False)

    # get overall market trend
    bearish_totals =  -np.mean(list(bearish_signals_qqq.values()) + list(bearish_signals_spy.values()) + list(bearish_signals_dia.values()))
    bullish_totals =  np.mean(list(bullish_signals_qqq.values()) + list(bullish_signals_spy.values()) + list(bullish_signals_dia.values()))

    overall = np.mean([bearish_totals, bullish_totals])
    print('average of all bearish/bullish signals:', overall)
    if overall > 0.05:
        print('bullish market!')
        market_is = 'bullish'
    elif overall < -0.05:
        print('bearish market!')
        market_is = 'bearish'
    else:
        print('somewhat neutral market')
        market_is = None

    return market_is


def scan_watchlist():
    sys.path.append('../stocktwits/')
    import get_st_data as gt

    bear_bull_scores = {}
    ta_dfs = {}
    bear_sigs = {}
    bull_sigs = {}
    bull_buy_sigs = {}
    bear_sell_sigs = {}
    overall_bear_bull = {}

    market_is = get_market_status_ib()
    watchlist = get_stock_watchlist(update=False)
    for ticker in tqdm(watchlist):
        # print(ticker)
        try:
            trades_1day = gt.load_ib_data(ticker)
        except FileNotFoundError:
            print('no trade data for', ticker)
            continue

        if trades_1day.shape[0] < 50:  # need enough data for moving averages
            continue

        trades_1day_tas = get_TAs(trades_1day)
        ta_dfs[ticker] = trades_1day_tas
        bearish_signals, bullish_signals, bearish_sell_signals, bullish_buy_signals = get_bullish_bearish_signals(trades_1day_tas, verbose=False)
        bear_sigs[ticker] = bearish_signals
        bull_sigs[ticker] = bullish_signals
        bear_sell_sigs[ticker] = bearish_sell_signals
        bull_buy_sigs[ticker] = bullish_buy_signals

        # screen for buy/sell signals
        sell_sigs = np.sum(list(bearish_sell_signals.values()))
        buy_sigs = np.sum(list(bullish_buy_signals.values()))
        if sell_sigs > 0:
            print(sell_sigs, 'sell signals for', ticker)
        if buy_sigs > 0:
            print(buy_sigs, 'buy signals for', ticker)

        bearish_totals =  -np.mean(list(bear_sigs[ticker].values()))
        bullish_totals =  np.mean(list(bull_sigs[ticker].values()))

        overall = np.mean([bearish_totals, bullish_totals])
        overall_bear_bull[ticker] = overall


    # sorted from bull to bears
    sorted_overall_bear_bull = sorted(overall_bear_bull.items(), key=operator.itemgetter(1))

    # get bulls with over 0.25 scores overall (at least half of bullish signals triggering)

    # TODO: find most recent buy signals
    for b, v in overall_bear_bull.items():
        if v >= 0.25:
            print(b, v)

    # now get most recent buy/sell signals
    days_since_buy_signals = {}
    days_since_sell_signals = {}
    avg_days_since_buy_sigs = {}
    avg_days_since_sell_sigs = {}
    for t in ta_dfs.keys():
        days_since_buy_signals[t] = {}
        days_since_sell_signals[t] = {}
        days_since_buy_signals[t]['ppo'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['ppo_buy_signal'] == 1].index.max()).days
        days_since_buy_signals[t]['trix'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['trix_buy_signal'] == 1].index.max()).days
        days_since_buy_signals[t]['rsi_short'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_5_buy_signal'] == 1].index.max()).days
        days_since_buy_signals[t]['rsi_mid'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_14_buy_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['ppo'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['ppo_sell_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['trix'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['trix_sell_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['rsi_short'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_5_sell_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['rsi_mid'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_14_sell_signal'] == 1].index.max()).days

        avg_days_since_buy_sigs[t] = np.mean([v for v in days_since_buy_signals[t].values()])
        avg_days_since_sell_sigs[t] = np.mean([v for v in days_since_sell_signals[t].values()])

    # sorted from shorted times to longest
    sorted_avg_buy_days = sorted(avg_days_since_buy_sigs.items(), key=operator.itemgetter(1))
    sorted_avg_sell_days = sorted(avg_days_since_sell_sigs.items(), key=operator.itemgetter(1))
    # add overall bear_bull to mix, and bear/bull individually
    for i, s in enumerate(sorted_avg_buy_days):
        sorted_avg_buy_days[i] = s + (overall_bear_bull[s[0]],)

    for i, s in enumerate(sorted_avg_sell_days):
        sorted_avg_sell_days[i] = s + (overall_bear_bull[s[0]],)


def scan_all_quandl_stocks():
    # load full dataframe with all stocks
    sys.path.append('../../stock_prediction/code')
    import dl_quandl_EOD as dlq
    dfs = dlq.load_stocks()

    # bear_bull_scores = {}
    ta_dfs = {}
    # bear_sigs = {}
    # bull_sigs = {}
    # bull_buy_sigs = {}
    # bear_sell_sigs = {}
    # overall_bear_bull = {}

    # dataframe for storing all bear/bull signals
    bear_bull_sigs_df = pd.DataFrame()

    # get market status, although this is not necessary
    market_is = get_market_status_quandl(dfs)
    for t in tqdm(sorted(dfs.keys())):
        # print(t)
        trades_1day = dfs[t]

        # TODO: adapt so can handle smaller number of points
        if trades_1day.shape[0] < 50:  # need enough data for moving averages
            continue

        # get TAs
        trades_1day_tas = get_TAs(trades_1day, source='quandl')
        ta_dfs[t] = trades_1day_tas

        # get bear/bull signals
        bearish_signals, bullish_signals, bearish_sell_signals, bullish_buy_signals = get_bullish_bearish_signals(trades_1day_tas, verbose=False)

        # put latest signals into DF
        temp_df = pd.DataFrame({**bearish_signals, **bullish_signals, **bearish_sell_signals, **bullish_buy_signals}, index=[t])

        # get latest values of ADX, RSI, OBV, etc
        keep_cols = ['adx_5', 'adx_14', 'obv_cl', 'obv_cl_ema_14', 'rsi_cl_5', 'rsi_cl_14', 'ppo_cl', 'trix_cl_12', 'natr_5', 'natr_14']
        adx_frame = trades_1day_tas[keep_cols].iloc[-1].to_frame().T
        adx_frame.index = [t]
        temp_df = pd.concat([temp_df, adx_frame], axis=1)

        # get days since last buy and sell signals
        temp_df['days_since_ppo_buy'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['ppo_buy_signal'] == 1].index.max()).days
        temp_df['days_since_trix_buy'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['trix_buy_signal'] == 1].index.max()).days
        temp_df['days_since_short_rsi_buy'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_5_buy_signal'] == 1].index.max()).days
        temp_df['days_since_mid_rsi_buy'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_14_buy_signal'] == 1].index.max()).days
        temp_df['days_since_ppo_sell'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['ppo_sell_signal'] == 1].index.max()).days
        temp_df['days_since_trix_sell'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['trix_sell_signal'] == 1].index.max()).days
        temp_df['days_since_short_rsi_sell'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_5_sell_signal'] == 1].index.max()).days
        temp_df['days_since_mid_rsi_sell'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_14_sell_signal'] == 1].index.max()).days

        bear_bull_sigs_df = pd.concat([bear_bull_sigs_df, temp_df], sort=True)

    # calculate some averages
    bear_bull_sigs_df['overall_bear_bull'] = bear_bull_sigs_df[list(bullish_signals.keys())].mean(axis=1) - bear_bull_sigs_df[list(bearish_signals.keys())].mean(axis=1)
    buy_sigs_cols = ['days_since_ppo_buy', 'days_since_trix_buy', 'days_since_short_rsi_buy', 'days_since_mid_rsi_buy']
    sell_sigs_cols = [b.replace('buy', 'sell') for b in buy_sigs_cols]
    bear_bull_sigs_df['avg_days_since_buy_sigs'] = bear_bull_sigs_df[buy_sigs_cols].mean(axis=1)
    bear_bull_sigs_df['avg_days_since_sell_sigs'] = bear_bull_sigs_df[sell_sigs_cols].mean(axis=1)

    return ta_dfs, bear_bull_sigs_df


def screen_stocks(bear_bull_sigs_df):
    # get bulls with over 0.25 scores overall (at least half of bullish signals triggering)

    # TODO: find most recent buy signals

    # see if any stocks buy signals today
    # look at stocks with most recent buy signals on average
    most_recent_avg_buys = bear_bull_sigs_df.sort_values(by=['avg_days_since_buy_sigs', 'overall_bear_bull'], ascending=[True, False])

    most_recent_mid_rsi_buys = bear_bull_sigs_df.sort_values(by=['days_since_mid_rsi_buy', 'overall_bear_bull', 'adx_14'], ascending=[True, False, False])
    most_recent_mid_rsi_buys[['days_since_mid_rsi_buy', 'overall_bear_bull', 'adx_14']].head(50)

    # columns to show when checking out head of sorted dfs
    head_cols = ['avg_days_since_buy_sigs', 'overall_bear_bull', 'adx_14']


    # order by top bull signals
    top_bull = bear_bull_sigs_df.sort_values(by='overall_bear_bull', ascending=False)
    top_bull[head_cols].head(50)

    # sorted from shorted times to longest
    nearest_buys = bear_bull_sigs_df.sort_values(by='avg_days_since_buy_sigs')
    nearest_buys[head_cols].head(50)
    # sorted_avg_buy_days = sorted(avg_days_since_buy_sigs.items(), key=operator.itemgetter(1))
    # sorted_avg_sell_days = sorted(avg_days_since_sell_sigs.items(), key=operator.itemgetter(1))

    # days since rsi buy signals
    # sorted_rsi_short_buy_days = sorted(rsi_short_term_buy_signals.items(), key=operator.itemgetter(1))
    # sorted_rsi_mid_buy_days = sorted(rsi_mid_term_buy_signals.items(), key=operator.itemgetter(1))

    # mid_buy_1_day_ago = [s[0] for s in sorted_rsi_mid_buy_days if s[1] <= 1]
    # mid_buy_bear_bull = [overall_bear_bull[s] for s in mid_buy_1_day_ago]
    # sorted_idx = np.argsort(mid_buy_bear_bull)[::-1]
    # np.array(list(zip(mid_buy_1_day_ago, mid_buy_bear_bull)))[sorted_idx]


    # want to find stocks with upward momentum and a RSI buy signal
    # so the entries in bullish_signals, 'short-term ADX strong trend' and 'mid-term ADX' should be 1
    # also having a short squeeze possibility would be good




    # add overall bear_bull to mix, and bear/bull individually
    # for i, s in enumerate(sorted_avg_buy_days):
    #     sorted_avg_buy_days[i] = s + (overall_bear_bull[s[0]],)

    # for i, s in enumerate(sorted_avg_sell_days):
    #     sorted_avg_sell_days[i] = s + (overall_bear_bull[s[0]],)
    #
    # top_sorted_avg_buy_days = [s for s in sorted_avg_buy_days if s[2] >= 0.25]


    # for b, v in overall_bear_bull.items():
    #     if v >= 0.25:
    #         print(b, v)


def check_current_portfolio(current_portfolio=None):
    if current_portfolio is None:
        current_portfolio = ['BJ',
                            'CRON',
                            'NEPT',
                            'TLRY',
                            'CGC',
                            'CRON',
                            'BILI',
                            'MOMO',
                            'SQ',
                            'DDD',
                            'TTD',
                            'AOBC',
                            'LVVV',
                            'OLED']  # not enough data yet for BJ and TLRY

    for c in current_portfolio:
        print(c)
        if c in overall_bear_bull.keys():
            print(overall_bear_bull[c])


def get_price_changes(ta_dfs, col='ppo'):
    """
    gets price changes and percent price changes from buy to sell and sell to buy

    col can be one of ppo, trix, rsi_5, rsi_14
    """
    # get average price changes between buy and sell signals
    # rsi_5 and rsi_14 are perfect for SPY...and seemingly everything else
    full_sells_buys = pd.DataFrame()#{'ticker', 'buy_price', 'sell_price', 'price_change', 'price_pct_change', 'time_diffs'})
    full_buys_sells = pd.DataFrame()#{'ticker', 'sell_price', 'buy_price', 'price_change', 'price_pct_change', 'time_diffs'})

    for ticker in tqdm(ta_dfs.keys()):
        df = ta_dfs[ticker]
        buy_idxs = df[df[col + '_buy_signal'] == 1].index
        sell_idxs = df[df[col + '_sell_signal'] == 1].index
        buy_prices = df.loc[buy_idxs]['Adj_Close']
        sell_prices = df.loc[sell_idxs]['Adj_Close']

        # get buy-sell df and price changes
        if buy_idxs.min() < sell_idxs.min():
            # buy is first action, match all buys to sells
            # possibly more buys than sells
            buys = buy_prices.iloc[:sell_prices.shape[0]]
            sells = sell_prices
        else:
            # sell was first, so take the second sell up to the end
            buys = buy_prices
            sells = sell_prices.iloc[1:] #  should also be able to do [-buy_prices.shape[0]:]

        if buys.shape[0] > sells.shape[0]:
            # have a new buy without a matching sell
            buys = buy_prices.iloc[:-1]

        # combine buys and sells to match them
        # need to use values of sells so it doesn't try to index by date
        buys_sells = pd.DataFrame({'ticker': ticker, 'buy_price': buys, 'sell_price': sells.values})
        buys_sells.loc[:, 'price_change'] = buys_sells['sell_price'] - buys_sells['buy_price']
        buys_sells.loc[:, 'price_pct_change'] = buys_sells['price_change'] / buys_sells['buy_price']

        # buys_sells['price_pct_change'].hist(bins=100); plt.show()

        time_diffs_buy_sell = (sells.index - buys.index).days
        buys_sells.loc[:, 'time_diffs'] = time_diffs_buy_sell
        full_buys_sells = pd.concat([full_buys_sells, buys_sells])

        # get sell-buy df and price changes (for shorting)
        if sell_idxs.min() < buy_idxs.min():
            # sell is first action, match all sell to buys
            # possibly more buys than sells
            buys = buy_prices
            sells = sell_prices.iloc[:buy_prices.shape[0]]
        else:
            # buy was first, take second buy to end
            buys = buy_prices.iloc[1:]  # sell_prices.shape[0]
            sells = sell_prices

        if sells.shape[0] > buys.shape[0]:
            # have a new buy without a matching sell
            sells = sell_prices.iloc[:-1]

        # combine buys and sells to match them
        # need to use values of buys so it doesn't try to index by date
        sells_buys = pd.DataFrame({'ticker': ticker, 'sell_price': sells, 'buy_price': buys.values})
        sells_buys['price_change'] = sells_buys['sell_price'] - sells_buys['buy_price']
        sells_buys['price_pct_change'] = sells_buys['price_change'] / sells_buys['sell_price']


        time_diffs_sell_buy = (buys.index - sells.index).days
        sells_buys.loc[:, 'time_diffs'] = time_diffs_sell_buy
        full_sells_buys = pd.concat([full_sells_buys, sells_buys])

        # plt.hist(time_diffs_sell_buy, bins=30); plt.show()
        # # longer time period, higher gain

    return full_sells_buys, full_buys_sells


def plot_price_changes(full_sells_buys, full_buys_sells, col):
    """
    plots price changes from get_price_changes
    """
    # plot price pct changes -- always positive for RSI, but lots of little numbers
    full_sells_buys['price_pct_change'].hist(bins=100)
    plt.title(col + ' sells->buys price pct change')
    plt.show()

    full_buys_sells['price_pct_change'].hist(bins=100)
    plt.title(col + ' buys->sells price pct change')
    plt.show()

    # for plotting, only look at price pct change %200 and belowe
    full_buys_sells_limited_pct_change = full_buys_sells[full_buys_sells['price_pct_change'] <= 200]['price_pct_change']
    full_buys_sells_limited_pct_change.hist(bins=100)
    plt.title(col + ' buys->sells price pct change, <200%')
    plt.show()


    plt.scatter(sells_buys['time_diffs'], sells_buys['price_pct_change'])
    plt.xlabel('time diffs (days)')
    plt.ylabel('price pct change')
    plt.title(col + 'sells->buys price pct change vs days')
    plt.show()

    plt.scatter(buys_sells['time_diffs'], buys_sells['price_pct_change'])
    plt.xlabel('time diffs (days)')
    plt.ylabel('price pct change')
    plt.title(col + 'buys->sells price pct change vs days')
    plt.show()


# TODO: get stocks with best expected values from buys sell and sells buys DFs

def get_trailing_stop_pct(df):
    """
    uses general rules from "Honest guide to stock trading"
    trailing stop at 4x latest ATR (13-week ATR) for weekly breakout strategy
    7x for daily breakout (20 day)
    2.5x for countertrend (20 day)

    df should be a ta_dfs which has 20day and 65day ATRs
    """
    latest_price = df.iloc[-1]



#
# ticker_groups  = full_sells_buys[['ticker', 'price_pct_change', 'time_diffs']].groupby('ticker').mean()
#
# for t, d in ticker_groups:





# TODO: look at buy sell differences when market is bullish and sell-buy when market bearish


def get_bullish_bearish_market_ranges(dfs):
    """
    gets date ranges when market is bullish or bearish or neutral

    takes dfs list from quandl data
    """
    bear_bull_df_spy = get_bearish_bullish_full_df(dfs['SPY'])
    bear_bull_df_qqq = get_bearish_bullish_full_df(dfs['QQQ'])
    bear_bull_df_dia = get_bearish_bullish_full_df(dfs['DIA'])

if __name__ == "__main__":
    pass
    # ta_dfs, bear_bull_sigs_df = scan_all_quandl_stocks()
    #
    # full_sells_buys_rsi_14, full_buys_sells_rsi_14 = get_price_changes(ta_dfs, col='rsi_14')
    #
    # buy_ticker_groups  = full_buys_sells_rsi_14[['ticker', 'price_pct_change', 'time_diffs']].groupby('ticker').mean().sort_values(by='price_pct_change', ascending=False)
    # full_df_buy = buy_ticker_groups.merge(bear_bull_sigs_df, left_index=True, right_index=True)
    # full_df_buy[full_df_buy['days_since_mid_rsi_buy'] < 4][['price_pct_change', 'time_diffs', 'days_since_mid_rsi_buy', 'overall_bear_bull']].head(50)
    #
    #
    print('getting ta dfs and bear bull sigs df...')
    ta_dfs, bear_bull_sigs_df = scan_all_quandl_stocks()

    print('getting rsi_14 buys sells')
    full_sells_buys_rsi_14, full_buys_sells_rsi_14 = get_price_changes(ta_dfs, col='rsi_14')

    buy_ticker_groups  = full_buys_sells_rsi_14[['ticker', 'price_pct_change', 'time_diffs']].groupby('ticker').mean().sort_values(by='price_pct_change', ascending=False)
    full_df_buy = buy_ticker_groups.merge(bear_bull_sigs_df, left_index=True, right_index=True)
    full_df_buy[full_df_buy['days_since_mid_rsi_buy'] < 4][['price_pct_change', 'time_diffs', 'days_since_mid_rsi_buy', 'overall_bear_bull']].head(50)


    # bear_bull_sigs_df.loc['EGC']
