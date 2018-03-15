import scipy.optimize as op
import numpy as np
import os
import scipy.integrate as integrate
from settings import COSMO,TEDDINGTON,MBH_INTERP_MAX,MBH_INTERP_MIN,SPLINE_DICT
from settings import M_INTERP_MIN,LITTLEH,PI,JY,DH,MP,MSOL,TH,KBOLTZMANN
from settings import N_INTERP_Z,N_INTERP_MBH,Z_INTERP_MAX,Z_INTERP_MIN,ERG
from settings import M_INTERP_MAX,KPC,F_HE,F_H,YP,BARN,YR,EV,ERG
from settings import N_TSTEPS,E_HI_ION,E_HEI_ION,E_HEII_ION,SIGMAT
from settings import KBOLTZMANN_KEV
from cosmo_utils import massfunc,dict2tuple,tvir2mvir
import scipy.interpolate as interp
import copy
import matplotlib.pyplot as plt
import radio_background as RB
import recfast4py.recfast as recfast
from settings import DEBUG

#********************************************
#We first define a routine that generates
#and grows black holes through the halo
#mass function.
#********************************************

def dnbh_grid(recompute=False,**kwargs):
    '''
    differential number of black holes with mass mbh
        mbh: black hole mass
        z: redshift
    '''
    mkey=('dnbh','grid')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(mkey):
        tau_grow=TEDDINGTON/kwargs['GROWTH_FACTOR']
        #create t vals
        tmax=COSMO.age(kwargs['ZMIN'])
        tmin=COSMO.age(kwargs['ZMAX'])
        tval=tmin
        tvals=[tmin]
        dt=0.
        while tval<=tmax:
            zval=COSMO.age(tval,inverse=True)
            dt=21.7/COSMO.Ez(zval)/(1.+1.11*zval)#resolve time interval for one e-fold in
                                                    #halo mass
            tvals.append(tval+dt)
            tval=tval+dt
        tvals=tvals+[tmax,tmax*1.1]
        tvals=[.9*tmin]+tvals

        tvals=np.array(tvals)
        nt=len(tvals)
        nz=nt
        zvals=COSMO.age(tvals,inverse=True)
        #Calculate bounds halo masses
        mmax_form_vals=np.zeros_like(zvals)
        mmin_form_vals=np.zeros_like(mmax_form_vals)
        for znum,zval in enumerate(zvals):
            if kwargs['MASSLIMUNITS']=='KELVIN':
                mmin_form_vals[znum]=tvir2mvir(kwargs['TMIN_HALO'],zval)
                mmax_form_vals[znum]=tvir2mvir(kwargs['TMAX_HALO'],zval)
            elif kwargs['MASSLIMUNITS']=='MSOL':
                mmin_form_vals[znum]=kwargs['MMIN_HALO']
                mmax_form_vals[znum]=kwargs['MMAX_HALO']
        #Initialize mass grid.
        mvals0=np.logspace(np.log(10.**MBH_INTERP_MIN),
        np.log(10.**MBH_INTERP_MAX),N_INTERP_MBH,base=np.exp(1.))
        nm=len(mvals0)
        nbh_grid=np.zeros((nt,nm))
        mgrid=np.zeros_like(nbh_grid)
        mgrid[0]=mvals0
        mhalos0=mvals0/kwargs['MASSFRACTION']
        #print('pre-computing seed bh counts')
        n_seeds=np.zeros((nt,nm))
        n_seeds0=np.zeros_like(n_seeds)
        for znum,zval in enumerate(zvals):
            select=np.logical_and(mhalos0<=mmax_form_vals[znum],
            mhalos0>=mmin_form_vals[znum])
            n_seeds0[znum,select]=np.vectorize(massfunc)\
            (mhalos0[select],zvals[znum])*kwargs['HALOFRACTION']

        n_seeds[0,select]=n_seeds0[0,select]
        nbh_grid[0]=n_seeds[0]
        #print('growing black holes!')
        for tnum in range(1,len(tvals)):
            dt=tvals[tnum]-tvals[tnum-1]
            mgrid[tnum]=mgrid[tnum-1]*np.exp(dt/tau_grow)#grow black holes from
                                                         #accretion
            #compute the number of seeds. To do this, look at t-delta t
            #at t-delta t, halos that are one e-fold below m-min now have
            #mass mmin to mmin+maccreted
            #mhalos_prev=mgrid[tnum-1]/kwargs['massfrac']#mass of halos in last
                                                        #t-step in each mbh bin
            #mhalos_now=mhalos_prev*np.exp(dt/tau_halo(zvals[tnum-1]))#their mass now

            #How to add seeds? Number of new black holes with mass from logmbh to logmbh+dlogmbh
            #on this time-step equals number of halos with mhalo_prev=mbh/mhalo x exp(-dt/thalo)
            mhalo_now=mgrid[tnum]/kwargs['MASSFRACTION']
            mhalo_prev=mhalo_now*np.exp(-dt/tau_halo(zvals[tnum]))
            select=mhalo_prev<=mmin_form_vals[tnum-1]#allow seeds in halos
            select=np.logical_and(select,             #below thresshold in last
            np.logical_and(mhalo_now>=mmin_form_vals[tnum],#time but in range
            mhalo_now<=mmax_form_vals[tnum]))               #during this time
            if np.any(select):
                #print 'new seeds!'
                n_seeds[tnum,select]=massfunc(mhalo_prev[select],zvals[tnum-1])\
                *kwargs['HALOFRACTION']#number of seed halos per log10 mass
            #else:
                #print 'no new seeds! z=%.1f'%zvals[tnum]
            nbh_grid[tnum]=nbh_grid[tnum-1]+n_seeds[tnum]
        nbh_grid[nbh_grid<=0.]=1e-20
        SPLINE_DICT[mkey]=(tvals,zvals,mgrid,nbh_grid,n_seeds,n_seeds0)
    return SPLINE_DICT[mkey]

