import sys
import html
import glob
import requests
from urllib import request

from bs4 import BeautifulSoup







sys.exit(0)

## Fetch and parse
url_fd = open("url/url_2019-12-17.html")
url_list=url_fd.readlines()
url_fd.close()

url=url_list


test_fd=open("test.txt","w")

for url in url_list:
    print(url)
    
    ## page = requests.get(url)
    page = request.urlopen(url).read().decode('utf8')

    soup = BeautifulSoup(page, 'html.parser')
    title=soup.find_all('title')
    paragraph=soup.find_all('p',  class_='article__paragraph')

    title = soup.title.string
    paragraph=soup.find_all('p',  class_='article__paragraph')

    test_fd.write(title)

    for p in paragraph:
        test_fd.write(p.get_text())

test_fd.close()
