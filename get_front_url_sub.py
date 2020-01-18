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
## get front html pages whose link is included in front_html pages
##################################################################################

get_front_url_sub=True
## get_front_url_sub=False
if get_front_url_sub:
    
    ## get base front_base_file_list
    ## toc/front_yyyy-mm-dd.html
    front_base_fname_list_tmp = list(set(glob.glob(front_dir + "/front_*.html")))
    front_base_fname_list_tmp.sort()
    front_base_fname_list = front_base_fname_list_tmp.copy()
    for f in front_base_fname_list_tmp:
        m=re.search("front_(\d{4})-(\d{2})-(\d{2})_(\d+)\.html",f)
        if m:
            front_base_fname_list.remove(f)

    ## href="https://www.lemonde.fr/archives-du-monde/13-12-2019/2/
    ## <a class="river__pagination river__pagination--page " href="/archives-du-monde/29-06-2010/3/">3</a>
    get_url_thread_list=[]
    for front_fname in front_base_fname_list:

        ## get date of front_fname
        m=re.search("(\d{4})-(\d{2})-(\d{2})", front_fname)
        day=m.group(3)
        month=m.group(2)
        year=m.group(1)
        
        front_fd=open(front_fname, "r")
        lines = front_fd.readlines()
        front_fd.close()
        front_url_tmp=[]

        for l in lines:
            pattern="archives-du-monde/"+day+"-"+month+"-"+year+"\/(\d+)"
            m=re.findall(pattern,l)
            if m:
                for e in m:
                    front_url_tmp.append("https://www.lemonde.fr/archives-du-monde/"+day+"-"+month+"-"+year+"/"+e+"/")
        front_url_tmp=list(set(front_url_tmp))
        front_url_tmp.sort()
        
        for u in front_url_tmp:
            front_url=u
            index=re.search("\/(\d+)\/",front_url).group(1)
            front_fname = front_dir + "/front_" + year + "-" + month + "-" + day + "_" + index + ".html"
            if( (not os.path.exists(front_fname)) or (os.path.getsize(front_fname)<=front_fname_min_size) ):
                print(front_url)
                print(front_fname)
                get_url_thread_list.append(GetUrlThread(front_url, front_fname))


    ## send requests
    nb_req_max=97
    for i in range(0, len(get_url_thread_list), nb_req_max):
         get_url_thread_list_sub=get_url_thread_list[i:i + nb_req_max]
         for m in get_url_thread_list_sub:
             m.start()
         print("")
         for m in get_url_thread_list_sub:
             m.join()


