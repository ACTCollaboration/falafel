from __future__ import print_function
from pixell import curvedsky as cs, enmap, lensing as enlensing, powspec
from enlib import bench # comment this and any uses of bench if you dont have enlib
import numpy as np
import healpy as hp # needed only for isotropic filtering and alm -> cl, need to make it healpy independent
from orphics import io,cosmology,lensing,maps,stats,mpi
from falafel import qe
import os,sys


lmax = int(sys.argv[1]) # cmb ellmax
Nsims = int(sys.argv[2])


comm = mpi.MPI.COMM_WORLD
rank = comm.Get_rank()
numcores = comm.Get_size()
Njobs = Nsims
num_each,each_tasks = mpi.mpi_distribute(Njobs,numcores)
if rank==0: print ("At most ", max(num_each) , " tasks...")
my_tasks = each_tasks[rank]


res = 1.0 # resolution in arcminutes
mlmax = lmax + 250 # lmax used for harmonic transforms



# load theory
camb_root = "data/cosmo2017_10K_acc3"
theory = cosmology.loadTheorySpectraFromCAMB(camb_root,get_dimensionless=False)

# ells corresponding to modes in the alms
ells = np.arange(0,mlmax,1)
    
lpfile = "/gpfs01/astro/workarea/msyriac/data/sims/msyriac/lenspix/cosmo2017_lmax_fix_lens_lmax_%d_qest_lmax_%d_AL.txt" % (lmax+2000,lmax)
lpls,lpal = np.loadtxt(lpfile,unpack=True,usecols=[0,1])
lpal = lpal / (lpls) / (lpls+1.)

dh_nls = np.nan_to_num(lpal*(lpls*(lpls+1.))**2./4.)
dh_als = np.nan_to_num(dh_nls * 2. / lpls /(lpls+1))
Al = dh_als
Al = maps.interp(lpls,dh_als)(ells)
Nl = maps.interp(lpls,dh_nls)(ells)
Al[ells<1] = 0
Nl[ells<1] = 0

shape,wcs = enmap.fullsky_geometry(res=np.deg2rad(res/60.),proj="car")
#sim_location = "/global/cscratch1/sd/engelen/simsS1516_v0.3/data/"
#ksim_location = "/global/cscratch1/sd/dwhan89/shared/act/simsS1516_v0.3/data/"

sim_location = "/gpfs01/astro/workarea/msyriac/data/sims/alex/v0.3/"
ksim_location = "/gpfs01/astro/workarea/msyriac/data/sims/alex/v0.3/"


#bin_edges = ls#np.logspace(np.log10(2),np.log10(lmax),100)
#bin_edges = np.linspace(2,lmax,300)
#binner = stats.bin1D(bin_edges)

mstats = stats.Stats(comm)

