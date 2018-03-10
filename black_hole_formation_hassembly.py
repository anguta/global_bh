#Functions for modeling the formation of black-hole seeds at high redshift
#Our formalism is based around the definition of a ``black-hole initial
#mass function'', similar to the stellar initial mass function
#it gives dN/dmbh/dVc/dz
#
import scipy.optimize as op
import numpy as np
import os
import scipy.integrate as integrate
from settings import COSMO,TEDDINGTON,MBH_INTERP_MAX,MBH_INTERP_MIN,SPLINE_DICT
from settings import M_INTERP_MIN,LITTLEH,PI,JY,DH,MP,MSOL
from settings import N_INTERP_Z,N_INTERP_MBH,Z_INTERP_MAX,Z_INTERP_MIN,ERG
from settings import M_INTERP_MAX,KPC,F_HE,F_H,YP,BARN,YR,EV
from settings import N_TSTEPS,E_HI_ION,E_HEI_ION,E_HEII_ION,SIGMAT
from cosmo_utils import massfunc,dict2tuple,tvir2mvir
import scipy.interpolate as interp
import copy
import matplotlib.pyplot as plt
import radio_background as RB
import recfast4py.recfast as recfast
from settings import DEBUG

def q_ionize(zlow,fesc=1.,norec=False,ntimes=int(1e4),T4=1.,**kwargs):
    '''
    compute ionization fraction by integrating differential equation (Madau 1999)
    '''
    tmax=COSMO.age(np.min([kwargs['zmin'],zlow]))
    tmin=COSMO.age(kwargs['zmax'])
    taxis=np.linspace(tmin,tmax,ntimes)#times in Gyr
    dt=taxis[1]-taxis[0]
    zaxis=COSMO.age(taxis,inverse=True)#z axis
    qvals=np.zeros_like(taxis)
    qvals_he=np.zeros_like(taxis)
    qdots=np.zeros_like(taxis)
    qdots_he=np.zeros_like(taxis)
    dtaus=np.zeros_like(taxis)
    taus=np.zeros_like(qvals)
    nH0=(1.-YP)*COSMO.rho_b(0.)*(1e3)**3.*MSOL/MP#hydrogen number density at z=0 in coMpc^-3
    nH0cm=nH0/(1e3*KPC*1e2)**3./LITTLEH**3.#hydrogen density at z=0 in cm^-3
    chi=YP/4./(1.-YP)
    nHe0cm=chi*nH0cm
    nHe0=chi*nH0
    for tnum in range(1,len(qvals)):
        tval,zval=taxis[tnum-1],zaxis[tnum-1]
        crr=2.9*((1.+zval)/6.)**(-1.1)#clumping factor
        trec=1./(crr*(1+chi)*nH0cm*(1.+zval)**3.*2.6e-13*(T4)**-.7)/1e9/YR# trec in Gyr
        trec_he=1./((1.+2.*chi)*nH0cm*(1.+zval)**3.*2*2.6e-13*(T4/4)**-.7*crr)/1e9/YR
        #print trec
        #if not(norec):
        if zval>=kwargs['zmin']:
            qdots[tnum-1]=.9*fesc*ndot_ion(zval,**kwargs)/nH0*1e9*YR-qvals[tnum-1]/trec
            qdots_he[tnum-1]=.1*fesc*ndot_ion(zval,**kwargs)/nHe0*1e9*YR-qvals_he[tnum-1]/trec_he
        else:
            qdots[tnum-1]=-qvals[tnum-1]/trec
            qdots_he[tnum-1]=-qvals_he[tnum-1]/trec_he
        #else:
        #    qdot=fesc*ndot_ion(zval,**kwargs)/nH0*1e9*YR
        qvals[tnum]=np.min([1.,qvals[tnum-1]+dt*qdots[tnum-1]])
        qvals_he[tnum]=np.min([1.,qvals_he[tnum-1]+dt*qdots_he[tnum-1]])
        dz=-zaxis[tnum]+zaxis[tnum-1]
        DHcm=3e5/COSMO.H0*1e3*1e2*KPC
        dtaus[tnum-1]=DHcm*nH0cm*SIGMAT*(1.+zval)**2./COSMO.Ez(zval)*\
        (qvals[tnum-1]*(1+chi)+qvals_he[tnum-1]*chi)*dz
        taus[tnum]=taus[tnum-1]+dtaus[tnum-1]
    #print fesc*ndot_ion(zval,**kwargs)*1e9*YRs
    #print nH0
    return zaxis,taxis,qvals,taus,qdots,dtaus
