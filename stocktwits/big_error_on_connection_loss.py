132 requests left
ERROR:root:Internal Python error in the inspect module.
Below is the traceback from this internal error.

Traceback (most recent call last):
  File "/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py", line 280, in recv_into
    return self.connection.recv_into(*args, **kwargs)
  File "/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py", line 1715, in recv_into
    self._raise_ssl_error(self._ssl, result)
  File "/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py", line 1521, in _raise_ssl_error
    raise WantReadError()
OpenSSL.SSL.WantReadError

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py", line 280, in recv_into
    return self.connection.recv_into(*args, **kwargs)
  File "/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py", line 1715, in recv_into
    self._raise_ssl_error(self._ssl, result)
  File "/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py", line 1538, in _raise_ssl_error
    raise SysCallError(errno, errorcode.get(errno))
OpenSSL.SSL.SysCallError: (104, 'ECONNRESET')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/usr/local/lib/python3.5/dist-packages/urllib3/response.py", line 302, in _error_catcher
    yield
  File "/usr/local/lib/python3.5/dist-packages/urllib3/response.py", line 598, in read_chunked
    self._update_chunk_length()
  File "/usr/local/lib/python3.5/dist-packages/urllib3/response.py", line 540, in _update_chunk_length
    line = self._fp.fp.readline()
  File "/usr/lib/python3.5/socket.py", line 575, in readinto
    return self._sock.recv_into(b)
  File "/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py", line 296, in recv_into
    return self.recv_into(*args, **kwargs)
  File "/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py", line 285, in recv_into
    raise SocketError(str(e))
OSError: (104, 'ECONNRESET')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/usr/local/lib/python3.5/dist-packages/requests/models.py", line 745, in generate
    for chunk in self.raw.stream(chunk_size, decode_content=True):
  File "/usr/local/lib/python3.5/dist-packages/urllib3/response.py", line 432, in stream
    for line in self.read_chunked(amt, decode_content=decode_content):
  File "/usr/local/lib/python3.5/dist-packages/urllib3/response.py", line 626, in read_chunked
    self._original_response.close()
  File "/usr/lib/python3.5/contextlib.py", line 77, in __exit__
    self.gen.throw(type, value, traceback)
  File "/usr/local/lib/python3.5/dist-packages/urllib3/response.py", line 320, in _error_catcher
    raise ProtocolError('Connection broken: %r' % e, e)
urllib3.exceptions.ProtocolError: ('Connection broken: OSError("(104, \'ECONNRESET\')",)', OSError("(104, 'ECONNRESET')",))

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/nate/github/ipython/IPython/core/interactiveshell.py", line 2961, in run_code
    exec(code_obj, self.user_global_ns, self.user_ns)
  File "<ipython-input-2-a5f6e013cbd9>", line 1, in <module>
    update_lots_of_tickers()
  File "/home/nate/github/stocks_emotional_analysis/stocktwits/get_st_data.py", line 1608, in update_lots_of_tickers
    scrape_historical_data(t)
  File "/home/nate/github/stocks_emotional_analysis/stocktwits/get_st_data.py", line 161, in scrape_historical_data
    st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
  File "/home/nate/github/stocks_emotional_analysis/stocktwits/api.py", line 38, in get_stock_stream
    return R.get_json(ST_BASE_URL + 'streams/symbol/{}.json'.format(symbol), params=all_params)
  File "/home/nate/github/stocks_emotional_analysis/stocktwits/requestors.py", line 76, in get_json
    resp = requests.get(url, params=params, timeout=5)
  File "/usr/local/lib/python3.5/dist-packages/requests/api.py", line 72, in get
    return request('get', url, params=params, **kwargs)
  File "/usr/local/lib/python3.5/dist-packages/requests/api.py", line 58, in request
    return session.request(method=method, url=url, **kwargs)
  File "/usr/local/lib/python3.5/dist-packages/requests/sessions.py", line 508, in request
    resp = self.send(prep, **send_kwargs)
  File "/usr/local/lib/python3.5/dist-packages/requests/sessions.py", line 658, in send
    r.content
  File "/usr/local/lib/python3.5/dist-packages/requests/models.py", line 823, in content
    self._content = bytes().join(self.iter_content(CONTENT_CHUNK_SIZE)) or bytes()
  File "/usr/local/lib/python3.5/dist-packages/requests/models.py", line 748, in generate
    raise ChunkedEncodingError(e)
