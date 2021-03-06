#
#cosmology utility functions
#
import numpy as np
import os
import scipy.integrate as integrate
import scipy.interpolate as interpolate
import scipy.optimize as op
from settings import COSMO, MP, MSOL, LITTLEH,PI,BARN,E_HI_ION,E_HEI_ION, DH
from settings import E_HEII_ION,SIGMAT,F_H,F_HE,A10,TCMB0,NH0_CM,YP,KPC,YR,C,G
from settings import POP_III_ION,POP_II_ION,DIRNAME,TH,KBOLTZMANN,ERG,RY_KEV, KEV
from colossus.lss import mass_function
from colossus.lss import bias as col_bias
from settings import SPLINE_DICT
import scipy.interpolate as interp
from settings import LY_N_ALPHA_SWITCH,HPLANCK_EV,HPLANCK_KEV,KBOLTZMANN_KEV
from settings import NSPEC_MAX
import scipy.special as sp
A_ST=0.3222
B_ST=0.707
P_ST=0.3

#import pyccl as ccl
#COSMO_CCL = ccl.Cosmology(Omega_c=0.27, Omega_b=0.045, h=0.67,
#A_s=2.1e-9, n_s=0.96, Omega_k=0.)
#*********************************************************
#utility functions
#*********************************************************
def dict2tuple(dictionary):
    '''
    Convert a dictionary to a tuple of alternating key values
    and referenced values.
    Example: {'apple':0,'beta':2000} -> ('apple',0,'beta',20000)
    Args:
        dict, dictionary
    Returns:
        tuple of (key0, value0, key1, value1, key2, value2, ...)
    '''
    output=()
    for key in dictionary.keys():
        if isinstance(dictionary[key],dict):
            output=output+dict2tuple(dictionary[key])
        else:
            output=output+(key,dictionary[key])
    return output
def dict2string(dictionary):
    '''
    Convert dictionary to a string
    '''
    outout=''
    for key in diciontary.keys():
        if isinstance(dictionary[key],dict):
            output=output+dict2string(dictionary[key])
        else:
            output=output+','+str(key)+':'+dictionary[key]
#**********************************************************
#cosmology utility functions
#**********************************************************
def massfunc(m,z,model='tinker08',mdef='200m'):
    '''
    dark matter mass function dN/dlog_10M/dV (h^3 Mpc^-3)
    Args:
        mass, float, msolar/h
        z, float, redshift
        model, string, dark matter prescription (see colossus documentation)
        mdef, string, mass definition.
    Returns:
        dark matter mass function dN/dlog_10M/dV (h^3 Mpc^-3)
    '''
    return mass_function.massFunction(m,z,mdef=mdef,model=model,
    q_out='dndlnM')*np.log(10.)
    #return ccl.massfunc(COSMO_CCL,m/LITTLEH,1./(1.+z))*LITTLEH**2.


def bias(mvir,z,mode='tinker10',mdef='200m'):
    '''
    halo bias
    Args:
        mvir, virial mass [msol/h] (float)
        z, redshift (float)
        mode, string, specify mass function and mass function to be used
        (see https://bdiemer.bitbucket.io/colossus/)
    Returns:
        float, bias for halos with mass mvir
    '''
    return col_bias.haloBias(mvir, model = 'tinker10', z = z,mdef=mdef)


def sigma(m,z,derivative = False):
    '''
    sigma for tophat filtered density field at mass m.
    Args:
        mass, (msol/h)
        z, redshift
        derivative, if true, return - d ln \sigma / dm
    Returns:
        standard deviation of density field smoothed on mass scale (m) at
        redshift z.
    '''
    #print('m=%.2e'%m)
    r=(3./4./PI*m/COSMO.rho_m(0.))**(1./3.)/1e3
    if not derivative:
        return COSMO.sigma(r,z)
    else:
        return -1./3.*COSMO.sigma(r,z,derivative=True) * m**-1.

def nu(z,m,d=False):
    '''
    delta_crit/sqrt(2.*sigma**2.)
    Args:
        z, float, redshift
        m, halo mass, (msol/h)
        d, (if True, compute the derivative with respect to z)
    Returns:
        delta_crit/sqrt(2.*sigma**2.) (unitless)
    '''
    if not d:
        output=1.686/COSMO.growthFactor(z)/np.sqrt(2.)/sigma(m,0.)\
        *COSMO.Om(z)**0.0055
    else:
        ai=(1.+z)
        pnumer=9.*COSMO.Om0*ai**8.+10.*COSMO.Or0*ai**9.\
        +8.*COSMO.Ok0*ai**7.+6.*COSMO.Ode0*ai**5.
        pdenom=COSMO.Om0*ai**9.+COSMO.Or0*ai**10.+COSMO.Ok0*ai**8.\
        +COSMO.Ode0*ai**6.
        output=-nu(z,m,d=False)*(COSMO.growthFactor(z,derivative=True)\
        /COSMO.growthFactor(z,derivative=False)+0.0055/2\
        *pnumer/pdenom)
    return output

