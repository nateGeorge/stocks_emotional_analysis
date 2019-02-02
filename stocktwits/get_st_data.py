# TODO: keep track of which tickers have reached end of data

import os
import gc
import time
import operator
import pickle as pk
from pprint import pprint
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor

import psutil
import glob
import pytz
import talib
import datetime
import pandas_market_calendars as mcal
import pandas as pd
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import dask.dataframe as dd
# from swifter import swiftapply
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import ParameterGrid
from tqdm import tqdm
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from pprint import pprint

import api  # local file in same directory

# import plotting libraries
import matplotlib.pyplot as plt
import seaborn as sns

import sys
sys.path.append('../../scrape_ib')
import scrape_ib
sys.path.append('../../stock_prediction/code')
import dl_quandl_EOD as dlq

DATA_DIR = '/home/nate/Dropbox/data/stocktwits/data/'
DB = 'stocktwits'

def make_dirs_from_home_dir(path):
    """
    makes directory, one folder at a time, starting at github repo home dir
    """
    last_dir = get_home_dir()
    new_path = path
    if last_dir in path:
        new_path = path.replace(last_dir, '')

    for d in new_path.split('/'):
        last_dir = os.path.join(last_dir, d)
        if not os.path.exists(last_dir):
            os.mkdir(last_dir)


def make_dirs(path):
    """
    makes directory, one folder at a time
    """
    last_dir = '/'
    for d in path.split('/'):
        last_dir = os.path.join(last_dir, d)
        if not os.path.exists(last_dir):
            os.mkdir(last_dir)


def get_home_dir(repo_name='stocks_emotional_analysis'):
    cwd = os.getcwd()
    cwd_list = cwd.split('/')
    repo_position = [i for i, s in enumerate(cwd_list) if s == repo_name]
    if len(repo_position) > 1:
        print("error!  more than one intance of repo name in path")
        return None

    home_dir = '/'.join(cwd_list[:repo_position[0] + 1]) + '/'
    return home_dir


def check_new_data(latest, st, all_messages, all_new_messages, filename, new_filename):
    """
    checks to see if all new data has been retrieved based on 'latest'
    args:
    latest -- int; should be latest id from current data in db
    st -- json object returned from API
    all_messages -- dict with all current messages
    all_new_messages -- dict with all new messages just retrieved
    filename -- string; where full data is stored
    new_filename -- string; where updated data is stored
    """
    new_ids = [m['id'] for m in st['messages']]
    # old way of doing it, but doesn't work if latest message was deleted!
    # if latest in set(new_ids):
    if min(new_ids) < latest:
        print('got all new data')
        new_msg_idx = np.where(latest >= np.array(new_ids))[0][0]
        # list is sorted from newest to oldest, so want to get the newest
        # messages down to (but not including) the latest one in the DB
        new_messages = st['messages'][:new_msg_idx]
        all_new_messages.extend(new_messages)
        all_messages = all_new_messages + all_messages
        write_files(all_messages, filename, all_new_messages, new_filename, only_update_latest=True)
        # delete temp new_messages file
        if os.path.exists(new_filename):
            os.remove(new_filename)

        return True

    return False


def write_files(all_messages, filename, new_messages=None, new_filename=None, only_update_latest=False):
    if only_update_latest:
        # check to make sure not None
        if new_messages is None:
            print('new messages is None, not saving anything')
            return
        elif new_filename is None:
            print('new_filename is None, not saving anything')
            return

        with open(new_filename, "wb") as f:
            pk.dump(new_messages, f, -1)
        with open(filename, "wb") as f:
            pk.dump(all_messages, f, -1)
    else:
        with open(filename, "wb") as f:
            pk.dump(all_messages, f, -1)


def scrape_historical_data(ticker='AAPL', verbose=True, only_update_latest=False):
    """
    only_update_latest=True will fill in any data from present back to latest existing data
    """
    #TODO: deal with misssing data in the middle somehow...
    # filepath = get_home_dir() + 'stocktwits/data/' + ticker + '/'
    filepath = DATA_DIR + ticker + '/'
    if not os.path.exists(filepath): make_dirs(filepath)
    filename = filepath + ticker + '_all_messages.pk'
    new_filename = filepath + ticker + '_new_messages.pk'  # for new data when updating
    if os.path.exists(new_filename): os.remove(new_filename)
    if os.path.exists(filename):
        print("existing file")
        with open(filename, 'rb') as f:
            all_messages = pk.load(f)

        ids = [m['id'] for m in all_messages]
        earliest = min(ids)  #should also be able to do this: all_messages[-1]['id']
        latest = max(ids)
    else:
        print('no previously existing file')
        earliest = None
        latest = None
        all_messages = []

    new_messages = []
    if only_update_latest:
        # too hard to deal with existing new messages, just start over if partially completed
        earliest = None
        print('going to update only the latest messages')
    else:
        print('going to get the earliest messages to the end')

    start = time.time()
    # returns a dictionary with keys ['cursor', 'response', 'messages', 'symbol']
    # docs say returns less than or equal to max, but seems to be only less than
    # get first request
    st = None
    while st in [None, False]:
        st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
        if st is None:
            print('returned None for some reason, sleeping 1 min and trying again')
            time.sleep(60)
        elif st is False:
            print('tried all access tokens, none have enough calls left')
            print('sleeping 5 minutes')
            time.sleep(60*5)

    if only_update_latest:
        new_messages.extend(st['messages'])
        # see if we got all the new data yet
        if check_new_data(latest, st, all_messages, new_messages, filename, new_filename):
            return
    else:
        all_messages.extend(st['messages'])

    num_calls = 1

    while True:
        if st['cursor']['more']:
            # save every 50 calls just in case something happens
            if num_calls % 50 == 0:
                # overwrite old data with updated data
                write_files(all_messages, filename, new_messages, new_filename, only_update_latest)
            if verbose:
                print('getting more data, made', str(num_calls), 'calls so far')
                print(str(req_left), 'requests left')

            time_elapsed = time.time() - start
            try:
                st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
            except:  # sometimes some weird connection issues
                time.sleep(5)
                continue

            if req_left is None:
                print('requests left is None, probably need to wait longer...')
                time.sleep(5 * 60)
                st = {'cursor': {'more': True}}
                continue
            elif req_left is False:
                print('requests left is False, probably need to wait longer...')
                time.sleep(5 * 60)
                st = {'cursor': {'more': True}}
                continue
            elif req_left < 2:  # or (time_elapsed < 3600 and num_calls > 398)
                print('made too many calls too fast, need to change access token or')
                print('wait another', str(round((3600 - time_elapsed) / 60)), 'minutes')
                print('made', str(num_calls), 'calls in', str(round(time_elapsed)), 'seconds')

                # overwrite old data with updated data
                write_files(all_messages, filename, new_messages, new_filename, only_update_latest)

                # TODO: sleep until reset time from header is met
                time.sleep(3601 - time_elapsed)
                start = time.time()
                num_calls = 0

            earliest = st['cursor']['max']
            if st is None:
                print('returned None for some reason')
                # overwrite old data with updated data
                write_files(all_messages, filename, new_messages, new_filename, only_update_latest)
                st = {'cursor': {'more': True}}
                continue
            elif st is False:
                print('tried all access tokens, sleeping for 5 mins')
                time.sleep(5*60)
                st = {'cursor': {'more': True}}
                continue

            if only_update_latest:
                if check_new_data(latest, st, all_messages, new_messages, filename, new_filename):
                    return
                    break  # just in case

                new_messages.extend(st['messages'])
            else:
                all_messages.extend(st['messages'])

            num_calls += 1
            # seems to take long enough that we don't need to sleep
            # time.sleep(0.117)
        else:
            print('reached end of data')
            break

    # write data with updates
    all_messages = new_messages + all_messages
    write_files(all_messages, filename, new_messages, new_filename, only_update_latest=False)


def get_sentiments_vader(x, analyzer):
    vs = analyzer.polarity_scores(x)
    return pd.Series([vs['compound'], vs['pos'], vs['neg'], vs['neu']], index=['compound', 'pos', 'neg', 'neu'])