def rho_bh(z,**kwargs):
    '''
    density of black holes in msolar h^2/Mpc^3
    at redshift z given model in **kwargs
    '''
    splkey=('rho','gridded')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(splkey):
        t,zv,m,n_bh,_,_=dnbh_grid(**kwargs)
        #dlogm=np.log(m[0,1])-np.log(m[0,0])
        rhovals=np.zeros_like(t)
        for tnum in range(len(t)):
            mfunc=interp.interp1d(m[tnum],n_bh[tnum])
            rhovals[tnum]=integrate.quad(mfunc,m[tnum].min(),m[tnum].max())
        tfunc=interp.interp1d(t,rhovals)
        zv=np.linspace(zv.min(),zv.max(),N_INTERP_Z)#[1:-1]
        rhoz=tfunc(np.hstack([t.min(),COSMO.age(zv[1:-1]),t.max()]))
        SPLINE_DICT[splkey]=interp.interp1d(zv,rhoz)
    return SPLINE_DICT[splkey](z)

def emissivity_radio(z,freq,**kwargs):
    '''
    emissivity of radio emission from accreting black holes at redshift z
    in W/Hz*(h/Mpc)^3
    Args:
        z, redshift
        freq, co-moving frequency
        kwargs, model dictionary parameters
    '''
    return 1.0e22*(kwargs['F_R']/250.)*(kwargs['F_X']/2e-2)**0.86\
    *(rho_bh(z,**kwargs)/1e4)*(freq/1.4e9)**(-kwargs['ALPHA_R'])\
    *((2.4**(1.-kwargs['ALPHA_X'])-0.1**(1.-kwargs['ALPHA_X']))/\
    (10.**(1.-kwargs['ALPHA_X']-2.**(1.-kwargs['ALPHA_X']))))

def emissivity_xrays(z,E_x,**kwargs):
    '''
    emissivity of X-rays from accreting black holes at redshift z
    in (keV)/sec/keV/(h/Mpc)^3
    Args:
        z, redshift
        E_x, x-ray energy (keV)
        kwargs, model parameters dictionary
    '''
    return 2.322e48*(kwargs['F_X']/2e-2)*E_x**(-kwargs['ALPHA_X'])\
    *(rho_bh(z,**kwargs)/1e4)*(1.-kwargs['ALPHA_X'])\
    /(10.**(1.-kwargs['ALPHA_X'])-2.**(1.-kwargs['ALPHA_X']))\
    *np.exp(-10.**kwargs['LOG10_N']*(F_H*sigma_HLike(E_x)\
    +F_HE*sigma_HeI(E_x)))

def emissivity_uv(z,E_uv,**kwargs):
    '''
    emissivity in UV-photons from accreting black holes at redshift z
    in (eV)/sec/eV/(h/Mpc)^3
    Args:
        z, redshift
        E_uv, energy of uv photon (eV)
        kwargs, model parameter dictionary
    '''
    
