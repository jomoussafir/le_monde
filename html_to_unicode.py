import sys
import html
import glob
import requests
from urllib import request

from bs4 import BeautifulSoup


url_fd = open("url/url_2019-12-17.html")
url_list=url_fd.readlines()
url_fd.close()

url=url_list[1]



## page = requests.get(url)
page = request.urlopen(url).read().decode('utf8')

soup = BeautifulSoup(page, 'html.parser')
title=soup.find_all('title')
paragraph=soup.find_all('p',  class_='article__paragraph')

title = soup.title.string
paragraph=soup.find_all('p',  class_='article__paragraph')

print(title)

for p in paragraph:
    print(p.get_text())



#for url in url_list[1]:
#    page = requests.get(url)




#title=soup.find_all('title')


#print(title.get_text())



#sys.exit(0)
