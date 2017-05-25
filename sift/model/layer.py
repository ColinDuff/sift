#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
layer.py
~~~~~~~~~

PURPOSE
Document Layer & LayerDoc

REFERENCES


REQUIRES


:author: R.K.Garcia <rayg@ssec.wisc.edu>
:copyright: 2014 by University of Wisconsin Regents, see AUTHORS for more details
:license: GPLv3, see LICENSE for more details
"""
from _weakref import ref
from collections import MutableMapping
from itertools import chain
from enum import Enum
from sift.common import INFO, KIND

__author__ = 'rayg'
__docformat__ = 'reStructuredText'

import os
import sys
import logging
import numpy as np
import unittest
import argparse

LOG = logging.getLogger(__name__)

# class LayerStack(list):
#     """
#     A LayerStack includes
#     - stacking of layers
#     - reordering of layers
#     - time-ordered grouping of similar layers
#     - time sequence animation
#     Layer types includes
#     - background images
#     - RGB imagery tiles from GeoTIFF or other
#     - Imagery field tiles with color maps
#     - markers and selections
#     - geopolitical vector boundaries
#
#     Everything in LayerDoc should be serializable in order to load an identical configuration later.
#     LayerDoc interacts with view classes to manage drawing plan and layer representations.
#     Scripts and UI Controls can modify the LayerDoc, which propagates update signals to its dependencies
#     Facets - LayerDocAsTimeSeries for instance, will be introduced as needed to manage complexity
#     Multiple LayerDocs may be present, especially if we're copying content like color maps over
#     """
#
#     _layerlist = None
#
#
#     def __init__(self, document, init_layers=None):
#         super(LayerStack, self).__init__()
#         self._layerlist = list(init_layers or [])
#
#
#     def __iter__(self):
#         # FIXME: this is an animation test pattern
#         if self.animating:
#             todraw = self._layerlist[self.frame_number % len(self._layerlist)]
#             todraw.z = 0
#             yield todraw
#             return
#         for level,layer in enumerate(reversed(self._layerlist)):
#             layer.z = float(level)
#             yield layer
#
#
#     def __getitem__(self, item):
#         return self._layerlist[item]
#
#
#     def __len__(self):
#         return len(self._layerlist)
#
#
#     def append(self, layer):
#         self._layerlist.append(layer)
#         # self.layerStackDidChangeOrder.emit(tuple(range(len(self))))
#
#
#     def __delitem__(self, dex):
#         order = list(range(len(self)))
#         del self._layerlist[dex]
#         del order[dex]
#         # self.layerStackDidChangeOrder(tuple(order))
#
#
#     def swap(self, adex, bdex):
#         order = list(range(len(self)))
#         order[bdex], order[adex] = adex, bdex
#         new_list = [self._layerlist[dex] for dex in order]
#         self._layerlist = new_list
#         # self.layerStackDidChangeOrder.emit(tuple(order))
#
#
#
#     # @property
#     # def top(self):
#     #     return self._layerlist[0] if self._layerlist else None
#     #
#
#     @property
#     def listing(self):
#         """
#         return representation summary for layer list - name, icon, source, etc
#         """
#         for layer in self._layerlist:
#             yield {'name': str(layer.name)}
#



class mixing(Enum):
    UNKNOWN = 0
    NORMAL = 1
    ADD = 2
    SUBTRACT = 3


