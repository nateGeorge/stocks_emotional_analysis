import os
import time
import pickle as pk

import datetime
import pytz
import pandas_market_calendars as mcal
import pandas as pd
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import dask.dataframe as dd
# from swifter import swiftapply

import api  # local file in same directory

# import plotting libraries
import matplotlib.pyplot as plt
import seaborn as sns

import sys
sys.path.append('../../scrape_ib')
import scrape_ib


def make_dirs(path):
    """
    makes directory, one folder at a time
    """
    last_dir = get_home_dir()
    new_path = path
    if last_dir in path:
        new_path = path.replace(last_dir, '')

    for d in new_path.split('/'):
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
    new_ids = [m['id'] for m in st['messages']]
    if latest in new_ids:
        print('got all new data')
        new_msg_idx = np.where(latest == np.array(new_ids))[0][0]
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
    filepath = get_home_dir() + 'stocktwits/data/' + ticker + '/'
    if not os.path.exists(filepath): make_dirs(filepath)
    filename = filepath + ticker + '_all_messages.pk'
    new_filename = filepath + ticker + '_new_messages.pk'  # for new data when updating
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

    if only_update_latest:
        # too hard to deal with existing new messages, just start over if partially completed
        earliest = None
        new_messages = []
        print('going to update only the latest messages')
    else:
        print('going to get the earliest messages to the end')
        new_messages = None

    start = time.time()
    # returns a dictionary with keys ['cursor', 'response', 'messages', 'symbol']
    # docs say returns less than or equal to max, but seems to be only less than
    # get first request
    st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
    if st is None:
        print('returned None for some reason')
    elif st is False:
        print('tried all access tokens, none have enough calls left')
        return
    else:
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
            if req_left is None:
                print('requests left is None, probably need to wait longer...')
                time.sleep(5 * 60)
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
            st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
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
    write_files(all_messages, filename, new_messages, new_filename, only_update_latest)


def get_sentiments_vader(x, analyzer):
    vs = analyzer.polarity_scores(x)
    return pd.Series([vs['compound'], vs['pos'], vs['neg'], vs['neu']], index=['compound', 'pos', 'neg', 'neu'])


def get_sentiments_vader_dask(df, analyzer):
    vs = analyzer.polarity_scores(df['body'])
    return pd.Series([vs['compound'], vs['pos'], vs['neg'], vs['neu']], index=['compound', 'pos', 'neg', 'neu'])



def load_historical_data(ticker='AAPL'):
    filepath = get_home_dir() + 'stocktwits/data/' + ticker + '/'
    filename = filepath + ticker + '_all_messages.pk'
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            all_messages = pk.load(f)
    else:
        print('file doesn\'t exist!')
        return None

    df = pd.io.json.json_normalize(all_messages)
    # convert datetime column to datetime and set as index
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.set_index('created_at', inplace=True)
    df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('America/New_York')
    # drop empty columns
    df.drop(['entities.sentiment', 'reshare_message.message.entities.sentiment'], axis=1, inplace=True)
    # is the bearish/bullish tag
    df['entities.sentiment.basic'].value_counts()

    # most useful columns
    useful_df = df[['body', 'entities.sentiment.basic', 'likes.total', 'user.followers']]
    useful_df = useful_df.sort_index(ascending=False)

    analyzer = SentimentIntensityAnalyzer()
    """
    https://github.com/cjhutto/vaderSentiment#about-the-scoring
    compound: most useful single metric -- average valence of each word in sentence
    """
    print('getting sentiments')
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
    conv_dict = {'Bearish': -1, np.nan: 0, 'Bullish': 1}
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