def rho_collapse_st(mmin,mmax,z,fractional=False, number = False, verbose=False):
    '''
    Compute the comoving density of collapse matter or fraction of matter collapsed
    in halos between mass mmin and mmax at redshift z \
    Using Sheth Tormen mass function.
    Args:
        mmin, minimum halo mass (msolar/h)
        mmax, maximum halo mass (msolar/h)
        z, redshift
        fractional, if true, return fraction of density in halos, if false,
                    return comoving density in halos.
        number, if true, return number of halos between mmin and mmax
        (rather than density)
    Returns:
        density (msol/Mpc^3 h^2) or 'dimensionless' if fractional=True or
        Mpc^-3 h^2 if number.
    '''
    assert not(fractional and number)
    nmax=nu(z,mmax)
    nmin=nu(z,mmin)

    if not number:
        lower=-sp.erf(B_ST**.5*nmin)-2.**(-P_ST)\
        *sp.gamma(.5-P_ST)*sp.gammainc(.5-P_ST,B_ST*nmin**2.)
        upper=sp.erf(B_ST**.5*nmax)+2.**(-P_ST)\
        *sp.gamma(.5-P_ST)*sp.gammainc(.5-P_ST,B_ST*nmax**2.)
        output=upper+lower
        output*=A_ST
        if verbose:print('not number, lower=%.2e'%lower)
        if verbose:print('not number, upper=%.2e'%upper)

    else:
        limlow = np.log(mmin)
        limhigh = np.log(mmax)
        g = lambda x: 2.*A_ST*np.sqrt(B_ST/PI)*(1.+(.5*nu(z,np.exp(x))**-2./B_ST)**P_ST)\
        * nu(z,np.exp(x)) * np.exp(- nu(z,np.exp(x))**2.*B_ST) * sigma(np.exp(x), z, derivative = True)
        output = integrate.quad(g,limlow,limhigh)[0]
        if verbose:print('number, output=%.2e'%output)
    if not fractional:
        output = COSMO.rho_m(0.)*1e9*output
    return output


def delta(z):
    '''
    critical density from Bryan and Norman 1998
    Args:
         z, float, redshift
    Returns:
         collapsed virial density relative to mean density
    '''
    x=COSMO.Om(z)-1.
    return 18.*PI*PI+82.*x-39.*x*x

def tvir(mhalo,z,mu=1.22):
    '''
    virial temperature of a halo with dark matter mass mhalo
    Args:
        mhalo: (msolar/h)
        z: redshift
        mu: mean molecular weight of hydrogen, 1.22 for neutral,
        0.59 for ionized,
        0.61 for ionized gas and singly ionized helium
    Returns:
        Virial temperature of halo in Kelvin using equation 26 from Barkana+2001
    '''
    return 1.98e4*(mu/.6)*(mhalo/1e8)**(2./3.)\
    *(COSMO.Om(0.)/COSMO.Om(z)*delta(z)/18./PI/PI)**(1./3.)*((1.+z)/10.)


def tvir2mvir(t,z,mu=1.22):
    '''
    convert from virial temperature to halo mass
    Args:
        t, temperature (K)
        z, redshift
        mu, mean molecular weight of gas
    Returns:
        dark-matter halo mass corresponding to virial temperature tvir in Msol/h
    '''
    return 1e8*(t/tvir(1e8,z,mu))**(3./2.)