class DocLayer(MutableMapping):
    """
    Layer as represented within the document
    Essentially: A helper representation of a layer and part of the public interface to the document.
    Substitutes in for document layer information dictionaries initially,
      but eventually dictionary interfaces will be limited to non-standard annotation keys.
    Incrementally migrate functionality from Document into these classes as appropriate, to keep Document from getting too complicated.
    Make sure that DocLayer classes remain serializable and long-term connected only to the document, not to UI elements or workspace.
    """
    _doc = None  # weakref to document that owns us

    def __init__(self, doc, *args, **kwargs):
        self._doc = ref(doc)
        # store of metadata that comes from the input content and does not change
        self._definitive = dict()
        # implied metadata that was derived from definitive metadata
        self._implied_cache = dict()
        self._definitive.update(dict(*args, **kwargs))

    @property
    def parent(self):
        """
        parent layer, if any
        :return:
        """
        return None

    @property
    def children(self):
        """
        return dictionary of weakrefs to layers we require in order to function
        :return:
        """
        return {}

    @property
    def uuid(self):
        """
        UUID of the layer, which for basic layers is likely to be the UUID of the dataset in the workspace.
        :return:
        """
        return self._definitive[INFO.UUID]

    @property
    def kind(self):
        """
        which kind of layer it is - RGB, Algebraic, etc. This can also be tested by the class of the layer typically.
         We may deprecate this eventually?
        :return:
        """
        return self._definitive[INFO.KIND]

    @property
    def band(self):
        return self._definitive.get(INFO.BAND, None)

    @property
    def instrument(self):
        return self._definitive.get(INFO.INSTRUMENT, None)

    @property
    def platform(self):
        return self._definitive.get(INFO.PLATFORM, None)

    @property
    def sched_time(self):
        return self._definitive.get(INFO.SCHED_TIME, None)

    @property
    def dataset_name(self):
        return self._definitive[INFO.DATASET_NAME]

    @property
    def display_name(self):
        return self._implied_cache[INFO.DISPLAY_NAME]

    @display_name.setter
    def display_name(self, value):
        self._implied_cache[INFO.DISPLAY_NAME] = value

    @property
    def is_valid(self):
        """
        invalid layers cannot be displayed (are never visible)
        valid layers may or may not be visible
        visibility is managed by the scenegraph
        validity is managed by the document
        example of an invalid layer: an RGB or algebraic layer that's insufficiently specified to actually display,
        be it through lack of data or lack of projection information
        however, an invalid layer may still be configurable in order to allow it to become valid and then visible
        :return: bool
        """
        return True

    @property
    def is_flat_field(self):
        """
        return whether the layer can be represented as a flat numerical field or not (RGB layers cannot)
        :return: bool
        """
        return True

    def __getitem__(self, key):
        if key not in self._definitive:
            return self._implied_cache[key]
        return self._definitive[key]

    def __setitem__(self, key, value):
        if key in self._definitive:
            raise ValueError("Can't set value on definitive metadata: {}".format(key))
        self._implied_cache[key] = value

    def __delitem__(self, key):
        if key in self._definitive:
            raise ValueError("Can't delete definitive metadata: {}".format(key))
        del self._implied_cache[key]

    def update(self, *args, **kwds):
        if args:
            kwds.update(args[0])
        for k, v in kwds.items():
            self[k] = v

    def __iter__(self):
        return chain(iter(self._definitive), iter(self._implied_cache))

    def __len__(self):
        return len(self._definitive) + len(self._implied_cache)


class DocBasicLayer(DocLayer):
    """
    A layer consistent of a simple scalar floating point value field, which can have color maps applied
    """
    pass


class DocCompositeLayer(DocLayer):
    """
    A layer which combines other layers, be they basic or composite themselves
    """
    def __getitem__(self, key):
        value = super(DocCompositeLayer, self).__getitem__(key)
        # FIXME debug
        if key == INFO.KIND:
            assert(value == KIND.RGB)
        return value

def _concurring(*q):
    if len(q)==0:
        return None
    elif len(q)==1:
        return q[0]
    for a,b in zip(q[:-1], q[1:]):
        if a!=b:
            return False
    return q[0]


