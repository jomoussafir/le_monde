import os,sys
import html
import re
import threading
import datetime
import pathlib
import glob
import requests
from urllib import request
from bs4 import BeautifulSoup


art_txt_dir = "articles_txt"
art_utf_8_dir = "articles_utf_8"

if not os.path.isdir(art_utf_8_dir):
    pathlib.Path(art_utf_8_dir).mkdir(parents=True, exist_ok=True)

art_txt_fname_list=list(set(glob.glob("articles_txt/2019-*/*.html")))

for fname in art_txt_fname_list:

    m=re.search("(\d{4})-(\d{2})-(\d{2})",fname)
    if m:
        out_dir=art_utf_8_dir+"/"+m.group(1) + "-" + m.group(2) + "-" + m.group(3) + "/"
        if not os.path.exists(out_dir):
            pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
        
    
    fd = open(fname, "r")
    lines=fd.readlines()
    fd.close()

    page="<html><body><p>" + "</p>\n<p>".join(lines)+"</p></body></html>"
    soup = BeautifulSoup(page, 'html.parser')

    out_fname=re.sub(art_txt_dir+"/",art_utf_8_dir+"/", fname)
    out_fd=open(out_fname, "w")
    for p in soup.find_all('p'):
        out_fd.write(p.get_text())

    out_fd.close()
    


