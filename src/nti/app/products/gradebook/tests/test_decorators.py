#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import not_none
from hamcrest import has_items
from hamcrest import assert_that
from hamcrest import has_property

import unittest

from nti.contenttypes.courses.courses import CourseInstance

from nti.app.products.gradebook.decorators import _CourseInstanceGradebookLinkDecorator

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestDecorators(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    @WithMockDSTrans
    def test_gradebook(self):
        ci = CourseInstance()
        result = {}
        decorator = _CourseInstanceGradebookLinkDecorator(ci, None)
        decorator.course = ci
        decorator._do_decorate_external(ci, result)

        gradebook = result.get('GradeBook')

        assert_that(gradebook, not_none())
        links = gradebook['Links']
        assert_that(links,
                    has_items(has_property('rel', 'GradeBookSummary'),
                              has_property('rel', 'SetGrade'),
                              has_property('rel', 'ExportContents')))
