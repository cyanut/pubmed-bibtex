from urllib.request import urlopen
from urllib.parse import urlencode
import json
from pyP2B import getPubmedReference as pmid2bib
from pprint import pprint
from lxml import etree

PM_BASE = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
PM_SEARCH = '{}{}'.format(PM_BASE, 'esearch.fcgi')
PM_DOWNLOAD = '{}{}'.format(PM_BASE, 'efetch.fcgi')

def pm_search(q, n):
    data = {'db':'pubmed', 'retmax':n, 'retmode':'json', 'term':q}
    res_html = urlopen(PM_SEARCH, data=urlencode(data).encode('utf8')).read()
    return json.loads(res_html.decode('utf8'))['esearchresult']['idlist']

def pm_download(id_list):
    data = {'db':'pubmed', 'retmode':'xml', 'id':",".join([str(x) for x in id_list]), 'rettype':'medline'}
    res_html = urlopen(PM_DOWNLOAD, data=urlencode(data).encode('utf8')).read()
    #return json.loads(res_html.decode('utf8'))
    tree = etree.fromstring(res_html)
    authors = ""
    authl = tree.xpath('/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/AuthorList/Author/LastName')
    authi = tree.xpath('/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/AuthorList/Author/Initials')
    authf = tree.xpath('/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/AuthorList/Author/ForeName')    
    for i in range(len(authl)):
        lastname = authl[i].text
        initials = ""
        for j in range(len(authi[i].text)):
            initials = initials + str(authi[i].text)[j]
            initials = initials + "."
        if i > 0:
            authors = "%s and %s, %s" % (authors, lastname, initials)
        else: #i = 0
            authors = "%s, %s" % (lastname, initials)

    return authors

def loop(f):
    while True:
        q = input("query>")
        idlist = pm_search(q, n=1)
        if len(idlist) == 0:
            print('No matching result')
            continue
        else:
            ref = pm_download(idlist)
            
            pprint(ref)


if __name__ == "__main__":
    import sys
    print(pm_download(pm_search('amygdala', 1)))
    #loop(None)

