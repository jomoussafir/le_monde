
Scrap Le Monde archives


get_front_url.py
================
	- Get all html front pages for each date and store them in
		front/front_yyyy-mm-dd.html
	- Re-run several times to get everything - not all requests are filled

get_front_url_sub.py
================
	- Get all html front sub-pages for each date and store them in
		front/front_yyyy-mm-dd_index.html
	- Re-run several times to get everything - not all requests are filled

extract_url.py
==============
	- Extract article urls from each front html page and store them in
		url/url_yyyy-mm-dd.html

get_art.py
==========
	- Read all url_yyyy-mm-dd.html files in the url directory and make a list
	  containing all urls
	- Fetch all urls from this url list and extract
	  the corresponding text to articles_txt/yyyy-mm-dd/xxx.html



	T
