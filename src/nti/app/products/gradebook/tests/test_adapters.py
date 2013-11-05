#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.dataserver.users import User
from nti.dataserver import interfaces as nti_interfaces

from .. import grades
from .. import adapters

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from . import ConfiguringTestBase

from hamcrest import (assert_that, none, is_not, is_, has_property)

class TestAdapters(ConfiguringTestBase):

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

	@WithMockDSTrans
	def test_grade_note(self):
		username = "ichigo@bleach.com"
		self._create_user(username)
		g = grades.Grade(username=username, ntiid="quiz1", grade=85.0, autograde=80.2)
		note = adapters.get_grade_discussion_note(g)
		assert_that(note, is_(none()))
		note = nti_interfaces.INote(g)
		assert_that(note, is_not(none()))
		assert_that(note, has_property('containerId', 'quiz1'))
		note2 = nti_interfaces.INote(g)
		assert_that(note, is_(note2))

