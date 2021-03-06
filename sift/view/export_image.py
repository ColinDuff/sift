import os
import sys
import logging

from PyQt4 import QtCore, QtGui
from PIL import Image, ImageDraw, ImageFont

from sift.common import INFO
from sift.ui import export_image_dialog_ui
from sift.util import get_data_dir

LOG = logging.getLogger(__name__)
DATA_DIR = get_data_dir()


def _default_directory():
    try:
        if sys.platform.startswith('win'):
            return os.path.join(os.environ['USERPROFILE'], 'Desktop')
        else:
            return os.path.join(os.path.expanduser('~'), 'Desktop')
    except (KeyError, ValueError):
        return os.getcwd()


class ExportImageDialog(QtGui.QDialog):
    default_filename = 'sift_screenshot.png'

    def __init__(self, parent):
        super(ExportImageDialog, self).__init__(parent)

        self.ui = export_image_dialog_ui.Ui_ExportImageDialog()
        self.ui.setupUi(self)

        self.ui.animationGroupBox.setDisabled(True)
        self.ui.constantDelaySpin.setDisabled(True)
        self.ui.constantDelaySpin.setValue(100)
        self.ui.timeLapseRadio.setChecked(True)
        self.ui.timeLapseRadio.clicked.connect(self._delay_clicked)
        self.ui.constantDelayRadio.clicked.connect(self._delay_clicked)
        self._delay_clicked()

        self.ui.frameRangeFrom.setValidator(QtGui.QIntValidator(1, 1))
        self.ui.frameRangeTo.setValidator(QtGui.QIntValidator(1, 1))
        self.ui.saveAsLineEdit.textChanged.connect(self._validate_filename)
        self.ui.saveAsButton.clicked.connect(self._show_file_dialog)

        self._last_dir = _default_directory()
        self.ui.saveAsLineEdit.setText(os.path.join(self._last_dir, self.default_filename))
        self._validate_filename()

        self.ui.includeFooterCheckbox.clicked.connect(self._footer_changed)
        self._footer_changed()

        self.ui.frameAllRadio.clicked.connect(self.change_frame_range)
        self.ui.frameCurrentRadio.clicked.connect(self.change_frame_range)
        self.ui.frameRangeRadio.clicked.connect(self.change_frame_range)
        self.change_frame_range()  # set default

    def set_total_frames(self, n):
        self.ui.frameRangeFrom.validator().setBottom(1)
        self.ui.frameRangeTo.validator().setBottom(2)
        self.ui.frameRangeFrom.validator().setTop(n - 1)
        self.ui.frameRangeTo.validator().setTop(n)
        if (self.ui.frameRangeFrom.text() == '' or
            int(self.ui.frameRangeFrom.text()) > n - 1):
            self.ui.frameRangeFrom.setText('1')
        if self.ui.frameRangeTo.text() in ['', '1']:
            self.ui.frameRangeTo.setText(str(n))

    def _delay_clicked(self):
        if self.ui.constantDelayRadio.isChecked():
            self.ui.constantDelaySpin.setDisabled(False)
        else:
            self.ui.constantDelaySpin.setDisabled(True)

    def _footer_changed(self):
        if self.ui.includeFooterCheckbox.isChecked():
            self.ui.footerFontSizeSpinBox.setDisabled(False)
        else:
            self.ui.footerFontSizeSpinBox.setDisabled(True)

    def _show_file_dialog(self):
        fn = QtGui.QFileDialog.getSaveFileName(self,
                                               caption=self.tr('Screenshot Filename'),
                                               directory=os.path.join(self._last_dir, self.default_filename),
                                               filter=self.tr('Image Files (*.png *.jpg *.gif)'),
                                               options=QtGui.QFileDialog.DontConfirmOverwrite)
        if fn:
            self.ui.saveAsLineEdit.setText(fn)
        # bring this dialog back in focus
        self.raise_()
        self.activateWindow()

    def _validate_filename(self):
        t = self.ui.saveAsLineEdit.text()
        bt = self.ui.buttonBox.button(QtGui.QDialogButtonBox.Save)
        if not t or os.path.splitext(t)[-1] not in ['.png', '.jpg', '.gif']:
            bt.setDisabled(True)
        else:
            self._last_dir = os.path.dirname(t)
            bt.setDisabled(False)
        self._check_animation_controls()

    def _is_animation_filename(self):
        fn = self.ui.saveAsLineEdit.text()
        return os.path.splitext(fn)[-1] in ['.gif']

    def _check_animation_controls(self):
        disable = (self.ui.frameCurrentRadio.isChecked() or
                   not self._is_animation_filename() or
                   self.ui.frameRangeTo.validator().top() == 1)
        if disable:
            self.ui.animationGroupBox.setDisabled(True)
            self.ui.frameDelayGroup.setDisabled(True)
        else:
            self.ui.animationGroupBox.setDisabled(False)
            self.ui.frameDelayGroup.setDisabled(False)

    def change_frame_range(self):
        if self.ui.frameRangeRadio.isChecked():
            self.ui.frameRangeFrom.setDisabled(False)
            self.ui.frameRangeTo.setDisabled(False)
        else:
            self.ui.frameRangeFrom.setDisabled(True)
            self.ui.frameRangeTo.setDisabled(True)

        self._check_animation_controls()

    def get_frame_range(self):
        if self.ui.frameCurrentRadio.isChecked():
            frame = None
        elif self.ui.frameAllRadio.isChecked():
            frame = [None, None]
        elif self.ui.frameRangeRadio.isChecked():
            frame = [
                int(self.ui.frameRangeFrom.text()),
                int(self.ui.frameRangeTo.text())
            ]
        else:
            LOG.error("Unknown frame range selection")
            return
        return frame

    def get_info(self):
        if self.ui.timeLapseRadio.isChecked():
            delay = None
        else:
            delay = self.ui.constantDelaySpin.value()

        # loop is actually an integer of number of times to loop (0 infinite)
        info = {
            'frame_range': self.get_frame_range(),
            'include_footer': self.ui.includeFooterCheckbox.isChecked(),
            # 'transparency': self.ui.transparentCheckbox.isChecked(),
            'loop': self.ui.loopRadio.isChecked(),
            'filename': self.ui.saveAsLineEdit.text(),
            'delay': delay,
            'font_size': self.ui.footerFontSizeSpinBox.value(),
        }
        return info

    def show(self):
        self._check_animation_controls()
        return super(ExportImageDialog, self).show()


