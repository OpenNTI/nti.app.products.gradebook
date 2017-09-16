#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import gc
import os
import os.path

from zope import component

from zope.component.interfaces import IComponents

import ZODB

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.dataserver.users.users import User

from nti.app.products.courseware.tests import publish_ou_course_entries

from nti.app.testing.application_webtest import ApplicationTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import mock_db_trans


class InstructedCourseApplicationTestLayer(ApplicationTestLayer):

    @classmethod
    def _setup_library(cls, *unused_args, **unused_kwargs):
        from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library
        lib = Library(
            paths=(os.path.join(os.path.dirname(__file__),
                                'Library',
                                'CLC3403_LawAndJustice'),
        ))
        return lib

    @classmethod
    def setUp(cls):
        # Must implement!
        gsm = component.getGlobalSiteManager()
        cls.__old_library = gsm.getUtility(IContentPackageLibrary)
        cls.__new_library = cls._setup_library()
        gsm.registerUtility(cls.__new_library, IContentPackageLibrary)

        database = ZODB.DB(ApplicationTestLayer._storage_base,
                           database_name='Users')

        @WithMockDS(database=database)
        def _create():
            with mock_db_trans():
                User.create_user(username=u'harp4162', password=u'temp001')
                # Re-enum to pick up instructor
                publish_ou_course_entries()
        _create()

    @classmethod
    def tearDown(cls):
        # Must implement!
        gsm = component.getGlobalSiteManager()
        gsm.unregisterUtility(cls.__new_library, IContentPackageLibrary)
        gsm.registerUtility(cls.__old_library, IContentPackageLibrary)

        components = gsm.getUtility(IComponents, name='platform.ou.edu')
        catalog = components.getUtility(ICourseCatalog)
        catalog.clear()

        global_catalog = gsm.getUtility(ICourseCatalog)
        global_catalog.clear()

        del cls.__old_library
        del cls.__new_library
        gc.collect()

    @classmethod
    def testSetUp(cls, test=None):
        pass

    @classmethod
    def testTearDown(cls):
        pass


from nti.testing.layers import find_test

from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin

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

    @classmethod
    def testTearDown(cls):
        pass
