#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

import os
import codecs
import unittest
import simplejson

import fudge

from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.gradescheme import IntegerGradeScheme

from nti.app.products.gradebook.grading.interfaces import ICategoryGradeScheme
from nti.app.products.gradebook.grading.interfaces import IGradeBookGradingPolicy

from nti.app.products.gradebook.grading.policies import CategoryGradeScheme
from nti.app.products.gradebook.grading.policies import CS1323EqualGroupGrader
from nti.app.products.gradebook.grading.policies import CS1323CourseGradingPolicy
from nti.app.products.gradebook.grading.policies import ICS1323CourseGradingPolicy

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.assignment import MappingAssignmentPolicies

from nti.externalization.internalization import find_factory_for
from nti.externalization.externalization import to_external_object
from nti.externalization.internalization import update_from_external_object
	
import nti.dataserver.tests.mock_dataserver as mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.testing.matchers import verifiably_provides, validly_provides

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

class TestCS1323GradePolicy(unittest.TestCase):
	
	layer = SharedConfiguringTestLayer
	
	def test_verifiably_provides(self):		
		cat = CategoryGradeScheme()
		cat.Weight = 1.0
		cat.GradeScheme = IntegerGradeScheme(min=0, max=1)
		assert_that(cat, validly_provides(ICategoryGradeScheme))
		assert_that(cat, verifiably_provides(ICategoryGradeScheme))
		
		grader = CS1323EqualGroupGrader()
		grader.groups =  {'cat': cat}
		
		policy = CS1323CourseGradingPolicy()
		policy.grader = grader
		assert_that(policy, validly_provides(ICS1323CourseGradingPolicy))
		assert_that(policy, verifiably_provides(ICS1323CourseGradingPolicy))
		
	def test_externalization(self):
		cat = CategoryGradeScheme()
		cat.Weight = 1.0

		grader = CS1323EqualGroupGrader()
		grader.groups =  {'category': cat}
		
		policy = CS1323CourseGradingPolicy()
		policy.grader = grader
		
		ext = to_external_object(policy)
		assert_that(ext, has_entry('Grader', has_entry('Groups', has_length(1))))
		
		factory = find_factory_for(ext)
		obj = factory()
		update_from_external_object(obj, ext)

		assert_that(obj, has_property('Grader', has_property('Groups', has_length(1))))
		
	@property
	def cs1323_policy(self):
		path = os.path.join( os.path.dirname(__file__), 'cs1323_policy.json')
		with codecs.open(path, "r", encoding="UTF-8") as fp:
			ext = simplejson.load(fp)
		factory = find_factory_for(ext)
		result = factory()
		update_from_external_object(result, ext)		
		return result

	def test_internalization(self):
		policy = self.cs1323_policy	
		assert_that(policy, validly_provides(IGradeBookGradingPolicy))
		
		assert_that(policy, has_property('grader', has_length(2)))	
		category = policy.grader['iclicker']
		assert_that(category, has_property('Weight', is_(0.25)))
		assert_that(category, has_property('DropLowest', is_(1)))
		
		ext = to_external_object(policy)
		assert_that(ext, has_key('PresentationGradeScheme'))
				
	@WithMockDSTrans
	@fudge.patch('nti.contenttypes.courses.grading.policies.get_assignment',
				 'nti.contenttypes.courses.grading.policies.get_assignment_policies')
	def test_grade(self, mock_ga, mock_gap):
		connection = mock_dataserver.current_transaction
		course = CourseInstance()
		connection.add(course)
		
		policy = self.cs1323_policy	
		policy.__parent__ = course
		
		# assignment policies
		mock_ga.is_callable().with_args().returns(fudge.Fake())
		cap = MappingAssignmentPolicies()
		cap['a1'] = {'grader': {'group':'iclicker', 'points':10}}
		cap['a2'] = {'grader': {'group':'turingscraft', 'points':10}}
		
		mock_gap.is_callable().with_args().returns(cap)
		policy.validate()
		
		book = IGradeBook(course)
		for name, cat in (('a1', 'iclicker'), ('a2', 'turingscraft')):
			part = GradeBookPart()
			book[cat] = part
			
			entry = GradeBookEntry()
			entry.assignmentId = name
			part[cat] = entry
			
			grade = PersistentGrade()
			grade.value = 5
			grade.username = 'cald3307'
			entry['cald3307'] = grade
		
		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.5))
