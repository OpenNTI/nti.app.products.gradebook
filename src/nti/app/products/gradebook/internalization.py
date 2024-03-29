#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook internalization

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import sys
import operator

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from nti.app.externalization.error import raise_json_error

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import ILetterGradeScheme

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater

logger = __import__('logging').getLogger(__name__)


def raise_field_error(request, field, message):
    exc_info = sys.exc_info()
    data = {u'field': field, u'message': message}
    raise_json_error(request, hexc.HTTPUnprocessableEntity, data, exc_info[2])


@component.adapter(IGrade)
@interface.implementer(IInternalObjectUpdater)
class _GradeObjectUpdater(InterfaceObjectIO):

    # INterface object io doesn't seem to have a way to pull this
    # info from the iface so we do it manually.
    _excluded_in_ivars_ = frozenset(
        getattr(InterfaceObjectIO, '_excluded_in_ivars_').union({'AssignmentId', 'Username'})
    )

    _ext_iface_upper_bound = IGrade

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        result = False
        if 'Username' in parsed and self._ext_replacement().Username is None:
            self._ext_setattr(self._ext_replacement(),
                              'Username',
                              parsed['Username'])
            result = True
        result |= super(_GradeObjectUpdater, self).updateFromExternalObject(parsed, *args, **kwargs) or False
        return result


@component.adapter(ILetterGradeScheme)
@interface.implementer(IInternalObjectUpdater)
class _LetterGradeSchemeObjectUpdater(object):

    __slots__ = ('obj',)

    def __init__(self, obj):
        self.obj = obj

    def updateFromExternalObject(self, ext, *unused_args, **unused_kwargs):
        grades = ext.get('grades', ())
        ranges = ext.get('ranges', ())
        if not ranges and not grades:  # defaults
            return False

        request = get_current_request()
        if len(grades) < 1 or len(set(grades)) != len(grades):
            raise_field_error(request,
                              "grades",
                              _(u"Must specify a valid unique list of letter grades"))

        if len(grades) != len(ranges):
            raise_field_error(request,
                              "ranges",
                              _(u"Must specify equal number of ranges to grades"))

        # If we wanted to localize these messages, we must
        # take the explicit string formatting out
        for idx, r in enumerate(ranges):
            if not r or len(r) != 2:
                raise_field_error(request,
                                  "range",
                                  u"'%r' is not a valid range" % r)
            elif r[0] >= r[1]:
                raise_field_error(request,
                                  "range",
                                  u"'%r' is not a valid range" % r)
            elif r[0] < 0 or r[1] < 0:
                raise_field_error(request,
                                  "range",
                                  u"'%r' has invalid values" % r)
            else:
                ranges[idx] = tuple(r)

        sorted_ranges = list(ranges)
        last_idx = len(sorted_ranges) - 1
        sorted_ranges.sort(key=operator.itemgetter(0), reverse=True)
        for idx in range(last_idx):
            a = sorted_ranges[idx]
            b = sorted_ranges[idx + 1]
            if a[0] <= b[0]:
                raise_field_error(request,
                                  "range",
                                  u"'%r' overlaps '%r'" % (a, b))

        self.obj.ranges = tuple(ranges)
        self.obj.grades = tuple(grades)
        return True
