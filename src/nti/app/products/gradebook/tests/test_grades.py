#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property

from nti.dataserver.users import User

from .. import grades

from .  import ConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestGrades(ConfiguringTestBase):

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

	ntiid = 'tag:nextthought.com,2011-10:NextThought-quiz-quiz'

	def test_grade_clone(self):
		g = grades.Grade(username='nt@nti.com', NTIID=self.ntiid, grade=85.0)
		c = g.clone()
		assert_that(c, is_not(none()))
		assert_that(c, has_property('username', g.username))
		assert_that(c, has_property('NTIID', g.NTIID))
		assert_that(c, has_property('grade', g.grade))

	def test_grade_copy(self):
		g = grades.Grade(username='nt@nti.com', NTIID=self.ntiid, grade=85.0)
		c = grades.Grade()
		c.copy(g)
		assert_that(c, is_not(none()))
		assert_that(c, has_property('username', g.username))
		assert_that(c, has_property('NTIID', g.NTIID))
		assert_that(c, has_property('grade', g.grade))

	@WithMockDSTrans
	def test_grades(self):
		self._create_user()
		store = grades.Grades()
		g1 = grades.Grade(username='nt@nti.com', NTIID=self.ntiid, grade=85.0)
		idx = store.add_grade(g1)
		assert_that(idx, is_(0))

		g2 = grades.Grade(username='nt@nti.com', NTIID=self.ntiid + '2', grade=84.0)
		idx = store.add_grade(g2)
		assert_that(idx, is_(1))

		g2.grade = 82.0
		idx = store.add_grade(g2)
		assert_that(idx, is_(1))

		lst = store.get_grades('nt@nti.com')
		assert_that(lst, has_length(2))

		g = store.find_grade(self.ntiid + '2', 'nt@nti.com')
		assert_that(g2, is_(g))
		assert_that(g, has_property('grade', 82.0))

		idx = store.remove_grade(g.NTIID, 'nt@nti.com')
		assert_that(idx, is_(1))
		lst = store.get_grades('nt@nti.com')
		assert_that(lst, has_length(1))

		g3 = grades.Grade(username='nt@nti.com', NTIID=self.ntiid + '3', grade=100.0)
		idx = store.add_grade(g3)
		assert_that(idx, is_(1))

		store.remove_grades(self.ntiid)
		g = store.find_grade(self.ntiid, 'nt@nti.com')
		assert_that(g, is_(none()))

		assert_that(store.clear('nt@nti.com'), is_(True))
		assert_that(store.clear('nt@nti.com'), is_(False))