def get_sentiments_vader_dask(df, analyzer):
    vs = analyzer.polarity_scores(df['body'])
    return pd.Series([vs['compound'], vs['pos'], vs['neg'], vs['neu']], index=['compound', 'pos', 'neg', 'neu'])


def load_historical_data(ticker='AAPL', must_be_up_to_date=False):
    # TODO: try new method from swifter

    # DEPRECATED: old method using pickle files
    """
    # filepath = get_home_dir() + 'stocktwits/data/' + ticker + '/'
    filepath = '/home/nate/Dropbox/data/stocktwits/data/' + ticker + '/'
    filename = filepath + ticker + '_all_messages.pk'
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            all_messages = pk.load(f)
    else:
        print('file doesn\'t exist!')
        return None
    """
    client = MongoClient()
    db = client[DB]
    coll = db[ticker]
    # only keep some columns
    # TODO: look into all available columns, like 'source' and investigate further
    all_messages = list(coll.find({}, {'body': 1,
                                        'entities.sentiment.basic': 1,
                                        'likes.total': 1,
                                        'created_at': 1,
                                        'user.id': 1,
                                        'user.username': 1,
                                        'user.join_date': 1,
                                        'user.followers': 1,
                                        'user.following': 1,
                                        'user.ideas': 1,
                                        'user.watchlist_stocks_count': 1,
                                        'user.like_count': 1,
                                        '_id': 0}))
    if len(all_messages) == 0:
        print("no data available in DB")
        return None

    df = pd.io.json.json_normalize(all_messages)
    # convert datetime column to datetime and set as index
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.set_index('created_at', inplace=True)
    df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('America/New_York')
    # orig_num_samples = df.shape[0]
    # df.drop_duplicates(inplace=True)
    # print('dropped', df.shape[0] - orig_num_samples, 'duplicates')

    # check if data up to date
    up_to_date = check_if_data_up_to_date(df.index[0].date())
    if not up_to_date:
        print('stocktwits data not up to date')
        if must_be_up_to_date:
            return None
    else:
        print('stocktwits data up to date')

    # drop empty columns
    for c in ['entities.sentiment', 'reshare_message.message.entities.sentiment']:
        if c in df.columns:
            df.drop(c, axis=1, inplace=True)
    # is the bearish/bullish tag
    df['entities.sentiment.basic'].value_counts()

    # most useful columns
    useful_df = df.loc[:, ['body', 'entities.sentiment.basic', 'likes.total', 'user.followers']]
    # useful_df.drop_duplicates(inplace=True)  # dupes should already be dropped in mongodb
    useful_df = useful_df.sort_index(ascending=False)

    analyzer = SentimentIntensityAnalyzer()
    """
    https://github.com/cjhutto/vaderSentiment#about-the-scoring
    compound: most useful single metric -- average valence of each word in sentence
    """
    print('getting sentiments...')
    # original non-parallelized way to do it:
    # sentiments = useful_df['body'].apply(lambda x: get_sentiments_vader(x, analyzer))

    # swifter doesn't work with functions that return series right now
    # sentiments = swiftapply(useful_df['body'], get_sentiments_vader, analyzer=analyzer)

    ddata = dd.from_pandas(useful_df['body'], npartitions=8)
    sentiments = ddata.map_partitions(lambda ddf: ddf.apply((lambda x: get_sentiments_vader(x, analyzer)))).compute(scheduler='processes')
    # returns backwards for some reason...
    sentiments = sentiments.iloc[::-1]
    # shouldn't need to sort
    # sentiments = sentiments.sort_index(ascending=False)
    # sentiments.hist()
    full_useful = pd.concat([useful_df, sentiments], axis=1)

    # convert entities.sentiment.basic to +1 for bullish and -1 for bearish, 0 for NA
    conv_dict = {'Bearish': -1, 'Bullish': 1}  # thinking it's best to leave np.nan in there
    conv_dict2 = {'Bearish': -1, np.nan: 0, 'Bullish': 1}
    full_useful.loc[:, 'entities.sentiment.basic.nona'] = full_useful['entities.sentiment.basic'].replace(conv_dict2)
    full_useful.loc[:, 'entities.sentiment.basic'] = full_useful['entities.sentiment.basic'].replace(conv_dict)

    return full_useful


def get_eastern_market_open_close():
    ny = pytz.timezone('America/New_York')
    today_ny = datetime.datetime.now(ny)
    ndq = mcal.get_calendar('NASDAQ')
    open_days = ndq.schedule(start_date=today_ny - pd.Timedelta(str(3*365) + ' days'), end_date=today_ny)
    # convert times to eastern
    for m in ['market_open', 'market_close']:
        open_days[m] = open_days[m].dt.tz_convert('America/New_York')

    return open_days


def check_if_data_up_to_date(latest_data_date):
    ny = pytz.timezone('America/New_York')
    today_ny = datetime.datetime.now(ny)
    if latest_data_date != today_ny.date():
        open_days = get_eastern_market_open_close()
        # if not same day as NY date, check if NY time is before market close
        if today_ny >= open_days.iloc[-1]['market_close']:
            print("data not up to todays date")
            return False

    return True


