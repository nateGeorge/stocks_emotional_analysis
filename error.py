trying next access token:
header info was None.  resp.content:
b'<!DOCTYPE html>\n<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->\n<!--$
if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->\n<!--[if IE 8]>    <html clas$
="no-js ie8 oldie" lang="en-US"> <![endif]-->\n<!--[if gt IE 8]><!--> <html class="no-js" lang="en-$
S"> <!--<![endif]-->\n<head>\n\n\n<title>api.stocktwits.com | 502: Bad gateway</title>\n<meta chars$
t="UTF-8" />\n<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />\n<meta http-equ$
v="X-UA-Compatible" content="IE=Edge,chrome=1" />\n<meta name="robots" content="noindex, nofollow" $
>\n<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1" />\n<link rel$
"stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" type="text/css" media="screen,$
rojection" />\n<!--[if lt IE 9]><link rel="stylesheet" id=\'cf_styles-ie-css\' href="/cdn-cgi/style$
/cf.errors.ie.css" type="text/css" media="screen,projection" /><![endif]-->\n<style type="text/css"$
body{margin:0;padding:0}</style>\n\n\n\n\n</head>\n<body>\n<div id="cf-wrapper">\n\n    \n\n    <di$
 id="cf-error-details" class="cf-error-details-wrapper">\n        <div class="cf-wrapper cf-error-o$
erview">\n            <h1>\n              \n              <span class="cf-error-type">Error</span>\$
              <span class="cf-error-code">502</span>\n              <small class="heading-ray-id">R$
y ID: 49dbb5931865c7a7 &bull; 2019-01-23 16:41:41 UTC</small>\n            </h1>\n            <h2 c$
ass="cf-subheadline">Bad gateway</h2>\n        </div><!-- /.error-overview -->\n        \n        <$
iv class="cf-section cf-highlight cf-status-display">\n            <div class="cf-wrapper">\n
         <div class="cf-columns cols-3">\n                  \n<div id="cf-browser-status" class="cf$
column cf-status-item cf-browser-status ">\n  <div class="cf-icon-error-container">\n    <i class="$
f-icon cf-icon-browser"></i>\n    <i class="cf-icon-status cf-icon-ok"></i>\n  </div>\n  <span clas$
="cf-status-desc">You</span>\n  <h3 class="cf-status-name">Browser</h3>\n  <span class="cf-status-l$
bel">Working</span>\n</div>\n\n<div id="cf-cloudflare-status" class="cf-column cf-status-item cf-cl$
udflare-status ">\n  <div class="cf-icon-error-container">\n    <i class="cf-icon cf-icon-cloud"></$
>\n    <i class="cf-icon-status cf-icon-ok"></i>\n  </div>\n  <span class="cf-status-desc">Denver</$
pan>\n  <h3 class="cf-status-name">Cloudflare</h3>\n  <span class="cf-status-label">Working</span>\$
</div>\n\n<div id="cf-host-status" class="cf-column cf-status-item cf-host-status cf-error-source">$
n  <div class="cf-icon-error-container">\n    <i class="cf-icon cf-icon-server"></i>\n    <i class=$
cf-icon-status cf-icon-error"></i>\n  </div>\n  <span class="cf-status-desc">api.stocktwits.com</sp$
n>\n  <h3 class="cf-status-name">Host</h3>\n  <span class="cf-status-label">Error</span>\n</div>\n\$
                </div>\n              \n            </div>\n        </div><!-- /.status-display -->$
n\n        <div class="cf-section cf-wrapper">\n            <div class="cf-columns two">\n
      <div class="cf-column">\n                    <h2>What happened?</h2>\n                    <p>$
he web server reported a bad gateway error.</p>\n                </div>\n              \n
     <div class="cf-column">\n                    <h2>What can I do?</h2>\n                    <p>P$
ease try again in a few minutes.</p>\n                </div>\n            </div>\n              \n
      </div><!-- /.section -->\n\n        <div class="cf-error-footer cf-wrapper">\n  <p>\n    <spa$
 class="cf-footer-item">Cloudflare Ray ID: <strong>49dbb5931865c7a7</strong></span>\n    <span clas$
="cf-footer-separator">&bull;</span>\n    <span class="cf-footer-item"><span>Your IP</span>: 207.93$
211.50</span>\n    <span class="cf-footer-separator">&bull;</span>\n    <span class="cf-footer-item"
><span>Performance &amp; security by</span> <a href="https://www.cloudflare.com/5xx-error-landing?ut
m_source=error_footer" id="brand_link" target="_blank">Cloudflare</a></span>\n    \n  </p>\n</div><!
-- /.error-footer -->\n\n\n    </div><!-- /#cf-error-details -->\n</div><!-- /#cf-wrapper -->\n</bod
y>\n</html>\n'
---------------------------------------------------------------------------
TypeError                                 Traceback (most recent call last)
<ipython-input-1-a5f6e013cbd9> in <module>

----> 1 update_lots_of_tickers()

/media/nate/nates/github/stocks_emotional_analysis/stocktwits/get_st_data.py in update_lots_of_ticke
rs()
   1759         for t in tickers:
   1760             # update tickers to get watch list constantly
-> 1761             _ = get_stock_watchlist()
   1762             try:
   1763                 print('scraping', t)

/media/nate/nates/github/stocks_emotional_analysis/stocktwits/get_st_data.py in get_stock_watchlist(
update, return_trending)
   1707         trending = None
   1708         while trending is None:
-> 1709             trending = api.get_trending_stocks()
   1710             if trending is not None: break
   1711             print('sleeping 30s')

/media/nate/nates/github/stocks_emotional_analysis/stocktwits/api.py in get_trending_stocks()
     85         return None
     86
---> 87     trending = trending['symbols']
     88     # exchange does not seem to be in there anymore
     89     # symbols = [s['symbol'] for s in trending if s['exchange'] in EXCHANGES]

TypeError: 'NoneType' object is not subscriptable
