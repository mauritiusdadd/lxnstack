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
# - http://www.aavso.org/differential-vs-absolute-photometry
# - http://brucegary.net/DifferentialPhotometry/dp.htm#1._
# - http://www.britastro.org/vss/ccd_photometry.htm
# - http://www.physics.csbsju.edu/370/photometry/manuals/OU.edu_CCD_photometry_wrccd06.pdf

import utils
import plotting
import numpy as np
import scipy as sp
import scipy.stats

class LightCurvePlot(plotting.Plot):

    def exportNumericDataCSV(self):
        file_name = str(Qt.QFileDialog.getSaveFileName(
            None,
            tr.tr("Save the project"),
            os.path.join(self.current_dir, 'lightcurves.csv'),
            "CSV *.csv (*.csv);;All files (*.*)",
            None,
            utils.DIALOG_OPTIONS))
        # utils.exportTableCSV(self, self.wnd.numDataTableWidget,
        #                      file_name, sep='\t', newl='\n')

def getInstMagnitudeADU(star, ndimg=None):
    val_adu = []
    bkg_adu = []
    ir2 = star.r1**2
    mr2 = star.r2**2
    or2 = star.r3**2

    if ndimg is None:
        ndimg = star.getParent().getData()

    stx, sty = star.getAbsolutePosition()

    for x in range(-int(star.r1)-1, int(star.r1)+1):
        for y in range(-int(star.r1)-1, int(star.r1)+1):
            p = (x**2 + y**2)
            if p <= ir2:
                val_adu.append(ndimg[sty+y, stx+x])

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
    #     we use sigmaclip here to remove evetual cosmic rays
    #     or hot-pixels present in the sky background
    bkg_adu = sp.stats.sigmaclip(np.array(bkg_adu),4,4)[0]

    # val_adu_sigma = np.sqrt(val_adu)
    # bkg_adu_sigma = np.sqrt(bkg_adu)
    # Computing these values is only a waste of resources, see NOTE(2)


    # These are the total counts of ADUs (directly poportional
    # to the number of photons hitting the photodiode, unless
    # we are near the saturation)
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
