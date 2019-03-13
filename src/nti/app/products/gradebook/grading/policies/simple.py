#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

import six

from zope import interface

from zope.cachedescriptors.property import readproperty

from zope.security.interfaces import IPrincipal

from nti.app.products.gradebook.grading.policies.interfaces import ISimpleTotalingGradingPolicy

from nti.app.products.gradebook.gradescheme import NumericGradeScheme

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import FINAL_GRADE_NAMES
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.app.products.gradebook.grading.utils import build_predicted_grade

from nti.app.products.gradebook.utils import MetaGradeBookObject

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.interfaces import ICourseAssignmentCatalog
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.contenttypes.courses.grading.policies import DefaultCourseGradingPolicy

from nti.contenttypes.courses.grading.policies import get_assignment_policies

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@six.add_metaclass(MetaGradeBookObject)
@interface.implementer(ISimpleTotalingGradingPolicy)
class SimpleTotalingGradingPolicy(DefaultCourseGradingPolicy):
    createDirectFieldProperties(ISimpleTotalingGradingPolicy)

    PresentationGradeScheme = NumericGradeScheme()
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

    def verify(self, unused_book=None):
        return True

    def _is_due(self, assignment, now):
        dates = self.dateContext
        if assignment is not None and dates is not None:
            # pylint: disable=no-member
            _ending = dates.of(assignment).available_for_submission_ending
            return bool(_ending and now > _ending)
        return False

    # pylint: disable=arguments-differ,keyword-arg-before-vararg
    def grade(self, principal, scheme=None, *unused_args, **unused_kwargs):
        now = datetime.utcnow()
        total_points_earned = 0
        total_points_available = 0

        gradebook_assignment_ids = set()
        assignment_policies = get_assignment_policies(self.course)
        username = IPrincipal(principal).id

        # First we look through all grades for a certain username
        # in the gradebook. These are all the grades a student
        # has been assigned.
        # pylint: disable=no-member
        for grade in self.book.iter_grades(username):
            gradebook_assignment_ids.add(grade.AssignmentId)
            excused = grade.__parent__.Excused
            if not excused:
                entry = grade.__parent__
                name = getattr(entry, 'Name', None)
                part = getattr(entry, '__parent__', None)
                if      part is not None \
                    and part.__name__ == NO_SUBMIT_PART_NAME \
                    and name in FINAL_GRADE_NAMES:
                    continue

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

        # Ignore assignments that we've looked at already. Also
        # ignore no-submit assignments that haven't been graded yet,
        # and assignments that aren't due yet.
        for assignment in all_assignments:
            ntiid = assignment.ntiid
            if      self._is_due(assignment, now) \
                and not ntiid in gradebook_assignment_ids \
                and not assignment.no_submit \
                and self._has_questions(assignment):
                total_points = self._get_total_points_for_assignment(ntiid,
                                                                     assignment_policies)
                if total_points:
                    total_points_available += total_points

        if total_points_available == 0:
            # There are no assignments due with assigned point values,
            # so just return none because we can't meaningfully
            # predict any grade for this case.
            return None

        return build_predicted_grade(self,
                                     points_earned=total_points_earned,
                                     points_available=total_points_available,
                                     scheme=scheme)

    def _has_questions(self, assignment):
        assignment_parts = assignment.parts or ()
        for part in assignment_parts:
            question_set = part.question_set
            if len(question_set.questions or ()) > 0:
                return True
        return False

    def _get_all_assignments_for_user(self, course, user):
        catalog = ICourseAssignmentCatalog(course)
        uber_filter = get_course_assessment_predicate_for_user(user, course)
        # Must grab all assignments in our parent
        # pylint: disable=too-many-function-args
        assignments = catalog.iter_assignments(True)
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
            logger.warning(
                'Assignment without total_points cannot be part of grade policy (%s) (%s)',
                assignment_id,
                result)
        return result

    def _get_earned_points_for_assignment(self, grade):
        try:
            value = grade.value
            if isinstance(value, six.string_types):
                value = value.strip()
                if value.endswith('-'):
                    value = value[:-1]
            return float(value)
        except (ValueError, TypeError):
            logger.warning('Gradebook entry without valid point value (%s) (%s)',
                           grade.value,
                           grade.AssignmentId)
            return None
