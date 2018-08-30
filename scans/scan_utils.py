import sys
import operator
from collections import OrderedDict

import numpy as np
import pandas as pd
from pprint import pprint

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
    if source == 'ib':
        trades_1d_ta = cts.create_tas(trades_1d.copy(), ohlcv_cols=['open', 'high', 'low', 'close', 'volume'], return_df=True, tp=False)
    elif source == 'quandl':
        trades_1d_ta = cts.create_tas(trades_1d.copy(), ohlcv_cols=['Adj_Open', 'Adj_High', 'Adj_Low', 'Adj_Close', 'Adj_Volume'], return_df=True, tp=False)

    keep_tas = ['atr_5',
                'atr_14',
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
                        'OBV': 0,
                        'short-term RSI': 0,
                        'mid-term RSI': 0,
                        'mid-term ADX': 0,
                        'mid-term ADX strong trend': 0,
                        'short-term ADX strong trend': 0,
                        'PPO trend': 0,
                        'TRIX trend': 0
                        })

    bullish_buy_signals = OrderedDict({
                                        'PPO buy signal': 0,
                                        'TRIX buy signal': 0,
                                        'short-term RSI buy': 0,
                                        'mid-term RSI buy': 0
                                        })

    bearish_signals = OrderedDict({
                        'OBV': 0,
                        'short-term RSI': 0,
                        'mid-term RSI': 0,
                        'mid-term ADX': 0,
                        'mid-term ADX strong trend': 0,
                        'short-term ADX strong trend': 0,
                        'PPO trend': 0,
                        'TRIX trend': 0
                        })

    bearish_sell_signals = OrderedDict({
                                        'PPO sell signal': 0,
                                        'TRIX sell signal': 0,
                                        'short-term RSI sell': 0,
                                        'mid-term RSI sell': 0
                                        })

    latest_point = trades_1d_tas.iloc[-1].to_frame().T

    if market_is is None:
        # test for both bearish and bullish signals
        # this is mainly intended for getting trends of the market/sector/related stocks, etc

        # obv rising or falling
        if latest_point['obv_cl_ema_14_diff_ema9'][0] > trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            if verbose:
                print('OBV is showing sign of bullish trend')
            bullish_signals['OBV'] = 1
        elif latest_point['obv_cl_ema_14_diff_ema9'][0] < trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            if verbose:
                print('OBV is showing sign of bearish trend')
            bearish_signals['OBV'] = 1

        # RSI
        if latest_point['rsi_cl_5'][0] > 50:
            if verbose:
                print('short-term RSI bullish signal')
            bullish_signals['short-term RSI'] = 1
        else:
            if verbose:
                print('short-term RSI bearish signal')
            bearish_signals['short-term RSI'] = 1
        if latest_point['rsi_cl_14'][0] > 50:
            if verbose:
                print('mid-term RSI bullish signal')
            bullish_signals['mid-term RSI'] = 1
        else:
            if verbose:
                print('mid-term RSI bearish signal')
            bearish_signals['mid-term RSI'] = 1

        # buy signals
        if latest_point['rsi_5_buy_signal'][0] == 1:
            if verbose:
                print('RSI short-term buy signal!')
            bullish_buy_signals['short-term RSI buy'] = 1
        if latest_point['rsi_14_buy_signal'][0] == 1:
            if verbose:
                print('RSI mid-term buy signal!')
            bullish_buy_signals['mid-term RSI buy'] = 1

        # sell signals
        if latest_point['rsi_5_sell_signal'][0] == 1:
            if verbose:
                print('RSI short-term sell signal!')
            bearish_buy_signals['short-term RSI sell'] = 1
        if latest_point['rsi_14_sell_signal'][0] == 1:
            if verbose:
                print('RSI mid-term sell signal!')
            bearish_buy_signals['mid-term RSI sell'] = 1

        # ADX
        if latest_point['pldi'][0] > latest_point['mdi'][0]:
            if latest_point['adx_14_diff_ema'][0] > 0:
                if verbose:
                    print('mid-term adx EMA bullish signal')
                bullish_signals['mid-term ADX'] = 1
            if latest_point['adx_14'][0] > 25:
                if verbose:
                    print('mid-term adx strong trend signal')
                bullish_signals['mid-term ADX strong trend'] = 1
            if latest_point['adx_5'][0] > 25:
                if verbose:
                    print('adx short-term strong bullish signal')
                bullish_signals['short-term ADX strong trend'] = 1
        else:
            if latest_point['adx_14_diff_ema'][0] > 0:
                if verbose:
                    print('mid-term adx EMA bearish signal')
                bearish_signals['mid-term ADX'] = 1
            if latest_point['adx_14'][0] > 25:
                if verbose:
                    print('mid-term adx strong trend signal')
                bearish_signals['mid-term ADX strong trend'] = 1
            if latest_point['adx_5'][0] > 25:
                if verbose:
                    print('adx short-term strong bullish signal')
                bearish_signals['short-term ADX strong trend'] = 1


        # PPO/TRIX
        # if ppo_cl is above signal line (ppo_cl_signal), then bullish sign, especially if both below 0
        # ppo_cl crossing signal line below zero is a buy signal, or bullish signal
        if latest_point['ppo_buy_signal'][0] == 1:
            if verbose:
                print('PPO buy signal!')
            bullish_buy_signals['PPO buy signal'] = 1
        if latest_point['trix_buy_signal'][0] == 1:
            if verbose:
                print('TRIX buy signal!')
            bullish_buy_signals['TRIX buy signal'] = 1
        if latest_point['ppo_diff'][0] > 0:
            if verbose:
                print('ppo trend is bullish')
            bullish_signals['PPO trend'] = 1
        if latest_point['trix_diff'][0] > 0:
            if verbose:
                print('trix trend is bullish')
            bullish_signals['TRIX trend'] = 1

        if latest_point['ppo_sell_signal'][0] == 1:
            if verbose:
                print('PPO sell signal!')
            bearish_buy_signals['PPO sell signal'] = 1
        if latest_point['trix_sell_signal'][0] == 1:
            if verbose:
                print('TRIX sell signal!')
            bullish_buy_signals['TRIX sell signal'] = 1
        if latest_point['ppo_diff'][0] < 0:
            if verbose:
                print('ppo trend is bearish')
            bearish_signals['PPO trend'] = 1
        if latest_point['trix_diff'][0] < 0:
            if verbose:
                print('trix trend is bearish')
            bearish_signals['TRIX trend'] = 1

        return bearish_signals, bullish_signals, bearish_sell_signals, bullish_buy_signals

    elif market_is == 'bullish':
        # obv rising
        if latest_point['obv_cl_ema_14_diff_ema9'][0] > trades_1d_tas['obv_cl_ema_14_diff_ema9'].std() * 0.5:
            if verbose:
                print('OBV is showing sign of bullish trend')
            bullish_signals['OBV'] = 1

        # RSI
        if latest_point['rsi_cl_5'][0] > 50:
            if verbose:
                print('short-term RSI bullish signal')
            bullish_signals['short-term RSI'] = 1
        if latest_point['rsi_cl_14'][0] > 50:
            if verbose:
                print('mid-term RSI bullish signal')
            bullish_signals['mid-term RSI'] = 1

        # buy signals
        if latest_point['rsi_5_buy_signal'][0] == 1:
            if verbose:
                print('RSI short-term buy signal!')
            bullish_buy_signals['short-term RSI buy'] = 1
        if latest_point['rsi_14_buy_signal'][0] == 1:
            if verbose:
                print('RSI mid-term buy signal!')
            bullish_buy_signals['mid-term RSI buy'] = 1

        # ADX
        # for adx_14, should be increasing
        # adx_5 should be above 25
        # first check that trend is positive direction with plus and minus DI indicators
        if latest_point['pldi'][0] > latest_point['mdi'][0]:
            if latest_point['adx_14_diff_ema'][0] > 0:
                if verbose:
                    print('mid-term adx EMA bullish signal')
                bullish_signals['mid-term ADX'] = 1
            if latest_point['adx_14'][0] > 25:
                if verbose:
                    print('mid-term adx strong trend signal')
                bullish_signals['mid-term ADX strong trend'] = 1
            if latest_point['adx_5'][0] > 25:
                if verbose:
                    print('adx short-term strong bullish signal')
                bullish_signals['short-term ADX strong trend'] = 1

        # PPO/TRIX
        # if ppo_cl is above signal line (ppo_cl_signal), then bullish sign, especially if both below 0
        # ppo_cl crossing signal line below zero is a buy signal, or bullish signal
        if latest_point['ppo_buy_signal'][0] == 1:
            if verbose:
                print('PPO buy signal!')
            bullish_buy_signals['PPO buy signal'] = 1
        if latest_point['trix_buy_signal'][0] == 1:
            if verbose:
                print('TRIX buy signal!')
            bullish_buy_signals['TRIX buy signal'] = 1
        if latest_point['ppo_diff'][0] > 0:
            if verbose:
                print('ppo trend is bullish')
            bullish_signals['PPO trend'] = 1
        if latest_point['trix_diff'][0] > 0:
            if verbose:
                print('trix trend is bullish')
            bullish_signals['TRIX trend'] = 1

        return bullish_signals, bullish_buy_signals

    elif market_is == 'bearish':
        pass