def run_heating(zlow,xe0,Tk0,fesc=1.,ntimes=int(1e2),T4=1.,NX=100,XRAYMAX=1e2,**kwargs):
    #first compute QHII
    nH0=(1.-YP)*COSMO.rho_b(0.)*(1e3)**3.*MSOL/MP#hydrogen number density at z=0 in coMpc^-3
    nH0cm=nH0/(1e3*KPC*1e2)**3./LITTLEH**3.#hydrogen density at z=0 in cm^-3
    chi=YP/4./(1.-YP)
    nHe0cm=chi*nH0cm
    nHe0=chi*nH0
    nB0=nH0+nHe0
    nB0cm=nH0cm+nHe0cm
    print('Computing HII Evolution')
    zaxis,taxis,qvals,_,_,_=q_ionize(zlow,fesc=fesc,ntimes=ntimes,T4=T4,**kwargs)
    #for each z in zaxis
    jvals=[]
    #NX=100
    #XRAYMAX=1e4#start with very high maximum energy. The maximum value at each redshift should be
               #XRAYMAX
    xray_axes=np.zeros((ntimes,NX))
    xray_axes[0]=np.logspace(np.log10(kwargs['EX_min']),np.log10(XRAYMAX),NX)#interpolate between min_X and 10 keV
    #initialize optical depth table and Tk
    Tks=np.zeros_like(zaxis)
    xes=np.zeros_like(zaxis)
    #zdec=137.*(COSMO.Ob(0)*LITTLEH**2./.022)**.4-1.
    #Tks[0]=2.73*(1+zdec)*(1+zaxis[0])/(1.+zdec)**2.#initialize first Tk to equal adiabatic cooled value.
    print('Initializing xe,Tk with RecFast')
    #zarr, Xe_H, Xe_He, Xe ,TM=recfast.Xe_frac(Yp=YP, T0=COSMO.Tcmb0,
    #Om=COSMO.Om0, Ob=COSMO.Ob0, OL=COSMO.Ode0, Ok=0.,
    #h100=LITTLEH, Nnu=COSMO.Neff, F=1.14, fDM=0.)
    xes[0]=xe0#interp.interp1d(zarr,Xe)(zaxis[0])#xe in non HI regions set to zero at first (or recfast)
    Tks[0]=Tk0#interp.interp1d(zarr,TM)(zaxis[0])#Temperature from recfast
    taus={}
    print('Initializing Interpolation')
    init_interpolation_tables()
    def tau0(ex,zp):
        return 0.
    taus[zaxis[0]]=lambda x,y:tau0(x,y)#will return 0. for all frequencies
    #array of taus
    print('Starting Evolution at z=%.2f, xe=%.2e, Tk=%.2f'%(zaxis[0],xes[0],Tks[0]))

    for tnum in range(1,len(taxis)):
        #first compute the optical depths to higher redshifts
        zval,tval=zaxis[tnum],taxis[tnum]
        tau_vals=np.zeros((tnum+1,NX))
        dz=zaxis[tnum-1]-zaxis[tnum]
        zm1=zaxis[tnum-1]
        qm1=qvals[tnum-1]
        xem1=xes[tnum-1]
        xim1=qm1+(1-qm1)*xem1#ionized fraction from HI and HII regions
        dz=zm1-zval
        tau_splines={}
        xray_axes[tnum]=np.logspace(np.log10(kwargs['EX_min']),
        np.log10(XRAYMAX*(1.+kwargs['zmax'])/\
        (1.+zval)),NX)
        dlogx=xray_axes[tnum-1][1]-xray_axes[tnum-1][0]
        print('calculating tau values at z=%.2f'%(zval))
        for xnum,ex in enumerate(xray_axes[tnum]):
            #compute the optical depth to last redshift using linear approximation
            dtau=dz*(DH*1e3*KPC*1e2)*(1.+zm1)**2./COSMO.Ez(zm1)*(1.-qm1)\
            *((1.-xem1)*nH0cm*sigma_HLike(ex,z=1.)\
            +(1.-xem1)*nHe0cm*sigma_HeI(ex)\
            +xem1*nHe0cm*sigma_HLike(ex,z=2.))
            #print tau_vals[:-1,xnum].shape
            #print zaxis[:tnum].shape
            tau_vals[:-1,xnum]=dtau+np.vectorize(lambda x:\
            taus[zm1](ex*(1.+zval)/(1.+zm1),x))(zaxis[:tnum])
            #evaluate tau values at energy ex to all higher redshifts
            #print zaxis[:tnum+1][::-1].shape
            #print tau_vals[:,xnum][::-1].shape
            tau_splines[ex]=interp.interp1d(zaxis[:tnum+1][::-1],tau_vals[:,xnum][::-1],
            bounds_error=False,fill_value=0.,kind='linear')
        def tau_function(ex,zp):
            #find high and low ex
            exi_l=int((np.log10(ex)-np.log10(kwargs['EX_min']))/dlogx)
            exi_u=exi_l+1
            tau_l=tau_splines[exi_l](zp)
            tau_h=tau_splines[exi_h](zp)
            #interpolate logarithmically
            a=np.log10(tau_h/tau_l)/(np.log10(xray_axes[tnum-1,exi_h]\
            /xray_axes[tnum-1,exi_l]))
            b=np.log10(tau_h)-a*np.log10(ex_h)
            return b+a*np.log10(ex)
        taus[zaxis[tnum]]=tau_function
        #now that we have a tau_function, lets compute the integrated fluxes
        print('Computing integrated X-ray fluxes at z=%.2f'%zm1)
        #for xnum,ex in enumerate(xray_axis):
            #I am here!
        jx_vals=np.zeros_like(xray_axes[tnum-1])
        for exnum,ex in enumerate(xray_axes[tnum-1]):
            g=lambda x:np.exp(-taus[zm1](ex,x))\
            *emissivity_X_gridded(x,ex*(1.+x)/(1.+zm1),**kwargs)/COSMO.Ez(x)\
            /(1.+x)
            jx_vals[exnum]=(1.+zm1)**3./4./PI*DH\
            *integrate.quad(g,zm1,zaxis[0])[0]\
            /(1e3*KPC*1e2)**2.*LITTLEH**3.
            #gives flux in Watts/keV/(cm)^2/Sr
            #convert flux to keV sec^-1/keV/cm^2/Sr
            jx_vals[exnum]=jx_vals[exnum]/EV/1e3
        jx_func=interp.interp1d(np.log(xray_axes[tnum-1]),jx_vals,fill_value=0.,
        kind='linear',bounds_error=False)
        print('Computing integrated X-ray heating rate at z=%.2f'%zm1)
        g=lambda x:4.*PI*jx_func(np.exp(x))\
        *interp_heat_val(np.exp(x),xem1,'f_heat')\
        *((np.exp(x)-E_HI_ION)*(1.-xem1)*sigma_HLike(np.exp(x))*F_H\
        +F_HE*(np.exp(x)-E_HEI_ION)*(1-xem1)*sigma_HeI(np.exp(x))\
        +(np.exp(x)-E_HEII_ION)*xem1*F_HE*sigma_HLike(np.exp(x),z=2.))
        logxmax=np.log(xray_axes[tnum-1].max())
        eps_x=integrate.quad(g,np.log(kwargs['EX_min']),logxmax)[0]
        #integrate dJ/dE * dlogE*sigma_heat*E_heat
        #convert back to Watts
        eps_x=eps_x*1e3*EV
        dtdzm1=TH*1e9*YR/(COSMO.Ez(zm1)*(zm1+1))
        print('Computing integrated X-ray ionization rate at z=%.2f'%zm1)
        g=lambda x:4.*PI*jx_func(np.exp(x))*ion_sum(np.exp(x),xem1)
        gamma_ion=integrate.quad(g,np.log(kwargs['EX_min']),logxmax)
        #integrate dJ/dE * dlogE*sigma_ion
        print('Stepping xe')
        alpha_a=4.2e-13*(Tks[tnum-1]/1e4)**-.7
        dxe=-alpha_a*xem1**2.*nB0cm*(1.+zm1)**3.*F_H\
        *CRR*dz*dtdzm1
        dxe=dxe+dz*dtdzm1*gamma_ion
        print('Stepping T_k')
        #!!!Ignoring Compton Heating for now.
        dTK=2.*Tks[tnum-1]/(3.*nB0*(1.+zm1)**3.)*3.*(1.+zm1)**2.*nB0*dz\
        -Tks[tnum-1]/(1.+xem1)*dxe
        dTk=dTk+2./(3.*KBOLTZMANN*(1.+xem1))\
        *eps_x*dz*dtdzm1
        Tks[tnum]=Tks[tnum-1]+dTk
        xes[tnum]=xes[tnum-1]+dxe
        print('Tk=%.2f,xe=%.3f'%(Tks[tnum],xes[tnum]))
    return taxis,zaxis,Tks,xes