requests.exceptions.ChunkedEncodingError: ('Connection broken: OSError("(104, \'ECONNRESET\')",)', OSError("(104, 'ECONNRESET')",))

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/nate/github/ipython/IPython/core/interactiveshell.py", line 1863, in showtraceback
    stb = value._render_traceback_()
AttributeError: 'ChunkedEncodingError' object has no attribute '_render_traceback_'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/nate/github/ipython/IPython/core/ultratb.py", line 1095, in get_records
    return _fixed_getinnerframes(etb, number_of_lines_of_context, tb_offset)
  File "/home/nate/github/ipython/IPython/core/ultratb.py", line 313, in wrapped
    return f(*args, **kwargs)
  File "/home/nate/github/ipython/IPython/core/ultratb.py", line 347, in _fixed_getinnerframes
    records = fix_frame_records_filenames(inspect.getinnerframes(etb, context))
  File "/usr/lib/python3.5/inspect.py", line 1453, in getinnerframes
    frameinfo = (tb.tb_frame,) + getframeinfo(tb, context)
  File "/usr/lib/python3.5/inspect.py", line 1410, in getframeinfo
    filename = getsourcefile(frame) or getfile(frame)
  File "/usr/lib/python3.5/inspect.py", line 672, in getsourcefile
    if getattr(getmodule(object, filename), '__loader__', None) is not None:
  File "/usr/lib/python3.5/inspect.py", line 718, in getmodule
    os.path.realpath(f)] = module.__name__
AttributeError: module has no attribute '__name__'
---------------------------------------------------------------------------
WantReadError                             Traceback (most recent call last)
/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py in recv_into(self, *args, **kwargs)
    279         try:
--> 280             return self.connection.recv_into(*args, **kwargs)
    281         except OpenSSL.SSL.SysCallError as e:

/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py in recv_into(self, buffer, nbytes, flags)
   1714             result = _lib.SSL_read(self._ssl, buf, nbytes)
-> 1715         self._raise_ssl_error(self._ssl, result)
   1716

/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py in _raise_ssl_error(self, ssl, result)
   1520         if error == _lib.SSL_ERROR_WANT_READ:
-> 1521             raise WantReadError()
   1522         elif error == _lib.SSL_ERROR_WANT_WRITE:

WantReadError:

During handling of the above exception, another exception occurred:

SysCallError                              Traceback (most recent call last)
/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py in recv_into(self, *args, **kwargs)
    279         try:
--> 280             return self.connection.recv_into(*args, **kwargs)
    281         except OpenSSL.SSL.SysCallError as e:

/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py in recv_into(self, buffer, nbytes, flags)
   1714             result = _lib.SSL_read(self._ssl, buf, nbytes)
-> 1715         self._raise_ssl_error(self._ssl, result)
   1716

/usr/local/lib/python3.5/dist-packages/OpenSSL/SSL.py in _raise_ssl_error(self, ssl, result)
   1537                     if errno != 0:
-> 1538                         raise SysCallError(errno, errorcode.get(errno))
   1539                 raise SysCallError(-1, "Unexpected EOF")

SysCallError: (104, 'ECONNRESET')

During handling of the above exception, another exception occurred:

OSError                                   Traceback (most recent call last)
/usr/local/lib/python3.5/dist-packages/urllib3/response.py in _error_catcher(self)
    301             try:
--> 302                 yield
    303

