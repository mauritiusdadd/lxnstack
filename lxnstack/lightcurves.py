# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Some useful resources I found on the web:
#   http://www.aavso.org/differential-vs-absolute-photometry
#   http://brucegary.net/DifferentialPhotometry/dp.htm#1._
#   http://www.britastro.org/vss/ccd_photometry.htm
#   http://www.physics.csbsju.edu/370/photometry/manuals/OU.edu_CCD_photometry_wrccd06.pdf

from itertools import combinations

import plotting
import numpy as np
import scipy.optimize as opt
import astropy.stats as stats
from astropy.modeling import models, fitting
import utils


PHOTOMETRIC_BANDS = {
    'U': 365,
    'B': 445,
    'V': 551,
    'R': 658,
    'I': 806,
    'Z': 900,
    'Y': 1020,
    'J': 1220,
    'H': 1630,
    'K': 2190,
    'L': 3450,
    'M': 4750,
    'N': 10500,
    'Q': 21000,
}


COMPONENTS_NAME = tuple(PHOTOMETRIC_BANDS.keys())


def getComponentTable(ncomps, named=True):
    component_table = {}
    if named and (ncomps+1 < len(COMPONENTS_NAME)):
        if ncomps == 1:
            component_table[0] = COMPONENTS_NAME[0]
        elif ncomps == 2:
            component_table[0] = COMPONENTS_NAME[1]
            component_table[1] = COMPONENTS_NAME[2]
        elif ncomps == 3:
            component_table[0] = COMPONENTS_NAME[3]
            component_table[1] = COMPONENTS_NAME[2]
            component_table[2] = COMPONENTS_NAME[1]
        elif ncomps > 3:
            for c in range(ncomps):
                component_table[c] = COMPONENTS_NAME[c+1]
    else:
        for c in range(ncomps):
            component_table[c] = 'C'+str(c)
    return component_table


def getColorIndexes(used_bands):
    try:
        sorted_bands = sorted(used_bands, key=PHOTOMETRIC_BANDS.get)
    except KeyError:
        return []
    else:
        return tuple(x for x in combinations(sorted_bands, 2))


def getColors(mag_dict):
    colors = getColorIndexes(mag_dict.keys())
    color_index = []
    for color in colors:
        color_index.append((color, mag_dict[color[0]] - mag_dict[color[1]]))
    return color_index


def getBestColorIndex(mag_dict, channel_mapping):
    available_mapped_bands = {}

    for band in channel_mapping.values():
        try:
            mag = mag_dict[band]
        except KeyError:
            continue
        else:
            available_mapped_bands[band] = mag

    if len(available_mapped_bands) >= 2:
        return getColors(available_mapped_bands)
    else:
        return []


class LightCurvePlot(plotting.Plot):

    def exportNumericDataCSV(self, csvsep):
        csvdata = str(self.getName()) + csvsep*3 + '\n'

        csvdata += "time" + csvsep
        csvdata += "value" + csvsep
        csvdata += "time error" + csvsep
        csvdata += "value error" + csvsep
        csvdata += '\n'

        # Plot data
        for i in range(len(self._xdata)):
            csvdata += str(self._xdata[i]) + csvsep
            csvdata += str(self._ydata[i]) + csvsep
            csvdata += str(self._xerr[i]) + csvsep
            csvdata += str(self._yerr[i]) + csvsep
            csvdata += '\n'

        return csvdata


