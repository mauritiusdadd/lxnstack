
# http://www.aavso.org/differential-vs-absolute-photometry
# http://brucegary.net/DifferentialPhotometry/dp.htm#1._
# http://www.britastro.org/vss/ccd_photometry.htm


import numpy as np
import plotting
import utils


class LightCurvePlot(plotting.Plot):
    pass

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

def getStarMagnitudeADU(star, ndimg=None):
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

    val_adu = np.array(val_adu)
    bkg_adu = np.array(bkg_adu)

    total_star_pixels = len(val_adu)

    total_val_adu = val_adu.sum(0)  # total ADU value for the star
    mean_bkg_adu = bkg_adu.mean(0)  # average for the background

    total_val_adu_delta = val_adu.shape[0]  # error value for the star
    mean_bkg_adu_sigma = bkg_adu.std(0)  # average for the background

    # best value for the star
    mean_adu = total_val_adu - mean_bkg_adu*total_star_pixels
    mean_adu_delta = total_val_adu_delta/3.0 + mean_bkg_adu_sigma

    # this avoids negative or null value:
    if (mean_adu > 0).all():
        return (mean_adu, mean_adu_delta)
    else:
        raise ValueError('Negative or null ADU values are not allowed!\n' +
                         'Please set the star marker correctly.')