class ExportImageHelper(QtCore.QObject):
    """Handle all the logic for creating screenshot images"""
    default_font = os.path.join(DATA_DIR, 'fonts', 'Andale Mono.ttf')

    def __init__(self, parent, doc, sgm):
        """Initialize helper with defaults and other object handles.
        
        Args:
            doc: Main ``Document`` object for frame metadata
            sgm: ``SceneGraphManager`` object to get image data
        """
        super(ExportImageHelper, self).__init__(parent)
        self.doc = doc
        self.sgm = sgm
        self._screenshot_dialog = None

    def take_screenshot(self):
        if not self._screenshot_dialog:
            self._screenshot_dialog = ExportImageDialog(self.parent())
            self._screenshot_dialog.accepted.connect(self._save_screenshot)
        self._screenshot_dialog.set_total_frames(max(self.sgm.layer_set.max_frame, 1))
        self._screenshot_dialog.show()

    def _add_screenshot_footer(self, im, banner_text, font_size=11):
        orig_w, orig_h = im.size
        font = ImageFont.truetype(self.default_font, font_size)
        banner_h = font_size
        new_im = Image.new(im.mode, (orig_w, orig_h + banner_h), "black")
        new_draw = ImageDraw.Draw(new_im)
        new_draw.rectangle([0, orig_h, orig_w, orig_h + banner_h], fill="#000000")
        # give one extra pixel on the left to make sure letters
        # don't get cut off
        new_draw.text([1, orig_h], banner_text, fill="#ffffff", font=font)
        txt_w, txt_h = new_draw.textsize("SIFT", font)
        new_draw.text([orig_w - txt_w, orig_h], "SIFT", fill="#ffffff", font=font)
        new_im.paste(im, (0, 0, orig_w, orig_h))
        return new_im

    def _create_filenames(self, uuids, base_filename):
        if not uuids or uuids[0] is None:
            return [None], [base_filename]
        filenames = []
        # only use the first uuid to fill in filename information
        file_uuids = uuids[:1] if base_filename.endswith('.gif') else uuids
        for u in file_uuids:
            layer_info = self.doc[u]
            fn = base_filename.format(
                start_time=layer_info[INFO.SCHED_TIME],
                scene=INFO.SCENE,
                instrument=INFO.INSTRUMENT,
            )
            filenames.append(fn)

        # check for duplicate filenames
        if len(filenames) > 1 and all(filenames[0] == fn for fn in filenames):
            ext = os.path.splitext(filenames[0])[-1]
            filenames = [os.path.splitext(fn)[0] + "_{:03d}".format(i + 1) + ext for i, fn in enumerate(filenames)]

        return uuids, filenames

    def _overwrite_dialog(self):
        msg = QtGui.QMessageBox(self.parent())
        msg.setWindowTitle("Overwrite File(s)?")
        msg.setText("One or more files already exist.")
        msg.setInformativeText("Do you want to overwrite existing files?")
        msg.setStandardButtons(msg.Cancel)
        msg.setDefaultButton(msg.Cancel)
        msg.addButton("Overwrite All", msg.YesRole)
        # XXX: may raise "modalSession has been exited prematurely" for pyqt4 on mac
        ret = msg.exec_()
        if ret == msg.Cancel:
            # XXX: This could technically reach a recursion limit
            self.take_screenshot()
            return False
        return True

    def _get_animation_parameters(self, info, images):
        params = {}
        params['save_all'] = True
        if info['delay'] is None:
            t = [self.doc[u][INFO.SCHED_TIME] for u, im in images]
            t_diff = [(t[i] - t[i - 1]).total_seconds() for i in range(1, len(t))]
            min_diff = float(min(t_diff))
            duration = [100 * int(this_diff / min_diff) for this_diff in t_diff]
            params['duration'] = [duration[0]] + duration
            # params['duration'] = [50 * i for i in range(len(images))]
            if not info['loop']:
                params['duration'] = params['duration'] + params['duration'][-2:0:-1]
        else:
            params['duration'] = info['delay']
        if not info['loop']:
            # rocking animation
            # we want frames 0, 1, 2, 3, 2, 1
            images = images + images[-2:0:-1]

        params['loop'] = 0  # infinite number of loops
        params['append_images'] = [x for u, x in images[1:]]
        return params

    def _convert_frame_range(self, frame_range):
        """Convert 1-based frame range to SGM's 0-based"""
        if frame_range is None:
            return None
        s, e = frame_range
        # user provided frames are 1-based, scene graph are 0-based
        if s is None:
            s = 1
        if e is None:
            e = max(self.sgm.layer_set.max_frame, 1)
        return s - 1, e - 1

    def _save_screenshot(self):
        info = self._screenshot_dialog.get_info()
        LOG.info("Exporting image with options: {}".format(info))
        info['frame_range'] = self._convert_frame_range(info['frame_range'])
        if info['frame_range']:
            s, e = info['frame_range']
            uuids = self.sgm.layer_set.frame_order[s: e + 1]
        else:
            uuids = [self.sgm.layer_set.top_layer_uuid()]
        uuids, filenames = self._create_filenames(uuids, info['filename'])

        # check for existing filenames
        if (any(os.path.isfile(fn) for fn in filenames) and
                not self._overwrite_dialog()):
            return

        # get canvas screenshot arrays (numpy arrays of canvas pixels)
        img_arrays = self.sgm.get_screenshot_array(info['frame_range'])
        if not len(img_arrays) or len(uuids) != len(img_arrays):
            LOG.error("Number of frames does not equal number of filenames")
            return

        images = [(u, Image.fromarray(x)) for u, x in img_arrays]
        if info['include_footer']:
            banner_text = [self.doc[u][INFO.DATASET_NAME] if u else "" for u, im in images]
            images = [(u, self._add_screenshot_footer(im, bt, font_size=info['font_size'])) for (u, im), bt in zip(images, banner_text)]

        if filenames[0].endswith('.gif') and len(images) > 1:
            params = self._get_animation_parameters(info, images)
            filenames = filenames[:1]
            images = images[:1]
        else:
            params = {}

        for fn, (u, new_img) in zip(filenames, images):
            LOG.info("Saving screenshot to '{}'".format(fn))
            LOG.debug("File save parameters: {}".format(params))
            new_img.save(fn, **params)

