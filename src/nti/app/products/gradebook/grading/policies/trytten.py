#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import logging

from datetime import datetime
from collections import defaultdict

import six

from ZODB import loglevels

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import readproperty

from zope.security.interfaces import IPrincipal

from nti.app.products.gradebook.gradescheme import NumericGradeScheme
from nti.app.products.gradebook.gradescheme import LetterNumericGradeScheme

from nti.app.products.gradebook.grading.policies.interfaces import ICategoryGradeScheme
from nti.app.products.gradebook.grading.policies.interfaces import ICS1323EqualGroupGrader
from nti.app.products.gradebook.grading.policies.interfaces import ICS1323CourseGradingPolicy

from nti.app.products.gradebook.grading.utils import build_predicted_grade

from nti.app.products.gradebook.interfaces import FINAL_GRADE_NAMES
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.utils import MetaGradeBookObject

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.grading.policies import EqualGroupGrader
from nti.contenttypes.courses.grading.policies import DefaultCourseGradingPolicy
from nti.contenttypes.courses.grading.policies import CategoryGradeScheme as BaseCategoryGradeScheme

from nti.externalization.representation import WithRepr

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


def to_correctness(value, scheme):
    value = scheme.fromUnicode(value) if isinstance(value, six.string_types) else value
    scheme.validate(value)
    result = scheme.toCorrectness(value)
    return result


@WithRepr
@EqHash('assignmentId')
class GradeProxy(object):

    invalid_grade = False

    def __init__(self, assignmentId, value, weight, scheme,
                 excused=False, penalty=0.0):
        self.value = value
        self.weight = weight
        self.scheme = scheme
        self.excused = excused
        self.penalty = penalty
        self.assignmentId = assignmentId

    @readproperty
    def correctness(self):
        try:
            result = to_correctness(self.value, self.scheme)
            result = result * (1 - self.penalty)
        except (ValueError, TypeError):
            logger.error("Invalid value %s for grade scheme %s in assignment %s",
                         self.value, self.scheme, self.assignmentId)
            result = 0
            self.invalid_grade = True
        return result


@WithRepr
@six.add_metaclass(MetaGradeBookObject)
@interface.implementer(ICategoryGradeScheme)
@EqHash('Weight', 'DropLowest', 'LatePenalty')
class CategoryGradeScheme(BaseCategoryGradeScheme):
    createDirectFieldProperties(ICategoryGradeScheme)

    LatePenalty = 1

    dropLowest = alias('DropLowest')


@six.add_metaclass(MetaGradeBookObject)
@interface.implementer(ICS1323EqualGroupGrader)
class CS1323EqualGroupGrader(EqualGroupGrader):
    createDirectFieldProperties(ICS1323EqualGroupGrader)


