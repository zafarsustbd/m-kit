#!/usr/bin/python
from networkx.readwrite import json_graph
import json
import sys
import traceback
from itertools import groupby
import multiprocessing as mp
import networkx as nx
import pdb
import re
import os
from datetime import datetime, timedelta
from ..inference import ip_to_asn as ip2asn
import constants
from ..inference import ixp as ixp

print "To ensure correct usage, place the extracted Iplane dumps (get from here: http://iplane.cs.washington.edu/data/today/traces_2016_02_27.tar.gz) in ~/data/iplane/. Place the readout file (http://iplane.cs.washington.edu/data/readoutfile) in ~/data/iplane/ and then the APIs will be able to find the data."

def parse_iplane_file(dirName, fName):
    print "Parsing file", fName
    as_paths_dict = {}
    aspath = []
    current_dest = None
    ipRegex = r"((([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])[ (\[]?(\.|dot)[ )\]]?){3}([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5]))"
    parseCommand = "%s %s > %s" % (constants.readOutExec, fName, fName+"-read")
    os.system(parseCommand)
    with open(fName+"-read") as fi:
        for line in fi:
            if 'destination' in line:
                match = re.search(ipRegex, line)
                if match:
                    # Add previous AS path to dictionary
                    if current_dest and aspath and current_dest in as_paths_dict:
                        aspath = [k for k,g in groupby(aspath)]
                        as_paths_dict[current_dest].append(aspath)
                    elif current_dest and aspath:
                        aspath = [k for k,g in groupby(aspath)]
                        as_paths_dict[current_dest] = [aspath]
                    dest = match.group(0)
                    ixp_match = ixp.ixp_radix.search_best(dest)
                    if ixp_match:
                        continue
                    asn = ip2asn.ip2asn_bgp(dest)
                    if asn:
                        aspath = []
                        current_dest = asn
            elif current_dest:
                # If current destination is not set, what could we even gather a path towards?
                match = re.search(ipRegex, line)
                if match:
                    hop = match.group(0)
                    ixp_match = ixp.ixp_radix.search_best(hop)
                    if ixp_match:
                        continue
                    asn = ip2asn.ip2asn_bgp(hop)
                    if asn:
                        aspath = aspath + [asn]
                    
    return as_paths_dict

def get_iplane_graphs(dates):
    dir_files = {}
    for date in [dates]:
        dirName = "traces_" + date 
        dir_path = os.path.join(constants.IPLANE_DATA, dirName)
        files = [x for x in os.listdir(dir_path) if
                 os.path.isfile(os.path.join(dir_path, x))]
        files = [os.path.join(dir_path, f) for f in files]
        dir_files[ dirName ] = files
    
    results = []
    pool = mp.Pool(processes=32)
    for dName, files in dir_files.iteritems():
        for f in files:
            results.append( pool.apply_async( parse_iplane_file, args=(dName,f) ) )

    pool.close()
    pool.join()
    output = [ p.get() for p in results ]
    dest_based_as_paths = {}
    for op in output:
        for dst_asn, aspaths in op.iteritems():
            if not dst_asn in dest_based_as_paths:
                dest_based_as_paths[dst_asn] = aspaths
            else:
                dest_based_as_paths[dst_asn].extend(aspaths)
    return dest_based_as_paths

