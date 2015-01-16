#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_key
from hamcrest import assert_that

from zope import component

from nti.app.products.gradebook.grades import Grade
from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.assignments import synchronize_gradebook

from nti.app.products.gradebook.generations.evolve2 import evolve_book

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

class TestAssignments(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer
	
	@WithSharedApplicationMockDS(testapp=True,
								 default_authenticate=True)
	def test_evolution(self):
		conn = mock_dataserver.current_transaction
		root = conn.root()
		generations = root['zope.generations']
		assert_that( generations, has_key('nti.dataserver-products-gradebook'))

		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user("ichigo")
			self._create_user("aizen")
			
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

			lib = component.getUtility(IContentPackageLibrary)

			for package in lib.contentPackages:
				course = ICourseInstance(package)
				if course.__name__ != 'CLC3403':
					continue

				synchronize_gradebook(course)
				book = IGradeBook(course)
				entry = book['quizzes']['Main Title']
				entry['ichigo'] = Grade(value=100)
				entry['aizen'] = Grade(value=90)
				
				count = evolve_book(book)
				assert_that(count, is_(2))