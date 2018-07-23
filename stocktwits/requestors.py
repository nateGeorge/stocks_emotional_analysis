""" A variety of classes using different libraries to implement `get_json` and `post_json` methods.
"""
import os
import json
import logging as log
from collections import OrderedDict
# Try to import modules needed for Google App Engine just in case
try:
    from google.appengine.api import urlfetch
    from google.appengine.runtime import DeadlineExceededError
    import urllib
    import json
except:
    pass

# Try to import requests just in case
try:
    import requests
except:
    pass


# StockTwits details
ST_BASE_URL = 'https://api.stocktwits.com/api/2/'
all_ats = ['', 'stock_twits_testing_at', 'stock_twits_testing2_at', 'stock_twits_aapl1', 'stock_twits_vioo', 'stock_twits_sly']
at_name = all_ats[0]
ST_BASE_PARAMS = dict(access_token=os.getenv(at_name))

__author__ = 'Jason Haury'


def get_header_info(headers):
    """
    gets crucial header info such as how many requests left and when it resets
    """
    try:
        return int(headers['X-RateLimit-Remaining']), int(headers['X-RateLimit-Reset'])
    except KeyError:
        return None, None



class Requests():
    """ Uses `requests` library to GET and POST to Stocktwits, and also to convert resonses to JSON
    """
    def __init__(self):
        # dictionary of access tokens, max number of calls left, and time till reset
        self.ats = OrderedDict({'': [200, None],
                    'stock_twits_testing_at': [400, None],
                    'stock_twits_testing2_at': [400, None],
                    'stock_twits_aapl1': [400, None],
                    'stock_twits_vioo': [400, None],
                    'stock_twits_sly': [400, None]})
        self.at_index = 1
        self.at = list(self.ats.items())[self.at_index][0]
        self.at_val = os.getenv(self.at)
        ST_BASE_PARAMS['access_token'] = os.getenv(self.at)


    def set_at(self, at):
        self.at = at
        self.at_val = os.getenv(self.at)
        ST_BASE_PARAMS['access_token'] = os.getenv(self.at)


    def get_json(self, url, params=None):
        """ Uses tries to GET a few times before giving up if a timeout.  returns JSON
        """
        calls_threshold = 3
        resp = None
        for i in range(4):
            try:
                tries = 1
                while tries < 6:
                    resp = requests.get(url, params=params, timeout=5)
                    calls_left, limit_reset_time = get_header_info(resp.headers)
                    if calls_left is None:
                        continue
                    self.ats[self.at] = [calls_left, limit_reset_time]
                    if calls_left < calls_threshold:
                        print('calls left:', calls_left)
                        self.at_index = (self.at_index + 1) % 6
                        at = list(self.ats.items())[self.at_index][0]
                        self.set_at(at)
                        # need to update params here so the requests.get uses the new access token
                        params['access_token'] = self.at_val
                        print('trying next access token:', at)
                        tries += 1
                        if tries == 6 and calls_left < 5:
                            print('tried all access tokens, none have enough calls available')
                            return False, None, None
                    # if we have enough calls left or if we tried one that worked
                    elif calls_left >= calls_threshold or (calls_left != 0 and tries > 1):
                        break

            except requests.Timeout:
                trimmed_params = {k: v for k, v in params.items() if k not in ST_BASE_PARAMS.keys()}
                log.error('GET Timeout to {} w/ {}'.format(url[len(ST_BASE_URL):], trimmed_params))
            if resp is not None:
                break
        if resp is None:
            log.error('GET loop Timeout')
            return None, None, None
        else:
            header_info = get_header_info(resp.headers)
            if header_info[0] is None:
                print('header info was None.  resp.content:')
                print(resp.content)
                return None, None, None

            return json.loads(resp.content.decode('utf-8')), header_info[0], header_info[1]

    def post_json(url, params=None, deadline=30):
        """ Tries to post a couple times in a loop before giving up if a timeout.
        """
        resp = None
        for i in range(4):
            try:
                resp = requests.post(url, params=params, timeout=5)
            except requests.Timeout:
                trimmed_params = {k: v for k, v in params.items() if k not in ST_BASE_PARAMS.keys()}
                log.error('POST Timeout to {} w/ {}'.format(url[len(ST_BASE_URL):], trimmed_params))
            if resp is not None:
                break
        # TODO wrap in appropriate try/except
        header_info = get_header_info(resp.headers)
        return json.loads(resp.content.decode('utf-8')), header_info[0], header_info[1]



class GAE():
    """ A wrapper around Google App Engine's `urlfetch` to make it act like `requests` package
    """
    def get_json(url, params=None):
        """ Uses tries to GET a few times before giving up if a timeout.  returns JSON
        """
        params = ('?' + urllib.urlencode(params)) if params else ''  # URL query string parameters (Access Token, etc)
        resp = None
        for i in range(4):
            try:
                resp = urlfetch.fetch(url+params, method='GET')
            except:
                trimmed_params = {k: v for k, v in params.items() if k not in ST_BASE_PARAMS.keys()}
                log.error('GET Timeout to {} w/ {}'.format(url[len(ST_BASE_URL):], trimmed_params))
            if resp is not None:
                break
        if resp is None:
            log.error('GET loop Timeout')
            return None, None, None
        else:
            header_info = get_header_info(resp.headers)
            return json.loads(resp.content.decode('utf-8')), header_info[0], header_info[1]

    def post_json(url, params=None, deadline=30):
        """ Tries to post a couple times in a loop before giving up if a timeout.
        """
        params = '?' + urllib.urlencode(params) if params else ''  # URL query string parameters (Access Token)
        resp = None
        for i in range(4):
            try:
                resp = urlfetch.fetch(url+params, method='POST', deadline=deadline)
            except DeadlineExceededError:
                trimmed_params = {k: v for k, v in params.items() if k not in ST_BASE_PARAMS.keys()}
                log.error('POST Timeout to {} w/ {}'.format(url[len(ST_BASE_URL):], trimmed_params))
            if resp is not None:
                break
        # TODO wrap in appropriate try/except
        header_info = get_header_info(resp.headers)
        return json.loads(resp.content.decode('utf-8')), header_info[0], header_info[1]