@six.add_metaclass(MetaGradeBookObject)
@interface.implementer(ICS1323CourseGradingPolicy)
class CS1323CourseGradingPolicy(DefaultCourseGradingPolicy):
    createDirectFieldProperties(ICS1323CourseGradingPolicy)

    PresentationGradeScheme = LetterNumericGradeScheme()

    presentation = alias('PresentationGradeScheme')

    @Lazy
    def book(self):
        book = IGradeBook(self.course)
        return book

    @Lazy
    def dateContext(self):
        result = IQAssignmentDateContext(self.course, None)
        return result

    def to_correctness(self, value, scheme):
        result = to_correctness(value, scheme)
        return result

    def validate(self):
        super(CS1323CourseGradingPolicy, self).validate()
        # pylint: disable=protected-access,no-member
        for assignment in self.grader._raw_assignments():
            points = self._points.get(assignment)
            assert points, "Could not find points for %s" % assignment

    def verify(self, book=None):
        result = True
        book = self.book if book is None else book
        # pylint: disable=protected-access
        for name in self.grader._raw_assignments():
            if is_valid_ntiid_string(name):
                entry = book.getEntryByAssignment(name)
                if entry is None:
                    result = False
                    logger.error("Could not find GradeBook Entry for %s", name)
        return result

    @property
    def groups(self):
        return self.grader.groups

    @Lazy
    def _assignments(self):
        result = defaultdict(set)
        # pylint: disable=protected-access
        for name, items in self.grader._categories.items():
            for data in items:
                assignment = data['assignment']
                result[name].add(assignment)
        return result

    @Lazy
    def _points(self):
        result = {}
        # pylint: disable=protected-access
        for items in self.grader._categories.values():
            for data in items:
                assignment = data['assignment']
                points = data.get('points') or data.get('total_points')
                if points:
                    result[assignment] = points
        return result

    @Lazy
    def _total_weight(self):
        result = 0
        for category in self.groups.values():
            result += category.Weight
        return result

    @Lazy
    def _rev_categories(self):
        # pylint: disable=protected-access
        return self.grader._rev_categories

    @Lazy
    def _weights(self):
        result = {}
        # pylint: disable=no-member
        for name, data in self._assignments.items():
            category = self.groups[name]
            item_weight = round(1 / float(len(data)), 3)
            for item in data:
                result[item] = item_weight * category.Weight
        return result

    @Lazy
    def _schemes(self):
        result = {}
        # pylint: disable=no-member
        for name, points in self._points.items():
            scheme = NumericGradeScheme(min=0, max=points)
            result[name] = scheme
        return result

    def _is_late(self, assignmentId, now=None):
        dates = self.dateContext
        now = now or datetime.utcnow()
        # pylint: disable=no-member
        assignment = component.queryUtility(IQAssignment, name=assignmentId)
        if assignment is not None and dates is not None:
            _ending = dates.of(assignment).available_for_submission_ending
            return bool(_ending and now > _ending)
        return False

    def _is_no_submit(self, assignmentId):
        assignment = component.queryUtility(IQAssignment, name=assignmentId)
        return bool(assignment is not None and assignment.no_submit)

    def _grade_map(self, username):
        now = datetime.utcnow()
        result = defaultdict(list)
        entered = defaultdict(set)
        # pylint: disable=no-member
        # parse all grades and bucket them by category
        for grade in self.book.iter_grades(username):
            assignmentId = grade.AssignmentId

            entry = grade.__parent__
            name = getattr(entry, 'Name', None)
            part = getattr(entry, '__parent__', None)
            if      part is not None \
                and part.__name__ == NO_SUBMIT_PART_NAME \
                and name in FINAL_GRADE_NAMES:
                continue

            weight = self._weights.get(assignmentId)
            if not weight:
                logger.error("Incomplete policy, no weight found for %s",
                              assignmentId)
                continue

            scheme = self._schemes.get(assignmentId)
            if not scheme:
                logger.error("Incomplete policy, no total points were found for %s",
                             assignmentId)
                continue

            correctness = None
            excused = grade.__parent__.Excused
            is_late = self._is_late(assignmentId, now)

            value = grade.value
            if value is None:  # not graded assume correct
                value = 0
                correctness = 1

            # record grade
            proxy = GradeProxy(assignmentId, value, weight, scheme, excused)
            if correctness is not None:
                proxy.correctness = correctness
            # pylint: disable=unsubscriptable-object
            cat_name = self._rev_categories[assignmentId]
            result[cat_name].append(proxy)
            entered[cat_name].add(assignmentId)

        # now create proxy grades with 0 correctes for missing ones
        # that we know about in the policy
        for cat_name, assignments in self._assignments.items():
            inputed = entered[cat_name]
            for assignmentId in assignments.difference(inputed):

                is_late = self._is_late(assignmentId, now)
                is_no_submit = self._is_no_submit(assignmentId)

                # we assume the assigment is correct
                correctness = 1
                weight = self._weights.get(assignmentId)
                scheme = self._schemes.get(assignmentId)

                # check if the assigment is late
                if is_late:
                    if not is_no_submit:  # no no_submit
                        correctness = 0
                    else:
                        penalty = 1
                        correctness = 1 - penalty

                # create proxy grade
                proxy = GradeProxy(assignmentId, 0, weight, scheme)
                proxy.correctness = correctness
                result[cat_name].append(proxy)

        # sort by correctness
        for name in result.keys():
            result[name].sort(key=lambda g: g.correctness)

        # return
        return result

    def grade(self, principal, verbose=False, scheme=None):  # pylint: disable=arguments-differ
        """
        if an assignment is overdue and there is no submission, the assignment grade is 0
        if an assignment is submitted and no grades were assigned, the assignment grade
        is max grade.
        For each category of assignments:
                1. ignore/drop the assignments that were marked as excused

                2. ignore/drop the assignments that are invalid
                   (i.e. entered grade is greater than specified max grade)

                3. calculate grade percentage: actual grade/max grade

                4. ignore/drop the specified N lowest grade assignments

                5. calculate average out of remaining assignments and multiply by category weights.

        Sum up the result derived from each category and arrive at predictor grade
        """

        LOGLEVEL = logging.INFO if verbose else loglevels.TRACE

        logger.log(LOGLEVEL, "Grading %s", principal)

        result = 0
        username = IPrincipal(principal).id
        grade_map = self._grade_map(username)
        for name, grades in grade_map.items():
            logger.log(LOGLEVEL,
                       "Grading category %s", name)

            drop_count = 0
            grade_count = len(grades)
            category = self.groups[name]

            # drop excused grades and invalid grades
            logger.log(LOGLEVEL,
                       "%s have been skipped",
                       [x for x in grades if x.excused or x.invalid_grade])

            grades = [
                x for x in grades if not x.excused and not x.invalid_grade
            ]
            drop_count += (grade_count - len(grades))
            grade_count = len(grades)

            # drop lowest grades in the category
            # make sure we don't drop excused grades
            if category.DropLowest and category.DropLowest < grade_count:
                logger.log(LOGLEVEL,
                           "%s have been dropped",
                           grades[0:category.DropLowest])
                grades = grades[category.DropLowest:]
                drop_count += (grade_count - len(grades))

            # if we drop any rebalance weights equally
            if drop_count and grades:
                # pylint: disable=no-member
                assignments = len(self._assignments.get(name) or ())
                denominator = assignments - drop_count
                if denominator:
                    item_weight = round(1 / float(denominator), 3)
                else:
                    logger.error("Internal policy error. %s, %s",
                                  assignments,
                                  drop_count)
                    item_weight = 0

                for grade in grades:
                    grade.weight = item_weight * category.weight

            # go through remaining grades
            for grade in grades:
                weight = grade.weight
                if grade.excused:
                    result += weight
                    logger.log(LOGLEVEL, "%s is excused. Skipped", grade)
                    continue
                correctness = grade.correctness
                weighted_correctness = correctness * weight
                result += weighted_correctness
                logger.log(LOGLEVEL,
                           "%s correctness and weighted correctness are %s, %s",
                           grade, correctness, weighted_correctness)

        logger.log(LOGLEVEL,
                   "Unjusted total grade percentage is %s. Adjust weight is %s",
                   result, self._total_weight)

        # divide over the total weight in case the policy
        # is not complete
        result = result / self._total_weight
        result = round(result, 2)

        return build_predicted_grade(self, raw_value=result, scheme=scheme)
