#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.dataserver.users import User

from .. import grades

from .  import ConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from hamcrest import (assert_that, none, is_, is_not, has_property, has_length)

class TestGrades(ConfiguringTestBase):

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

	def test_grade_clone(self):
		g = grades.Grade(username='nt@nti.com', ntiid="quiz1", grade=85.0, autograde=80.2)
		c = g.clone()
		assert_that(c, is_not(none()))
		assert_that(c, has_property('username', g.username))
		assert_that(c, has_property('ntiid', g.ntiid))
		assert_that(c, has_property('grade', g.grade))
		assert_that(c, has_property('autograde', g.autograde))

	def test_grade_copy(self):
		g = grades.Grade(username='nt@nti.com', ntiid="quiz1", grade=85.0, autograde=80.2)
		c = grades.Grade()
		c.copy(g)
		assert_that(c, is_not(none()))
		assert_that(c, has_property('username', g.username))
		assert_that(c, has_property('ntiid', g.ntiid))
		assert_that(c, has_property('grade', g.grade))
		assert_that(c, has_property('autograde', g.autograde))

	@WithMockDSTrans
	def test_grades(self):
		self._create_user()
		store = grades.Grades()
		g1 = grades.Grade(username='nt@nti.com', ntiid="quiz1", grade=85.0, autograde=80.2)
		idx = store.add_grade(g1)
		assert_that(idx, is_(0))

		g2 = grades.Grade(username='nt@nti.com', ntiid="quiz2", grade=84.0, autograde=81.0)
		idx = store.add_grade(g2)
		assert_that(idx, is_(1))

		g2.grade = 82.0
		idx = store.add_grade(g2)
		assert_that(idx, is_(1))

		lst = store.get_grades('nt@nti.com')
		assert_that(lst, has_length(2))

		g = store.find_grade("quiz2", 'nt@nti.com')
		assert_that(g2, is_(g))
		assert_that(g, has_property('grade', 82.0))

		idx = store.remove_grade("quiz2", 'nt@nti.com')
		assert_that(idx, is_(1))
		lst = store.get_grades('nt@nti.com')
		assert_that(lst, has_length(1))

		g3 = grades.Grade(username='nt@nti.com', ntiid="quiz3", grade=100.0, autograde=100.0)
		idx = store.add_grade(g3)
		assert_that(idx, is_(1))

		store.remove_grades("quiz1")
		g = store.find_grade("quiz1", 'nt@nti.com')
		assert_that(g, is_(none()))

		assert_that(store.clear('nt@nti.com'), is_(True))
		assert_that(store.clear('nt@nti.com'), is_(False))
