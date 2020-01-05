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
## get raw html pages for each day
## re-run a couple of times to have all files
##################################################################################

get_raw_url=True
get_raw_url=False
if get_raw_url:

    ## make raw_dir if it does not exist
    if not os.path.isdir(raw_dir):
        pathlib.Path(raw_dir).mkdir(parents=True, exist_ok=True)
        
    ## get base raw_base_file_list
    ## raw/raw_yyyy-mm-dd.html
    raw_base_fname_list = glob.glob(raw_dir + "/raw_*.html")
    for f in raw_base_fname_list:
        m=re.search("raw_(\d{4})-(\d{2})-(\d{2})\.html",f)
        if not m:
            raw_base_fname_list.remove(f)

    ## remove from date list if raw file size
    ## above threshold
    for f in raw_base_fname_list:
        if(os.path.getsize(f)>raw_fname_min_size):
            m=re.search("(\d{4})-(\d{2})-(\d{2})",f)
            d=datetime.datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)))
            date_list.remove(d)
            print(d)
    
    get_url_thread_list=[]
    print("fetch url...",end="")
    for d in date_list:
        url=le_monde_base_url + d.strftime("%d-%m-%Y/")
        print("get "+ url)
        raw_fname = raw_dir + "/raw_" + d.strftime("%Y-%m-%d") + ".html"
        get_url_thread_list.append(GetUrlThread(url, raw_fname))

    for m in get_url_thread_list:
        m.start()

    print("")
        
    for m in get_url_thread_list:
        m.join()

    print("done")
        

##################################################################################
## get raw html pages whose link
## is included in raw_html pages
##################################################################################

get_raw_url_sub=True
## get_raw_url_sub=False
if get_raw_url_sub:
    
    ## get base raw_base_file_list
    ## toc/raw_yyyy-mm-dd.html
    raw_base_fname_list_tmp = list(set(glob.glob(raw_dir + "/raw_*.html")))
    raw_base_fname_list_tmp.sort()
    raw_base_fname_list = raw_base_fname_list_tmp.copy()
    for f in raw_base_fname_list_tmp:
        m=re.search("raw_(\d{4})-(\d{2})-(\d{2})_(\d+)\.html",f)
        if m:
            raw_base_fname_list.remove(f)
                
    ## href="https://www.lemonde.fr/archives-du-monde/13-12-2019/2/
    ## <a class="river__pagination river__pagination--page " href="/archives-du-monde/29-06-2010/3/">3</a>
    get_url_thread_list=[]
    for raw_fname in raw_base_fname_list:
        m=re.search("(\d{4})-(\d{2})-(\d{2})", raw_fname)
        day=m.group(3)
        month=m.group(2)
        year=m.group(1)
        
        raw_fd=open(raw_fname, "r")
        lines = raw_fd.readlines()
        raw_fd.close()
        raw_url_tmp=[]
        for l in lines:
            pattern="archives-du-monde/"+day+"-"+month+"-"+year+"\/(\d+)"
            m=re.findall(pattern,l)
            if m:
                for e in m:
                    raw_url_tmp.append("https://www.lemonde.fr/archives-du-monde/29-06-2010/"+e+"/")
        raw_url_tmp=list(set(raw_url_tmp))
        raw_url_tmp.sort()

        for u in raw_url_tmp:
            raw_url=u
            index=re.search("\/(\d+)\/",raw_url).group(1)
            raw_fname = raw_dir + "/raw_" + year + "-" + month + "-" + day + "_" + index + ".html"
            if( (not os.path.exists(raw_fname)) or (os.path.getsize(raw_fname)<=raw_fname_min_size) ):
                print(raw_url)
                print(raw_fname)
                get_url_thread_list.append(GetUrlThread(raw_url, raw_fname))


    ## send requests
    nb_req_max=97
    for i in range(0, len(get_url_thread_list), nb_req_max):
         get_url_thread_list_sub=get_url_thread_list[i:i + nb_req_max]
         for m in get_url_thread_list_sub:
             m.start()
         print("")
         for m in get_url_thread_list_sub:
             m.join()


