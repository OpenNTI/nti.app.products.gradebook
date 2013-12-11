#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import assert_that

import os

from zope import component

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.app.products.gradebook import assignments
from nti.app.products.gradebook import interfaces as grades_interfaces

from nti.app.testing.application_webtest import SharedApplicationTestBase

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.dataserver.tests import mock_dataserver

class TestViews(SharedApplicationTestBase):

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		lib = Library(
					paths=(os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice'),
				   ))
		return lib

	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_create_assignments_entries(self):

		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			for package in lib.contentPackages:
				course = ICourseInstance(package)
				entries = assignments.create_assignments_entries(course)
				assert_that(entries, is_(2))

				book = grades_interfaces.IGradeBook(course)
				assert_that(book, has_key('Assignments'))
				part = book['Assignments']
				assert_that(part, has_length(2))

