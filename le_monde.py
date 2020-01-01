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
    ## toc/raw_yyyy-mm-dd.html
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
get_raw_url_sub=False
if get_raw_url_sub:
    
    ## get base raw_base_file_list
    ## toc/raw_yyyy-mm-dd.html
    raw_base_fname_list = list(set(glob.glob(raw_dir + "/raw_*.html")))
    raw_base_fname_list.sort()
    for f in raw_base_fname_list:
        m=re.search("raw_(\d{4})-(\d{2})-(\d{2})_(\d+)\.html",f)
        if m:
            print(f)
            raw_base_fname_list.remove(f)
    
    ## href="https://www.lemonde.fr/archives-du-monde/13-12-2019/2/
    get_url_thread_list=[]
    for raw_fname in raw_base_fname_list:
        raw_fd=open(raw_fname, "r")
        lines = raw_fd.readlines()
        raw_fd.close()
        for l in lines:
            m=re.search("https:\/\/www\.lemonde\.fr\/archives-du-monde\/(\d{2})-(\d{2})-(\d{4})\/(\d+)",l)
            if(m):
                d=datetime.datetime(int(m.group(3)),int(m.group(2)),int(m.group(1)))
                raw_url="https://www.lemonde.fr/archives-du-monde/"+m.group(1)+"-"+m.group(2)+"-"+m.group(3)+"/"+m.group(4)+"/"
                raw_fname = raw_dir + "/raw_" + d.strftime("%Y-%m-%d") + "_" + m.group(4) + ".html"

                if( (not os.path.exists(raw_fname)) or (os.path.getsize(raw_fname)<=raw_fname_min_size) ):
                    print(raw_url)
                    print(raw_fname)
                    get_url_thread_list.append(GetUrlThread(raw_url, raw_fname))
    
    ## send requests
    nb_req_max=10
    for i in range(0, len(get_url_thread_list), nb_req_max):
        get_url_thread_list_sub=get_url_thread_list[i:i + nb_req_max]
        for m in get_url_thread_list_sub:
            m.start()
        print("")
        for m in get_url_thread_list_sub:
            m.join()

            
##################################################################################
## read all raw files and extract article urls
##################################################################################

get_url=True
get_url=False
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
        raw_fname_list_tmp=[]
        for f in raw_fname_list:
            if re.search(d_str,f):
                raw_fname_list_tmp.append(f)
        
        
        url_fname = url_dir + "/url_" + d.strftime("%Y-%m-%d") + ".html"
        url_fd=open(url_fname, "w")
        for f in raw_fname_list_tmp:
            print(f)
            raw_fd=open(f,"r")
            raw_lines=raw_fd.readlines()
            raw_fd.close()
            for l in raw_lines:
                
                m = re.findall("https:\/\/www.lemonde.fr\/.*?html", l)
                if m:
                    for e in m:
                        if re.search("article\/"+d.strftime("%Y/%m/%d"),e):
                            if not re.search("<",e):
                                url_fd.write(e+"\n")
                                
        url_fd.close()


##################################################################################
## fetch articles from url contained in url/url_yyyy_mm_dd.html
##################################################################################


## for each url/url_yyyymmdd.html
## fetch article.html
get_art=True
## get_art=False
if get_art:
    
    ## make art_dir if it does not exist
    if not os.path.isdir(art_dir):
        pathlib.Path(art_dir).mkdir(parents=True, exist_ok=True)

    
    get_art_thread_list=[]
    url_fname_list=list(set(glob.glob("url/url_*.html")))
    url_fname_list.sort()
    for f in url_fname_list[:5]:
        print(f)

        m=re.search("(\d{4})-(\d{2})-(\d{2})",f)
        if m:
            url_fd=open(f,"r")
            lines=url_fd.readlines()
            url_fd.close()

            d=datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            d_str = d.strftime("%Y\/%m\/%d")
            
            for l in lines:
                l=l.rstrip()
                m=re.search("www.lemonde.fr\/.*\/article/"+d_str+"/(.*?html)", l)
                if m:
                    art_url=l
                    art_fname=art_dir+"/"+m.group(1)
                    #print(art_url)
                    print(art_fname)
                    get_art_thread_list.append(GetUrlThread(art_url, art_fname))
                    

    ## send requests
    nb_req_max=10
    for i in range(0, len(get_art_thread_list), nb_req_max):
        get_art_thread_list_sub=get_art_thread_list[i:i + nb_req_max]
        for m in get_art_thread_list_sub:
            m.start()
        print("")
        for m in get_art_thread_list_sub:
            m.join()




            
##################################################################################
## extract text from each article page
##################################################################################
parse_art=True
parse_art=False
if parse_art:
    txt_pattern="article__paragraph.*"
    txt_pattern="<p class=\"article__paragraph \">(.*?)<\/p>"
    for d in date_list:
        art_tmp_dir=art_base_dir + "/" + d.strftime("%Y-%m-%d") + "_tmp"
        art_dir=art_base_dir + "/" + d.strftime("%Y-%m-%d")

        ##print("parse "+art_tmp_dir)

        if not os.path.isdir(art_dir):
            pathlib.Path(art_dir).mkdir(parents=True, exist_ok=True)

        ## list files in art_tmp_dir
        art_tmp_list = glob.glob(art_tmp_dir + "/*.html")
        for f in art_tmp_list:
            fd=open(f,"r")
            lines = fd.readlines()
            fd.close()

            art_fname = re.sub(art_tmp_dir,art_dir, f)
            art_fd = open(art_fname, "w")
            for l in lines:
                m=re.findall(txt_pattern, l)
                if m:
                    art_fd.write("\n".join(m))
            art_fd.close()

        cmd="rm -fr " + art_tmp_dir
        ## print(cmd)
        os.system(cmd)