def combine_with_price_data_ib(ticker='TSLA', must_be_up_to_date=True):
    # meld with price data and see if any correlations
    trades_3min = scrape_ib.load_data(ticker)  # by default loads 3 mins bars
    # check if data up to date, first check if data is same day as NY date
    up_to_date = check_if_data_up_to_date(trades_3min.index[-1].date())
    if not up_to_date:
        print('price data not up to date')
        if must_be_up_to_date:
                return None, None, None
    else:
        print('stock price data up to date')

    st = load_historical_data(ticker, must_be_up_to_date=must_be_up_to_date)  # get stock twits data
    if st is None:  # data is not up to date
        print('stocktwits data not up to date')
        return None, None, None

    st = st.iloc[::-1]  # reverse order from oldest -> newest to match IB data
    # create counts column for resampling
    st['count'] = 1
    st_min = st[['entities.sentiment.basic', 'entities.sentiment.basic.nona', 'compound', 'pos', 'neg', 'neu', 'count']]
    #TWS bars are labeled by the start of the time bin, so  use label='left'
    st_min_3min = st_min.resample('3min', label='left').mean().ffill()  # forward fill because it's not frequent enough

    st_min_3min['count'] = st['count'].resample('3min', label='left').sum().ffill()


    # go through each unique date, get market open and close times from IB data,
    # then get average of sentiment features from market closed times and add as new feature
    unique_dates = np.unique(st_min_3min.index.date)
    open_days = get_eastern_market_open_close()
    last_close = None
    # new_feats = {}
    new_feats = pd.DataFrame()
    for d in unique_dates:
        if d in open_days.index:  # if it's a trading day...
            open_time = open_days.loc[d]['market_open']
            if last_close is None:
                new_feats[d] = st_min_3min.loc[:open_time].mean()
                new_feats[d]['count'] = st_min_3min.loc[:open_time, 'count'].sum()
            else:
                new_feats[d] = st_min_3min.loc[last_close:open_time].mean()
                new_feats[d]['count'] = st_min_3min.loc[last_close:open_time, 'count'].sum()

            last_close = open_days.loc[d]['market_open']

    new_feats = new_feats.T
    new_feats.columns = ['bearish_bullish_closed', 'bearish_bullish_closed.nona', 'compound_closed', 'pos_closed', 'neg_closed', 'neu_closed', 'count_closed']

    st_full_3min = st_min_3min.copy()
    nf_cols = new_feats.columns
    for d in new_feats.index:
        for c in nf_cols:
            st_full_3min.loc[d:d + pd.Timedelta('1D'), c] = new_feats.loc[d, c]

    # merge sentiment with price data
    full_3min = pd.concat([trades_3min, st_full_3min], axis=1)
    full_3min = full_3min.loc[trades_3min.index]
    # make 1h price change and 1h future price change
    full_3min['close_1h_chg'] = full_3min['close'].pct_change(20)  # for 3 min, 20 segments is 60 mins
    # full_tsla['3m_future_price'] = full_tsla['close'].shift(-1)  # sanity check
    full_3min['1h_future_price'] = full_3min['close'].shift(-20)
    full_3min['1h_future_price_chg'] = full_3min['1h_future_price'].pct_change(20)

    full_3min['8h_future_price'] = full_3min['close'].shift(-20*8)
    full_3min['8h_future_price_chg'] = full_3min['1h_future_price'].pct_change(20*8)


    # resample to daily frequency
    # weekdays : monday = 0, sunday = 6
    st_daily = st_min.resample('1D', label='left').mean().ffill()
    st_daily['bear_count'] = st_min[st_min['entities.sentiment.basic'] == -1]['entities.sentiment.basic'].resample('1D', label='left').count()
    st_daily['bull_count'] = st_min[st_min['entities.sentiment.basic'] == 1]['entities.sentiment.basic'].resample('1D', label='left').count()
    st_daily['pos_count'] = st_min[st_min['compound'] > 0.05]['compound'].resample('1D', label='left').count()
    st_daily['neg_count'] = st_min[st_min['compound'] < -0.05]['compound'].resample('1D', label='left').count()
    st_weekend = st_min[st_min.index.weekday.isin(set([5, 6]))]
    st_daily_weekend = st_weekend.resample('W-MON', label='right').mean()
    st_daily['count'] = st_min['count'].resample('1D', label='left').sum().ffill()
    st_daily_weekend['count'] = st_weekend['count'].resample('W-MON', label='right').sum().ffill()
    st_daily_std = st_min.resample('1D', label='left').std().ffill()
    st_daily_weekend_std = st_weekend.resample('W-MON', label='right').std().ffill()

    # count column is all 0s
    st_daily_std.drop('count', inplace=True, axis=1)
    st_daily_weekend_std.drop('count', inplace=True, axis=1)

    # rename columns for clarity
    st_daily_std.columns = [c + '_std' for c in st_daily_std.columns]
    st_daily_weekend.columns = [c + '_weekend' for c in st_daily_weekend.columns]
    st_daily_weekend_std.columns = [c + '_weekend_std' for c in st_daily_weekend_std.columns]


    # combine regular sentiment and standard deviation dataframes
    st_daily_full = pd.concat([st_daily, st_daily_std], axis=1)
    # get rid of weekend days in resampled data
    to_drop_idxs = st_daily_full[st_daily_full.index.weekday.isin(set([5, 6]))].index
    st_daily_full.drop(to_drop_idxs, inplace=True)
    # add weekend data to daily df
    st_daily_full = pd.concat([st_daily_full, st_daily_weekend, st_daily_weekend_std], axis=1).ffill().dropna()


    trades_1d = trades_3min.resample('1D').apply({'open': 'first',
                                            'high': 'max',
                                            'low': 'min',
                                            'close': 'last',
                                            'volume': 'sum',
                                            'bid_open': 'first',
                                            'bid_high': 'max',
                                            'bid_low': 'min',
                                            'bid_close': 'last',
                                            'ask_open': 'first',
                                            'ask_high': 'max',
                                            'ask_low': 'min',
                                            'ask_close': 'last',
                                            'opt_vol_open': 'first',
                                            'opt_vol_high': 'max',
                                            'opt_vol_low': 'min',
                                            'opt_vol_close': 'last'})

    # ignore weekends
    trades_1d = trades_1d[trades_1d.index.weekday.isin(set(range(5)))]

    # drop holidays
    trades_1d.dropna(inplace=True)

    full_daily = pd.concat([trades_1d, st_daily_full], axis=1)
    future_price_chg_cols = []
    for i in range(1, 11):
        full_daily[str(i) + 'd_price_chg_pct'] = full_daily['close'].pct_change(i)
        full_daily[str(i) + 'd_future_price_chg_pct'] = full_daily[str(i) + 'd_price_chg_pct'].shift(-i)
        # full_daily[str(i) + 'd_future_price_chg_pct'] = full_daily[str(i) + 'd_future_price'].pct_change(i)
        future_price_chg_cols.append(str(i) + 'd_future_price_chg_pct')
        # drop future price column because we care about % change
        # full_daily.drop(str(i) + 'd_future_price', axis=1, inplace=True)


    return full_3min, full_daily, future_price_chg_cols


def combine_with_price_data_quandl(ticker='AAPL', must_be_up_to_date=False, ema_periods=[5, 10, 20], future_days=[1, 3, 5, 10, 20, 40]):
    # meld with price data and see if any correlations
    print('loading quandl data...')
    stocks = dlq.load_stocks()

    print('loading stocktwits data...')
    st = load_historical_data(ticker, must_be_up_to_date=must_be_up_to_date)  # get stock twits data
    if st is None:  # data is not up to date
        print('stocktwits data not up to date')
        return None, None, None

    st = st.iloc[::-1]  # reverse order from oldest -> newest to match quandl data
    # create counts column for resampling
    st['count'] = 1
    st_min = st[['entities.sentiment.basic', 'entities.sentiment.basic.nona', 'compound', 'pos', 'neg', 'neu', 'count']]
    # bars are labeled by the start of the time bin, so  use label='left'
    st_min_1d = st_min.resample('1D', label='left').mean().ffill()  # forward fill because it's not frequent enough

    st_min_1d['count'] = st['count'].resample('1D', label='left').sum().ffill()


    # go through each unique date, get market open and close times for each day
    # then get average of sentiment features from market closed times and add as new feature
    unique_dates = np.unique(st_min_1d.index.date)
    open_days = get_eastern_market_open_close()
    last_close = None
    # new_feats = {}
    new_feats = pd.DataFrame()
    for d in unique_dates:
        if d in open_days.index:  # if it's a trading day...
            open_time = open_days.loc[d]['market_open']
            if last_close is None:
                new_feats[d] = st_min_1d.loc[:open_time].mean()
                new_feats[d]['count'] = st_min_1d.loc[:open_time, 'count'].sum()
            else:
                new_feats[d] = st_min_1d.loc[last_close:open_time].mean()
                new_feats[d]['count'] = st_min_1d.loc[last_close:open_time, 'count'].sum()

            last_close = open_days.loc[d]['market_open']

    new_feats = new_feats.T
    new_feats.columns = ['bearish_bullish_closed', 'bearish_bullish_closed.nona', 'compound_closed', 'pos_closed', 'neg_closed', 'neu_closed', 'count_closed']

    st_full_1d = st_min_1d.copy()
    nf_cols = new_feats.columns
    for d in new_feats.index:
        for c in nf_cols:
            st_full_1d.loc[d, c] = new_feats.loc[d, c]

    # merge sentiment with price data
    stock_df = stocks[ticker].copy()
    stock_df.index = stock_df.index.tz_localize('America/New_York')
    st_daily = pd.concat([stock_df, st_full_1d], axis=1)

    # make more daily features
    # weekdays : monday = 0, sunday = 6
    st_daily['bear_count'] = st_min[st_min['entities.sentiment.basic'] == -1]['entities.sentiment.basic'].resample('1D', label='left').count()
    st_daily['bull_count'] = st_min[st_min['entities.sentiment.basic'] == 1]['entities.sentiment.basic'].resample('1D', label='left').count()
    st_daily['pos_count'] = st_min[st_min['compound'] > 0.05]['compound'].resample('1D', label='left').count()
    st_daily['neg_count'] = st_min[st_min['compound'] < -0.05]['compound'].resample('1D', label='left').count()
    # get moving average of sentiments
    # bear/bull from ST
    for e in ema_periods:
        st_daily['bear_bull_EMA_' + str(e)] = talib.EMA(st_daily['entities.sentiment.basic'].values, timeperiod=e)
        st_daily['compound_EMA_' + str(e)] = talib.EMA(st_daily['compound'].values, timeperiod=e)

    st_weekend = st_min[st_min.index.weekday.isin(set([5, 6]))]
    st_daily_weekend = st_weekend.resample('W-MON', label='right').mean()
    st_daily['count'] = st_min['count'].resample('1D', label='left').sum().ffill()
    st_daily_weekend['count'] = st_weekend['count'].resample('W-MON', label='right').sum().ffill()
    st_daily_std = st_min.resample('1D', label='left').std().ffill()
    st_daily_weekend_std = st_weekend.resample('W-MON', label='right').std().ffill()

    # count column is all 0s
    st_daily_std.drop('count', inplace=True, axis=1)
    st_daily_weekend_std.drop('count', inplace=True, axis=1)

    # rename columns for clarity
    st_daily_std.columns = [c + '_std' for c in st_daily_std.columns]
    st_daily_weekend.columns = [c + '_weekend' for c in st_daily_weekend.columns]
    st_daily_weekend_std.columns = [c + '_weekend_std' for c in st_daily_weekend_std.columns]


    # combine regular sentiment and standard deviation dataframes
    st_daily_full = pd.concat([st_daily, st_daily_std], axis=1)
    # get rid of weekend days in resampled data
    to_drop_idxs = st_daily_full[st_daily_full.index.weekday.isin(set([5, 6]))].index
    st_daily_full.drop(to_drop_idxs, inplace=True)
    # add weekend data to daily df
    st_daily_full = pd.concat([st_daily_full, st_daily_weekend, st_daily_weekend_std], axis=1).ffill().dropna()

    full_daily = st_daily_full.copy()#pd.concat([trades_1d, st_daily_full], axis=1)
    future_price_chg_cols = []
    for i in future_days:
        full_daily[str(i) + 'd_price_chg_pct'] = full_daily['Adj_Close'].pct_change(i)
        full_daily[str(i) + 'd_future_price_chg_pct'] = full_daily[str(i) + 'd_price_chg_pct'].shift(-i)
        # full_daily[str(i) + 'd_future_price_chg_pct'] = full_daily[str(i) + 'd_future_price'].pct_change(i)
        future_price_chg_cols.append(str(i) + 'd_future_price_chg_pct')
        # drop future price column because we care about % change
        # full_daily.drop(str(i) + 'd_future_price', axis=1, inplace=True)


    return full_daily, future_price_chg_cols


