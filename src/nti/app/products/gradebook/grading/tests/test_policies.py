#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import contains_string
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
from nti.app.products.gradebook.grading.policies import IAssigmentGradeScheme
from nti.app.products.gradebook.grading.policies import DefaultCourseGradingPolicy
from nti.app.products.gradebook.grading.policies import IDefaultCourseGradingPolicy

from nti.externalization.internalization import find_factory_for
from nti.externalization.externalization import to_external_object
from nti.externalization.internalization import update_from_external_object
	
from nti.testing.matchers import verifiably_provides, validly_provides

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

class TestDefaultGradePolicy(unittest.TestCase):
	
	layer = SharedConfiguringTestLayer
	
	def test_verifiably_provides(self):
		age = AssigmentGradeScheme()
		age.weight = 1.0
		age.GradeScheme = IntegerGradeScheme(min=0, max=1)
		assert_that(age, validly_provides(IAssigmentGradeScheme))
		assert_that(age, verifiably_provides(IAssigmentGradeScheme))
		
		policy = DefaultCourseGradingPolicy()
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=1)
		policy.items = {'assigment': age}
		assert_that(policy, validly_provides(IDefaultCourseGradingPolicy))
		assert_that(policy, verifiably_provides(IDefaultCourseGradingPolicy))
		
	def test_externalization(self):
		items = {}
		policy = DefaultCourseGradingPolicy()
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=50)
		for x in range(5):
			age = AssigmentGradeScheme()
			age.Weight = 0.20
			age.GradeScheme = IntegerGradeScheme(min=0, max=10)
			items['assigment_%s' % (x+1)] = age
		policy.items = items
		
		ext = to_external_object(policy)
		assert_that(ext, has_entry('DefaultGradeScheme', is_not(none())))
		assert_that(ext, has_entry('AssigmentGradeSchemes', has_length(5)))
		items = ext['AssigmentGradeSchemes']
		for name, e in items.items():
			assert_that(name, contains_string('assigment_'))
			assert_that(e, has_entry('Weight', 0.20))
			assert_that(e, has_entry('GradeScheme', is_not(none())))

		ext_ag_1 = items['assigment_1']
		factory = find_factory_for(ext_ag_1)
		obj = factory()
		update_from_external_object(obj, ext_ag_1)
		assert_that(obj, has_property('Weight', is_(0.2)))
		assert_that(obj, has_property('GradeScheme', is_not(none())))
		
		factory = find_factory_for(ext)
		obj = factory()
		update_from_external_object(obj, ext)
		
		assert_that(obj, has_property('DefaultGradeScheme', is_(policy.DefaultGradeScheme)))
		assert_that(obj, has_property('AssigmentGradeSchemes', is_(policy.AssigmentGradeSchemes)))
		
	def test_validate(self):
		items = {}
		policy = DefaultCourseGradingPolicy()
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=50)
		for x in range(5):
			age = AssigmentGradeScheme()
			age.Weight = 0.20
			age.GradeScheme = IntegerGradeScheme(min=0, max=10)
			items['assigment_%s' % (x+1)] = age
		policy.items = items
		
		book = GradeBook()
		part = GradeBookPart()
		book['part'] = part
		for x in range(5):
			name = 'assigment_%s' % (x+1)
			entry = GradeBookEntry()
			entry.assignmentId = name
			part[name] = entry
		
		policy.__dict__['book'] = book
		policy.validate()
		
	def test_grade(self):
		items = {}
		policy = DefaultCourseGradingPolicy()
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=10)
		for x in range(5):
			age = AssigmentGradeScheme(Weight=0.2)
			items['assigment_%s' % (x+1)] = age
		policy.items = items
		
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

from nti.app.products.gradebook.grading.policies import CategoryGradeScheme
from nti.app.products.gradebook.grading.policies import ICategoryGradeScheme
from nti.app.products.gradebook.grading.policies import CS1323CourseGradingPolicy
from nti.app.products.gradebook.grading.policies import ICS1323CourseGradingPolicy

class TestCS1323GradePolicy(unittest.TestCase):
	
	layer = SharedConfiguringTestLayer
	
	def test_verifiably_provides(self):
		age = AssigmentGradeScheme()
		age.weight = 1.0
		age.GradeScheme = IntegerGradeScheme(min=0, max=1)
		assert_that(age, validly_provides(IAssigmentGradeScheme))
		assert_that(age, verifiably_provides(IAssigmentGradeScheme))
		
		cat = CategoryGradeScheme()
		cat.Weight = 1.0
		cat.GradeScheme = IntegerGradeScheme(min=0, max=1)
		cat.assigments = {'assigment': age}
		assert_that(cat, validly_provides(ICategoryGradeScheme))
		assert_that(cat, verifiably_provides(ICategoryGradeScheme))
		
		policy = CS1323CourseGradingPolicy()
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=1)
		policy.categories = {'cat': cat}
		assert_that(policy, validly_provides(ICS1323CourseGradingPolicy))
		assert_that(policy, verifiably_provides(ICS1323CourseGradingPolicy))
		
	def test_externalization(self):
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
		
		ext = to_external_object(policy)
		assert_that(ext, has_entry('DefaultGradeScheme', is_not(none())))
		assert_that(ext, has_entry('CategoryGradeSchemes', has_length(1)))
		assert_that(ext, has_entry('CategoryGradeSchemes', has_key('category')))
		
		category = ext['CategoryGradeSchemes']['category']
		assert_that(category, has_entry('Weight', 1.0))
		assert_that(category, has_entry('GradeScheme', is_not(none())))
		
		items = category['AssigmentGradeSchemes']
		for name, e in items.items():
			assert_that(name, contains_string('assigment_'))
			assert_that(e, has_entry('Weight', 0.20))
			assert_that(e, has_entry('GradeScheme', is_not(none())))
		
		factory = find_factory_for(ext)
		obj = factory()
		update_from_external_object(obj, ext)

		assert_that(obj, has_property('DefaultGradeScheme', is_(policy.DefaultGradeScheme)))
		assert_that(obj, has_property('CategoryGradeSchemes', is_(policy.CategoryGradeSchemes)))
		
	def test_internalization(self):
		path = os.path.join( os.path.dirname(__file__), 'cs1323_policy.json')
		with codecs.open(path, "r", encoding="UTF-8") as fp:
			ext = simplejson.load(fp)
		factory = find_factory_for(ext)
		obj = factory()
		update_from_external_object(obj, ext)
		
	def test_validate(self):
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
		
		policy.__dict__['book'] = book
		policy.validate()
		
	def test_grade(self):
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
