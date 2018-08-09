import os
import time
import pickle as pk

import datetime
import pytz
import pandas_market_calendars as mcal
import pandas as pd
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import api


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
    else:
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
            if req_left < 2:  # or (time_elapsed < 3600 and num_calls > 398)
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
                print('tried all access tokens, stopping for now')
                break

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


def get_sentiments_vader(analyzer, x):
    vs = analyzer.polarity_scores(x)
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

    analyzer = SentimentIntensityAnalyzer()
    """
    https://github.com/cjhutto/vaderSentiment#about-the-scoring
    compound: most useful single metric -- average valence of each word in sentence
    """
    sentiments = useful_df['body'].apply(lambda x: get_sentiments_vader(analyzer, x))
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


# meld with price data and see if any correlations
import sys
sys.path.append('../../scrape_ib')
import scrape_ib
ticker = 'TSLA'
tsla_3min = scrape_ib.load_data(ticker)
tsla_st = load_historical_data(ticker)
tsla_st = tsla_st.iloc[::-1]  # reverse order from oldest -> newest to match IB data
tsla_st_min = tsla_st[['entities.sentiment.basic', 'compound', 'pos', 'neg', 'neu']]
#TWS bars are labeled by the start of the time bin, so  use label='left'
tsla_st_min_3min = tsla_st_min.resample('3min', label='left').mean().ffill()  # forward fill because it's not frequent enough


# go through each unique date, get market open and close times from IB data,
# then get average of sentiment features from market closed times and add as new feature
unique_dates = np.unique(tsla_st_min_3min.index.date)
open_days = get_eastern_market_open_close()
last_close = None
# new_feats = {}
new_feats = pd.DataFrame()
for d in unique_dates:
    if d in open_days.index:  # if it's a trading day...
        open_time = open_days.loc[d]['market_open']
        if last_close is None:
            new_feats[d] = tsla_st_min_3min.loc[:open_time].mean()
        else:
            new_feats[d] = tsla_st_min_3min.loc[last_close:open_time].mean()

        last_close = open_days.loc[d]['market_open']

new_feats = new_feats.T
new_feats.columns = ['bearish_bullish', 'compound_closed', 'pos_closed', 'neg_closed', 'neu_closed']

tsla_st_full_3min = tsla_st_min_3min.copy()
nf_cols = new_feats.columns
for d in new_feats.index:
    for c in nf_cols:
        tsla_st_full_3min.loc[d:d + pd.Timedelta('1D'), c] = new_feats.loc[d, c]

# merge sentiment with price data
full_tsla = pd.concat([tsla_3min, tsla_st_full_3min], axis=1)
full_tsla = full_tsla.loc[tsla_3min.index]

# make 1h price change and 1h future price change
full_tsla['close_1h_chg'] = full_tsla['close'].pct_change(20)  # for 3 min, 20 segments is 60 mins
full_tsla['1h_future_price'] = full_tsla['close'].shift(-20)
full_tsla['1h_future_price_chg'] = full_tsla['1h_future_price'].pct_change(20)




# resample tsla_st to 3_min data to match 3min bars

ticker = 'TSLA'
scrape_historical_data(ticker, only_update_latest=True)
# scrape_historical_data(ticker, only_update_latest=False)