def get_param_grid(num_feats):
    # get auto setting for max_features
    auto = int(np.sqrt(num_feats))
    auto_1_2 = auto // 2
    auto_to_max = num_feats - auto
    step_size = auto_to_max // 3
    max_features = list(range(auto, num_feats + 1, step_size))

    grid = ParameterGrid({
                        'n_estimators': [500],
                        'random_state': [42],
                        'n_jobs': [-1],
                        'max_depth': [3, 7, 12, 25],
                        'min_samples_split': [2, 4, 6, 8, 10],
                        'max_features': ['auto', auto_1_2,] + max_features
                        })
    return grid


def get_tr_test_feats_targs(full_daily, feats_cols, future_price_chg_cols, future_days_prediction, tr_size=0.8):
    # ignore highly correlated columns -- bid and ask correlated with open/close/hi/low
    # opt_vol_open and close correlated, and correlated to opt_vol_low
    feats_cols_trimmed = [f for f in feats_cols if 'ask' not in f and 'bid' not in f and 'opt_vol_open' not in f]
    ignore_cols = set(['2d_price_chg_pct', '4d_price_chg_pct', '6d_price_chg_pct',
                    '7d_price_chg_pct', '8d_price_chg_pct', '9d_price_chg_pct', 'open', 'high', 'low', 'close'])
    feats_cols_trimmed = [f for f in feats_cols_trimmed if f not in ignore_cols]
    nona = full_daily.dropna()
    feats = nona[feats_cols_trimmed]
    # 3d seems to be best for IQ
    targs = nona[[str(f) + 'd_future_price_chg_pct' for f in future_days_prediction]]
    tr_idx = int(tr_size * feats.shape[0])
    tr_feats = feats[:tr_idx]
    te_feats = feats[tr_idx:]
    tr_targs = targs[:tr_idx]
    te_targs = targs[tr_idx:]

    return tr_feats, te_feats, tr_targs, te_targs


# TODO: prototype and functionize getting select TAs and converting previous prices into

# TODO: plot rolling min/max of prices of stocks to look for patterns of new highs (breakouts)

# TODO: add short data


# TAs to keep
# natr, normalized average true range

# OBV
# on-balance volume -- rising price should be accompanied by rising OBV
# https://www.investopedia.com/articles/active-trading/041814/four-most-commonlyused-indicators-trend-trading.asp
# If OBV is rising and price isn't, price is likely to follow the OBV and start rising. If price is rising and OBV is flat-lining or falling, the price may be near a top. If the price is falling and OBV is flat-lining or rising, the price could be nearing a bottom.
# https://www.investopedia.com/articles/active-trading/021115/uncover-market-sentiment-onbalance-volume-obv.asp

# RSI
# Say the long-term trend of a stock is up. A buy signal occurs when the RSI moves below 50 and then back above it
# A short-trade signal occurs when the trend is down and the RSI moves above 50 and then back below it.
# RSI, relative strength index

# ADX
# average directional index; above 25 is a strong trend
# A series of higher ADX peaks means trend momentum is increasing.
# https://www.investopedia.com/articles/trading/07/adx-trend-indicator.asp

# trend indicators: https://www.incrediblecharts.com/indicators/trend_indicators.php
# https://www.incrediblecharts.com/indicators/trix_indicator.php
# TRIX
# Go long [L] when TRIX crosses to above the signal line while below zero.
# Price closes above the MA 4 days earlier, but then whipsaws us in and out of several times at [W].
# Go short [S] when TRIX crosses to below the signal line while above zero.
# By comparison the MA signal [X] is much later.

# http://www.incrediblecharts.com/indicators/macd-percentage-price-oscillator.php
# PPO
# if abs(PPO) > 1%, then trending
# First check whether price is trending.
# Go long when MACD crosses its signal line from below.
# Go short when MACD crosses its signal line from above.


# ATR:
# https://www.investopedia.com/articles/trading/08/atr.asp


def load_ib_data(ticker, timeframe='1D'):
    trades_3min = scrape_ib.load_data(ticker)  # by default loads 3 mins bars
    if timeframe == '3 mins':
        return trades_3min
    elif timeframe == '1D':
        trades_1d = trades_3min.resample('1D').apply({'open': 'first',
                                                    'high': 'max',
                                                    'low': 'min',
                                                    'close': 'last',
                                                    'volume': 'sum',
                                                    'bid_open': 'first',
                                                    'bid_high': 'max',
                                                    'bid_low': 'min',
                                                    'bid_close': 'last',
                                                    'ask_open': 'first',
                                                    'ask_high': 'max',
                                                    'ask_low': 'min',
                                                    'ask_close': 'last',
                                                    'opt_vol_open': 'first',
                                                    'opt_vol_high': 'max',
                                                    'opt_vol_low': 'min',
                                                    'opt_vol_close': 'last'})
        # ignore weekends
        trades_1d = trades_1d[trades_1d.index.weekday.isin(set(range(5)))]
        # drop holidays
        trades_1d.dropna(inplace=True)
        return trades_1d


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


def load_cron():
    # load data into daily format
    ticker = 'CRON'
    trades_1d = load_ib_data(ticker)
    trades_1d_tas = get_TAs(trades_1d)

    # TODO: plot with TAs


def get_market_status_ib():
    """
    gets if the market is bearish, bullish, or neutral
    for QQQ, DIA, SPY, IJR, IJH
    nasdaq, dow, and sp indexes

    also checks for buy/sell signals

    uses interactive brokers data
    """
    # TODO: use list of tickers and make it an argument so can scan sectors as well
    ticker = 'QQQ'
    qqq_1day = load_ib_data(ticker)
    qqq_1day_tas = get_TAs(qqq_1day)
    bearish_signals_qqq, bullish_signals_qqq, bearish_sell_signals_qqq, bullish_buy_signals_qqq = get_bullish_bearish_signals(qqq_1day_tas, verbose=False)
    ticker = 'SPY'
    spy_1day = load_ib_data(ticker)
    spy_1day_tas = get_TAs(spy_1day)
    bearish_signals_spy, bullish_signals_spy, bearish_sell_signals_spy, bullish_buy_signals_spy = get_bullish_bearish_signals(spy_1day_tas, verbose=False)
    ticker = 'DIA'
    dia_1day = load_ib_data(ticker)
    dia_1day_tas = get_TAs(dia_1day)
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
    # at least half of bull signals are triggered...ish
    best_bulls = [s for s in sorted_overall_bear_bull if s[1] >= 0.25]
    best_bull_tickers = set(s[0] for s in best_bulls)

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

    top_sorted_avg_buy_days = [s for s in sorted_avg_buy_days if s[2] >= 0.25]


    for b, v in overall_bear_bull.items():
        if v >= 0.25:
            print(b, v)

    current_portfolio = ['BJ', 'CRON', 'NEPT', 'TLRY', 'CGC', 'BILI', 'MOMO', 'SQ', 'DDD', 'TTD', 'AOBC', 'LVVV']

    for c in current_portfolio:
        print(c)
        print(overall_bear_bull[c])


