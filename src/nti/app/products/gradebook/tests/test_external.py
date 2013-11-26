#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property

import random

from nti.dataserver.users import User

from nti.externalization import externalization
from nti.externalization import internalization

from .. import grades
from .. import gradebook

from .  import ConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestExternal(ConfiguringTestBase):

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

	def test_grade(self):
		g = grades.Grade(username='nt@nti.com', ntiid="quiz1", grade=85.0, autograde=80.2)
		ext = externalization.to_external_object(g)
		assert_that(ext, has_entry(u'Class', 'Grade'))
		assert_that(ext, has_entry(u'grade', is_(85.0)))
		assert_that(ext, has_entry(u'ntiid', 'quiz1'))
		assert_that(ext, has_entry(u'autograde', is_(80.2)))
		assert_that(ext, has_entry(u'username', 'nt@nti.com'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.grade'))
		assert_that(ext, has_entry(u'Last Modified', is_not(none())))

		factory = internalization.find_factory_for(ext)
		newgrade = factory()
		internalization.update_from_external_object(newgrade, ext)
		assert_that(newgrade, has_property('ntiid', 'quiz1'))
		assert_that(newgrade, has_property('grade', is_(85.0)))
		assert_that(newgrade, has_property('autograde', is_(80.2)))
		assert_that(newgrade, has_property('username', is_('nt@nti.com')))

	def test_grades(self):
		count = 0
		store = grades.Grades()
		r = random.randint(5, 15)
		for _ in range(r):
			username = 'u%s' % random.randint(1, 5)
			entry = 'e%s' % random.randint(1, 5)
			grade = grades.Grade(ntiid=entry,
								 username=username,
								 grade=float(random.randint(1, 100)),
								 autograde=float(random.randint(1, 100)))
			if store.index(grade) == -1:
				count += 1
				store.add_grade(grade)

		ext = externalization.to_external_object(store)
		assert_that(ext, has_entry(u'Class', 'Grades'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.grades'))
		new_count = 0
		for lst in ext.get('Items', {}).values():
			new_count += len(lst)
		assert_that(new_count, is_(count))

		factory = internalization.find_factory_for(ext)
		new_store = factory()
		internalization.update_from_external_object(new_store, ext)

		assert_that(len(store), is_(len(new_store)))
		for username in store.keys():
			for grade in store.get_grades(username):
				new_grade = new_store.find_grade(grade, username)
				assert_that(new_grade, is_not(none()))
				assert_that(new_grade, has_property('username', grade.username))
				assert_that(new_grade, has_property('grade', grade.grade))
				assert_that(new_grade, has_property('autograde'), is_(grade.autograde))
		
	@WithMockDSTrans
	def test_gradebook(self):
		class Parent(object):
			__parent__ = None
			__name__ = 'CS1330'

		gb = gradebook.GradeBook()
		gb.__parent__ = Parent()
		gb.creator = self._create_user()

		ext = externalization.to_external_object(gb)
		assert_that(ext, has_entry(u'Class', 'GradeBook'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'Creator', 'nt@nti.com'))
		assert_that(ext, has_entry(u'TotalPartWeight', 0.0))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebook'))
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:course-gradebook-CS1330'))

	@WithMockDSTrans
	def test_gradebookpart(self):

		gb = gradebook.GradeBook()

		gbp = gradebook.GradeBookPart()
		gbp.__parent__ = gb
		gbp.__name__ = 'quizzes'
		gbp.order = 1
		gbp.name = 'quizzes'
		gbp.weight = 0.95

		ext = externalization.to_external_object(gbp)
		assert_that(ext, has_entry(u'Class', 'GradeBookPart'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'name', 'quizzes'))
		assert_that(ext, has_entry(u'order', 1))
		assert_that(ext, has_entry(u'weight', 0.95))
		assert_that(ext, has_entry(u'TotalEntryWeight', 0.0))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebookpart'))
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:course-gradebookpart-quizzes'))

	@WithMockDSTrans
	def test_gradebookentry(self):

		gbp = gradebook.GradeBookPart()
		gbp.__name__ = 'quizzes'

		gbe = gradebook.GradeBookEntry()
		gbe.__parent__ = gbp
		gbe.order = 2
		gbe.name = 'quiz-1'
		gbe.weight = 0.55
		gbe.maxGrade = 30
		gbe.assignmentId = 'myquestion'

		ext = externalization.to_external_object(gbe)
		assert_that(ext, has_entry(u'Class', 'GradeBookEntry'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'name', 'quiz-1'))
		assert_that(ext, has_entry(u'order', 2))
		assert_that(ext, has_entry(u'weight', 0.55))
		assert_that(ext, has_entry(u'maxGrade', 30))
		assert_that(ext, has_entry(u'DueDate', is_(none())))
		assert_that(ext, has_entry(u'assignmentId', 'myquestion'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebookentry'))
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:course-gradebookentry-quizzes.quiz_1'))

