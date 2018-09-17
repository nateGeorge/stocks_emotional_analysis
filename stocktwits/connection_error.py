ConnectionError                           Traceback (most recent call last)
~/github/ipython/IPython/core/interactiveshell.py in run_code(self, code_obj, result)
   2960                 #rprint('Running code', repr(code_obj)) # dbg
-> 2961                 exec(code_obj, self.user_global_ns, self.user_ns)
   2962             finally:

<ipython-input-2-a5f6e013cbd9> in <module>
----> 1 update_lots_of_tickers()

~/github/stocks_emotional_analysis/stocktwits/get_st_data.py in update_lots_of_tickers()
   1630                 # TODO: save latest in a temp file, then once finished getting all new data, appe
nd to big file
-> 1631                 scrape_historical_data(t, only_update_latest=True)
   1632             except KeyError:

~/github/stocks_emotional_analysis/stocktwits/get_st_data.py in scrape_historical_data(ticker, verbose, o
nly_update_latest)
    176             time_elapsed = time.time() - start
--> 177             st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
    178             if req_left is None:

~/github/stocks_emotional_analysis/stocktwits/api.py in get_stock_stream(symbol, params)
     37         all_params[k] = v
---> 38     return R.get_json(ST_BASE_URL + 'streams/symbol/{}.json'.format(symbol), params=all_params)
     39

~/github/stocks_emotional_analysis/stocktwits/requestors.py in get_json(self, url, params)
     75                     # TODO: catch catch error when connection is lost -- happens here on requests
.get.
---> 76                     resp = requests.get(url, params=params, timeout=5)
     77                     calls_left, limit_reset_time = get_header_info(resp.headers)

/usr/local/lib/python3.6/dist-packages/requests/api.py in get(url, params, **kwargs)
     71     kwargs.setdefault('allow_redirects', True)
---> 72     return request('get', url, params=params, **kwargs)
     73

/usr/local/lib/python3.6/dist-packages/requests/api.py in request(method, url, **kwargs)
     57     with sessions.Session() as session:
---> 58         return session.request(method=method, url=url, **kwargs)
     59

/usr/local/lib/python3.6/dist-packages/requests/sessions.py in request(self, method, url, params, data, h
eaders, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)
    507         send_kwargs.update(settings)
--> 508         resp = self.send(prep, **send_kwargs)
    509

/usr/local/lib/python3.6/dist-packages/requests/sessions.py in send(self, request, **kwargs)
    617         # Send the request
--> 618         r = adapter.send(request, **kwargs)
    619
/usr/local/lib/python3.6/dist-packages/requests/adapters.py in send(self, request, stream, timeout, verif
y, cert, proxies)
    507
--> 508             raise ConnectionError(e, request=request)
    509

ConnectionError: HTTPSConnectionPool(host='api.stocktwits.com', port=443): Max retries exceeded with url:
 /api/2/streams/symbol/UAA.json?access_token=22c0c35722685c2b1ce162afac7f9d91a1de8a7c&max=107262111 (Caus
ed by NewConnectionError('<urllib3.connection.VerifiedHTTPSConnection object at 0x7ff8af69db38>: Failed t
o establish a new connection: [Errno -3] Temporary failure in name resolution',))

During handling of the above exception, another exception occurred:

AttributeError                            Traceback (most recent call last)
~/github/ipython/IPython/core/interactiveshell.py in showtraceback(self, exc_tuple, filename, tb_offset,
exception_only, running_compiled_code)
   1862                         # in the engines. This should return a list of strings.
-> 1863                         stb = value._render_traceback_()
   1864                     except Exception:

AttributeError: 'ConnectionError' object has no attribute '_render_traceback_'

During handling of the above exception, another exception occurred:

TypeError                                 Traceback (most recent call last)
~/github/ipython/IPython/core/interactiveshell.py in run_code(self, code_obj, result)
   2976             if result is not None:
   2977                 result.error_in_exec = sys.exc_info()[1]
-> 2978             self.showtraceback(running_compiled_code=True)
   2979         else:
   2980             outflag = False

~/github/ipython/IPython/core/interactiveshell.py in showtraceback(self, exc_tuple, filename, tb_offset,
exception_only, running_compiled_code)
   1864                     except Exception:
   1865                         stb = self.InteractiveTB.structured_traceback(etype,
-> 1866                                             value, tb, tb_offset=tb_offset)
   1867
   1868                     self._showtraceback(etype, value, stb)

~/github/ipython/IPython/core/ultratb.py in structured_traceback(self, etype, value, tb, tb_offset, numbe
r_of_lines_of_context)
   1371         self.tb = tb
   1372         return FormattedTB.structured_traceback(
-> 1373             self, etype, value, tb, tb_offset, number_of_lines_of_context)
   1374
   1375
   ~/github/ipython/IPython/core/ultratb.py in structured_traceback(self, etype, value, tb, tb_offset, numbe
   r_of_lines_of_context)
      1279             # Verbose modes need a full traceback
      1280             return VerboseTB.structured_traceback(
   -> 1281                 self, etype, value, tb, tb_offset, number_of_lines_of_context
      1282             )
      1283         else:

   ~/github/ipython/IPython/core/ultratb.py in structured_traceback(self, etype, evalue, etb, tb_offset, num
   ber_of_lines_of_context)
      1142         exception = self.get_parts_of_chained_exception(evalue)
      1143         if exception:
   -> 1144             formatted_exceptions += self.prepare_chained_exception_message(evalue.__cause__)
      1145             etype, evalue, etb = exception
      1146         else:

   TypeError: must be str, not list
