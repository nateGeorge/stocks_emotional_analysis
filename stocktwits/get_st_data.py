import os
import time
import pickle as pk

import pandas as pd
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


def scrape_historical_data(ticker='AAPL', verbose=True):
    filepath = get_home_dir() + 'stocktwits/data/' + ticker + '/'
    if not os.path.exists(filepath): make_dirs(filepath)
    filename = filepath + ticker + '_all_messages.pk'
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            all_messages = pk.load(f)
        earliest = min([m['id'] for m in all_messages])  #should also be able to do this: all_messages[-1]['id']
    else:
        print('no previously existing file')
        earliest = None
        all_messages = []

    start = time.time()
    # returns a dictionary with keys ['cursor', 'response', 'messages', 'symbol']
    # docs say returns less than or equal to max, but seems to be only less than
    st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
    if st is None:
        print('returned None for some reason')
    elif st is False:
        print('tried all access tokens, none have enough calls left')
        return
    else:
        all_messages.extend(st['messages'])

    num_calls = 1

    while True:
        if st['cursor']['more']:
            # save every 50 calls just in case something happens
            if num_calls % 50 == 0:
                # overwrite old data with updated data
                with open(filename, "wb") as f:
                    pk.dump(all_messages, f)
            if verbose:
                print('getting more data, made', str(num_calls), 'calls so far')
                print(str(req_left), 'requests left')
            time_elapsed = time.time() - start
            if req_left < 2:  # or (time_elapsed < 3600 and num_calls > 398)
                print('made too many calls too fast, need to change access token or')
                print('wait another', str(round((3600 - time_elapsed) / 60)), 'minutes')
                print('made', str(num_calls), 'calls in', str(round(time_elapsed)), 'seconds')

                # overwrite old data with updated data
                with open(filename, "wb") as f:
                    pk.dump(all_messages, f)

                # TODO: sleep until reset time from header is met
                time.sleep(3601 - time_elapsed)
                start = time.time()
                num_calls = 0

            earliest = st['cursor']['max']
            st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
            if st is None:
                print('returned None for some reason')
                # overwrite old data with updated data
                with open(filename, "wb") as f:
                    pk.dump(all_messages, f)
                st = {'cursor': {'more': True}}
                continue
            elif st is False:
                print('tried all access tokens, stopping for now')
                break

            all_messages.extend(st['messages'])
            num_calls += 1
            # seems to take long enough that we don't need to sleep
            # time.sleep(0.117)
        else:
            print('reached end of data')
            break

    # write data with updates
    with open(filename, "wb") as f:
        pk.dump(all_messages, f)


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
    df['created_at'] = pd.to_datetime(df['created_at'])
    # drop empty columns
    df.drop(['entities.sentiment', 'reshare_message.message.entities.sentiment'], axis=1, inplace=True)
    # is the bearish/bullish tag
    df['entities.sentiment.basic'].value_counts()

    # most useful columns
    useful_df = df[['body', 'created_at', 'entities.sentiment.basic', 'likes.total', 'user.followers']]

    analyzer = SentimentIntensityAnalyzer()

    def get_sentiments_vader(x):
        vs = analyzer.polarity_scores(x)
        return pd.Series([vs['compound'], vs['pos'], vs['neg'], vs['neu']], index=['compound', 'pos', 'neg', 'neu'])

    sentiments = useful_df['body'].apply(get_sentiments_vader)
    # sentiments.hist()
    full_useful = pd.concat([useful_df, sentiments], axis=1)

    return full_useful


    # meld with price data and see if any correlations