def getInstMagnitudeADU(star, ndimg=None):

    val_adu = []
    bkg_adu = []
    ir2 = star.r1**2
    mr2 = star.r2**2
    or2 = star.r3**2

    if ndimg is None:
        ndimg = star.getParent().getData()

    stx, sty = star.getAbsolutePosition()

    # Get pixels inside the cirle centered on the star
    # with radius r1
    for x in range(-int(star.r1)-1, int(star.r1)+1):
        for y in range(-int(star.r1)-1, int(star.r1)+1):
            p = (x**2 + y**2)
            if p <= ir2:
                val_adu.append(ndimg[sty+y, stx+x])

    # Get pixels inside the circular area centered on the star
    # with inner radius r2 and outer radius r3
    for x in range(-int(star.r2)-1, int(star.r2)+1):
        for y in range(-int(star.r2)-1, int(star.r2)+1):
            p = (x**2 + y**2)
            if (p <= or2) and (p > mr2):
                bkg_adu.append(ndimg[sty+y, stx+x])

    # This is basically a counting experiment and hence the
    # Poisson probability distribution can be applied.
    # In such situation, if for each photodiode (pixel) k we
    # measure a number of photons A_k, the best value for its
    # uncertainty is DA_k = sqrt(A_k)

    val_adu = np.array(val_adu)
    total_star_pixels = len(val_adu)

    # NOTE(1):
    #     we use sigmaclip here to remove cosmic rays
    #     or hot-pixels present in the sky background
    #     (Yeah... not everyone uses calibrated images).

    bkg_adu = stats.sigma_clip(np.array(bkg_adu), 4, axis=0)

    # val_adu_sigma = np.sqrt(val_adu)
    # bkg_adu_sigma = np.sqrt(bkg_adu)
    # Computing these values is only a waste of resources, see NOTE(2)

    # These are the total counts of ADUs (directly poportional
    # to the number of photons hitting the photodiode, unless
    # we are near the saturation). We sum the ADU for the star because
    # we want to know the total photons emitted by the star which reach
    # the sensor, and we average the ADU from the background because
    # we want to know the mean background noise.
    total_val_adu = val_adu.sum(0)
    mean_bkg_adu = bkg_adu.mean(0)

    # NOTE(2):
    #     Applying the error propagation, the error for total_val_adu
    #     should be:
    #
    #         total_val_adu_sigma = np.sqrt((val_adu_sigma**2).sum(0))
    #
    #     however, a simple calculation leads to the following value:
    #
    #         total_val_adu_sigma = np.sqrt((val_adu_sigma**2).sum(0)) =
    #         = np.sqrt((np.sqrt(val_adu)**2).sum(0)) =
    #         = np.sqrt((val_adu).sum(0)) =
    #         = np.sqrt(total_val_adu))
    #
    #     as espected for the Poisson probability distribution.
    #     A similar calculation ca be done for mean_bkg_adu_sigma:
    #
    #     if we define N = len(bkg_adu_sigma) = len(bkg_adu) then,
    #     since mean_bkg_adu = bkg_adu.mean(0), we have
    #
    #         mean_bkg_adu_sigma = np.sqrt((bkg_adu_sigma**2).sum(0))/N =
    #         = np.sqrt(bkg_adu.sum(0)) / N =
    #         = np.sqrt(bkg_adu.sum(0) / N**2) =
    #         = np.sqrt(bkg_adu.mean(0) / N) =
    #         = np.sqrt(mean_bkg_adu / N) =
    #         = np.sqrt(mean_bkg_adu / len(bkg_adu))

    total_val_adu_sigma = np.sqrt(total_val_adu)
    mean_bkg_adu_sigma = np.sqrt(mean_bkg_adu / len(bkg_adu))

    # best value for the star
    mean_adu = total_val_adu - mean_bkg_adu*total_star_pixels
    delta_a = total_val_adu_sigma**2
    delta_b = (total_star_pixels*mean_bkg_adu_sigma)**2
    mean_adu_delta = np.sqrt(delta_a + delta_b)

    # this avoids negative or null value:
    if (mean_adu > 0).all():
        if mean_adu.shape:
            return (mean_adu, mean_adu_delta)
        else:
            return (np.array((mean_adu,)), np.array((mean_adu_delta,)))
    else:
        raise ValueError('Negative or null ADU values are not allowed!\n' +
                         'Please set the star marker correctly.')


