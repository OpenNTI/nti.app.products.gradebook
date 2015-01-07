#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import assert_that
does_not = is_not

import unittest

#from nti.app.products.gradebook.gradescheme import LetterGradeScheme
from nti.app.products.gradebook.gradescheme import IntegerGradeScheme
from nti.app.products.gradebook.grading_policies import AssigmentGradeScheme
from nti.app.products.gradebook.grading_policies import IAssigmentGradeScheme
from nti.app.products.gradebook.grading_policies import DefaultCourseGradingPolicy
from nti.app.products.gradebook.grading_policies import IDefaultCourseGradingPolicy

from nti.testing.matchers import verifiably_provides, validly_provides

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

class TestGradePolicies(unittest.TestCase):
	
	layer = SharedConfiguringTestLayer
	
	def test_validate(self):
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
