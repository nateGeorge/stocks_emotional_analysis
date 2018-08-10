import os

import twitter

c_key = os.environ.get('tw_c_key')
c_sec = os.environ.get('tw_c_sec')
atk = os.environ.get('tw_ac_tok')
ats = os.environ.get('tw_ac_sec')

api = twitter.Api(c_key, c_sec, atk, ats)

res = api.GetSearch(raw_query='q=BDSI')
