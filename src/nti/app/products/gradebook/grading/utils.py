#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import namedtuple

from zope import component

from zope.container.interfaces import INameChooser

from zope.security.interfaces import IPrincipal

from nti.app.products.gradebook.assignments import create_assignment_part

from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.grading.interfaces import IGradeBookGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeScheme
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

PredictedGrade = namedtuple('PredictedGrade',
                            'Grade RawValue Correctness')


def calculate_grades(context,
                     usernames=(),
                     grade_scheme=None,
                     entry_name=None,
                     verbose=False):

    result = {}
    course = ICourseInstance(context)
    policy = find_grading_policy_for_course(course)
    if policy is None:
        raise ValueError("Course does not have grading policy")

    if entry_name:
        part = create_assignment_part(course, NO_SUBMIT_PART_NAME)
        entry = part.getEntryByAssignment(entry_name)
        if entry is None:
            order = len(part) + 1
            entry = part.entryFactory(order=order,
                                      displayName=entry_name,
                                      AssignmentId=entry_name)
            part[INameChooser(part).chooseName(entry_name, entry)] = entry
    else:
        entry = None

    for record in ICourseEnrollments(course).iter_enrollments():
        principal = IPrincipal(record.Principal, None)
        if principal is None:
            # ignore dup enrollment
            continue

        username = principal.id.lower()
        if usernames and username not in usernames:
            continue

        # grade correctness
        if IGradeBookGradingPolicy.providedBy(policy):
            value = correctness = policy.grade(principal, verbose=verbose)
        else:
            value = correctness = policy.grade(principal)

        # if there is a grade scheme convert value
        if grade_scheme is not None:
            value = grade_scheme.fromCorrectness(correctness)

        grade = PersistentGrade(value=value)
        grade.username = username
        result[username] = grade

        # if entry is available save it
        if entry is not None:
            entry[username] = grade

    return result


def get_presentation_scheme(policy):
    if IGradeBookGradingPolicy.providedBy(policy):
        return policy.PresentationGradeScheme
    return None


def calculate_predicted_grade(user, policy, scheme=u''):
    presentation = get_presentation_scheme(policy)
    if presentation is None:
        presentation = component.getUtility(IGradeScheme, name=scheme)
    correctness = policy.grade(user)
    if correctness is not None:
        grade = presentation.fromCorrectness(correctness)
        raw = correctness
        correctness = int(round(correctness * 100))
        if grade and grade == correctness:
            # Don't want to return confusing information if the
            # grade simply matches the correctness.
            grade = None
        return PredictedGrade(grade, raw, correctness)
    return None