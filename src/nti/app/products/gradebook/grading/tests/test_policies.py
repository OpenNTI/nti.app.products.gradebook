#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

import os
import codecs
import unittest
import simplejson

from nti.app.products.gradebook.grades import Grade
from nti.app.products.gradebook.gradebook import GradeBook
from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.gradescheme import IntegerGradeScheme

from nti.app.products.gradebook.grading.policies import AssigmentGradeScheme
from nti.app.products.gradebook.grading.policies import CategoryGradeScheme
from nti.app.products.gradebook.grading.policies import ICategoryGradeScheme
from nti.app.products.gradebook.grading.policies import CS1323EqualGroupGrader
from nti.app.products.gradebook.grading.policies import CS1323CourseGradingPolicy
from nti.app.products.gradebook.grading.policies import ICS1323CourseGradingPolicy

from nti.externalization.internalization import find_factory_for
from nti.externalization.externalization import to_external_object
from nti.externalization.internalization import update_from_external_object
	
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
		
	def test_internalization(self):
		path = os.path.join( os.path.dirname(__file__), 'cs1323_policy.json')
		with codecs.open(path, "r", encoding="UTF-8") as fp:
			ext = simplejson.load(fp)
		factory = find_factory_for(ext)
		obj = factory()
		update_from_external_object(obj, ext)
		
		category = obj.grader['iclicker']
		assert_that(category, has_property('Weight', is_(0.25)))
		assert_that(category, has_property('DropLowest', is_(1)))

	def test_grade(self):
		return
		items = {}
		cat = CategoryGradeScheme()
		cat.Weight = 1.0
		cat.GradeScheme = IntegerGradeScheme(min=0, max=1)		
		for x in range(5):
			age = AssigmentGradeScheme()
			age.Weight = 0.20
			age.GradeScheme = IntegerGradeScheme(min=0, max=10)
			items['assigment_%s' % (x+1)] = age
		cat.AssigmentGradeSchemes = items
		
		policy = CS1323CourseGradingPolicy()
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=50)
		policy.CategoryGradeSchemes = {'category': cat}
		
		book = GradeBook()
		part = GradeBookPart()
		book['part'] = part
		for x in range(5):
			name = 'assigment_%s' % (x+1)
			entry = GradeBookEntry()
			entry.assignmentId = name
			part[name] = entry
			grade = Grade()
			grade.value = 5
			grade.username = 'cald3307'
			entry['cald3307'] = grade
		
		policy.__dict__['book'] = book
		grade = policy.grade('cald3307')
		assert_that(grade, is_(0.5))
