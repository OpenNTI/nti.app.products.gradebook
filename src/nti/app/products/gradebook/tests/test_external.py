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

import unittest

from nti.dataserver.users import User

from nti.externalization import externalization
from nti.externalization import internalization

from .. import grades
from .. import gradebook
from .. import gradescheme

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from . import SharedConfiguringTestLayer

class TestExternal(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def _create_user(self, username='nt@nti.com', password='temp001'):
		usr = User.create_user(self.ds, username=username, password=password)
		return usr

	def test_grade(self):
		g = grades.Grade(username='nt@nti.com',  grade=85.0)
		ext = externalization.to_external_object(g)
		assert_that(ext, has_entry('Class', 'Grade'))
		assert_that(ext, has_entry('value', is_(85.0)))
		assert_that(ext, has_entry('Username', 'nt@nti.com'))
		assert_that(ext, has_entry('MimeType', 'application/vnd.nextthought.grade'))
		assert_that(ext, has_entry('Last Modified', is_not(none())))

		factory = internalization.find_factory_for(ext)
		newgrade = factory()
		newgrade.__parent__ = gradebook.GradeBookEntry()

		internalization.update_from_external_object(newgrade, ext)
		assert_that(newgrade, has_property('value', is_(85.0)))
		assert_that(newgrade, has_property('Username', is_('nt@nti.com')))

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
		#assert_that(ext, has_entry(u'TotalPartWeight', 0.0))
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
		#gbp.weight = 0.95

		ext = externalization.to_external_object(gbp)
		assert_that(ext, has_entry(u'Class', 'GradeBookPart'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'Name', 'quizzes'))
		assert_that(ext, has_entry(u'order', 1))
		#assert_that(ext, has_entry(u'weight', 0.95))
		assert_that(ext, has_entry(u'displayName', 'Quizzes'))
		#assert_that(ext, has_entry(u'TotalEntryWeight', 0.0))
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
		#gbe.weight = 0.55
		gbe.displayName = 'Quiz 1'
		gbe.assignmentId = 'myquestion'

		ext = externalization.to_external_object(gbe)
		assert_that(ext, has_entry(u'Class', 'GradeBookEntry'))
		assert_that(ext, has_entry(u'Name', 'quiz1'))
		assert_that(ext, has_entry(u'order', 2))
		#assert_that(ext, has_entry(u'weight', 0.55))
		assert_that(ext, has_entry(u'displayName', 'Quiz 1'))
		assert_that(ext, has_entry(u'DueDate', is_(none())))
		assert_that(ext, has_entry(u'GradeScheme', is_(none())))
		assert_that(ext, has_entry(u'AssignmentId', 'myquestion'))
		assert_that(ext, has_entry(u'CreatedTime', is_not(none())))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebookentry'))
		assert_that(ext, has_entry(u'NTIID', 'tag:nextthought.com,2011-10:NextThought-gradebookentry-quizzes.quiz1'))

	@WithMockDSTrans
	def test_gradescheme(self):
		s = gradescheme.BooleanGradeScheme()
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'BooleanGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebook.booleangradescheme'))

		s = gradescheme.IntegerGradeScheme()
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'IntegerGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebook.integergradescheme'))
		assert_that(ext, has_entry(u'min', 0))
		assert_that(ext, has_entry(u'max', 100))

		s = gradescheme.NumericGradeScheme(min=10.0, max=15.0)
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'NumericGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebook.numericgradescheme'))
		assert_that(ext, has_entry(u'min', 10.0))
		assert_that(ext, has_entry(u'max', 15.0))

		scheme = internalization.find_factory_for(ext)()
		internalization.update_from_external_object(scheme, ext)
		assert_that(s, is_(scheme))

		s = gradescheme.LetterGradeScheme()
		ext = externalization.to_external_object(s)
		assert_that(ext, has_entry(u'Class', 'LetterGradeScheme'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.gradebook.lettergradescheme'))
		assert_that(ext, has_entry(u'grades', is_([u'A', u'B', u'C', u'D', u'F'])))
		assert_that(ext, has_entry(u'ranges', is_([[90, 100], [80, 89], [70, 79], [40, 69], [0, 39]])))

		scheme = internalization.find_factory_for(ext)()
		internalization.update_from_external_object(scheme, ext)
		assert_that(s, is_(scheme))
		assert_that(s, has_property(u'grades', is_((u'A', u'B', u'C', u'D', u'F'))))
		assert_that(s, has_property(u'ranges', is_(((90, 100), (80, 89), (70, 79), (40, 69), (0, 39)))))
