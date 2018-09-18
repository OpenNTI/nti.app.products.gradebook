#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Basic auto-grade policies.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import copy

from zope import component
from zope import interface

from nti.app.products.gradebook.interfaces import IPendingAssessmentAutoGradePolicy

from nti.assessment.interfaces import IQAssignmentPolicies

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPendingAssessmentAutoGradePolicy)
class TrivialFixedScaleAutoGradePolicy(object):
    """
    Scales each question equally, normalized to a particular value.
    If any part of a question is auto-assessed as incorrect, the entire
    question is graded as incorrect.

    We ignore the weight of parts.
    """

    normalize_to = 20.0  # Magic value for the one class currently using this

    def autograde(self, item):
        # The UIs and/or some higher level ensure that we can never
        # submit an assignment that is missing any question sets,
        # or individual question parts. Therefore we can
        # assume we have the complete representation for scaling purposes.
        assessed_sum = 0.0
        theoretical_best = 0.0
        for assessed_set in item.parts:
            for assessed_question in assessed_set.questions:
                part_sum = 0.0
                theoretical_best += 1.0  # scale to the number of questions
                for assessed_part in assessed_question.parts:
                    if not hasattr(assessed_part, 'assessedValue'):
                        # Almost certainly trying to autograde something
                        # that cannot be autograded, like a modeled content or
                        # file response.
                        # We can now be lenient with this case; so allow the
                        # submission and this can be re-graded as necessary.
                        logger.warning(
                            'Non-autogradable type submitted to auto-gradable assignment'
                        )
                        return None

                    if not assessed_part.assessedValue:
                        # WRONG part, whole question is toast
                        part_sum = 0.0
                        break
                    part_sum += assessed_part.assessedValue
                # scale the parts to the whole question
                part_sum = part_sum / float(len(assessed_question.parts))
                # and finally count it for the question
                assessed_sum += part_sum

        # No submit part
        if not theoretical_best:
            return None

        # Each part was between 0 and 1. Now normalize
        as_percent = assessed_sum / theoretical_best
        return as_percent * self.normalize_to, self.normalize_to


@interface.implementer(IPendingAssessmentAutoGradePolicy)
class PointBasedAutoGradePolicy(object):

    def __init__(self, auto_grade, assignmentId):
        self.assignmentId = assignmentId
        self.auto_grade = copy.copy(auto_grade)

    def question_points(self, ntiid):
        question_map = self.auto_grade.get('questions') or self.auto_grade
        points = question_map.get(ntiid) or question_map.get('default')
        return points

    def assignment_points(self, item):
        result = 0
        for assessed_set in item.parts:
            for assessed_question in assessed_set.questions:
                questionId = assessed_question.questionId
                question_points = self.question_points(questionId)
                result += question_points
        return result

    def autograde(self, item):
        assessed_sum = 0.0
        practical_best = self.assignment_points(item)
        theoretical_best = self.auto_grade.get('total_points')
        if practical_best != theoretical_best:
            logger.warning(
                "Policy total points %s is different from sum of questions points %s",
                theoretical_best, practical_best
            )
        for assessed_set in item.parts:
            for assessed_question in assessed_set.questions:
                part_sum = 0.0

                for assessed_part in assessed_question.parts:
                    if not hasattr(assessed_part, 'assessedValue'):
                        # See note in fixed policy.
                        logger.warning(
                            'Non-autogradable type submitted to auto-gradable assignment'
                        )
                        return None
                    if not assessed_part.assessedValue:
                        # WRONG part, whole question is toast
                        part_sum = 0.0
                        break
                    part_sum += assessed_part.assessedValue

                # scale the parts to the whole question. most of the times
                # questions have one part.
                part_sum = part_sum / float(len(assessed_question.parts))

                questionId = assessed_question.questionId
                question_points = self.question_points(questionId)
                scaled_points = question_points * part_sum

                # and finally count it for the question
                assessed_sum += scaled_points

        return assessed_sum, theoretical_best


def _policy_based_autograde_policy(course, assignmentId):
    policies = IQAssignmentPolicies(course, None)
    if policies is not None:
        # pylint: disable=too-many-function-args
        policy = policies.getPolicyForAssignment(assignmentId)
    else:
        policy = None

    if policy is not None:
        auto_grade = policy.get('auto_grade') or {}
        disable = auto_grade.get('disable') or False
        if disable:  # if disable don't auto-grade
            return None
        name = auto_grade.get('name')
        if not name:
            total_points = auto_grade.get('total_points')
            if total_points is not None:
                total_points = float(total_points)
                policy = TrivialFixedScaleAutoGradePolicy()
                policy.normalize_to = total_points
                return policy
        elif name.lower() in ('pointbased'):
            policy = PointBasedAutoGradePolicy(auto_grade, assignmentId)
            return policy
        else:
            policy = component.queryUtility(IPendingAssessmentAutoGradePolicy,
                                            name=name)
            return policy


def find_autograde_policy(course, assignmentId):
    # We don't *really* need to be taking the assignmentId, it's
    # part of the item submitted for autograding. We could wrap the logic
    # all up in the policy itself. But this makes the API intent fairly
    # clear...

    if course is None or not assignmentId:
        return None

    # Is there a nice new one?
    policy = _policy_based_autograde_policy(course, assignmentId)
    if policy is not None:
        return policy

    # We need to actually be registering these as annotations
    # or some such...
    policy = IPendingAssessmentAutoGradePolicy(course, None)
    if policy is not None:
        return policy

    registry = component
    # Courses may be ISites (couldn't we do this with
    # the context argument?)
    try:
        registry = course.getSiteManager()
        names = ('',)
        # If it is, we want the default utility in this course
    except LookupError:
        # If it isn't we need a named utility
        # We look for a bunch of different names, depending on the
        # kind of course.
        # We probably want to replace this with an adapter
        # that we can setup at course sync time as an annotation?
        names = list()
        try:
            # Legacy single-package courses
            names.append(course.ContentPackageNTIID)
        except AttributeError:
            # new-style
            names.extend((x.ntiid for x in get_course_packages(course)))

        cat_entry = ICourseCatalogEntry(course, None)
        if cat_entry:
            names.append(cat_entry.ntiid)

    for name in names:
        try:
            return registry.getUtility(IPendingAssessmentAutoGradePolicy, name=name)
        except LookupError:
            pass
    return None
find_autograde_policy_for_assignment_in_course = find_autograde_policy # BWC