class DocRGBLayer(DocCompositeLayer):
    def __init__(self, *args, **kwargs):
        self.l = [None, None, None, None]  # RGBA upstream layers
        self.n = [None, None, None, None]  # RGBA minimum value from upstream layers
        self.x = [None, None, None, None]  # RGBA maximum value from upstream layers
        if len(args) and isinstance(args, dict):
            args[0].setdefault(INFO.KIND, KIND.RGB)
        super().__init__(*args, **kwargs)

    @property
    def r(self):
        return self.l[0]
    @property
    def g(self):
        return self.l[1]
    @property
    def b(self):
        return self.l[2]
    @property
    def a(self):
        return self.l[3]

    @r.setter
    def r(self, x):
        self.l[0] = x
    @g.setter
    def g(self, x):
        self.l[1] = x
    @b.setter
    def b(self, x):
        self.l[2] = x
    @a.setter
    def a(self, x):
        self.l[3] = x

    @property
    def has_deps(self):
        return (self.r is not None or
                self.g is not None or
                self.b is not None)

    @property
    def shared_projections(self):
        return all(x[INFO.PROJ] == self[INFO.PROJ] for x in self.l[:3] if x is not None)

    @property
    def shared_origin(self):
        if all(x is None for x in self.l[:3]):
            return False

        atol = max(abs(x[INFO.CELL_WIDTH])
                   for x in self.l[:3] if x is not None)
        shared_x = all(np.isclose(x[INFO.ORIGIN_X], self[INFO.ORIGIN_X], atol=atol)
                       for x in self.l[:3] if x is not None)

        atol = max(abs(x[INFO.CELL_HEIGHT])
                   for x in self.l[:3] if x is not None)
        shared_y = all(np.isclose(x[INFO.ORIGIN_Y], self[INFO.ORIGIN_Y], atol=atol)
                       for x in self.l[:3] if x is not None)
        return shared_x and shared_y

    @property
    def is_valid(self):
        return self.has_deps and self.shared_projections and \
               self.shared_origin

    @property
    def is_flat_field(self):
        return False

    @property
    def band(self):
        gb = lambda l: None if (l is None) else l.band
        return (gb(self.r), gb(self.g), gb(self.b))

    @property
    def sched_time(self):
        gst = lambda x: None if (x is None) else x.sched_time
        return _concurring(gst(self.r), gst(self.g), gst(self.b))

    @property
    def instrument(self):
        gst = lambda x: None if (x is None) else x.instrument
        return _concurring(gst(self.r), gst(self.g), gst(self.b))

    @property
    def platform(self):
        gst = lambda x: None if (x is None) else x.platform
        return _concurring(gst(self.r), gst(self.g), gst(self.b))

    def update_metadata_from_dependencies(self):
        """
        recalculate origin and dimension information based on new upstream
        :return:
        """
        # FUTURE: resolve dictionary-style into attribute-style uses
        dep_info = [self.r, self.g, self.b]
        display_time = self._doc()._guidebook._default_display_time(self)
        name = self._doc()._guidebook._default_display_name(self, display_time=display_time)
        bands = [nfo.get(INFO.BAND) if nfo is not None else None for nfo in dep_info]
        insts = [nfo.get(INFO.INSTRUMENT) if nfo is not None else None for nfo in dep_info]
        plats = [nfo.get(INFO.PLATFORM) if nfo is not None else None for nfo in dep_info]
        ds_info = {
            INFO.DATASET_NAME: name,
            INFO.DISPLAY_NAME: name,
            INFO.DISPLAY_TIME: display_time,
            INFO.BAND: bands,
            INFO.INSTRUMENT: insts[0] if all(inst == insts[0] for inst in insts[1:]) else None,
            INFO.PLATFORM: plats[0] if all(plat == plats[0] for plat in plats[1:]) else None,
            INFO.UNIT_CONVERSION: self._doc()._guidebook.units_conversion(self),
        }

        if self.r is None and self.g is None and self.b is None:
            ds_info.update({
                INFO.ORIGIN_X: None,
                INFO.ORIGIN_Y: None,
                INFO.CELL_WIDTH: None,
                INFO.CELL_HEIGHT: None,
                INFO.PROJ: None,
                INFO.CLIM: ((None, None), (None, None), (None, None)),  # defer initialization until we have upstream layers
            })
        else:
            highest_res_dep = min([x for x in dep_info if x is not None], key=lambda x: x[INFO.CELL_WIDTH])
            ds_info.update({
                INFO.ORIGIN_X: highest_res_dep[INFO.ORIGIN_X],
                INFO.ORIGIN_Y: highest_res_dep[INFO.ORIGIN_Y],
                INFO.CELL_WIDTH: highest_res_dep[INFO.CELL_WIDTH],
                INFO.CELL_HEIGHT: highest_res_dep[INFO.CELL_HEIGHT],
                INFO.PROJ: highest_res_dep[INFO.PROJ],
            })

            old_clim = self.get(INFO.CLIM, None)
            if not old_clim:  # initialize from upstream default maxima
                ds_info[INFO.CLIM] = tuple(tuple(d[INFO.CLIM]) if d is not None else (None, None) for d in dep_info)
            else:  # merge upstream with existing settings, replacing None with upstream; watch out for upstream==None case
                upclim = lambda up: (None, None) if (up is None) else tuple(up.get(INFO.CLIM, (None, None)))
                ds_info[INFO.CLIM] = tuple((existing or upclim(upstream)) for (existing,upstream) in zip(old_clim, dep_info))

        self.update(ds_info)
        if not self.shared_projections:
            LOG.warning("RGB dependency layers don't share the same projection")
        if not self.shared_origin:
            LOG.warning("RGB dependency layers don't share the same origin")

        return ds_info


class DocAlgebraicLayer(DocCompositeLayer):
    """
    A value field derived from other value fields algebraically
    """
    pass



# class DocMapLayer(DocLayer):
#     """
#     FUTURE: A layer containing a background map as vector
#     """
#     pass
#
# class DocShapeLayer(DocLayer):
#     """
#     FUTURE: A layer represented in the scene graph as an editable shape
#     """
#     pass
#
# class DocProbeLayer(DocShapeLayer):
#     """
#     FUTURE: A shape layer which feeds probe values to another UI element or helper.
#     """



def main():
    parser = argparse.ArgumentParser(
        description="PURPOSE",
        epilog="",
        fromfile_prefix_chars='@')
    parser.add_argument('-v', '--verbose', dest='verbosity', action="count", default=0,
                        help='each occurrence increases verbosity 1 level through ERROR-WARNING-INFO-DEBUG')
    # http://docs.python.org/2.7/library/argparse.html#nargs
    # parser.add_argument('--stuff', nargs='5', dest='my_stuff',
    #                    help="one or more random things")
    parser.add_argument('pos_args', nargs='*',
                        help="positional arguments don't have the '-' prefix")
    args = parser.parse_args()

    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level=levels[min(3, args.verbosity)])

    if not args.pos_args:
        unittest.main()
        return 0

    for pn in args.pos_args:
        pass

    return 0


if __name__ == '__main__':
    sys.exit(main())