def stellar_spectrum(E_uv_in,pop='II',**kwargs):
    '''
    Stellar UV spectrum (Barkana 2001).
    Args:
        E_uv, float, energy of photon (eV)
        pop, string, 'II' or 'III'
        kwargs, dictionary containing model parameters
    Returns:
        Number of UV photons as a fraction of the number of ionizing photons
        per energy interval in units of lyman-alpha transition Energy
        (number/E_lyalpha)
    '''
    E_uv=E_uv_in/(.75*1e3*E_HI_ION)#Units of ly-alpha energy
    splkey=('stellar_spectrum',pop)
    if not splkey in SPLINE_DICT:
        stellar_data=np.loadtxt(DIRNAME+'/../tables/stellar_spectra.dat')
        if pop=='II':
            SPLINE_DICT[('stellar_spectrum',pop)]=\
            np.vstack([stellar_data[:,0],
            stellar_data[:,1],stellar_data[:,2]]).T
        elif pop=='III':
            SPLINE_DICT[('stellar_spectrum',pop)]=\
            np.vstack([stellar_data[:,0],
            stellar_data[:,3],stellar_data[:,4]]).T
    #Figure out the order of the transition.
    nval=np.floor(1./np.sqrt(1.-E_uv*.75)).astype(int)
    #print nval
    E_n=4.*(1.-1./nval**2.)/3.
    E_np=4.*(1.-1./(nval+1)**2.)/3.
    #print SPLINE_DICT[splkey]
    if isinstance(E_uv,float):
        if nval<2 or nval>=NSPEC_MAX:
            return 0.
        else:
            #print(nval)
            #print(SPLINE_DICT[splkey].shape)
            norm_factor=SPLINE_DICT[splkey][nval-2,1]
            alpha=SPLINE_DICT[splkey][nval-2,2]
            output=norm_factor*(1.+alpha)\
            /(E_np**(1.+alpha)-E_n**(1.+alpha))*E_uv**alpha
    else:
        output=np.zeros_like(E_uv)
        select=np.logical_and(nval>=2,nval<=NSPEC_MAX)
        norm_factor=SPLINE_DICT[splkey][nval[select]-2,1]
        alpha=SPLINE_DICT[splkey][nval[select]-2,2]
        output[select]=norm_factor*(1.+alpha)\
        /(E_np[select]**(1.+alpha)-E_n[select]**(1.+alpha))*E_uv**alpha
    #convert from 1/Ly-alpha energy to 1/energy (eV)
    return output/(E_HI_ION*1e3*.75)#fraction of ionization photon Number
                                    #per lyman-alpha energy


def vVir(m,z):
    '''
    virial velocity of halo in km/sec
    from Maller and Bullock 2004
    Args:
         m,float,mass of halo in solar masses/h
         z,float,redshift
    Returns:
        float, circular virial velocity of dark
        matter halo (km/sec)
    '''
    return 144.*(COSMO.Om(z)*delta(z)/97.2)**(1./6.)\
    *(m/1e12)**(1./3.)*(1.+z)**.5

def rVir(m,z):
    '''
    virial radius (coMpc/h)
    from Maller and Bullock 2004
    Args:
        m,float,mass from halo in msolar/h
        z,float,redshift
    Returns:
        virial radius of DM halo. (coMpc/h)
    '''
    return 206.*(COSMO.Om(z)*delta(z)/97.2)**(-1./3.)\
    *(m/1e12)**(1./3.)*(1.+z)**-1.*1e-3*(1.+z)

#*******************************************
#Atomic Data/Info
#*******************************************
def sigma_HLike(e,z=1.):
    '''
    gives ionization cross section in cm^2 for an X-ray with energy ex (keV)
    for a Hydrogen-like atom with atomic number Z
    Args:
        e, float, photon energy (in keV)
        z, atomic number
    Returns:
        photo-ionization cross section, float, (cm^2)
    '''
    ex=e*1e3 #input energy in keV, convert to eV
    e1=13.6*z**2.
    if isinstance(ex,float):
        if ex<e1:
            return 0.
        else:
            eps=np.sqrt(ex/e1-1.)
            return 6.3e-18*(e1/ex)**4.*np.exp(4.-(4.*np.arctan(eps)/eps))/\
            (1-np.exp(-2.*PI/eps))/z/z
    else:
        output=np.zeros_like(ex)
        select=ex>=e1
        eps=np.sqrt(ex[select]/e1-1.)
        output[select]=6.3e-18*(e1/ex[select])**4.\
        *np.exp(4.-(4.*np.arctan(eps)/eps))/(1.-np.exp(-2.*PI/eps))/z/z
        return output