# TODO: get trend of sector and even more specific sector, e.g. related stocks (like marijuana stocks for CRON)

# TODO: plot average gain between buy/signals


def check_buy_sell_signals():
    pass


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





# TODO: play around with slopes of trix and ppo; feed historical data into neural network
# TODO: atr trends https://www.investopedia.com/articles/trading/08/atr.asp



def ml_on_combined_data(ticker, full_daily, future_price_chg_cols, show_tr_test=True, show_feat_imps=True):
    ######### try some ML
    # save best hyperparameters and other info
    todays_date = datetime.datetime.today().date().strftime('%Y-%m-%d')
    best_hyperparams_filename = 'best_hyperparams_daily_rf_{}.pk'.format(todays_date)
    cur_best_hyperparams = {}
    if os.path.exists(best_hyperparams_filename):
        cur_best_hyperparams = pk.load(open(best_hyperparams_filename, 'rb'))

    future_days_prediction = [2, 3, 5, 10]
    non_price_chg_cols = [c for c in full_daily.columns if c not in future_price_chg_cols]
    tr_feats, te_feats, tr_targs, te_targs = get_tr_test_feats_targs(full_daily, non_price_chg_cols, future_price_chg_cols, future_days_prediction)
    # gridsearch to find best hyperparams

    grid = get_param_grid(tr_feats.shape[1])

    tr_scores, te_scores = [], []
    for g in tqdm(grid):
        rfr = RandomForestRegressor(**g)
        rfr.fit(tr_feats, tr_targs)
        tr_scores.append(rfr.score(tr_feats, tr_targs))
        te_scores.append(rfr.score(te_feats, te_targs))

    best_idx = np.argmax(te_scores)
    print('best score on test:', str(te_scores[best_idx]))

    cur_best_hyperparams[ticker] = {}
    cur_best_hyperparams[ticker]['date_range'] = (tr_feats.index[0], te_feats.index[-1])
    cur_best_hyperparams[ticker]['full_features_best_hyper'] = grid[best_idx]

    rfr = RandomForestRegressor(**grid[best_idx])
    rfr.fit(tr_feats, tr_targs)
    tr_score = rfr.score(tr_feats, tr_targs)
    te_score = rfr.score(te_feats, te_targs)
    cur_best_hyperparams[ticker]['tr_te_scores_full_feats'] = (tr_score, te_score)
    print('train score:', tr_score)
    print('test score:', te_score)

    if show_tr_test:
        tr_preds = rfr.predict(tr_feats)
        te_preds = rfr.predict(te_feats)
        f, ax = plt.subplots(2, 2)
        i = 0
        for row in range(2):
            for col in range(2):
                ax[row][col].scatter(tr_preds[:, i], tr_targs.iloc[:, i], label='train')
                ax[row][col].scatter(te_preds[:, i], te_targs.iloc[:, i], label='test')
                ax[row][col].set_title(str(future_days_prediction[i]) + 'd future price pct')
                i += 1

        plt.ylabel('targets')
        plt.xlabel('predictions')
        plt.legend()
        plt.suptitle('using all features')
        plt.tight_layout()
        plt.show()

    # get feature importances
    feat_imps = rfr.feature_importances_
    feat_idx = np.argsort(feat_imps)[::-1]
    cur_best_hyperparams[ticker]['feat_imps_all'] = feat_imps[feat_idx]
    cur_best_hyperparams[ticker]['feat_names_all'] = tr_feats.columns[feat_idx]

    if show_feat_imps:
        f = plt.figure()
        x = range(len(feat_imps))
        plt.bar(x, feat_imps[feat_idx])
        plt.xticks(x, tr_feats.columns[feat_idx], rotation=90)
        plt.tight_layout()
        plt.show()

    # get cumulative sum of feature importances, only take top 90%
    cum_sum = np.cumsum(feat_imps[feat_idx])
    cutoff_idx = np.argmin(np.abs(cum_sum - 0.9)) + 1
    print('selected', cutoff_idx, 'features out of', tr_feats.shape[1])
    new_feats = tr_feats.columns[feat_idx][:cutoff_idx]
    # 3d seems to be best for IQ

    tr_feats, te_feats, tr_targs, te_targs = get_tr_test_feats_targs(full_daily, new_feats, future_price_chg_cols, future_days_prediction)
    grid = get_param_grid(tr_feats.shape[1])

    tr_scores, te_scores = [], []
    for g in tqdm(grid):
        rfr = RandomForestRegressor(**g)
        rfr.fit(tr_feats, tr_targs)
        tr_scores.append(rfr.score(tr_feats, tr_targs))
        te_scores.append(rfr.score(te_feats, te_targs))

    best_idx = np.argmax(te_scores)
    print('best score on test:', str(te_scores[best_idx]))

    cur_best_hyperparams[ticker]['trimmed_features_best_hyper'] = grid[best_idx]

    rfr = RandomForestRegressor(**grid[best_idx])

    rfr.fit(tr_feats, tr_targs)
    tr_score = rfr.score(tr_feats, tr_targs)
    te_score = rfr.score(te_feats, te_targs)
    cur_best_hyperparams[ticker]['tr_te_scores_trimmed_feats'] = (tr_score, te_score)
    print(tr_score)
    print(te_score)
    tr_preds = rfr.predict(tr_feats)
    te_preds = rfr.predict(te_feats)

    feat_imps = rfr.feature_importances_
    feat_idx = np.argsort(feat_imps)[::-1]
    cur_best_hyperparams[ticker]['feat_imps_trimmed'] = feat_imps[feat_idx]
    cur_best_hyperparams[ticker]['feat_names_trimmed'] = tr_feats.columns[feat_idx]

    if show_tr_test:
        # plot predictions vs actual
        f, ax = plt.subplots(2, 2)
        i = 0
        for row in range(2):
            for col in range(2):
                ax[row][col].scatter(tr_preds[:, i], tr_targs.iloc[:, i], label='train')
                ax[row][col].scatter(te_preds[:, i], te_targs.iloc[:, i], label='test')
                ax[row][col].set_title(str(future_days_prediction[i]) + 'd future price pct')
                i += 1

        plt.ylabel('targets')
        plt.xlabel('predictions')
        plt.legend()
        plt.suptitle('using trimmed features')
        plt.tight_layout()
        plt.show()

    # fit on full data and make prediction for current day
    # save here because often has problem with NAs
    pk.dump(cur_best_hyperparams, open(best_hyperparams_filename, 'wb'), -1)
    feats = np.vstack((tr_feats, te_feats))
    targs = np.vstack((tr_targs, te_targs))
    rfr.fit(feats, targs)
    last_feature = full_daily[new_feats].iloc[-2:]
    # TODO: deal with NA/infinity values (LNG)
    newest_prediction = rfr.predict(last_feature)
    print('latest prediction:', str(newest_prediction[-1]))
    cur_best_hyperparams[ticker]['latest_predictions'] = newest_prediction[-1]
    pk.dump(cur_best_hyperparams, open(best_hyperparams_filename, 'wb'), -1)


    # TODO: add in short interest as feature

    # TODO: get post volume as a feature...looks like high post volume increase, high sentiment, and high short % is a good combo for incr in price (MTCH)