/usr/local/lib/python3.5/dist-packages/urllib3/response.py in read_chunked(self, amt, decode_content)
    597             while True:
--> 598                 self._update_chunk_length()
    599                 if self.chunk_left == 0:

/usr/local/lib/python3.5/dist-packages/urllib3/response.py in _update_chunk_length(self)
    539             return
--> 540         line = self._fp.fp.readline()
    541         line = line.split(b';', 1)[0]

/usr/lib/python3.5/socket.py in readinto(self, b)
    574             try:
--> 575                 return self._sock.recv_into(b)
    576             except timeout:

/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py in recv_into(self, *args, **kwargs)
    295             else:
--> 296                 return self.recv_into(*args, **kwargs)
    297

/usr/local/lib/python3.5/dist-packages/urllib3/contrib/pyopenssl.py in recv_into(self, *args, **kwargs)
    284             else:
--> 285                 raise SocketError(str(e))
    286         except OpenSSL.SSL.ZeroReturnError as e:

OSError: (104, 'ECONNRESET')

During handling of the above exception, another exception occurred:

ProtocolError                             Traceback (most recent call last)
/usr/local/lib/python3.5/dist-packages/requests/models.py in generate()
    744                 try:
--> 745                     for chunk in self.raw.stream(chunk_size, decode_content=True):
    746                         yield chunk

/usr/local/lib/python3.5/dist-packages/urllib3/response.py in stream(self, amt, decode_content)
    431         if self.chunked and self.supports_chunked_reads():
--> 432             for line in self.read_chunked(amt, decode_content=decode_content):
    433                 yield line

/usr/local/lib/python3.5/dist-packages/urllib3/response.py in read_chunked(self, amt, decode_content)
    625             if self._original_response:
--> 626                 self._original_response.close()

/usr/lib/python3.5/contextlib.py in __exit__(self, type, value, traceback)
     76             try:
---> 77                 self.gen.throw(type, value, traceback)
     78                 raise RuntimeError("generator didn't stop after throw()")

/usr/local/lib/python3.5/dist-packages/urllib3/response.py in _error_catcher(self)
    319                 # This includes IncompleteRead.
--> 320                 raise ProtocolError('Connection broken: %r' % e, e)
    321

ProtocolError: ('Connection broken: OSError("(104, \'ECONNRESET\')",)', OSError("(104, 'ECONNRESET')",))

During handling of the above exception, another exception occurred:

ChunkedEncodingError                      Traceback (most recent call last)
~/github/ipython/IPython/core/interactiveshell.py in run_code(self, code_obj, result)
   2960                 #rprint('Running code', repr(code_obj)) # dbg
-> 2961                 exec(code_obj, self.user_global_ns, self.user_ns)
   2962             finally:

<ipython-input-2-a5f6e013cbd9> in <module>
----> 1 update_lots_of_tickers()

~/github/stocks_emotional_analysis/stocktwits/get_st_data.py in update_lots_of_tickers()
   1607                 print('scraping', t)
-> 1608                 scrape_historical_data(t)
   1609                 # TODO: save latest in a temp file, then once finished getting all new data, append to big file

~/github/stocks_emotional_analysis/stocktwits/get_st_data.py in scrape_historical_data(ticker, verbose, only_update_latest)
    160             time_elapsed = time.time() - start
--> 161             st, req_left, reset_time = api.get_stock_stream(ticker, {'max': earliest})
    162             if req_left is None:

~/github/stocks_emotional_analysis/stocktwits/api.py in get_stock_stream(symbol, params)
     37         all_params[k] = v
---> 38     return R.get_json(ST_BASE_URL + 'streams/symbol/{}.json'.format(symbol), params=all_params)
     39

~/github/stocks_emotional_analysis/stocktwits/requestors.py in get_json(self, url, params)
     75                     # TODO: catch catch error when connection is lost -- happens here on requests.get.
