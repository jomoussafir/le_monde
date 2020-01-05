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
art_txt_dir = "articles_txt"




raw_fname_min_size=50000


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

    ## make art_txt_dir if it does not exist
    if not os.path.isdir(art_txt_dir):
        pathlib.Path(art_txt_dir).mkdir(parents=True, exist_ok=True)

    
    get_art_thread_list=[]
    url_fname_list=list(set(glob.glob("url/url_*.html")))
    url_fname_list.sort()
    for f in url_fname_list:
        print(f)
        m=re.search("(\d{4})-(\d{2})-(\d{2})",f)
        if m:
            url_fd=open(f,"r")
            lines=url_fd.readlines()
            url_fd.close()

            
            d=datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            d_str = d.strftime("%Y\/%m\/%d")

            art_dir_sub = art_dir + "/" + d.strftime("%Y-%m-%d")
            art_txt_dir_sub = art_txt_dir + "/" + d.strftime("%Y-%m-%d")

            ## make art_dir_sub if it does not exist
            if not os.path.isdir(art_dir_sub):
                pathlib.Path(art_dir_sub).mkdir(parents=True, exist_ok=True)

            ## make art_txt_dir_sub if it does not exist
            if not os.path.isdir(art_txt_dir_sub):
                pathlib.Path(art_txt_dir_sub).mkdir(parents=True, exist_ok=True)
            
            for l in lines:
                l=l.rstrip()
                m=re.search("www.lemonde.fr\/.*\/article/"+d_str+"/(.*?html)", l)
                if m:
                    art_url=l
                    art_fname=art_dir_sub+"/"+m.group(1)
                    art_txt_fname=art_txt_dir_sub+"/"+m.group(1)
                    if not os.path.exists(art_txt_fname):
                        get_art_thread_list.append(GetUrlThread(art_url, art_fname))
                    
    
    ## send requests
    nb_req_max=20
    txt_pattern="<p class=\"article__paragraph \">(.*?)<\/p>"
    for i in range(0, len(get_art_thread_list), nb_req_max):
        
        ## get articles
        get_art_thread_list_sub=get_art_thread_list[i:i + nb_req_max]

        print(datetime.datetime.now().strftime("%H:%M:%S"))
        
        for m in get_art_thread_list_sub:
            print(m.fname)

            
        for m in get_art_thread_list_sub:
            m.start()
        print("")
        for m in get_art_thread_list_sub:
            m.join()



            
        ## parse articles
        for m in get_art_thread_list_sub:
            art_fname = m.fname
            if os.path.exists(art_fname):
                fd=open(art_fname,"r")
                lines = fd.readlines()
                fd.close()

                art_txt_fname = re.sub(art_dir,art_txt_dir, art_fname)
                art_txt_fd = open(art_txt_fname, "w")
                for l in lines:
                    m=re.findall(txt_pattern, l)
                    if m:
                        art_txt_fd.write("\n".join(m))
                art_txt_fd.close()

                os.remove(art_fname)

        ## sys.exit(0)