#*******************************************
#Ionization parameters
#*******************************************
def sigma_HLike(e,z=1.):
    '''
    gives ionization cross section in cm^2 for an X-ray with energy ex (keV)
    for a Hydrogen-like atom with atomic number z
    '''
    ex=e*1e3 #input energy in keV, convert to eV
    e1=13.6*z**2.
    if ex<e1:
        return 0.
    else:
        eps=np.sqrt(ex/e1-1.)
        return 6.3e-18*(e1/ex)**4.*np.exp(4.-(4.*np.arctan(eps)/eps))/\
        (1-np.exp(-2.*PI/eps))/z/z
def sigma_HeI(e):
    '''
    gives ionization cross section in cm^2 for X-ray of energy ex (keV)
    for HeI atom.
    '''
    ex=e*1e3#input energy is in keV, convert to eV
    if ex>=2.459e1 and ex<=1e4:
        e0,sigma0,ya,p,yw,y0,y1=1.361e1,9.492e2,1.469,3.188,2.039,4.434e-1,2.136
        x=ex/e0-y0
        y=np.sqrt(x**2.+y1*2.)
        fy=((x-1.)**2.+yw**2.)*y**(0.5*p-5.5)*np.sqrt(1.+np.sqrt(y/ya))**(-p)
        return fy*sigma0*BARN*1e6#Last factor converts from Mbarnes to cm^-2
    else:
        return 0.


