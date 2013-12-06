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
from .. import gradescheme

from .  import ConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestExternal(ConfiguringTestBase):

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

	def test_grade(self):
		g = grades.Grade(username='nt@nti.com', NTIID="quiz1", grade=85.0)
		ext = externalization.to_external_object(g)
		assert_that(ext, has_entry(u'Class', 'Grade'))
		assert_that(ext, has_entry(u'grade', is_(85.0)))
		assert_that(ext, has_entry(u'NTIID', 'quiz1'))
		assert_that(ext, has_entry(u'username', 'nt@nti.com'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.grade'))
		assert_that(ext, has_entry(u'Last Modified', is_not(none())))

		factory = internalization.find_factory_for(ext)
		newgrade = factory()
		internalization.update_from_external_object(newgrade, ext)
		assert_that(newgrade, has_property('NTIID', 'quiz1'))
		assert_that(newgrade, has_property('grade', is_(85.0)))
		assert_that(newgrade, has_property('username', is_('nt@nti.com')))

	def test_grades(self):
		count = 0
		store = grades.Grades()
		r = random.randint(5, 15)
		for _ in range(r):
			username = 'u%s' % random.randint(1, 5)
			entry = 'e%s' % random.randint(1, 5)
			grade = grades.Grade(NTIID=entry,
								 username=username,
								 grade=float(random.randint(1, 100)))
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
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:NextThought-gradebook-CS1330'))

	@WithMockDSTrans
	def test_gradebookpart(self):

		gb = gradebook.GradeBook()

		gbp = gradebook.GradeBookPart()
		gbp.__parent__ = gb
		gbp.Name = 'quizzes'
		gbp.order = 1
		gbp.displayName = 'Quizzes'
		gbp.weight = 0.95

		ext = externalization.to_external_object(gbp)
		assert_that(ext, has_entry(u'Class', 'GradeBookPart'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'Name', 'quizzes'))
		assert_that(ext, has_entry(u'order', 1))
		assert_that(ext, has_entry(u'weight', 0.95))
		assert_that(ext, has_entry(u'displayName', 'Quizzes'))
		assert_that(ext, has_entry(u'TotalEntryWeight', 0.0))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebookpart'))
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:NextThought-gradebookpart-quizzes'))

	@WithMockDSTrans
	def test_gradebookentry(self):

		gbp = gradebook.GradeBookPart()
		gbp.__name__ = 'quizzes'

		gbe = gradebook.GradeBookEntry()
		gbe.__parent__ = gbp
		gbe.order = 2
		gbe.Name = 'quiz1'
		gbe.weight = 0.55
		gbe.displayName = 'Quiz 1'
		gbe.assignmentId = 'myquestion'

		ext = externalization.to_external_object(gbe)
		assert_that(ext, has_entry(u'Class', 'GradeBookEntry'))
		assert_that(ext, has_entry(u'Name', 'quiz1'))
		assert_that(ext, has_entry(u'order', 2))
		assert_that(ext, has_entry(u'weight', 0.55))
		assert_that(ext, has_entry(u'displayName', 'Quiz 1'))
		assert_that(ext, has_entry(u'DueDate', is_(none())))
		assert_that(ext, has_entry(u'GradeScheme', is_(none())))
		assert_that(ext, has_entry(u'assignmentId', 'myquestion'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebookentry'))
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:NextThought-gradebookentry-quizzes.quiz1'))


	@WithMockDSTrans
	def test_gradescheme(self):
		s = gradescheme.BooleanGradeScheme()
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'BooleanGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.booleangradescheme'))

		s = gradescheme.IntegerGradeScheme()
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'IntegerGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.integergradescheme'))
		assert_that(ext, has_entry(u'min', 0))
		assert_that(ext, has_entry(u'max', 100))

		s = gradescheme.NumericGradeScheme(min=10.0, max=15.0)
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'NumericGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.numericgradescheme'))
		assert_that(ext, has_entry(u'min', 10.0))
		assert_that(ext, has_entry(u'max', 15.0))

		scheme = internalization.find_factory_for(ext)()
		internalization.update_from_external_object(scheme, ext)
		assert_that(s, is_(scheme))

