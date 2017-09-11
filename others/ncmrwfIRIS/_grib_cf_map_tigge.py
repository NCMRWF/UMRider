# (C) British Crown Copyright 2013 - 2016, Met Office
#
# This file is part of Iris.
#
# Iris is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Iris is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Iris.  If not, see <http://www.gnu.org/licenses/>.
#
# DO NOT EDIT: AUTO-GENERATED
# Created on 12 February 2016 17:02 from 
# http://www.metarelate.net/metOcean
# at commit cf419fba84a70fba5f394f1481cfcdbba28877ff

# https://github.com/metarelate/metOcean/commit/cf419fba84a70fba5f394f1481cfcdbba28877ff

"""
Provides GRIB/CF phenomenon translations.

"""

from __future__ import (absolute_import, division, print_function)
from six.moves import (filter, input, map, range, zip)  # noqa

from collections import namedtuple


CFName = namedtuple('CFName', 'standard_name long_name units')

DimensionCoordinate = namedtuple('DimensionCoordinate',
                                 'standard_name units points')

G1LocalParam = namedtuple('G1LocalParam', 'edition t2version centre iParam')
#G2Param = namedtuple('G2Param', 'edition discipline category number')

# Arulalan.T has introduced two extra default argumetns in namedtuple!
G2Param = namedtuple('G2Param', 'edition discipline category number typeOfFirstFixedSurface  scaleFactorOfFirstFixedSurface typeOfStatisticalProcessing')

class G2Param(G2Param):
    # ref https://ceasarjames.wordpress.com/2012/03/19/how-to-use-default-arguments-with-namedtuple/
    def __new__(cls, edition, discipline, category, number, 
          typeOfFirstFixedSurface=None, scaleFactorOfFirstFixedSurface=None, 
          typeOfStatisticalProcessing=None):
        # add default values
        return super(G2Param, cls).__new__(cls, edition, discipline, category,
             number, typeOfFirstFixedSurface, scaleFactorOfFirstFixedSurface,
             typeOfStatisticalProcessing)
# end o fclass G2Param(G2Param):

GRIB1_LOCAL_TO_CF_CONSTRAINED = {
    G1LocalParam(1, 128, 98, 165): (CFName('x_wind', None, 'm s-1'), DimensionCoordinate('height', 'm', (10,))),
    G1LocalParam(1, 128, 98, 166): (CFName('y_wind', None, 'm s-1'), DimensionCoordinate('height', 'm', (10,))),
    G1LocalParam(1, 128, 98, 167): (CFName('air_temperature', None, 'K'), DimensionCoordinate('height', 'm', (2,))),
    G1LocalParam(1, 128, 98, 168): (CFName('dew_point_temperature', None, 'K'), DimensionCoordinate('height', 'm', (2,))),
    }

GRIB1_LOCAL_TO_CF = {
    G1LocalParam(1, 128, 98, 31): CFName('sea_ice_area_fraction', None, '1'),
    G1LocalParam(1, 128, 98, 34): CFName('sea_surface_temperature', None, 'K'),
    G1LocalParam(1, 128, 98, 59): CFName('atmosphere_specific_convective_available_potential_energy', None, 'J kg-1'),
    G1LocalParam(1, 128, 98, 129): CFName('geopotential', None, 'm2 s-2'),
    G1LocalParam(1, 128, 98, 130): CFName('air_temperature', None, 'K'),
    G1LocalParam(1, 128, 98, 131): CFName('x_wind', None, 'm s-1'),
    G1LocalParam(1, 128, 98, 132): CFName('y_wind', None, 'm s-1'),
    G1LocalParam(1, 128, 98, 135): CFName('lagrangian_tendency_of_air_pressure', None, 'Pa s-1'),
    G1LocalParam(1, 128, 98, 141): CFName('thickness_of_snowfall_amount', None, 'm'),
    G1LocalParam(1, 128, 98, 151): CFName('air_pressure_at_sea_level', None, 'Pa'),
    G1LocalParam(1, 128, 98, 157): CFName('relative_humidity', None, '%'),
    G1LocalParam(1, 128, 98, 164): CFName('cloud_area_fraction', None, '1'),
    G1LocalParam(1, 128, 98, 173): CFName('surface_roughness_length', None, 'm'),
    G1LocalParam(1, 128, 98, 174): CFName(None, 'grib_physical_atmosphere_albedo', '1'),
    G1LocalParam(1, 128, 98, 186): CFName('low_type_cloud_area_fraction', None, '1'),
    G1LocalParam(1, 128, 98, 187): CFName('medium_type_cloud_area_fraction', None, '1'),
    G1LocalParam(1, 128, 98, 188): CFName('high_type_cloud_area_fraction', None, '1'),
    G1LocalParam(1, 128, 98, 235): CFName(None, 'grib_skin_temperature', 'K'),
    }

