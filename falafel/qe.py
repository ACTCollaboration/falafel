from enlib import curvedsky as cs, enmap
import numpy as np
import healpy as hp # needed only for isotropic filtering and alm -> cl, need to make it healpy independent

"""
1. you can use wigner-d gauss-legendre quadrature to calculate norm without evaluating wigner 3j
2. factorization tricks can be used for above
3. TT might not be correct. What is divergence doing to (spin-1?) gradient?

"""

def get_fullsky_res(npix,squeeze=0.8):
    "Slightly squeezed pixel width in radians given npix pixels on the full sky."
    return np.sqrt(4.*np.pi/npix) * squeeze

def gmap2alm(imap,lmax,healpix=False,iter=3):
    """Generic map -> alm for both healpix and rectangular pixels"""
    if not(healpix): 
        assert imap.ndim >= 2
        return cs.map2alm(imap,lmax=lmax)
    else:
        return hp.map2alm(imap,lmax=lmax,iter=iter)


def isotropic_filter_T(imap=None,alm=None,lcltt=None,ucltt=None,
                       nltt_deconvolved=None,tcltt=None,lmin=None,lmax=None,gradient=False):
    if imap is not None:
        imap -= imap.mean()
    if alm is None: alm = cs.map2alm(imap,lmax=lmax)
    if gradient:
        if ucltt is None: ucltt = lcltt
        numer = ucltt
    else:
        numer = 1.
    denom = tcltt if tcltt is not None else lcltt+nltt_deconvolved
    wfilter = np.nan_to_num(numer/denom)
    ells = np.arange(0,wfilter.size,1)
    if lmin is not None: wfilter[ells<lmin] = 0
    wfilter[ells>lmax] = 0
    return hp.almxfl(alm,wfilter)


def gradient_T_map(shape,wcs,alm):
    """
    Given appropriately Wiener filtered temperature map alms,
    returns a real-space map containing the gradient of T.
    """
    omap = enmap.zeros((2,)+shape[-2:],wcs)
    return cs.alm2map(alm,omap,deriv=True,method="cyl") # note that deriv=True gives the scalar derivative of a scalar alm field




def gradient_E_map(alm):
    """
    Given appropriately Wiener filtered E-mode alms,
    returns a real-space map containing the gradient of E.
    """
    pass

def gradient_B_map(alm):
    """
    Given appropriately Wiener filtered B-mode alms,
    returns a real-space map containing the gradient of B.
    """
    pass


def qe_tt_simple(Xmap,Ymap=None,lcltt=None,ucltt=None, \
                 nltt_deconvolved=None,tcltt=None,nltt_deconvolved_y=None,tcltt_y=None,
                 lmin=None,lmax=None,lmin_y=None,lmax_y=None,do_curl=False,mlmax=None,healpix=False,pure_healpix=False):
    """
    Does -div(grad(wX)*wY) where wX and wY are Wiener filtered appropriately for isotropic noise
    from provided X and Y, and CMB and noise spectra.
    Does not normalize the estimator.
    """

    # Set defaults if the high-res map Y is not different from the gradient map X
    if Ymap is None: assert (nltt_deconvolved_y is None) and (tcltt_y is None) and (lmin_y is None) and (lmax_y is None)
    if nltt_deconvolved_y is None: nltt_deconvolved_y = nltt_deconvolved
    if tcltt_y is None: tcltt_y = tcltt
    if lmin_y is None: lmin_y = lmin
    if lmax_y is None: lmax_y = lmax

    # lmax at which harmonic operations are performed
    #if mlmax is None: mlmax = max(lmax,lmax_y) + 250
    #if mlmax is None: mlmax = 2*max(lmax,lmax_y)
    if mlmax is None: mlmax = max(lmax,lmax_y)+250
    if pure_healpix: mlmax = None

    # if healpix, then calculate intermediate CAR geometry
    if healpix:
        npix = Xmap.size
        shape,wcs = enmap.fullsky_geometry(res=get_fullsky_res(npix=npix),proj="car")
    else:
        shape,wcs = Xmap.shape,Xmap.wcs

    # map -> alm
    Xmap -= Xmap.mean()
    iXalm = gmap2alm(Xmap,lmax=mlmax,healpix=healpix)
    del Xmap
    if Ymap is None:
        iYalm = iXalm.copy()
    else:
        Ymap -= Ymap.mean()
        iYalm = gmap2alm(Ymap,lmax=mlmax,healpix=healpix)
    del Ymap

    # filter alms
    Xalm = isotropic_filter_T(alm=iXalm,lcltt=lcltt,ucltt=ucltt,
                              nltt_deconvolved=nltt_deconvolved,tcltt=tcltt,lmin=lmin,lmax=lmax,gradient=True)
    Yalm = isotropic_filter_T(alm=iYalm,lcltt=lcltt,ucltt=ucltt,
                              nltt_deconvolved=nltt_deconvolved_y,tcltt=tcltt_y,lmin=lmin_y,lmax=lmax_y,gradient=False)
    # get kappa
    if pure_healpix:
        from falafel import qehp
        nside = hp.npix2nside(npix)
        return qehp.qe_tt(nside,Xalm,Yalm,mlmax=mlmax,do_curl=do_curl,lmax_x=lmax,lmax_y=lmax_y)
    else:    
        return qe_tt(shape,wcs,Xalm,Yalm,mlmax=mlmax,do_curl=do_curl,lmax_x=lmax,lmax_y=lmax_y)
    
