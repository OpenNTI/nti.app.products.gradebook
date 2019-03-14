#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import unittest

import fudge

from nti.app.products.gradebook.gradescheme import NumericGradeScheme

from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.grades import GradeContainer
from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.grading.policies.interfaces import ISimpleTotalingGradingPolicy

from nti.app.products.gradebook.grading.policies.simple import SimpleTotalingGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.assessment.assignment import QAssignment
from nti.assessment.assignment import QAssignmentPart

from nti.assessment.parts import QMathPart

from nti.assessment.question import QQuestion
from nti.assessment.question import QQuestionSet

from nti.contenttypes.courses.assignment import MappingAssignmentPolicies

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.grading import set_grading_policy_for_course

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.externalization.externalization import to_external_object

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object


class TestSimpleGradingPolicy(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_verifiably_provides(self):
        policy = SimpleTotalingGradingPolicy()
        assert_that(policy, validly_provides(ISimpleTotalingGradingPolicy))
        assert_that(policy, verifiably_provides(ISimpleTotalingGradingPolicy))

    def test_externalization(self):
        policy = SimpleTotalingGradingPolicy()

        ext = to_external_object(policy)
        assert_that(ext,
                    has_entry('MimeType',
                              'application/vnd.nextthought.gradebook.simpletotalinggradingpolicy'))

        factory = find_factory_for(ext)
        obj = factory()
        update_from_external_object(obj, ext)

    @WithMockDSTrans
    @fudge.patch('nti.contenttypes.courses.grading.policies.get_assignment',
                 'nti.app.products.gradebook.grading.policies.simple.get_assignment_policies',
                 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._get_all_assignments_for_user',
                 'nti.app.products.gradebook.grading.utils.get_presentation_scheme')
    def test_simple_grade_predictor_policy(self,
                                           mock_ga,
                                           mock_gap,
                                           mock_get_assignments,
                                           mock_presentation):

        connection = mock_dataserver.current_transaction
        course = CourseInstance()
        connection.add(course)

        policy = SimpleTotalingGradingPolicy()
        policy.__parent__ = course

        # assignment policies
        mock_ga.is_callable().with_args().returns(fudge.Fake())
        cap = MappingAssignmentPolicies()
        assignments = []
        # We don't really need to test assignments here
        # because we do in the test for due assignments,
        # and that case really doesn't come up for
        # assignments before they're due.

        set_grading_policy_for_course(course, policy)
        mock_gap.is_callable().with_args().returns(cap)
        mock_get_assignments.is_callable().with_args().returns(assignments)

        # Use the numeric grade scheme to check grades
        presentation_scheme = NumericGradeScheme()
        mock_presentation.is_callable().with_args().returns(presentation_scheme)

        book = IGradeBook(course)

        # If there are no points available, we return None.
        grade = policy.grade('cald3307')
        assert_that(grade, is_(None))

        for name, cat in ((u'a1', 'iclicker'), (u'a2', 'turingscraft')):
            part = GradeBookPart()
            book[cat] = part

            entry = GradeBookEntry()
            entry.assignmentId = name
            part[cat] = entry

            grade = PersistentGrade()
            grade.value = 5.5
            grade.username = u'cald3307'
            grade.__parent__ = container = GradeContainer()
            entry[u'cald3307'] = container

        # If no points available, we return None even
        # if there happen to be grades in the gradebook.
        grade = policy.grade('cald3307')
        assert_that(grade, is_(None))

        # Now if we provide total points in our policy,
        # we should get meaningful results.
        cap['a1'] = {'auto_grade': {'total_points': 10}}
        cap['a2'] = {'auto_grade': {'total_points': 5}}
        cap['a3'] = {'auto_grade': {'total_points': 5}}
        cap['a4'] = {'auto_grade': {'total_points': 5}}

        # We should have earned 11 points out of a possible 15.
        grade = policy.grade('cald3307')

        assert_that(grade.correctness, is_(73))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(11))

        # Check that an assignment not due and not graded
        # does not affect the total
        part = GradeBookPart()
        book[u'early_and_ungraded'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'a3'
        part[u'early_and_ungraded'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(73))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(11))

        # Check that a non-numeric grade gets ignored.
        part = GradeBookPart()
        book[u'non_numeric_grade'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'a4'
        part[u'non_numeric_grade'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = u'non-numeric grade, but has 1 number in it'
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade(u'cald3307')
        assert_that(grade.correctness, is_(73))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(11))

        # Check that an excused grade does not affect the total
        cap['excused'] = {'auto_grade': {'total_points': 5}}

        part = GradeBookPart()
        book[u'excused'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'excused'
        part[u'excused'] = entry
        grade = PersistentGrade()
        grade.value = 100
        grade.__parent__ = container = GradeContainer()
        grade.__parent__.Excused = True
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(73))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(11))

        # A grade without an entry in the course policy
        # should be ignored.
        part = GradeBookPart()
        book[u'no_policy'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'id_to_missing_assignment'
        part[u'excused'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = 100
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(73))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(11))

        # Negative grades are possible, but cannot
        # make the course grade less than 0.
        cap['negative_grade'] = {'auto_grade': {'total_points': 5}}

        part = GradeBookPart()
        book[u'negative_grade'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'negative_grade'
        part[u'negative_grade'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = -12  # We now have -1 points for the course
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(0))
        assert_that(grade.points_available, is_(20))
        assert_that(grade.points_earned, is_(-1))

        # Extra credit cannot cause a grade to be
        # more than 1 (a perfect score)
        cap['extra_credit_grade'] = {'auto_grade': {'total_points': 5}}

        part = GradeBookPart()
        book[u'extra_credit'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'extra_credit_grade'
        part[u'extra_credit'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = 100
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(100))
        assert_that(grade.points_available, is_(25))
        assert_that(grade.points_earned, is_(99))


    @WithMockDSTrans
    @fudge.patch('nti.contenttypes.courses.grading.policies.get_assignment',
                 'nti.app.products.gradebook.grading.policies.simple.get_assignment_policies',
                 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._get_all_assignments_for_user',
                 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._is_due',
                 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._has_questions',
                 'nti.app.products.gradebook.grading.utils.get_presentation_scheme')
    def test_simple_grade_predictor_for_late_assignments(self,
                                                         mock_ga,
                                                         mock_gap,
                                                         mock_get_assignments,
                                                         mock_is_due,
                                                         mock_has_questions,
                                                         mock_presentation):

        connection = mock_dataserver.current_transaction
        course = CourseInstance()
        connection.add(course)

        policy = SimpleTotalingGradingPolicy()
        policy.__parent__ = course

        # assignment policies
        mock_ga.is_callable().with_args().returns(fudge.Fake())
        mock_is_due.is_callable().with_args().returns(True)
        mock_has_questions.is_callable().with_args().returns(True)
        presentation_scheme = NumericGradeScheme()
        mock_presentation.is_callable().with_args().returns(presentation_scheme)
        cap = MappingAssignmentPolicies()

        cap['tag:nextthought.com,2011-10:due_and_passed'] = {
            'auto_grade': {'total_points': 5}
        }
        cap['tag:nextthought.com,2011-10:due_and_failed'] = {
            'auto_grade': {'total_points': 5}
        }

        set_grading_policy_for_course(course, policy)
        mock_gap.is_callable().with_args().returns(cap)
        assignments = []
        a2 = QAssignment()
        a2.ntiid = u'tag:nextthought.com,2011-10:due_and_failed'
        assignments.append(a2)
        a3 = QAssignment()
        a3.ntiid = u'tag:nextthought.com,2011-10:due_and_passed'
        assignments.append(a3)
        a4 = QAssignment()
        a4.ntiid = u'tag:nextthought.com,2011-10:excused'
        assignments.append(a4)
        a5 = QAssignment()
        a5.ntiid = u'tag:nextthought.com,2011-10:unsubmitted'
        assignments.append(a5)
        a6 = QAssignment()
        a6.ntiid = u'tag:nextthought.com,2011-10:ungraded'
        assignments.append(a6)
        mock_get_assignments.is_callable().with_args().returns(assignments)

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(0))
        assert_that(grade.points_available, is_(10))
        assert_that(grade.points_earned, is_(0))

        book = IGradeBook(course)
        # This should be counted because it's due and not excused,
        # even though the student earned 0 points on this assignment.
        part = GradeBookPart()
        book[u'failed'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'tag:nextthought.com,2011-10:due_and_failed'
        part[u'failed'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = 0
        grade.username = u'cald3307'
        entry[u'cald3307'] = container
        # We have earned 0 points out of a possible 10.
        # While this assignment is only worth 5 points,
        # the unsubmitted assignment (due_and_passed) is
        # also being counted towards the total possible
        # points for the course.
        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(0))
        assert_that(grade.points_available, is_(10))
        assert_that(grade.points_earned, is_(0))

        # This should also be counted because it's due.
        part = GradeBookPart()
        book[u'passed'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'tag:nextthought.com,2011-10:due_and_passed'
        part[u'passed'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = 5
        grade.username = u'cald3307'
        entry[u'cald3307'] = container
        # We have earned 5 points out of a possible 10.
        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(50))
        assert_that(grade.points_available, is_(10))
        assert_that(grade.points_earned, is_(5))

        # If the student has not been graded, but has submitted
        # the assignment, we ignore it instead of counting as a 0.
        part = GradeBookPart()
        book[u'ungraded'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'tag:nextthought.com,2011-10:ungraded'
        part[u'ungraded'] = entry
        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(50))
        assert_that(grade.points_available, is_(10))
        assert_that(grade.points_earned, is_(5))

        # Check that an excused grade does not affect
        # the total, even if it is due.
        cap['tag:nextthought.com,2011-10:excused'] = {
            'auto_grade': {'total_points': 5}
        }
        part = GradeBookPart()
        book[u'excused'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'tag:nextthought.com,2011-10:excused'
        part[u'excused'] = entry
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = 100
        container.Excused = True
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(50))
        assert_that(grade.points_available, is_(10))
        assert_that(grade.points_earned, is_(5))

        # If a student has not submitted an assignment that is
        # due and for which there is a policy, it should count
        # as a 0. Thus, we have another assignment worth 5 points,
        # but since it does not have a corresponding gradebook
        # entry, we count it as a zero. We have scored
        # 5 points out of what is now a possible 15.
        cap['tag:nextthought.com,2011-10:unsubmitted'] = {
            'auto_grade': {'total_points': 5}
        }

        part = GradeBookPart()
        book[u'unsubmitted'] = part
        entry = GradeBookEntry()
        entry.assignmentId = u'tag:nextthought.com,2011-10:unsubmitted'
        part[u'unsubmitted'] = entry

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(33))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(5))

        # Check that a no-submit grade does not affect
        # the total if it is not graded.
        cap['tag:nextthought.com,2011-10:no-submit'] = {
            'auto_grade': {'total_points': 5}
        }
        part = GradeBookPart()
        book[u'no-submit'] = part
        part.no_submit = True
        entry = GradeBookEntry()
        entry.assignmentId = u'tag:nextthought.com,2011-10:no-submit'
        part[u'no-submit'] = entry

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(33))
        assert_that(grade.points_available, is_(15))
        assert_that(grade.points_earned, is_(5))

        # But if we grade it, it should be counted normally.
        # We now expect to have earned 10 out of 20 points.
        grade = PersistentGrade()
        grade.__parent__ = container = GradeContainer()
        grade.value = 5
        grade.username = u'cald3307'
        entry[u'cald3307'] = container

        grade = policy.grade('cald3307')
        assert_that(grade.correctness, is_(50))
        assert_that(grade.points_available, is_(20))
        assert_that(grade.points_earned, is_(10))

    def test_assignment_has_questions(self):

        assignment = QAssignment()
        simple_policy = SimpleTotalingGradingPolicy()

        # This assignment has no questions yet, so it
        # should be considered no-submit.
        no_submit = simple_policy._has_questions(assignment)
        assert_that(no_submit, is_(False))

        # If we add a part, a question set, and a question,
        # it shouldn't be no-submit anymore.
        part = QAssignmentPart(
                question_set=QQuestionSet(
                    questions=[QQuestion(
                        parts=[QMathPart()])]))
        assignment.parts = [part]

        no_submit = simple_policy._has_questions(assignment)
        assert_that(no_submit, is_(True))