GRIB2_TO_CF = {
    G2Param(2, 0, 0, 0): CFName('air_temperature', None, 'K'),
    G2Param(2, 0, 0, 2): CFName('air_potential_temperature', None, 'K'),
    G2Param(2, 0, 0, 6): CFName('dew_point_temperature', None, 'K'),
    G2Param(2, 0, 0, 10): CFName('surface_upward_latent_heat_flux', None, 'W m-2'),
    G2Param(2, 0, 0, 11): CFName('surface_upward_sensible_heat_flux', None, 'W m-2'),
    G2Param(2, 0, 0, 17): CFName('surface_temperature', None, 'K'),
    G2Param(2, 0, 1, 0): CFName('specific_humidity', None, 'kg kg-1'),
    G2Param(2, 0, 1, 1): CFName('relative_humidity', None, '%'),
    G2Param(2, 0, 1, 2): CFName('humidity_mixing_ratio', None, 'kg kg-1'),
    G2Param(2, 0, 1, 3): CFName(None, 'precipitable_water', 'kg m-2'),
    G2Param(2, 0, 1, 7): CFName('precipitation_flux', 'precipitation_rate', 'kg m-2 s-1'),
    G2Param(2, 0, 1, 11): CFName('thickness_of_snowfall_amount', None, 'm'),
    G2Param(2, 0, 1, 13): CFName('liquid_water_content_of_surface_snow', None, 'kg m-2'),
    G2Param(2, 0, 1, 51): CFName('atmosphere_mass_content_of_water', None, 'kg m-2'),
    G2Param(2, 0, 1, 53): CFName('snowfall_flux', 'snowfall_rate', 'kg m-2 s-1'),
    G2Param(2, 0, 1, 64): CFName('atmosphere_mass_content_of_water_vapor', None, 'kg m-2'),
    G2Param(2, 0, 2, 0): CFName('wind_from_direction', None, 'degrees'),
    G2Param(2, 0, 2, 1): CFName('wind_speed', None, 'm s-1'),
    G2Param(2, 0, 2, 2): CFName('x_wind', None, 'm s-1'),
    G2Param(2, 0, 2, 3): CFName('y_wind', None, 'm s-1'),
    G2Param(2, 0, 2, 8): CFName('lagrangian_tendency_of_air_pressure', None, 'Pa s-1'),
    G2Param(2, 0, 2, 10): CFName('atmosphere_absolute_vorticity', None, 's-1'),
    G2Param(2, 0, 2, 14): CFName(None, 'ertel_potential_velocity', 'K m2 kg-1 s-1'),
    G2Param(2, 0, 2, 22): CFName('wind_speed_of_gust', None, 'm s-1'),
    G2Param(2, 0, 3, 0): CFName('surface_air_pressure', None, 'Pa'),
    G2Param(2, 0, 3, 1): CFName('air_pressure_at_sea_level', None, 'Pa'),
    G2Param(2, 0, 3, 3): CFName(None, 'icao_standard_atmosphere_reference_height', 'm'),
    G2Param(2, 0, 3, 4): CFName('geopotential', None, 'm2 s-2'),
    G2Param(2, 0, 3, 5): CFName('geopotential_height', None, 'm'),
    G2Param(2, 0, 3, 6): CFName('altitude', None, 'm'),
    G2Param(2, 0, 3, 9): CFName('geopotential_height_anomaly', None, 'm'),
    G2Param(2, 0, 4, 7): CFName('surface_downwelling_shortwave_flux_in_air', None, 'W m-2'),
    G2Param(2, 0, 4, 9): CFName('surface_net_downward_shortwave_flux', None, 'W m-2'),
    G2Param(2, 0, 5, 3): CFName('surface_downwelling_longwave_flux', None, 'W m-2'),
    G2Param(2, 0, 5, 5): CFName('surface_net_downward_longwave_flux', None, 'W m-2'),
    
    G2Param(2, 0, 6, 1): CFName('cloud_area_fraction', None, '%'),
    G2Param(2, 0, 6, 3): CFName('low_type_cloud_area_fraction', None, '%'),
    G2Param(2, 0, 6, 4): CFName('medium_type_cloud_area_fraction', None, '%'),
    G2Param(2, 0, 6, 5): CFName('high_type_cloud_area_fraction', None, '%'),
    G2Param(2, 0, 6, 6): CFName('atmosphere_mass_content_of_cloud_liquid_water', None, 'kg m-2'),
    G2Param(2, 0, 6, 7): CFName('cloud_area_fraction_in_atmosphere_layer', None, '%'),
#    G2Param(2, 0, 7, 6): CFName('atmosphere_specific_convective_available_potential_energy', None, 'J kg-1'),
#    G2Param(2, 0, 7, 7): CFName(None, 'convective_inhibition', 'J kg-1'),
    G2Param(2, 0, 7, 8): CFName(None, 'storm_relative_helicity', 'J kg-1'),
    G2Param(2, 0, 14, 0): CFName('atmosphere_mole_content_of_ozone', None, 'Dobson'),
    G2Param(2, 0, 19, 1): CFName(None, 'grib_physical_atmosphere_albedo', '%'),
    G2Param(2, 2, 0, 0): CFName('land_binary_mask', None, '1'),
    G2Param(2, 2, 0, 1): CFName('surface_roughness_length', None, 'm'),
    G2Param(2, 2, 0, 2): CFName('soil_temperature', None, 'K'),
    G2Param(2, 2, 0, 7): CFName('surface_altitude', None, 'm'),
    G2Param(2, 2, 3, 20): CFName('moisture_content_of_soil_layer', None, 'kg m-2'),
    G2Param(2, 2, 0, 25): CFName(None, 'volumetric_moisture_of_soil_layer', 'm3 m-3'),
    G2Param(2, 2, 0, 34): CFName('surface_runoff_flux', None, 'kg m-2 s-1'),
    G2Param(2, 10, 1, 2): CFName('sea_water_x_velocity', None, 'm s-1'),
    G2Param(2, 10, 1, 3): CFName('sea_water_y_velocity', None, 'm s-1'),
    G2Param(2, 10, 2, 0): CFName('sea_ice_area_fraction', None, '1'),
    G2Param(2, 10, 2, 1): CFName('sea_ice_thickness', None, 'm'),
    G2Param(2, 10, 3, 0): CFName('sea_surface_temperature', None, 'K'),        
    
    ## begin the ncum load rules cf names  
    G2Param(2, 0, 7, 6): CFName('atmosphere_convective_available_potential_energy_wrt_surface', None, 'J kg-1'),
    G2Param(2, 0, 7, 7): CFName('atmosphere_convective_inhibition_wrt_surface', None, 'J kg-1'),
    ## end the ncum load rules cf names  
    
    # G2Param(grib version, discipline, parameter category, parameter no): CFName('standard_name', 'long_name', 'units') # paramid
    G2Param(2, 0, 2, 9): CFName('upward_air_velocity', None, 'm s-1'), # 500032
    G2Param(2, 0, 2, 8): CFName(None, 'upward_air_velocity_in_pascal', 'Pa s-1'), 
    G2Param(2, 0, 6, 23): CFName(None, 'cloud_ice_mixing_ratio', 'kg kg-1'), # 260118
    G2Param(2, 0, 3, 10): CFName(None, 'density', 'kg m-3'), # 3089
    G2Param(2, 0, 19, 0): CFName('visibility_in_air', None, 'm'), # 3020
    G2Param(2, 0, 1, 8): CFName('precipitation_amount', None, 'kg m-2'), # 228228
    G2Param(2, 2, 0, 3): CFName(None, 'soil_moisture_content', 'kg m-2'), # 3086    
    G2Param(2, 192, 150, 129): CFName('sea_water_potential_temperature', 'ocean_potential_temperature', 'C'), # 150129
    G2Param(2, 192, 150, 130): CFName('sea_water_salinity', 'ocean_salinity', '1e-3'), # 150130
    G2Param(2, 0, 19, 3): CFName('ocean_mixed_layer_thickness', 'mixed_layer_depth', 'm'), # 3067
    G2Param(2, 192, 151, 153): CFName(None, 'u_stress', 'N m-2'), # 151153
    G2Param(2, 192, 151, 154): CFName(None, 'v_stress', 'N m-2'), # 151154
    G2Param(2, 192, 151, 158): CFName(None, 'precipitation_minus_evaporation', 'kg m-2 s-1' ), # 151158
    G2Param(2, 0, 1, 65): CFName('rainfall_flux', 'rainfall_rate', 'kg m-2 s-1'), # 260058
    G2Param(2, 0, 3, 18): CFName('atmosphere_boundary_layer_thickness', None, 'm'), # WMO
#    G2Param(2, 0, 1, 60): CFName('surface_snow_amount_where_land', None, 'kg m-2'), # TIGGE
    G2Param(2, 0, 1, 60): CFName('snowfall_amount', None, 'kg m-2'), # TIGGE
    G2Param(2, 0, 1, 192): CFName('fog_area_fraction', None, '%'), # NCMRWF Local
    G2Param(2, 0, 20, 102): CFName('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', None, '1'), # WMO
    
    G2Param(2, 3, 1, 192): CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.38um', '1'), # NCMRWF Local
    G2Param(2, 3, 1, 193): CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.44um', '1'), # NCMRWF Local
    G2Param(2, 3, 1, 194): CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.55um', '1'), # NCMRWF Local
    G2Param(2, 3, 1, 195): CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.67um', '1'), # NCMRWF Local
    G2Param(2, 3, 1, 196): CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.87um', '1'), # NCMRWF Local
    G2Param(2, 3, 1, 197): CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_1.02um', '1'), # NCMRWF Local

    G2Param(2, 3, 1, 198): CFName('atmosphere_mass_content_of_dust_dry_aerosol_particles', None, 'kg m-2'), # NCMRWF Local
    
#    G2Param(2, 0, 0, 0): CFName(None, 'air_temperature_maximum', 'K'), # TIGGE
#    G2Param(2, 0, 0, 0): CFName(None, 'air_temperature_minimum', 'K'), # TIGGE
    G2Param(2, 0, 1, 69): CFName('atmosphere_cloud_liquid_water_content', None, 'kg m-2'), 
    G2Param(2, 0, 1, 70): CFName('atmosphere_cloud_ice_content', None, 'kg m-2'), 
    
    G2Param(2, 0, 1, 3): CFName(None, 'atmosphere_precipitable_water_content', 'kg m-2'),
    
    # G2Param(grib version, discipline, parameter category, parameter no, typeOfFirstFixedSurface):
#    G2Param(2, 0, 1, 60, 1): CFName(None, 'snow_depth_water_equivalent', 'kg m-2'), # 228141
#    G2Param(2, 2, 0, 0, 1): CFName(None, 'land_sea_mask', '(0 - 1)'), # 172
#    G2Param(2, 0, 3, 5, 1): CFName(None, 'orography', 'm'), # 228002
    G2Param(2, 10, 2, 8, 1): CFName(None, 'sea_ice_temperature', 'K'), # 500172
#    G2Param(2, 0, 3, 0, 1): CFName(None, 'surface_pressure', 'Pa'), # 134
    
    # G2Param(grib version, discipline, parameter category, parameter no, typeOfFirstFixedSurface,      
    # scaleFactorOfFirstFixedSurface):
    G2Param(2, 0, 1, 22, 105, 0): CFName(None, 'cloud_mixing_ratio', 'kg kg-1'), # 500100
    G2Param(2, 0, 19, 11, 105, 0): CFName(None, 'turbulent_kinetic_energy', 'J kg-1'), # 500158
    
    G2Param(2, 0, 6, 1): CFName(None, 'cloud_area_fraction_assuming_random_overlap', '%'), # TIGGE
    
#    G2Param(2, 0, 6, 202): CFName(None, 'cloud_area_fraction_assuming_random_overlap', '%'), # NCMRWF Local
    G2Param(2, 0, 6, 203): CFName(None, 'cloud_area_fraction_assuming_maximum_random_overlap', '%'), # NCMRWF Local
    
    ### NCEP map begin ###
    G2Param(2, 0, 1, 15): CFName('stratiform_snowfall_amount', None, 'kg m-2'), # 260012    
    G2Param(2, 0, 1, 14): CFName('convective_snowfall_amount', None, 'kg m-2'), # 260011
    G2Param(2, 2, 0, 13): CFName('canopy_water_amount', None, 'kg m-2'), # 260189   
    ### NCEP map end ###    
   
	G2Param(2, 0, 1, 47): CFName('stratiform_rainfall_amount', None, 'kg m-2'), # WMO    
    G2Param(2, 0, 1, 48): CFName('convective_rainfall_amount', None, 'kg m-2'), # WMO    
    
    G2Param(2, 0, 4, 8): CFName('surface_upwelling_shortwave_flux_in_air', None, 'W m-2'), # WMO 
    G2Param(2, 0, 5, 4): CFName('surface_upwelling_longwave_flux_in_air', None, 'W m-2'),    
            
    G2Param(2, 0, 4, 198): CFName('toa_outgoing_shortwave_flux_assuming_clear_sky', None, 'W m-2'), # NCMRWF Local
    G2Param(2, 0, 5, 195): CFName('toa_outgoing_longwave_flux_assuming_clear_sky', None, 'W m-2'), # NCMRWF Local
    
#    # the below 6 gets conflicts with surface_downwelling_shortwave_flux_in_air while loading from iris, because of same key in this dictionary (we didnt implement typeOfFirstFixedSurface in grib1_phenom_to_cf_info)
#    G2Param(2, 0, 4, 7, 8): CFName('toa_incoming_shortwave_flux', None, 'W m-2'), # WMO
#    #WMO need to set surface level type as toa (Nominal top of the atmosphere, 8)
#    G2Param(2, 0, 5, 4, 8): CFName('toa_outgoing_longwave_flux', None, 'W m-2'),   # WMO
#    G2Param(2, 0, 4, 8, 8): CFName('toa_outgoing_shortwave_flux', None, 'W m-2'),  # WMO        
#    #WMO need to set  surface level type as tropopause (7)
#    G2Param(2, 0, 3, 0, 7): CFName('tropopause_air_pressure', None, 'Pa'), # WMO
#    G2Param(2, 0, 0, 0, 7): CFName('tropopause_air_temperature', None, 'K'),  # WMO
#    G2Param(2, 0, 3, 6, 7): CFName('tropopause_altitude', None, 'm'), # WMO 
     
     # the above 3 gets conflicts with surface_air_temperature, surface_air_pressure, surface_altitude while loading from iris, because of same key in this dictionary (we didnt implement typeOfFirstFixedSurface in grib1_phenom_to_cf_info)
      
     
    }

