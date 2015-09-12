# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging
from xml.dom import minidom

import log
import utils
import imgfeatures
import lightcurves as lcurves


def getProjectAbsURL(project_dir, url):
    if os.path.isabs(url):
        return url
    else:
        abs_url = os.path.join(project_dir, url)
        return os.path.realpath(abs_url)


class Project(object):

    def __init__(self, frame_open_args):

        self.frame_open_args = frame_open_args

        self.bias_frames = []
        self.dark_frames = []
        self.flat_frames = []
        self.light_frames = []

        self.master_bias_url = ""
        self.master_dark_url = ""
        self.master_flat_url = ""

        self.master_bias_mul = 1
        self.master_dark_mul = 1
        self.master_flat_mul = 1

        self.use_master_bias = False
        self.use_master_dark = False
        self.use_master_flat = False

        self.imw = -1
        self.imh = -1
        self.dep = -1

        self.current_image_idx = -1

        self.aap_rectangle = (-1, -1)
        self.max_points = -1
        self.min_quality = -1
        self.use_whole_image = -1
        self.use_image_time = False
        self.project_directory = ""
        self.channel_mapping = {}

    def loadProject(self, project_fname=None):

        if not project_fname.strip():
            log.log(repr(self),
                    ' no project selected, retvert to previous state',
                    level=logging.INFO)
            return None
        else:
            log.log(repr(self),
                    ' project name: \''+str(project_fname)+'\'',
                    level=logging.DEBUG)

        proj_path = os.path.dirname(project_fname)

        try:
            dom = minidom.parse(project_fname)
        except Exception as err:
            log.log(repr(self),
                    'failed to parse project, xml formatting error',
                    level=logging.ERROR)
            return self.corruptedMsgBox(err)

        try:
            root = dom.getElementsByTagName('project')[0]
            information_node = root.getElementsByTagName('information')[0]
            dark_frames_node = root.getElementsByTagName('dark-frames')[0]
            flat_frames_node = root.getElementsByTagName('flat-frames')[0]
            pict_frames_node = root.getElementsByTagName('frames')[0]

            try:  # backward compatibility
                bs_node_list = root.getElementsByTagName('bias-frames')
                bias_frames_node = bs_node_list[0]

                mbs_list = information_node.getElementsByTagName('master-bias')
                master_bias_node = mbs_list[0]

                mbs_ckd = master_bias_node.getAttribute('checked')
                master_bias_checked = int(mbs_ckd)

                mbs_mul = master_bias_node.getAttribute('mul')
                master_bias_mul = float(mbs_mul)
                has_bias_section = True
            except Exception as exc:
                log.log(repr(self),
                        'No bias section',
                        level=logging.DEBUG)
                master_bias_node = None
                has_bias_section = False

            try:  # backward compatibility
                photometry_list = root.getElementsByTagName('photometry')
                photometry_node = photometry_list[0]
                has_photometry_section = True
            except Exception as exc:
                log.log(repr(self),
                        'no fotometric section, skipping star loading',
                        level=logging.DEBUG)
                has_photometry_section = False

            log.log(repr(self),
                    'loading project information',
                    level=logging.DEBUG)

            cdir_lst = information_node.getElementsByTagName('current-dir')
            crow_lst = information_node.getElementsByTagName('current-row')
            mdrk_lst = information_node.getElementsByTagName('master-dark')
            mflt_lst = information_node.getElementsByTagName('master-flat')
            arct_lst = information_node.getElementsByTagName('align-rect')
            mp_lst = information_node.getElementsByTagName('max-align-points')
            mq_lst = information_node.getElementsByTagName('min-point-quality')

            current_dir_node = cdir_lst[0]
            current_row_node = crow_lst[0]
            master_dark_node = mdrk_lst[0]
            master_flat_node = mflt_lst[0]
            align_rect_node = arct_lst[0]
            max_points_node = mp_lst[0]
            min_quality_node = mq_lst[0]

            imw = int(information_node.getAttribute('width'))
            imh = int(information_node.getAttribute('height'))
            dep = int(information_node.getAttribute('mode'))

            try:
                bayer_mode = int(information_node.getAttribute('bayer-mode'))
            except:
                bayer_mode = -1

            ar_w = int(align_rect_node.getAttribute('width'))
            ar_h = int(align_rect_node.getAttribute('height'))
            use_whole_image = int(align_rect_node.getAttribute('whole-image'))
            max_points = int(max_points_node.getAttribute('value'))
            min_quality = float(min_quality_node.getAttribute('value'))

            current_dir = current_dir_node.getAttribute('url')
            current_row = int(current_row_node.getAttribute('index'))
            master_dark_checked = int(master_dark_node.getAttribute('checked'))
            master_flat_checked = int(master_flat_node.getAttribute('checked'))
            master_dark_mul = float(master_dark_node.getAttribute('mul'))
            master_flat_mul = float(master_flat_node.getAttribute('mul'))

            try:
                url_node = master_bias_node.getElementsByTagName('url')[0]
                node_url = url_node.childNodes[0].data
                master_bias_url = getProjectAbsURL(proj_path, node_url)
            except:
                master_bias_url = ''

            try:
                url_node = master_dark_node.getElementsByTagName('url')[0]
                node_url = url_node.childNodes[0].data
                master_dark_url = getProjectAbsURL(proj_path, node_url)
            except:
                master_dark_url = ''

            try:
                url_node = master_flat_node.getElementsByTagName('url')[0]
                node_url = url_node.childNodes[0].data
                master_flat_url = getProjectAbsURL(proj_path, node_url)
            except:
                master_flat_url = ''

            biasframelist = []
            if has_bias_section:
                log.log(repr(self),
                        'reading bias-frames section',
                        level=logging.DEBUG)
                for node in bias_frames_node.getElementsByTagName('image'):
                    im_bias_name = node.getAttribute('name')
                    try:
                        im_bias_used = int(node.getAttribute('used'))
                    except Exception as exc:
                        try:
                            st_im_used = str(node.getAttribute('used')).lower()
                            if st_im_used.lower() == 'false':
                                im_bias_used = 0
                            elif st_im_used.lower() == 'true':
                                im_bias_used = 2
                            else:
                                raise exc
                        except:
                            im_bias_used = 2

                    url_bias_node = node.getElementsByTagName('url')[0]
                    _bias_url = url_bias_node.childNodes[0].data
                    im_bias_url = getProjectAbsURL(proj_path, _bias_url)

                    if 'page' in url_bias_node.attributes.keys():
                        im_bias_page = url_bias_node.getAttribute('page')
                        biasfrm = utils.Frame(im_bias_url,
                                              int(im_bias_page),
                                              skip_loading=False,
                                              **self.frame_open_args)
                    else:
                        biasfrm = utils.Frame(im_bias_url,
                                              0,
                                              skip_loading=False,
                                              **self.frame_open_args)
                    biasfrm.tool_name = im_bias_name
                    biasfrm.width = imw
                    biasfrm.height = imh
                    biasfrm.mode = dep
                    biasfrm.setUsed(im_bias_used)

                    biasfrm.addProperty('frametype', utils.BIAS_FRAME_TYPE)
                    biasframelist.append(biasfrm)

            log.log(repr(self),
                    'reading dark-frames section',
                    level=logging.DEBUG)

            darkframelist = []
            for node in dark_frames_node.getElementsByTagName('image'):
                im_dark_name = node.getAttribute('name')
                try:
                    im_dark_used = int(node.getAttribute('used'))
                except Exception as exc:
                    try:
                        st_im_used = str(node.getAttribute('used')).lower()
                        if st_im_used.lower() == 'false':
                            im_dark_used = 0
                        elif st_im_used.lower() == 'true':
                            im_dark_used = 2
                        else:
                            raise exc
                    except:
                        im_dark_used = 2

                url_dark_node = node.getElementsByTagName('url')[0]
                _dark_url = url_dark_node.childNodes[0].data
                im_dark_url = getProjectAbsURL(proj_path, _dark_url)

                if 'page' in url_dark_node.attributes.keys():
                    im_dark_page = url_dark_node.getAttribute('page')
                    darkfrm = utils.Frame(im_dark_url,
                                          int(im_dark_page),
                                          skip_loading=False,
                                          **self.frame_open_args)
                else:
                    darkfrm = utils.Frame(im_dark_url,
                                          0,
                                          skip_loading=False,
                                          **self.frame_open_args)
                darkfrm.tool_name = im_dark_name
                darkfrm.width = imw
                darkfrm.height = imh
                darkfrm.mode = dep
                darkfrm.setUsed(im_dark_used)

                darkfrm.addProperty('frametype', utils.DARK_FRAME_TYPE)
                darkframelist.append(darkfrm)

            log.log(repr(self),
                    'reading flatfield-frames section',
                    level=logging.DEBUG)

            flatframelist = []
            for node in flat_frames_node.getElementsByTagName('image'):
                im_flat_name = node.getAttribute('name')
                try:
                    im_flat_used = int(node.getAttribute('used'))
                except Exception as exc:
                    try:
                        st_im_used = str(node.getAttribute('used')).lower()
                        if st_im_used.lower() == 'false':
                            im_flat_name = 0
                        elif st_im_used.lower() == 'true':
                            im_flat_name = 2
                        else:
                            raise exc
                    except:
                        im_flat_name = 2

                url_flat_node = node.getElementsByTagName('url')[0]
                _flat_url = url_flat_node.childNodes[0].data
                im_flat_url = getProjectAbsURL(proj_path, _flat_url)

                if 'page' in url_flat_node.attributes.keys():
                    im_flat_page = url_flat_node.getAttribute('page')
                    flatfrm = utils.Frame(im_flat_url,
                                          int(im_flat_page),
                                          skip_loading=False,
                                          **self.frame_open_args)
                else:
                    flatfrm = utils.Frame(im_flat_url,
                                          0,
                                          skip_loading=False,
                                          **self.frame_open_args)
                flatfrm.tool_name = im_flat_name
                flatfrm.width = imw
                flatfrm.height = imh
                flatfrm.mode = dep
                flatfrm.setUsed(im_flat_used)

                flatfrm.addProperty('frametype', utils.FLAT_FRAME_TYPE)
                flatframelist.append(flatfrm)

            log.log(repr(self),
                    'reading light-frames section',
                    level=logging.DEBUG)

            framelist = []
            for node in pict_frames_node.getElementsByTagName('image'):
                im_name = node.getAttribute('name')
                try:
                    im_used = int(node.getAttribute('used'))
                except Exception as exc:
                    st_im_used = str(node.getAttribute('used')).lower()
                    if st_im_used.lower() == 'false':
                        im_used = 0
                    elif st_im_used.lower() == 'true':
                        im_used = 2
                    else:
                        raise exc

                im_url_node = node.getElementsByTagName('url')[0]
                _url = im_url_node.childNodes[0].data
                im_url = getProjectAbsURL(proj_path, _url)

                if 'page' in im_url_node.attributes.keys():
                    im_page = im_url_node.getAttribute('page')
                    frm = utils.Frame(im_url,
                                      int(im_page),
                                      skip_loading=True,
                                      **self.frame_open_args)
                else:
                    frm = utils.Frame(im_url,
                                      0,
                                      skip_loading=True,
                                      **self.frame_open_args)

                for point in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_al = point.getAttribute('aligned').lower()
                    point_al = bool(point_al == 'True')
                    point_x = int(point.getAttribute('x'))
                    point_y = int(point.getAttribute('y'))
                    pnt = imgfeatures.AlignmentPoint(point_x, point_y,
                                                     point_id, point_id)
                    pnt.aligned = point_al
                    frm.addAlignPoint(pnt)

                for s in node.getElementsByTagName('star'):
                    st_x = int(s.getAttribute('x'))
                    st_y = int(s.getAttribute('y'))
                    st_name = s.getAttribute('name')
                    st_id = s.getAttribute('id')
                    st_r1 = float(s.getAttribute('inner_radius'))
                    st_r2 = float(s.getAttribute('middle_radius'))
                    st_r3 = float(s.getAttribute('outer_radius'))
                    st_ref = bool(int(s.getAttribute('reference')))
                    st_mag = {}

                    for attrname in s.attributes.keys():
                        if attrname[0:4] == 'mag_':
                            bandname = attrname[4:]
                            magval = float(s.getAttribute(attrname))
                            st_mag[bandname] = magval
                        else:
                            continue

                    st = imgfeatures.Star(st_x, st_y,
                                          st_name, st_id)
                    st.r1 = st_r1
                    st.r2 = st_r2
                    st.r3 = st_r3
                    st.reference = st_ref
                    st.magnitude = st_mag
                    frm.addStar(st)

                for star in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_al = point.getAttribute('aligned').lower()
                    point_al = bool(point_al == 'True')
                    point_x = int(point.getAttribute('x'))
                    point_y = int(point.getAttribute('y'))
                    pnt = imgfeatures.AlignmentPoint(point_x, point_y,
                                                     point_id, point_id)
                    pnt.aligned = point_al
                    frm.alignpoints.append(pnt)

                offset_node = node.getElementsByTagName('offset')[0]
                offset_x = float(offset_node.getAttribute('x'))
                offset_y = float(offset_node.getAttribute('y'))

                if 'theta' in offset_node.attributes.keys():
                    offset_t = float(offset_node.getAttribute('theta'))
                else:
                    offset_t = 0

                frm.tool_name = im_name
                frm.width = imw
                frm.height = imh
                frm.mode = dep
                frm.setOffset([offset_x, offset_y])
                frm.setAngle(offset_t)
                frm.setUsed(im_used)

                frm.addProperty('frametype', utils.LIGHT_FRAME_TYPE)
                framelist.append(frm)

            if has_photometry_section:
                log.log(repr(self),
                        'reading photometry section',
                        level=logging.DEBUG)
                time_attr = int(photometry_node.getAttribute('time_type'))
                use_image_time = bool(time_attr)

                # photometry section
                channel_mapping = {}
                sels = photometry_node.getElementsByTagName('channel')
                for comp in sels:
                    idx = int(comp.getAttribute('index'))
                    nme = comp.getAttribute('band')
                    channel_mapping[idx] = nme
            else:
                use_image_time = self.use_image_time
                channel_mapping = lcurves.getComponentTable(dep)

        except Exception as exc:
            log.log(repr(self),
                    'An error has occurred while reading the project:' +
                    '\"' + str(exc) + '\"',
                    level=logging.ERROR)
            raise(exc)

        self.imw = imw
        self.imh = imh
        self.dep = dep

        self.light_frames = framelist
        self.bias_frames = biasframelist
        self.dark_frames = darkframelist
        self.flat_frames = flatframelist

        self.current_image_idx = current_row

        self.master_bias_url = master_bias_url
        self.master_dark_url = master_dark_url
        self.master_flat_url = master_flat_url

        self.master_bias_mul = master_bias_mul
        self.master_dark_mul = master_dark_mul
        self.master_flat_mul = master_flat_mul

        self.use_master_bias = bool(master_bias_checked)
        self.use_master_dark = bool(master_dark_checked)
        self.use_master_flat = bool(master_flat_checked)

        self.bayer_mode = bayer_mode
        self.aap_rectangle = (ar_w, ar_h)
        self.max_points = max_points
        self.min_quality = min_quality
        self.use_whole_image = use_whole_image
        self.project_directory = current_dir

        self.use_image_time = use_image_time
        self.channel_mapping = channel_mapping
        log.log(repr(self),
                'project fully loaded',
                level=logging.INFO)

    def saveProject(self, project_fname):
        doc = minidom.Document()

        root = doc.createElement('project')
        doc.appendChild(root)

        information_node = doc.createElement('information')
        bias_frames_node = doc.createElement('bias-frames')
        dark_frames_node = doc.createElement('dark-frames')
        flat_frames_node = doc.createElement('flat-frames')
        pict_frames_node = doc.createElement('frames')
        photometry_node = doc.createElement('photometry')

        root.appendChild(information_node)
        root.appendChild(bias_frames_node)
        root.appendChild(dark_frames_node)
        root.appendChild(flat_frames_node)
        root.appendChild(pict_frames_node)
        root.appendChild(photometry_node)

        # <information> section
        information_node.setAttribute('width', str(int(self.imw)))
        information_node.setAttribute('height', str(int(self.imh)))
        information_node.setAttribute('mode', str(int(self.dep)))
        information_node.setAttribute('bayer-mode', str(int(self.bayer_mode)))

        current_dir_node = doc.createElement('current-dir')
        current_row_node = doc.createElement('current-row')
        master_bias_node = doc.createElement('master-bias')
        master_dark_node = doc.createElement('master-dark')
        master_flat_node = doc.createElement('master-flat')
        min_quality_node = doc.createElement('min-point-quality')
        max_points_node = doc.createElement('max-align-points')
        align_rect_node = doc.createElement('align-rect')

        information_node.appendChild(current_dir_node)
        information_node.appendChild(current_row_node)
        information_node.appendChild(master_bias_node)
        information_node.appendChild(master_dark_node)
        information_node.appendChild(master_flat_node)
        information_node.appendChild(align_rect_node)
        information_node.appendChild(max_points_node)
        information_node.appendChild(min_quality_node)

        mb_cck_state = self.use_master_bias*2
        md_cck_state = self.use_master_dark*2
        mf_cck_state = self.use_master_flat*2

        current_dir_node.setAttribute('url', str(self.project_directory))
        current_row_node.setAttribute('index', str(self.current_image_idx))
        master_bias_node.setAttribute('checked', str(mb_cck_state))
        master_bias_node.setAttribute('mul', str(self.master_bias_mul))
        master_dark_node.setAttribute('checked', str(md_cck_state))
        master_dark_node.setAttribute('mul', str(self.master_dark_mul))
        master_flat_node.setAttribute('checked', str(mf_cck_state))
        master_flat_node.setAttribute('mul', str(self.master_flat_mul))
        align_rect_node.setAttribute('width', str(self.aap_rectangle[0]))
        align_rect_node.setAttribute('height', str(self.aap_rectangle[1]))
        align_rect_node.setAttribute('whole-image', str(self.use_whole_image))
        max_points_node.setAttribute('value', str(self.max_points))
        min_quality_node.setAttribute('value', str(self.min_quality))

        url = doc.createElement('url')
        url_txt = doc.createTextNode(str(self.master_bias_url))
        url.appendChild(url_txt)
        master_bias_node.appendChild(url)

        url = doc.createElement('url')
        url_txt = doc.createTextNode(str(self.master_dark_url))
        url.appendChild(url_txt)
        master_dark_node.appendChild(url)

        url = doc.createElement('url')
        url_txt = doc.createTextNode(str(self.master_flat_url))
        url.appendChild(url_txt)
        master_flat_node.appendChild(url)

        # <bias-frams> section
        for i in self.bias_frames:
            im_bias_used = str(i.isUsed())
            im_bias_name = str(i.tool_name)
            im_bias_page = i.page
            im_bias_url = i.url

            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_bias_name)
            image_node.setAttribute('used', im_bias_used)
            bias_frames_node.appendChild(image_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_bias_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_bias_page))
            image_node.appendChild(url)

        # <dark-frams> section
        for i in self.dark_frames:
            im_dark_used = str(i.isUsed())
            im_dark_name = str(i.tool_name)
            im_dark_page = i.page
            im_dark_url = i.url
            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_dark_name)
            image_node.setAttribute('used', im_dark_used)
            dark_frames_node.appendChild(image_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_dark_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_dark_page))
            image_node.appendChild(url)

        # <flat-frames> section
        for i in self.flat_frames:
            im_flat_used = str(i.isUsed())
            im_flat_name = str(i.tool_name)
            im_flat_page = i.page
            im_flat_url = i.url
            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_flat_name)
            image_node.setAttribute('used', im_flat_used)
            flat_frames_node.appendChild(image_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_flat_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_flat_page))
            image_node.appendChild(url)

        # <frames> section
        for img in self.light_frames:
            im_used = str(img.isUsed())
            im_name = str(img.tool_name)
            im_page = img.page
            im_url = img.url
            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_name)
            image_node.setAttribute('used', im_used)

            pict_frames_node.appendChild(image_node)

            for point in img.alignpoints:
                point_node = doc.createElement('align-point')
                point_node.setAttribute('x', str(int(point.x)))
                point_node.setAttribute('y', str(int(point.y)))
                point_node.setAttribute('id', str(point.id))
                point_node.setAttribute('name', str(point.name))
                point_node.setAttribute('aligned', str(point.aligned))
                image_node.appendChild(point_node)

            for s in img.stars:
                star_node = doc.createElement('star')
                star_node.setAttribute('x', str(int(s.x)))
                star_node.setAttribute('y', str(int(s.y)))
                star_node.setAttribute('name', str(s.name))
                star_node.setAttribute('id', str(s.id))
                star_node.setAttribute('inner_radius', str(float(s.r1)))
                star_node.setAttribute('middle_radius', str(float(s.r2)))
                star_node.setAttribute('outer_radius', str(float(s.r3)))
                star_node.setAttribute('reference', str(int(s.reference)))
                for band in s.magnitude:
                    name = "mag_{}".format(band)
                    mag = str(float(s.magnitude[band]))
                    star_node.setAttribute(name, mag)
                image_node.appendChild(star_node)

            offset_node = doc.createElement('offset')
            offset_node.setAttribute('x', str(float(img.offset[0])))
            offset_node.setAttribute('y', str(float(img.offset[1])))
            offset_node.setAttribute('theta', str(float(img.angle)))
            image_node.appendChild(offset_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_page))
            image_node.appendChild(url)

        # photometry section
        img_tm = int(self.use_image_time)
        photometry_node.setAttribute('time_type', str(img_tm))

        # photometry section
        for ch in self.channel_mapping:
            channel_node = doc.createElement('channel')
            channel_node.setAttribute('index', str(ch))
            channel_node.setAttribute('band', str(self.channel_mapping[ch]))
            photometry_node.appendChild(channel_node)

        try:
            f = open(project_fname, 'w')
            f.write(doc.toprettyxml(' ', '\n'))
            f.close()
        except IOError as err:
            log.log(repr(self),
                    "Cannot save the project: " + str(err),
                    level=logging.ERROR)
            raise err