def get_bearish_bullish_full_df(df):
    # test for both bearish and bullish signals
    # this is mainly intended for getting trends of the market/sector/related stocks, etc
    new_columns = ['OBV_bear_bull',
                    'short-term_RSI_bear_bull',
                    'mid-term_RSI_bear_bull',
                    'mid-term_ADX_bear_bull',
                    'mid-term_ADX_strong_trend_bear_bull',
                    'short-term_ADX_strong_trend_bear_bull',
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
            df.loc[idx, 'short-term_RSI_bear_bull'] = 1
        else:
            df.loc[idx, 'short-term_RSI_bear_bull'] = -1
        if latest_point['rsi_cl_14'][0] > 50:
            df.loc[idx, 'mid-term_RSI_bear_bull'] = 1
        else:

            df.loc[idx, 'mid-term_RSI_bear_bull'] = -1

        # ADX
        if latest_point['pldi'][0] > latest_point['mdi'][0]:
            if latest_point['adx_14_diff_ema'][0] > 0:
                df.loc[idx, 'mid-term_ADX_bear_bull'] = 1
            if latest_point['adx_14'][0] > 25:
                df.loc[idx, 'mid-term_ADX_strong_trend_bear_bull'] = 1
            if latest_point['adx_5'][0] > 25:
                df.loc[idx, 'short-term_ADX_strong_trend_bear_bull'] = 1
        else:
            if latest_point['adx_14_diff_ema'][0] > 0:
                df.loc[idx, 'mid-term_ADX_bear_bull'] = -1
            if latest_point['adx_14'][0] > 25:
                df.loc[idx, 'mid-term_ADX_strong_trend_bear_bull'] = -1
            if latest_point['adx_5'][0] > 25:
                df.loc[idx, 'short-term_ADX_strong_trend_bear_bull'] = -1


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
    bear_bull_scores = {}
    ta_dfs = {}
    bear_sigs = {}
    bull_sigs = {}
    bull_buy_sigs = {}
    bear_sell_sigs = {}
    overall_bear_bull = {}

    market_is = get_market_status_ib()
    watchlist = get_stock_watchlist(update=False)
    for ticker in watchlist:
        print(ticker)
        try:
            trades_1day = load_ib_data(ticker)
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
    sys.path.append('../../stock_prediction/code')
    import dl_quandl_EOD as dlq
    dfs = dlq.load_stocks()

    bear_bull_scores = {}
    ta_dfs = {}
    bear_sigs = {}
    bull_sigs = {}
    bull_buy_sigs = {}
    bear_sell_sigs = {}
    overall_bear_bull = {}

    market_is = get_market_status_quandl(dfs)
    for ticker in sorted(dfs.keys()):
        print(ticker)
        trades_1day = dfs[ticker]

        # TODO: adapt so can handle smaller number of points
        if trades_1day.shape[0] < 50:  # need enough data for moving averages
            continue

        trades_1day_tas = get_TAs(trades_1day, source='quandl')
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


    # get bulls with over 0.25 scores overall (at least half of bullish signals triggering)

    # TODO: find most recent buy signals

    # for now, just get stocks with buy signals today
    has_buy_sigs = {}
    for t in bull_buy_sigs.keys():
        buy_sigs = sum(bull_buy_sigs[t].values())
        if buy_sigs > 0:
            has_buy_sigs[t] = bull_buy_sigs[t]


    # order by top bull signals
    # sorts from least to greatest
    sorted_overall_bear_bull = sorted(overall_bear_bull.items(), key=operator.itemgetter(1))
    pprint(sorted_overall_bear_bull[-100:])
    best_bulls = [s for s in sorted_overall_bear_bull if s[1] == 0.5]


    # now get most recent buy/sell signals
    days_since_buy_signals = {}
    days_since_sell_signals = {}
    avg_days_since_buy_sigs = {}
    avg_days_since_sell_sigs = {}
    rsi_short_term_buy_signals = {}
    rsi_mid_term_buy_signals = {}
    for t in ta_dfs.keys():
        days_since_buy_signals[t] = {}
        days_since_sell_signals[t] = {}
        days_since_buy_signals[t]['ppo'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['ppo_buy_signal'] == 1].index.max()).days
        days_since_buy_signals[t]['trix'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['trix_buy_signal'] == 1].index.max()).days
        rsi_short_days = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_5_buy_signal'] == 1].index.max()).days
        rsi_mid_days = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_14_buy_signal'] == 1].index.max()).days
        days_since_buy_signals[t]['rsi_short'] = rsi_short_days
        days_since_buy_signals[t]['rsi_mid'] = rsi_mid_days
        rsi_short_term_buy_signals[t] = rsi_short_days
        rsi_mid_term_buy_signals[t] = rsi_mid_days
        days_since_sell_signals[t]['ppo'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['ppo_sell_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['trix'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['trix_sell_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['rsi_short'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_5_sell_signal'] == 1].index.max()).days
        days_since_sell_signals[t]['rsi_mid'] = (ta_dfs[t].index.max() - ta_dfs[t][ta_dfs[t]['rsi_14_sell_signal'] == 1].index.max()).days

        avg_days_since_buy_sigs[t] = np.mean([v for v in days_since_buy_signals[t].values()])
        avg_days_since_sell_sigs[t] = np.mean([v for v in days_since_sell_signals[t].values()])

    # sorted from shorted times to longest
    sorted_avg_buy_days = sorted(avg_days_since_buy_sigs.items(), key=operator.itemgetter(1))
    sorted_avg_sell_days = sorted(avg_days_since_sell_sigs.items(), key=operator.itemgetter(1))

    # days since rsi buy signals
    sorted_rsi_short_buy_days = sorted(rsi_short_term_buy_signals.items(), key=operator.itemgetter(1))
    sorted_rsi_mid_buy_days = sorted(rsi_mid_term_buy_signals.items(), key=operator.itemgetter(1))

    mid_buy_1_day_ago = [s[0] for s in sorted_rsi_mid_buy_days if s[1] <= 1]
    mid_buy_bear_bull = [overall_bear_bull[s] for s in mid_buy_1_day_ago]
    sorted_idx = np.argsort(mid_buy_bear_bull)[::-1]
    np.array(list(zip(mid_buy_1_day_ago, mid_buy_bear_bull)))[sorted_idx]


    # want to find stocks with upward momentum and a RSI buy signal
    # so the entries in bullish_signals, 'short-term ADX strong trend' and 'mid-term ADX' should be 1
    # also having a short squeeze possibility would be good




    # add overall bear_bull to mix, and bear/bull individually
    for i, s in enumerate(sorted_avg_buy_days):
        sorted_avg_buy_days[i] = s + (overall_bear_bull[s[0]],)

    for i, s in enumerate(sorted_avg_sell_days):
        sorted_avg_sell_days[i] = s + (overall_bear_bull[s[0]],)

    top_sorted_avg_buy_days = [s for s in sorted_avg_buy_days if s[2] >= 0.25]


    for b, v in overall_bear_bull.items():
        if v >= 0.25:
            print(b, v)

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

    for t in ta_dfs.keys():
        df = ta_dfs[ticker]
        ppo_buy_idxs = df[df[col + '_buy_signal'] == 1].index
        ppo_sell_idxs = df[df[col + '_sell_signal'] == 1].index
        buy_prices = dfs[ticker].loc[ppo_buy_idxs]['Adj_Close']
        sell_prices = dfs[ticker].loc[ppo_sell_idxs]['Adj_Close']

        # get buy-sell df and price changes
        if ppo_buy_idxs.min() < ppo_sell_idxs.min():
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
        buys_sells = pd.DataFrame({'buy_price': buys, 'sell_price': sells.values})
        buys_sells.loc[:, 'price_change'] = buys_sells['sell_price'] - buys_sells['buy_price']
        buys_sells.loc[:, 'price_pct_change'] = buys_sells['price_change'] / buys_sells['buy_price']

        # buys_sells['price_pct_change'].hist(bins=100); plt.show()

        time_diffs_buy_sell = (sells.index - buys.index).days
        buys_sells.loc[:, 'time_diffs'] = time_diffs_buy_sell
        full_buys_sells = pd.concat([full_buys_sells, buys_sells])

        # get sell-buy df and price changes (for shorting)
        if ppo_sell_idxs.min() < ppo_buy_idxs.min():
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
        sells_buys = pd.DataFrame({'ticker': t, 'sell_price': sells, 'buy_price': buys.values})
        sells_buys['price_change'] = sells_buys['sell_price'] - sells_buys['buy_price']
        sells_buys['price_pct_change'] = sells_buys['price_change'] / sells_buys['sell_price']


        time_diffs_sell_buy = (buys.index - sells.index).days
        sells_buys.loc[:, 'time_diffs'] = time_diffs_sell_buy
        full_sells_buys = pd.concat([full_sells_buys, sells_buys])

        # plt.hist(time_diffs_sell_buy, bins=30); plt.show()
        # # longer time period, higher gain

    sells_buys['price_pct_change'].hist(bins=100); plt.show()
    plt.scatter(time_diffs_sell_buy, sells_buys['price_pct_change']); plt.show()


# TODO: look at buy sell differences when market is bullish and sell-buy when market bearish


def get_bullish_bearish_market_ranges():
    """
    gets date ranges when market is bullish or bearish or neutral
    """
