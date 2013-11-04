#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from zope import component

from nti.dataserver.users import User
from nti.dataserver import interfaces as nti_interfaces

from .. import adapters
from .. import gradebook
from .. import interfaces as grade_interfaces

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from . import ConfiguringTestBase

from hamcrest import (assert_that, none, is_not, is_, has_property)

class TestAdapters(ConfiguringTestBase):

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

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

	@WithMockDSTrans
	def test_grade_note(self):
		g = grade_interfaces.IGrade('quiz1', None)
		user = self._create_user()
		note = adapters.get_grade_discussion_note(user, g)
		assert_that(note, is_(none()))
		note = component.queryMultiAdapter((user, g), nti_interfaces.INote)
		assert_that(note, is_not(none()))
		assert_that(note, has_property('containerId', 'quiz1'))
		note2 = component.queryMultiAdapter((user, g), nti_interfaces.INote)
		assert_that(note, is_(note2))
