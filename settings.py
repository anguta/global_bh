import numpy as np
from colossus.cosmology import cosmology

PI=np.pi
F21=1420405751.7667 #HI hyperfine line frequency (Hz)
KBOLTZMANN=1.28e-23#Boltzmann Constant in Joules/Kelvin
ERG=1e-7#ERG in Joules
C=3e5#speed of light (km/sec)
KPC=3.068e19#kpc in meters
COSMO=cosmology.setCosmology('planck15')
LITTLEH=COSMO.H0/100.
DH=C/COSMO.H0#Hubble Distance
TEDDINGTON=.45#EDDINGTON E-folding time (Gyr)
SPLINE_DICT={}
MP=1.6726219e-27#Proton mass in kg
MSOL=1.99e30#solar mass in kg
PI=np.pi
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
JY=1e-26
E_HI_ION=13.6#eV
E_HII_ION=4.*E_HI_ION#eV
E_HEI_ION=24.7#eV
SIGMAT=6.625e-25#cm^2 Thompson cross-section
HPLANCK_KEV=4.135668e-18 #planck constant in keV seconds
ERG=1e-7
EV=1.60218E-19#1 electron volt in eV
YP=25.
F_HE=YP/(1-.75*YP)
F_H=(1.-YP)/(1.-.75*YP)