#*******************************************
#initialize interpolation x_int_tables
#*******************************************
def init_interpolation_tables():
    '''
    Initialize interpolation tables for number of ionizing electrons produced
    per ionization of H, He, HI, fraction of energy deposited in heating and
    fraction deposited in ionization.
    '''
    table_names=['x_int_tables/log_xi_-4.0.dat',
                   'x_int_tables/log_xi_-3.6.dat',
                   'x_int_tables/log_xi_-3.3.dat',
                   'x_int_tables/log_xi_-3.0.dat',
                   'x_int_tables/log_xi_-2.6.dat',
                   'x_int_tables/log_xi_-2.3.dat',
                   'x_int_tables/log_xi_-2.0.dat',
                   'x_int_tables/log_xi_-1.6.dat',
                   'x_int_tables/log_xi_-1.3.dat',
                   'x_int_tables/log_xi_-1.0.dat',
                   'x_int_tables/xi_0.500.dat',
                   'x_int_tables/xi_0.900.dat',
                   'x_int_tables/xi_0.990.dat',
                   'x_int_tables/xi_0.999.dat']

    SPLINE_DICT['xis']=np.array([1e-4,2.318e-4,4.677e-4,1.0e-3,2.318e-3,
    4.677e-3,1.0e-2,2.318e-2,4.677e-3,1.0e-2,2.318e-2,
    4.677e-2,1.0e-1,.5,.9,.99,.999])
    for tname,xi in zip(table_names,SPLINE_DICT['xis']):
        dirname,filename=os.path.split(os.path.abspath(__file__))
        itable=np.loadtxt(dirname+'/'+tname,skiprows=3)
        SPLINE_DICT[('f_ion',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,1])
        SPLINE_DICT[('f_heat',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,2])
        SPLINE_DICT[('f_exc',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,3])
        SPLINE_DICT[('n_Lya',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,4])
        SPLINE_DICT[('n_{ion,HI}',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,5])
        SPLINE_DICT[('n_{ion,HeI}',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,6])
        SPLINE_DICT[('n_{ion,HeII}',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,7])
        SPLINE_DICT[('shull_heating',xi)]=interp.interp1d(itable[:,0]/1e3,itable[:,8])
        SPLINE_DICT[('min_e_kev',xi)]=(itable[:,0]/1e3).min()
        SPLINE_DICT[('max_e_kev',xi)]=(itable[:,0]/1e3).max()

def interp_heat_val(e_kev,xi,mode='f_ion'):
    '''
    get the fraction of photon energy going into ionizations at energy e_kev
    and ionization fraction xi
    Args:
    ex, energy of X-ray in keV
    xi, ionized fraction of IGM
    '''
    ind_high=int(np.arange(SPLINE_DICT['xis'].shape[0])[SPLINE_DICT['xis']>=xi].min())
    ind_low=int(np.arange(SPLINE_DICT['xis'].shape[0])[SPLINE_DICT['xis']<xi].max())
    x_l=SPLINE_DICT['xis'][ind_low]
    x_h=SPLINE_DICT['xis'][ind_high]
    min_e=np.max([SPLINE_DICT[('min_e_kev',x_l)],SPLINE_DICT[('min_e_kev',x_h)]])
    max_e=np.min([SPLINE_DICT[('max_e_kev',x_l)],SPLINE_DICT[('max_e_kev',x_h)]])
    if e_kev<=min_e: e_kev=min_e
    if e_kev>=max_e: e_kev=max_e
    vhigh=SPLINE_DICT[(mode,x_h)](e_kev)
    vlow=SPLINE_DICT[(mode,x_l)](e_kev)
    a=(vhigh-vlow)/(x_h-x_l)
    b=vhigh-a*x_h
    return b+a*xi #linearly interpolate between xi values.


def ion_sum(ex,xe):
    '''
    \sum_{i,j}(hnu-E^th_j)*(fion,HI/E^th_j)f_i x_i \sigma_i
    for hun=ex
    and ionized IGM fraction xe
    '''
    e_hi=ex-E_HI_ION
    e_hei=ex-E_HEI_ION
    e_heiii=ex-E_HEII_ION

    fi_hi=interp_heat_val(e_hi,xe,'n_{ion,HI}')\
    +interp_heat_val(e_hei,xe,'n_{ion,HeI}')\
    +interp_heat_val(e_heii,xe,'n_{ion,HeII}')+1.
    fi_hi=fi_hi*(F_H*(1-xe))*sigma_HLike(ex)

    fi_hei=interp_heat_val(e_hei,xe,'n_{ion,HI}')\
    +interp_heat_val(e_hei,xe,'n_{ion,HeI}')\
    +interp_heat_val(e_heii,xe,'n_{ion,HeII}')+1.
    fi_hei=fi_hei*(F_HE*(1-xe))*sigma_HeI(ex)

    fi_heii=interp_heat_val(e_heii,xe,'n_{ion,HI}')\
    +interp_heat_val(e_hei,xe,'n_{ion,HeI}')\
    +interp_heat_val(e_heii,xe,'n_{ion,HeII}')+1.
    fi_heii=fi_heii*(F_HE*xe*sigma_HLike(ex,z=2.))

    return ri_hi+fi_hei+fi_heii