CF_CONSTRAINED_TO_GRIB1_LOCAL = {
    (CFName('air_temperature', None, 'K'), DimensionCoordinate('height', 'm', (2,))): G1LocalParam(1, 128, 98, 167),
    (CFName('dew_point_temperature', None, 'K'), DimensionCoordinate('height', 'm', (2,))): G1LocalParam(1, 128, 98, 168),
    (CFName('x_wind', None, 'm s-1'), DimensionCoordinate('height', 'm', (10,))): G1LocalParam(1, 128, 98, 165),
    (CFName('y_wind', None, 'm s-1'), DimensionCoordinate('height', 'm', (10,))): G1LocalParam(1, 128, 98, 166),
    }

CF_TO_GRIB1_LOCAL = {
    CFName(None, 'grib_physical_atmosphere_albedo', '1'): G1LocalParam(1, 128, 98, 174),
    CFName(None, 'grib_skin_temperature', 'K'): G1LocalParam(1, 128, 98, 235),
    CFName('air_pressure_at_sea_level', None, 'Pa'): G1LocalParam(1, 128, 98, 151),
    CFName('air_temperature', None, 'K'): G1LocalParam(1, 128, 98, 130),
    CFName('atmosphere_specific_convective_available_potential_energy', None, 'J kg-1'): G1LocalParam(1, 128, 98, 59),
    CFName('cloud_area_fraction', None, '1'): G1LocalParam(1, 128, 98, 164),
    CFName('geopotential', None, 'm2 s-2'): G1LocalParam(1, 128, 98, 129),
    CFName('high_type_cloud_area_fraction', None, '1'): G1LocalParam(1, 128, 98, 188),
    CFName('lagrangian_tendency_of_air_pressure', None, 'Pa s-1'): G1LocalParam(1, 128, 98, 135),
    CFName('low_type_cloud_area_fraction', None, '1'): G1LocalParam(1, 128, 98, 186),
    CFName('medium_type_cloud_area_fraction', None, '1'): G1LocalParam(1, 128, 98, 187),
    CFName('relative_humidity', None, '%'): G1LocalParam(1, 128, 98, 157),
    CFName('sea_ice_area_fraction', None, '1'): G1LocalParam(1, 128, 98, 31),
    CFName('sea_surface_temperature', None, 'K'): G1LocalParam(1, 128, 98, 34),
    CFName('surface_roughness_length', None, 'm'): G1LocalParam(1, 128, 98, 173),
    CFName('thickness_of_snowfall_amount', None, 'm'): G1LocalParam(1, 128, 98, 141),
    CFName('x_wind', None, 'm s-1'): G1LocalParam(1, 128, 98, 131),
    CFName('y_wind', None, 'm s-1'): G1LocalParam(1, 128, 98, 132),
    }