def sigma_HeI(e):
    '''
    gives ionization cross section in cm^2 for X-ray of energy ex (keV)
    for HeI atom.
    Args:
        e, energy of ionizing photon (keV)
    Returns:
        photo-ionization cross section(cm^2)
    '''
    ex=e*1e3#input energy is in keV, convert to eV
    if isinstance(ex,float):
        if ex>=2.459e1:
            e0,sigma0,ya,p,yw,y0,y1=1.361e1,9.492e2,1.469,3.188,2.039,4.434e-1,2.136
            x=ex/e0-y0
            y=np.sqrt(x**2.+y1**2.)
            fy=((x-1.)**2.+yw**2.)*y**(0.5*p-5.5)\
            *np.sqrt(1.+np.sqrt(y/ya))**(-p)
            return fy*sigma0*BARN*1e6#Last factor converts from Mbarnes to cm^-2
        else:
            return 0.
    else:
        output=np.zeros_like(ex)
        select=ex>=2.459e1
        e0,sigma0,ya,p,yw,y0,y1=1.361e1,9.492e2,1.469,3.188,2.039,4.434e-1,2.136
        x=ex/e0-y0
        y=np.sqrt(x**2.+y1**2.)
        fy=((x-1.)**2.+yw**2.)*y**(0.5*p-5.5)\
        *np.sqrt(1.+np.sqrt(y/ya))**(-p)
        output[select]=fy[select]*sigma0*BARN*1e6#Last factor converts from Mbarnes to cm^-2
        return output

