#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from .. import gradebook
from .. import interfaces as grade_interfaces

from .  import ConfiguringTestBase

from hamcrest import (assert_that, none, is_not, has_property)

class TestAdapters(ConfiguringTestBase):

	def test_grade(self):
		g = grade_interfaces.IGrade('quiz1', None)
		assert_that(g, is_not(none()))
		assert_that(g, has_property('ntiid', 'quiz1'))

	def test_gradebookentry(self):
		gbp = gradebook.GradeBookPart()
		gbp.__name__ = 'quizzes'

		gbe = gradebook.GradeBookEntry()
		gbe.__parent__ = gbp
		gbe.__name__ = 'quiz1'
		gbe.order = 2
		gbe.name = 'quiz-1'

		g = grade_interfaces.IGrade(gbe, None)
		assert_that(g, is_not(none()))
		assert_that(g, has_property('ntiid',
					'tag:nextthought.com,2011-10:system-gradebookentry-quizzes.quiz1'))

