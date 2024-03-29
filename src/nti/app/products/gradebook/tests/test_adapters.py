#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that

import unittest

from zope import interface

from zope.dublincore.interfaces import IWriteZopeDublinCore

from nti.contenttypes.courses.courses import CourseInstance

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeChangeContainer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.containers.containers import LastModifiedBTreeContainer


class TestAdapters(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    @WithMockDSTrans
    def test_course_instance(self):
        ci = CourseInstance()
        gb = IGradeBook(ci, None)
        assert_that(gb, is_not(none()))

    def test_zdc_gradebook_entry(self):
        entry = GradeBookEntry()
        assert_that(IWriteZopeDublinCore(entry, None), none())

    def test_zdc_grade_change_container(self):
        container = LastModifiedBTreeContainer()
        interface.alsoProvides(container, IGradeChangeContainer)
        assert_that(IWriteZopeDublinCore(container, None), none())
