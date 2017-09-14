'''
This module supports for 'unknown' variables while loading ncum output
(fieldsfiles).
Authour : Arulalan.T <arulalan@ncmrwf.gov.in>
'''
from cf_units import Unit
from iris.fileformats.grib import GribWrapper
from iris.coords import DimCoord, AuxCoord
import iris.analysis.cartography as icart
import cartopy.crs as ccrs
from numpy import meshgrid, array

regular2DLatitude, regular2DLongitude = None, None
warning = False
windCount = 0

ncumSTASH_Vs_cf = {
# http://reference.metoffice.gov.uk/um/stash/m01s00i023
#'m01s00i023': ('surface_snow_amount_where_land', None, 'Kg m-2', None), # update standard_name instead of WRONG standard name (by default) as snowfall_amount
'm01s01i202': ('surface_net_downward_shortwave_flux', None, 'W m-2', None),
'm01s01i238': ('surface_downwelling_longwave_flux_in_air', None, 'W m-2', None),
'm01s01i216': ('surface_diffuse_downwelling_shortwave_flux_in_air', None, 'W m-2', None),
'm01s03i229': ('water_evaporation_flux_from_soil', None, 'kg m-2', None),
'm01s30i403': ('atmosphere_mass_content_of_dust_dry_aerosol_particles', None, 'kg m-2', None),
# though m01s05i233 already standard_name exist, but wrongly assinged as
# mass_fraction_of_convective_cloud_liquid_water_in_air in um_cf_map.py. So
# in the below we are correcting the cf_standard_name of m01s05i233.
'm01s05i233': ('atmosphere_convective_available_potential_energy_wrt_surface', None, 'J kg-1', None),
'm01s05i234': ('atmosphere_convective_inhibition_wrt_surface', None, 'J kg-1', None),
# 50meter B-Grid U component wind
'm01s15i212': ('x_wind', None, 'm s-1', 50),   
# 50meter B-Grid V component wind
'm01s15i213': ('y_wind', None, 'm s-1', 50),
'm01s00i253': (None, 'density_r_r_in_air', None, None),
'm01s01i215': (None, 'direct_surface_shortwave_flux_in_air', 'W m-2', None),
'm01s09i202': (None, 'very_low_type_cloud_area_fraction', '%', None),
'm01s01i212': (None, 'direct_uv_flux_in_air', 'W m-2', None),
'm01s03i296': (None, 'soil_evaporation_rate', 'kg m-2 s-1', None),
'm01s03i297': (None, 'canopy_evaporation_rate', 'kg m-2 s-1', None),
'm01s03i232': (None, 'open_sea_evaporation_rate', 'kg m-2 s-1', None),
#'m01s01i202': (None, 'surface_net_downward_shortwave_flux_corrected', 'W m-2', None), # This required only for IMDAA
}

duplicateSTASH_vs_cf = {
# duplicate STASH but cell_methods are different, variables comes here.
# STASH : {cell_method1 : (standard_name, long_name, unit, height),
#          cell_method2 : (standard_name, long_name, unit, height)}
'm01s03i236': {'maximum': (None, 'air_temperature_maximum', 'K', None),
               'minimum': (None, 'air_temperature_minimum', 'K', None)}
}