def ccdTransformationEquation(instadu, instadu_ref, stdmag_ref,
                              extinction, airmass, airmass_ref,
                              color, color_ref, transf,
                              insterr, insterr_ref, stdmagerr_ref,
                              extinctionerr, airmasserr, airmasserr_ref,
                              colorerr, colorerr_ref, transferr):
    """
    This function computes the transformation from
    instrumental magnitude to standard magnitude.

    Parameters
    ----------
    instadu: float or array-like
        The instrumental flux of the target star (ADU counts).
    instadu_ref: float or array-like
        The instrumental flux of the reference star (ADU counts).
    stdmag_ref: float
        The standard magnitude of the reference star.
    extinction: float
        The first order extinction coefficient.
    airmass: float or array-like
        The airmass value for the target star.
    airmass_ref: float or array-like
        The airmass value for the reference star.
    color: float or array-like
        The color of the target star.
    color_ref: float or array-like
        The colot of the reference star.
    transf: float
        The transformation coefficient.
    insterr: float or array-like
        The error on instrumental flux of the target star.
    insterr_ref: float or arrya-like
        The error on the instrumental flux of the reference star.
    stdmagerr_ref: float
        The error on the standard magnitude for the refenence star.
    extinctionerr: float
        The error on the extinction coefficient.
    airmasserr: float or array-like
        The error on the airmass for the target star.
    airmasserr_ref: float or array-like
        The error on the airmass for the refenence star.
    colorerr: fload or array-like
        The error for the color of the target star.
    colorerr_ref: float or array-like
        The error for the color of the reference star.
    transferr: floar or array-like
        The error for the transformation coefficient.

    Returns
    -------
    stdmag: float of array-like
        The standard magnitude of the target star

    Examples
    --------

    Math
    ----

    The instrumental magnitude l is defined as

        l = -2.5 * log10(f) = -2.5 * log10(ADU/g)

    where

        log10 is the base 10 logarithm.
        f is the fulx of the star.
        ADU is the measured ADU counts.
        g is the exposure time.

    The standard magnitude of a star for a specific band,
    can be computed from the instrumental mangitude using
    the following relation:

        L = l - k*X + T_hk*C_hk + c

    where

        L is the standard magnitude (in the selected band)
        l is the instrumental magnitud (in the selected band)
        k is the first order extinction coefficient (for the selected bnad)
        X is the airmass for the star
        C_hk is the color of the star computed using the bands Ih and Ik
        T_hk is the transformation coefficiuent for the bads Ih and Ik
        c is a costant specific for the selected band

    If we identify with ' the quantities that refer to the target
    variable star and with " the quantities that refer to the reference
    star, then we have:

        L' = l' - k*X' + T_hk*C'_hk + c
        L" = l" - k*X" + T_hk*C"_hk + c

    If we compute the color using the bands B and V then we obtain

        L' = l' - k*X' + T_bv*(B'-V') + c
        L" = l" - k*X" + T_bv*(B"-V") + c

    therefore

        L' = L" + (l' - l") - k*(X' - X") + T_bv*[(B'-V') - (B"-V")]

    but

        l' - l" = -2.5 * log10(f') + 2.5 * log10(f") =
                = -2.5 * log10(f'/f") =
                = -2.5 * log10((ADU'/g')/(ADU"/g")

    and since ADU' and ADU" are measured from the same image, then
    g' = g", therefore

        l' - l" = -2.5 * log10(ADU'/ADU")

    and

        L' = L" -2.5*log10(ADU'/ADU2) - k*(X'-X") + T_bv*[(B'-V')-(B"-V")]

    The error on L' is computed using the standard error propagation.
    """

    LOGE10 = np.log(10)  # just for convenience

    inst_term = -2.5 * np.log10(instadu/instadu_ref)
    airm_term = extinction*(airmass - airmass_ref)
    trns_term = transf*(color - color_ref)

    stdmag = stdmag_ref + inst_term - airm_term + trns_term

    ############################################################
    #                STANDARD ERROR PROPAGATION                #
    ############################################################
    #
    # if V = f(A,B) then the error for V is
    #
    #   DV = sqrt(|DA*df(A,B)/dA|**2 + |DB*df(A,B)/dB|**2)
    #
    # -------------------------------------
    # Errors for instumental magnitude term
    # -------------------------------------
    #
    # since the instrumental magnitude is:
    #
    #   inst_term = -2.5 * np.log10(instadu/instadu_ref)
    #
    # then, if we define
    #
    #   A = instadu     DA = insterr
    #   B = instadu_ref DB = insterr_ref
    #   f = log10
    #
    # the error on inst_term is:
    #
    #   inst_err^2=6.25*(|DA*df(A,B)/dA|^2 + |DB*df(A,B)/dB|^2)
    #   = 6.25*(|DA*1/[A*ln(10)]|^2 + |DB * -1/[B*ln(10)|^2)
    #   = 6.25*(|DA/[A*ln(10)]|^2 + |DB/[B*ln(10)]|^2)

    inst_erra = (insterr/(instadu*LOGE10))**2
    inst_errb = (insterr_ref/(instadu_ref*LOGE10))**2
    inst_err2 = 6.25*(inst_erra + inst_errb)

    # ----------------------------------
    # Errors for airmass correction term
    # ----------------------------------
    #
    # since the airmass correction term is
    #
    #   airm_term = extinction*(airmass - airmass_ref)
    #
    # then if we define
    #
    #   k = extinction  Dk = extinctionerr
    #   A = airmass     DA = airmasserr
    #   B = airmass_ref DB = airmasserr_ref
    #
    # then the error term is:
    #
    #   air_err^2 = |Dk*(A-B)|^2 + |DA*k|^2 + |DB*k|^2

    air_errk = (extinctionerr*(airmass - airmass_ref))**2
    air_erra = (extinction*airmasserr)**2
    air_errb = (extinction*airmasserr_ref)**2
    air_err2 = air_errk + air_erra + air_errb

    # ------------------------------
    # Errors for transformation term
    # ------------------------------
    #
    # since the transformation term is
    #
    #   trns_term = transf*(color - color_ref)
    #
    # then if we define
    #
    #   T = extinction  DT = extinctionerr
    #   A = airmass     DA = airmasserr
    #   B = airmass_ref DB = airmasserr_ref
    #
    # then the error term is:
    #
    #   trans_err^2= |DT*(A-B)|^2 + |DA*T|^2 + |DB*T|^2

    transf_errt = (transferr*(color - color_ref))**2
    transf_erra = (transf*colorerr)**2
    transf_errb = (transf*colorerr_ref)**2
    transf_err2 = transf_errt + transf_erra + transf_errb

    # -----------
    # Total error
    # -----------
    #
    # Statistical error are summed using the
    # Root-Sum-Square method.

    stdmagerr = np.sqrt(stdmagerr_ref**2 +
                        inst_err2 +
                        air_err2 +
                        transf_err2)

    return (stdmag, stdmagerr)


