from urllib.request import urlopen
from urllib.parse import urlencode, urlsplit
import json
from lxml import etree
import argparse
import logging
logger = logging.getLogger()
import requests
import os
import time
import numpy as np
from scipy.misc import imread
import matplotlib.pyplot as plt
from io import BytesIO
try:
    from captcha_solver import solver
    solve_captcha = solver("model1k.h5")
except ImportError:
    solve_captcha = None

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

def solve_manual(img):
    plt.imshow(im)
    plt.show()
    captcha = input("Input captcha:")

    return captcha

if solve_captcha is None:
    solve_captcha = solve_manual

def urlbase(url):
    return "{0.scheme}://{0.netloc}/".format(urlsplit(url))

def fetch(doi, solve_captcha=solve_captcha):
    #res = requests.post(SCIHUB_URL, data={'request':doi, 'sci-hub-plugin-check':""}, headers=HEADERS)
    sess = requests.Session()
    sess.headers.update(HEADERS)
    res = sess.post(SCIHUB_URL, data={"request":doi, "sci-hub-plugin-check":""})
    s = etree.HTML(res.content)
    iframe = s.find('.//iframe')
    u = None
    if iframe is not None:
        u = iframe.get('src')
        if u[:2] == "//":
            u = "http:" + u
    if u:
        captcha = None
        print(u)
        logger.debug("getting page from {}".format(u))
        while True:
            try:
                if captcha is None:
                    res = sess.get(u, headers=HEADERS)
                else:
                    res = sess.post(u, data={'captcha_code':captcha}, headers={'Referer':u})
                base_url = urlbase(res.url)
                logging.debug(repr(res.headers))
                logging.debug(repr(res.content[:100]))
                if res.headers['Content-Type'] == 'application/pdf':
                    return u.split("/")[-1], res.content
                else:
                    captcha_page = etree.HTML(res.content)
                    captcha_u = captcha_page.find(".//img[@id='captcha']").get('src')
                    logging.debug("Found captcha, getting {}".format(captcha_u))
                    if captcha_u is not None:
                        captcha_u = requests.compat.urljoin(base_url, captcha_u)
                        logger.debug(captcha_u)
                        captcha_img = sess.get(captcha_u, headers={'Referer':u})

                        logger.debug(repr(captcha_img.headers))
                        logger.debug(len(captcha_img.content))
                        logger.debug(captcha_img.cookies)
                        im = imread(BytesIO(captcha_img.content))
                        captcha = solve_captcha(im)
                        logger.debug('Captcha: {}'.format(captcha))


            except requests.exceptions.RequestException as e:
                logging.error("Cannot fetch pdf with DOI: {}".format(doi))
                break
        logger.error("Error fetching {}".format(doi))
    return (None, None)

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
            _, pdf = fetch(doi) 
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

