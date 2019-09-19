#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.container.interfaces import INameChooser

from zope.security.interfaces import IPrincipal

from nti.app.products.gradebook.assignments import create_assignment_part

from nti.app.products.gradebook.grades import PredictedGrade
from nti.app.products.gradebook.grades import GradeContainer
from nti.app.products.gradebook.grades import PersistentMetaGrade

from nti.app.products.gradebook.grading.interfaces import IGradeBookGradingPolicy

from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.app.products.gradebook.interfaces import IGradeScheme

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

logger = __import__('logging').getLogger(__name__)


def calculate_grades(context,
                     usernames=(),
                     grade_scheme=None,
                     entry_name=None,
                     verbose=False):
    # XXX: This is only called from a script. Is it used anymore?
    # We're also setting a grade below
    result = {}
    course = ICourseInstance(context)
    policy = find_grading_policy_for_course(course)
    if policy is None:
        raise ValueError("Course does not have grading policy")
    # pylint: disable=too-many-function-args
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
        # pylint: disable=no-member
        username = principal.id.lower()
        if usernames and username not in usernames:
            continue
        # grade correctness
        if IGradeBookGradingPolicy.providedBy(policy):
            # pylint: disable=unexpected-keyword-arg
            value = correctness = policy.grade(principal, verbose=verbose)
        else:
            value = correctness = policy.grade(principal)
        # if there is a grade scheme convert value
        if grade_scheme is not None:
            value = grade_scheme.fromCorrectness(correctness)
        grade = PersistentMetaGrade(value=value)
        result[username] = grade
        # if entry is available save it
        if entry is not None:
            try:
                grade_container = entry[username]
            except KeyError:
                grade_container = GradeContainer()
                entry[username] = grade_container
            grade.__parent__ = grade_container
            grade.__name__ = u'MetaGrade'
            grade_container.MetaGrade = grade
    return result


def get_presentation_scheme(policy):
    if IGradeBookGradingPolicy.providedBy(policy):
        return policy.PresentationGradeScheme
    return None


def calculate_predicted_grade(user, policy, scheme=''):
    if not scheme:
        scheme = get_presentation_scheme(policy)
    predicted_grade = policy.grade(user, scheme=scheme)
    return predicted_grade


def build_predicted_grade(policy, points_earned=None, points_available=None,
                          raw_value=None, scheme=None):

    presentation_scheme = get_presentation_scheme(policy)
    if presentation_scheme is None:
        presentation_scheme = component.getUtility(IGradeScheme, name=scheme)
    if points_available == 0:
        return None
    return PredictedGrade(points_earned=points_earned,
                          points_available=points_available,
                          raw_value=raw_value,
                          presentation_scheme=presentation_scheme)