G2Param_vs_cf = {
# whose  surface level type as top of atmosphere (8)
# grib version, discipline, parameter category, parameter no, typeOfFirstFixedSurface
(2, 0, 5, 4, 8): ('toa_outgoing_longwave_flux', None, 'W m-2'),
(2, 0, 4, 8, 8): ('toa_outgoing_shortwave_flux', None, 'W m-2'),
(2, 0, 4, 11, 8): ('toa_outgoing_shortwave_flux_assuming_clear_sky', None, 'W m-2'),
(2, 0, 4, 7, 8): ('toa_incoming_shortwave_flux', None, 'W m-2'),
# whose  surface level type as tropopause (7)
(2, 0, 3, 0, 7): ('tropopause_air_pressure', None, 'Pa'),
(2, 0, 0, 0, 7): ('tropopause_air_temperature', None, 'K'),
(2, 0, 3, 6, 7): ('tropopause_altitude', None, 'm'),
# Need to load from NCMRWF Local Table entries Begin
(2, 0, 4, 198, 8): ('toa_outgoing_shortwave_flux_assuming_clear_sky', None, 'W m-2'),
(2, 0, 5, 195, 8): ('toa_outgoing_longwave_flux_assuming_clear_sky', None, 'W m-2'),
(2, 0, 1, 192, 1): ('fog_area_fraction', None, '%'),
(2, 0, 1, 193, 1): (None, 'soil_evaporation_rate', 'kg m-2 s-1'),
(2, 0, 1, 194, 1): (None, 'canopy_evaporation_rate', 'kg m-2 s-1'),
(2, 0, 1, 195, 1): (None, 'open_sea_evaporation_rate', 'kg m-2 s-1'),
(2, 0, 5, 192, 1): (None, 'surface_downwelling_longwave_flux_assuming_clear_sky', 'W m-2'),
(2, 0, 6, 204, 1): (None, 'cloud_volume_fraction_in_atmosphere_layer', '%'),
(2, 0, 6, 205, 1): (None, 'liquid_cloud_volume_fraction_in_atmosphere_layer', '%'),
(2, 0, 6, 206, 1): (None, 'ice_cloud_volume_fraction_in_atmosphere_layer', '%'),
(2, 0, 6, 201, 1): (None, 'very_low_type_cloud_area_fraction', '%'),
(2, 0, 4, 194, 1): (None, 'direct_uv_flux_in_air', 'W m-2'),
(2, 0, 1, 196, 1): (None, 'density_r_r_in_air', None),
(2, 2, 0, 231, 1): ('subsurface_runoff_flux', None, 'kg m-2 s-1'),
(2, 2, 0, 232, 1): ('surface_upward_water_flux', None, 'kg m-2 s-1'),
(2, 2, 0, 193, 1): ('downward_heat_flux_in_soil', None, 'W m-2'),

# grib version, discipline, parameter category, parameter no, typeOfFirstFixedSurface, scaleFactorOfFirstFixedSurface
(2, 3, 1, 192, 1, 7): (None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.38um', '1'),
(2, 3, 1, 193, 1, 7): (None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.44um', '1'),
(2, 3, 1, 194, 1, 7): (None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.55um', '1'),
(2, 3, 1, 195, 1, 7): (None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.67um', '1'),
(2, 3, 1, 196, 1, 7): (None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_0.87um', '1'),
(2, 3, 1, 197, 1, 7): (None, 'atmosphere_optical_thickness_due_to_dust_ambient_aerosol_at_1.02um', '1'),

# required to load NGFS OSF files.
(2, 0, 4, 192, 1): ('surface_downwelling_shortwave_flux_in_air', None, 'W m-2'),
(2, 0, 4, 193, 1): ('surface_upwelling_shortwave_flux_in_air', None, 'W m-2'),
(2, 0, 5, 192, 1): ('surface_downwelling_longwave_flux', None, 'W m-2'),
(2, 0, 5, 193, 1): ('surface_upwelling_longwave_flux_in_air', None, 'W m-2'),

(2, 0, 4, 196): ('surface_downwelling_shortwave_flux_in_air_assuming_clear_sky', None, 'W m-2'),
(2, 0, 4, 197): ('surface_upwelling_shortwave_flux_in_air_assuming_clear_sky', None, 'W m-2'),

# load from NCMRWF Local Table entries end
}

# In NCUM_Regional model time axis 'forecast_reference_time' and 'forecast_period' are wrong.
# so lets fix it.
fix_timeaxis_of_regional_acc_avg_cubes = [('stratiform_rainfall_amount', 'm01s04i201'),
                                          ('stratiform_snowfall_amount', 'm01s04i202')]

def update_cf_standard_name(cube, field, filename):
    """
    This call back function used to update the cubes standard_name if not
    exists (i.e unknown) or to correct the cf_standard_name of particular
    cube (if wrongly assigned in um_cf_map.py) while loading cubes via iris.

    >>> import iris
    >>> cubes = iris.load('umglaa_pf000', callback=update_cf_standard_name)
    >>> cubes = iris.load('um_ana.grib2', callback=update_cf_standard_name)

    Arulalan.T
    12-Feb-2016
    """

    # get input filename
    fname = filename.split('/')[-1] if '/' in filename else filename
    if cube.attributes:
        # loading from pp/fieldsfiles
        varSTASH = str(cube.attributes['STASH'])
        if varSTASH in ncumSTASH_Vs_cf:
            # get correct standard_name and units
            sname, lname, unit, height = ncumSTASH_Vs_cf[varSTASH]
            # update cube's standard_name and its units
            cube.standard_name = sname
            cube.long_name = lname
            cube.units = Unit(unit)
            if height:
                heightAx = DimCoord(array([float(height)]), standard_name='height',
                             units=Unit('m'), attributes={'positive': 'up'})
                cube.add_aux_coord(heightAx)
        elif varSTASH in duplicateSTASH_vs_cf:
            ccm = cube.cell_methods
            if ccm:
                ccmm = ccm[0].method
                if ccmm in duplicateSTASH_vs_cf[varSTASH]:
                    # get correct standard_name, units and height
                    sname, lname, unit, height = duplicateSTASH_vs_cf[varSTASH][ccmm]
                    # update cube's standard_name and its units
                    cube.standard_name = sname
                    cube.long_name = lname
                    cube.units = Unit(unit)
                    if height:
                        heightAx = DimCoord(array([float(height)]), standard_name='height',
                                     units=Unit('m'), attributes={'positive': 'up'})
                        cube.add_aux_coord(heightAx)
            # end of if ccm:
        # end of if varSTASH in ncumSTASH_Vs_cf:

        if fname == '000_pg000': # update NEPS Control file's first record alone.
             forecast_period = cube.coords('forecast_period')[0]
             if forecast_period.points[0] == 0.19999999925494194: # equivalent to 12th minutes
                ## update first time step of control run of NEPS for purpose of TIGGE.
                forecast_period.points = array([0.0]) # change to 0 instead of 12th minutes
                time = cube.coords('time')[0]
                time.points = array([float(int(time.points[0]))]) # update time also.

        if fname.startswith('umnsa'):
            # regional model produces wrong reference_time for avg/acc variables. Lets fix it here.
            # fix the time axis varying reference_time problem which occurs in NCUM_Regional model.
            forecast_reference_time = cube.coords('forecast_reference_time')[0]
            fpoint = forecast_reference_time.points[0]
            # get floating point remainder
            freminder = fpoint % 1
            if freminder:
                # yes, forecast_reference_time has minutes/float values. So lets make it as hour/int.
                forecast_reference_time.points = array([float(int(fpoint))])
                # add the minutes values to the forecast_period and its bounds.
                forecast_period = cube.coords('forecast_period')[0]
                forecast_period.points = array([round(forecast_period.points[0], 3)+freminder])
                forecast_period.bounds = array([[round(forecast_period.bounds[0][0], 3)+freminder,
                                            round(forecast_period.bounds[0][1], 3)+freminder]])
        # end of if fname.startswith('umnsaa'):
        
        if fname.startswith('umglc.pp0'):
            if (cube.standard_name, varSTASH) == ('surface_altitude', 'm01s00i033'):
                # UPDATE 3 UTC by adding in all time properties. So that it will
                # become common time information along with other variables UTC.
                forecast_reference_time = cube.coords('forecast_reference_time')[0]
                forecast_reference_time.points = array([forecast_reference_time.points[0]+6.0])
                forecast_period = cube.coords('forecast_period')[0]
                forecast_period.points = array([0.0])
                time = cube.coords('time')[0]
                time.points = array([time.points[0]+3.0])
        # end of if fname.startswith('umglc.pp0'):
        
    elif isinstance(field, GribWrapper):
        # loading from grib file
        if field.editionNumber == 2 and (field.parameterNumber > 191 or
                             field.typeOfFirstFixedSurface in [7, 8] or
                             field.typeOfSecondFixedSurface in [7]):
            # loaded from grib2 file
            # loaded tropopause or toa or local table entries
            discipline = field.discipline
            pcategory = field.parameterCategory
            pnumber = field.parameterNumber
            fsfc = field.typeOfFirstFixedSurface
            ssfc = field.typeOfSecondFixedSurface
            if ssfc in [7]:
                G2ParamKey = (2, discipline, pcategory, pnumber, fsfc, ssfc)
            else:
                G2ParamKey = (2, discipline, pcategory, pnumber, fsfc)
            if G2ParamKey in G2Param_vs_cf:
                # get correct standard_name and units
                sname, lname, unit = G2Param_vs_cf[G2ParamKey]
                # update cube's standard_name and its units
                cube.standard_name = sname
                cube.long_name = lname
                cube.units = Unit(unit)
            # end of if G2ParamKey in G2Param_vs_cf:
# end of def update_cf_standard_name_if_not_exists(cube, field, filename):

def setCubeRegularLatLon(cube, field, filename):

    # https://github.com/SciTools/iris/issues/448
    glon = cube.coord('grid_longitude')
    rotated_lons = glon.points
    glat = cube.coord('grid_latitude')
    rotated_lats = glat.points
    pole_lat = glat.coord_system.grid_north_pole_latitude
    pole_lon = glat.coord_system.grid_north_pole_longitude

    rotated_lats, rotated_lons = meshgrid(rotated_lons, rotated_lats)

    lons, lats = icart.unrotate_pole(rotated_lons, rotated_lats, pole_lon, pole_lat)

    ## the below lat is 2D array
    regular2DLatitude = AuxCoord(lons, standard_name='longitude', units='degree_north')
    ## the below lon is 2D array
    regular2DLongitude = AuxCoord(lats, standard_name='latitude', units='degree_east')

    cube.remove_coord('grid_latitude')
    cube.remove_coord('grid_longitude')

    cube.add_aux_coord(regular2DLatitude, [0, 1])
    cube.add_aux_coord(regular2DLongitude, [0, 1])
    ## https://groups.google.com/forum/#!searchin/scitools-iris/unrotate/scitools-iris/m5B2752zRjQ/Xmcp5yaqAQAJ
    ## Andrew Dawson's reply : If you really want the data on a Plate Carree projection with 1D dimension coordinates (lat/lon) then you will need to regrid/reproject to move the actual data points onto a regular grid in lat/lon space.

    ## So after this, if we regrid to our regular lat, lon then regridded cube lat, lon will become two 1D array.
    ## Hopefully !!!!

# end of def setCubeRegularLatLon(cube, field, filename):