def ccdTransfSimpyfied(instadu, instadu_ref, stdmag_ref,
                       color, color_ref, transf,
                       insterr, insterr_ref, stdmagerr_ref,
                       colorerr, colorerr_ref, transferr):
    """
    This function is a simplified version of ccdTransformationEquation
    It computes the transformation from instrumental magnitude
    to standard magnitude.

    Parameters
    ----------
    instadu: float or array-like
        The instrumental flux of the target star (ADU counts).
    instadu_ref: float or array-like
        The instrumental flux of the reference star (ADU counts).
    stdmag_ref: float
        The standard magnitude of the reference star.
    color: float or array-like
        The color of the target star.
    color_ref: float or array-like
        The colot of the reference star.
    transf: float
        The transformation coefficient.
    insterr: float or array-like
        The error on instrumental flux of the target star.
    insterr_ref: float or arrya-like
        The error on the instrumental flux of the reference star.
    stdmagerr_ref: float
        The error on the standard magnitude for the refenence star.
    colorerr: fload or array-like (default is 0)
        The error for the color of the target star.
    colorerr_ref: float or array-like (default is 0)
        The error for the color of the reference star.
    transferr: floar or array-like
        The error for the transformation coefficient.

    Returns
    -------
    stdmag: float or array-like
        The standard magnitude of the target star

    stdmagerr: float or aray-like
        The error for the standard magnitude of the target star

    Notes
    -----

    see help(ccdTransformationEquation) for the full deriavation
    of the transformation equation:

        L' = L" + (l' - l") - k*(X' - X") + T_bv*[(B'-V') - (B"-V")]

    If the star are very colse, X' - X" ~ 0 so the airmass
    correction term cancels out

        L' = L" + (l' - l") + T_bv*[(B'-V') - (B"-V")]
    """

    # See ccdTransformationEquation for more information

    LOGE10 = np.log(10)  # just for convenience

    inst_term = -2.5 * np.log10(instadu/instadu_ref)
    trns_term = transf*(color - color_ref)

    stdmag = stdmag_ref + inst_term + trns_term

    inst_erra = (insterr/(instadu*LOGE10))**2
    inst_errb = (insterr_ref/(instadu_ref*LOGE10))**2
    inst_err2 = 6.25 * (inst_erra + inst_errb)

    transf_errt = (transferr*(color - color_ref))**2
    transf_erra = (transf*colorerr)**2
    transf_errb = (transf*colorerr_ref)**2
    transf_err2 = transf_errt + transf_erra + transf_errb

    stdmagerr = np.sqrt(stdmagerr_ref**2 + inst_err2 + transf_err2)

    return stdmag, stdmagerr


