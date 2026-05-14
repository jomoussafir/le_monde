The project is about downloading papers from the newspaper "le monde" since 1944
from the archive web site : https://www.lemonde.fr/archives-du-monde/
convert them into a readable format like txt and store them into folders 
organised by year, month, day like yyyy/mm/dd/title.txt
It may be necessary to store the html versions as well.

The papers links are accessible under urls formed like : 

https://www.lemonde.fr/archives-du-monde/07-02-2026/
https://www.lemonde.fr/archives-du-monde/07-02-2026/2/
https://www.lemonde.fr/archives-du-monde/07-02-2026/3/

and the papers are accssible under urls formed like
https://www.lemonde.fr/international/article/2026/02/07/<title>.html

adapt /Users/msfr/Documents/le_monde/fetch_test.py and make 

- a script that extract all paper urls and store them in a url folder, the urls from dd-mm-yyyy should be stored in url/yyyymmdd.txt

- a script that will look for the urls contained in url/yyyymmdd.txt and actually fetch the html and store it in html/yyyy/mm/dd/<title>.html where <title> is the title of the paper