def combine_with_price_data(ticker='TSLA'):
    # meld with price data and see if any correlations
    trades_3min = scrape_ib.load_data(ticker)  # by default loads 3 mins bars
    st = load_historical_data(ticker)  # get stock twits data
    st = st.iloc[::-1]  # reverse order from oldest -> newest to match IB data
    # create counts column for resampling
    st['count'] = 1
    st_min = st[['entities.sentiment.basic', 'compound', 'pos', 'neg', 'neu', 'count']]
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
    new_feats.columns = ['bearish_bullish_closed', 'compound_closed', 'pos_closed', 'neg_closed', 'neu_closed', 'count_closed']

    st_full_3min = st_min_3min.copy()
    nf_cols = new_feats.columns
    for d in new_feats.index:
        for c in nf_cols:
            st_full_3min.loc[d:d + pd.Timedelta('1D'), c] = new_feats.loc[d, c]

    # merge sentiment with price data
    full_df = pd.concat([trades_3min, st_full_3min], axis=1)
    full_df = full_df.loc[trades_3min.index]

    # resample to daily frequency
    st_daily = st_min.resample('1D', label='left').mean().ffill()
    st_daily['count'] = st_min['count'].resample('1D', label='left').sum().ffill()
    st_daily_std = st_min.resample('1D', label='left').std().ffill()

    # count column is all 0s for some reason
    st_daily_std.drop('count', inplace=True, axis=1)
    st_daily_std.columns = [c + '_std' for c in st_daily_std.columns]

    # st_daily_full = pd.concat([st_daily, st_daily_std], axis=1)
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

    # make new feature for sentiment action over weekends and closed days
    # monday = 0, sunday = 6
    # TODO:
    # weekend_feats = pd.DataFrame()
    # temp_feats = pd.DataFrame()
    # for i in st_daily.index:
    #     if i not in trades_1d.index:
    #         temp_feats


    full_daily = pd.concat([trades_1d, st_daily, st_daily_std], axis=1)
    future_price_chg_cols = []
    for i in range(1, 11):
        full_daily[str(i) + 'd_future_price'] = full_daily['close'].shift(-i)
        full_daily[str(i) + 'd_future_price_chg_pct'] = full_daily[str(i) + 'd_future_price'].pct_change(i)
        future_price_chg_cols.append(str(i) + 'd_future_price_chg_pct')
        # drop future price column because we care about % change
        full_daily.drop(str(i) + 'd_future_price', axis=1, inplace=True)


    non_price_chg_cols = [c for c in full_daily.columns if c not in future_price_chg_cols]
    f = plt.figure(figsize=(20, 20))
    sns.heatmap(full_daily.corr().loc[non_price_chg_cols, future_price_chg_cols], annot=True)
    plt.tight_layout()

    ######### try some ML
    from sklearn.ensemble import RandomForestRegressor

    rfr = RandomForestRegressor(n_estimators=500, random_state=42, n_jobs=-1, max_depth=10, min_samples_split=4)
    nona = full_daily.dropna()
    feat_cols = ['entities.sentiment.basic', 'compound', 'pos', 'neg', 'neu', 'count', 'entities.sentiment.basic_std', 'compound_std']
    feats = nona[feat_cols]
    # 3d seems to be best for IQ
    targs = nona['3d_future_price_chg_pct']#nona[future_price_chg_cols]
    tr_idx = int(0.8 * feats.shape[0])
    tr_feats = feats[:tr_idx]
    tr_targs = targs[:tr_idx]
    te_feats = feats[tr_idx:]
    te_targs = targs[tr_idx:]

    rfr.fit(tr_feats, tr_targs)
    print(rfr.score(tr_feats, tr_targs))
    print(rfr.score(te_feats, te_targs))
    tr_preds = rfr.predict(tr_feats)
    te_preds = rfr.predict(te_feats)

    plt.scatter(tr_targs, tr_preds, label='train')
    plt.scatter(te_targs, te_preds, label='test')

    feat_imps = rfr.feature_importances_
    feat_idx = np.argsort(feat_imps)[::-1]
    x = range(len(feat_imps))
    plt.bar(x, feat_imps[feat_idx])
    plt.xticks(x, feats.columns[feat_idx], rotation=90)
    plt.tight_layout()

    # get feature importances


    # slight positive correlation
    plt.scatter(full_daily['entities.sentiment.basic_std'], full_daily['10d_future_price_chg_pct'])

    plt.scatter(full_daily['opt_vol_close'], full_daily['10d_future_price_chg_pct'])

    plt.scatter(full_daily['count'], full_daily['10d_future_price_chg_pct'])

    plt.scatter(full_daily['compound'], full_daily['1d_future_price_chg_pct'])

    plt.scatter(full_daily['entities.sentiment.basic'], full_daily['10d_future_price_chg_pct'])

    plt.scatter(full_daily['compound'], full_daily['10d_future_price_chg_pct'])
    plt.scatter(full_daily['pos'], full_daily['10d_future_price_chg_pct'])

    # get things correlated with 5d change > 0.1
    idx_5d = np.where(full_daily.columns == '5d_future_price_chg_pct')[0][0]
    idx_1d = np.where(full_daily.columns == '1d_future_price_chg_pct')[0][0]
    full_daily.columns[:idx_1d][(full_daily.corr() > 0.1).iloc[:idx_1d, idx_5d]]

    # TODO: get post volume as a feature...looks like high post volume increase, high sentiment, and high short % is a good combo for incr in price (MTCH)

    # make 1h price change and 1h future price change
    full_df['close_1h_chg'] = full_df['close'].pct_change(20)  # for 3 min, 20 segments is 60 mins
    # full_tsla['3m_future_price'] = full_tsla['close'].shift(-1)  # sanity check
    full_df['1h_future_price'] = full_df['close'].shift(-20)
    full_df['1h_future_price_chg'] = full_df['1h_future_price'].pct_change(20)

    full_df['8h_future_price'] = full_df['close'].shift(-20*8)
    full_df['8h_future_price_chg'] = full_df['1h_future_price'].pct_change(20*8)


