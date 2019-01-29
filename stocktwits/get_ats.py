"""
automation for getting access tokens
"""

import os
from collections import OrderedDict

import requests as req
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException


# setup API apps -- use the same domain for each of them
# I used www.google.com for 'Site domain'
uname = os.environ.get('st_username')
password = os.environ.get('st_password')
domain = 'www.google.com'
app_names = ['fill in your app names here', '', '', '', '']
consumer_keys = ['fill in each of your consumer keys in these strings',
                '',
                '',
                '',
                '']
consumer_secrets = ['fill in each consumer secret in these strings',
                    '',
                    '',
                    '',
                    '']

def get_at(driver, consumer_key, consumer_secret):
    # consumer key and client id are the same thing
    driver.get('https://api.stocktwits.com/api/2/oauth/authorize?client_id={}&response_type=code&redirect_uri=http://{}&scope=read,watch_lists,publish_messages,publish_watch_lists,direct_messages,follow_users,follow_stocks'.format(consumer_key, domain))
    # login if needed
    try:
        login_box = driver.find_element_by_id('user_session_login')
        login_box.send_keys(uname)
        pass_box = driver.find_element_by_id('user_session_password')
        pass_box.send_keys(password)
        pass_box.send_keys(Keys.ENTER)
    except NoSuchElementException:
        print('probably already logged in')

    # if already authorized, will go straight to redirect domain with code
    try:
        connect_button = driver.find_element_by_link_text('Connect')
        connect_button.click()
    except NoSuchElementException:
        print('probably already authorized this app')

    # code is in redirect url
    url = driver.current_url
    code = url.split('/?')[-1].split('&')[0].split('=')[1]
    res = req.post('https://api.stocktwits.com/api/2/oauth/token?client_id={}&client_secret={}&code={}&grant_type=authorization_code&redirect_uri=http://www.google.com'.format(consumer_key, consumer_secret, code))
    access_token = res.json()['access_token']
    return access_token


"""
need to first download and setup geckodriver
on linux, download latest version from here:
https://github.com/mozilla/geckodriver/releases/tag/v0.23.0
and move to /usr/bin
"""
driver = webdriver.Firefox()

ats = OrderedDict()
for n, k, s in zip(app_names, consumer_keys, consumer_secrets):
    ats[n] = get_at(driver, k, s)

driver.quit()