def fit_neural_network(full_daily, future_price_chg_cols):
    # neural network prototyping
    future_days_prediction = [2, 3, 5, 10]
    non_price_chg_cols = [c for c in full_daily_baba.columns if c not in future_price_chg_cols_baba]
    tr_feats, te_feats, tr_targs, te_targs = get_tr_test_feats_targs(full_daily, non_price_chg_cols, future_price_chg_cols, future_days_prediction, tr_size=0.9)

    from sklearn.preprocessing import StandardScaler

    tr_feats_sc, te_feats_sc = [], []
    for i in range(tr_feats.shape[1]):
        sc = StandardScaler()
        tr_feats_sc.append(sc.fit_transform(tr_feats.iloc[:, i].values.reshape(-1, 1)))
        te_feats_sc.append(sc.transform(te_feats.iloc[:, i].values.reshape(-1, 1)))

    tr_feats_sc = np.concatenate(tr_feats_sc, axis=1)
    te_feats_sc = np.concatenate(te_feats_sc, axis=1)

    from keras.layers import Input, Dense, BatchNormalization, Dropout
    from keras.models import Model
    import tensorflow as tf
    import keras.backend as K
    import keras.losses

    # custom loss with correct direction
    def stock_loss_mae_log(y_true, y_pred):
        alpha1 = 4.  # penalty for predicting positive but actual is negative
        alpha2 = 4.  # penalty for predicting negative but actual is positive
        loss = tf.where(K.less(y_true * y_pred, 0), \
                         tf.where(K.less(y_true, y_pred), \
                                    alpha1 * K.log(K.abs(y_true - y_pred) + 1), \
                                    alpha2 * K.log(K.abs(y_true - y_pred) + 1)), \
                         K.log(K.abs(y_true - y_pred) + 1))

        return K.mean(loss, axis=-1)

    keras.losses.stock_loss_mae_log = stock_loss_mae_log


    # works decently on BABA stock currently (8-22-2018) with 872 tr samples
    inputs = Input(shape=(tr_feats.shape[1],))

    # a layer instance is callable on a tensor, and returns a tensor
    # x = BatchNormalization()(inputs)
    x = Dense(1000, activation='elu')(inputs)
    x = BatchNormalization()(x)
    x = Dropout(0.5)(x)
    x = Dense(500, activation='elu')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.5)(x)
    x = Dense(250, activation='elu')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.3)(x)
    x = Dense(100, activation='elu')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.3)(x)
    x = Dense(20, activation='elu')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.1)(x)
    predictions = Dense(tr_targs.shape[1], activation='linear')(x)

    model = Model(inputs=inputs, outputs=predictions)
    model.compile(optimizer='adam',
                  loss='mae')
    model.fit(tr_feats_sc, tr_targs, epochs=2000, batch_size=2000)

    tr_preds = model.predict(tr_feats_sc)
    te_preds = model.predict(te_feats_sc)
    # plot predictions vs actual
    f, ax = plt.subplots(2, 2)
    i = 0
    for row in range(2):
        for col in range(2):
            ax[row][col].scatter(tr_preds[:, i], tr_targs.iloc[:, i], label='train')
            ax[row][col].scatter(te_preds[:, i], te_targs.iloc[:, i], label='test')
            ax[row][col].set_title(str(future_days_prediction[i]) + 'd future price pct')
            i += 1

    plt.ylabel('targets')
    plt.xlabel('predictions')
    plt.legend()
    plt.tight_layout()
    plt.show()


def examine_autocorrelations():
    pass


def plot_combined_data(full_df, only_daily=True, is_ib=False):
    """
    full_df should be dataframe from combine_with_price_data_ib or combine_with_price_data_quandl

    if using combine_with_price_data_quandl, only_daily should be True
    otherwise, needs to be something with 8h_future_price_chg column
    """
    # plt.scatter(full_tsla['bearish_bullish_closed'], full_tsla['1h_future_price_chg'])
    f = plt.figure(figsize=(12, 12))
    sns.heatmap(full_df.corr(), annot=True)
    plt.tight_layout()
    plt.show()

    if not only_daily:
        plt.scatter(full_df['bearish_bullish_closed'], full_df['8h_future_price_chg'])
        plt.show()

        plt.scatter(full_df['entities.sentiment.basic'], full_df['8h_future_price_chg'])
        plt.show()

        plt.scatter(full_df['opt_vol_high'], full_df['8h_future_price_chg'])
        plt.show()

        # when it was -0.05, strong correlation to negative returns -- all on one day, 3/28
        plt.scatter(full_df['compound_closed'], full_df['8h_future_price_chg'])
        plt.show()


    non_price_chg_cols = [c for c in full_df.columns if c not in future_price_chg_cols]
    f = plt.figure(figsize=(20, 20))
    sns.heatmap(full_df.corr().loc[non_price_chg_cols, future_price_chg_cols], annot=True)
    plt.tight_layout()
    plt.show()


    # slight positive correlation
    plt.scatter(full_df['entities.sentiment.basic_std'], full_df['10d_future_price_chg_pct'])
    plt.show()

    plt.scatter(full_df['pos_weekend_std'], full_df['10d_future_price_chg_pct'])
    plt.show()

    if is_ib:
        plt.scatter(full_df['opt_vol_close'], full_df['10d_future_price_chg_pct'])
        plt.show()

    plt.scatter(full_df['count'], full_df['10d_future_price_chg_pct'])
    plt.show()

    plt.scatter(full_df['compound'], full_df['1d_future_price_chg_pct'])
    plt.show()

    plt.scatter(full_df['entities.sentiment.basic'], full_df['10d_future_price_chg_pct'])
    plt.show()

    plt.scatter(full_df['entities.sentiment.basic_weekend'], full_df['10d_future_price_chg_pct'])
    plt.show()

    plt.scatter(full_df['compound'], full_df['10d_future_price_chg_pct'])
    plt.show()

    plt.scatter(full_df['pos'], full_df['10d_future_price_chg_pct'])
    plt.show()
    # get things correlated with 5d change > 0.1
    # idx_5d = np.where(full_df.columns == '5d_future_price_chg_pct')[0][0]
    # idx_1d = np.where(full_df.columns == '1d_future_price_chg_pct')[0][0]
    # full_df.columns[:idx_1d][(full_df.corr() > 0.1).iloc[:idx_1d, idx_5d]]

    # get daily price change and daily bearish/bullish and sentiments

    # don't think I nede this anymore
    # trades_1d = trades_3min.resample('1D').apply({'open': 'first',
    #                                         'high': 'max',
    #                                         'low': 'min',
    #                                         'close': 'last'})


def plot_col_vs_pct_chg(full_daily, ticker, col='entities.sentiment.basic'):
    f, ax = plt.subplots(2, 2)
    ax[0][0].scatter(full_daily[col], full_daily['1d_future_price_chg_pct'], alpha=0.4)
    ax[0][1].scatter(full_daily[col], full_daily['3d_future_price_chg_pct'], alpha=0.4)
    ax[1][0].scatter(full_daily[col], full_daily['5d_future_price_chg_pct'], alpha=0.4)
    ax[1][1].scatter(full_daily[col], full_daily['10d_future_price_chg_pct'], alpha=0.4)
    ax[1][0].set_xlabel(col)  # 'bearish/bullish daily average'
    ax[1][1].set_xlabel(col)
    ax[0][0].set_ylabel('1 day price change %')
    ax[0][1].set_ylabel('3 day price change %')
    ax[1][0].set_ylabel('5 day price change %')
    ax[1][1].set_ylabel('10 day price change %')
    f.suptitle('bearish/bullish sentiment vs price changes for ' + ticker)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

# resample bearish/bullish to daily, get number of counts of posts

# ticker = 'TSLA'
# scrape_historical_data(ticker, only_update_latest=True)
# scrape_historical_data(ticker, only_update_latest=False)

# reached end of data

# no messages
# ['XLM']


