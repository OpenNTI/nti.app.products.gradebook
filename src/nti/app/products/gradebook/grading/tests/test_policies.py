#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
from hamcrest.library.object.hasproperty import has_property
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
does_not = is_not

import unittest

# from nti.app.products.gradebook.grades import Grade
# from nti.app.products.gradebook.gradebook import GradeBook
# from nti.app.products.gradebook.gradebook import GradeBookPart
# from nti.app.products.gradebook.gradebook import GradeBookEntry
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

class TestGradePolicies(unittest.TestCase):
	
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
		policy = DefaultCourseGradingPolicy()
		items = policy.items = {}
		policy.DefaultGradeScheme = IntegerGradeScheme(min=0, max=50)
		for x in range(5):
			age = AssigmentGradeScheme()
			age.Weight = 0.20
			age.GradeScheme = IntegerGradeScheme(min=0, max=10)
			items['assigment_%s' % (x+1)] = age
		
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
		