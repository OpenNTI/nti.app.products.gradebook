#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import component
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.app.testing.application_webtest import ApplicationTestLayer
import os
import os.path

import ZODB
from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import mock_db_trans

from nti.dataserver import users
from zope.component.interfaces import IComponents
from nti.app.products.courseware.interfaces import ICourseCatalog

class InstructedCourseApplicationTestLayer(ApplicationTestLayer):

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library
		lib = Library(
					paths=(os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice'),
				   ))
		return lib

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(cls._setup_library(), IContentPackageLibrary)

		database = ZODB.DB( ApplicationTestLayer._storage_base,
							database_name='Users')
		@WithMockDS(database=database)
		def _create():
			with mock_db_trans():
				users.User.create_user( username='harp4162', password='temp001')
				# Re-enum to pick up instructor
				lib = component.getUtility(IContentPackageLibrary)
				#del lib.contentPackages
				getattr(lib, 'contentPackages')

				components = component.getUtility(IComponents, name='platform.ou.edu')
				catalog = components.getUtility( ICourseCatalog )

				# re-register globally
				global_catalog = component.getUtility(ICourseCatalog)
				global_catalog._entries[:] = catalog._entries

		_create()
	@classmethod
	def tearDown(cls):
		# Must implement!
		component.provideUtility(cls.__old_library, IContentPackageLibrary)

		components = component.getUtility(IComponents, name='platform.ou.edu')
		catalog = components.getUtility( ICourseCatalog )
		del catalog._entries[:]

		global_catalog = component.getUtility(ICourseCatalog)
		del global_catalog._entries[:]

	# TODO: May need to recreate the application with this library?



from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import find_test

from nti.dataserver.tests.mock_dataserver import DSInjectorMixin
import zope.testing.cleanup


class SharedConfiguringTestLayer(ZopeComponentLayer,
								 GCLayerMixin,
								 ConfiguringLayerMixin,
								 DSInjectorMixin):
	set_up_packages = ('nti.dataserver', 'nti.app.products.gradebook')

	@classmethod
	def setUp(cls):
		cls.setUpPackages()

	@classmethod
	def tearDown(cls):
		cls.tearDownPackages()


	@classmethod
	def testSetUp(cls, test=None):
		cls.setUpTestDS(test)