def get_stock_watchlist(update=True, return_trending=False):
    """
    gets trending stocks and saves to pickle file of stocks to monitor
    """
    # original list I started with
    # tickers = ['CRON', 'AMD', 'IQ', 'MU', 'SNAP', 'MTCH', 'BTC', 'ETH', 'ETH.X',
    #             'SPY', 'BABA', 'TVIX', 'OSTK', 'MU', 'QQQ', 'SNAP', 'TTD', 'VKTX',
    #             'OMER', 'OLED', 'TSLA', 'LNG', 'ALNY', 'OMER', 'FOLD', 'RDFN',
    #             'TUR', 'TXMD', 'TDOC', 'SQ',
    #             'PYPL', 'ADBE', 'FB', 'BOX', 'Z', 'TGT', 'FMC', 'KIRK', 'FTD',
    #             'ABEV', 'GE', 'F', 'TTT', 'DDD', 'VSAT', 'TKC', 'NWSA']

    # list from scrape_ib
    # tickers = ['CRON', 'ADBE', 'ROKU', 'PLNT', 'BDSI', 'MTCH', 'DBX', 'FNKO', 'OSTK', 'SPY', 'BABA', 'MU', 'QQQ', 'SNAP', 'TTD', 'VKTX', 'OMER', 'OLED']
    # tickers =  tickers + ['ALNY', 'OMER', 'FOLD', 'RDFN', 'TUR', 'TXMD', 'TDOC', 'SQ',
    #             'PYPL', 'ADBE', 'FB', 'BOX', 'Z', 'TGT', 'FMC', 'KIRK', 'FTD',
    #             'ABEV', 'GE', 'F', 'TTT', 'DDD', 'VSAT', 'TKC', 'NWSA']

    filename = '/home/nate/github/stocks_emotional_analysis/stocktwits/tickers_watching.pk'
    cur_tickers = []
    if os.path.exists(filename):
        cur_tickers = pk.load(open(filename, 'rb'))

    if update:
        trending = None
        while trending is None:
            trending = api.get_trending_stocks()
            if trending is not None: break
            print('sleeping 30s')
            time.sleep(30)

        # only unique tickers
        tickers = sorted(list(set(cur_tickers + trending)))
        pk.dump(tickers, open(filename, 'wb'), -1)  # use highest available pk protocol
        if return_trending:
            return tickers, trending
        return tickers
    else:
        if return_trending:
            return cur_tickers, trending
        return cur_tickers


def add_stocks_to_watchlist(stocks):
    """
    supply a list of stocks which gets added to the pickle file
    """
    filename = 'tickers_watching.pk'
    cur_tickers = []
    if os.path.exists(filename):
        cur_tickers = pk.load(open(filename, 'rb'))

    tickers = sorted(list(set(cur_tickers + stocks)))
    pk.dump(tickers, open(filename, 'wb'), -1)


def remove_stocks_from_watchlist(stocks):
    """
    supply a list of stocks which gets removed from the pickle file
    """
    filename = 'tickers_watching.pk'
    cur_tickers = []
    if os.path.exists(filename):
        cur_tickers = pk.load(open(filename, 'rb'))

    for s in stocks:
        if s in cur_tickers:
            cur_tickers.remove(s)

    tickers = sorted(list(set(cur_tickers)))
    pk.dump(tickers, open(filename, 'wb'), -1)


def update_lots_of_tickers():
    """
    DEPRECATED: stores data in .pk files
    use update_lots_of_tickers_mongo instead
    """
    tickers = get_stock_watchlist()
    while True:
        for t in tickers:
            # update tickers to get watch list constantly
            _ = get_stock_watchlist()
            try:
                print('scraping', t)
                # shouldn't need to do this without only_update_latest anymore,
                # as it has been done for a while...
                # scrape_historical_data(t)
                # TODO: save latest in a temp file, then once finished getting all new data, append to big file
                scrape_historical_data(t, only_update_latest=True)
            except KeyError:
                print('probably no data')
                continue


def update_lots_of_tickers_mongo():
    tickers = get_stock_watchlist()
    while True:
        for t in tickers:
            # update tickers to get watch list constantly
            _ = get_stock_watchlist()
            try:
                print('scraping', t)
                # shouldn't need to do this without only_update_latest anymore,
                # as it has been done for a while...
                # scrape_historical_data(t)
                # TODO: save latest in a temp file, then once finished getting all new data, append to big file
                scrape_historical_data_mongo(t, only_update_latest=True)
            except KeyError:
                print('probably no data')
                continue


def do_ml(ticker, must_be_up_to_date=False):
    df = load_historical_data(ticker)
    full_3min, full_daily, future_price_chg_cols = combine_with_price_data_ib(ticker, must_be_up_to_date)
    ml_on_combined_data(ticker, full_daily, future_price_chg_cols)


def plot_close_bear_bull_count(full_daily):
    f, axs = plt.subplots(4, 1, sharex=True)
    axs[0].plot(full_daily['entities.sentiment.basic'], label='bearish/bullish', c='k')
    axs[0].set_ylabel('bearish/bullish daily')
    ax2 = axs[0].twinx()
    ax2.plot(full_daily['close'], label='close')
    ax2.set_ylabel('close')
    ax2.legend()
    axs[1].plot(full_daily['count'], c='orange')
    axs[1].set_ylabel('count')
    axs[2].plot(full_daily['bull_count'], label='bull_count', c='g')
    axs[2].plot(full_daily['bear_count'], label='bear_count', c='r')
    axs[2].legend()
    axs[3].plot(full_daily['pos_count'], c='g')
    axs[3].plot(full_daily['neg_count'], c='r')
    axs[3].legend()
    plt.show()


def convert_pickle_to_mongodb(ticker):
    """
    pickle files were used as a first storage mechanism, but are extremely slow to load.
    This function moves the data from a pickle file into the mongodb.
    """
    filepath = DATA_DIR + ticker + '/'
    filename = filepath + ticker + '_all_messages.pk'

    # # as long as memory isn't too full, move on to next one
    # # the biggest .pk file for SPY is 8GB on disk, and takes up about 65GB
    # vmem = psutil.virtual_memory()
    # pid = os.getpid()
    # py = psutil.Process(pid)
    # memoryUse = py.memory_info()[0]/2.**30

    with open(filename, 'rb') as f:
        all_messages = pk.load(f)

    DB = 'stocktwits'
    client = MongoClient()
    db = client[DB]
    coll = db[ticker]

    # remove duplicates from entries -- takes way too long
    # non_dupes = []
    # for m in tqdm(all_messages):
    #     if m not in non_dupes:
    #         non_dupes.append(m)

    """
    # drop _id column so can use insert_many
    # seems to only get added upon insert_many
    for m in tqdm(all_messages):
        if '_id' in m:
            del m['_id']
    """


    try:
        coll.insert_many(all_messages, ordered=False)
    except BulkWriteError as bwe:
        pass
        # would print the error, but pretty much always duplicates
        # pprint(bwe.details)

    """
    # too slow -- estimated at 130 hours for AAPL
    for m in tqdm(all_messages):
        # check if already in DB...some dupes
        if coll.find_one({'id': m['id']}) is None:
            # restructure for more efficient storage
            # --actually don't do for now, since some of the subdata changes over time
            # m_restr = {'id': m['id'],
            #             'body': m['body'],
            #             'created_at': m['created_at'],
            #             'user': }
            coll.insert_one(m)
    """


    # checking what user profiles look like over time
    # created = []
    # user = []
    # for m in all_messages:
    #     if m['user']['id'] == 689515:
    #         user.append(m['user'])
    #         created.append(m['created_at'])

    del all_messages
    gc.collect()
    client.close()
    print('finished ', ticker)


def convert_all_pickle_to_mongo(linear=False, max_workers=None):
    """
    converts all pickle files to mongodb storage
    """
    tickers = sorted([t.split('/')[-1] for t in glob.glob(DATA_DIR + '*')])
    # tickers to run separately since they have huge files
    ignore_tickers = ['SPY', 'FB', 'AMZN', 'AAPL', 'BB', 'NFLX', 'QQQ', 'BABA', 'DRYS', 'UVXY', 'GOOG', 'NUGT', 'AMD', 'JNUG', 'TWTR', 'SNAP', 'BAC', 'VXX']
    ignore_set = set(ignore_tickers)
    if linear:
        for t in tqdm(tickers):
            print('on', t)
            convert_pickle_to_mongodb(t)
    else:
        # jobs = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for t in tickers:
                if t not in ignore_set:
                    executor.submit(convert_pickle_to_mongodb, t)
                    # jobs.append(t)

        for t in ignore_tickers:
            convert_pickle_to_mongodb(t)

        # for t in jobs:
        #     pass