for task in my_tasks:


    sim_index = task+1
    assert sim_index>0

    sindex = str(sim_index).zfill(5)
    if rank==0: print("Loading lensed map...")
    Xmap = enmap.read_map(sim_location+"fullskyLensedMapUnaberrated_T_%s.fits" % (sindex))
    Xmap = enmap.enmap(Xmap,wcs)
    assert Xmap.shape==shape

    ### DO FULL SKY RECONSTRUCTION
    if rank==0: print("Calculating unnormalized full-sky kappa...")
    lcltt = theory.lCl('TT',range(lmax))
    ukappa_alm = qe.qe_tt_simple(Xmap,lcltt=lcltt,nltt_deconvolved=0.,lmin=2,lmax=lmax,mlmax=mlmax)[0]
    del Xmap
    kappa_alm = hp.almxfl(ukappa_alm,Al).astype(np.complex128)
    

    # alms of input kappa
    #ikappa = enmap.read_map(ksim_location+"phi_%s/kappaMap_%s.fits" % (sindex,sindex))
    ikappa = enmap.read_map(ksim_location+"kappaMap_%s.fits" % (sindex))
    ikappa.wcs = wcs
    assert ikappa.shape==shape
    ik_alm = cs.map2alm(ikappa,lmax=mlmax).astype(np.complex128)
    del ikappa

    # cross and auto powers
    cuu = hp.alm2cl(ukappa_alm)
    cui = hp.alm2cl(ik_alm,ukappa_alm)
    cri = hp.alm2cl(ik_alm,kappa_alm)
    crr = hp.alm2cl(kappa_alm)
    cii = hp.alm2cl(ik_alm)

    del kappa_alm
    del ik_alm

    ls = np.arange(len(crr))

    cuu[ls<1] = np.nan
    cui[ls<1] = np.nan
    cri[ls<1] = np.nan
    crr[ls<1] = np.nan
    cii[ls<1] = np.nan


    cents,buu = ls,cuu #binner.binned(ls,cuu)
    cents,bui = ls,cui #binner.binned(ls,cui)
    cents,bri = ls,cri #binner.binned(ls,cri)
    cents,brr = ls,crr #binner.binned(ls,crr)
    cents,bii = ls,cii #binner.binned(ls,cii)

    mstats.add_to_stats("cuu",cuu)

    mstats.add_to_stats("uu",buu)
    mstats.add_to_stats("ui",bui)
    mstats.add_to_stats("ri",bri)
    mstats.add_to_stats("rr",brr)
    mstats.add_to_stats("ii",bii)
    mstats.add_to_stats("diff",(bri-bii)/bii)

    if rank==0: print ("Rank 0 done with task ", task+1, " / " , len(my_tasks))

mstats.get_stats()

if rank==0:

    buu = mstats.stats['uu']['mean']
    bri = mstats.stats['ri']['mean']
    brr = mstats.stats['rr']['mean']
    bii = mstats.stats['ii']['mean']
    diff = mstats.stats['diff']['mean']

    ebuu = mstats.stats['uu']['errmean']
    ebri = mstats.stats['ri']['errmean']
    ebrr = mstats.stats['rr']['errmean']
    ebii = mstats.stats['ii']['errmean']
    ediff = mstats.stats['diff']['errmean']

    pl = io.Plotter(yscale='log',xscale='log')
    pl.add(ells,(theory.gCl('kk',ells)+Nl)/Al**2. ,lw=3,color='k')
    pl.add(ls,mstats.stats['cuu']['mean'],marker="o",label='uxu')
    vsize = mstats.vectors['cuu'].shape[0]
    for i in range(vsize):
        v = mstats.vectors['cuu'][i,:]
        pl.add(ls,v,label='uxu',alpha=0.2,color='C1')
        
    pl.legend()
    pl.done(io.dout_dir+"qe_debug.png")

    
    # plot
    pl = io.Plotter(yscale='log',xscale='log')
    pl.add(ells,theory.gCl('kk',ells),lw=3,color='k')
    pl.add_err(cents,bri,yerr=ebri,ls="none",marker="o",label='rxi')
    pl.add_err(cents,brr,yerr=ebrr,ls="none",marker="o",label='rxr') #!!!
    pl.add_err(cents,bii,yerr=ebii,ls="none",marker="x",label='ixi')
    pl.add(lpls,(lpal*(lpls*(lpls+1.))**2./4.)+theory.gCl('kk',lpls),ls="--")
    pl.add(lpls,lpal*(lpls*(lpls+1.))**2./4.,ls="-.")
    pl.legend()
    pl.done(io.dout_dir+"fullsky_qe_result_%d.png" % lmax)

    pl = io.Plotter()
    pl.add_err(cents,diff,yerr=ediff,ls="-",marker="o")
    pl.hline()
    pl._ax.set_ylim(-0.03,0.03)
    pl._ax.set_xlim(0,lmax)
    pl.done(io.dout_dir+"fullsky_qe_result_diff_%d.png" % lmax)


    pl = io.Plotter(xscale='log')
    pl.add_err(cents,diff,yerr=ediff,ls="-",marker="o")
    pl.hline()
    pl._ax.set_ylim(-0.2,0.2)
    pl._ax.set_xlim(0,lmax)
    pl.done(io.dout_dir+"fullsky_qe_result_diff_%d_log.png" % lmax)
    
