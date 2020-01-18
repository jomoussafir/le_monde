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

front_dir="front"

front_fname_min_size=50000


##################################################################################
## get front html pages for each day
## re-run a couple of times to have all files
##################################################################################

get_front_url=True
##get_front_url=False
if get_front_url:

    ## make front_dir if it does not exist
    if not os.path.isdir(front_dir):
        pathlib.Path(front_dir).mkdir(parents=True, exist_ok=True)
        
    ## get base front_base_file_list
    ## front/front_yyyy-mm-dd.html
    ## and exclude everything else
    front_base_fname_list = glob.glob(front_dir + "/front_*.html")
    for f in front_base_fname_list:
        m=re.search("front_(\d{4})-(\d{2})-(\d{2})\.html",f)
        if not m:
            front_base_fname_list.remove(f)

    ## remove from date list if front file size
    ## above threshold
    for f in front_base_fname_list:
        if(os.path.getsize(f)>front_fname_min_size):
            m=re.search("(\d{4})-(\d{2})-(\d{2})",f)
            d=datetime.datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)))
            date_list.remove(d)
            print(d)

    get_url_thread_list=[]
    print("fetch url...",end="")
    for d in date_list:
        url=le_monde_base_url + d.strftime("%d-%m-%Y/")
        print("get "+ url)
        front_fname = front_dir + "/front_" + d.strftime("%Y-%m-%d") + ".html"
        get_url_thread_list.append(GetUrlThread(url, front_fname))

    for m in get_url_thread_list:
        m.start()

    print("")
        
    for m in get_url_thread_list:
        m.join()

    print("done")
        

