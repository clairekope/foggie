from __future__ import print_function

import numpy as np

from astropy.io import fits
from astropy.table import Table
from astropy.io import ascii
import astropy.units as u
c = 299792.458 * u.Unit('km/s')

import matplotlib.pyplot as plt
import matplotlib as mpl

import os
import glob
import collections

os.sys.path.insert(0, '/Users/molly/Dropbox/misty/MISTY-pipeline/spectacle')
from spectacle.analysis.statistics import delta_v_90, equivalent_width
from spectacle.analysis import Resample
from spectacle.analysis.line_finding import LineFinder

from scipy.signal import argrelextrema


def run_spectacle_on_kodiaq(**kwargs):
    plotting = kwargs.get('plotting', False)

    # first, read in the dataset
    kodiaq_file = 'tab_fit_result.txt'
    kodiaq = ascii.read(kodiaq_file)

    # output table has Nmin, Ncomp_in, Ncomp_out, EW, dv90
    all_data = Table(names=('los', 'HI_col',
                    'Si_II_col','Si_II_Nmin','Si_II_Ncomp','Si_II_EW','Si_II_dv90',\
                    'Si_IV_col','Si_IV_Nmin','Si_IV_Ncomp','Si_IV_EW','Si_IV_dv90',\
                    'C_IV_col','C_IV_Nmin','C_IV_Ncomp','C_IV_EW','C_IV_dv90',\
                    'O_VI_col','O_VI_Nmin',"O_VI_Ncomp","O_VI_EW",'O_VI_dv90'), \
             dtype=('S16', 'f8',  # HI
                    "f8","f8",'f8','f8','f8',  # Si II
                    'f8','f8','f8','f8','f8',  # Si IV
                    'f8','f8','f8','f8','f8',  # C IV
                    'f8',"f8",'f8','f8',"f8")) # O VI


    # assume KODIAQ has SiII, SiIV, CIV, OVI per each
    si2_component_data = Table(names=('los', 'tot_col', 'component', 'comp_col', 'comp_b'), \
                               dtype=('S16', 'f8', 'i8', 'f8', 'f8'))
    si4_component_data = Table(names=('los', 'tot_col', 'component', 'comp_col', 'comp_b'), \
                               dtype=('S16', 'f8', 'i8', 'f8', 'f8'))
    c4_component_data = Table(names=('los', 'tot_col', 'component', 'comp_col', 'comp_b'), \
                               dtype=('S16', 'f8', 'i8', 'f8', 'f8'))
    o6_component_data = Table(names=('los', 'tot_col', 'component', 'comp_col', 'comp_b'), \
                               dtype=('S16',  'f8', 'i8', 'f8', 'f8'))
    ion_dict =  collections.OrderedDict()
    ion_dict['SiII'] = 'Si II 1206'
    ion_dict['CIV'] = 'C IV 1548'
    ion_dict['SiIV'] = 'Si IV 1394'
    ion_dict['OVI'] = 'O VI 1032'
    ion_table_name_dict = {'SiII' : si2_component_data, \
                           'SiIV' : si4_component_data, \
                           'CIV'  : c4_component_data, \
                           'OVI'  : o6_component_data}



    redshift = 0.0
    print('constructing with redshift = ',redshift,'!!!')
            velocity = np.arange(-500,500,2) * u.Unit('km/s')


    # group by sightline
    kodiaq_los = kodiaq.group_by('Name')
    for this_los in kodiaq_los.groups:
        row = [this_los['Name'][0], this_los['logN_HI'][0]]
        these_ions = this_los.group_by(['Ion'])
        for ion in ion_dict.keys():
            mask = these_ions.groups.keys['Ion'] == ion
            this_ion = these_ions.groups[mask]
            # for each ion in sightline, generate spectrum
            spectrum = Spectrum1DModel(redshift=redshift)
            for comp in range(len(this_ion)):
                comp_row_start = [this_los['Name'][0]]
                delta_v = this_ion['v_i'][comp] * u.Unit('km/s')
                col_dens = this_ion['log_N_i'][comp]
                v_dop = this_ion['b_i'][comp] * u.Unit('km/s')
                print(col_dens, v_dop, delta_v)
                spectrum.add_line(name=ion_dict[ion],
                                  column_density=col_dens,
                                  v_doppler=v_dop,
                                  delta_v=delta_v)
            # run spectacle and calculate non-parametric measures
            disp = velocity
            flux = spectrum.flux(velocity)
            default_values = dict(
                bounds={
                        'column_density': (10, 17), # Global bounds in log,
                        'v_doppler': (3, 1e3) # Global bounds in km/s
                        }
            )
            print('*~*~*~*~*~> setting up the LineFinder *~*~*~*~*~>')
            print('length of arrays:', len(disp), len(velocity), len(flux))
            line_finder = LineFinder(ion_name = ion_dict[ion],
                                     redshift=redshift,
                                     data_type='flux',
                                     defaults=default_values,
                                     threshold=0.01, # flux decrement has to be > threshold; default 0.01
                                     min_distance=2. * u.Unit('km/s'), # The distance between minima, in dispersion units!
                                     max_iter=2000 # The number of fitter iterations; reduce to speed up fitting at the cost of possibly poorer fits
                                     )
            print('*~*~*~*~*~> running the fitter now *~*~*~*~*~>')
            spec_mod = line_finder(velocity, flux)
            # OK, now save this information as a row in the relevant table
            comp_table = spec_mod.stats(velocity)
            tot_col = np.log10(np.sum(np.power(10.0,comp_table['col_dens'])))
            for i, comp in enumerate(comp_table):
                comp_row = comp_row_start + [tot_col, int(i), comp['col_dens'], comp['v_dop'].value]
                ion_table_name_dict[ion].add_row(comp_row)

        # plotting is optional once implemented

    # and save that info to the all_data table and the individual measures tables
    ascii.write(all_data, 'kodiaq_spectacle_all.dat', format='fixed_width', overwrite=True)
    ascii.write(si2_component_data, 'kodiaq_spectacle_si2.dat', format='fixed_width', overwrite=True)
    ascii.write(si4_component_data, 'kodiaq_spectacle_si4.dat', format='fixed_width', overwrite=True)
    ascii.write(c4_component_data, 'kodiaq_spectacle_c4.dat', format='fixed_width', overwrite=True)
    ascii.write(o6_component_data, 'kodiaq_spectacle_o6.dat', format='fixed_width', overwrite=True)


    # not sure yet how to systematically compare the output fits to the inputs --- N,b vs v?


if __name__ == "__main__":
    run_spectacle_on_kodiaq(plotting=False)