#*******************************************
#heating and ionization fractions at xi
#*******************************************
def f_heat(xi):
    splkey=('f_heat')
    if not SPLINE_DICT.has_key(splkey):
        xiv=np.array([0.,.0001,.00023,.00047,.001,.0023,
        .0047,.01,.023,.047,.1,.5,.9,.99,.999,1.])
        f_heat=np.array([.126,.126,.138,.153,.176,.212,.255,
        .319,.418,.528,.668,.922,.973,.979,.979,.979])

def f_ion(xi):
    splkey=('f_ion')
    if not SPLINE_DICT.has_key(splkey):
        xiv=np.array([0.,.0001,.00023,.00047,.001,.0023,
        .0047,.01,.023,.047,.1,.5,.9,.99,.999,1.])
        fions=np.array([.394,.394,.392,.389,.384,.371,.355,.329,
        .283,.232,.165,.0446,.0229,.0209,.0207,.0207])
        SPLINE_DICT[splkey]=interp.interp1d(xiv,fions)
    return SPLINE_DICT[splkey](xi)


def f_lya(xi):
    splkey=('f_lya')
    if not SPLINE_DICT.has_key(splkey):
        xiv=np.array([0.,.0001,.00023,.00047,.001,.0023,
        .0047,.01,.023,.047,.1,.5,.9,.99,.999,1.])
        flyas=np.array([.376,.376,.369,.360,.347,.330,
        .310,.281,.239,.193,.134,.0266,.00323,
        .000284,.0000303,.0000303])
        SPLINE_DICT[splkey]=interp.interp1d(xiv,flyas)
    return SPLINE_DICT[splkey](xi)
#*****************************************
#Functions for computing radio luminosity
#*****************************************
def radio_luminosity_fp_5ghz_merloni03(mbh,**kwargs):
    lx=0.3*1.26e38*kwargs['fedd']*kwargs['fduty']*mbh
    l5ghz=10.**(7.33+0.78*np.log10(mbh)+0.6*np.log10(lx))/5e9
    return l5ghz*ERG
def x_ray_luminosity_2kev_wang06(mbh,**kwargs):
    '''
    2 keV luminosity in Watts keV^-1
    '''
    m=mbh/LITTLEH#convert from msolar/h units to msolar
    #mean logarithm of Lx/Ledd
    mux=(kwargs['mu_loglxf']-np.log10(kwargs['fedd']))*np.log(10.)
    #print 'mux=%.2e'%mux
    #std of logarithm of Lx/Ledd (from Wang 2006)
    sigmax=np.log(10.)*kwargs['sigma_loglxf']
    fx=np.exp(mux+.5*(sigmax)**2.)*kwargs['fedd']
    lxp1_2p4=fx*m*1.26e31#luminosity from .1 to 2.4 keV in Watts
    l0e0alpha=(1.-kwargs['alphaX'])*lxp1_2p4\
    /((2.4)**(1.-kwargs['alphaX'])-(np.max([.1,kwargs['EX_min']]))**(1.-kwargs['alphaX']))
    return l0e0alpha*2.**(-kwargs['alphaX'])#returns Watts/keV at 2 keV


def radio_luminosity_fp_5ghz_wang06(mbh,**kwargs):
    #mean logarithm of Lx/Ledd
    m=mbh/LITTLEH
    mux=(kwargs['mu_loglxf']-np.log10(kwargs['fedd']))*np.log(10.)
    #print 'mux=%.2e'%mux
    #std of logarithm of Lx/Ledd (from Wang 2006)
    sigmax=np.log(10.)*kwargs['sigma_loglxf']
    fx=np.exp(mux+.5*(sigmax)**2.)*kwargs['fedd']#total fraction of Eddington luminosity
    lr=10.**(.86*np.log10(fx)-5.08)#Wang 2006 equation 6 gives L_nu*nu in eddington luminosities
    lr=lr*m*1.26e31*(5e9/1.4e9)**kwargs['radioind']/1.4e9#convert eddington luminosities
                                                     #to frequency luminosity at 1.4GHz.
    return lr

    #******************************************
    #Here's a different approach: Differential equation
    #******************************************

def halo_accretion_rate(mh,z):
    '''
    Mean accretion rate from Fakhouri 2010
    '''
    #convert from msol/h to msol
    m=mh/LITTLEH
    return 46.1*(m/1e12)**1.1*(1.+1.11*z)*COSMO.Ez(z)*LITTLEH*1e9


def tau_grow(**kwargs):
    return TEDDINGTON/kwargs['fedd']/kwargs['fduty']/(1./kwargs['radeff']-1.)

def tau_halo(x):
    return 21.7/COSMO.Ez(x)/(1.+1.11*x)

def zmin(**kwargs):
    '''
    Solve minimum z before halo accretion time-scale equals black-hole
    accretion time scale.
    '''
    return op.minimize(lambda x: np.abs(tau_halo(x)-tau_grow(**kwargs)),
    x0=[15.]).x[0]

