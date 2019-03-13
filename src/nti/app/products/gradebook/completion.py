#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adapters for application-level events.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.assessment.common.history import get_most_recent_history_item

from nti.app.assessment.common.policy import get_auto_grade_policy
from nti.app.assessment.common.policy import get_policy_completion_passing_percent

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.utils.gradebook import numeric_grade_val,\
    get_applicable_user_grade

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IPlaceholderAssignmentSubmission

from nti.contenttypes.completion.progress import Progress

from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

logger = __import__('logging').getLogger(__name__)


def _is_assignment_no_submit(assignment):
    result = assignment.no_submit
    if not result:
        # We are not a no_submit, do we have questions? These are probably
        # api created assignments that we cannot trust the category_name.
        result = True
        for part in assignment.parts or ():
            result = not bool(part.question_set.question_count)
    return result


@component.adapter(IUser, IQAssignment, ICourseInstance)
@interface.implementer(IProgress)
def _assignment_progress(user, assignment, course):
    """
    Calculate the :class:`IProgress` for this user, assignment, course.
    """
    progress_date = None
    is_synth = False
    try:
        item = get_most_recent_history_item(user, course, assignment.ntiid)
        if item is not None:
            is_synth = IPlaceholderAssignmentSubmission.providedBy(item.Submission)
            progress_date = item.created
    except KeyError:
        pass

    gradebook = IGradeBook(course)
    # pylint: disable=too-many-function-args
    entry = gradebook.getColumnForAssignmentId(assignment.ntiid)
    grade_container = entry.get(user.username) if entry is not None else None
    excused_grade = grade_container.excused
    grade = get_applicable_user_grade(entry, user)

    # We cannot calculate progress if:
    # * passing percent required and no grade (synth or not)
    # * no passing percent and submittable, but not non-synth submission
    # * no grade on a no_submit
    is_no_submit = _is_assignment_no_submit(assignment)
    passing_percent = get_policy_completion_passing_percent(assignment, course)
    if     (   (grade is None and passing_percent is not None) \
            or (    (progress_date is None or is_synth) \
                and not is_no_submit and passing_percent is None) \
            or (grade is None and is_no_submit)) \
        and not excused_grade:
        return

    if progress_date is None:
        # We're here because of grade value or excused grade.
        progress_date = grade.lastModified

    grade_val = getattr(grade, 'value', None)
    grade_val = numeric_grade_val(grade_val)

    total_points = None
    policy = get_auto_grade_policy(assignment, course)
    if policy:
        try:
            total_points = policy.get('total_points') or None
        except AttributeError:
            pass

    if passing_percent is not None and excused_grade:
        # For excused grade, we make points equal total_points required
        # XXX: This is a yuk approach. Maybe we have a field for
        # forced completion.
        grade_val = total_points

    progress = Progress(NTIID=assignment.ntiid,
                        AbsoluteProgress=grade_val,
                        MaxPossibleProgress=total_points,
                        LastModified=progress_date,
                        User=user,
                        Item=assignment,
                        CompletionContext=course,
                        HasProgress=True)
    return progress
