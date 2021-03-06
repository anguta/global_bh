import numpy as np
import os
from colossus.cosmology import cosmology
TCMB0=2.73
PI=np.pi
ARAD=7.5657e-16#J/m^3/K^4 radiation constant
F21=1420405751.7667 #HI hyperfine line frequency (Hz)
KBOLTZMANN=1.38064852e-23#Boltzmann Constant in Joules/Kelvin
ERG=1e-7#ERG in Joules
C=3e5#speed of light (km/sec)
#C=3e8#speed of light in m/sec
NSPEC_MAX=23
KPC=3.068e19#kpc in meters
COSMO=cosmology.setCosmology('planck15')
LITTLEH=COSMO.H0/100.
TH=(.7/LITTLEH)*13.98#Hubble time in Gyr
DH=C/COSMO.H0#Hubble Distance
TEDDINGTON=.45#EDDINGTON E-folding time (Gyr)
SPLINE_DICT={}
MP=1.6726219e-27#Proton mass in kg
ME=9.10938356e-31#Electron mass in kg
MSOL=1.99e30#solar mass in kg
PI=np.pi
AU=1.496e11
BARN=1e-24#cm^2
G=6.67408e-11#gravitational constant in m^3 /kg^2/s
MBH_INTERP_MIN=-3.
MBH_INTERP_MAX=7.
N_INTERP_MBH=100
Z_INTERP_MIN=10.
Z_INTERP_MAX=40.
N_INTERP_Z=1000
M_INTERP_MIN=1.
M_INTERP_MAX=17.
N_INTERP_M=100
N_TSTEPS=1000
N_INTERP_X=100
KEV=1.60218e-16
EV=1.60218e-19
JY=1e-26
LEDD=1.26e31#Eddington luminosity in Watts/Msolar
E_HI_ION=13.6/1e3#keV
E_HEII_ION=4.*E_HI_ION/1e3#keV
E_HEI_ION=24.7/1e3#keV
SIGMAT=6.65246e-25#cm^2 Thompson cross-section
HPLANCK = 6.62607004e-34
HPLANCK_KEV=HPLANCK / KEV #planck constant in keV seconds
HPLANCK_EV=HPLANCK / EV #planck constant in eV seconds
ERG=1e-7
A10=2.5e-15#spontenous decay rate for hyperfine HI transition (sec^-1)
YP=.25
F_HE=YP/(1-.75*YP)
F_H=(1.-YP)/(1.-.75*YP)
YR=3.15e7#1 year in seconds
DEBUG=False
E2500_KEV = 0.004959368
KBOLTZMANN_KEV=KBOLTZMANN/(EV*1e3)#Boltzmann constant in keV
NH0=COSMO.rho_b(0.)*(1e3)**3.*MSOL/MP*(1.-YP)/LITTLEH
NH0_CM=NH0/(1e5*KPC)**3.*LITTLEH**3.
NHE0=NH0*YP/4./(1.-YP)
NHE0_CM=NH0_CM*YP/4./(1.-YP)
NB0=NH0+NHE0
NB0_CM=NH0_CM+NHE0_CM
DIRNAME,_=os.path.split(os.path.abspath(__file__))
LY_N_ALPHA_SWITCH={0:1.,
                   1:1.,
                   2:1.,
                   3:0.,
                   4:0.2609,
                   5:0.3078,
                   6:0.3259,
                   7:0.3353,
                   8:0.3410,
                   9:0.3448,
                   10:0.3476,
                   11:0.3496,
                   12:0.3512,
                   13:0.3524,
                   14:0.3535,
                   15:0.3543,
                   16:0.3550,
                   17:0.3556,
                   18:0.3561,
                   19:0.3565,
                   20:0.3569,
                   21:0.3572,
                   22:0.3575,
                   23:0.3578,
                   24:0.3580,
                   25:0.3582,
                   26:0.3584,
                   27:0.3586,
                   28:0.3587,
                   29:0.3589,
                   30:0.3590}#dictionary returning
                   #fraction of Ly-n photons re-emitted
                   #as Ly-alpha photons.
POP_II_ION=4361
POP_III_ION=44021
RY_KEV= 13.6e-3
