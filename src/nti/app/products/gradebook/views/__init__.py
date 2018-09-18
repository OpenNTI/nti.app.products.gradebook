#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from six import string_types

from zope import component
from zope import interface

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.contenttypes.courses.interfaces import ICourseInstance

logger = __import__('logging').getLogger(__name__)


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
