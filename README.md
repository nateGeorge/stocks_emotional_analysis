# stocks_emotional_analysis
Uses sentiment and emotion classifier to predict future stock prices.


# stocktwits

For stocktwits, create an application:
https://api.stocktwits.com/developers/apps/new
Then use the consumer key as client id, and your domain for the app at

https://<USER>:<PASSWORD>@api.stocktwits.com/api/2/oauth/authorize?client_id=<CLIENT_ID>&response_type=token&redirect_uri=http://<YOUR DOMAIN>&scope=read,watch_lists,publish_messages,publish_watch_lists,follow_users,follow_stocks

your domain should be domain set during app creation process (I just use www.google.com and http://www.google.com)

https://<USER>:<PASSWORD>@api.stocktwits.com/api/2/oauth/authorize?client_id=<CLIENT_ID>&response_type=token&redirect_uri=http://www.google.com&scope=read,watch_lists,publish_messages,publish_watch_lists,follow_users,follow_stocks

The access token shows up in the URL