def dnbh_grid(recompute=False,**kwargs):
    '''
    differential number of black holes with mass mbh
        mbh: black hole mass
        z: redshift
    '''
    mkey=('dnbh','grid')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(mkey):
        tau_grow=TEDDINGTON/kwargs['fedd']/kwargs['fduty']/(1./kwargs['radeff']-1.)
        #create t vals
        tmax=COSMO.age(kwargs['zmin'])
        tmin=COSMO.age(kwargs['zmax'])
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
            if kwargs['masslimunits']=='KELVIN':
                mmin_form_vals[znum]=tvir2mvir(kwargs['tmin_halo'],zval)
                mmax_form_vals[znum]=tvir2mvir(kwargs['tmax_halo'],zval)
            elif kwargs['masslimunits']=='MSOL':
                mmin_form_vals[znum]=kwargs['mmin_halo']
                mmax_form_vals[znum]=kwargs['mmax_halo']
        #Initialize mass grid.
        mvals0=np.logspace(np.log(10.**MBH_INTERP_MIN),
        np.log(10.**MBH_INTERP_MAX),N_INTERP_MBH,base=np.exp(1.))
        nm=len(mvals0)
        nbh_grid=np.zeros((nt,nm))
        mgrid=np.zeros_like(nbh_grid)
        mgrid[0]=mvals0
        mhalos0=mvals0/kwargs['massfrac']
        #print('pre-computing seed bh counts')
        n_seeds=np.zeros((nt,nm))
        n_seeds0=np.zeros_like(n_seeds)
        for znum,zval in enumerate(zvals):
            select=np.logical_and(mhalos0<=mmax_form_vals[znum],
            mhalos0>=mmin_form_vals[znum])
            n_seeds0[znum,select]=np.vectorize(massfunc)\
            (mhalos0[select],zvals[znum])*kwargs['halofraction']

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
            mhalo_now=mgrid[tnum]/kwargs['massfrac']
            mhalo_prev=mhalo_now*np.exp(-dt/tau_halo(zvals[tnum]))
            select=mhalo_prev<=mmin_form_vals[tnum-1]#allow seeds in halos
            select=np.logical_and(select,             #below thresshold in last
            np.logical_and(mhalo_now>=mmin_form_vals[tnum],#time but in range
            mhalo_now<=mmax_form_vals[tnum]))               #during this time
            if np.any(select):
                #print 'new seeds!'
                n_seeds[tnum,select]=massfunc(mhalo_prev[select],zvals[tnum-1])\
                *kwargs['halofraction']#number of seed halos per log10 mass
            #else:
                #print 'no new seeds! z=%.1f'%zvals[tnum]
            nbh_grid[tnum]=nbh_grid[tnum-1]+n_seeds[tnum]
        nbh_grid[nbh_grid<=0.]=1e-20
        SPLINE_DICT[mkey]=(tvals,zvals,mgrid,nbh_grid,n_seeds,n_seeds0)
    return SPLINE_DICT[mkey]

#def emissivity_dnbh(z,**kwargs)
def emissivity_gridded(z,freq,**kwargs):
    splkey=('emissivity','gridded')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(splkey):
        rfactor=np.exp(kwargs['rl_mean']*kwargs['rl_slope']*np.log(10.)\
        +.5*(kwargs['rl_std']*kwargs['rl_slope']*np.log(10.))**2.)
        #print 'rfactor=%e'%rfactor
        rqfrac=1.-kwargs['rl_fraction']
        t,zv,m,n_bh,_,_=dnbh_grid(**kwargs)#get grid of black hole masses as a function
        if kwargs['fp']=='m03':
            l5ghz=radio_luminosity_fp_5ghz_merloni03(m,**kwargs)#luminosities
        elif kwargs['fp']=='w06':
            l5ghz=radio_luminosity_fp_5ghz_wang06(m,**kwargs)#luminosities
        dlogm=np.log(m[0,1])-np.log(m[0,0])#all redshifts have same dlogm res
        emissivities=(n_bh*l5ghz*(rqfrac+kwargs['rl_fraction']*rfactor)\
        *dlogm/np.log(10.)).sum(axis=1)*kwargs['fduty']#total 5 GHz emissivity
        tfunc=interp.interp1d(t,emissivities)
        zv=np.linspace(zv.min(),zv.max(),N_INTERP_Z)#[1:-1]
        emz=tfunc(np.hstack([t.min(),COSMO.age(zv[1:-1]),t.max()]))

        SPLINE_DICT[splkey]=interp.interp1d(zv,emz)
    return SPLINE_DICT[splkey](z)*(freq/5e9)**kwargs['radioind']

