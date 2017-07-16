#!/usr/bin/env python3
"""
This program de-duplicates MyMemory files based on the changedate time stamp.
Author: Ulrich Germann
(c) 2017 University of Edinburgh
License: LGPL2
"""

import sys, os, re, gzip, html
from bs4 import BeautifulSoup as BS
from argparse import ArgumentParser 
from datetime import datetime
from collections import defaultdict
import xml
from lxml import etree 

D = defaultdict(dict)
global srclang

def unescape(text):
    """
    recursive de-escaping of HTML escapes, because sometimes text is doubly escaped.
    """
    ret = html.unescape(text)
    while ret != text:
        text = ret
        ret = html.unescape(ret)
        pass
    return ret
    
# from: https://gist.github.com/Sukonnik-Illia/7419f0a1f50530ba30e5
def fast_iter(context, process, *args, **kwargs):
    """
    Iteration that removes processed elements after processing, to keep
    memory consumption down. Otherwise, incremental parsing will still build
    the entire document tree.
    """
    ctr = 0
    for event, elem in context:
        process(elem, *args, **kwargs)
        ctr += 1
        if ctr % 10000 == 0:
            sys.stderr.write("%d K units processed.\n"%(ctr/1000))
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
            pass
        pass
    del context
    return

class Chunk:
    """
    Corresponds to an TMX TUV node.
    """
    def __init__(self,node):
        for k,v in node.attrib.items():
            setattr(self,k,v)
        self.lang = node.attrib['{http://www.w3.org/XML/1998/namespace}lang']
        self.text = unescape(node[0].text) if len(node) and node[0].text else ""
        return
    
class TranslationUnit:
    def __init__(self,node):
        global srclang
        for k,v in node.attrib.items():
            setattr(self,k,v)
        self.tuid = int(self.tuid)
        self.changedate = datetime.strptime(self.changedate,"%Y%m%dT%H%M%SZ")
        self.creationdate = datetime.strptime(self.creationdate,"%Y%m%dT%H%M%SZ")
        self.segs = {}
        for child in node:
            if child.tag == 'prop':
                 if child.attrib['type'] == 'tda-type':
                    self.domain = child.text.strip()
                    pass
            elif child.tag == 'tuv':
                child = Chunk(child)
                if child.lang[:len(srclang)] == srclang:
                    srclang = child.lang
                    self.src = child
                else:
                    self.trg = child
                    pass
                pass
            pass
        return
    def __hash__(self):
        return hash(self.src.text)
    def __eq__(self,other):
        return self.src.text == other.src.text
    def __cmp__(self,other):
        return cmp(self.src.text, other.src.text)
    pass # end of class
                 
def process_tu(elem):
    tu2 = TranslationUnit(elem)
    if tu2.src == "" or tu2.trg == "":
        return
    tu1 = D[tu2.domain].setdefault(tu2,tu2)
    if tu1.changedate < tu2.changedate:
        # We leave tu1 in the dictionary and update only what we want
        # changed, so that we don't have to remove it and then insert
        # tu2. We also want to later sort things in order of first
        # occurrence, so we keep the original tuid.
        # print("old: {:4d} {}".format(tu1.tuid, tu1.trg.text))
        # print("new: {:4d} {}".format(tu2.tuid, tu2.trg.text))
        tu1.trg.text = tu2.trg.text
        tu1.changedate = tu2.changedate
        pass
    return

if __name__ == "__main__":
    a = ArgumentParser()
    a.add_argument("--src",type=str,help="source languages", required=True,dest="srclang")
    a.add_argument("input", nargs='+', help="Input TMX file(s)")
    a.add_argument("-o", help="output dir", default="-", dest="odir")
    a.add_argument("-z",dest="gzip",action="store_true", help="output dir",default=False)

    global srclang 
    opts = a.parse_args(sys.argv[1:])
    srclang = opts.srclang

    for ifile in opts.input:
        sys.stderr.write("Processing %s\n"%ifile)
        context = etree.iterparse(ifile, events=('end',),tag='tu')
        fast_iter(context, process_tu)
    
        for domain,tmx in D.items():
            tunits = sorted(tmx, key=lambda x: x.tuid)
            if opts.odir == "-":
                for tu in tunits:
                    print("[{}] {:4d} {}".format(domain,tu.tuid, tu.src.text))
                    print("[{}] {:4d} {}".format(domain,tu.tuid, tu.trg.text))
                    print()
            else:
                # create subdirectory for domain
                try:
                    os.makedirs(opts.odir+"/"+domain)
                except:
                    pass
                # create output file pattern
                obase  = "%s/%s/"%(opts.odir,domain)
                obase += re.sub(r'.tmx(?:.gz)?', '', os.path.basename(ifile))
                obase += "_%s"%(domain)
                if opts.gzip:
                    out1 = gzip.open("%s.%s.gz_"%(obase,tunits[0].src.lang),'w')
                    out2 = gzip.open("%s.%s.gz_"%(obase,tunits[0].trg.lang),'w')
                else:
                    out1 = open("%s.%s_"%(obase,tunits[0].src.lang),'w')
                    out2 = open("%s.%s_"%(obase,tunits[0].trg.lang),'w')
                for tu in tunits:
                    print(tu.src.text, file=out1)
                    print(tu.trg.text, file=out2)
                # rename temporary files after completion
                os.rename(out1.name, out1.name[:-1])
                os.rename(out2.name, out2.name[:-1])
                pass # end writing to files
            pass # end loop over domains
        pass # end for ifile in opts.inout
    pass # end if __name__ == ....



    