def ccdTransfSimpyfied2(instadu, instadu_ref, stdmag_ref,
                        insterr, insterr_ref, stdmagerr_ref):
    """
    This function is a very simplified version of
    ccdTransformationEquation. It computes the transformation
    from instrumental magnitude to standard magnitude.

    Parameters
    ----------
    instadu: float or array-like
        The instrumental flux of the target star (ADU counts).
    instadu_ref: float or array-like
        The instrumental flux of the reference star (ADU counts).
    stdmag_ref: float
        The standard magnitude of the reference star.
    insterr: float or array-like
        The error on instrumental flux of the target star.
    insterr_ref: float or arrya-like
        The error on the instrumental flux of the reference star.
    stdmagerr_ref: float
        The error on the standard magnitude for the refenence star.

    Returns
    -------
    stdmag: float or array-like
        The standard magnitude of the target star

    stdmagerr: float or aray-like
        The error for the standard magnitude of the target star

    Notes
    -----

    see help(ccdTransformationEquation) for the full deriavation
    of the transformation equation:

        L' = L" + (l' - l") - k*(X' - X") + T_bv*[(B'-V') - (B"-V")]

    If the star are very colse, X' - X" ~ 0 so the airmass
    correction term cancels out. And if the stars have the
    same color, then [(B'-V') - (B"-V")] ~ 0 and the color
    correction term cancels out too:

        L' = L" + (l' - l")
    """

    # See ccdTransformationEquation for more information

    LOGE10 = np.log(10)  # just for convenience

    inst_term = -2.5 * np.log10(instadu/instadu_ref)

    stdmag = stdmag_ref + inst_term

    inst_erra = (insterr/(instadu*LOGE10))**2
    inst_errb = (insterr_ref/(instadu_ref*LOGE10))**2
    inst_err2 = 6.25 * (inst_erra + inst_errb)

    stdmagerr = np.sqrt(stdmagerr_ref**2 + inst_err2)

    return stdmag, stdmagerr


