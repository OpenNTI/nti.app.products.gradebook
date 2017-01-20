#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types
from datetime import datetime

from zope import interface

from zope.security.interfaces import IPrincipal

from nti.app.products.gradebook.grading.policies.interfaces import ISimpleTotalingGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IExcusedGrade

from nti.app.products.gradebook.utils import MetaGradeBookObject

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.interfaces import ICourseAssignmentCatalog
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.contenttypes.courses.grading.policies import DefaultCourseGradingPolicy

from nti.contenttypes.courses.grading.policies import get_assignment_policies

from nti.property.property import alias
from nti.property.property import readproperty

from nti.schema.fieldproperty import createDirectFieldProperties


@interface.implementer(ISimpleTotalingGradingPolicy)
class SimpleTotalingGradingPolicy(DefaultCourseGradingPolicy):
    __metaclass__ = MetaGradeBookObject
    createDirectFieldProperties(ISimpleTotalingGradingPolicy)

    PresentationGradeScheme = None
    presentation = alias('PresentationGradeScheme')

    def __init__(self, *args, **kwargs):
        DefaultCourseGradingPolicy.__init__(self, *args, **kwargs)

    @readproperty
    def book(self):
        return IGradeBook(self.course)

    @readproperty
    def dateContext(self):
        return IQAssignmentDateContext(self.course, None)

    def validate(self):
        if self.grader is not None:
            self.grader.validate()

    def verify(self, book=None):
        return True

    def _is_due(self, assignment, now):
        dates = self.dateContext
        if assignment is not None and dates is not None:
            _ending = dates.of(assignment).available_for_submission_ending
            return bool(_ending and now > _ending)
        return False

    def grade(self, principal, *args, **kwargs):
        now = datetime.utcnow()
        total_points_earned = 0
        total_points_available = 0

        gradebook_assignment_ids = set()
        assignment_policies = get_assignment_policies(self.course)
        username = IPrincipal(principal).id

        for grade in self.book.iter_grades(username):
            gradebook_assignment_ids.add(grade.AssignmentId)
            excused = IExcusedGrade.providedBy(grade)
            if not excused:
                ntiid = grade.AssignmentId
                total_points = self._get_total_points_for_assignment(ntiid,
                                                                     assignment_policies)
                if not total_points:
                    # If an assignment doesn't have a total_point value, we
                    # ignore it.
                    continue

                earned_points = self._get_earned_points_for_assignment(grade)
                if earned_points is None:
                    # If for some reason we couldn't convert this grade
                    # to an int, we ignore this assignment.
                    continue

                total_points_available += total_points
                total_points_earned += earned_points

        # Now fetch assignments we haven't seen that are past due.
        all_assignments = self._get_all_assignments_for_user(self.course,
                                                             principal)

        for assignment in all_assignments:
            ntiid = assignment.ntiid
            if        self._is_due(assignment, now) \
                and not ntiid in gradebook_assignment_ids:
                total_points = self._get_total_points_for_assignment(ntiid,
                                                                     assignment_policies)
                if total_points:
                    total_points_available += total_points

        if total_points_available == 0:
            # There are no assignments due with assigned point values,
            # so just return none because we can't meaningfully
            # predict any grade for this case.
            return None

        result = float(total_points_earned) / total_points_available
        result = min(max(0, result), 1) # results should be bounded to be within [0, 1]    
        return round(result, 2)

    def _get_all_assignments_for_user(self, course, user):
        catalog = ICourseAssignmentCatalog(course)
        uber_filter = get_course_assessment_predicate_for_user(user, course)
        # Must grab all assignments in our parent
        assignments = catalog.iter_assignments(course_lineage=True)
        return tuple(x for x in assignments if uber_filter(x))

    def _get_total_points_for_assignment(self, assignment_id, assignment_policies):
        result = None
        try:
            policy = assignment_policies[assignment_id]
        except KeyError:
            # If there is no entry for this assignment, we ignore it.
            pass
        else:
            autograde_policy = policy.get('auto_grade', None)
            if autograde_policy:
                # If we have an autograde entry with total_points,
                # return total_points. If it does not have total_points,
                # or if no autograde entry exists, we return 0.
                result = autograde_policy.get('total_points', None)
        if not result:
            logger.warn(
                'Assignment without total_points cannot be part of grade policy (%s) (%s)',
                assignment_id,
                result)
        return result

    def _get_earned_points_for_assignment(self, grade):
        try:
            value = grade.value
            if isinstance(value, string_types):
                value = value.strip()
                if value.endswith('-'):
                    value = value[:-1]
            return float(value)
        except (ValueError, TypeError):
            logger.warn('Gradebook entry without valid point value (%s) (%s)',
                        grade.value,
                        grade.AssignmentId)
            return None