def emissivity_X_gridded(z,ex,**kwargs):
    '''
    Emissivity (Watts/(Mpc/h)^3/keV) of X-rays from accretion.
    Args:
        ex, emission-frame X-ray energy (at redshift z) (kev)
        z, redshift
    Returns:
        comoving X-ray emissivity emissivity (Watts/(Mpc/h)^3/keV)
        of X-rays from accretion.
    '''
    splkey=('emissivity_X','gridded')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(splkey):
        t,zv,m,n_bh,_,_=dnbh_grid(**kwargs)#get grid of black hole masses as a function
        lx=x_ray_luminosity_2kev_wang06(m,**kwargs)
        dlogm=np.log(m[0,1])-np.log(m[0,0])
        emissivities=(n_bh*lx\
        *dlogm/np.log(10.)).sum(axis=1)*kwargs['fduty']#total 2keV emissivity
        tfunc=interp.interp1d(t,emissivities)
        zv=np.linspace(zv.min(),zv.max(),N_INTERP_Z)#[1:-1]
        emz=tfunc(np.hstack([t.min(),COSMO.age(zv[1:-1]),t.max()]))
        SPLINE_DICT[splkey]=interp.interp1d(zv,emz)
    if isinstance(ex,float):
        if ex<=kwargs['EX_min']:
            return 0
        else:
            return SPLINE_DICT[splkey](z)*(ex/2.)**(-kwargs['alphaX'])
    else:
        output=np.zeros_like(ex)
        select=ex>=kwargs['EX_min']
        output[select]=SPLINE_DICT[splkey](z)*(ex[select]/2.)**(-kwargs['alphaX'])
        return output




def rho_gridded(z,**kwargs):
    splkey=('rho','gridded')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(splkey):
        t,zv,m,n_bh,_,_=dnbh_grid(**kwargs)
        dlogm=np.log(m[0,1])-np.log(m[0,0])
        rhos=(n_bh*dlogm/np.log(10.)*m).sum(axis=1)
        tfunc=interp.interp1d(t,rhos)
        zv=np.linspace(zv.min(),zv.max(),N_INTERP_Z)#[1:-1]
        rhoz=tfunc(np.hstack([t.min(),COSMO.age(zv[1:-1]),t.max()]))
        SPLINE_DICT[splkey]=interp.interp1d(zv,rhoz)
    return SPLINE_DICT[splkey](z)



def radio_source_counts(freq,**kwargs):
    '''
    number of sources per comoving Megaparsec at redshift z with flux between
    S and S+dS
    Args:
        s, flux (Jy)
        z, redshift
        freq, observed frequency (Hz)
    '''
    splkey=('radio source','counts')+dict2tuple(kwargs)
    if not SPLINE_DICT.has_key(splkey):
        rfactor=np.exp(kwargs['rl_mean']*kwargs['rl_slope']*np.log(10.)\
        +.5*(kwargs['rl_std']*kwargs['rl_slope']*np.log(10.))**2.)
        #print 'rfactor=%e'%rfactor
        rqfrac=1.-kwargs['rl_fraction']
        t,zv,m,n_bh,_,_=dnbh_grid(**kwargs)#get grid of black hole masses as a function
        if kwargs['fp']=='m03':
            l5ghz=radio_luminosity_fp_5ghz_merloni03(m,**kwargs)#luminosities
        elif kwargs['fp']=='w06':
            l5ghz=radio_luminosity_fp_5ghz_wang06(m,**kwargs)#luminosities
        s_q=(l5ghz.T/4./PI/(COSMO.luminosityDistance(zv)*1e3*KPC)**2.*(1.+zv.T)/JY\
        *LITTLEH**2.).T
        s_l=s_q*rfactor
        n_bh_q=rqfrac*n_bh
        n_bh_l=(1-rqfrac)*n_bh
        SPLINE_DICT[splkey]=(zv,s_q,s_l,n_bh_q,n_bh_l)
    zv,s_q,s_l,n_bh_q,n_bh_l=SPLINE_DICT[splkey]
    return zv,(s_q.T*(freq*(1.+zv.T)/5e9)**kwargs['radioind']).T,(s_l.T*(freq*(1.+zv.T)/5e9)**kwargs['radioind']).T,n_bh_q,n_bh_l


def dndlogs(freq,**kwargs):
    '''
    calculate the number of sources per steradian per logs on the sky obs at z=0
    '''
    zv,s_q,s_l,n_q,n_l=radio_source_counts(5e9,**kwargs)
    def grid_s(sgrid,ngrid):
        s_axis=np.logspace(-15,0,100)
        output=np.zeros_like(ngrid)
        for tnum in range(sgrid.shape[0]):
            output[tnum]=interp.interp1d(np.log10(sgrid[tnum]),ngrid[tnum],fill_value=0.,bounds_error=False)(np.log10(s_axis))
        return s_axis,output
    s_q,n_q=grid_s(s_q,n_q)#place all source counts on same flux scale in dn/dlogs/dvc
    s_l,n_l=grid_s(s_l,n_l)
    #plt.close()
    #plt.pcolor(n_l)
    #plt.colorbar()
    #plt.show()
    #plt.pcolor(n_q)
    #plt.colorbar()
    #plt.show()
    dvcdomega=(COSMO.luminosityDistance(zv)/(1.+zv))**2./COSMO.Ez(zv)
    dndlogs_q=DH*(n_q[:-1].T*dvcdomega[:-1]*np.abs(np.diff(zv))).T.sum(axis=0)
    dndlogs_l=DH*(n_l[:-1].T*dvcdomega[:-1]*np.abs(np.diff(zv))).T.sum(axis=0)
    return (s_q.T*(freq/5e9)**kwargs['radioind']).T,(s_l.T*(freq/5e9)**kwargs['radioind']).T,dndlogs_q,dndlogs_l



