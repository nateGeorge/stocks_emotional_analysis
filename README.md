# stocks_emotional_analysis
Uses sentiment and emotion classifier to predict future stock prices.  This also scrapes stocktwits.

Currently it stores data in hdf5 files, which is unweildy.  It would be much better to store data in MongoDB or another NoSQL database.


# stocktwits

For stocktwits, create an application:
https://api.stocktwits.com/developers/apps/new
Then use the consumer key as client id, and your domain for the app at

https://<USER>:<PASSWORD>@api.stocktwits.com/api/2/oauth/authorize?client_id=<CLIENT_ID>&response_type=token&redirect_uri=http://<YOUR DOMAIN>&scope=read,watch_lists,publish_messages,publish_watch_lists,follow_users,follow_stocks

your domain should be domain set during app creation process (I just use www.google.com and http://www.google.com)

https://<USER>:<PASSWORD>@api.stocktwits.com/api/2/oauth/authorize?client_id=<CLIENT_ID>&response_type=token&redirect_uri=http://www.google.com&scope=read,watch_lists,publish_messages,publish_watch_lists,follow_users,follow_stocks

The access token shows up in the URL


# emotion analysis

There are many data sources for emotion analysis:


https://github.com/JULIELab/EmoBank
http://saifmohammad.com/WebPages/EmotionIntensity-SharedTask.html
https://www.crowdflower.com/wp-content/uploads/2016/07/text_emotion.csv

https://stackoverflow.com/a/34860872/4549682

http://www.romanklinger.de/ssec/

http://nlp.cs.swarthmore.edu/semeval/tasks/task14/data.shtml

https://www.cs.york.ac.uk/semeval-2013/

http://alt.qcri.org/semeval2017/task4/index.php?id=data-and-tools

https://www.dropbox.com/s/byzr8yoda6bua1b/2017_English_final.zip?



lexicons:
https://github.com/JULIELab/EmoMap/tree/master/lrec18/resources

should be more lexicons available from this paper: https://github.com/JULIELab/wordEmotions/blob/master/naacl/framework/constants.py

https://github.com/JULIELab/HistEmo/tree/master/historical_gold_lexicons

http://sentiment.nrc.ca/lexicons-for-research/

http://saifmohammad.com/WebPages/lexicons.html
