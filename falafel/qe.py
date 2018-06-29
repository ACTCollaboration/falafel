from enlib import curvedsky as cs, enmap
import numpy as np
import healpy as hp # needed only for isotropic filtering and alm -> cl, need to make it healpy independent

"""
1. you can use wigner-d gauss-legendre quadrature to calculate norm without evaluating wigner 3j
2. factorization tricks can be used for above
3. TT might not be correct. What is divergence doing to (spin-1?) gradient?

"""

def isotropic_filter_T(imap=None,alm=None,lcltt=None,ucltt=None,
                       nltt_deconvolved=None,tcltt=None,lmin=None,lmax=None,gradient=False):
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
    return cs.alm2map(alm,omap,deriv=True) # note that deriv=True gives the scalar derivative of a scalar alm field

def gradient_E_map(alm):
    """
    Given appropriately Wiener filtered E-mode alms,
    returns a real-space map containing the gradient of E.
    """
    pass

def gradient_B_map(alm):
    """
    Given appropriately Wiener filtered E-mode alms,
    returns a real-space map containing the gradient of B.
    """
    pass


def qe_tt_simple(Xmap,Ymap=None,lcltt=None,ucltt=None, \
                 nltt_deconvolved=None,tcltt=None,nltt_deconvolved_y=None,tcltt_y=None,
                 lmin=None,lmax=None,lmin_y=None,lmax_y=None,do_curl=False,mlmax=None):
    """
    Does -div(grad(wX)*wY) where wX and wY are Wiener filtered appropriately for isotropic noise
    from provided X and Y, and CMB and noise spectra.
    Does not normalize the estimator.
    """

    if Ymap is None: assert (nltt_deconvolved_y is None) and (tcltt_y is None) and (lmin_y is None) and (lmax_y is None)
    if nltt_deconvolved_y is None: nltt_deconvolved_y = nltt_deconvolved
    if tcltt_y is None: tcltt_y = tcltt
    if lmin_y is None: lmin_y = lmin
    if lmax_y is None: lmax_y = lmax

    if mlmax is None:
        mlmax = 2*max(lmax,lmax_y)

    iXalm = cs.map2alm(Xmap,lmax=mlmax)
    if Ymap is None:
        iYalm = iXalm.copy()
    else:
        iYalm = cs.map2alm(Ymap,lmax=mlmax)
        
    Xalm = isotropic_filter_T(alm=iXalm,lcltt=lcltt,ucltt=ucltt,
                              nltt_deconvolved=nltt_deconvolved,tcltt=tcltt,lmin=lmin,lmax=lmax,gradient=True)
    Yalm = isotropic_filter_T(alm=iYalm,lcltt=lcltt,ucltt=ucltt,
                              nltt_deconvolved=nltt_deconvolved_y,tcltt=tcltt_y,lmin=lmin_y,lmax=lmax_y,gradient=False)
    shape,wcs = Xmap.shape,Xmap.wcs
    return qe_tt(shape,wcs,Xalm,Yalm,lmax=mlmax,do_curl=do_curl)
    
def qe_tt(shape,wcs,Xalm,Yalm,do_curl=False,lmax=None):
    """
    Does -div(grad(wX)*wY) where wX_alm and wY_alm are provided as appropriately Wiener filtered alms.
    Does not normalize the estimator.
    """
    
    gradT = gradient_T_map(shape,wcs,Xalm)
    highT = enmap.zeros(shape[-2:],wcs)
    highT = cs.alm2map(Yalm,highT)

    px = gradT[0] * highT
    py = gradT[1] * highT
    
    alm_px = cs.map2alm(px,lmax=lmax)
    alm_py = cs.map2alm(py,lmax=lmax)
    
    dpx = enmap.zeros((2,)+shape[-2:],wcs)
    dpx = cs.alm2map(alm_px,dpx,deriv=True)
    dpxdx = dpx[0].copy()
    if do_curl: dpxdy = dpx[1].copy()
    dpy = enmap.zeros((2,)+shape[-2:],wcs)
    dpy = cs.alm2map(alm_py,dpy,deriv=True)
    if do_curl: dpydx = dpy[0].copy()
    dpydy = dpy[1].copy()

    kappa = dpxdx + dpydy
    alm_kappa = -cs.map2alm(kappa,lmax=lmax)
    if do_curl:
        curl = dpydx - dpxdy
        alm_curl = -cs.map2alm(curl,lmax=lmax)
        return alm_kappa,alm_curl
    else:
        return alm_kappa
    


