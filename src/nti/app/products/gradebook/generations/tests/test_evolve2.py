#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import has_property

import zope.intid

from zope import component

from nti.app.products.gradebook.grades import Grade
from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.assignments import synchronize_gradebook
from nti.app.products.gradebook.utils import record_grade_without_submission

from nti.app.products.gradebook.generations.evolve2 import do_evolve
from nti.app.products.gradebook.generations.evolve2 import evolve_book

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

class TestEvolution2(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer
	
	@WithSharedApplicationMockDS(testapp=True,
								 default_authenticate=True)
	def test_evolve_book(self):
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user("ichigo")
			self._create_user("aizen")
			
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

			lib = component.getUtility(IContentPackageLibrary)
			intids = component.getUtility(zope.intid.IIntIds)
			
			for package in lib.contentPackages:
				course = ICourseInstance(package)
				if course.__name__ != 'CLC3403':
					continue
				
				synchronize_gradebook(course)
				book = IGradeBook(course)

				assignment_name = 'Main Title'
				entry = book['quizzes'][assignment_name]
				
				for username, value in (('ichigo', 100), ('aizen', 90)):			
					user = self._get_user(username)
					record_grade_without_submission(entry, user, clazz=Grade)
					grade = entry[username]
					grade.value = value

				count = evolve_book(book, intids)
				assert_that(count, is_(2))
				
				for username, value in (('ichigo', 100), ('aizen', 90)):	
					grade = entry[username]
					assert_that(grade, has_property('value', is_(value)))
					assert_that(grade, has_property(intids.attribute, is_not(none())))
				
				return
			
	@WithSharedApplicationMockDS(testapp=True,
								 default_authenticate=True)
	def test_do_evolve(self):
			
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

			class _context(object): pass
			context = _context()
			context.connection = mock_dataserver.current_transaction
					
			total = do_evolve(context)
			assert_that(total, is_(0))
