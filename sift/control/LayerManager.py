#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

PURPOSE
Manage the layer sets.

REFERENCES

REQUIRES

:author: Eva Schiffer <evas@ssec.wisc.edu>
:copyright: 2015 by University of Wisconsin Regents, see AUTHORS for more details
:license: GPLv3, see LICENSE for more details
"""
__author__ = 'evas'
__docformat__ = 'reStructuredText'

import logging
from PyQt4.QtCore import SIGNAL, QObject, Qt, pyqtSignal
from PyQt4.QtGui import (QWidget, QListView, QComboBox, QSlider, QTreeView,
                         QGridLayout, QVBoxLayout, QLabel, QLineEdit,
                         QScrollArea, QLayout, QTextDocument,
                         QDoubleValidator, QTextEdit, QFont, QSizePolicy)
from weakref import ref
from sift.common import INFO, KIND
from sift.control.layer_tree import LayerStackTreeViewModel
from sift.model.layer import DocLayer, DocBasicLayer, DocCompositeLayer, DocRGBLayer
from sift.ui.custom_widgets import QNoScrollWebView
import numpy as np
from sift.view.Colormap import ALL_COLORMAPS
from uuid import UUID

LOG = logging.getLogger(__name__)


class LayerSetsManager(QObject):
    """This is the controller object that manages the extended functionality of the layer sets.
    """

    document = None
    tab_widget = None
    layer_sets = None
    max_tab_number = None
    set_behaviors = None
    layer_info_pane = None
    rgb_config = None

    @property
    def didChangeRGBLayerComponentRange(self):
        return self.rgb_config_pane.didChangeRGBLayerComponentRange

    @property
    def didChangeRGBLayerSelection(self):
        return self.rgb_config_pane.didChangeRGBLayerSelection

    def __init__(self, ui, tab_view_widget:QWidget, layer_info_widget:QWidget, document):

        super(LayerSetsManager, self).__init__(tab_view_widget)

        self.document = document

        # hang on to the various widgets for later
        self.tab_widget = tab_view_widget

        self.layer_info_pane = SingleLayerInfoPane(layer_info_widget, document)
        self.rgb_config_pane = RGBLayerConfigPane(ui, layer_info_widget, document)

        if tab_view_widget.count() > 1:
            LOG.warning("Unexpected number of tabs present at start up in the layer list set pane.")

        # set up our layer sets and make the first one
        self.layer_sets = []
        self.max_tab_number = 1
        self.set_up_tab(0, do_increment_tab_number=False)
        self.set_behaviors.uuidSelectionChanged.connect(self.layer_info_pane.update_display)
        self.set_behaviors.uuidSelectionChanged.connect(self.rgb_config_pane.selection_did_change)

        # hook things up so we know when the selected tab changes
        self.tab_widget.connect(self.tab_widget,
                                SIGNAL('currentChanged(int)'),
                                self.handle_tab_change)

    def handle_tab_change (self, ) :
        """deal with the fact that the tab changed in the tab widget
        """

        newTabIndex = self.tab_widget.currentIndex()

        # self.layer_info_pane.setVisible(False)  # FIXME DEBUG
        # self.rgb_config_pane.setVisible(True)  # FIXME DEBUG

        # if this is the last tab, make a new tab and switch to that
        if newTabIndex == (self.tab_widget.count() - 1) :
            LOG.info ("Creating new layer set tab.")

            self.set_up_tab(newTabIndex)

        # tell the document which layer set we're using now
        self.document.select_layer_set(newTabIndex)

    def set_up_tab(self, new_tab_index, do_increment_tab_number=True) :
        """Build a new layer set tab
        """

        # increment our tab label number if desired
        if do_increment_tab_number :
            self.max_tab_number = self.max_tab_number + 1

        # create our tab
        temp_widget = QWidget()
        self.tab_widget.insertTab(new_tab_index, temp_widget, str(self.max_tab_number))

        # create the associated graph display object
        new_layer_set = SingleLayerSetManager(temp_widget, str(self.max_tab_number))
        self.layer_sets.append(new_layer_set)
        layer_list_obj = new_layer_set.getLayerList()
        if self.set_behaviors is None :
            self.set_behaviors = LayerStackTreeViewModel([layer_list_obj], self.document, parent=self.tab_widget)
        else:
            self.set_behaviors.add_widget(layer_list_obj)

        # go to the tab we just created
        self.tab_widget.setCurrentIndex(new_tab_index)

    def getLayerStackListViewModel (self, ) :
        return self.set_behaviors


class SingleLayerSetManager (QWidget) :
    """handles controls and data for a single layer list
    """

    my_name = None
    my_layer_list = None

    def __init__(self, parent, set_name) :
        """set up the controls and signals for this layer set
        """

        super(SingleLayerSetManager, self).__init__(parent)

        self.my_name = set_name

        # create our controls

        # the list of layers
        self.my_layer_list = QTreeView (parent)

        # set the layout
        # Note: add in a grid is (widget, row#, col#) or (widget, row#, col#, row_span, col_span)
        layout = QGridLayout()
        layout.addWidget(self.my_layer_list,   1, 1)
        parent.setLayout(layout)

    def getLayerList (self,) :

        return self.my_layer_list


class SingleLayerInfoPane(QObject):
    """shows details about one layer that is selected in the list
    """

    document = None
    name_text = None
    time_text = None
    instrument_text = None
    band_text = None
    colormap_text = None
    clims_text = None

    def __init__(self, parent, document):
        """build our info display
        """
        super(SingleLayerInfoPane, self).__init__(parent)

        self.document = document  # FUTURE: make this a weakref?

        # build our layer detail info display controls
        self.name_text = QLabel("")
        self.name_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.time_text = QLabel("")
        self.time_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.instrument_text = QLabel("")
        self.instrument_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.band_text = QLabel("")
        self.band_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wavelength_text = QLabel("")
        self.wavelength_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.colormap_text = QLabel("")
        self.colormap_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clims_text = QLabel("")
        self.clims_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cmap_vis = QNoScrollWebView()
        self.cmap_vis.setFixedSize(3 * 100, 30)
        self.cmap_vis.page().mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.composite_details = QLabel("Composite Details")
        self.composite_details.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        f = QFont()
        f.setUnderline(True)
        self.composite_details.setFont(f)
        self.composite_codeblock = QTextEdit()
        self.composite_codeblock.setReadOnly(True)
        self.composite_codeblock.setMinimumSize(3 * 100, 100)
        self.composite_codeblock.setDisabled(True)
        self.composite_codeblock.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        # set the layout
        # Note: add in a grid is (widget, row#, col#) or (widget, row#, col#, row_span, col_span)
        layout = QGridLayout()
        layout.addWidget(self.name_text,       1, 1)
        layout.addWidget(self.time_text,       2, 1)
        layout.addWidget(self.instrument_text, 3, 1)
        layout.addWidget(self.band_text,       4, 1)
        layout.addWidget(self.wavelength_text, 5, 1)
        layout.addWidget(self.colormap_text,   6, 1)
        layout.addWidget(self.clims_text,      7, 1)
        layout.addWidget(self.cmap_vis, 8, 1)
        layout.addWidget(self.composite_details, 9, 1)
        layout.addWidget(self.composite_codeblock, 10, 1)
        parent.setLayout(layout)

        # clear out the display
        self.update_display()

    def update_display(self, selected_uuid_list=None):
        """update the information being displayed to match the given UUID(s)

        If the uuid list parameter is None, clear out the information instead
        """
        if selected_uuid_list is not None and len(selected_uuid_list)==1:
            layer_uuid, = list(selected_uuid_list)
            layer_info = self.document[layer_uuid]
            is_rgb = isinstance(layer_info, DocRGBLayer)

        # clear the list if we got None
        if selected_uuid_list is None or len(selected_uuid_list) <= 0:
            # set the various text displays
            self.name_text.setText("Name: ")
            self.time_text.setText("Time: ")
            self.instrument_text.setText("Instrument: ")
            self.band_text.setText("Band: ")
            self.wavelength_text.setText("Wavelength: ")
            self.colormap_text.setText("Colormap: ")
            self.clims_text.setText("Color Limits: ")
            self.cmap_vis.setHtml("")
            self.composite_codeblock.setText("")
        else:
            # otherwise display information on the selected layer(s)
            # figure out the info shared between all the layers currently selected
            shared_info = {}
            presentation_info = self.document.current_layer_set
            for layer_uuid in selected_uuid_list:

                layer_info = self.document.get_info(uuid=layer_uuid)

                this_prez = None
                for prez_tuple in presentation_info :
                    if prez_tuple.uuid == layer_uuid :
                        this_prez = prez_tuple

                # compare our various values

                # name
                new_name = layer_info[INFO.DISPLAY_NAME] if INFO.DISPLAY_NAME in layer_info else ""
                if INFO.DISPLAY_NAME not in shared_info:
                    shared_info[INFO.DISPLAY_NAME] = new_name
                else:
                    shared_info[INFO.DISPLAY_NAME] = "" if shared_info[INFO.DISPLAY_NAME] != new_name else new_name

                # time
                new_time = layer_info[INFO.DISPLAY_TIME] if INFO.DISPLAY_TIME in layer_info else ""
                if INFO.DISPLAY_TIME not in shared_info :
                    shared_info[INFO.DISPLAY_TIME] = new_time
                else :
                    shared_info[INFO.DISPLAY_TIME] = "" if shared_info[INFO.DISPLAY_TIME] != new_time else new_time

                # instrument
                new_inst = str(layer_info[INFO.INSTRUMENT].value) if layer_info.get(INFO.INSTRUMENT) else ""
                if INFO.INSTRUMENT not in shared_info :
                    shared_info[INFO.INSTRUMENT] = new_inst
                else :
                    shared_info[INFO.INSTRUMENT] = "" if shared_info[INFO.INSTRUMENT] != new_inst else new_inst

                # band
                new_band = layer_info.get(INFO.BAND)
                if isinstance(new_band, (tuple, list)):
                    new_band = "(" + ", ".join([str(x) if x is not None else '---' for x in new_band]) + ")"
                else:
                    new_band = str(new_band) if new_band is not None else '---'
                if INFO.BAND not in shared_info:
                    shared_info[INFO.BAND] = new_band
                else:
                    shared_info[INFO.BAND] = "---" if shared_info[INFO.BAND] != new_band else new_band

                # wavelength
                wl = layer_info.get(INFO.CENTRAL_WAVELENGTH)
                fmt = "{:0.2f} µm"
                if isinstance(wl, (tuple, list)):
                    wl = [fmt.format(x) if x is not None else '---' for x in wl]
                    wl = "(" + ", ".join(wl) + ")"
                else:
                    wl = fmt.format(wl) if wl is not None else '---'
                if INFO.CENTRAL_WAVELENGTH not in shared_info:
                    shared_info[INFO.CENTRAL_WAVELENGTH] = wl
                else:
                    shared_info[INFO.CENTRAL_WAVELENGTH] = "---" if shared_info[INFO.CENTRAL_WAVELENGTH] != wl else wl

                # colormap
                new_cmap = this_prez.colormap if this_prez is not None else ""
                if "colormap" not in shared_info:
                    shared_info["colormap"] = new_cmap
                else :
                    shared_info["colormap"] = "" if shared_info["colormap"] != new_cmap else new_cmap

                # c-limits
                new_clims = ""
                if this_prez is not None:
                    new_clims = np.array(this_prez.climits)
                    unit_info = self.document[this_prez.uuid][INFO.UNIT_CONVERSION]
                    new_clims = unit_info[1](new_clims, inverse=False)
                    try:
                        if layer_info[INFO.KIND] in [KIND.IMAGE, KIND.COMPOSITE]:
                            min_str = layer_info[INFO.UNIT_CONVERSION][2](new_clims[0], include_units=False)
                            max_str = layer_info[INFO.UNIT_CONVERSION][2](new_clims[1])
                            new_clims = '{} ~ {}'.format(min_str, max_str)
                        else:
                            # FUTURE: Other layer types
                            deps = (layer_info.r, layer_info.g, layer_info.b)

                            tmp_clims = []
                            for i, dep in enumerate(deps):
                                if dep is None:
                                    tmp_clims.append('N/A')
                                    continue

                                min_str = dep[INFO.UNIT_CONVERSION][2](new_clims[i][0], include_units=False)
                                max_str = dep[INFO.UNIT_CONVERSION][2](new_clims[i][1])
                                tmp_clims.append('{} ~ {}'.format(min_str, max_str))
                            new_clims = ", ".join(tmp_clims)
                    except TypeError as err:
                        LOG.warning("unable to format color limit: %r" % (new_clims,), exc_info=True)
                        new_clims = "N/A"
                if "climits" not in shared_info :
                    shared_info["climits"] = new_clims
                else :
                    shared_info["climits"] = "" if shared_info["climits"] != new_clims else new_clims

                # color map
                cmap = this_prez.colormap if this_prez is not None else None
                if "colormap" not in shared_info:
                    shared_info["colormap"] = cmap
                else:
                    shared_info["colormap"] = None if shared_info["colormap"] != cmap else cmap

                ns, codeblock = self.document.get_algebraic_namespace(layer_uuid)
                if codeblock:
                    short_names = []
                    for name, uuid in ns.items():
                        try:
                            dep_info = self.document[uuid]
                            short_name = dep_info.get(INFO.SHORT_NAME, '<Unknown>')
                        except KeyError:
                            LOG.debug("Layer '{}' not found in document".format(uuid))
                            short_name = '<Unknown>'
                        short_names.append("# {} = {}".format(name, short_name))
                    ns_str = "\n".join(short_names)
                    codeblock_str = ns_str + '\n\n' + codeblock
                else:
                    codeblock_str = ''
                if 'codeblock' not in shared_info:
                    shared_info['codeblock'] = codeblock_str
                else:
                    shared_info['codeblock'] = '' if shared_info['codeblock'] != codeblock_str else codeblock_str

            # set the various text displays
            temp_name = shared_info[INFO.DISPLAY_NAME] if INFO.DISPLAY_NAME in shared_info else ""
            self.name_text.setText("Name: " + temp_name)
            temp_time = shared_info[INFO.DISPLAY_TIME] if INFO.DISPLAY_TIME in shared_info else ""
            self.time_text.setText("Time: " + (temp_time or ""))
            temp_inst = shared_info[INFO.INSTRUMENT] if INFO.INSTRUMENT in shared_info else ""
            self.instrument_text.setText("Instrument: " + temp_inst)
            temp_band = shared_info[INFO.BAND] if INFO.BAND in shared_info else ""
            self.band_text.setText("Band: " + temp_band)
            temp_wl = shared_info[INFO.CENTRAL_WAVELENGTH] if INFO.CENTRAL_WAVELENGTH in shared_info else ""
            self.wavelength_text.setText("Wavelength: " + temp_wl)
            temp_cmap = shared_info["colormap"] if shared_info.get("colormap", None) is not None else ""
            self.colormap_text.setText("Colormap: " + temp_cmap)
            temp_clims = shared_info["climits"] if "climits" in shared_info else ""
            self.clims_text.setText("Color Limits: " + temp_clims)
            self.composite_codeblock.setText(shared_info['codeblock'])

            # format colormap
            if shared_info.get("colormap", None) is None:
                self.cmap_vis.setHtml("")
            else:
                cmap_html = ALL_COLORMAPS[shared_info["colormap"]]._repr_html_()
                cmap_html = cmap_html.replace("height", "border-collapse: collapse;\nheight")
                self.cmap_vis.setHtml("""<html><head></head><body style="margin: 0px"><div>%s</div></body></html>""" % (cmap_html,))

RGBA2IDX = dict(r=0, g=1, b=2, a=3)


class RGBLayerConfigPane(QObject):
    """Configures RGB channel selection and ranges on behalf of document.
    Document in turn generates update signals which cause the SceneGraph to refresh.
    """
    document_ref = None  # weakref to document
    active_layer_ref = None  # weakref to RGB layer we're currently showing

    didChangeRGBLayerSelection = pyqtSignal(UUID, str, object)  # layer being changed, character from 'rgba', layer being assigned
    didChangeRGBLayerComponentRange = pyqtSignal(UUID, str, float, float)  # layer being changed, char from 'rgba', new-min, new-max

    _rgb = None  # combo boxes in r,g,b order; cache
    _sliders = None  # sliders in r,g,b order; cache
    _edits = None
    _valid_ranges = None # tuples of each layer's c-limits
    _gamma_boxes = None # tuple of each layer's gamma spin boxes
    _uuids = None  # [r-uuid, g, b]; used for conversion purposes

    def __init__(self, ui, parent, document):
        super(RGBLayerConfigPane, self).__init__(parent)
        self.document_ref = ref(document)
        self.ui = ui
        self._valid_ranges = [None, None, None]
        self._uuids = [None, None, None ]
        from functools import partial

        # TODO: Put in UI file?
        self._slider_steps = 100
        self.ui.slideMinRed.setRange(0, self._slider_steps)
        self.ui.slideMaxRed.setRange(0, self._slider_steps)
        self.ui.slideMinGreen.setRange(0, self._slider_steps)
        self.ui.slideMaxGreen.setRange(0, self._slider_steps)
        self.ui.slideMinBlue.setRange(0, self._slider_steps)
        self.ui.slideMaxBlue.setRange(0, self._slider_steps)

        self._double_validator = qdoba = QDoubleValidator()
        self.ui.editMinRed.setValidator(qdoba)
        self.ui.editMaxRed.setValidator(qdoba)
        self.ui.editMinGreen.setValidator(qdoba)
        self.ui.editMaxGreen.setValidator(qdoba)
        self.ui.editMinBlue.setValidator(qdoba)
        self.ui.editMaxBlue.setValidator(qdoba)

        [x.currentIndexChanged.connect(partial(self._combo_changed, combo=x, color=rgb))
         for rgb,x in zip(('b', 'g', 'r'), (self.ui.comboBlue, self.ui.comboGreen, self.ui.comboRed))]
        [x.sliderReleased.connect(partial(self._slider_changed, slider=x, color=rgb, is_max=False))
         for rgb,x in zip(('b', 'g', 'r'), (self.ui.slideMinBlue, self.ui.slideMinGreen, self.ui.slideMinRed))]
        [x.sliderReleased.connect(partial(self._slider_changed, slider=x, color=rgb, is_max=True))
         for rgb, x in zip(('b', 'g', 'r'), (self.ui.slideMaxBlue, self.ui.slideMaxGreen, self.ui.slideMaxRed))]
        [x.editingFinished.connect(partial(self._edit_changed, line_edit=x, color=rgb, is_max=False))
         for rgb, x in zip(('b', 'g', 'r'), (self.ui.editMinBlue, self.ui.editMinGreen, self.ui.editMinRed))]
        [x.editingFinished.connect(partial(self._edit_changed, line_edit=x, color=rgb, is_max=True))
         for rgb, x in zip(('b', 'g', 'r'), (self.ui.editMaxBlue, self.ui.editMaxGreen, self.ui.editMaxRed))]
        [x.valueChanged.connect(self._gamma_changed)
         for rgb, x in zip(('b', 'g', 'r'), (self.ui.redGammaSpinBox, self.ui.greenGammaSpinBox, self.ui.blueGammaSpinBox))]

    @property
    def rgb(self):
        if self._rgb is None:
            self._rgb = [self.ui.comboRed, self.ui.comboGreen, self.ui.comboBlue]
            return self._rgb
        else:
            return self._rgb

    @property
    def sliders(self):
        if self._sliders is None:
            self._sliders = [
                (self.ui.slideMinRed, self.ui.slideMaxRed),
                (self.ui.slideMinGreen, self.ui.slideMaxGreen),
                (self.ui.slideMinBlue, self.ui.slideMaxBlue),
            ]
        return self._sliders

    @property
    def line_edits(self):
        if self._edits is None:
            self._edits = [
                (self.ui.editMinRed, self.ui.editMaxRed),
                (self.ui.editMinGreen, self.ui.editMaxGreen),
                (self.ui.editMinBlue, self.ui.editMaxBlue),
            ]
        return self._edits

    @property
    def gamma_boxes(self):
        if self._gamma_boxes is None:
            self._gamma_boxes = (
                self.ui.redGammaSpinBox,
                self.ui.greenGammaSpinBox,
                self.ui.blueGammaSpinBox,
            )
        return self._gamma_boxes

    def _gamma_changed(self, value):
        gamma = tuple(x.value() for x in self.gamma_boxes)
        self.document_ref().change_gamma_for_siblings(self.active_layer_ref().uuid, gamma)

    def _combo_changed(self, index, combo:QComboBox=None, color=None):
        """
        user changed combo box, relay that to upstream as didChangeRGBLayerSelection
        :return:
        """
        uuid_str = combo.itemData(index)

        LOG.debug("RGB: user selected %s for %s" % (uuid_str, color))
        if uuid_str:
            uuid = UUID(uuid_str)
            new_layer = self.document_ref()[uuid]
            self._uuids[RGBA2IDX[color]] = uuid
        else:
            new_layer = None
            self._uuids[RGBA2IDX[color]] = None
        # reset slider position to min and max for layer
        self._set_minmax_slider(color, new_layer)
        self.didChangeRGBLayerSelection.emit(self.active_layer_ref().uuid, color, new_layer)

    def _display_to_data(self, color:str, values):
        "convert display value to data value"
        uuid = self._uuids[RGBA2IDX[color]]
        if not uuid:
            return values
        return self.document_ref()[uuid][INFO.UNIT_CONVERSION][1](values, inverse=True)

    def _data_to_display(self, color:str, values):
        "convert data value to display value"
        uuid = self._uuids[RGBA2IDX[color]]
        if not uuid:
            return values
        return self.document_ref()[uuid][INFO.UNIT_CONVERSION][1](values)

    def _get_slider_value(self, valid_min, valid_max, slider_val):
        return (slider_val / self._slider_steps) * (valid_max - valid_min) + valid_min

    def _create_slider_value(self, valid_min, valid_max, channel_val):
        return ((channel_val - valid_min) / (valid_max - valid_min)) * self._slider_steps

    def _min_max_for_color(self, rgba:str):
        """
        return min value, max value as represented in sliders
        :param rgba: char in 'rgba'
        :return: (min-value, max-value) where min can be > max
        """
        idx = RGBA2IDX[rgba]
        slider = self.sliders[idx]
        valid_min, valid_max = self._valid_ranges[idx]
        n = self._get_slider_value(valid_min, valid_max, slider[0].value())
        x = self._get_slider_value(valid_min, valid_max, slider[1].value())
        return n, x

    def _update_line_edits(self, color:str, n:float=None, x:float=None):
        """
        update edit controls to match non-None values provided
        if called with just color, returns current min and max
        implicitly convert data values to and from display values
        :param color: in 'rgba'
        :param n: minimum data value or None
        :param x: max data value or None
        :return: new min, new max
        """
        idx = RGBA2IDX[color]
        edn, edx = self.line_edits[idx]
        if n is not None:
            ndis = self._data_to_display(color, n)
            LOG.debug('%s min %f => %f' % (color, n, ndis))
            edn.setText('%f' % ndis)
        else:
            ndis = float(edn.text())
            n = self._display_to_data(color, ndis)
        if x is not None:
            xdis = self._data_to_display(color, x)
            edx.setText('%f' % xdis)
        else:
            xdis = float(edx.text())
            x = self._display_to_data(color, xdis)
        return n, x

    def _signal_color_changing_range(self, color:str, n:float, x:float):
        self.didChangeRGBLayerComponentRange.emit(self.active_layer_ref().uuid, color, n, x)

    def _slider_changed(self, slider=None, color:str=None, is_max:bool=False):
        """
        handle slider update event from user
        :param slider: control
        :param color: char in 'rgba'
        :param is_max: whether slider's value represents the max or the min
        :return:
        """
        idx = RGBA2IDX[color]
        valid_min, valid_max = self._valid_ranges[idx]
        val = self._get_slider_value(valid_min, valid_max, slider.value())
        LOG.debug('slider %s %s => %f' % (color, 'max' if is_max else 'min', val))
        n, x = self._update_line_edits(color, val if not is_max else None, val if is_max else None)
        self._signal_color_changing_range(color, n, x)

    def _edit_changed(self, line_edit:QLineEdit=None, color:str=None, is_max:bool=False):
        """
        update relevant slider value, propagate to the document
        :param line_edit: field that got a new value
        :param color: in 'rgba'
        :param is_max: whether the min or max edit field was changed
        :return:
        """
        idx = RGBA2IDX[color]
        vn, vx= self._valid_ranges[idx]
        vdis = float(line_edit.text())
        val = self._display_to_data(color, vdis)
        LOG.debug('line edit %s %s => %f => %f' % (color, 'max' if is_max else 'min', vdis, val))
        sv = self._create_slider_value(vn, vx, val)
        slider = self.sliders[idx][1 if is_max else 0]
        slider.setValue(sv)
        self._signal_color_changing_range(color, *self._update_line_edits(color))

    def selection_did_change(self, uuids=None):
        """
        document has changed selection sets,
        figure out if we're active or not and enable/disable
        if we're active, allow user to change which channels to use
        :param uuids: list of selected UUIDs
        :return:
        """
        doc = self.document_ref()
        if uuids is not None and len(uuids)==1:
            layer_uuid = uuids[0]
            layer = doc[layer_uuid]
            is_rgb = isinstance(layer, DocRGBLayer)
            self._show_settings_for_layer(None if not is_rgb else layer)
        else:
            self._show_settings_for_layer(None)

    def _show_settings_for_layer(self, layer):
        self.active_layer_ref = ref(layer) if layer is not None else None
        if layer is None:
            for slider in self.sliders:
                slider[0].setDisabled(True)
                slider[1].setDisabled(True)
            for combo in self.rgb:
                combo.setDisabled(True)
            for edit in self.line_edits:
                edit[0].setDisabled(True)
                edit[1].setDisabled(True)
            for sbox in self.gamma_boxes:
                sbox.setDisabled(True)
            return
        else:
            # re-enable all the widgets
            for slider in self.sliders:
                slider[0].setDisabled(False)
                slider[1].setDisabled(False)
            for combo in self.rgb:
                combo.setDisabled(False)
            for edit in self.line_edits:
                edit[0].setDisabled(False)
                edit[1].setDisabled(False)
            for sbox in self.gamma_boxes:
                sbox.setDisabled(False)

        for widget in self.rgb:
            # block signals so an existing RGB layer doesn't get overwritten with new layer selections
            widget.blockSignals(True)

        guuid = lambda lyr: lyr.uuid if lyr is not None else None
        self._uuids = [guuid(layer.r), guuid(layer.g), guuid(layer.b)] if layer is not None else [None, None, None]

        # update the combo boxes
        self._set_combos_to_layer_names()
        self._select_layers_for(layer)
        self._set_minmax_sliders(layer)
        self._set_gamma_boxes(layer)

        for widget in self.rgb:
            # block signals so an existing RGB layer doesn't get overwritten with new layer selections
            widget.blockSignals(False)

    def _set_minmax_slider(self, color:str, layer, clims=None, valid_range=None):
        idx = RGBA2IDX[color]
        slider = self.sliders[idx]
        editn, editx = self.line_edits[idx]
        if layer is None:
            self._valid_ranges[idx] = None
            slider[0].setSliderPosition(0)
            slider[1].setSliderPosition(0)
            editn.setText('0.0')
            editx.setText('0.0')
        else:
            valid_range = self.document_ref().valid_range_for_uuid(layer.uuid) if valid_range is None else valid_range
            clims = valid_range if clims is None else clims
            self._valid_ranges[idx] = valid_range

            slider_val = self._create_slider_value(valid_range[0], valid_range[1], clims[0])
            slider[0].setSliderPosition(max(slider_val, 0))
            slider_val = self._create_slider_value(valid_range[0], valid_range[1], clims[1])
            slider[1].setSliderPosition(min(slider_val, self._slider_steps))
            self._update_line_edits(color, *clims)

    def _set_minmax_sliders(self, layer=None, rgb_clims=None):
        if isinstance(layer, DocRGBLayer):
            prez, = self.document_ref().prez_for_uuids([layer.uuid])
            rgb_clims = prez.climits if rgb_clims is None else rgb_clims
            for idx, (color, sub_layer) in enumerate(zip("rgb", [layer.r, layer.g, layer.b])):
                clim = rgb_clims[idx] if rgb_clims else None
                self._set_minmax_slider(color, sub_layer, clim)
        else:
            self._set_minmax_slider("r", None)
            self._set_minmax_slider("g", None)
            self._set_minmax_slider("b", None)

    def _select_layers_for(self, layer=None):
        """
        set combo boxes to match selection for a given composite layer
        :param layer:
        :return:
        """
        if isinstance(layer, DocRGBLayer):
            for slayer,widget in zip([layer.r, layer.g, layer.b], self.rgb):
                if slayer is None:
                    widget.setCurrentIndex(0)
                else:
                    dex = widget.findData(str(slayer.uuid))
                    if dex<=0:
                        widget.setCurrentIndex(0)
                        LOG.error('layer %s not available to be selected' % repr(slayer))
                    else:
                        widget.setCurrentIndex(dex)
        else:
            for widget in self.rgb:
                widget.setCurrentIndex(0)

    def _set_combos_to_layer_names(self):
        """
        update combo boxes with the list of layer names and then select the right r,g,b,a layers if they're not None
        :return:
        """
        doc = self.document_ref()
        non_rgb_classes = [DocBasicLayer, DocCompositeLayer]
        # non_rgb_kinds = [k for k in KIND if k != KIND.RGB]

        # clear out the current lists
        layer_list = list(doc.layers_where(is_valid=True, in_type_set=non_rgb_classes))
        for widget in self.rgb:
            widget.clear()
            widget.addItem('None', '')

        # fill up our lists of layers
        for layer_prez in doc.layers_where(is_valid=True, in_type_set=non_rgb_classes):
            uuid = layer_prez.uuid
            layer = doc[layer_prez.uuid]
            layer_name = layer[INFO.DISPLAY_NAME]
            LOG.debug('adding layer %s to RGB combo selectors' % layer_name)
            uuid_string = str(uuid)
            for widget in self.rgb:
                widget.addItem(layer_name, uuid_string)

    def _set_gamma_boxes(self, layer=None):
        if isinstance(layer, DocRGBLayer):
            prez, = self.document_ref().prez_for_uuids([layer.uuid])
            for idx, sbox in enumerate(self.gamma_boxes):
                sbox.setValue(prez.gamma[idx])
        else:
            for idx, sbox in enumerate(self.gamma_boxes):
                sbox.setValue(1.)