def lc_emissivity_wang06(rho_bh,energy_units='Watts',**kwargs):
    '''
    Ly-C emissivity between 1 and 4 Ryd in W Hz^-1 (h/Mpc)^3
    '''
    if energy_units=='Ergs' or energy_units=='ERGS' or energy_units=='ergs':
        nfactor=1e7
    else:
        nfactor=1.
    return 5.8e19*rho_bh*(kwargs['lyx_correction'])*nfactor

def uv_emissivity_wang06(z,freq,**kwargs):
    '''
    emissivity in UV redward of 912 angstroms
    in W Hz^-1 h^3 Mpc^-3
    '''
    return 4.3e15*rho_gridded(z,**kwargs)*(freq/1.2e15)**(-.61)\
    *(kwargs['fduty']/.5)


def ndot_ion(z,**kwargs):
    '''
    number of ionizing photons per second
    '''
    return 6.52e48*rho_gridded(z,**kwargs)*kwargs['fduty']#.9 from integral of 1 to 4 ryd


def q_ionize(zlow,fesc=1.,norec=False,ntimes=int(1e4),YP=0.25,T4=1.,**kwargs):
    '''
    compute ionization fraction by integrating differential equation (Madau 1999)
    '''
    tmax=COSMO.age(np.min([kwargs['zmin'],zlow]))
    tmin=COSMO.age(kwargs['zmax'])
    taxis=np.linspace(tmin,tmax,ntimes)#times in Gyr
    dt=taxis[1]-taxis[0]
    zaxis=COSMO.age(taxis,inverse=True)#z axis
    qvals=np.zeros_like(taxis)
    qvals_he=np.zeros_like(taxis)
    qdots=np.zeros_like(taxis)
    qdots_he=np.zeros_like(taxis)
    dtaus=np.zeros_like(taxis)
    taus=np.zeros_like(qvals)
    #nH0=(1.-YP)/(1.-.75*YP)*COSMO.rho_b(0.)*(1e3)**3.*MSOL/MP#hydrogen number density at z=0 in coMpc^-3
    nH0=(1.-YP)*COSMO.rho_b(0.)*(1e3)**3.*MSOL/MP#hydrogen number density at z=0 in h^3coMpc^-3
    nH0cm=nH0/(1e3*KPC*1e2)**3./LITTLEH**3.#hydrogen density at z=0 in cm^-3
    chi=YP/4./(1.-YP)
    nHe0cm=chi*nH0cm
    nHe0=chi*nH0
    for tnum in range(1,len(qvals)):
        tval,zval=taxis[tnum-1],zaxis[tnum-1]
        crr=2.9*((1.+zval)/6.)**(-1.1)#clumping factor
        trec=1./(crr*(1+chi)*nH0cm*(1.+zval)**3.*2.6e-13*(T4)**-.7)/1e9/YR# trec in Gyr
        trec_he=1./((1.+2.*chi)*nH0cm*(1.+zval)**3.*2*2.6e-13*(T4/4)**-.7*crr)/1e9/YR
        #print trec
        #if not(norec):
        if zval>=kwargs['zmin']:
            qdots[tnum-1]=.9*fesc*ndot_ion(zval,**kwargs)/nH0*1e9*YR-qvals[tnum-1]/trec
            qdots_he[tnum-1]=.1*fesc*ndot_ion(zval,**kwargs)/nHe0*1e9*YR-qvals_he[tnum-1]/trec_he
        else:
            qdots[tnum-1]=-qvals[tnum-1]/trec
            qdots_he[tnum-1]=-qvals_he[tnum-1]/trec_he
        #else:
        #    qdot=fesc*ndot_ion(zval,**kwargs)/nH0*1e9*YR
        qvals[tnum]=np.min([1.,qvals[tnum-1]+dt*qdots[tnum-1]])
        qvals_he[tnum]=np.min([1.,qvals_he[tnum-1]+dt*qdots_he[tnum-1]])
        dz=-zaxis[tnum]+zaxis[tnum-1]
        DHcm=3e5/COSMO.H0*1e3*1e2*KPC
        dtaus[tnum-1]=DHcm*nH0cm*SIGMAT*(1.+zval)**2./COSMO.Ez(zval)*\
        (qvals[tnum-1]*(1+chi)+qvals_he[tnum-1]*chi)*dz
        taus[tnum]=taus[tnum-1]+dtaus[tnum-1]
    #print fesc*ndot_ion(zval,**kwargs)*1e9*YRs
    #print nH0
    return zaxis,taxis,qvals,taus,qdots,dtaus