def qe_tt(shape,wcs,Xalm,Yalm,do_curl=False,mlmax=None,lmax_x=None,lmax_y=None):
    """
    Does -div(grad(wX)*wY) where wX_alm and wY_alm are provided as appropriately Wiener filtered alms.
    Does not normalize the estimator.
    """

    # Filters to impose hard ell cuts on output alms
    if (lmax_x is not None) or (lmax_y is not None):
        ells = np.arange(mlmax)
        lxymax = max(lmax_x,lmax_y)
        xyfil = np.ones(mlmax)
        xyfil[ells>lxymax] = 0
    if lmax_x is not None:
        xfil = np.ones(mlmax)
        xfil[ells>lmax_x] = 0
        Xalm = hp.almxfl(Xalm,xfil)
    if lmax_y is not None:
        yfil = np.ones(mlmax)
        yfil[ells>lmax_y] = 0
        Yalm = hp.almxfl(Yalm,yfil)
        
    # Get gradient and high-pass map in real space
    gradT = gradient_T_map(shape,wcs,Xalm)
    highT = enmap.zeros(shape[-2:],wcs)
    highT = cs.alm2map(Yalm,highT,method="cyl")

    # Form real-space products of gradient and high-pass
    py = gradT[0] * highT
    px = gradT[1] * highT

    del gradT
    del highT
    
    # alms of products for divergence
    px -= px.mean()
    py -= py.mean()
    alm_px = cs.map2alm(px,lmax=mlmax)
    alm_py = cs.map2alm(py,lmax=mlmax)
    # if (lmax_x is not None) or (lmax_y is not None):
    #     alm_px = hp.almxfl(alm_px,xyfil)
    #     alm_py = hp.almxfl(alm_py,xyfil)
    
    del px
    #del py

    # divergence from alms
    dpx = enmap.zeros((2,)+shape[-2:],wcs)
    dpx = cs.alm2map(alm_px,dpx,deriv=True,method="cyl")
    del alm_px
    dpxdx = dpx[1]
    if do_curl: dpxdy = dpx[0]
    dpy = enmap.zeros((2,)+shape[-2:],wcs)
    dpy = cs.alm2map(alm_py,dpy,deriv=True,method="cyl")
    del alm_py
    if do_curl: dpydx = dpy[1]
    dpydy = dpy[0]

    # unnormalized kappa from divergence
    kappa = dpxdx + dpydy
    kappa -= kappa.mean()
    alm_kappa = -cs.map2alm(kappa,lmax=mlmax)
    del py
    # if (lmax_x is not None) or (lmax_y is not None):
    #     alm_kappa = hp.almxfl(alm_kappa,xyfil)
    
    del kappa

    if do_curl:
        curl = dpydx - dpxdy
        del dpxdx,dpydy,dpydx,dpxdy,dpx,dpy
        curl -= curl.mean()
        alm_curl = -cs.map2alm(curl,lmax=mlmax)
        # if (lmax_x is not None) or (lmax_y is not None):
        #     alm_curl = hp.almxfl(alm_curl,xyfil)
        
        del curl
        return alm_kappa,alm_curl
    else:
        del dpxdx,dpydy,dpx,dpy
        return alm_kappa
    