def getInstColor(b1_counts, b2_counts, b1_error, b2_error):
    """
    This function is computes the transformation color
    index of a star using two photometric bands.

    Parameters
    ----------
    b1_counts: float or array-like
        The instrumental flux of the target star
        in the first band (ADU counts).
    b2_counts: float or array-like
        The instrumental flux of the target star
        in the second band (ADU counts).
    b1_error: float or array-like
        The error on instrumental flux of the target
        star in the first band.
    b2_error: float or arrya-like
        The error on instrumental flux of the target
        star in the second band.

    Returns
    -------
    color_index: float
        The color index of the target star

    color_error: float
        The error for the color index of the target star

    Notes
    -----
    The instrumental magnitude l is defined as

        l = -2.5 * log10(f) = -2.5 * log10(ADU/g)

    where

        log10 is the base 10 logarithm.
        f is the fulx of the star.
        ADU is the measured ADU counts.
        g is the exposure time.

    The color index of a star is defined as the difference
    of the magnitudes in two photometric bands B1 and B2
    (which usually are B and V):

        C(B1, B2) = L(B1) - L(B1) =
            = -2.5*log10(Flux_B1) +2.5*log10(Flux_B2) =
            = -2.5*log10(Flux_B1/Flux_B2)

    Where Flux_B1 and Flux_B2 are the fluxes of the target
    star in the two bands B1 and B2.

    Ignowing the arimass correcions, and assuming that the
    number of ADU counts is directly proportional to the
    number of electrons wich comes from the sensor and thus
    is directly proportional to the number of photon hitting
    the sensor, then we can define

        f1 = ADU1/g = k * Flux_B1
        f2 = ADU2/g = k * Flux_B2

    therefore

        C(B1, B2) = -2.5*log10((f1/k)/(f2/k)) =
                  = -2.5*log10(f1/f2) =
                  = -2.5*log10(ADU1/ADU2)
    """

    LOGE10 = np.log(10)  # just for convenience

    color_index_list = -2.5*np.log10(b1_counts/b2_counts)

    ###########################################################
    #                STANDARD ERROR PROPAGATION               #
    ###########################################################
    #
    # NOTE: We cannot compute the average of each adu counts
    #       because they are NOT repeated measueres of the
    #       SAME quantity as the adu count can vary over the
    #       time due to atmospheric extincion, etc.
    #       The only quantity wich remains constants is the
    #       b1_counts/b2_counts ratio.
    #
    # if V = f(A,B) then the error for V is
    #
    #   DV = sqrt(|DA*df(A,B)/dA|**2 + |DB*df(A,B)/dB|**2)
    #
    # since the color index is
    #
    #   star_bv_index = -2.5*np.log10(b1_counts/b2_counts)
    #
    # then, if we define
    #
    #   A = b1_counts     DA = b1_error
    #   B = b1_counts     DB = b2_error
    #   f = log10
    #
    # the error on inst_term is:
    #
    #   inst_err^2=6.25*(|DA*df(A,B)/dA|^2 + |DB*df(A,B)/dB|^2)
    #   = 6.25*(|DA*1/[A*ln(10)]|^2 + |DB * -1/[B*ln(10)|^2)
    #   = 6.25*(|DA/[A*ln(10)]|^2 + |DB/[B*ln(10)]|^2)

    b1_rerr2 = (b1_error/(b1_counts*LOGE10))**2
    b2_rerr2 = (b2_error/(b2_counts*LOGE10))**2

    color_error2 = 6.25*(b1_rerr2+b2_rerr2)

    wei = 1 / color_error2

    color_index = np.average(color_index_list, weights=wei)
    color_error = np.sqrt(color_error2.mean())
    return (color_index, color_error)


def genStarPSF():
    # TODO: todo
    pass 


def getStarFWHM(subdata):
    # Does not work... needs improvements
    h = subdata.shape[0]
    w = subdata.shape[1]

    cx = w/2.0
    cy = h/2.0

    x = np.linspace(0, w, w)
    y = np.linspace(0, h, h)
    x, y = np.meshgrid(x, y)

    if len(subdata.shape) > 2:
        subdata = subdata.max(2)

    submax = np.unravel_index(subdata.argmax(), subdata.shape)
    off = subdata.min()
    amp = subdata.max() - off
    sx = 10
    sy = 10
   
    guess = (amp, submax[1], submax[0], sx, sy, 0, off)
    print(guess)
    popt, pcov = opt.curve_fit(utils.gaussian, (x, y), subdata.ravel(), p0=guess)

    popt[1] += w/2
    popt[2] += h/2

    return popt
