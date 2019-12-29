import re
import os,sys
import glob
import datetime
import pathlib


le_monde_base_url="https://www.lemonde.fr/archives-du-monde/"

def date_seq(start_date, end_date):
	date_list=[]
	new_date=start_date
	while new_date <= end_date:
		date_list.append(new_date)
		new_date=new_date + datetime.timedelta(days = 1)
	return(date_list)


start_date = datetime.datetime(2019, 10, 1)
end_date = datetime.datetime(2019, 11, 1)
date_list = date_seq(start_date, end_date)

toc_dir="toc"
content_base_dir="content"

## get raw html page for each day
## and extract article urls
get_url=True
## get_url=False
if get_url:
					
	if not os.path.isdir(toc_dir):
		os.mkdir(toc_dir)
		
	for d in date_list:
		url=le_monde_base_url + d.strftime("%d-%m-%Y/")
		print("get "+ url)
		raw_fname =  toc_dir + "/raw_" + d.strftime("%Y-%m-%d") + ".html"
		cmd = "curl -s --cookie cookies.txt " + url + " > " + raw_fname
		
		os.system(cmd)
		
		raw_fd=open(raw_fname, "r")
		raw_lines = raw_fd.readlines()
		raw_fd.close()
		
		url_fname=toc_dir + "/url_" + d.strftime("%Y-%m-%d") + ".html"
		url_fd=open(url_fname, "w")		

		for l in raw_lines:
			pattern="https:\/\/www.lemonde.fr\/.*?html"
			m = re.findall(pattern, l)
			if m:
				for e in m:
					if re.search("article\/"+d.strftime("%Y/%m/%d"),e):
						if not re.search("<",e):
							url_fd.write(e+"\n")

		url_fd.close()


art_base_dir = "articles"

## for each url_yyyymmdd.html
## grep article url
## fetch article.html
get_art=True
## get_art=False
if get_art:
	for d in date_list:
		art_tmp_dir = art_base_dir + "/" + d.strftime("%Y-%m-%d") + "_tmp"
		print("get "+art_tmp_dir, end="",flush=True)

		if not os.path.isdir(art_tmp_dir):
			pathlib.Path(art_tmp_dir).mkdir(parents=True, exist_ok=True)

		## read url file for given date
		url_fname=toc_dir + "/url_" + d.strftime("%Y-%m-%d") + ".html"
		url_fd=open(url_fname, "r")
		url_list=[url.rstrip() for url in url_fd.readlines()]
		url_fd.close()		


		d_str = d.strftime("%Y\/%m\/%d")
		pattern = "www.lemonde.fr\/.*\/article/"+d_str+"/(.*?html)"
		for url in url_list:
			print(".", end=".",flush=True)
			m_art_name=re.search(pattern, url)
			if m_art_name:
				art_tmp_fname = art_tmp_dir + "/" + m_art_name.group(1)
				cmd = "curl -s --cookie cookies.txt " + url + " > " + art_tmp_fname
				os.system(cmd)
		print("")


## extract text from each article page
parse_art=True	
## parse_art=False
if parse_art:
	txt_pattern="article__paragraph.*"
	txt_pattern="<p class=\"article__paragraph \">(.*?)<\/p>"
	for d in date_list:
		art_tmp_dir = art_base_dir + "/" + d.strftime("%Y-%m-%d") + "_tmp"
		art_dir = art_base_dir + "/" + d.strftime("%Y-%m-%d") 

		print("parse "+art_tmp_dir)

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
		print(cmd)
		os.system(cmd)