def plot_combined_data(full_df):
    # plt.scatter(full_tsla['bearish_bullish_closed'], full_tsla['1h_future_price_chg'])
    f = plt.figure(figsize=(12, 12))
    sns.heatmap(full_df.corr(), annot=True)
    plt.tight_layout()

    plt.scatter(full_df['bearish_bullish_closed'], full_df['8h_future_price_chg'])
    plt.scatter(full_df['entities.sentiment.basic'], full_df['8h_future_price_chg'])

    plt.scatter(full_df['opt_vol_high'], full_df['8h_future_price_chg'])

    # when it was -0.05, strong correlation to negative returns -- all on one day, 3/28
    plt.scatter(full_df['compound_closed'], full_df['8h_future_price_chg'])


    # get daily price change and daily bearish/bullish and sentiments

    # don't think I nede this anymore
    # trades_1d = trades_3min.resample('1D').apply({'open': 'first',
    #                                         'high': 'max',
    #                                         'low': 'min',
    #                                         'close': 'last'})

# resample bearish/bullish to daily, get number of counts of posts

# ticker = 'TSLA'
# scrape_historical_data(ticker, only_update_latest=True)
# scrape_historical_data(ticker, only_update_latest=False)

# reached end of data

# no messages
# ['XLM']


def get_stock_watchlist(update=True):
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

    filename = 'tickers_watching.pk'
    cur_tickers = []
    if os.path.exists(filename):
        cur_tickers = pk.load(open(filename, 'rb'))

    if update:
        trending = None
        while trending is None:
            trending = api.get_trending_stocks()
            time.sleep(10)

        # only unique tickers
        tickers = sorted(list(set(cur_tickers + trending)))
        pk.dump(tickers, open(filename, 'wb'), -1)  # use highest available pk protocol
        return tickers
    else:
        return cur_tickers


def update_lots_of_tickers():
    tickers = get_stock_watchlist()
    while True:
        for t in tickers:
            print('scraping', t)
            scrape_historical_data(t)
            scrape_historical_data(t, only_update_latest=True)


# # find large gap in data for missing intermediate data
# tsla = load_historical_data('TSLA')
# index_diff = tsla.index[:-1] - tsla.index[1:]
# max_diff_idx = np.argmax(index_diff)
# tsla.iloc[max_diff_idx]
# tsla.iloc[max_diff_idx + 1]
