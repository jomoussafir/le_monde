import html
import glob


fname_list=glob.glob("articles_txt/*html")

for f in fname_list[-1:]:
    fd=open(f,'r')
    lines=fd.readlines()
    fd.close()

    for l in lines:
        print(html.unescape(l))
