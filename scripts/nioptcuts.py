#!/usr/bin/env python
from __future__ import (print_function, division, unicode_literals, absolute_import)
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import argparse
from astropy import log
from nicer.values import *
from astropy.table import Table, vstack
import astropy.units as u
from pint.eventstats import hm,z2m


# Python 2 (xrange) and Python 3 (range) compatibility
try:
    xrange
except NameError:
    xrange = range


def cached_hm(mask):
    nph = mask.sum()
    if nph == 0:
        return 0
    s = (cached_hm._cache[...,mask].sum(axis=2)**2).sum(axis=1)
    return ((2./nph)*np.cumsum(s)-4*np.arange(0,cached_hm._cache.shape[0])).max()

def cached_zm(mask):
    nph = mask.sum()
    if nph == 0:
        return 0
    s = (cached_zm._cache[...,mask].sum(axis=2)**2).sum()
    return (2./nph)*s

parser = argparse.ArgumentParser(description="Read event file with phase and optimize cuts")
parser.add_argument("evfiles", help="Name of event files to process", nargs='+')
parser.add_argument("--noplot", help="Suppress plotting.", action="store_true",default=False)
parser.add_argument("-m","--maxharm", help="Search up to harmonic m; [default=20, H-test]", default=20,type=int)
parser.add_argument("-z","--ztest", help="Use Z-test rather than H-test; this searches with exactly the number of harmonics specified.  m=1 is Rayleigh, m=2 is Z^2_2, etc.", action="store_true",default=False)
parser.add_argument("--min_good_time", help="Ignore files with GTI sum below specified value [default None; unit sec].", default=None,type=float)
args = parser.parse_args()

tlist = []
for fn in args.evfiles:
    log.info('Reading file {0}'.format(fn))
    t = Table.read(fn,hdu=1)
    if len(t) == 0:
        continue
    if args.min_good_time is not None:
        tgti = Table.read(fn,hdu='gti')
        good_time = np.sum(tgti['STOP']-tgti['START'])
        if good_time < args.min_good_time:
            print('Ignoring file {0} with good time {1:0.2f}.'.format(fn,good_time))
            continue
    tlist.append(t)

log.info('Concatenating files')
if len(tlist) == 1:
    etable = tlist[0]
else:
    etable = vstack(tlist,metadata_conflicts='silent')
del tlist

m = args.maxharm
ts_func = cached_zm if  args.ztest else cached_hm
phasesinitial = etable['PULSE_PHASE'].astype(np.float32)
hbest = z2m(phasesinitial,m=m)[-1] if args.ztest else hm(phasesinitial,m=m)
eminbest = 0.0
emaxbest = 100.0
ts_name = "Ztest" if args.ztest else "Htest"
print("Initial {0} = {1}".format(ts_name,hbest))

# assemble cache
cache = np.empty([m,2,len(phasesinitial)],dtype=np.float32)
for i in xrange(m):
    cache[i,0] = np.cos(phasesinitial*(2*np.pi*(i+1)))
    cache[i,1] = np.sin(phasesinitial*(2*np.pi*(i+1)))
cached_hm._cache = cached_zm._cache = cache

emins = np.arange(0.25,4.00,0.02)
for emin in emins:
    emaxs = np.arange(emin+0.10,12.01,0.10)
    for emax in emaxs:
        mask = np.logical_and(etable['PI']*PI_TO_KEV>emin,
            etable['PI']*PI_TO_KEV<emax)
        h = ts_func(mask)
        if h>=hbest:
            hbest=h
            eminbest=emin
            emaxbest=emax


print("Final {0} = {1}".format(ts_name,hbest))
print("Best emin {0} emax {1}".format(eminbest,emaxbest))

if not args.noplot:
    fig,ax = plt.subplots()
    ax.hist(phasesinitial, bins = 32)
    idx = np.where(np.logical_and(etable['PI']*PI_TO_KEV>eminbest,
         etable['PI']*PI_TO_KEV<emaxbest))[0]
    phases = etable['PULSE_PHASE'][idx]
    ax.hist(phases,bins=32)
    ax.text(0.1, 0.1, '{0} = {1:.2f}'.format(ts_name,hbest), transform=ax.transAxes)
    ax.set_ylabel('Counts')
    ax.set_xlabel('Pulse Phase')
    ax.set_title('Pulse Profile')

    plt.show()
