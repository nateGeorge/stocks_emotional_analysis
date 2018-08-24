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
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import ParameterGrid
from tqdm import tqdm

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
            st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
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
    df.drop(['entities.sentiment', 'reshare_message.message.entities.sentiment'], axis=1, inplace=True)
    # is the bearish/bullish tag
    df['entities.sentiment.basic'].value_counts()

    # most useful columns
    useful_df = df.loc[:, ['body', 'entities.sentiment.basic', 'likes.total', 'user.followers']]
    useful_df.drop_duplicates(inplace=True)
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


def combine_with_price_data(ticker='TSLA', must_be_up_to_date=True):
    # meld with price data and see if any correlations
    trades_3min = scrape_ib.load_data(ticker)  # by default loads 3 mins bars
    # check if data up to date, first check if data is same day as NY date
    if must_be_up_to_date:
        up_to_date = check_if_data_up_to_date(trades_3min.index[-1].date())
        if not up_to_date:
            print('price data not up to date')
            return None, None, None

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


    non_price_chg_cols = [c for c in full_daily.columns if c not in future_price_chg_cols]
    f = plt.figure(figsize=(20, 20))
    sns.heatmap(full_daily.corr().loc[non_price_chg_cols, future_price_chg_cols], annot=True)
    plt.tight_layout()
    plt.show()


    # slight positive correlation
    plt.scatter(full_daily['entities.sentiment.basic_std'], full_daily['10d_future_price_chg_pct'])

    plt.scatter(full_daily['pos_weekend_std'], full_daily['10d_future_price_chg_pct'])

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

    # list from scrape_ib
    # tickers = ['CRON', 'ADBE', 'ROKU', 'PLNT', 'BDSI', 'MTCH', 'DBX', 'FNKO', 'OSTK', 'SPY', 'BABA', 'MU', 'QQQ', 'SNAP', 'TTD', 'VKTX', 'OMER', 'OLED']
    # tickers =  tickers + ['ALNY', 'OMER', 'FOLD', 'RDFN', 'TUR', 'TXMD', 'TDOC', 'SQ',
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
            # TODO: save latest in a temp file, then once finished getting all new data, append to big file
            scrape_historical_data(t, only_update_latest=True)


def do_ml(ticker, must_be_up_to_date=False):
    df = load_historical_data(ticker)
    full_3min, full_daily, future_price_chg_cols = combine_with_price_data(ticker, must_be_up_to_date)
    ml_on_combined_data(ticker, full_daily, future_price_chg_cols)


def plot_close_bear_bull_count():
    f, axs = plt.subplots(4, 1)
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



# TODO: plot above with counts, create new feature from counts and bear/bull, resample bear/bull with sum instead of mean (and do for individual bear/bull)
# examine what happened when it went bearish for a sec then back to bullish

# get predictions for all stocks in watchlist
# tickers = get_stock_watchlist()
# full_3min, full_daily, future_price_chg_cols = combine_with_price_data('SNAP')

# # find large gap in data for missing intermediate data
# tsla = load_historical_data('TSLA')
# index_diff = tsla.index[:-1] - tsla.index[1:]
# max_diff_idx = np.argmax(index_diff)
# tsla.iloc[max_diff_idx]
# tsla.iloc[max_diff_idx + 1]