---> 76                     resp = requests.get(url, params=params, timeout=5)
     77                     calls_left, limit_reset_time = get_header_info(resp.headers)

/usr/local/lib/python3.5/dist-packages/requests/api.py in get(url, params, **kwargs)
     71     kwargs.setdefault('allow_redirects', True)
---> 72     return request('get', url, params=params, **kwargs)
     73

/usr/local/lib/python3.5/dist-packages/requests/api.py in request(method, url, **kwargs)
     57     with sessions.Session() as session:
---> 58         return session.request(method=method, url=url, **kwargs)
     59

/usr/local/lib/python3.5/dist-packages/requests/sessions.py in request(self, method, url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)
    507         send_kwargs.update(settings)
--> 508         resp = self.send(prep, **send_kwargs)
    509

/usr/local/lib/python3.5/dist-packages/requests/sessions.py in send(self, request, **kwargs)
    657         if not stream:
--> 658             r.content
    659

/usr/local/lib/python3.5/dist-packages/requests/models.py in content(self)
    822             else:
--> 823                 self._content = bytes().join(self.iter_content(CONTENT_CHUNK_SIZE)) or bytes()
    824

/usr/local/lib/python3.5/dist-packages/requests/models.py in generate()
    747                 except ProtocolError as e:
--> 748                     raise ChunkedEncodingError(e)
    749                 except DecodeError as e:

ChunkedEncodingError: ('Connection broken: OSError("(104, \'ECONNRESET\')",)', OSError("(104, 'ECONNRESET')",))

During handling of the above exception, another exception occurred:

AttributeError                            Traceback (most recent call last)
~/github/ipython/IPython/core/interactiveshell.py in showtraceback(self, exc_tuple, filename, tb_offset, exception_only, running_compiled_code)
   1862                         # in the engines. This should return a list of strings.
-> 1863                         stb = value._render_traceback_()
   1864                     except Exception:

AttributeError: 'ChunkedEncodingError' object has no attribute '_render_traceback_'

During handling of the above exception, another exception occurred:

TypeError                                 Traceback (most recent call last)
~/github/ipython/IPython/core/interactiveshell.py in run_code(self, code_obj, result)
   2976             if result is not None:
   2977                 result.error_in_exec = sys.exc_info()[1]
-> 2978             self.showtraceback(running_compiled_code=True)
   2979         else:
   2980             outflag = False

~/github/ipython/IPython/core/interactiveshell.py in showtraceback(self, exc_tuple, filename, tb_offset, exception_only, running_compiled_code)
   1864                     except Exception:
   1865                         stb = self.InteractiveTB.structured_traceback(etype,
-> 1866                                             value, tb, tb_offset=tb_offset)
   1867
   1868                     self._showtraceback(etype, value, stb)

~/github/ipython/IPython/core/ultratb.py in structured_traceback(self, etype, value, tb, tb_offset, number_of_lines_of_context)
   1371         self.tb = tb
   1372         return FormattedTB.structured_traceback(
-> 1373             self, etype, value, tb, tb_offset, number_of_lines_of_context)
   1374
   1375

~/github/ipython/IPython/core/ultratb.py in structured_traceback(self, etype, value, tb, tb_offset, number_of_lines_of_context)
   1279             # Verbose modes need a full traceback
   1280             return VerboseTB.structured_traceback(
-> 1281                 self, etype, value, tb, tb_offset, number_of_lines_of_context
   1282             )
   1283         else:

~/github/ipython/IPython/core/ultratb.py in structured_traceback(self, etype, evalue, etb, tb_offset, number_of_lines_of_context)
   1142         exception = self.get_parts_of_chained_exception(evalue)
   1143         if exception:
-> 1144             formatted_exceptions += self.prepare_chained_exception_message(evalue.__cause__)
   1145             etype, evalue, etb = exception
   1146         else:

TypeError: Can't convert 'list' object to str implicitly
