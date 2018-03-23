#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adapters for application-level events.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from six import string_types
from six import integer_types

from zope import component
from zope import interface

from nti.app.assessment.common.policy import get_auto_grade_policy

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from nti.app.products.gradebook.interfaces import IGrade

from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.completion.progress import Progress

from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

logger = __import__('logging').getLogger(__name__)


def _numeric_grade_val(grade_val):
    """
    Convert the grade's possible char "number - letter" scheme to a number,
    or None.
    """
    result = None
    if isinstance(grade_val, string_types):
        try:
            if grade_val.endswith(' -'):
                result = float(grade_val.split()[0])
            else:
                result = float(grade_val)
        except ValueError:
            pass
    elif isinstance(grade_val, (integer_types, float)):
        result = grade_val
    return result


@component.adapter(IUser, IQAssignment, ICourseInstance)
@interface.implementer(IProgress)
def _assignment_progress(user, assignment, course):
    """
    Calculate the :class:`IProgress` for this user, assignment, course.
    """
    histories = component.queryMultiAdapter((course, user),
                                            IUsersCourseAssignmentHistory)
    item = submitted_date = None
    try:
        item = histories[assignment.ntiid]
        submitted_date = item.created
    except KeyError:
        pass

    if item is None:
        return

    grade = IGrade(item, None)
    grade_val = getattr(grade, 'value', None)
    grade_val = _numeric_grade_val(grade_val)

    total_points = None
    policy = get_auto_grade_policy(assignment, course)
    if policy:
        try:
            total_points = policy.get('total_points') or None
        except AttributeError:
            pass
    progress = Progress(NTIID=assignment.ntiid,
                        AbsoluteProgress=grade_val,
                        MaxPossibleProgress=total_points,
                        LastModified=submitted_date,
                        User=user,
                        Item=assignment,
                        CompletionContext=course,
                        HasProgress=True)
    return progress