#*******************************************
#initialize interpolation x_int_tables
#*******************************************
def init_interpolation_tables():
    '''
    Initialize interpolation tables for number of ionizing electrons produced
    per ionization of H, He, HI, fraction of energy deposited in heating and
    fraction deposited in ionization.
    Credit Mesinger 2011 for interpolation tables
    https://github.com/andreimesinger/21cmFAST
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
    4.677e-3,1.0e-2,2.318e-2,4.677e-2,1e-1,.5,.9,.99,.999])
    for tname,xi in zip(table_names,SPLINE_DICT['xis']):
        itable=np.loadtxt(DIRNAME+'/../tables/'+tname,skiprows=3)
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
    if xi>SPLINE_DICT['xis'].min() and xi<SPLINE_DICT['xis'].max():
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
    elif xi<=SPLINE_DICT['xis'].min():
        xi=SPLINE_DICT['xis'].min()
        if e_kev<SPLINE_DICT[('min_e_kev',xi)]:
            e_kev=SPLINE_DICT[('min_e_kev',xi)]
        if e_kev>SPLINE_DICT[('max_e_kev',xi)]:
            e_kev=SPLINE_DICT[('max_e_kev',xi)]
        return SPLINE_DICT[(mode,xi)](e_kev)
    elif xi>=SPLINE_DICT['xis'].max():
        xi=SPLINE_DICT['xis'].max()
        if e_kev<SPLINE_DICT[('min_e_kev',xi)]:
            e_kev=SPLINE_DICT[('min_e_kev',xi)]
        if e_kev>SPLINE_DICT[('max_e_kev',xi)]:
            e_kev=SPLINE_DICT[('max_e_kev',xi)]
        return SPLINE_DICT[(mode,xi)](e_kev)
    else:
        print('xi='+str(xi))


def heating_integrand(ex,xe,jxf):
    '''
    energy injected
    per baryon for X-rays between ex and
    ex+dex
    Args:
        ex, x-ray energy
        xe, ionized fraction
        jxf,X-ray intensity function (keV/sec)/keV/cm^2/sr
    '''
    pfactor=4.*PI*jxf(ex)

    ex_hi=np.max([ex-E_HI_ION,0.])
    ex_hei=np.max([ex-E_HEI_ION,0.])
    ex_heii=np.max([ex-E_HEII_ION,0.])

    hi_rate=ex_hi*(1.-xe)*sigma_HLike(ex)*F_H\
    *interp_heat_val(ex_hi,xe,'f_heat')
    hei_rate=ex_hei*(1.-xe)*sigma_HeI(ex)*F_HE\
    *interp_heat_val(ex_hei,xe,'f_heat')
    heii_rate=ex_heii*xe*sigma_HLike(ex,z=2.)*F_HE\
    *interp_heat_val(ex_heii,xe,'f_heat')

    return pfactor*(hi_rate+hei_rate+heii_rate)

def ionization_integrand(ex,xe,jxf):
    pfactor = 4.*PI*jxf(ex)
    return pfactor*ion_sum(ex,xe)

def xray_lyalpha_integrand(ex,xe,jxf):
    '''
    number of lyman alpha photons emitted
    per baryon for X-rays between ex and
    ex+dex
    Args:
        ex, x-ray energy
        xe, ionized fraction
        jxf,X-ray intensity function (keV/sec)/keV/cm^2/sr
    Returns: number of lyman alpha photons emitted per baryon
    '''
    pfactor=4.*PI*jxf(ex)

    ex_hi=np.max([ex-E_HI_ION,0.])
    ex_hei=np.max([ex-E_HEI_ION,0.])
    ex_heii=np.max([ex-E_HEII_ION,0.])

    hi_rate=(1.-xe)*sigma_HLike(ex)*F_H\
    *interp_heat_val(ex_hi,xe,'n_Lya')
    hei_rate=(1.-xe)*sigma_HeI(ex)*F_HE\
    *interp_heat_val(ex_hei,xe,'n_Lya')
    heii_rate=xe*sigma_HLike(ex,z=2.)*F_HE\
    *interp_heat_val(ex_heii,xe,'n_Lya')

    return pfactor*(hi_rate+hei_rate+heii_rate)



def ion_sum(ex,xe):
    '''
    \sum_{i,j}(hnu-E^th_j)*(fion,HI/E^th_j)f_i x_i \sigma_i
    for hnu=ex
    and ionized IGM fraction xe
    Args:
        ex, energy of photon, float
        xe, electron fraction (float)
    Returns:
        number of ionizations that occur per photon flux unit with energy ex
        [cm^2 ]
    '''
    #extra energies not deposited into ionization
    e_hi=ex-E_HI_ION
    e_hei=ex-E_HEI_ION
    e_heii=ex-E_HEII_ION

    #number of ionizations that occur from H-ionization
    fi_hi=interp_heat_val(e_hi,xe,'n_{ion,HI}')\
    +interp_heat_val(e_hi,xe,'n_{ion,HeI}')\
    +interp_heat_val(e_hi,xe,'n_{ion,HeII}')+1.
    fi_hi=fi_hi*(F_H*(1-xe))*sigma_HLike(ex)
    #number of ionizations that occur from HeI-ionization
    fi_hei=interp_heat_val(e_hei,xe,'n_{ion,HI}')\
    +interp_heat_val(e_hei,xe,'n_{ion,HeI}')\
    +interp_heat_val(e_hei,xe,'n_{ion,HeII}')+1.
    fi_hei=fi_hei*(F_HE*(1-xe))*sigma_HeI(ex)
    #number of ionizations that occur from HeII-ionization
    fi_heii=interp_heat_val(e_heii,xe,'n_{ion,HI}')\
    +interp_heat_val(e_heii,xe,'n_{ion,HeI}')\
    +interp_heat_val(e_heii,xe,'n_{ion,HeII}')+1.
    fi_heii=fi_heii*(F_HE*xe*sigma_HLike(ex,z=2.))

    return fi_hi+fi_hei+fi_heii



def alpha_B(T4):
    '''
    Case-B recombination coefficient
    for neutral gas at T4x10^4K
    Returns cm^3, sec^-1. Applies to situation
    where photon is not re-absorbed by nearby Hydrogen
    '''
    return 2.6e-13*(T4)**-.7

def alpha_A(T4):
    '''
    Case-A recombination coefficient
    for ionized gas at T4x10^4K
    Returns cm^3, sec^-1. Applies to situation
    where photon is re-absorbed by nearby Hydrogen
    '''
    return 4.2e-13*(T4)**-.7

def clumping_factor(z):
    '''
    Clumping factor at redshift z
    Madau 2017
    '''
    return 2.9*((1.+z)/6.)**(-1.1)
    #return 27.466*np.exp(-0.114*z+0.001328*z*z)

def kappa_10_HH(tk):
    '''
    kappa_10 collisional rate for HH collisions
    in cm^3/sec
    Args:
        tk, kinetic temperature (Kelvin)
    Credit Mesinger 2011 for interpolation tables
    https://github.com/andreimesinger/21cmFAST
    '''
    splkey=('kappa_10','HH')
    if not splkey in SPLINE_DICT:
        kappa_array=\
        np.array([[1.,1.38e-13],
                  [2.,1.43e-13],
                  [4.,2.71e-13],
                  [5.,6.60e-13],
                  [8.,1.47e-12],
                  [10.,2.88e-12],
                  [15.,9.10e-12],
                  [20.,1.78e-11],
                  [25.,2.73e-11],
                  [30.,3.67e-11],
                  [40.,5.38e-11],
                  [50.,6.86e-11],
                  [60.,8.14e-11],
                  [70.,9.25e-11],
                  [80.,1.02e-10],
                  [90.,1.11e-10],
                  [100.,1.19e-10],
                  [200.,1.75e-10],
                  [300.,2.09e-10],
                  [501.,2.565e-10],
                  [701.,2.91e-10],
                  [1000.,3.31e-10],
                  [2000.,4.27e-10],
                  [3000.,4.97e-10],
                  [5000.,6.03e-10],
                  [7000.,6.87e-10],
                  [1e4,7.87e-10]])
        SPLINE_DICT[splkey]=interp.interp1d(np.log10(kappa_array[:,0]),
        np.log10(kappa_array[:,1]))
    if isinstance(tk,float) or isinstance(tk,np.float64):
        if tk<1.:
            tk=1.
        if tk>1e4:
            tk=1e4
    else:
        tk[tk<1.]=1.
        tk[tk>1e4]=1e4
    return 10.**SPLINE_DICT[splkey](np.log10(tk))

def kappa_10_eH(tk):
    '''
    Kappa in cm^3/sec for e-H collisions
    Args:
        tk, kinetic temperature (kelvin)
    Credit Mesinger 2011 for interpolation tables
    https://github.com/andreimesinger/21cmFAST
    '''
    splkey=('kappa_10','eH')
    if not splkey in SPLINE_DICT:
        kappa_eH_data=np.loadtxt(DIRNAME+'/../tables/kappa_eH_table.dat')
        SPLINE_DICT[splkey]=interp.interp1d(np.log10(kappa_eH_data[:,0]),
        np.log10(kappa_eH_data[:,1]))
    if isinstance(tk,float) or isinstance(tk,np.float64):
        if tk<1.:
            tk=1.
        if tk>1e5:
            tk=1e5
    else:
        tk[tk<1.]=1.
        tk[tk>1e5]=1e5
    return 10.**SPLINE_DICT[splkey](np.log10(tk))
def kappa_10_pH(tk):
    '''
    Kappa in cm^3/sec for p-H collisions
    Args:
        tk, kinetic temperature (kelvin)
    Credit Mesinger 2011 for interpolation tables
    https://github.com/andreimesinger/21cmFAST
    '''
    splkey=('kappa_10','pH')
    if not splkey in SPLINE_DICT:
        kappa_pH_data=np.loadtxt(DIRNAME+'/../tables/kappa_pH_table.dat')
        SPLINE_DICT[splkey]=interp.interp1d(np.log10(kappa_pH_data[:,0]),
        np.log10(kappa_pH_data[:,1]))
    if isinstance(tk,float) or isinstance(tk,np.float64):
        if tk<1.:
            tk=1.
        if tk>2e4:
            tk=2e4
    else:
        tk[tk<1.]=1.
        tk[tk>2e4]=2e4
    return 10.**SPLINE_DICT[splkey](np.log10(tk))

def x_coll(tk,xe,z,tr):
    '''
    collisional coupling constant
    Args:
        tk, kinetic temperature (kelvin)
        xe, ionization fraction of Hydrogen and Helium I
        z, redshift
    '''
    return 0.0628/(tr+TCMB0*(1.+z))/A10*(kappa_10_HH(tk)*(1.-xe)\
    +xe*(kappa_10_eH(tk)+kappa_10_pH(tk)))*NH0_CM*(1.+z)**3.



def tau_GP(z,xe):
    '''
    Gunn-Peterson Optical depth in neutral IGM
    Args:
        z=redshift
        xe=ionization fraction
    '''
    return 1.342881e-7/COSMO.Hz(z)*(1.-xe)*NH0_CM*(1.+z)**3.

def s_alpha_tilde(tk,ts,z,xe):
    '''
    S_\alpha, fitted in Hirata 2006 Equation 40
    Args:
        tk, kinetic temperature (Kelvin)
        ts, spin temperature (Kelvin)
        xe, ionized fraction outside of HII regions
        z, redshift
    '''
    taugp=tau_GP(z,xe)
    xi=(1e-7*taugp/tk/tk)**(1./3.)
    return (1.0-0.0631789/tk+0.115995/tk/tk\
    -0.401403/ts/tk+0.336463/ts/tk/tk)\
    /(1.+2.98394*xi+1.53583*xi*xi+3.85289*xi*xi*xi)

def s_alpha(tk,ts,z,xe):
    '''
    s_apha
    '''
    return s_alpha_tilde(tk,ts,z,xe)*(1./tc_eff(tk,ts)-1./ts)\
    /(1./tk-1./ts)

def tc_eff(tk,ts):
    '''
    effective color temperature
    Hirata 2006 equation 42
    args:
        tk, kinetic temperature
        ts, spin temperature
    '''
    return (1./tk+0.405535/tk*(1./ts-1./tk))**-1.

def xalpha_over_jalpha(tk,ts,tr,z,xe):
    '''
    Ly-alpha coupling constant/Ly-alpha flux
    Args:
        tk, kinetic temperature (kelvin)
        ts, spin temperature (kelvin)
        tr, 21-cm brightness temperature background (including CMB+sources)
        xe, ioniszation fraction
    '''
    return s_alpha_tilde(tk,ts,z,xe)*1.66e11*TCMB0/(tr+TCMB0*(1.+z))

def pn_alpha(n):
    '''
    probability of a photon being absorbed at lyman-n transition is re-emitted
    as a ly-alpha photon.
    '''
    if isinstance(n,int):
        if n<=30 and n>=0:
            return LY_N_ALPHA_SWITCH[n]
        else:
            return 0.
    elif isinstance(n,np.ndarray):
        ouput=np.zeros_like(n)
        selection=np.logical_and(n>=0,n<=30)
        output[selection]=\
        np.vectorize(lambda x: LY_N_ALPHA_SWITCH[int(x)])(n[selection])
        return ouput

def zmax(z,n):
    '''
    return maximum redshift for Ly-alpha photons
    '''
    return (1.+z)*(1.-(1.+n)**-2.)/(1.-n**-2.)-1.

def e_ly_n(n):
    '''
    energy (in eV) for n->1 lyman series transition
    '''
    return E_HI_ION*1e3*(1.-n**-2.)

def tspin(xc,ja,tk,trad,z,xe):
    '''
    spin temperature from couplign constants
    Args:
        xc, collisional coupling
        xa, ly-alpha coupling
        tk, kinetic temperature
        tc, ly-alpha color temperature
        tcmb, cmb temperature
        trad, additional radio background.
    '''
    #Only do this if there is a ly-alpha background
    tcmb=TCMB0*(1.+z)
    if ja>1e-20:
        ts=tcmb+trad
        ts_old=0.
        ta=tc_eff(tk,ts)#+tcmb
        xa=xalpha_over_jalpha(tk,ts,trad,z,xe)*ja
        while(np.abs(ts-ts_old)/ts>1e-3):
            ts_old=ts
            xa=xalpha_over_jalpha(tk,ts,trad,z,xe)*ja
            ta=tc_eff(tk,ts)#+tcmb
            ts=(1.+xa+xc)/(1./(trad+tcmb)+xa/ta+xc/tk)
    else:
        ts=(xc+1)/(xc/tk+1./(trad+tcmb))
        xa=0.
        ta=tcmb
    return ts,ta,xa


def tc_eff(tk,ts):
    '''
    ly-alpha color temperature
    '''
    return (1./tk+0.405535/tk*(1./ts-1./tk))**-1.


def n_h(m,z,cs=1.):
    '''
    column density from the center of a tophat halo.
    (cm^-2)
    Args:
        m, halo mass
        z, redshift
        cs, concentration parameter
    '''
    rval=rVir(m,z)*1e2*1e3*KPC/(1.+z)/LITTLEH/cs
    return (m*COSMO.Ob(0.)/COSMO.Om(0.)*(MSOL/LITTLEH))/(1.25*PI*MP*rval**2.)\
    *(1.-YP)/(1.-.75*YP)


def gamma_c(tg,nmax=20, gff = 1.1, gfb = lambda x: 1.05):
    '''
    continuum emission coefficient from free-free and
    bound-free electron collisions (Fernandez 2006)
    Args:
        tg, gas temperature (Kelvin)
        nmax, number of bound-free terms in sum include (default = 20)
        gff, free-free gaunt factor
        gfb, bound-free gaunt factor.
    Returns:
        continuum emission coefficient (keV K^1/2 cm^3 kev^-1 sec^-1)
    '''
    nvals = np.arange(2,nmax+1)
    xvals = (RY_KEV/(KBOLTZMANN_KEV*tg*nvals**2.))
    output = 5.44e-39 * ( gff + np.sum(gfb(nvals)*np.exp(xvals)*xvals/nvals ))
    #convert from ergs to kev
    return output * ERG / KEV / HPLANCK_KEV



def labs_over_q(**kwargs):
    '''
    determine the ratio between the absorbed luminosity and rate of ionizing photon
    production
    Args:
        dictionary with parameters determining emission spectrum
    Returns:
        L_abs/Q_H (keV)
    '''
    eabs = lambda x: np.exp(-10.**kwargs['LOG10_N']*sigma_HLike(x))
    g = lambda x: (x/.2)**(-kwargs['ALPHA_X'])*np.exp(-x/300.)*(1.-eabs(x))
    h = lambda x: (x/.2)**(-kwargs['ALPHA_O2'])*(1.-eabs(x))

    j = lambda x: (1. + (1./3.)*(x/RY_KEV-1.))*g(x)/x
    k = lambda x: h(x)/x
    output = integrate.quad(g,.2,np.inf)[0] + integrate.quad(h,RY_KEV,.2)[0]
    output = output/(integrate.quad(k,RY_KEV,.2)[0]+integrate.quad(j,.2,np.inf)[0])
    return output




def p_lya(y):
    '''
    probability distribution of 2-photon lyman-alpha emission (Fernandez 2006)
    Args:
        y = \nu / \nu_\alpha
    Returns:
        p(y) [units of dimensionless y^-1], \int_0^1 p(y) ~ 1
    '''
    if y>=0. and y<=1.:
        return 1.307 - 2.627 * (y - .5)**2. + 2.563 * (y-.5)**4. -51.69 * (y-.5)**6.
    else:
        return 0.

coeffs_lt = {'2p':np.array([3.435e-1,1.297e-5,2.178e-12,7.928e-17]),
             '3s':np.array([6.25e-2,-1.299e-6,2.666e-11,3.973e-16]),
             '3d':np.array([5.03e-2,7.514e-7,-2.826e-13,-1.098e-17])}
coeffs_ht = {'2p':np.array([3.162e-1,1.472e-5,-8.275e-12,-9.794e-19]),
             '3s':np.array([3.337e-2,2.223e-7,-2.794e-13,-1.29e-18]),
             '3d':np.array([5.051e-2,7.876e-7,2.072e-12,1.902e-18])}
degeneracies = {'2p': 6, '3s': 2,'3d': 10}

def qcoll(transition,tg):
    '''
    collisional excitation coefficient from hydrogen ground
    (Cantalupo,Porciani, Lilly. 2006)
    Args:
        transition: excited electron state (2p, 2s, 3d)
        tg, gas temperature (K)
    Returns:
        collisional excitation coefficient in cm^3 s^-1
    '''
    g = degeneracies[transition]
    n = float(transition[0])
    if tg > 5e4: coeffs = coeffs_ht[transition]
    else: coeffs = coeffs_lt[transition]
    gamma = np.dot(coeffs,tg**np.arange(4))
    return 8.629e-6*gamma/g/tg**.5*np.exp(-RY_KEV*(1.-1./n**2.)/KBOLTZMANN_KEV/tg)

def c_coll(tg):
    '''
    collisional excitation rates from ground summed over dominant excited states
    (Cantalupo,Porciani, Lilly. 2006)
    Args:
        tg, gas temperature
    Returns:
        sum of excitation rates from Hydrogen ground state (cm^3 s^-1). Sum
        is approximated by first few dominant terms.
    '''
    return qcoll('2p',tg) + qcoll('3s',tg) + qcoll('3d',tg)


def solve_t(**kwargs):
    '''
    find equilibrium temperature of a nebula around black hole by
    setting emission luminosity in IR equal to absorbed energy
    Args:
        spectral parameters
    Returns:
        equilibrium temperature of nebular gas.
    '''
    splkey = dict2tuple(kwargs)+('temperature',0)
    if not splkey in SPLINE_DICT:
        loq = labs_over_q(**kwargs)
        g = lambda t: KBOLTZMANN_KEV*t*4.*np.pi*gamma_c(t)/t**.5/alpha_B(t/1e4) \
        + 2.*RY_KEV*(1-.25)*.53*(1.+(1.-.5)/.5*c_coll(t)/alpha_B(t/1e4)) - loq
        SPLINE_DICT[splkey] = op.fsolve(lambda x: g(x),x0=[1e3])[0]
        print('T=%.2f'%SPLINE_DICT[splkey])
    return SPLINE_DICT[splkey]

def dvc(z):
    '''
    comoving volume element (Mpc/h)^3
    Args:
        z, redshift, float
    returns;
        comoving volume element dvc/ dz /d omega
    '''
    return  DH*(COSMO.angularDiameterDistance(z)*(1.+z))**2./ COSMO.Ez(z)*LITTLEH
