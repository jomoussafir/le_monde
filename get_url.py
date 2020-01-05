import re
import os,sys
import glob
import threading
import datetime
import pathlib

##################################################################################
## Functions
##################################################################################

## class used to send batches of cur requests
class GetUrlThread (threading.Thread):
    def __init__(self, url, fname):
        self.url = url
        self.fname = fname
        threading.Thread.__init__(self)

    def run(self):
        print(".",end="",flush=True)
        cmd = "curl -s --cookie cookie.txt " + self.url + " > " + self.fname
        os.system(cmd)


def date_seq(start_date, end_date):
    date_list=[]
    new_date=start_date
    while new_date <= end_date:
        date_list.append(new_date)
        new_date=new_date + datetime.timedelta(days = 1)
    return(date_list)


##################################################################################
## Params
##################################################################################
le_monde_base_url="https://www.lemonde.fr/archives-du-monde/"

start_date = datetime.datetime(1945, 1, 1)
end_date = datetime.datetime(2019, 12, 25)
date_list = date_seq(start_date, end_date)

raw_dir="raw"
url_dir="url"
art_dir = "articles"

raw_fname_min_size=50000


##################################################################################
## read all raw files and extract article urls
##################################################################################

get_url=True
## get_url=False
if get_url:
    ## make raw_dir if it does not exist
    if not os.path.isdir(url_dir):
        pathlib.Path(url_dir).mkdir(parents=True, exist_ok=True)
        
    ## get date list from raw files
    date_list=[]
    raw_fname_list = glob.glob(raw_dir + "/raw_*.html")
    raw_fname_list.sort()
    for f in raw_fname_list:
        m=re.search("raw_(\d{4})-(\d{2})-(\d{2}).*html",f)
        if m:
            d=datetime.datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)))
            date_list.append(d)
    date_list=list(set(list(date_list)))
    date_list.sort()

    ## for each date find raw files raw_yyyy-mm-dd[_x].html
    ## extract urls from them
    for d in date_list:
        d_str=d.strftime("%Y-%m-%d")
        print(d_str)
        raw_fname_list_tmp=[]
        for f in raw_fname_list:
            if re.search(d_str,f):
                raw_fname_list_tmp.append(f)
        
        
        url_fname = url_dir + "/url_" + d.strftime("%Y-%m-%d") + ".html"
        url_fd=open(url_fname, "w")
        for f in raw_fname_list_tmp:
            
            raw_fd=open(f,"r")
            raw_lines=raw_fd.readlines()
            raw_fd.close()
            for l in raw_lines:
                m = re.findall("https:\/\/www.lemonde.fr\/\w+[-\w+]*\/article\/.*?html", l) 
                if m:                    
                    for e in m:
                        if re.search("article\/"+d.strftime("%Y/%m/%d"),e):
                            url_fd.write(e+"\n")
                            #print(e)
                            #print("-"*10)        
        url_fd.close()
