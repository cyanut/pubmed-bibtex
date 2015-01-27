from urllib.request import urlopen
from urllib.parse import urlencode
import json
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
    print(res_html.decode('utf8'))
    #return json.loads(res_html.decode('utf8'))
    tree = etree.fromstring(res_html)
    bib_ref = []
    for article_tree in tree.xpath('/PubmedArticleSet/PubmedArticle'):
        authors = []
        authl = article_tree.xpath('MedlineCitation/Article/AuthorList/Author/LastName')
        authf = article_tree.xpath('MedlineCitation/Article/AuthorList/Author/ForeName')    
        for lastname, firstname in zip(authl, authf):
            authors.append('{}, {}'.format(lastname.text, firstname.text))
        authors = " and ".join(authors)

        title = article_tree.xpath('MedlineCitation/Article/ArticleTitle')[0].text
        if title[-1] == '.':
            title = title[:-1]
        journal_tree = article_tree.xpath('MedlineCitation/Article/Journal')[0]
        year = journal_tree.xpath('JournalIssue/PubDate/Year')[0].text
        bibtexid = authl[0].text.lower() + year[-2:]
        journal = journal_tree.xpath('Title')[0].text

        volume = journal_tree.xpath('JournalIssue/Volume')[0].text

        issue = journal_tree.xpath('JournalIssue/Issue')
        if issue:
            issue = issue[0].text
        else:
            issue = None
        pages = article_tree.xpath('MedlineCitation/Article/Pagination/MedlinePgn')
        pages = pages[0].text.replace('-','--')
        pmid = article_tree.xpath('MedlineCitation/PMID')[0].text

        idlist = article_tree.xpath('PubmedData/ArticleIdList/ArticleId')
        doi = None
        if idlist:
            for id_node in idlist:
                if id_node.attrib['IdType'] == 'doi':
                    doi = id_node.text
        keywords = [node.text for node in article_tree.xpath('MedlineCitation/KeywordList/Keyword')]
        keywords = ",".join(keywords)

        result = '''
@article {{{},
    author ={{{}}},
    title = {{{}}},
    year = {{{}}},
    journal={{{}}},
    volume={{{}}},'''.format(bibtexid, authors, title, year, journal, volume)
        if issue:
            result = '''{}
    number={{{}}},'''.format(result, issue)
        result = '''{}
    pages={{{}}},
    pmid={{{}}},'''.format(result, pages, pmid)
        if doi:
            result = '''{}
    doi={{{}}},'''.format(result, doi)
        result = '''{}
    keywords={{{}}}
}}'''.format(result, keywords)
        
        bib_ref.append(result)

    return "\n".join(bib_ref)

def loop(f):
    while True:
        q = input("query>")
        if q == "bye":
            break
        idlist = pm_search(q, n=1)
        if len(idlist) == 0:
            print('No matching result')
            continue
        else:
            ref_text = pm_download(idlist)
            f.write(ref_text)
            f.flush()
            print(ref_text)

if __name__ == "__main__":
    import sys
    f = open(sys.argv[1], 'a')
    loop(f)
    f.close()

