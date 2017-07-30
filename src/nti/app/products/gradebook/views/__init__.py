#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types

from zope import component
from zope import interface

from zope.traversing.interfaces import IPathAdapter

from pyramid.interfaces import IRequest

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.contenttypes.courses.interfaces import ICourseInstance


def _get_grade_parts(grade_value):
    """
    Convert the webapp's "number - letter" scheme to a tuple.
    """
    result = (grade_value,)
    if grade_value and isinstance(grade_value, string_types):
        try:
            values = grade_value.split()
            values[0] = float(values[0])
            result = tuple(values)
        except ValueError:
            pass
    return result


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def GradeBookPathAdapter(context, unused_request):
    result = IGradeBook(context)
    return result