CF_TO_GRIB2 = {
#    CFName(None, 'convective_inhibition', 'J kg-1'): G2Param(2, 0, 7, 7),
    CFName(None, 'ertel_potential_velocity', 'K m2 kg-1 s-1'): G2Param(2, 0, 2, 14),
    CFName(None, 'grib_physical_atmosphere_albedo', '%'): G2Param(2, 0, 19, 1),
    CFName(None, 'icao_standard_atmosphere_reference_height', 'm'): G2Param(2, 0, 3, 3),
    CFName(None, 'precipitable_water', 'kg m-2'): G2Param(2, 0, 1, 3),
    CFName(None, 'storm_relative_helicity', 'J kg-1'): G2Param(2, 0, 7, 8),
    CFName('air_potential_temperature', None, 'K'): G2Param(2, 0, 0, 2),
#    CFName('air_pressure_at_sea_level', None, 'Pa'): G2Param(2, 0, 3, 1), 
    CFName('air_pressure_at_sea_level', None, 'Pa'): G2Param(2, 0, 3, 0),   # TIGGE NEEDS IT 
    CFName('air_temperature', None, 'K'): G2Param(2, 0, 0, 0),
    CFName('altitude', None, 'm'): G2Param(2, 0, 3, 6),
    CFName('atmosphere_absolute_vorticity', None, 's-1'): G2Param(2, 0, 2, 10),
    CFName('atmosphere_mass_content_of_cloud_liquid_water', None, 'kg m-2'): G2Param(2, 0, 6, 6),
    CFName('atmosphere_mass_content_of_water', None, 'kg m-2'): G2Param(2, 0, 1, 51),
    CFName('atmosphere_mass_content_of_water_vapor', None, 'kg m-2'): G2Param(2, 0, 1, 64),
    CFName('atmosphere_mole_content_of_ozone', None, 'Dobson'): G2Param(2, 0, 14, 0),
    CFName('cloud_area_fraction', None, '%'): G2Param(2, 0, 6, 1),
    CFName('cloud_area_fraction_in_atmosphere_layer', None, '%'): G2Param(2, 0, 6, 7),
    CFName('dew_point_temperature', None, 'K'): G2Param(2, 0, 0, 6),
    CFName('geopotential', None, 'm2 s-2'): G2Param(2, 0, 3, 4),
    CFName('geopotential_height', None, 'm'): G2Param(2, 0, 3, 5),
    CFName(None, 'surface_geopotential_height', 'm'): G2Param(2, 0, 3, 5), # this is orography, but some model requires orography should be written as in gpm.
    CFName('geopotential_height_anomaly', None, 'm'): G2Param(2, 0, 3, 9),
    CFName('high_type_cloud_area_fraction', None, '%'): G2Param(2, 0, 6, 5),
    CFName('humidity_mixing_ratio', None, 'kg kg-1'): G2Param(2, 0, 1, 2),
    CFName('lagrangian_tendency_of_air_pressure', None, 'Pa s-1'): G2Param(2, 0, 2, 8),
    CFName('land_area_fraction', None, '1'): G2Param(2, 2, 0, 0),
    CFName('land_binary_mask', None, '1'): G2Param(2, 2, 0, 0),
    CFName('liquid_water_content_of_surface_snow', None, 'kg m-2'): G2Param(2, 0, 1, 13),
    CFName('low_type_cloud_area_fraction', None, '%'): G2Param(2, 0, 6, 3),
    CFName('medium_type_cloud_area_fraction', None, '%'): G2Param(2, 0, 6, 4),
    CFName('moisture_content_of_soil_layer', None, 'kg m-2'): G2Param(2, 2, 3, 20),
    CFName(None, 'volumetric_moisture_of_soil_layer', 'm3 m-3'): G2Param(2, 2, 0, 25), 
    CFName('precipitation_flux', 'precipitation_rate', 'kg m-2 s-1'): G2Param(2, 0, 1, 7),
    CFName('relative_humidity', None, '%'): G2Param(2, 0, 1, 1),
    CFName('sea_ice_area_fraction', None, '1'): G2Param(2, 10, 2, 0),
    CFName('sea_ice_thickness', None, 'm'): G2Param(2, 10, 2, 1),
    CFName('sea_surface_temperature', None, 'K'): G2Param(2, 10, 3, 0),
    CFName('sea_water_x_velocity', None, 'm s-1'): G2Param(2, 10, 1, 2),
    CFName('sea_water_y_velocity', None, 'm s-1'): G2Param(2, 10, 1, 3),
    CFName('snowfall_flux', 'snowfall_rate', 'kg m-2 s-1'): G2Param(2, 0, 1, 53),
    CFName('soil_temperature', None, 'K'): G2Param(2, 2, 0, 2), # TIGGE
    CFName('specific_humidity', None, 'kg kg-1'): G2Param(2, 0, 1, 0),
    CFName('surface_air_pressure', None, 'Pa'): G2Param(2, 0, 3, 0),
    CFName('surface_altitude', None, 'm'): G2Param(2, 2, 0, 7),
    CFName('surface_downwelling_longwave_flux', None, 'W m-2'): G2Param(2, 0, 5, 3),
    CFName('surface_downwelling_shortwave_flux_in_air', None, 'W m-2'): G2Param(2, 0, 4, 7),    
    CFName('surface_net_downward_longwave_flux', None, 'W m-2 s'): G2Param(2, 0, 5, 5), # TIGGE
    CFName(None, 'time_integrated_surface_net_downward_longwave_flux', 'W m-2 s'): G2Param(2, 0, 5, 5), # TIGGE
    CFName('surface_net_downward_shortwave_flux', None, 'W m-2 s'): G2Param(2, 0, 4, 9),# TIGGE
    CFName(None, 'time_integrated_surface_net_downward_shortwave_flux', 'W m-2 s'): G2Param(2, 0, 4, 9), # TIGGE
    CFName('surface_upwelling_shortwave_flux_in_air', None, 'W m-2'): G2Param(2, 0, 4, 8),
    CFName('surface_upwelling_longwave_flux_in_air', None, 'W m-2'): G2Param(2, 0, 5, 4),    
    CFName('surface_roughness_length', None, 'm'): G2Param(2, 2, 0, 1),
    CFName('surface_runoff_flux', None, 'kg m-2 s-1'): G2Param(2, 2, 0, 34),
    CFName('surface_temperature', None, 'K'): G2Param(2, 0, 0, 17),  #TIGGE
    # OSF required it should be just TMP in grib2 file. So lets write as temperature itself.
    CFName('surface_upward_latent_heat_flux', None, 'W m-2 s'): G2Param(2, 0, 0, 10),# TIGGE
    CFName(None, 'time_integrated_surface_upward_latent_heat_flux', 'W m-2 s'): G2Param(2, 0, 0, 10), # TIGGE
    CFName('surface_upward_sensible_heat_flux', None, 'W m-2 s'): G2Param(2, 0, 0, 11),# TIGGE
    CFName(None, 'time_integrated_surface_upward_sensible_heat_flux', 'W m-2 s'): G2Param(2, 0, 0, 11), # TIGGE
    CFName('thickness_of_snowfall_amount', None, 'm'): G2Param(2, 0, 1, 11),
    CFName('wind_from_direction', None, 'degrees'): G2Param(2, 0, 2, 0),
    CFName('wind_speed', None, 'm s-1'): G2Param(2, 0, 2, 1),
    CFName('wind_speed_of_gust', None, 'm s-1'): G2Param(2, 0, 2, 22),
    CFName('x_wind', None, 'm s-1'): G2Param(2, 0, 2, 2),
    CFName('y_wind', None, 'm s-1'): G2Param(2, 0, 2, 3),
    
    # CFName('standard_name', 'long_name', 'units'): G2Param(grib version, discipline, parameter category, parameter no) # paramid
    CFName('upward_air_velocity', None, 'm s-1'): G2Param(2, 0, 2, 9), # 500032
    CFName(None, 'upward_air_velocity_in_pascal', 'Pa s-1'): G2Param(2, 0, 2, 8), 
    CFName(None, 'cloud_ice_mixing_ratio', 'kg kg-1'): G2Param(2, 0, 6, 23), # 260118
    CFName(None, 'density', 'kg m-3'): G2Param(2, 0, 3, 10), # 3089
    CFName('visibility_in_air', None, 'm'): G2Param(2, 0, 19, 0), # 3020   
    CFName('precipitation_amount', None, 'kg m-2'): G2Param(2, 0, 1, 8), # 228228
    CFName(None, 'time_cummulated_precipitation', 'kg m-2'): G2Param(2, 0, 1, 52), # 228228
    CFName(None, 'soil_moisture_content', 'kg m-2'): G2Param(2, 2, 0, 3), # 3086        
    CFName('sea_water_potential_temperature', 'ocean_potential_temperature', 'C'): G2Param(2, 192, 150, 129), # 150129
    CFName('sea_water_salinity', 'ocean_salinity', '1e-3'): G2Param(2, 192, 150, 130), # 150130
    CFName('ocean_mixed_layer_thickness', 'mixed_layer_depth', 'm'): G2Param(2, 0, 19, 3), # 3067
    CFName(None, 'u_stress', 'N m-2'): G2Param(2, 192, 151, 153), # 151153
    CFName(None, 'v_stress', 'N m-2'): G2Param(2, 192, 151, 154), # 151154
    CFName(None, 'precipitation_minus_evaporation', 'kg m-2 s-1' ): G2Param(2, 192, 151, 158), # 151158
    CFName('rainfall_flux', 'rainfall_rate', 'kg m-2 s-1'): G2Param(2, 0, 1, 65), # 260058
    CFName('atmosphere_boundary_layer_thickness', None, 'm'): G2Param(2, 0, 3, 18), # WMO
    CFName('fog_area_fraction', None, '%'): G2Param(2, 0, 1, 192), # NCMRWF Local
    CFName('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', None, '1'): G2Param(2, 0, 20, 102), # WMO
    
    CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.38um', '1'): G2Param(2, 3, 1, 192), # NCMRWF Local
    CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.44um', '1'): G2Param(2, 3, 1, 193), # NCMRWF Local
    CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.55um', '1'): G2Param(2, 3, 1, 194), # NCMRWF Local
    CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.67um', '1'): G2Param(2, 3, 1, 195), # NCMRWF Local
    CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.87um', '1'): G2Param(2, 3, 1, 196), # NCMRWF Local
    CFName(None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_1.02um', '1'): G2Param(2, 3, 1, 197), # NCMRWF Local
    
    CFName('atmosphere_mass_content_of_dust_dry_aerosol_particles', None, 'kg m-2'): G2Param(2, 3, 1, 198), # NCMRWF Local
    

##    CFName('surface_downwelling_shortwave_flux_in_air_assuming_clear_sky', None, 'W m-2'): G2Param(2, 0, 4, 196), #260342
##    CFName('surface_upwelling_shortwave_flux_in_air_assuming_clear_sky', None, 'W m-2'): G2Param(2, 0, 4, 196), #260342
    
    ## begin the ncum load rules cf names  
    CFName('atmosphere_convective_available_potential_energy_wrt_surface', None, 'J kg-1'): G2Param(2, 0, 7, 6),
    CFName('atmosphere_convective_inhibition_wrt_surface', None, 'J kg-1'): G2Param(2, 0, 7, 7),
    ## end the ncum load rules cf names  
    
    CFName(None, 'air_temperature_maximum', 'K'): G2Param(2, 0, 0, 0), # TIGGE
    CFName(None, 'air_temperature_minimum', 'K'): G2Param(2, 0, 0, 0), # TIGGE
    CFName('atmosphere_cloud_liquid_water_content', None, 'kg m-2'): G2Param(2, 0, 1, 69), 
    CFName('atmosphere_cloud_ice_content', None, 'kg m-2'): G2Param(2, 0, 1, 70), 
    
    CFName(None, 'atmosphere_precipitable_water_content', 'kg m-2'): G2Param(2, 0, 1, 3),
    
    #WMO need to set surface level type as toa (Nominal top of the atmosphere, 8)
    CFName('toa_outgoing_longwave_flux', None, 'W m-2 s'): G2Param(2, 0, 5, 5, 8),  # WMO # TIGGE
    CFName(None, 'time_integrated_toa_outgoing_longwave_flux', 'W m-2 s'): G2Param(2, 0, 5, 5, 8),  # TIGGE
    CFName('toa_outgoing_shortwave_flux', None, 'W m-2'): G2Param(2, 0, 4, 9, 8), # WMO    
    CFName('toa_outgoing_shortwave_flux_assuming_clear_sky', None, 'W m-2'): G2Param(2, 0, 4, 11, 8), #WMO    
    CFName('toa_outgoing_shortwave_flux_assuming_clear_sky', None, 'W m-2'): G2Param(2, 0, 4, 198), # NCMRWF Local
    CFName('toa_outgoing_longwave_flux_assuming_clear_sky', None, 'W m-2'): G2Param(2, 0, 5, 195), # NCMRWF Local
    
#    CFName('surface_snow_amount_where_land', None, 'kg m-2'): G2Param(2, 0, 1, 60), # TIGGE
    CFName('snowfall_amount', None, 'kg m-2'): G2Param(2, 0, 1, 60), # TIGGE
    
    #WMO need to set  surface level type as tropopause (7)
    CFName('tropopause_air_pressure', None, 'Pa'): G2Param(2, 0, 3, 0, 7), # WMO
    CFName('tropopause_air_temperature', None, 'K'): G2Param(2, 0, 0, 0, 7), # WMO
    CFName('tropopause_altitude', None, 'm'): G2Param(2, 0, 3, 6, 7), # WMO
    #WMO need to set  surface level type as top of atmosphere (8)
    CFName('toa_incoming_shortwave_flux', None, 'W m-2'): G2Param(2, 0, 4, 7, 8), # WMO
    ### though we made duplicate Grib param in the above 4 variables, but 
    ### since we made cf_standard_name as unique. so while writing into grib2 
    ### will not throw any error and for timebeing we are tweaking grib messages
    ### to set typeOfFirstFixedSurface for the above said varibles.
        
    # G2Param(grib version, discipline, parameter category, parameter no, typeOfFirstFixedSurface):
#    CFName(None, 'snow_depth_water_equivalent', 'kg m-2'): G2Param(2, 0, 1, 60, 1), # 228141
#    CFName(None, 'land_sea_mask', '(0 - 1)'): G2Param(2, 2, 0, 0, 1), # 172
    CFName(None, 'orography', 'm'): G2Param(2, 0, 3, 5, 1), # 228002  # TIGGE NEEDS IT
    CFName(None, 'sea_ice_temperature', 'K'): G2Param(2, 10, 2, 8, 1), # 500172
#    CFName(None, 'surface_pressure', 'Pa'): G2Param(2, 0, 3, 0, 1), # 134
    
    # G2Param(grib version, discipline, parameter category, parameter no, typeOfFirstFixedSurface,      
    # scaleFactorOfFirstFixedSurface):
    CFName(None, 'cloud_mixing_ratio', 'kg kg-1'): G2Param(2, 0, 1, 22, 105, 0), # 500100
    CFName(None, 'turbulent_kinetic_energy', 'J kg-1'): G2Param(2, 0, 19, 11, 105, 0), # 500158
    
    CFName(None, 'cloud_area_fraction_assuming_random_overlap', '%'): G2Param(2, 0, 6, 1), # TIGGE
#    CFName(None, 'cloud_area_fraction_assuming_random_overlap', '%'): G2Param(2, 0, 6, 202), # NCMRWF Local
    CFName(None, 'cloud_area_fraction_assuming_maximum_random_overlap', '%'): G2Param(2, 0, 6, 1), # TIGGE NEEDS IT
    
    ### NCEP map begin ###
    CFName('stratiform_snowfall_amount', None, 'kg m-2'): G2Param(2, 0, 1, 15), # 260012  
    CFName('convective_snowfall_amount', None, 'kg m-2'): G2Param(2, 0, 1, 14), # 260011
    CFName('canopy_water_amount', None, 'kg m-2'): G2Param(2, 2, 0, 13), # 260189   
    ### NCEP map end ###
    
    CFName('stratiform_rainfall_amount', None, 'kg m-2'): G2Param(2, 0, 1, 47), # WMO    
    CFName('convective_rainfall_amount', None, 'kg m-2'): G2Param(2, 0, 1, 48), # WMO
    }
