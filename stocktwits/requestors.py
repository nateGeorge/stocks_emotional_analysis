""" A variety of classes using different libraries to implement `get_json` and `post_json` methods.
"""
import os
import json
import logging as log
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
at_name = 'stock_twits_testing2_at'  # name of access token variable in ~/.bashrc
ST_BASE_PARAMS = dict(access_token=os.getenv(at_name))

__author__ = 'Jason Haury'


def get_header_info(headers):
    """
    gets crucial header info such as how many requests left and when it resets
    """
    return int(headers['X-RateLimit-Remaining']), int(headers['X-RateLimit-Reset'])


class Requests():
    """ Uses `requests` library to GET and POST to Stocktwits, and also to convert resonses to JSON
    """
    def get_json(url, params=None):
        """ Uses tries to GET a few times before giving up if a timeout.  returns JSON
        """
        resp = None
        for i in range(4):
            try:
                resp = requests.get(url, params=params, timeout=5)
                # to get headers:
                # resp.headers
                # contains how many requests are left and how long till reset
            except requests.Timeout:
                trimmed_params = {k: v for k, v in params.items() if k not in ST_BASE_PARAMS.keys()}
                log.error('GET Timeout to {} w/ {}'.format(url[len(ST_BASE_URL):], trimmed_params))
            if resp is not None:
                break
        if resp is None:
            log.error('GET loop Timeout')
            return None, None
        else:
            header_info = get_header_info(resp.headers)
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
            return None, None
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
