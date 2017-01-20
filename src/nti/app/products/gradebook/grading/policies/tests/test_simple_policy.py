#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import unittest

import fudge

from zope import interface

from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.grading.policies.interfaces import ISimpleTotalingGradingPolicy

from nti.app.products.gradebook.grading.policies.simple import SimpleTotalingGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IExcusedGrade

from nti.assessment.assignment import QAssignment

from nti.contenttypes.courses.assignment import MappingAssignmentPolicies

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.grading import set_grading_policy_for_course

from nti.externalization.externalization import to_external_object

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.dataserver.tests import mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


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
				 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._get_all_assignments_for_user')
	def test_simple_grade_predictor_policy(self, mock_ga, mock_gap, mock_get_assignments):

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

		book = IGradeBook(course)

		# If there are no points available, we return None.
		grade = policy.grade('cald3307')
		assert_that(grade, is_(None))

		for name, cat in (('a1', 'iclicker'), ('a2', 'turingscraft')):
			part = GradeBookPart()
			book[cat] = part

			entry = GradeBookEntry()
			entry.assignmentId = name
			part[cat] = entry

			grade = PersistentGrade()
			grade.value = 5.5
			grade.username = 'cald3307'
			entry['cald3307'] = grade

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
		assert_that(grade, is_(0.73))

		# Check that an assignment not due and not graded
		# does not affect the total
		part = GradeBookPart()
		book['early_and_ungraded'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'a3'
		part['early_and_ungraded'] = entry
		grade = PersistentGrade()
		grade.username = 'cald3307'
		entry['cald3307'] = grade

		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.73))

		# Check that a non-numeric grade gets ignored.
		part = GradeBookPart()
		book['non_numeric_grade'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'a4'
		part['non_numeric_grade'] = entry
		grade = PersistentGrade()
		grade.value = 'non-numeric grade, but has 1 number in it'
		grade.username = 'cald3307'
		entry['cald3307'] = grade

		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.73))

		# Check that an excused grade does not affect the total
		cap['excused'] = {'auto_grade': {'total_points': 5}}
		part = GradeBookPart()
		book['excused'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'excused'
		part['excused'] = entry
		grade = PersistentGrade()
		grade.value = 100
		interface.alsoProvides(grade, IExcusedGrade)
		grade.username = 'cald3307'
		entry['cald3307'] = grade

		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.73))

		# A grade without an entry in the course policy
		# should be ignored.
		part = GradeBookPart()
		book['no_policy'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'id_to_missing_assignment'
		part['excused'] = entry
		grade = PersistentGrade()
		grade.value = 100
		grade.username = 'cald3307'
		entry['cald3307'] = grade

		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.73))
		
		# Negative grades are possible, but cannot
		# make the course grade less than 0.
		cap['negative_grade']= {'auto_grade': {'total_points': 5}}
		part = GradeBookPart()
		book['negative_grade'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'negative_grade'
		part['negative_grade'] = entry
		grade = PersistentGrade()
		grade.value = -12 # We now have -1 points for the course
		grade.username = 'cald3307'
		entry['cald3307'] = grade
		
		grade = policy.grade('cald3307')
		assert_that(grade, is_(0))
		
		# Extra credit cannot cause a grade to be
		# more than 1 (a perfect score)
		cap['extra_credit_grade']= {'auto_grade': {'total_points': 5}}
		part = GradeBookPart()
		book['extra_credit'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'extra_credit_grade'
		part['extra_credit'] = entry
		grade = PersistentGrade()
		grade.value = 100
		grade.username = 'cald3307'
		entry['cald3307'] = grade
		
		grade = policy.grade('cald3307')
		assert_that(grade, is_(1))

	@WithMockDSTrans
	@fudge.patch('nti.contenttypes.courses.grading.policies.get_assignment',
				 'nti.app.products.gradebook.grading.policies.simple.get_assignment_policies',
				 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._get_all_assignments_for_user',
				 'nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._is_due')
	def test_simple_grade_predictor_for_late_assignments(self, mock_ga, mock_gap, mock_get_assignments, mock_is_due):

		connection = mock_dataserver.current_transaction
		course = CourseInstance()
		connection.add(course)

		policy = SimpleTotalingGradingPolicy()
		policy.__parent__ = course

		# assignment policies
		mock_ga.is_callable().with_args().returns(fudge.Fake())
		mock_is_due.is_callable().with_args().returns(True)
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
		a2.ntiid = 'tag:nextthought.com,2011-10:due_and_failed'
		assignments.append(a2)
		a3 = QAssignment()
		a3.ntiid = 'tag:nextthought.com,2011-10:due_and_passed'
		assignments.append(a3)
		a4 = QAssignment()
		a4.ntiid = 'tag:nextthought.com,2011-10:excused'
		assignments.append(a4)
		a5 = QAssignment()
		a5.ntiid = 'tag:nextthought.com,2011-10:unsubmitted'
		assignments.append(a5)
		mock_get_assignments.is_callable().with_args().returns(assignments)

		book = IGradeBook(course)
		# This should be counted because it's due and not excused,
		# even though the student earned 0 points on this assignment.
		part = GradeBookPart()
		book['failed'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'tag:nextthought.com,2011-10:due_and_failed'
		part['failed'] = entry
		grade = PersistentGrade()
		grade.value = 0
		grade.username = 'cald3307'
		entry['cald3307'] = grade
		# We have earned 0 points out of a possible 10.
		# While this assignment is only worth 5 points,
		# the unsubmitted assignment (due_and_passed) is
		# also being counted towards the total possible
		# points for the course.
		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.0))

		# This should also be counted because it's due.
		part = GradeBookPart()
		book['passed'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'tag:nextthought.com,2011-10:due_and_passed'
		part['passed'] = entry
		grade = PersistentGrade()
		grade.value = 5
		grade.username = 'cald3307'
		entry['cald3307'] = grade
		# We have earned 5 points out of a possible 10.
		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.5))

		# Check that an excused grade does not affect
		# the total, even if it is due.
		cap['tag:nextthought.com,2011-10:excused'] = {
			'auto_grade': {'total_points': 5}
		}
		part = GradeBookPart()
		book['excused'] = part
		entry = GradeBookEntry()
		entry.assignmentId = 'tag:nextthought.com,2011-10:excused'
		part['excused'] = entry
		grade = PersistentGrade()
		grade.value = 100
		interface.alsoProvides(grade, IExcusedGrade)
		grade.username = 'cald3307'
		entry['cald3307'] = grade

		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.5))

		# If a student has not submitted an assignment that is
		# due and for which there is a policy, it should count
		# as a 0. Thus, we have another assignment worth 5 points,
		# but since it does not have a corresponding gradebook
		# entry, we count it as a zero. We have scored
		# 5 points out of what is now a possible 15.
		cap['tag:nextthought.com,2011-10:unsubmitted'] = {
			'auto_grade': {'total_points': 5}
		}
		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.33))
