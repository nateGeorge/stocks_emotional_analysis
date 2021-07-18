scraping NDX
going to update only the latest messages
---------------------------------------------------------------------------
ValueError                                Traceback (most recent call last)
<ipython-input-1-2d6865f2d89b> in <module>
----> 1 update_lots_of_tickers_mongo()

/media/nate/nates/github/stocks_emotional_analysis/stocktwits/get_st_data.py in update_lots_of_tickers_mongo()
   1861                 # scrape_historical_data(t)
   1862                 # TODO: save latest in a temp file, then once finished getting all new data, append to big file
-> 1863                 scrape_historical_data_mongo(t, only_update_latest=True)
   1864             except KeyError:
   1865                 print('probably no data')

/media/nate/nates/github/stocks_emotional_analysis/stocktwits/get_st_data.py in scrape_historical_data_mongo(ticker, verbose, only_update_latest)
   2049     if only_update_latest:
   2050         # see if we got all the new data yet
-> 2051         done = check_new_data_mongo(latest, st, coll, db, ticker)
   2052         if done:
   2053             client.close()

/media/nate/nates/github/stocks_emotional_analysis/stocktwits/get_st_data.py in check_new_data_mongo(latest, st, coll, db, ticker)
   2145     # old way of doing it, but doesn't work if latest message was deleted!
   2146     # if latest in set(new_ids):
-> 2147     if min(new_ids) < latest:
   2148         print('got all new data')
   2149         new_msg_idx = np.where(latest >= np.array(new_ids))[0][0]

ValueError: min() arg is an empty sequence
