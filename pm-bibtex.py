from urllib.request import urlopen
from urllib.parse import urlencode
import json
from lxml import etree
import argparse
import logging
import requests
from bs4 import BeautifulSoup
import os

PM_BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
PM_SEARCH = '{}{}'.format(PM_BASE, 'esearch.fcgi')
PM_DOWNLOAD = '{}{}'.format(PM_BASE, 'efetch.fcgi')
SCIHUB_URL = 'http://sci-hub.cc/'
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:50.0) Gecko/20100101 Firefox/50.0',
          }

def pm_search(q, n):
    data = {'db':'pubmed', 'retmax':n, 'retmode':'json', 'term':q}
    res_html = urlopen(PM_SEARCH, data=urlencode(data).encode('utf8')).read()
    return json.loads(res_html.decode('utf8'))['esearchresult']['idlist']

def pm_download(id_list):
    data = {'db':'pubmed', 'retmode':'xml', 'id':",".join([str(x) for x in id_list]), 'rettype':'medline'}
    res_html = urlopen(PM_DOWNLOAD, data=urlencode(data).encode('utf8')).read()
    logging.debug(res_html.decode('utf8'))
    #return json.loads(res_html.decode('utf8'))
    tree = etree.fromstring(res_html)
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
        journal = journal_tree.xpath('Title')[0].text.title()

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
        
        return {'bibtexid':bibtexid,
                'authors':authors,
                'title':title,
                'year': year,
                'journal': journal,
                'volume': volume,
                'issue': issue,
                'pages': pages,
                'pmid': pmid,
                'doi': doi,
                'keywords': keywords,
                }

def fmt_pm_result(pm_res):
    fields = ['bibtexid',
                'authors',
                'title',
                'year',
                'journal',
                'volume',
                'issue',
                'pages',
                'pmid',
                'doi',
                'keywords',
              ]
    result = '''
@article {{{},
author ={{{}}},
title = {{{}}},
year = {{{}}},
journal={{{}}},
volume={{{}}},'''.format(*[pm_res[i] for i in fields[:6]])
    if pm_res['issue']:
        result = '''{}
number={{{}}},'''.format(result, pm_res['issue'])
    result = '''{}
pages={{{}}},
pmid={{{}}},'''.format(result, pm_res['pages'], pm_res['pmid'])
    if pm_res['doi']:
        result = '''{}
doi={{{}}},'''.format(result, pm_res['doi'])
    result = '''{}
keywords={{{}}}
}}'''.format(result, pm_res['keywords'])
    

    return result


def fetch(doi):
    logger.debug('requesting {}'.format(SCIHUB_URL + doi))
    res = requests.get(SCIHUB_URL + doi, headers=HEADERS, verify=False)
    s = BeautifulSoup(res.content, 'html.parser')
    iframe = s.find('iframe')
    u = None
    if iframe:
        u = iframe.get('src')
    if u:
        try:
            logger.debug('requesting {}'.format(u))
            res = requests.get(u, headers=HEADERS, verify=False)
            if res.headers['Content-Type'] == 'application/pdf':
                return res.content
            else:
                print(res)
        except requests.exceptions.RequestException as e:
            logging.error("Cannot fetch pdf with DOI: {}".format(doi))
    logger.error("Error fetching {}".format(doi))

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

def get_args():
    parser = argparse.ArgumentParser(\
            description = "search pubmed and format as latex bibliography")
    parser.add_argument("query", help="query string")
    parser.add_argument("-b", "--bib-file", help="latex bibliography file")
    parser.add_argument("-v", "--verbose", action='count', help="verbose level", default=0)
    parser.add_argument("-q", "--quiet", action='count', help="quiet level", default=0)
    parser.add_argument("-i", "--interactive", action="store_true", help="confirm before write, only useful with -b")
    parser.add_argument("-d", "--pdf-directory", help="directory to store pdf")
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    logger = logging.getLogger()
    logging_level = logging.INFO + 10*args.quiet - 10*args.verbose
    logger.setLevel(logging_level)
    idlist = pm_search(args.query, n=1)

    if len(idlist) == 0:
        logging.error("No matching result")
        quit()
    
    pm_res = pm_download(idlist)
    ref_text = fmt_pm_result(pm_res)
    logging.info(ref_text)

    if args.bib_file:
        if args.pdf_directory:
            doi = pm_res['doi']
            logging.info("Downloading {}".format(doi)) 
            pdf = fetch(doi) 
            fpath = os.path.join(args.pdf_directory, pm_res['bibtexid']+'.pdf')
            if os.path.exists(fpath):
                logger.error("{} already exist".format(fpath))
                quit()
            else:
                with open(fpath, 'wb') as f:
                    f.write(pdf)
        if args.interactive:
            c = input("Write to bib file? (y/n)")
            c = c.strip()
            if len(c) == 1 and (c == 'y' or c == 'Y'):
                with open(args.bib_file, 'a') as f:
                    f.write(ref_text)

