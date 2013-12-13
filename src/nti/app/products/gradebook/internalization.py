#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook internalization

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import operator

from zope import interface
from zope import component

from pyramid.threadlocal import get_current_request

from nti.externalization import internalization
from nti.externalization import interfaces as ext_interfaces

from . import utils
from . import interfaces as grade_interfaces

@interface.implementer(ext_interfaces.IInternalObjectUpdater)
@component.adapter(grade_interfaces.IGrade)
class _GradeObjectUpdater(object):

    __slots__ = ('obj',)

    def __init__(self, obj):
        self.obj = obj

    def updateFromExternalObject(self, externalObject, *args, **kwargs ):
        modified = False
        for name in ('NTIID', 'username'):
            value = externalObject.get(name, None)
            if getattr(self, name, None) is None and value is not None:
                setattr(self.obj, name, value)
                modified = True

        # get external grade
        grade = externalObject.get('grade', None)

        # adapt external grade value to a grade scheme
        entry = grade_interfaces.IGradeBookEntry(self.obj, None)
        if entry is not None and grade is not None:
            if isinstance(grade, six.string_types):
                grade = entry.GradeScheme.fromUnicode(grade)
            else:
                entry.GradeScheme.validate(grade)

        if self.obj.grade != grade:
            self.obj.grade = grade
            modified = True
        return modified

@interface.implementer(ext_interfaces.IInternalObjectUpdater)
@component.adapter(grade_interfaces.IGrades)
class _GradesObjectUpdater(object):

    __slots__ = ('obj',)

    def __init__(self, obj):
        self.obj = obj

    def updateFromExternalObject(self, ext, *args, **kwargs):
        modified = False
        items = ext.get('Items', {})
        for username, grades in items.items():
            for grade_ext in grades:
                modified = True
                grade = internalization.find_factory_for(grade_ext)()
                internalization.update_from_external_object(grade, grade_ext)
                self.obj.add_grade(grade, username)
        return modified


@interface.implementer(ext_interfaces.IInternalObjectUpdater)
@component.adapter(grade_interfaces.ILetterGradeScheme)
class _LetterGradeSchemeObjectUpdater(object):

    __slots__ = ('obj',)

    def __init__(self, obj):
        self.obj = obj

    def updateFromExternalObject(self, ext, *args, **kwargs):
        grades = ext.get('grades', ())
        ranges = ext.get('ranges', ())
        if not ranges and not grades:
            return False

        request = get_current_request()
        if len(grades) < 1 or len(set(grades)) != len(grades):
            utils.raise_field_error(request, "grades",
                                    "must specify a valid unique list of letter grades")

        if len(grades) != len(ranges):
            utils.raise_field_error(request, "ranges",
                                    "must specify equal number of ranges to grades")
        
        for r in ranges:
            if not r or len(r) != 2:
                utils.raise_field_error(request, "range",
                                        "'%r' is not a valid range" % r)

        sorted_ranges = list(ranges)
        sorted_ranges.sort(key=operator.itemgetter(0))

        self.ranges = ranges
        self.grades = grades
        return True