def scrape_historical_data_mongo(ticker='AAPL', verbose=True, only_update_latest=False):
    """
    finds latest datapoint from db and updates from there

    API returns the 30 latest posts, so have to work backwards from the newest posts

    args:
    ticker -- string like 'AAPL'
    verbose -- boolean, prints debugs if True
    only_update_latest -- boolean; if True, will only get the latest updates
                            (from most recent down to max already in db)
                            Otherwise, gets updates from earliest in db to first
                            post
    """
    # TODO: deal with missing data in the middle somehow...
    client = MongoClient()
    db = client[DB]
    # drop temp_data collection so no left over data is in there
    db.drop_collection('temp_data')
    coll = db[ticker]
    if ticker in db.list_collection_names():
        earliest = coll.find_one(sort=[('id', 1)])['id']  #should also be able to do this: all_messages[-1]['id']
        latest = coll.find_one(sort=[('id', -1)])['id']
        if only_update_latest:
            # TODO: deal with existing new messages, just starting over if partially completed for now
            earliest = None
            coll = db['temp_data']
            print('going to update only the latest messages')
        else:
            print('going to get the earliest messages to the end')
    else:
        print('no previously existing data')
        # can't only update latest because no previously existing data
        only_update_latest = False
        earliest = None
        latest = None

    start = time.time()
    # returns a dictionary with keys ['cursor', 'response', 'messages', 'symbol']
    # docs say returns less than or equal to max, but seems to be only less than
    # get first request
    st = None
    while st in [None, False]:
        st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
        if st is None:
            print('returned None for some reason, sleeping 1 min and trying again')
            time.sleep(60)
        elif st is False:
            print('tried all access tokens, none have enough calls left')
            print('sleeping 5 minutes')
            time.sleep(60*5)
        else:
            earliest = st['cursor']['max']

    if only_update_latest:
        # see if we got all the new data yet
        done = check_new_data_mongo(latest, st, coll, db, ticker)
        if done:
            client.close()
            return

    # inserts into main collection if updating earliest or scraping fresh;
    # inserts into temp_data if updating latest
    try:
        coll.insert_many(st['messages'], ordered=False)
    except BulkWriteError as bwe:
        pass

    num_calls = 1

    while True:
        if st['cursor']['more']:
            if verbose:
                print('getting more data, made', str(num_calls), 'calls so far')
                print(str(req_left), 'requests left')

            time_elapsed = time.time() - start
            try:
                st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
                if st not in [None, False] and len(st['messages']) > 0:
                    if only_update_latest:
                        done = check_new_data_mongo(latest, st, coll, db, ticker)
                        if done:
                            client.close()
                            return

                    try:
                        coll.insert_many(st['messages'], ordered=False)
                    except BulkWriteError as bwe:
                        pass

                    earliest = st['cursor']['max']
            except:  # sometimes some weird connection issues
                print('problem')
                time.sleep(5)
                continue

            if req_left is None:
                print('requests left is None, probably need to wait longer...')
                time.sleep(5 * 60)
                st = {'cursor': {'more': True}}
                continue
            elif req_left is False:
                print('requests left is False, probably need to wait longer...')
                time.sleep(5 * 60)
                st = {'cursor': {'more': True}}
                continue
            elif req_left < 2:  # or (time_elapsed < 3600 and num_calls > 398)
                print('made too many calls too fast, need to change access token or')
                print('wait another', str(round((3600 - time_elapsed) / 60)), 'minutes')
                print('made', str(num_calls), 'calls in', str(round(time_elapsed)), 'seconds')

                # TODO: sleep until reset time from header is met
                time.sleep(3601 - time_elapsed)
                start = time.time()
                num_calls = 0

            if st is None:
                print('returned None for some reason')
                st = {'cursor': {'more': True}}
                continue
            elif st is False:
                print('tried all access tokens, sleeping for 5 mins')
                time.sleep(5*60)
                st = {'cursor': {'more': True}}
                continue

            num_calls += 1
            # seems to take long enough that we don't need to sleep
            # time.sleep(0.117)
        else:
            print('reached end of data')
            break


def check_new_data_mongo(latest, st, coll, db, ticker):
    """
    checks to see if all new data has been retrieved based on 'latest'
    if latest is in st ids, then return True, else False
    adds last bit of data to temp_data db, then copies over to full db

    args:
    latest -- int; should be latest id from current data in db
    st -- json object returned from API
    coll -- collection (should be temp_data)
    db -- database connection
    ticker -- string, like 'AAPL'
    """
    new_ids = [m['id'] for m in st['messages']]
    # old way of doing it, but doesn't work if latest message was deleted!
    # if latest in set(new_ids):
    if min(new_ids) < latest:
        print('got all new data')
        new_msg_idx = np.where(latest >= np.array(new_ids))[0][0]
        # list is sorted from newest to oldest, so want to get the newest
        # messages down to (but not including) the latest one in the DB
        new_messages = st['messages'][:new_msg_idx]
        if len(new_messages) == 0:
            print('no new data')
            return True

        # finish adding to temp_data collection
        try:
            coll.insert_many(new_messages, ordered=False)
        except BulkWriteError as bwe:
            pass

        # add all data from temp_data to
        ticker_coll = db[ticker]
        new_data = list(coll.find())
        try:
            ticker_coll.insert_many(new_data, ordered=False)
        except BulkWriteError as bwe:
            pass

        return True

    return False


def clean_dupes(ticker):
    # difficult to figure out:
    # https://stackoverflow.com/questions/14184099/fastest-way-to-remove-duplicate-documents-in-mongodb
    # generate duplicate on purpose:
    # db['ZYME'].insertOne(db['ZYME'].findOne({}, {'_id': 0}));

    client = MongoClient()
    db = client[DB]
    coll = db[ticker]
    pipeline = [
        {'$group': { '_id': '$id', 'doc' : {'$first': '$$ROOT'}}},
        {'$replaceRoot': { 'newRoot': '$doc'}},
        {'$out': ticker}  # write over existing collection
    ]
    coll.aggregate(pipeline, allowDiskUse=True)
    # db.command('aggregate', ticker, pipeline=pipeline, allowDiskUse=True)
    client.close()

    # works in mongo
    # db.data.aggregate([
    # {
    #     $group: { "_id": {'ticker': '$ticker', '52WeekChange': '$52WeekChange'}, "doc" : {"$first": "$$ROOT"}}
    # },
    # {
    #     $replaceRoot: { "newRoot": "$doc"}
    # },
    # {
    #     $out: 'data'
    # }
    # ],
    # {allowDiskUse:true})


def clean_all_dupes():
    """
    goes through all tickers in db and cleans up dupes
    """
    client = MongoClient()
    db = client[DB]
    sorted_tickers = sorted(db.list_collection_names())
    for t in tqdm(sorted_tickers):
        clean_dupes(t)


if __name__ == "__main__":
    def do_some_analysis():
        """
        IDEA: sentiment seems to be inversely correlated to future price.  Use sentiment, along with past candlestick data, volatility index, and other
        econometrics to predict price in next few weeks
        """

        full_daily, future_price_chg_cols = combine_with_price_data_quandl(ticker='QQQ', must_be_up_to_date=False)
        # look at correlation between moving average sentiment/compound score and future prices
        sns.heatmap(full_daily[['bear_bull_EMA', 'compound_EMA'] + future_price_chg_cols].corr(), annot=True)
        plt.show()

        # somewhat of a negative trend...should be enough to add to a ML algo
        plt.scatter(full_daily['bear_bull_EMA'], full_daily['10d_future_price_chg_pct'])
        plt.show()

        # look at patterns with price
        full_daily[['bear_bull_EMA', 'Adj_Close']].plot(subplots=True); plt.show()

    # TODO: plot above with counts, create new feature from counts and bear/bull, resample bear/bull with sum instead of mean (and do for individual bear/bull)
    # examine what happened when it went bearish for a sec then back to bullish

    # get predictions for all stocks in watchlist
    # tickers = get_stock_watchlist()
    # full_3min, full_daily, future_price_chg_cols = combine_with_price_data_ib('SNAP')

    # # find large gap in data for missing intermediate data
    # tsla = load_historical_data('TSLA')
    # index_diff = tsla.index[:-1] - tsla.index[1:]
    # max_diff_idx = np.argmax(index_diff)
    # tsla.iloc[max_diff_idx]
    # tsla.iloc[max_diff_idx + 1]
